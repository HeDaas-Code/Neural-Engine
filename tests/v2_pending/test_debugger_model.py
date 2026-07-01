"""v4-06 · DebuggerModel 调试器数据模型测试（#114）。

验证 issue #114 验收点：
- 变量查看器：get_variables（实时）+ get_variable_history（暂停点快照）
- 执行路径 / 调用栈：get_execution_path + get_call_stack
- 断点列表管理：list/add/remove/toggle/has/clear（委托 BreakpointManager）
- 与 PreviewController 集成：on_block_visit/on_paused/on_finished 回调接线
- 调试事件日志：started/paused/breakpoint/resumed/step/stopped/completed/error
- 监视变量（watch list）：add/remove/get_watched_variables
- 表达式求值：evaluate_expression（ExprDispatcher 调度）
- 历史裁剪：max_history 上限保护
"""
from __future__ import annotations

import os
import sys
import time
import threading

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")

from core.engine.ast_nodes import Story, Block, BlockLocation, IdMeta, IdEnd, NextDecl, Start, End, Text
from core.engine.executor import GameState, MemoryInputSink
from core.engine.protocol import TextEvt, UserInputCmd
from editor.preview_controller import (
    BreakpointManager, PreviewController,
    STATUS_IDLE, STATUS_RUNNING, STATUS_PAUSED, STATUS_STOPPED, STATUS_ERROR,
)
from editor.dsl_sync import parse_source
from editor.debugger_model import (
    DebuggerModel, VariableSnapshot, DebugEvent,
    EVENT_STARTED, EVENT_PAUSED, EVENT_BREAKPOINT,
    EVENT_RESUMED, EVENT_STEP, EVENT_STOPPED,
    EVENT_COMPLETED, EVENT_ERROR,
    DEFAULT_MAX_HISTORY,
)


# ═══════════════════════════════════════════════════════════════════════
# 辅助：构造 Story + 等待状态 + Sink（与 test_preview_controller 同模式）
# ═══════════════════════════════════════════════════════════════════════


def _make_block(node_id: str, next_target: str | None = None, body_texts=(),
                is_end: bool = False) -> Block:
    """构造简单块（id:node_id + 可选 bare next + body Text 列表 + 可选 id:end 标记）。"""
    meta: tuple = (IdMeta(id=node_id, lineno=1),)
    if is_end:
        meta = (IdMeta(id=node_id, lineno=1), IdEnd(x=None, route_chapter=None, lineno=1))
    next_table = (NextDecl(var_name=None, target_id=next_target),) if next_target else ()
    body = [Start()] + [Text(t) for t in body_texts] + [End()]
    return Block(meta=meta, next_table=next_table, body=tuple(body),
                 loc=BlockLocation(lineno=1, col=1))


def _linear_story() -> Story:
    """3 块线性 Story：start → c1 → c2（无 In，纯 Text，c2 为 ending）。"""
    return Story(blocks=(
        _make_block("start", next_target="c1", body_texts=["开始。"]),
        _make_block("c1", next_target="c2", body_texts=["中间。"]),
        _make_block("c2", body_texts=["结束。"], is_end=True),
    ))


def _story_with_input() -> Story:
    """带 In 节点的 Story（c1 设变量 pick，c2 为 ending）。"""
    src = (
        "```neon\nid:start\nnext: c1\nnode start\n开始。\nnode end\n```\n\n"
        "```neon\nid:c1\nnext: c2\nnode start\nnode in → pick\nnode echo pick\nnode end\n```\n\n"
        "```neon\nid:c2\nid:end\nnode start\n结束。\nnode end\n```\n"
    )
    return parse_source(src)


class _CollectSink(MemoryInputSink):
    """收集 TextEvt 内容 + 提供预设输入的 sink。"""

    def __init__(self, inputs=None):
        super().__init__(inputs)
        self.texts: list[str] = []

    def put_evt(self, evt) -> None:
        super().put_evt(evt)
        if isinstance(evt, TextEvt):
            self.texts.append(evt.content)


def _wait_for_status(dbg: DebuggerModel, status: str, timeout: float = 2.0) -> bool:
    """轮询等待 dbg.status == status（测试用，避免 flaky）。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if dbg.status == status:
            return True
        time.sleep(0.005)
    return False


def _wait_for_event(dbg: DebuggerModel, kind: str, timeout: float = 2.0) -> bool:
    """轮询等待指定类型事件出现。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        for e in dbg.get_events():
            if e.kind == kind:
                return True
        time.sleep(0.005)
    return False


def _wait_for_latest_snapshot(dbg: DebuggerModel, block_id: str,
                              timeout: float = 2.0) -> bool:
    """轮询等待变量历史最新一条为指定 block_id（确保 on_paused 回调已完成）。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        h = dbg.get_variable_history()
        if h and h[-1].block_id == block_id:
            return True
        time.sleep(0.005)
    return False


def _event_kinds(dbg: DebuggerModel) -> list[str]:
    """取所有事件类型（按顺序）。"""
    return [e.kind for e in dbg.get_events()]


# ═══════════════════════════════════════════════════════════════════════
# 1. 构造 + 属性
# ═══════════════════════════════════════════════════════════════════════


def test_construct_basic():
    dbg = DebuggerModel(_linear_story(), _CollectSink())
    assert dbg.status == STATUS_IDLE
    assert dbg.is_running is False
    assert dbg.is_paused is False
    assert dbg.breakpoint_count == 0
    assert dbg.max_history == DEFAULT_MAX_HISTORY


def test_construct_with_breakpoint_manager():
    bpm = BreakpointManager()
    bpm.add("c1")
    dbg = DebuggerModel(_linear_story(), _CollectSink(), breakpoint_manager=bpm)
    # 委托到同一个 bpm
    assert dbg.preview_controller.breakpoint_manager is bpm
    assert dbg.has_breakpoint("c1") is True
    assert dbg.list_breakpoints() == ["c1"]


def test_construct_invalid_max_history():
    with pytest.raises(ValueError, match="max_history"):
        DebuggerModel(_linear_story(), _CollectSink(), max_history=0)
    with pytest.raises(ValueError):
        DebuggerModel(_linear_story(), _CollectSink(), max_history=-5)


def test_preview_controller_exposed():
    dbg = DebuggerModel(_linear_story(), _CollectSink())
    assert isinstance(dbg.preview_controller, PreviewController)


def test_max_history_property():
    dbg = DebuggerModel(_linear_story(), _CollectSink(), max_history=50)
    assert dbg.max_history == 50


# ═══════════════════════════════════════════════════════════════════════
# 2. 断点管理（委托 BreakpointManager）
# ═══════════════════════════════════════════════════════════════════════


def test_breakpoint_add_has():
    dbg = DebuggerModel(_linear_story(), _CollectSink())
    assert dbg.add_breakpoint("c1") is True
    assert dbg.has_breakpoint("c1") is True
    assert dbg.breakpoint_count == 1


def test_breakpoint_add_duplicate_returns_false():
    dbg = DebuggerModel(_linear_story(), _CollectSink())
    dbg.add_breakpoint("c1")
    assert dbg.add_breakpoint("c1") is False


def test_breakpoint_remove():
    dbg = DebuggerModel(_linear_story(), _CollectSink())
    dbg.add_breakpoint("c1")
    assert dbg.remove_breakpoint("c1") is True
    assert dbg.has_breakpoint("c1") is False
    assert dbg.remove_breakpoint("nope") is False


def test_breakpoint_toggle():
    dbg = DebuggerModel(_linear_story(), _CollectSink())
    assert dbg.toggle_breakpoint("c1") is True   # 添加
    assert dbg.toggle_breakpoint("c1") is False  # 移除


def test_breakpoint_clear():
    dbg = DebuggerModel(_linear_story(), _CollectSink())
    dbg.add_breakpoint("a")
    dbg.add_breakpoint("b")
    assert dbg.clear_breakpoints() == 2
    assert dbg.list_breakpoints() == []
    assert dbg.breakpoint_count == 0


def test_breakpoint_list_sorted_copy():
    dbg = DebuggerModel(_linear_story(), _CollectSink())
    dbg.add_breakpoint("c")
    dbg.add_breakpoint("a")
    dbg.add_breakpoint("b")
    result = dbg.list_breakpoints()
    assert result == ["a", "b", "c"]
    # 修改返回值不影响内部
    result.append("d")
    assert dbg.list_breakpoints() == ["a", "b", "c"]


# ═══════════════════════════════════════════════════════════════════════
# 3. 变量查看
# ═══════════════════════════════════════════════════════════════════════


def test_get_variables_initial_empty():
    dbg = DebuggerModel(_linear_story(), _CollectSink())
    assert dbg.get_variables() == {}


def test_get_variables_returns_copy():
    dbg = DebuggerModel(_linear_story(), _CollectSink())
    vars_view = dbg.get_variables()
    vars_view["hack"] = "evil"
    assert "hack" not in dbg.get_variables()


def test_get_variable_history_initial_empty():
    dbg = DebuggerModel(_linear_story(), _CollectSink())
    assert dbg.get_variable_history() == []


def test_get_variables_at_breakpoint():
    """带 In 节点的 story：断点 c2 命中时 vars 含 pick。"""
    sink = _CollectSink(inputs=["42"])
    dbg = DebuggerModel(_story_with_input(), sink)
    dbg.add_breakpoint("c2")
    dbg.run()
    assert _wait_for_status(dbg, STATUS_PAUSED, timeout=2.0)
    assert _wait_for_event(dbg, EVENT_BREAKPOINT, timeout=2.0)
    # c1 的 In 节点设了 pick=42，c2 命中时 vars 反映
    assert dbg.get_variables() == {"pick": 42}
    dbg.stop()


def test_get_variable_history_at_pause():
    """断点命中 → 变量历史记录 1 条快照。"""
    sink = _CollectSink(inputs=["42"])
    dbg = DebuggerModel(_story_with_input(), sink)
    dbg.add_breakpoint("c2")
    dbg.run()
    assert _wait_for_status(dbg, STATUS_PAUSED, timeout=2.0)
    assert _wait_for_event(dbg, EVENT_BREAKPOINT, timeout=2.0)
    history = dbg.get_variable_history()
    assert len(history) == 1
    snap = history[0]
    assert isinstance(snap, VariableSnapshot)
    assert snap.block_id == "c2"
    assert snap.variables == {"pick": 42}
    dbg.stop()


def test_get_variable_history_limit():
    """step 多次后 limit 取最近 N 条。"""
    sink = _CollectSink()
    dbg = DebuggerModel(_linear_story(), sink)
    dbg.add_breakpoint("start")
    dbg.run()
    assert _wait_for_status(dbg, STATUS_PAUSED, timeout=2.0)
    dbg.step()
    assert _wait_for_status(dbg, STATUS_PAUSED, timeout=2.0)  # c1
    dbg.step()
    assert _wait_for_status(dbg, STATUS_PAUSED, timeout=2.0)  # c2
    # 等第 3 次 on_paused 回调完成（c2 快照写入）
    assert _wait_for_latest_snapshot(dbg, "c2", timeout=2.0)
    # 3 次暂停（start / c1 / c2）
    assert len(dbg.get_variable_history()) == 3
    assert len(dbg.get_variable_history(limit=2)) == 2
    # 最近 1 条是 c2
    last = dbg.get_variable_history(limit=1)
    assert len(last) == 1
    assert last[0].block_id == "c2"
    dbg.stop()


def test_clear_history():
    """clear_history 清空变量历史 + 执行路径，保留事件。"""
    sink = _CollectSink()
    dbg = DebuggerModel(_linear_story(), sink)
    dbg.add_breakpoint("c1")
    dbg.run()
    assert _wait_for_status(dbg, STATUS_PAUSED, timeout=2.0)
    assert _wait_for_event(dbg, EVENT_BREAKPOINT, timeout=2.0)
    assert len(dbg.get_variable_history()) == 1
    assert len(dbg.get_execution_path()) >= 1
    dbg.clear_history()
    assert dbg.get_variable_history() == []
    assert dbg.get_execution_path() == []
    # 事件日志保留
    assert len(dbg.get_events()) >= 1
    dbg.stop()


# ═══════════════════════════════════════════════════════════════════════
# 4. 执行路径 / 调用栈
# ═══════════════════════════════════════════════════════════════════════


def test_execution_path_initial_empty():
    dbg = DebuggerModel(_linear_story(), _CollectSink())
    assert dbg.get_execution_path() == []


def test_execution_path_records_blocks():
    """断点 c1 命中 → 路径含 start + c1（每个块都记录）。"""
    sink = _CollectSink()
    dbg = DebuggerModel(_linear_story(), sink)
    dbg.add_breakpoint("c1")
    dbg.run()
    assert _wait_for_status(dbg, STATUS_PAUSED, timeout=2.0)
    assert _wait_for_event(dbg, EVENT_BREAKPOINT, timeout=2.0)
    # start 进入 → c1 进入（暂停）。c1 body 未执行
    assert dbg.get_execution_path() == ["start", "c1"]
    assert dbg.get_current_block_id() == "c1"
    dbg.stop()


def test_execution_path_full_run():
    """无断点跑完 → 路径含全部 3 块。"""
    sink = _CollectSink()
    dbg = DebuggerModel(_linear_story(), sink)
    dbg.run()
    dbg.join(timeout=2.0)
    assert dbg.status == STATUS_STOPPED
    assert dbg.get_execution_path() == ["start", "c1", "c2"]


def test_execution_path_returns_copy():
    sink = _CollectSink()
    dbg = DebuggerModel(_linear_story(), sink)
    dbg.add_breakpoint("c1")
    dbg.run()
    assert _wait_for_status(dbg, STATUS_PAUSED, timeout=2.0)
    path = dbg.get_execution_path()
    path.append("hack")
    assert dbg.get_execution_path() == ["start", "c1"]
    dbg.stop()


def test_call_stack_depth():
    """调用栈返回最近 N 个块。"""
    sink = _CollectSink()
    dbg = DebuggerModel(_linear_story(), sink)
    dbg.run()
    dbg.join(timeout=2.0)
    assert dbg.get_call_stack(10) == ["start", "c1", "c2"]
    assert dbg.get_call_stack(2) == ["c1", "c2"]
    assert dbg.get_call_stack(1) == ["c2"]


def test_call_stack_depth_zero():
    dbg = DebuggerModel(_linear_story(), _CollectSink())
    assert dbg.get_call_stack(0) == []


def test_call_stack_negative_raises():
    dbg = DebuggerModel(_linear_story(), _CollectSink())
    with pytest.raises(ValueError, match="depth"):
        dbg.get_call_stack(-1)


# ═══════════════════════════════════════════════════════════════════════
# 5. 监视变量（watch list）
# ═══════════════════════════════════════════════════════════════════════


def test_add_watch_new():
    dbg = DebuggerModel(_linear_story(), _CollectSink())
    assert dbg.add_watch("score") is True
    assert dbg.get_watch_list() == ["score"]


def test_add_watch_duplicate_returns_false():
    dbg = DebuggerModel(_linear_story(), _CollectSink())
    dbg.add_watch("score")
    assert dbg.add_watch("score") is False
    assert dbg.get_watch_list() == ["score"]


def test_add_watch_empty_raises():
    dbg = DebuggerModel(_linear_story(), _CollectSink())
    with pytest.raises(ValueError, match="empty"):
        dbg.add_watch("")


def test_remove_watch():
    dbg = DebuggerModel(_linear_story(), _CollectSink())
    dbg.add_watch("score")
    assert dbg.remove_watch("score") is True
    assert dbg.get_watch_list() == []
    assert dbg.remove_watch("score") is False


def test_get_watch_list_returns_copy():
    dbg = DebuggerModel(_linear_story(), _CollectSink())
    dbg.add_watch("a")
    wl = dbg.get_watch_list()
    wl.append("b")
    assert dbg.get_watch_list() == ["a"]


def test_get_watched_variables_values():
    """带变量的 story：监视 pick → 命中时取到值；监视未设置变量 → None。"""
    sink = _CollectSink(inputs=["42"])
    dbg = DebuggerModel(_story_with_input(), sink)
    dbg.add_watch("pick")
    dbg.add_watch("nope")
    dbg.add_breakpoint("c2")
    dbg.run()
    assert _wait_for_status(dbg, STATUS_PAUSED, timeout=2.0)
    assert _wait_for_event(dbg, EVENT_BREAKPOINT, timeout=2.0)
    watched = dbg.get_watched_variables()
    assert watched == {"pick": 42, "nope": None}
    dbg.stop()


def test_get_watched_variables_empty_when_no_watch():
    dbg = DebuggerModel(_linear_story(), _CollectSink())
    assert dbg.get_watched_variables() == {}


# ═══════════════════════════════════════════════════════════════════════
# 6. 事件日志
# ═══════════════════════════════════════════════════════════════════════


def test_events_initial_empty():
    dbg = DebuggerModel(_linear_story(), _CollectSink())
    assert dbg.get_events() == []


def test_events_started_on_run():
    dbg = DebuggerModel(_linear_story(), _CollectSink())
    dbg.run()
    # started 由主线程同步写入，立即可见
    assert _wait_for_event(dbg, EVENT_STARTED, timeout=1.0)
    dbg.stop()


def test_events_breakpoint_hit():
    """断点命中 → started + breakpoint 事件。"""
    sink = _CollectSink()
    dbg = DebuggerModel(_linear_story(), sink)
    dbg.add_breakpoint("c1")
    dbg.run()
    assert _wait_for_status(dbg, STATUS_PAUSED, timeout=2.0)
    assert _wait_for_event(dbg, EVENT_BREAKPOINT, timeout=2.0)
    kinds = _event_kinds(dbg)
    assert EVENT_STARTED in kinds
    assert EVENT_BREAKPOINT in kinds
    # breakpoint 事件关联 c1
    bp_events = [e for e in dbg.get_events() if e.kind == EVENT_BREAKPOINT]
    assert len(bp_events) == 1
    assert bp_events[0].block_id == "c1"
    dbg.stop()


def test_events_paused_for_step():
    """step 暂停（非断点）→ paused 事件。"""
    sink = _CollectSink()
    dbg = DebuggerModel(_linear_story(), sink)
    dbg.add_breakpoint("start")
    dbg.run()
    assert _wait_for_status(dbg, STATUS_PAUSED, timeout=2.0)
    # step 到 c1（c1 无断点 → paused 事件）
    dbg.step()
    assert _wait_for_status(dbg, STATUS_PAUSED, timeout=2.0)
    assert _wait_for_event(dbg, EVENT_PAUSED, timeout=2.0)
    paused_events = [e for e in dbg.get_events() if e.kind == EVENT_PAUSED]
    assert len(paused_events) >= 1
    assert paused_events[-1].block_id == "c1"
    dbg.stop()


def test_events_resumed():
    """resume → resumed 事件。"""
    sink = _CollectSink()
    dbg = DebuggerModel(_linear_story(), sink)
    dbg.add_breakpoint("c1")
    dbg.run()
    assert _wait_for_status(dbg, STATUS_PAUSED, timeout=2.0)
    assert dbg.resume() is True
    assert _wait_for_event(dbg, EVENT_RESUMED, timeout=2.0)
    dbg.join(timeout=2.0)


def test_events_clear():
    dbg = DebuggerModel(_linear_story(), _CollectSink())
    dbg.run()
    assert _wait_for_event(dbg, EVENT_STARTED, timeout=1.0)
    assert len(dbg.get_events()) >= 1
    dbg.clear_events()
    assert dbg.get_events() == []
    dbg.stop()


def test_events_limit():
    sink = _CollectSink()
    dbg = DebuggerModel(_linear_story(), sink)
    dbg.add_breakpoint("start")
    dbg.run()
    assert _wait_for_status(dbg, STATUS_PAUSED, timeout=2.0)
    dbg.step()
    assert _wait_for_status(dbg, STATUS_PAUSED, timeout=2.0)
    dbg.step()
    assert _wait_for_status(dbg, STATUS_PAUSED, timeout=2.0)
    all_events = dbg.get_events()
    assert len(all_events) >= 3
    limited = dbg.get_events(limit=2)
    assert len(limited) == 2
    # 最近 2 条等于全量末尾 2 条
    assert limited == all_events[-2:]
    dbg.stop()


# ═══════════════════════════════════════════════════════════════════════
# 7. 表达式求值
# ═══════════════════════════════════════════════════════════════════════


def test_evaluate_basic_arithmetic():
    dbg = DebuggerModel(_linear_story(), _CollectSink())
    assert dbg.evaluate_expression("1 + 2") == 3
    assert dbg.evaluate_expression("10 * 4") == 40


def test_evaluate_comparison():
    dbg = DebuggerModel(_linear_story(), _CollectSink())
    assert dbg.evaluate_expression("5 > 3") is True
    assert dbg.evaluate_expression("2 > 5") is False


def test_evaluate_with_variables():
    """带变量的 story：命中断点后求值 pick 表达式。"""
    sink = _CollectSink(inputs=["42"])
    dbg = DebuggerModel(_story_with_input(), sink)
    dbg.add_breakpoint("c2")
    dbg.run()
    assert _wait_for_status(dbg, STATUS_PAUSED, timeout=2.0)
    assert _wait_for_event(dbg, EVENT_BREAKPOINT, timeout=2.0)
    assert dbg.evaluate_expression("pick == 42") is True
    assert dbg.evaluate_expression("pick + 8") == 50
    assert dbg.evaluate_expression("pick >= 40") is True
    dbg.stop()


def test_evaluate_empty_raises():
    dbg = DebuggerModel(_linear_story(), _CollectSink())
    with pytest.raises(ValueError, match="empty"):
        dbg.evaluate_expression("")
    with pytest.raises(ValueError, match="empty"):
        dbg.evaluate_expression("   ")


def test_evaluate_does_not_affect_state():
    """求值用快照 vars，不影响执行期状态。"""
    sink = _CollectSink(inputs=["42"])
    dbg = DebuggerModel(_story_with_input(), sink)
    dbg.add_breakpoint("c2")
    dbg.run()
    assert _wait_for_status(dbg, STATUS_PAUSED, timeout=2.0)
    assert _wait_for_event(dbg, EVENT_BREAKPOINT, timeout=2.0)
    before = dbg.get_variables()
    dbg.evaluate_expression("pick + 100")
    after = dbg.get_variables()
    assert before == after == {"pick": 42}
    dbg.stop()


# ═══════════════════════════════════════════════════════════════════════
# 8. 控制集成（run / pause / resume / step / stop）
# ═══════════════════════════════════════════════════════════════════════


def test_run_emits_started():
    dbg = DebuggerModel(_linear_story(), _CollectSink())
    assert dbg.run() is True
    assert _wait_for_event(dbg, EVENT_STARTED, timeout=1.0)
    dbg.join(timeout=2.0)


def test_breakpoint_pause_and_resume_completes():
    """断点命中 → resume → 跑到完成。"""
    sink = _CollectSink()
    dbg = DebuggerModel(_linear_story(), sink)
    dbg.add_breakpoint("c1")
    dbg.run()
    assert _wait_for_status(dbg, STATUS_PAUSED, timeout=2.0)
    assert "开始。" in sink.texts
    assert "中间。" not in sink.texts
    assert dbg.resume() is True
    dbg.join(timeout=2.0)
    assert dbg.status == STATUS_STOPPED
    assert "中间。" in sink.texts
    assert "结束。" in sink.texts


def test_step_execution():
    """step 单步：每次只跑 1 块。"""
    sink = _CollectSink()
    dbg = DebuggerModel(_linear_story(), sink)
    dbg.add_breakpoint("start")
    dbg.run()
    assert _wait_for_status(dbg, STATUS_PAUSED, timeout=2.0)
    assert "开始。" not in sink.texts
    # step → start
    assert dbg.step() is True
    assert _wait_for_status(dbg, STATUS_PAUSED, timeout=2.0)
    assert "开始。" in sink.texts
    assert "中间。" not in sink.texts
    # step → c1
    assert dbg.step() is True
    assert _wait_for_status(dbg, STATUS_PAUSED, timeout=2.0)
    assert "中间。" in sink.texts
    assert "结束。" not in sink.texts
    # step → c2 → 完成
    assert dbg.step() is True
    dbg.join(timeout=2.0)
    assert dbg.status == STATUS_STOPPED
    assert "结束。" in sink.texts


def test_stop_emits_stopped():
    """stop → stopped 事件。"""
    sink = _CollectSink()
    dbg = DebuggerModel(_linear_story(), sink)
    dbg.add_breakpoint("c1")
    dbg.run()
    assert _wait_for_status(dbg, STATUS_PAUSED, timeout=2.0)
    dbg.stop()
    assert _wait_for_event(dbg, EVENT_STOPPED, timeout=2.0)
    assert dbg.status == STATUS_STOPPED


def test_completed_emits_completed():
    """无断点跑完 → completed 事件。"""
    sink = _CollectSink()
    dbg = DebuggerModel(_linear_story(), sink)
    dbg.run()
    dbg.join(timeout=2.0)
    assert dbg.status == STATUS_STOPPED
    assert _wait_for_event(dbg, EVENT_COMPLETED, timeout=2.0)


def test_pause_returns_false_when_idle():
    dbg = DebuggerModel(_linear_story(), _CollectSink())
    assert dbg.pause() is False


def test_resume_returns_false_when_idle():
    dbg = DebuggerModel(_linear_story(), _CollectSink())
    assert dbg.resume() is False


# ═══════════════════════════════════════════════════════════════════════
# 9. 历史裁剪（max_history）
# ═══════════════════════════════════════════════════════════════════════


def test_trim_execution_path():
    """max_history=1 → 执行路径只保留最近 1 个块。

    执行路径由 worker 在 on_block_visit 写入（status PAUSED 之前），确定性。
    不依赖事件同步（max_history=1 时事件有主/worker 线程竞态）。
    """
    sink = _CollectSink()
    dbg = DebuggerModel(_linear_story(), sink, max_history=1)
    dbg.add_breakpoint("c1")
    dbg.run()
    assert _wait_for_status(dbg, STATUS_PAUSED, timeout=2.0)
    # 访问了 start + c1，但裁剪到 1 → 只剩 c1
    assert dbg.get_execution_path() == ["c1"]
    dbg.stop()


def test_trim_events():
    """max_history=1 → 事件日志裁剪到 1 条。

    started（主线程）+ breakpoint（worker 线程）有竞态，两者顺序不定，
    但裁剪后必然只剩 1 条（裁剪在锁内原子完成，外部永不观测到 len>1）。
    """
    sink = _CollectSink()
    dbg = DebuggerModel(_linear_story(), sink, max_history=1)
    dbg.add_breakpoint("c1")
    dbg.run()
    assert _wait_for_status(dbg, STATUS_PAUSED, timeout=2.0)
    # 等待 started（主线程，run 后立即写入）+ 一小段让 worker 事件落定
    assert _wait_for_event(dbg, EVENT_STARTED, timeout=1.0)
    time.sleep(0.05)
    events = dbg.get_events()
    assert len(events) == 1
    dbg.stop()


def test_trim_variable_history():
    """max_history=1 → 变量历史只保留最近 1 条快照。"""
    sink = _CollectSink()
    dbg = DebuggerModel(_linear_story(), sink, max_history=1)
    dbg.add_breakpoint("start")
    dbg.run()
    assert _wait_for_status(dbg, STATUS_PAUSED, timeout=2.0)
    dbg.step()
    assert _wait_for_status(dbg, STATUS_PAUSED, timeout=2.0)  # c1
    dbg.step()
    assert _wait_for_status(dbg, STATUS_PAUSED, timeout=2.0)  # c2
    # 等第 3 次 on_paused 完成（c2 快照写入，裁剪后只剩 c2）
    assert _wait_for_latest_snapshot(dbg, "c2", timeout=2.0)
    history = dbg.get_variable_history()
    assert len(history) == 1
    assert history[0].block_id == "c2"
    dbg.stop()


# ═══════════════════════════════════════════════════════════════════════
# 10. dataclass + 常量 + 模块导入
# ═══════════════════════════════════════════════════════════════════════


def test_variable_snapshot_dataclass():
    snap = VariableSnapshot(
        block_id="c1", variables={"a": 1}, path=["start"], timestamp=1.5,
    )
    assert snap.block_id == "c1"
    assert snap.variables == {"a": 1}
    assert snap.path == ["start"]
    assert snap.timestamp == 1.5


def test_variable_snapshot_frozen():
    snap = VariableSnapshot(block_id="c1", variables={}, path=[], timestamp=0.0)
    with pytest.raises(Exception):
        snap.block_id = "c2"  # frozen


def test_debug_event_dataclass():
    evt = DebugEvent(kind=EVENT_STARTED, block_id=None, message="hi", timestamp=1.0)
    assert evt.kind == EVENT_STARTED
    assert evt.block_id is None
    assert evt.message == "hi"
    assert evt.timestamp == 1.0


def test_debug_event_frozen():
    evt = DebugEvent(kind=EVENT_STARTED, block_id=None, message="hi", timestamp=1.0)
    with pytest.raises(Exception):
        evt.kind = EVENT_ERROR  # frozen


def test_event_constants_distinct():
    consts = {EVENT_STARTED, EVENT_PAUSED, EVENT_BREAKPOINT, EVENT_RESUMED,
              EVENT_STEP, EVENT_STOPPED, EVENT_COMPLETED, EVENT_ERROR}
    assert len(consts) == 8


def test_default_max_history_value():
    assert DEFAULT_MAX_HISTORY == 1000


def test_module_imports():
    from editor import debugger_model
    assert hasattr(debugger_model, "DebuggerModel")
    assert hasattr(debugger_model, "VariableSnapshot")
    assert hasattr(debugger_model, "DebugEvent")
    assert debugger_model.DebuggerModel is DebuggerModel


def test_get_snapshot_delegates():
    """get_snapshot 委托 PreviewController，返回防御性拷贝。"""
    sink = _CollectSink()
    dbg = DebuggerModel(_linear_story(), sink)
    dbg.add_breakpoint("c1")
    dbg.run()
    assert _wait_for_status(dbg, STATUS_PAUSED, timeout=2.0)
    snap = dbg.get_snapshot()
    assert snap["block_id"] == "c1"
    assert snap["status"] == STATUS_PAUSED
    # 修改不影响内部
    snap["vars"]["hack"] = "evil"
    assert "hack" not in dbg.get_snapshot()["vars"]
    dbg.stop()
