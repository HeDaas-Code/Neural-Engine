"""v2-p0 chapter-manager 集成测试（V2-04 task 5）。

按 PM 派工 V2-04 task 5 验收：
- chapters/chapter01_route.md fixture：chapter01 末尾有 id:end1:chapter_route
- chapters/chapter_route.md fixture：简单章节验证跨章节
- tests/integration/test_chapter_loading.py 端到端跨章节测试

测试分两层：
1. **subprocess 端到端**：python -m core.engine.main chapters/chapter01_route.md
   → 实际跑通跨章节跳转，输出 / exit code 验证
2. **load_chapter_safe 直测**：load_chapter_safe(chapter01_route.md) / chapter_route.md
   → Story blocks / id:end1:chapter_route 标记解析正确
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")

CHAPTER01_ROUTE = Path(REPO_ROOT) / "chapters" / "chapter01_route.md"
CHAPTER_ROUTE = Path(REPO_ROOT) / "chapters" / "chapter_route.md"


# ─── 1. fixture 存在性 sanity（防 fixture 被误删） ──────────────────────────


def test_chapter01_route_fixture_exists():
    """chapters/chapter01_route.md fixture 必须存在（V2-04 task 5 必备）。"""
    assert CHAPTER01_ROUTE.exists(), (
        f"V2-04 task 5 fixture 缺失: {CHAPTER01_ROUTE}"
    )


def test_chapter_route_fixture_exists():
    """chapters/chapter_route.md fixture 必须存在（V2-04 task 5 必备）。"""
    assert CHAPTER_ROUTE.exists(), (
        f"V2-04 task 5 fixture 缺失: {CHAPTER_ROUTE}"
    )


# ─── 2. load_chapter_safe 直测 fixture ──────────────────────────────────────


def test_load_chapter_safe_parses_chapter01_route():
    """load_chapter_safe(chapter01_route.md) 解析出 1 个 block，meta 含 id:end1:chapter_route。"""
    from runtime.load_chapter import load_chapter_safe
    from core.engine.ast_nodes import IdEnd

    story = load_chapter_safe(CHAPTER01_ROUTE)
    # fixture 是最小章节：1 个块含 id:start + id:end1:chapter_route
    assert len(story.blocks) == 1
    block = story.blocks[0]
    # meta 含 id:end1:chapter_route
    end_markers = [m for m in block.meta if isinstance(m, IdEnd)]
    assert len(end_markers) == 1
    assert end_markers[0].route_chapter == "chapter_route"


def test_load_chapter_safe_parses_chapter_route():
    """load_chapter_safe(chapter_route.md) 解析出 1 个 block，meta 含 id:end2（无路由）。"""
    from runtime.load_chapter import load_chapter_safe
    from core.engine.ast_nodes import IdEnd

    story = load_chapter_safe(CHAPTER_ROUTE)
    assert len(story.blocks) == 1
    block = story.blocks[0]
    end_markers = [m for m in block.meta if isinstance(m, IdEnd)]
    assert len(end_markers) == 1
    assert end_markers[0].route_chapter is None  # 无跨章节


# ─── 3. ChapterManager 跨章节 end-to-end（in-process） ─────────────────────


def test_chapter_manager_routes_from_chapter01_route_to_chapter_route(monkeypatch):
    """ChapterManager 跑 chapter01_route.md → 末尾 id:end1:chapter_route → 加载 chapter_route.md。
    用 MemoryEngineBus 模拟 EngineBus（无 GUI 进程）。
    """
    from core.engine import main as main_mod
    from core.engine.executor import MemoryEventSink
    from core.engine.protocol import (
        TextEvt, RouteEvt, ChapterEndEvt,
    )
    from runtime.chapter_manager import ChapterManager

    class MemoryEngineBus:
        def __init__(self, *a, **kw):
            self._sink = MemoryEventSink()
            self._get_idx = 0
        @property
        def events(self):
            return self._sink.events
        def put_evt(self, evt):
            self._sink.put_evt(evt)
        def get_cmd(self):
            return None
        def get_evt(self):
            if self._get_idx < len(self._sink.events):
                e = self._sink.events[self._get_idx]
                self._get_idx += 1
                return e
            return None
        def close(self):
            pass

    monkeypatch.setattr(main_mod, "EngineBus", MemoryEngineBus)
    monkeypatch.setattr(main_mod, "CHAPTERS_ROOT", Path(REPO_ROOT) / "chapters")

    # 走 main() 入口（用 chapter01_route.md 当 initial_story）
    rc = main_mod.main(str(CHAPTER01_ROUTE))
    assert rc == 0

    # 验证：两个 chapter 的 text 都 emit 了
    # main() 内部 new 一个 MemoryEngineBus 存在 _last_bus
    events = main_mod._last_bus.events
    text_contents = [
        e.content.strip() for e in events
        if isinstance(e, TextEvt)
    ]
    # chapter01_route.md 应该有 "chapter01_route" 或类似标记
    # chapter_route.md 应该有 "chapter_route" 标记
    assert any("chapter01_route" in t for t in text_contents), (
        f"chapter01_route text not found in events: {text_contents}"
    )
    assert any("chapter_route" in t for t in text_contents), (
        f"chapter_route text not found in events: {text_contents}"
    )
    # 验证：emit RouteEvt('chapter_route')
    assert any(isinstance(e, RouteEvt) and e.target == "chapter_route" for e in events)
    # 验证：emit ChapterEndEvt（chapter_route.md 末尾 id:end2 触发）
    assert any(isinstance(e, ChapterEndEvt) for e in events)


# ─── 4. subprocess 端到端：python -m core.engine.main 实际跑通跨章节 ─────────


def test_subprocess_main_runs_chapter01_route_to_chapter_route():
    """subprocess 跑 main.py chapters/chapter01_route.md → 实际跨章节跳到 chapter_route.md。

    chapter01_route.md 末尾 id:end1:chapter_route → ChapterManager 加载 chapter_route.md
    → chapter_route.md 末尾 id:end2 触发 ChapterEndEvt → main 退出 0。

    注：subprocess 用 multiprocessing queue 跨进程；v0 阶段 In 节点会阻塞 CLI（无 input）。
    本 fixture 不含 In 节点，所以可正常跑通。
    """
    # 确保 fixtures 存在
    if not CHAPTER01_ROUTE.exists() or not CHAPTER_ROUTE.exists():
        pytest.skip("V2-04 fixtures missing")

    result = subprocess.run(
        [sys.executable, "-m", "core.engine.main", str(CHAPTER01_ROUTE)],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": f"{REPO_ROOT}/src"},
    )
    assert result.returncode == 0, (
        f"main() 返回非 0: rc={result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_subprocess_main_runs_chapter_route_standalone():
    """subprocess 跑 main.py chapters/chapter_route.md → 单章节跑通退出 0。"""
    if not CHAPTER_ROUTE.exists():
        pytest.skip("V2-04 fixture missing")

    result = subprocess.run(
        [sys.executable, "-m", "core.engine.main", str(CHAPTER_ROUTE)],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": f"{REPO_ROOT}/src"},
    )
    assert result.returncode == 0, (
        f"main() 返回非 0: rc={result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
