"""v0-issue-17 core 进程入口测试。

按 issue #40 acceptance criteria 验证 main() 错误路径 + import 可走。
"""
import sys


import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")


# 1. import 可走
def test_main_imports_successfully():
    from core.engine.main import main
    assert callable(main)


# 2. 缺文件 → 退出 1
def test_main_nonexistent_path_returns_1(tmp_path):
    from core.engine.main import main
    missing = tmp_path / "missing.md"
    rc = main(str(missing))
    assert rc == 1


# 3. 缺文件 → LogEvt error 广播
def test_main_emits_log_error_for_missing_chapter(tmp_path, monkeypatch):
    from core.engine import main as main_mod
    from core.engine.protocol import LogEvt

    # 替换 EngineBus 为可观察的 MemoryEngineBus
    class MemoryEngineBus:
        def __init__(self, *a, **kw):
            from core.engine.executor import MemoryEventSink
            self._sink = MemoryEventSink()
        @property
        def events(self):
            return self._sink.events
        def put_evt(self, evt):
            self._sink.put_evt(evt)
        def get_cmd(self):
            return None
        def close(self):
            pass

    monkeypatch.setattr(main_mod, "EngineBus", MemoryEngineBus)

    missing = tmp_path / "missing.md"
    rc = main_mod.main(str(missing))
    assert rc == 1
    # 验证 LogEvt error 已发出
    log_err = [e for e in main_mod._last_bus.events if isinstance(e, LogEvt) and e.level == "error"]
    assert len(log_err) >= 1


# 4. 最小可用 chapter → headless 走通
def test_main_with_minimal_chapter_returns_0_headless(tmp_path, monkeypatch):
    from core.engine import main as main_mod

    chapter = tmp_path / "chapter01.md"
    chapter.write_text(
        "```neon\n"
        "id:start\n"
        "next: c1\n"
        "node start\n"
        "node c1\n"
        "node end\n"
        "```\n"
        "```neon\n"
        "id:c1\n"
        "id:end0\n"
        "node start\n"
        "node end\n"
        "```\n",
        encoding="utf-8",
    )

    # 替换 EngineBus 为可观察的
    class MemoryEngineBus:
        def __init__(self, *a, **kw):
            from core.engine.executor import MemoryEventSink
            self._sink = MemoryEventSink()
        def put_evt(self, evt):
            self._sink.put_evt(evt)
        def get_cmd(self):
            return None
        def close(self):
            pass

    monkeypatch.setattr(main_mod, "EngineBus", MemoryEngineBus)

    rc = main_mod.main(str(chapter))
    assert rc == 0
