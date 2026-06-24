"""v0-issue-2 AST 节点 shape 测试。

按 issue #24 acceptance criteria 验证 AST dataclass 与错误类的形状。
"""
import sys

import pytest
from dataclasses import is_dataclass

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")


# 1. 全部 import 成功
def test_all_imports_succeed():
    """issue body AC #1：17 个类型 + 3 个单例 + ParserError 全部可 import。"""
    from core.engine import ast_nodes as n

    expected_types = [
        # 元数据
        "IdMeta", "IdStart", "IdEnd",
        # 块结构
        "BlockLocation", "NextDecl", "Block", "Story",
        # 块内执行
        "Start", "End", "Text", "In", "Echo", "NextId",
        "CallExpression", "Branch", "If",
        "DecoratorCall", "DecoratorStop",
        # 单例
        "START", "END", "ID_START",
        # 错误
        "ParserError",
    ]
    missing = [name for name in expected_types if not hasattr(n, name)]
    assert not missing, f"ast_nodes 缺少定义: {missing}"


# 2. 所有 dataclass 都是 frozen + slots
def test_all_dataclasses_are_frozen_and_slotted():
    from core.engine.ast_nodes import (
        IdMeta, IdStart, IdEnd,
        BlockLocation, NextDecl, Block, Story,
        Start, End, Text, In, Echo, NextId,
        CallExpression, Branch, If,
        DecoratorCall, DecoratorStop,
    )

    dataclasses = [
        IdMeta, IdStart, IdEnd,
        BlockLocation, NextDecl, Block, Story,
        Start, End, Text, In, Echo, NextId,
        CallExpression, Branch, If,
        DecoratorCall, DecoratorStop,
    ]
    for cls in dataclasses:
        assert is_dataclass(cls), f"{cls.__name__} 不是 dataclass"
        assert cls.__dataclass_params__.frozen, f"{cls.__name__} 不是 frozen"
        assert "__slots__" in cls.__dict__, f"{cls.__name__} 没启用 slots"

    # 额外：用 sentinel 实例验证 frozen 真的冻结
    from core.engine.ast_nodes import START
    with pytest.raises(Exception):  # FrozenInstanceError
        START.lineno = 999  # type: ignore[misc]


# 3. START/END/ID_START 模块级单例
def test_start_end_idstart_are_module_singletons():
    from core.engine import ast_nodes as n

    assert isinstance(n.START, n.Start)
    assert isinstance(n.END, n.End)
    assert isinstance(n.ID_START, n.IdStart)
    # sentinel 实例化空字段时仍为相等
    assert n.START == n.Start()
    assert n.END == n.End()
    assert n.ID_START == n.IdStart()


# 4. Text 节点构造 + 相等
def test_text_node_constructs_and_compares():
    from core.engine.ast_nodes import Text

    t1 = Text(content="hello")
    t2 = Text(content="hello")
    t3 = Text(content="world")
    assert t1 == t2
    assert t1 != t3
    assert t1.content == "hello"


# 5. NextDecl var_name=None = 单 next 简写
def test_nextdecl_var_name_none_means_singleton_shortcut():
    from core.engine.ast_nodes import NextDecl

    short = NextDecl(var_name=None, target_id="c1")
    full = NextDecl(var_name="t_a", target_id="ca")
    assert short.var_name is None
    assert short.target_id == "c1"
    assert full.var_name == "t_a"
    assert full.target_id == "ca"
    # 互不相等
    assert short != full


# 6. If cond 是 (kind, name) tuple
def test_if_cond_is_tuple_kind_name():
    from core.engine.ast_nodes import If, Branch, NextDecl

    # 多元：cond = ("var", "p_pick")
    if_node = If(
        cond=("var", "p_pick"),
        branches=(
            Branch(value=1, target=NextDecl(var_name="t_a", target_id="ca")),
            Branch(value=2, target=NextDecl(var_name="t_b", target_id="cb")),
        ),
    )
    assert if_node.cond == ("var", "p_pick")
    assert len(if_node.branches) == 2

    # 简略二元：cond = ("expr", "some_expr")
    expr_if = If(
        cond=("expr", "node_xxx"),
        branches=(
            Branch(value=0, target=NextDecl(var_name="a", target_id="aa")),
            Branch(value=1, target=NextDecl(var_name="b", target_id="bb")),
        ),
    )
    assert expr_if.cond[0] == "expr"


# 7. Branch.target Union: NextDecl | CallExpression
def test_branch_target_unions_nextdecl_and_call_expression():
    from core.engine.ast_nodes import Branch, NextDecl, CallExpression

    b_next = Branch(value=1, target=NextDecl(var_name="t_a", target_id="ca"))
    b_echo = Branch(value=3, target=CallExpression(kind="echo", var="p_pick"))
    b_in = Branch(value=4, target=CallExpression(kind="in", var="p_mood"))

    assert isinstance(b_next.target, NextDecl)
    assert isinstance(b_echo.target, CallExpression)
    assert b_echo.target.kind == "echo"
    assert b_in.target.kind == "in"


# 8. ParserError 带 loc
def test_parser_error_carries_location():
    from core.engine.ast_nodes import ParserError, BlockLocation

    loc = BlockLocation(lineno=42, col=7)
    err = ParserError("test error", loc=loc)
    assert err.loc is loc
    assert err.loc.lineno == 42
    assert "test error" in str(err)

    # loc 可选
    err2 = ParserError("no loc")
    assert err2.loc is None


# ─── D1 修法: BOOL_EXPR_KIND 常量 ────────────────────────────────────────────


def test_bool_expr_kind_constant_exists():
    """D1 修法: ast_nodes 暴露 BOOL_EXPR_KIND 常量 (值 'bool_expr')。

    业务代码可引用此常量, 避免硬编码字符串字面量。
    """
    from core.engine import ast_nodes as n

    assert hasattr(n, "BOOL_EXPR_KIND"), (
        "ast_nodes 应暴露 BOOL_EXPR_KIND 常量"
    )
    assert n.BOOL_EXPR_KIND == "bool_expr"


def test_if_cond_accepts_bool_expr_kind():
    """D1 修法: If.cond 接受 ('bool_expr', expr_str) 第三种 kind。"""
    from core.engine.ast_nodes import If, Branch, NextDecl

    if_node = If(
        cond=("bool_expr", "tall >= 18"),
        branches=(
            Branch(value=0, target=NextDecl(var_name="a", target_id="aa")),
            Branch(value=1, target=NextDecl(var_name="b", target_id="bb")),
        ),
    )
    assert if_node.cond == ("bool_expr", "tall >= 18")
    assert if_node.cond[0] == "bool_expr"


# ─── D5 修法: simpleeval 版本锁定 ────────────────────────────────────────────


def test_simpleeval_version_pinned_exact():
    """D5 修法: pyproject.toml 中 simpleeval 必须精确锁定到具体版本 (==X.Y.Z)。

    调研结果 (simpleeval PyPI + GitHub releases 2026-06-24):
    - 0.9.13: 最后 0.9.x
    - 1.0.0 (2024-10-05): 稳定版 - 沙箱逃逸修复, 字典推导支持, 自定义异常
    - 1.0.5 (2026-03-13): 安全修复 CVE-2026-32640 (BREAKING: 模块不再直接可访问)
    - 1.0.7 (2026-03-16): 最新, 1.0.5/1.0.6 安全修复的性能回退修复

    当前选用 1.0.7 (最新稳定, 含安全修复 + 性能修复)。
    """
    import re
    from pathlib import Path

    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")

    # 找 dependencies 段中的 simpleeval 行 (双引号包裹的依赖字符串)
    # 模式: "..." 简单字符串, 内含 simpleeval==X.Y.Z
    m = re.search(r'"simpleeval\s*([^\s"#]+)"', content)
    assert m, (
        "pyproject.toml 应在 dependencies 列表中包含 "
        '"simpleeval<spec>" 形式的依赖声明'
    )
    spec = m.group(1).strip()

    # 应为精确锁定 (==X.Y.Z 形式)
    assert spec.startswith("=="), (
        f"D5 修法: simpleeval 应精确锁定 (==X.Y.Z), 当前: {spec!r}"
    )
    version = spec[2:]
    # 版本号格式: X.Y.Z (semver 简化)
    assert re.match(r"^\d+\.\d+\.\d+$", version), (
        f"版本号应符合 X.Y.Z 格式, 当前: {version!r}"
    )


def test_simpleeval_installed_version_matches_pin():
    """D5 修法: 当前环境安装的 simpleeval 版本应与 pyproject.toml 锁定的版本一致。

    验证: pip metadata 显示的版本 == pyproject.toml 锁定的版本。
    """
    import importlib.metadata as md
    import re
    from pathlib import Path

    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")
    m = re.search(r'"simpleeval\s*==\s*(\d+\.\d+\.\d+)"', content)
    assert m, "pyproject.toml 应在 dependencies 中包含 'simpleeval==X.Y.Z' 锁定"
    pinned = m.group(1)

    installed = md.version("simpleeval")
    assert installed == pinned, (
        f"环境安装的 simpleeval {installed!r} 与 pyproject 锁定 {pinned!r} 不一致"
    )


def test_simpleeval_pin_exists_in_pypi():
    """D5 修法: 锁定的版本必须在 PyPI 上存在 (避免 pin 到不存在的版本)。

    查询 PyPI JSON API, 验证锁定的版本号在 releases 列表里。
    """
    import json
    import re
    import urllib.request
    from pathlib import Path

    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")
    m = re.search(r'"simpleeval\s*==\s*(\d+\.\d+\.\d+)"', content)
    assert m, "pyproject.toml 应在 dependencies 中包含 'simpleeval==X.Y.Z' 锁定"
    pinned = m.group(1)

    req = urllib.request.Request(
        "https://pypi.org/pypi/simpleeval/json",
        headers={"Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    releases = data.get("releases", {})

    assert pinned in releases, (
        f"PyPI simpleeval 中无版本 {pinned!r} (仅可用的: {sorted(releases)[:5]}...)"
    )
