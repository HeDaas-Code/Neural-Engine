"""runtime/chapter_manager.py (ChapterManager) 单元测试。

ChapterManager 负责章节加载与跨章节跳转编排，此前无任何测试覆盖。
本测试通过注入假 executor_factory 与 mock bus 来验证：
- RouteEvt 触发章节加载与执行
- ChapterEndEvt 终止主循环
- shared_state 跨章节状态传递
- executor_factory 注入机制
"""

import sys
import os
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, f"{REPO_ROOT}/src")

from core.engine.executor import GameState
from core.engine.protocol import RouteEvt, ChapterEndEvt, TextEvt
from runtime.chapter_manager import ChapterManager


class MockBus:
    """模拟双向 bus。"""
    def __init__(self, events=None):
        self._events = list(events) if events else []
        self._put_evt_log = []

    def get_evt(self):
        if self._events:
            return self._events.pop(0)
        return None

    def put_evt(self, evt):
        self._put_evt_log.append(evt)


class RecordingExecutor:
    """假 executor，记录 run() 调用。"""
    _instances = []

    def __init__(self, story, bus, **kwargs):
        self.story = story
        self.bus = bus
        self.kwargs = kwargs
        self.ran = False
        RecordingExecutor._instances.append(self)

    def run(self):
        self.ran = True


@pytest.fixture(autouse=True)
def reset_executor():
    RecordingExecutor._instances.clear()
    yield
    RecordingExecutor._instances.clear()


class TestChapterManagerInit:
    """ChapterManager 初始化。"""

    def test_init_with_defaults(self):
        mgr = ChapterManager(Path("/tmp/ch"), MockBus())
        assert mgr.chapters_root == Path("/tmp/ch")
        assert mgr._shared_state is None
        assert mgr._initial_story is None

    def test_init_with_shared_state(self):
        state = GameState(vars={"k": "v"})
        mgr = ChapterManager(Path("/tmp"), MockBus(), shared_state=state)
        assert mgr._shared_state is state


class TestChapterManagerRoute:
    """handle_route_evt() 行为。"""

    def test_handle_route_evt_creates_executor_and_runs(self):
        bus = MockBus()
        mgr = ChapterManager(Path("/tmp"), bus, executor_factory=RecordingExecutor)
        with tempfile.TemporaryDirectory() as tmp:
            mgr.chapters_root = Path(tmp)
            (Path(tmp) / "chapter02.md").write_text("# Ch02\n")
            mgr.handle_route_evt(RouteEvt(target="chapter02"))
            assert len(RecordingExecutor._instances) == 1
            assert RecordingExecutor._instances[0].ran is True

    def test_handle_route_evt_passes_shared_state(self):
        state = GameState(vars={"shared": "yes"})
        bus = MockBus()
        mgr = ChapterManager(Path("/tmp"), bus, executor_factory=RecordingExecutor, shared_state=state)
        with tempfile.TemporaryDirectory() as tmp:
            mgr.chapters_root = Path(tmp)
            (Path(tmp) / "ch.md").write_text("# Ch\n")
            mgr.handle_route_evt(RouteEvt(target="ch"))
            exe = RecordingExecutor._instances[0]
            assert exe.kwargs.get("state") is state


class TestChapterManagerRun:
    """run() 主循环。"""

    def test_run_breaks_on_chapter_end(self):
        bus = MockBus(events=[ChapterEndEvt()])
        mgr = ChapterManager(Path("/tmp"), bus, executor_factory=RecordingExecutor)
        mgr.run()

    def test_run_ignores_text_evt(self):
        bus = MockBus(events=[TextEvt(content="hello"), ChapterEndEvt()])
        mgr = ChapterManager(Path("/tmp"), bus, executor_factory=RecordingExecutor)
        mgr.run()

    def test_run_breaks_on_none(self):
        bus = MockBus(events=[])
        mgr = ChapterManager(Path("/tmp"), bus, executor_factory=RecordingExecutor)
        mgr.run()

    def test_run_handles_route_evt_in_loop(self):
        with tempfile.TemporaryDirectory() as tmp:
            bus = MockBus(events=[RouteEvt(target="ch1"), ChapterEndEvt()])
            mgr = ChapterManager(Path(tmp), bus, executor_factory=RecordingExecutor)
            (Path(tmp) / "ch1.md").write_text("# Ch1\n")
            mgr.run()
            assert any(e.ran for e in RecordingExecutor._instances)


class TestChapterManagerFactory:
    """executor_factory 注入。"""

    def test_build_executor_no_shared_state(self):
        bus = MockBus()
        mgr = ChapterManager(Path("/tmp"), bus, executor_factory=RecordingExecutor)
        kwargs = mgr._build_executor("story")
        assert "state" not in kwargs

    def test_build_executor_with_shared_state(self):
        state = GameState()
        bus = MockBus()
        mgr = ChapterManager(Path("/tmp"), bus, executor_factory=RecordingExecutor, shared_state=state)
        kwargs = mgr._build_executor("story")
        assert kwargs.get("state") is state