"""v0-issue-11 node if 解析测试。

按 issue #33 acceptance criteria 验证 3 种 if 形态 + 分支项省略 node 前缀。
"""
import sys

import pytest

REPO_ROOT = "/home/hedaas/桌面/Neural Engine"
sys.path.insert(0, f"{REPO_ROOT}/src")

from core.engine.interpreter import parse_if_stmt  # noqa: E402
from core.engine.ast_nodes import (  # noqa: E402
    If, Branch, NextDecl, CallExpression, ParserError,
)


def _next_table():
    return [
        NextDecl(var_name="a", target_id="ca", lineno=1),
        NextDecl(var_name="b", target_id="cb", lineno=2),
        NextDecl(var_name="c", target_id="cc", lineno=3),
    ]


# 1. 二元
def test_binary_if_with_default_values():
    line = "node if cond[a,b]\n"
    if_node = parse_if_stmt(line, lineno=10, next_table=_next_table())
    assert if_node.cond == ("var", "cond")
    assert len(if_node.branches) == 2
    assert if_node.branches[0].value == 0
    assert if_node.branches[0].target == NextDecl(var_name="a", target_id="ca", lineno=1)
    assert if_node.branches[1].value == 1
    assert if_node.branches[1].target == NextDecl(var_name="b", target_id="cb", lineno=2)


# 2. 多元 + echo
def test_multi_if_with_echo_branch():
    line = "node if var [1:a,2:b,3:echo p_pick]\n"
    if_node = parse_if_stmt(line, lineno=10, next_table=_next_table())
    assert if_node.cond == ("var", "var")
    assert len(if_node.branches) == 3
    assert if_node.branches[0].value == 1
    assert if_node.branches[0].target == NextDecl(var_name="a", target_id="ca", lineno=1)
    assert if_node.branches[1].value == 2
    assert if_node.branches[1].target == NextDecl(var_name="b", target_id="cb", lineno=2)
    assert if_node.branches[2].value == 3
    assert isinstance(if_node.branches[2].target, CallExpression)
    assert if_node.branches[2].target.kind == "echo"
    assert if_node.branches[2].target.var == "p_pick"


# 3. 多元 + in
def test_multi_if_with_in_branch():
    line = "node if var [1:a,2:in ->p_mood]\n"
    if_node = parse_if_stmt(line, lineno=10, next_table=_next_table())
    assert len(if_node.branches) == 2
    assert isinstance(if_node.branches[1].target, CallExpression)
    assert if_node.branches[1].target.kind == "in"
    assert if_node.branches[1].target.var == "p_mood"


# 4. 简略二元
def test_bare_shortcut_binary_if():
    line = "node [a?b:c]\n"
    if_node = parse_if_stmt(line, lineno=10, next_table=_next_table())
    assert if_node.cond == ("expr", "a")
    assert len(if_node.branches) == 2
    assert if_node.branches[0].value == 0
    assert if_node.branches[0].target == NextDecl(var_name="b", target_id="cb", lineno=2)
    assert if_node.branches[1].value == 1
    assert if_node.branches[1].target == NextDecl(var_name="c", target_id="cc", lineno=3)


# 5. 分支项带 node 前缀
def test_branch_with_node_prefix_works():
    line = "node if var [1:node a,2:node b]\n"
    if_node = parse_if_stmt(line, lineno=10, next_table=_next_table())
    assert if_node.branches[0].target == NextDecl(var_name="a", target_id="ca", lineno=1)
    assert if_node.branches[1].target == NextDecl(var_name="b", target_id="cb", lineno=2)


# 6. 分支项变量名不在 next_table
def test_branch_var_not_in_next_table_raises():
    line = "node if cond[a,unknown]\n"
    with pytest.raises(ParserError):
        parse_if_stmt(line, lineno=10, next_table=_next_table())


# 7. 二元缺 [a,b]
def test_malformed_binary_if_missing_brackets_raises():
    line = "node if cond a,b\n"
    with pytest.raises(ParserError):
        parse_if_stmt(line, lineno=10, next_table=_next_table())


# 8. 多元缺 [1:a,...]
def test_malformed_multi_if_missing_brackets_raises():
    line = "node if var 1:a,2:b\n"
    with pytest.raises(ParserError):
        parse_if_stmt(line, lineno=10, next_table=_next_table())


# 9. 简略二元正确构造 expr cond
def test_shortcut_binary_if_constructs_expr_cond():
    line = "node [some_expr?b:c]\n"
    if_node = parse_if_stmt(line, lineno=10, next_table=_next_table())
    assert if_node.cond[0] == "expr"
    assert if_node.cond[1] == "some_expr"
