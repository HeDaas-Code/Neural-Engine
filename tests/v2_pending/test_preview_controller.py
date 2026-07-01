"""v4-03 · PreviewController 实时预览 + 断点调试测试（#111）。

验证 issue #111 验收点：
- BreakpointManager：线程安全断点集合（add/remove/has/toggle/clear/list）
- PreviewController：worker 线程跑 Executor + 跨线程暂停/继续/单步/停止
- Executor before_block 钩子：块级前置回调（默认 None 不影响 v0/v1/v2/v3）
- 断点命中：before_block 检查 → Event.wait() 暂停 → resume/step/stop
- 状态快照：get_snapshot() 返回 block_id + vars + path + status 防御性拷贝
- on_paused / on_finished 回调
"""
from __future__ import annotations

import os
import sys
import time
import threading
from pathlib import Path

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")

from core.engine.ast_nodes import Story, Block, BlockLocation, IdMeta, IdEnd, NextDecl, Start, End, Text
from core.engine.executor import Executor, GameState, MemoryEventSink, MemoryInputSink
from core.engine.protocol import TextEvt, PromptInputEvt, UserInputCmd
from editor.preview_controller import (
    BreakpointManager, PreviewController,
    STATUS_IDLE, STATUS_RUNNING, STATUS_PAUSED, STATUS_STOPPED, STATUS_ERROR,
)
from editor.dsl_sync import parse_source


# ═══════════════════════════════════════════════════════════════════════
# 辅助：构造 Story + 等待状态 + Sink
# ═══════════════════════════════════════════════════════════════════════


def _make_block(node_id: str, next_target: str | None = None, body_texts=(),
                is_end: bool = False) -> Block:
    """构造简单块（id:node_id + 可选 bare next + body Text 列表 + 可选 id:end 标记）。"""
    meta: tuple = (IdMeta(id=node_id, lineno=1),)
    if is_end:
        meta = (IdMeta(id=node_id, lineno=1), IdEnd(x=None, route_chapter=None, lineno=1))
    next_table = (NextDecl(var_name=None, target_id=next_target),) if next_target else ()
    body = [Start()] + [Text(t) for t in body_texts] + [End()]
    return Block(meta=meta, next_table=next_table, body=tuple(body), loc=BlockLocation(lineno=1, col=1))


def _linear_story() -> Story:
    """3 块线性 Story：start → c1 → c2（无 In，纯 Text，c2 为 ending）。"""
    return Story(blocks=(
        _make_block("start", next_target="c1", body_texts=["开始。"]),
        _make_block("c1", next_target="c2", body_texts=["中间。"]),
        _make_block("c2", body_texts=["结束。"], is_end=True),
    ))


def _story_with_input() -> Story:
    """带 In 节点的 Story（需 MemoryInputSink 提供输入，c2 为 ending）。"""
    src = (
        "```neon\nid:start\nnext: c1\nnode start\n开始。\nnode end\n```\n\n"
        "```neon\nid:c1\nnext: c2\nnode start\nnode in → pick\nnode echo pick\nnode end\n```\n\n"
        "```neon\nid:c2\nid:end\nnode start\n结束。\nnode end\n```\n"
    )
    return parse_source(src)


def _wait_for_status(ctrl: PreviewController, status: str, timeout: float = 2.0) -> bool:
    """轮询等待 ctrl.status == status（测试用，避免 flaky）。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if ctrl.status == status:
            return True
        time.sleep(0.005)
    return False


class _CollectSink(MemoryInputSink):
    """收集 TextEvt 内容 + 提供预设输入的 sink。"""

    def __init__(self, inputs=None):
        super().__init__(inputs)
        self.texts: list[str] = []

    def put_evt(self, evt) -> None:
        super().put_evt(evt)
        if isinstance(evt, TextEvt):
            self.texts.append(evt.content)


class _BlockingInputSink:
    """阻塞式输入 sink：get_cmd 阻塞直到 submit 被调用（测试 manual pause 用）。

    用于让 worker 线程在 In 节点阻塞，主线程在此期间发控制命令。
    """

    def __init__(self):
        self._cmd: str | None = None
        self._event = threading.Event()
        self.texts: list[str] = []
        self.events: list = []

    def put_evt(self, evt) -> None:
        self.events.append(evt)
        if isinstance(evt, TextEvt):
            self.texts.append(evt.content)

    def get_cmd(self):
        self._event.wait()
        self._event.clear()
        return UserInputCmd(value=self._cmd)

    def submit(self, value: str) -> None:
        """提供输入值，唤醒阻塞的 get_cmd。"""
        self._cmd = value
        self._event.set()


# ═══════════════════════════════════════════════════════════════════════
# 1. BreakpointManager
# ═══════════════════════════════════════════════════════════════════════


def test_bp_add_new():
    bpm = BreakpointManager()
    assert bpm.add("c1") is True
    assert bpm.has("c1") is True


def test_bp_add_duplicate_returns_false():
    bpm = BreakpointManager()
    bpm.add("c1")
    assert bpm.add("c1") is False


def test_bp_remove_existing():
    bpm = BreakpointManager()
    bpm.add("c1")
    assert bpm.remove("c1") is True
    assert bpm.has("c1") is False


def test_bp_remove_nonexistent_returns_false():
    bpm = BreakpointManager()
    assert bpm.remove("nope") is False


def test_bp_toggle_add_then_remove():
    bpm = BreakpointManager()
    assert bpm.toggle("c1") is True   # 添加
    assert bpm.toggle("c1") is False  # 移除
    assert bpm.has("c1") is False


def test_bp_clear_returns_count():
    bpm = BreakpointManager()
    bpm.add("a")
    bpm.add("b")
    assert bpm.clear() == 2
    assert bpm.list() == []


def test_bp_list_sorted_copy():
    bpm = BreakpointManager()
    bpm.add("c")
    bpm.add("a")
    bpm.add("b")
    result = bpm.list()
    assert result == ["a", "b", "c"]
    # 修改返回值不影响内部
    result.append("d")
    assert bpm.list() == ["a", "b", "c"]


def test_bp_concurrent_add_safe():
    """多线程并发 add 不丢断点（线程安全 smoke）。"""
    bpm = BreakpointManager()

    def worker(prefix: str):
        for i in range(20):
            bpm.add(f"{prefix}_{i}")

    threads = [threading.Thread(target=worker, args=(p,)) for p in ("a", "b", "c")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # 3 * 20 = 60 个断点
    assert len(bpm.list()) == 60


# ═══════════════════════════════════════════════════════════════════════
# 2. PreviewController 基础
# ═══════════════════════════════════════════════════════════════════════


def test_ctrl_initial_state():
    ctrl = PreviewController(_linear_story(), _CollectSink())
    assert ctrl.status == STATUS_IDLE
    assert ctrl.is_running is False
    assert ctrl.is_paused is False
    snap = ctrl.get_snapshot()
    assert snap["block_id"] is None
    assert snap["vars"] == {}
    assert snap["status"] == STATUS_IDLE


def test_ctrl_run_completes_without_breakpoint():
    """无断点 → run → 自然完成 → STOPPED。"""
    sink = _CollectSink()
    ctrl = PreviewController(_linear_story(), sink)
    assert ctrl.run() is True
    assert _wait_for_status(ctrl, STATUS_STOPPED, timeout=2.0)
    # 3 块的 Text 都被收集
    assert "开始。" in sink.texts
    assert "中间。" in sink.texts
    assert "结束。" in sink.texts


def test_ctrl_run_duplicate_returns_false():
    """运行中/暂停中再 run → False（用断点保持 PAUSED 状态避免竞态）。"""
    ctrl = PreviewController(_linear_story(), _CollectSink())
    ctrl.set_breakpoint("c1")
    ctrl.run()
    assert _wait_for_status(ctrl, STATUS_PAUSED, timeout=2.0)
    # PAUSED 状态再 run → False
    assert ctrl.run() is False
    ctrl.stop()


def test_ctrl_get_snapshot_returns_copy():
    """get_snapshot 返回防御性拷贝，修改不影响内部。"""
    ctrl = PreviewController(_linear_story(), _CollectSink())
    snap = ctrl.get_snapshot()
    snap["vars"]["hack"] = "evil"
    snap2 = ctrl.get_snapshot()
    assert "hack" not in snap2["vars"]


def test_ctrl_breakpoint_manager_property():
    bpm = BreakpointManager()
    ctrl = PreviewController(_linear_story(), _CollectSink(), breakpoint_manager=bpm)
    assert ctrl.breakpoint_manager is bpm


# ═══════════════════════════════════════════════════════════════════════
# 3. 断点命中
# ═══════════════════════════════════════════════════════════════════════


def test_ctrl_breakpoint_hit_pauses():
    """设断点 c1 → run → 命中 c1 → PAUSED。"""
    sink = _CollectSink()
    ctrl = PreviewController(_linear_story(), sink)
    ctrl.set_breakpoint("c1")
    ctrl.run()
    assert _wait_for_status(ctrl, STATUS_PAUSED, timeout=2.0)
    # 命中 c1，start 已执行（"开始。" 已输出），c1 未执行
    assert "开始。" in sink.texts
    assert "中间。" not in sink.texts
    ctrl.stop()


def test_ctrl_breakpoint_snapshot_correct():
    """断点命中时 get_snapshot 返回正确 block_id。"""
    ctrl = PreviewController(_linear_story(), _CollectSink())
    ctrl.set_breakpoint("c1")
    ctrl.run()
    assert _wait_for_status(ctrl, STATUS_PAUSED, timeout=2.0)
    snap = ctrl.get_snapshot()
    assert snap["block_id"] == "c1"
    assert snap["status"] == STATUS_PAUSED
    ctrl.stop()


def test_ctrl_breakpoint_resume_completes():
    """断点命中 → resume → 继续到完成。"""
    sink = _CollectSink()
    ctrl = PreviewController(_linear_story(), sink)
    ctrl.set_breakpoint("c1")
    ctrl.run()
    assert _wait_for_status(ctrl, STATUS_PAUSED, timeout=2.0)
    assert ctrl.resume() is True
    assert _wait_for_status(ctrl, STATUS_STOPPED, timeout=2.0)
    # resume 后 c1/c2 都执行了
    assert "中间。" in sink.texts
    assert "结束。" in sink.texts


def test_ctrl_no_breakpoint_runs_to_end():
    """无断点 → run → 直接到 STOPPED（不停在中间）。"""
    ctrl = PreviewController(_linear_story(), _CollectSink())
    ctrl.run()
    assert _wait_for_status(ctrl, STATUS_STOPPED, timeout=2.0)
    # 不应出现 PAUSED
    assert ctrl.status != STATUS_PAUSED


def test_ctrl_breakpoint_on_paused_callback():
    """断点命中 → on_paused 回调被调用（block_id, snapshot）。"""
    paused_calls: list[tuple] = []

    def on_paused(block_id, snapshot):
        paused_calls.append((block_id, dict(snapshot)))

    ctrl = PreviewController(_linear_story(), _CollectSink(), on_paused=on_paused)
    ctrl.set_breakpoint("c2")
    ctrl.run()
    assert _wait_for_status(ctrl, STATUS_PAUSED, timeout=2.0)
    # 等回调被调用
    deadline = time.time() + 1.0
    while time.time() < deadline and not paused_calls:
        time.sleep(0.005)
    assert len(paused_calls) == 1
    assert paused_calls[0][0] == "c2"
    assert "block_id" in paused_calls[0][1]
    ctrl.stop()


# ═══════════════════════════════════════════════════════════════════════
# 4. 单步执行
# ═══════════════════════════════════════════════════════════════════════


def test_ctrl_step_one_block_at_a_time():
    """step() 单步：每次只执行 1 块就暂停。"""
    sink = _CollectSink()
    ctrl = PreviewController(_linear_story(), sink)
    # 用断点先停在 start 之后（c1 前）
    # 实际上 start 块也会触发 before_block，所以先设断点在 start
    ctrl.set_breakpoint("start")
    ctrl.run()
    assert _wait_for_status(ctrl, STATUS_PAUSED, timeout=2.0)
    # 在 start 块前暂停，start 未执行
    assert "开始。" not in sink.texts
    # step → 执行 start → 下块前暂停
    assert ctrl.step() is True
    assert _wait_for_status(ctrl, STATUS_PAUSED, timeout=2.0)
    assert "开始。" in sink.texts
    assert "中间。" not in sink.texts
    # step → 执行 c1 → 下块前暂停
    assert ctrl.step() is True
    assert _wait_for_status(ctrl, STATUS_PAUSED, timeout=2.0)
    assert "中间。" in sink.texts
    assert "结束。" not in sink.texts
    # step → 执行 c2 → 结束
    assert ctrl.step() is True
    assert _wait_for_status(ctrl, STATUS_STOPPED, timeout=2.0)
    assert "结束。" in sink.texts


def test_ctrl_step_returns_false_when_not_paused():
    ctrl = PreviewController(_linear_story(), _CollectSink())
    assert ctrl.step() is False  # IDLE 状态


def test_ctrl_resume_clears_step_mode():
    """step 模式下 resume → 清 step → 连续运行到结束。"""
    sink = _CollectSink()
    ctrl = PreviewController(_linear_story(), sink)
    ctrl.set_breakpoint("start")
    ctrl.run()
    assert _wait_for_status(ctrl, STATUS_PAUSED, timeout=2.0)
    # step 一次
    ctrl.step()
    assert _wait_for_status(ctrl, STATUS_PAUSED, timeout=2.0)
    # resume → 连续运行（不再单步暂停）
    ctrl.resume()
    assert _wait_for_status(ctrl, STATUS_STOPPED, timeout=2.0)
    # 全部执行完
    assert "结束。" in sink.texts


# ═══════════════════════════════════════════════════════════════════════
# 5. 暂停 / 停止
# ═══════════════════════════════════════════════════════════════════════


def test_ctrl_pause_requests_pause_at_next_block():
    """pause() 请求暂停 → 下次 before_block 生效。

    用 _BlockingInputSink 让 worker 在 In 节点阻塞，
    主线程在此期间发 pause，然后 submit 解阻塞，worker 在下块前暂停。
    """
    sink = _BlockingInputSink()
    ctrl = PreviewController(_story_with_input(), sink)
    ctrl.run()
    # 等 worker 阻塞在 c1 的 In 节点（get_cmd）
    deadline = time.time() + 2.0
    while time.time() < deadline and not any("开始" in t for t in sink.texts):
        time.sleep(0.01)
    assert any("开始" in t for t in sink.texts)  # start 块已执行
    # 此时 worker 阻塞在 c1.In → 发 pause 请求
    assert ctrl.pause() is True
    # 提交输入解除 get_cmd 阻塞 → worker 执行完 c1 → before_block(c2) 命中 manual pause
    sink.submit("1")
    assert _wait_for_status(ctrl, STATUS_PAUSED, timeout=2.0)
    snap = ctrl.get_snapshot()
    assert snap["block_id"] == "c2"
    ctrl.stop()


def test_ctrl_pause_with_input_story():
    """带 In 节点的 story → pause 在 In 后下块前生效（用阻塞 sink 确保确定）。"""
    sink = _BlockingInputSink()
    ctrl = PreviewController(_story_with_input(), sink)
    ctrl.run()
    # 等 worker 阻塞在 c1 的 In 节点
    deadline = time.time() + 2.0
    while time.time() < deadline and not any("开始" in t for t in sink.texts):
        time.sleep(0.01)
    ctrl.pause()
    sink.submit("1")
    assert _wait_for_status(ctrl, STATUS_PAUSED, timeout=2.0)
    ctrl.stop()


def test_ctrl_stop_terminates_worker():
    """stop() → worker 线程退出 → STOPPED（用断点保持 PAUSED 再 stop，避免竞态）。"""
    ctrl = PreviewController(_story_with_input(), _CollectSink(inputs=["1"]))
    ctrl.set_breakpoint("c1")
    ctrl.run()
    assert _wait_for_status(ctrl, STATUS_PAUSED, timeout=2.0)
    assert ctrl.stop() is True
    assert ctrl.status == STATUS_STOPPED
    assert ctrl.join(timeout=1.0) is True


def test_ctrl_stop_from_paused():
    """暂停状态下 stop() 也能停止。"""
    ctrl = PreviewController(_linear_story(), _CollectSink())
    ctrl.set_breakpoint("c1")
    ctrl.run()
    assert _wait_for_status(ctrl, STATUS_PAUSED, timeout=2.0)
    assert ctrl.stop() is True
    assert ctrl.status == STATUS_STOPPED


def test_ctrl_pause_stop_return_false_when_idle():
    ctrl = PreviewController(_linear_story(), _CollectSink())
    assert ctrl.pause() is False
    assert ctrl.stop() is False
    assert ctrl.resume() is False


# ═══════════════════════════════════════════════════════════════════════
# 6. on_finished 回调
# ═══════════════════════════════════════════════════════════════════════


def test_ctrl_on_finished_completed():
    """自然完成 → on_finished("completed")。"""
    finished_calls: list[str] = []

    def on_finished(reason):
        finished_calls.append(reason)

    ctrl = PreviewController(_linear_story(), _CollectSink(), on_finished=on_finished)
    ctrl.run()
    ctrl.join(timeout=2.0)
    deadline = time.time() + 1.0
    while time.time() < deadline and not finished_calls:
        time.sleep(0.005)
    assert finished_calls == ["completed"]


def test_ctrl_on_finished_stopped():
    """stop() → on_finished("stopped")（用断点保持 PAUSED 再 stop，避免竞态）。"""
    finished_calls: list[str] = []

    def on_finished(reason):
        finished_calls.append(reason)

    ctrl = PreviewController(_story_with_input(), _CollectSink(inputs=["1"]),
                             on_finished=on_finished)
    ctrl.set_breakpoint("c1")
    ctrl.run()
    assert _wait_for_status(ctrl, STATUS_PAUSED, timeout=2.0)
    ctrl.stop()
    deadline = time.time() + 1.0
    while time.time() < deadline and not finished_calls:
        time.sleep(0.005)
    assert "stopped" in finished_calls


def test_ctrl_on_finished_error():
    """执行异常 → on_finished("error: ...") + STATUS_ERROR。"""
    # 构造一个会抛异常的 sink（get_cmd 时抛错模拟 In 节点无输入）
    class _ErrorSink:
        def put_evt(self, evt): pass
        def get_cmd(self): raise RuntimeError("boom")

    finished_calls: list[str] = []

    def on_finished(reason):
        finished_calls.append(reason)

    ctrl = PreviewController(_story_with_input(), _ErrorSink(), on_finished=on_finished)
    ctrl.run()
    ctrl.join(timeout=2.0)
    assert ctrl.status == STATUS_ERROR
    assert len(finished_calls) == 1
    assert finished_calls[0].startswith("error")


# ═══════════════════════════════════════════════════════════════════════
# 7. Executor before_block 钩子（直接测 Executor）
# ═══════════════════════════════════════════════════════════════════════


def test_executor_before_block_called_per_block():
    """Executor 直接接 before_block → 每块前调用一次。"""
    calls: list[str] = []

    def hook(block, state):
        bid = next((m.id for m in block.meta if hasattr(m, "id")), "?")
        calls.append(bid)

    story = _linear_story()
    exe = Executor(story, MemoryEventSink(), before_block=hook)
    exe.run()
    assert calls == ["start", "c1", "c2"]


def test_executor_before_block_none_is_noop():
    """before_block=None（默认）→ 不影响 v0/v1/v2/v3 行为（回归）。"""
    story = _linear_story()
    sink = MemoryEventSink()
    exe = Executor(story, sink)  # 不传 before_block
    exe.run()
    # 正常执行，无异常
    assert exe.state.current_block_id == "c2"


def test_executor_before_block_receives_state():
    """before_block 收到 GameState，可在块执行前读/改 vars。"""
    seen_vars: list[dict] = []

    def hook(block, state):
        seen_vars.append(dict(state.vars))

    story = _story_with_input()
    exe = Executor(story, MemoryInputSink(["1"]), before_block=hook)
    exe.run()
    # start 块前 vars 空；c1 块前 vars 空（In 在 c1 内执行）；c2 块前 vars 有 pick
    assert seen_vars[0] == {}            # before start
    assert seen_vars[1] == {}            # before c1（pick 尚未赋值）
    assert seen_vars[2] == {"pick": 1}   # before c2（c1 的 In 已执行）


# ═══════════════════════════════════════════════════════════════════════
# 8. 模块导入
# ═══════════════════════════════════════════════════════════════════════


def test_preview_controller_module_exports():
    """preview_controller 公开 API 齐全。"""
    from editor import preview_controller as pc
    for name in ("BreakpointManager", "PreviewController",
                 "STATUS_IDLE", "STATUS_RUNNING", "STATUS_PAUSED",
                 "STATUS_STOPPED", "STATUS_ERROR"):
        assert hasattr(pc, name)
