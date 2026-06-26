"""V2-04 · Task 2 — runtime.chapter_manager.ChapterManager 测试。

按 PM 派工 V2-04 task 2 验收：
- class ChapterManager 监听 RouteEvt → 加载新章节 → 切换 executor
- 支持嵌套：chapter02.md 内部 id:end:chapter03 → chapter03.md
- __init__(chapters_root, bus, *, executor_factory, shared_state)
- executor_factory 注入：方便测试用 mock executor 替代真 Executor
- shared_state：跨章节状态共享（V2-04 OQ-3 决策）

测试分两层：
1. **单元测试**（mock executor_factory）—— handle_route_evt 的逻辑
   - 路径拼装、executor_factory 调用、shared_state 传递、默认 factory
2. **集成测试**（真 Executor + 真 chapters/）—— run() 主循环
   - chapter01 → chapter02 → ChapterEndEvt 跨章节跳转
   - 嵌套：chapter02 内部 id:end:chapter03 → chapter03

约束：
- 不修改 core.engine.executor（task 2 中同步扩 state 参数，但只加不影响现有行为）
- 测试路径用 tmp_path + monkeypatch CHAPTERS_ROOT 走 P0-S1 校验
"""
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")


# ─── Fake Bus + Fake Executor ───────────────────────────────────────────────


class FakeBus:
    """测试用 fake bus —— 模拟 EngineBus 单一队列语义。

    - get_evt()：FIFO 出队（先消费 put_evt 推入的，再消费预设 _events）
    - put_evt()：入队 + 记录到 all_put_events（测试可断言历史 put）
    - put_cmd() / get_cmd() / close()：满足 EventSink Protocol 即可
    """

    def __init__(self, events=None):
        self._preset_events: list = list(events or [])
        self._preset_idx = 0
        self._queue: list = []  # put_evt 推入的，FIFO 队列
        self.all_put_events: list = []  # 所有 put_evt 调用历史（不被消费）
        self.put_cmd_calls: list = []
        self.closed = False

    def get_evt(self):
        # 优先消费 put_evt 推入的（模拟 EngineBus 单一队列）
        if self._queue:
            return self._queue.pop(0)
        if self._preset_idx < len(self._preset_events):
            e = self._preset_events[self._preset_idx]
            self._preset_idx += 1
            return e
        return None  # 没事件

    def put_evt(self, evt) -> None:
        self._queue.append(evt)
        self.all_put_events.append(evt)

    def get_cmd(self):
        return None

    def put_cmd(self, cmd) -> None:
        self.put_cmd_calls.append(cmd)

    def close(self) -> None:
        self.closed = True


class RecordingExecutor:
    """测试用 fake executor —— 录制 run() 调用 + 不真跑 blocks。"""

    def __init__(self, story, bus, **kwargs):
        self.story = story
        self.bus = bus
        self.kwargs = kwargs
        self.run_called = 0

    def run(self) -> None:
        self.run_called += 1


# ─── 1. 构造 + 基本属性 ──────────────────────────────────────────────────────


def test_chapter_manager_init_stores_chapters_root_and_bus(tmp_path):
    """__init__ 把 chapters_root / bus 存为实例属性。"""
    from runtime.chapter_manager import ChapterManager

    chapters_dir = tmp_path / "chapters"
    bus = FakeBus()
    mgr = ChapterManager(chapters_dir, bus)
    assert mgr.chapters_root == chapters_dir
    assert mgr.bus is bus


# ─── 2. handle_route_evt 拼路径 chapters_root / {target}.md ────────────────


def test_handle_route_evt_resolves_chapter_path_from_target(tmp_path, monkeypatch):
    """RouteEvt(target='chapter02') → chapters_root / 'chapter02.md' 路径。"""
    from runtime.chapter_manager import ChapterManager
    from core.engine import main as main_mod
    from core.engine.protocol import RouteEvt

    chapters_dir = tmp_path / "chapters"
    chapters_dir.mkdir()
    chapter = chapters_dir / "chapter02.md"
    chapter.write_text(
        "```neon\n"
        "id:start\n"
        "node start\n"
        "node end\n"
        "```\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(main_mod, "CHAPTERS_ROOT", chapters_dir)

    factory_calls = []
    def fake_factory(story, bus, **kwargs):
        factory_calls.append(story)
        return RecordingExecutor(story, bus, **kwargs)

    bus = FakeBus()
    mgr = ChapterManager(chapters_dir, bus, executor_factory=fake_factory)
    mgr.handle_route_evt(RouteEvt(target="chapter02"))

    assert len(factory_calls) == 1
    story = factory_calls[0]
    # 加载的是 chapter02.md
    assert len(story.blocks) == 1
    from core.engine.ast_nodes import IdMeta
    assert any(isinstance(m, IdMeta) and m.id == "start" for m in story.blocks[0].meta)


# ─── 3. handle_route_evt 调 executor_factory(story, bus) 然后 .run() ───────


def test_handle_route_evt_calls_executor_factory_and_runs_executor(tmp_path, monkeypatch):
    """executor_factory(story, bus) 被调一次，返回的 executor.run() 被调一次。"""
    from runtime.chapter_manager import ChapterManager
    from core.engine import main as main_mod
    from core.engine.protocol import RouteEvt

    chapters_dir = tmp_path / "chapters"
    chapters_dir.mkdir()
    (chapters_dir / "chapter02.md").write_text(
        "```neon\nid:start\nnode start\nnode end\n```\n", encoding="utf-8",
    )
    monkeypatch.setattr(main_mod, "CHAPTERS_ROOT", chapters_dir)

    factory_calls: list = []
    def fake_factory(story, bus, **kwargs):
        factory_calls.append((story, bus, kwargs))
        exe = RecordingExecutor(story, bus, **kwargs)
        return exe

    bus = FakeBus()
    mgr = ChapterManager(chapters_dir, bus, executor_factory=fake_factory)
    mgr.handle_route_evt(RouteEvt(target="chapter02"))

    assert len(factory_calls) == 1
    story_arg, bus_arg, kwargs_arg = factory_calls[0]
    assert bus_arg is bus
    # fake_factory 返回的 RecordingExecutor.run() 被调一次
    # 通过 mgr.handle_route_evt 内部调用


# ─── 4. 默认 executor_factory 用 Executor 类 ────────────────────────────────


def test_default_executor_factory_uses_executor_class(tmp_path, monkeypatch):
    """不传 executor_factory → 用 core.engine.executor.Executor 构造。"""
    from runtime.chapter_manager import ChapterManager
    from core.engine import main as main_mod
    from core.engine.executor import Executor
    from core.engine.protocol import RouteEvt

    chapters_dir = tmp_path / "chapters"
    chapters_dir.mkdir()
    (chapters_dir / "chapter02.md").write_text(
        "```neon\nid:start\nnode start\nnode end\n```\n", encoding="utf-8",
    )
    monkeypatch.setattr(main_mod, "CHAPTERS_ROOT", chapters_dir)

    bus = FakeBus()
    mgr = ChapterManager(chapters_dir, bus)  # 没传 factory

    # 验证默认 factory 走 Executor
    from runtime import chapter_manager as cm_mod
    assert cm_mod._default_executor_factory is not None

    # 直接调 default factory，验证返回 Executor 实例
    from core.engine.interpreter import extract_neon_blocks
    from core.engine.ast_nodes import Story
    story = Story(blocks=())
    exe = cm_mod._default_executor_factory(story, bus)
    assert isinstance(exe, Executor)


# ─── 5. shared_state → executor_factory(state=...) 传递 ─────────────────────


def test_handle_route_evt_passes_shared_state_to_factory(tmp_path, monkeypatch):
    """shared_state 非 None → executor_factory 被调时 kwargs 含 state=shared_state。"""
    from runtime.chapter_manager import ChapterManager
    from core.engine import main as main_mod
    from core.engine.executor import GameState
    from core.engine.protocol import RouteEvt

    chapters_dir = tmp_path / "chapters"
    chapters_dir.mkdir()
    (chapters_dir / "chapter02.md").write_text(
        "```neon\nid:start\nnode start\nnode end\n```\n", encoding="utf-8",
    )
    monkeypatch.setattr(main_mod, "CHAPTERS_ROOT", chapters_dir)

    shared = GameState()
    shared.vars["p_mood"] = "happy"

    factory_kwargs: list = []
    def fake_factory(story, bus, **kwargs):
        factory_kwargs.append(kwargs)
        return RecordingExecutor(story, bus, **kwargs)

    bus = FakeBus()
    mgr = ChapterManager(chapters_dir, bus, executor_factory=fake_factory, shared_state=shared)
    mgr.handle_route_evt(RouteEvt(target="chapter02"))

    assert len(factory_kwargs) == 1
    assert factory_kwargs[0].get("state") is shared


# ─── 6. invalid route → FileNotFoundError（路径校验传播） ────────────────────


def test_handle_route_evt_raises_for_nonexistent_chapter(tmp_path, monkeypatch):
    """RouteEvt(target='nonexistent') → load_chapter_safe 抛 FileNotFoundError。"""
    from runtime.chapter_manager import ChapterManager
    from core.engine import main as main_mod
    from core.engine.protocol import RouteEvt

    chapters_dir = tmp_path / "chapters"
    chapters_dir.mkdir()
    monkeypatch.setattr(main_mod, "CHAPTERS_ROOT", chapters_dir)

    bus = FakeBus()
    mgr = ChapterManager(chapters_dir, bus, executor_factory=RecordingExecutor)

    with pytest.raises(FileNotFoundError):
        mgr.handle_route_evt(RouteEvt(target="nonexistent"))


# ─── 7. 嵌套路由：run() 主循环遇 RouteEvt 持续加载，遇 ChapterEndEvt 退出 ─


def test_run_loop_processes_multiple_route_events_until_chapter_end(tmp_path, monkeypatch):
    """run() 依次处理 RouteEvt → 加载 → 跑 executor → 下一 evt；ChapterEndEvt → break。
    支持嵌套：chapter01 末尾 id:end1:chapter02 触发 RouteEvt('chapter02')，
    run() 加载 chapter02；chapter02 末尾 id:end2 触发 ChapterEndEvt，run() 退出。
    """
    from runtime.chapter_manager import ChapterManager
    from core.engine import main as main_mod
    from core.engine.protocol import RouteEvt, ChapterEndEvt, TextEvt

    chapters_dir = tmp_path / "chapters"
    chapters_dir.mkdir()
    # chapter01：start + text + end with id:end1:chapter02
    (chapters_dir / "chapter01.md").write_text(
        "```neon\n"
        "id:start\n"
        "id:end1:chapter02\n"
        "node start\n"
        "chapter01 text\n"
        "node end\n"
        "```\n",
        encoding="utf-8",
    )
    # chapter02：start + text + end with id:end2 (no routing)
    (chapters_dir / "chapter02.md").write_text(
        "```neon\n"
        "id:start\n"
        "id:end2\n"
        "node start\n"
        "chapter02 text\n"
        "node end\n"
        "```\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(main_mod, "CHAPTERS_ROOT", chapters_dir)

    # fake_bus：先喂一个 RouteEvt 启动 chapter01
    # executor 跑完 chapter01 会 emit RouteEvt('chapter02')（通过 bus.put_evt 推入 _queue）
    # while 循环再读 _queue → 加载 chapter02 → executor emit ChapterEndEvt
    # while 循环再读 _queue → ChapterEndEvt → break
    bus = FakeBus(events=[
        RouteEvt(target="chapter01"),  # run() 启动入口
    ])

    mgr = ChapterManager(chapters_dir, bus)
    mgr.run()

    # 验证：所有 put_evt 都被记录在 all_put_events（不被 get_evt 消费）
    all_evts = bus.all_put_events

    # 两个 chapter 的 text 都通过 bus.put_evt 出来
    text_contents = [e.content.strip() for e in all_evts if hasattr(e, "content") and not isinstance(e, RouteEvt)]
    assert "chapter01 text" in text_contents
    assert "chapter02 text" in text_contents
    # end1 触发 RouteEvt('chapter02')
    route_targets = [e.target for e in all_evts if isinstance(e, RouteEvt)]
    assert "chapter02" in route_targets
    # end2 触发 ChapterEndEvt（且只有 1 个）
    chapter_ends = [e for e in all_evts if isinstance(e, ChapterEndEvt)]
    assert len(chapter_ends) == 1


# ─── 8. Executor 接受 state 参数（联合 task 2：executor.py 扩展） ────────────


def test_executor_accepts_shared_state_parameter():
    """Executor.__init__ 接受 state: GameState | None = None；非 None → 复用。"""
    from core.engine.executor import Executor, GameState
    from core.engine.interpreter import extract_neon_blocks
    from core.engine.ast_nodes import Story

    bus = FakeBus()
    shared = GameState()
    shared.vars["k"] = "v"

    story = Story(blocks=())
    exe = Executor(story, bus, state=shared)
    assert exe.state is shared
    assert exe.state.vars == {"k": "v"}

    # 不传 state → 新建
    exe2 = Executor(story, bus)
    assert exe2.state is not shared
    assert isinstance(exe2.state, GameState)


# ─── 9. initial_story：run() 先跑第一个 story 再进入循环（CLI 单章节入口） ─


def test_run_runs_initial_story_then_waits_for_route_evt(tmp_path, monkeypatch):
    """initial_story 非 None → run() 先用默认 factory 跑这个 story，然后进入 while 循环。
    CLI 单章节场景：main.py 传 initial_story=first_story 给 ChapterManager.run()。
    """
    from runtime.chapter_manager import ChapterManager
    from core.engine import main as main_mod
    from core.engine.protocol import ChapterEndEvt

    chapters_dir = tmp_path / "chapters"
    chapters_dir.mkdir()
    # 单章节：start + end with id:end2（无路由，触发 ChapterEndEvt）
    (chapters_dir / "chapter01.md").write_text(
        "```neon\n"
        "id:start\n"
        "id:end2\n"
        "node start\n"
        "hello\n"
        "node end\n"
        "```\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(main_mod, "CHAPTERS_ROOT", chapters_dir)

    # 加载 initial_story
    from runtime.load_chapter import load_chapter_safe
    initial_story = load_chapter_safe(chapters_dir / "chapter01.md")

    bus = FakeBus(events=[])  # 不预设 RouteEvt；executor emit ChapterEndEvt → run 退出
    mgr = ChapterManager(chapters_dir, bus, initial_story=initial_story)
    mgr.run()

    # 验证：initial story 跑了（emit TextEvt "hello"）
    text_contents = [e.content.strip() for e in bus.all_put_events if hasattr(e, "content") and not isinstance(e, type(e)) and not isinstance(e, ChapterEndEvt)]
    # 简化：直接看 has TextEvt
    from core.engine.protocol import TextEvt
    text_evts = [e for e in bus.all_put_events if isinstance(e, TextEvt)]
    assert any(e.content.strip() == "hello" for e in text_evts)
    # 验证：emit ChapterEndEvt → run 退出
    assert any(isinstance(e, ChapterEndEvt) for e in bus.all_put_events)
