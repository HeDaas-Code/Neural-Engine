"""v0-issue-6 neon 围栏块提取器测试。

按 issue #28 acceptance criteria 验证 extract_neon_blocks / NeonBlock。
"""
import sys

import pytest

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")

from core.engine.interpreter import extract_neon_blocks  # noqa: E402
from core.engine.ast_nodes import ParserError  # noqa: E402


# 1. 单块
def test_single_neon_block_extracted():
    md = "# 标题\n\n```neon\nc1 {\n  id: c1\n}\n```\n"
    blocks = extract_neon_blocks(md)
    assert len(blocks) == 1
    assert blocks[0].content.strip() == "c1 {\n  id: c1\n}"
    assert "```neon" in blocks[0].raw
    assert blocks[0].raw.endswith("```\n") or blocks[0].raw.endswith("```")


# 2. 无 neon 块
def test_no_neon_block_returns_empty_list():
    md = "# 只是标题\n\n普通段落。\n\n```python\nprint('hi')\n```\n"
    assert extract_neon_blocks(md) == []


# 3. 多块顺序保留
def test_multiple_neon_blocks_preserved_in_order():
    md = "```neon\nA\n```\n\n中间段落\n\n```neon\nB\n```\n\n```neon\nC\n```\n"
    blocks = extract_neon_blocks(md)
    assert len(blocks) == 3
    assert blocks[0].content.strip() == "A"
    assert blocks[1].content.strip() == "B"
    assert blocks[2].content.strip() == "C"
    # lineno 单调增
    assert blocks[0].lineno < blocks[1].lineno < blocks[2].lineno


# 4. ```markdown 围栏外忽略
def test_markdown_fence_outside_neon_is_ignored():
    md = "```markdown\n普通文本\n```\n\n```neon\nX\n```\n"
    blocks = extract_neon_blocks(md)
    assert len(blocks) == 1
    assert blocks[0].content.strip() == "X"


# 5. 标题 / 序言忽略
def test_heading_and_preamble_outside_neon_ignored():
    md = "# 第一章 雨夜\n\n> 旁白\n\n```neon\nY\n```\n"
    blocks = extract_neon_blocks(md)
    assert len(blocks) == 1
    assert blocks[0].content.strip() == "Y"
    # lineno 应是 5（1=标题,2=空,3=旁白,4=空,5=neon 开）
    assert blocks[0].lineno == 5


# 6. lineno 1-indexed
def test_lineno_is_one_indexed_for_fence_line():
    md = "first line\nsecond\n\n```neon\nZ\n```\n"
    blocks = extract_neon_blocks(md)
    # 1=first, 2=second, 3=空, 4=neon 开围栏
    assert blocks[0].lineno == 4


# 7. 多行围栏
def test_multiline_neon_content_preserved():
    md = "```neon\nline1\nline2\nline3\n```\n"
    blocks = extract_neon_blocks(md)
    assert blocks[0].content == "line1\nline2\nline3\n"


# 8. 未关闭围栏抛 ParserError
def test_unclosed_neon_fence_raises_parser_error():
    md = "```neon\nA\nB\n"  # 没闭
    with pytest.raises(ParserError):
        extract_neon_blocks(md)


# 9. 大小写变体忽略
def test_capitalized_neon_variant_ignored():
    md = "```Neon\nA\n```\n\n```NEON\nB\n```\n"
    blocks = extract_neon_blocks(md)
    # strip 后不等于 "neon"，所以忽略
    assert blocks == []


# 10. 空围栏
def test_empty_neon_block_returns_empty_content():
    md = "```neon\n```\n"
    blocks = extract_neon_blocks(md)
    assert len(blocks) == 1
    assert blocks[0].content == "" or blocks[0].content == "\n"
