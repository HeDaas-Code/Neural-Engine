"""v0-issue-10 块内执行区解析测试。

按 issue #32 acceptance criteria 验证 parse_block_body。
"""
import sys

import pytest

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")

from core.engine.ast_nodes import NextDecl, DecoratorCall  # noqa: E402
from core.engine.interpreter import parse_block_body, BlockMeta  # noqa: E402
from core.engine.ast_nodes import (  # noqa: E402
    Start, End, Text, In, Echo, NextId, If, ParserError,
)


def _empty_meta() -> BlockMeta:
    return BlockMeta(ids=[], start_lineno=10)


# 1. 全语句类型
def test_full_block_with_all_statement_types():
    lines = [
        "node start\n",
        "雨夜。\n",
        "node in ->p_mood\n",
        "node echo p_mood\n",
        "node next_id\n",
        "node end\n",
    ]
    nodes = parse_block_body(lines, start_lineno=10, block_meta=_empty_meta())
    # Start + Text + In + Echo + NextId + End
    assert len(nodes) == 6
    assert isinstance(nodes[0], Start)
    assert isinstance(nodes[-1], End)
    assert isinstance(nodes[1], Text) and nodes[1].content == "雨夜。\n"
    assert isinstance(nodes[2], In) and nodes[2].var == "p_mood"
    assert isinstance(nodes[3], Echo) and nodes[3].var == "p_mood"
    assert isinstance(nodes[4], NextId) and nodes[4].target_id == "next_id"


# 2. node in 两种格式
def test_node_in_with_arrow_space_and_without():
    # 带空格
    lines1 = ["node start\n", "node in ->p_mood\n", "node end\n"]
    nodes1 = parse_block_body(lines1, start_lineno=10, block_meta=_empty_meta())
    assert isinstance(nodes1[1], In) and nodes1[1].var == "p_mood"

    # 不带空格
    lines2 = ["node start\n", "node in->p_mood\n", "node end\n"]
    nodes2 = parse_block_body(lines2, start_lineno=10, block_meta=_empty_meta())
    assert isinstance(nodes2[1], In) and nodes2[1].var == "p_mood"


# 3. node echo
def test_node_echo():
    lines = ["node start\n", "node echo p_pick\n", "node end\n"]
    nodes = parse_block_body(lines, start_lineno=10, block_meta=_empty_meta())
    assert isinstance(nodes[1], Echo) and nodes[1].var == "p_pick"


# 4. node next_id
def test_node_next_id():
    lines = ["node start\n", "node c1\n", "node end\n"]
    nodes = parse_block_body(lines, start_lineno=10, block_meta=_empty_meta())
    assert isinstance(nodes[1], NextId) and nodes[1].target_id == "c1"


# 5. 文本行
def test_plain_text_line_becomes_text_node():
    lines = ["node start\n", "雨夜。\n", "敲门声。\n", "node end\n"]
    nodes = parse_block_body(lines, start_lineno=10, block_meta=_empty_meta())
    assert isinstance(nodes[1], Text) and nodes[1].content == "雨夜。\n"
    assert isinstance(nodes[2], Text) and nodes[2].content == "敲门声。\n"


# 6. @xxx → DecoratorCall/Stop（v0-issue-12 已解析，不再保留为 Text）
def test_decorator_line_preserved_for_issue_12():
    lines = ["node start\n", "@style bgm:rain\n", "node end\n"]
    nodes = parse_block_body(lines, start_lineno=10, block_meta=_empty_meta())
    # bgm:rain 是 key:val → DecoratorCall
    assert isinstance(nodes[1], DecoratorCall)
    assert nodes[1].name == "style"
    assert nodes[1].args == ("bgm:rain",)


# 7. 缺 node start
def test_missing_node_start_raises():
    lines = ["雨夜。\n", "node end\n"]
    with pytest.raises(ParserError):
        parse_block_body(lines, start_lineno=10, block_meta=_empty_meta())


# 8. 缺 node end
def test_missing_node_end_raises():
    lines = ["node start\n", "雨夜。\n"]
    with pytest.raises(ParserError):
        parse_block_body(lines, start_lineno=10, block_meta=_empty_meta())


# 9. 'node echo ' 无变量名
def test_unrecognized_prefix_raises():
    # 'node echo' 缺变量 → ParserError（v0-issue-10 行为）
    lines = ["node start\n", "node echo\n", "node end\n"]
    with pytest.raises(ParserError):
        parse_block_body(lines, start_lineno=10, block_meta=_empty_meta())


# 10. v0-issue-11 集成: node if 二元
def test_block_body_routes_node_if_binary():
    lines = ["node start\n", "node if cond[a,b]\n", "node end\n"]
    nt = [
        NextDecl(var_name="a", target_id="ca", lineno=1),
        NextDecl(var_name="b", target_id="cb", lineno=2),
    ]
    nodes = parse_block_body(lines, start_lineno=10, block_meta=_empty_meta(), next_table=nt)
    if_node = nodes[1]
    assert isinstance(if_node, If)
    assert if_node.cond == ("var", "cond")


# 11. v0-issue-11 集成: 简略二元
def test_block_body_routes_shortcut_if():
    lines = ["node start\n", "node [some?b:c]\n", "node end\n"]
    nt = [
        NextDecl(var_name="b", target_id="cb", lineno=1),
        NextDecl(var_name="c", target_id="cc", lineno=2),
    ]
    nodes = parse_block_body(lines, start_lineno=10, block_meta=_empty_meta(), next_table=nt)
    if_node = nodes[1]
    assert isinstance(if_node, If)
    assert if_node.cond[0] == "expr"
