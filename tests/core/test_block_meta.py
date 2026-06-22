"""v0-issue-8 元数据区解析测试（v0-issue-17 改用 IdMeta/IdEnd，IdSpec 弃用）。"""
import sys

import pytest

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")

from core.engine.interpreter import parse_block_meta, BlockMeta  # noqa: E402
from core.engine.ast_nodes import ParserError, IdMeta, IdEnd  # noqa: E402


# 1. id:start
def test_id_start():
    lines = ["id:start\n"]
    meta = parse_block_meta(lines, start_lineno=10)
    assert len(meta.ids) == 1
    spec = meta.ids[0]
    assert isinstance(spec, IdMeta)
    assert spec.id == "start"
    assert spec.lineno == 11


# 2. id:xxx normal
def test_id_normal():
    lines = ["id:c1\n"]
    meta = parse_block_meta(lines, start_lineno=5)
    spec = meta.ids[0]
    assert isinstance(spec, IdMeta)
    assert spec.id == "c1"


# 3. id:end 无 X
def test_id_end_no_x():
    lines = ["id:end\n"]
    meta = parse_block_meta(lines, start_lineno=5)
    spec = meta.ids[0]
    assert isinstance(spec, IdEnd)
    assert spec.x is None
    assert spec.route_chapter is None


# 4. id:endX
def test_id_end_with_x():
    lines = ["id:end1\n"]
    meta = parse_block_meta(lines, start_lineno=5)
    spec = meta.ids[0]
    assert isinstance(spec, IdEnd)
    assert spec.x == 1
    assert spec.route_chapter is None


# 5. id:endX:chapterYY
def test_id_end_with_x_and_chapter():
    lines = ["id:end2:chapter02\n"]
    meta = parse_block_meta(lines, start_lineno=5)
    spec = meta.ids[0]
    assert isinstance(spec, IdEnd)
    assert spec.x == 2
    assert spec.route_chapter == "chapter02"


# 6. 多 ID 按出现顺序
def test_multiple_ids_in_order():
    lines = ["id:c1\n", "id:c2\n", "id:c3\n"]
    meta = parse_block_meta(lines, start_lineno=10)
    assert [s.id for s in meta.ids if isinstance(s, IdMeta)] == ["c1", "c2", "c3"]


# 7. 重复 ID 抛 ParserError
def test_duplicate_id_raises():
    lines = ["id:c1\n", "id:c1\n"]
    with pytest.raises(ParserError):
        parse_block_meta(lines, start_lineno=5)


# 8. 未识别前缀抛 ParserError
def test_unrecognized_prefix_raises():
    # 元数据区只允许 id: 前缀（next: 留给 v0-issue-9）
    lines = ["foo: bar\n"]
    with pytest.raises(ParserError):
        parse_block_meta(lines, start_lineno=5)


# 9. endX 中 X 非自然数
def test_end_x_must_be_natural_number():
    lines = ["id:end1.5\n"]
    with pytest.raises(ParserError):
        parse_block_meta(lines, start_lineno=5)

    lines2 = ["id:endabc\n"]
    with pytest.raises(ParserError):
        parse_block_meta(lines2, start_lineno=5)


# 10. endX 中 X 负数
def test_end_x_negative_raises():
    lines = ["id:end-1\n"]
    with pytest.raises(ParserError):
        parse_block_meta(lines, start_lineno=5)
