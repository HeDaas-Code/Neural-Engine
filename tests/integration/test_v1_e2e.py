"""v1 端到端测试：chapter01_v1.md 真求值。

验证 ADR-0004 重构:
- ← / → 箭头符号
- echo 拼接
- node if expr 真求值
- v0 fixture 仍兼容
"""
import os
from pathlib import Path

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.engine.main import _load_story  # noqa: E402
from core.engine.executor import Executor, MemoryInputSink  # noqa: E402
from core.engine.protocol import (  # noqa: E402
    TextEvt,
)


def test_v1_chapter_loads():
    """v1 fixture 可被解析加载。"""
    chapter = Path(REPO_ROOT) / "chapters" / "chapter01_v1.md"
    story = _load_story(str(chapter))
    assert story is not None
    assert len(story.blocks) == 4  # start + c1 + ca + cb


def test_v1_echo_concat():
    """echo 拼接：node echo mood + ，是啊。"""
    chapter = Path(REPO_ROOT) / "chapters" / "chapter01_v1.md"
    story = _load_story(str(chapter))
    sink = MemoryInputSink(inputs=["平静", "1"])
    exe = Executor(story, sink)
    exe.run()
    # 找到 echo 拼接的 TextEvt
    text_evts = [e for e in sink.events if isinstance(e, TextEvt)]
    # 应该有 "平静，是啊。" 这个拼接结果
    concat_found = any("平静" in t.content and "是啊" in t.content for t in text_evts)
    assert concat_found, f"echo concat not found in text events: {[t.content for t in text_evts]}"


def test_v1_if_expr_true_branch():
    """node if pick == 1 → pick=1 时走 t_a (ca)。"""
    chapter = Path(REPO_ROOT) / "chapters" / "chapter01_v1.md"
    story = _load_story(str(chapter))
    sink = MemoryInputSink(inputs=["平静", "1"])
    exe = Executor(story, sink)
    exe.run()
    text_evts = [e for e in sink.events if isinstance(e, TextEvt)]
    # ca 块的文本 "你打开门"
    assert any("你打开门" in t.content for t in text_evts), \
        f"ca branch not taken: {[t.content for t in text_evts]}"


def test_v1_if_expr_false_branch():
    """node if pick == 1 → pick=2 时 False → branches[1] (t_b → cb)。"""
    chapter = Path(REPO_ROOT) / "chapters" / "chapter01_v1.md"
    story = _load_story(str(chapter))
    sink = MemoryInputSink(inputs=["平静", "2"])
    exe = Executor(story, sink)
    exe.run()
    text_evts = [e for e in sink.events if isinstance(e, TextEvt)]
    # cb 块的文本 "你没有开门"
    assert any("你没有开门" in t.content for t in text_evts), \
        f"cb branch not taken: {[t.content for t in text_evts]}"


def test_v0_chapter_still_works():
    """v0 chapter01.md 仍可正常加载。"""
    chapter = Path(REPO_ROOT) / "chapters" / "chapter01.md"
    if not chapter.exists():
        pytest.skip("chapter01.md not found")
    story = _load_story(str(chapter))
    assert story is not None
