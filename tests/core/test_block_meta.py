"""v0-issue-8 元数据区解析测试。

按 issue #30 acceptance criteria 验证 parse_block_meta / BlockMeta / IdSpec。
"""
import sys

import pytest

REPO_ROOT = "/home/hedaas/桌面/Neural Engine"
sys.path.insert(0, f"{REPO_ROOT}/src")

from core.engine.interpreter import parse_block_meta, BlockMeta, IdSpec  # noqa: E402
from core.engine.ast_nodes import ParserError  # noqa: E402


def _lineno_of_first_line(start_lineno: int) -> int:
    """围栏开行 +1 是第一行 meta（跳过围栏开）。"""
    return start_lineno + 1


# 1. id:start
def test_id_start():
    lines = ["id:start\n"]
    meta = parse_block_meta(lines, start_lineno=10)
    assert len(meta.ids) == 1
    spec = meta.ids[0]
    assert spec.kind == "start"
    assert spec.id == "start"
    assert spec.x is None
    assert spec.route_chapter is None
    assert spec.lineno == _lineno_of_first_line(10)


# 2. id:xxx normal
def test_id_normal():
    lines = ["id:c1\n"]
    meta = parse_block_meta(lines, start_lineno=5)
    spec = meta.ids[0]
    assert spec.kind == "normal"
    assert spec.id == "c1"
    assert spec.x is None
    assert spec.route_chapter is None


# 3. id:end 无 X
def test_id_end_no_x():
    lines = ["id:end\n"]
    meta = parse_block_meta(lines, start_lineno=5)
    spec = meta.ids[0]
    assert spec.kind == "end"
    assert spec.id is None
    assert spec.x is None
    assert spec.route_chapter is None


# 4. id:endX
def test_id_end_with_x():
    lines = ["id:end1\n"]
    meta = parse_block_meta(lines, start_lineno=5)
    spec = meta.ids[0]
    assert spec.kind == "end"
    assert spec.x == 1
    assert spec.route_chapter is None


# 5. id:endX:chapterYY
def test_id_end_with_x_and_chapter():
    lines = ["id:end2:chapter02\n"]
    meta = parse_block_meta(lines, start_lineno=5)
    spec = meta.ids[0]
    assert spec.kind == "end"
    assert spec.x == 2
    assert spec.route_chapter == "chapter02"


# 6. 多 ID 按出现顺序
def test_multiple_ids_in_order():
    lines = ["id:c1\n", "id:c2\n", "id:c3\n"]
    meta = parse_block_meta(lines, start_lineno=10)
    assert [s.id for s in meta.ids] == ["c1", "c2", "c3"]


# 7. 重复 ID 抛 ParserError
def test_duplicate_id_raises():
    lines = ["id:c1\n", "id:c1\n"]
    with pytest.raises(ParserError):
        parse_block_meta(lines, start_lineno=5)


# 8. 未识别前缀抛 ParserError
def test_unrecognized_prefix_raises():
    # 元数据区只允许 id: 前缀
    lines = ["next: c2\n"]
    with pytest.raises(ParserError):
        parse_block_meta(lines, start_lineno=5)


# 9. endX 中 X 非自然数
def test_end_x_must_be_natural_number():
    # 浮点
    lines = ["id:end1.5\n"]
    with pytest.raises(ParserError):
        parse_block_meta(lines, start_lineno=5)

    # 字母
    lines2 = ["id:endabc\n"]
    with pytest.raises(ParserError):
        parse_block_meta(lines2, start_lineno=5)


# 10. endX 中 X 负数
def test_end_x_negative_raises():
    lines = ["id:end-1\n"]
    with pytest.raises(ParserError):
        parse_block_meta(lines, start_lineno=5)
