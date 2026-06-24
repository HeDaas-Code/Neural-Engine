"""v0-issue-11 node if 解析测试。

按 issue #33 acceptance criteria 验证 3 种 if 形态 + 分支项省略 node 前缀。
"""
import sys

import pytest

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
    # D1 修法: 简略二元 = bool 求值, 用 bool_expr kind
    assert if_node.cond == ("bool_expr", "a")
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
    # D1 修法: 简略二元 = bool 求值, 用 bool_expr kind
    assert if_node.cond[0] == "bool_expr"
    assert if_node.cond[1] == "some_expr"


# ─── D1 修法: 二元表达式 if 用 bool_expr kind ────────────────────────────────


class TestBoolExprKind:
    """D1 修法 (ADR-0004): 二元表达式 if (`node if <expr> [a, b]` / 简略 `node [a?b:c]`)
    应使用 "bool_expr" kind, 区别于多元素值匹配 ("expr" kind)。

    三种 kind 区分:
    - "var": 变量值匹配 (`node if <var_name> [a, b]` / `[1:a, 2:b]`)
    - "expr": 表达式值匹配 (`node if <expr> [1:a, 2:b]`)
    - "bool_expr": 表达式布尔求值 (`node if <expr> [a, b]` / `node [a?b:c]`)
    """

    def test_表达式二元_产生_bool_expr_kind(self):
        """`node if pick == 1 [a, b]` → cond[0] == 'bool_expr' (不是 'expr')。"""
        line = "node if pick == 1 [a,b]\n"
        if_node = parse_if_stmt(line, lineno=10, next_table=_next_table())
        assert if_node.cond[0] == "bool_expr"
        assert if_node.cond[1] == "pick == 1"
        # 行为: True → branches[0], False → branches[1]
        assert len(if_node.branches) == 2
        assert if_node.branches[0].value == 0
        assert if_node.branches[1].value == 1

    def test_简略二元_产生_bool_expr_kind(self):
        """`node [a?b:c]` → cond[0] == 'bool_expr' (不是 'expr')。"""
        line = "node [a?b:c]\n"
        if_node = parse_if_stmt(line, lineno=10, next_table=_next_table())
        assert if_node.cond[0] == "bool_expr"
        assert if_node.cond[1] == "a"

    def test_多元值匹配仍用_expr_kind(self):
        """`node if pick == 1 [1:a, 2:b]` → cond[0] 仍为 'expr' (值匹配, 不是 bool 求值)。"""
        line = "node if pick == 1 [1:a,2:b]\n"
        if_node = parse_if_stmt(line, lineno=10, next_table=_next_table())
        assert if_node.cond[0] == "expr", (
            "多元素值匹配应保留 'expr' kind; 'bool_expr' 只用于二元形式"
        )
        assert if_node.cond[1] == "pick == 1"
        assert len(if_node.branches) == 2

    def test_变量二元仍用_var_kind(self):
        """`node if cond[a, b]` → cond[0] 仍为 'var' (无回归)。"""
        line = "node if cond[a,b]\n"
        if_node = parse_if_stmt(line, lineno=10, next_table=_next_table())
        assert if_node.cond[0] == "var"
        assert if_node.cond[1] == "cond"

    def test_变量多元仍用_var_kind(self):
        """`node if cond [1:a, 2:b]` → cond[0] 仍为 'var' (无回归)。"""
        line = "node if cond [1:a,2:b]\n"
        if_node = parse_if_stmt(line, lineno=10, next_table=_next_table())
        assert if_node.cond[0] == "var"
        assert if_node.cond[1] == "cond"

    def test_复合布尔表达式_产生_bool_expr_kind(self):
        """含 `and` / `or` 的复合布尔表达式 → 仍是 bool_expr。"""
        line = "node if tall >= 18 and age > 20 [a,b]\n"
        if_node = parse_if_stmt(line, lineno=10, next_table=_next_table())
        assert if_node.cond[0] == "bool_expr"
        assert if_node.cond[1] == "tall >= 18 and age > 20"
