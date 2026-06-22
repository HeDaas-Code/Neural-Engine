"""v0-issue-7 块级骨架解析测试。

按 issue #29 acceptance criteria 验证 parse_block_skeleton / BlockSkeleton。
"""
import sys

import pytest

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")

from core.engine.interpreter import parse_block_skeleton, BlockSkeleton  # noqa: E402
from core.engine.ast_nodes import ParserError  # noqa: E402


def _lines(s: str) -> list[str]:
    """把字符串按行切分（含末换行）。"""
    return s.splitlines(keepends=True)


# 1. 标准块
def test_block_with_meta_and_body():
    content = "id: c1\nnext: c2\n\nnode start\ntext 雨夜\ntext 敲门\nnode end\n"
    skel, rest = parse_block_skeleton(content, lineno=10)
    assert isinstance(skel, BlockSkeleton)
    assert skel.start_lineno == 10
    assert skel.meta_lines == _lines("id: c1\nnext: c2\n")
    assert "text 雨夜" in "".join(skel.body_lines)
    assert "text 敲门" in "".join(skel.body_lines)
    assert rest == []  # node end 之后无剩余


# 2. 缺 node start
def test_missing_node_start_raises_parser_error():
    content = "id: c1\ntext 雨夜\nnode end\n"
    with pytest.raises(ParserError):
        parse_block_skeleton(content, lineno=5)


# 3. 缺 node end
def test_missing_node_end_raises_parser_error():
    content = "id: c1\nnode start\ntext 雨夜\n"
    with pytest.raises(ParserError):
        parse_block_skeleton(content, lineno=5)


# 4. 多 node start
def test_duplicate_node_start_raises_parser_error():
    content = "node start\nnode start\ntext x\nnode end\n"
    with pytest.raises(ParserError):
        parse_block_skeleton(content, lineno=1)


# 5. 多 node end
def test_duplicate_node_end_raises_parser_error():
    content = "node start\ntext x\nnode end\nnode end\n"
    with pytest.raises(ParserError):
        parse_block_skeleton(content, lineno=1)


# 6. 整行注释跳过
def test_full_line_comment_skipped():
    content = "# 整行注释\nid: c1\n# 又一个注释\nnode start\ntext x\nnode end\n"
    skel, _ = parse_block_skeleton(content, lineno=1)
    # meta_lines 应只有 id: c1
    assert skel.meta_lines == _lines("id: c1\n")
    # 注释行不在 body
    assert not any("#" in l for l in skel.body_lines if l.strip())


# 7. 空行跳过
def test_blank_lines_skipped():
    content = "\n\nid: c1\n\n\nnode start\n\ntext x\n\nnode end\n"
    skel, _ = parse_block_skeleton(content, lineno=1)
    assert skel.meta_lines == _lines("id: c1\n")
    # v0-issue-17 fix: body_lines 含 sentinel（node start / node end 保留）
    assert skel.body_lines == _lines("node start\ntext x\nnode end\n")


# 8. start_lineno = 围栏开行
def test_start_lineno_is_fence_lineno():
    content = "node start\nnode end\n"
    skel, _ = parse_block_skeleton(content, lineno=42)
    assert skel.start_lineno == 42


# 9. 剩余行返回在第二元组元素
def test_remaining_lines_returned_in_second_tuple_element():
    content = "node start\ntext x\nnode end\ntext y\ntext z\n"
    skel, rest = parse_block_skeleton(content, lineno=1)
    assert rest == _lines("text y\ntext z\n")


# 10. node start 之前可有 空行 / 注释
def test_node_start_after_blank_or_comment_lines():
    content = "\n# 注释\nid: c1\n\nnode start\ntext x\nnode end\n"
    skel, _ = parse_block_skeleton(content, lineno=1)
    assert skel.meta_lines == _lines("id: c1\n")
    # v0-issue-17 fix: body_lines 含 sentinel
    assert skel.body_lines == _lines("node start\ntext x\nnode end\n")
