"""v0-issue-9 next 声明解析测试。

按 issue #31 acceptance criteria 验证 parse_next_decls。
"""
import sys

import pytest

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")

from core.engine.interpreter import parse_next_decls  # noqa: E402
from core.engine.ast_nodes import ParserError  # noqa: E402


# 1. 单 next 简写
def test_single_bare_next():
    lines = ["next: c2\n"]
    decls = parse_next_decls(lines, start_lineno=10)
    assert len(decls) == 1
    assert decls[0].var_name is None
    assert decls[0].target_id == "c2"


# 2. 单 next 带变量
def test_single_named_next():
    lines = ["t_a <-next: c2\n"]
    decls = parse_next_decls(lines, start_lineno=10)
    assert len(decls) == 1
    assert decls[0].var_name == "t_a"
    assert decls[0].target_id == "c2"


# 3. 多 next 都带变量
def test_multiple_named_nexts():
    lines = ["t_a <-next: ca\n", "t_b <-next: cb\n"]
    decls = parse_next_decls(lines, start_lineno=10)
    assert len(decls) == 2
    assert decls[0].var_name == "t_a" and decls[0].target_id == "ca"
    assert decls[1].var_name == "t_b" and decls[1].target_id == "cb"


# 4. 混合语法（1 简写 + 1 带变量）
def test_mixed_syntax_raises():
    lines = ["next: ca\n", "t_b <-next: cb\n"]
    with pytest.raises(ParserError):
        parse_next_decls(lines, start_lineno=10)


# 5. 多 next 含 1 条简写
def test_multi_next_with_one_bare_raises():
    lines = ["next: ca\n", "t_b <-next: cb\n", "t_c <-next: cc\n"]
    with pytest.raises(ParserError):
        parse_next_decls(lines, start_lineno=10)


# 6. 重复变量名
def test_duplicate_var_raises():
    lines = ["t_a <-next: ca\n", "t_a <-next: cb\n"]
    with pytest.raises(ParserError):
        parse_next_decls(lines, start_lineno=10)


# 7. 重复 target_id 合法
def test_duplicate_target_id_legal():
    lines = ["t_a <-next: same\n", "t_b <-next: same\n"]
    decls = parse_next_decls(lines, start_lineno=10)
    assert len(decls) == 2
    assert decls[0].target_id == "same"
    assert decls[1].target_id == "same"


# 8. 空输入
def test_empty_returns_empty_list():
    assert parse_next_decls([], start_lineno=10) == []
