"""v1-issue-1 ExprDispatcher 测试：translator → simpleeval → fallback 三层调度。

按 ADR-0003 §3.1 验证:
- eval_bool 返回正确 bool
- eval_int 返回正确 int
- 错误路径 (变量未定义 / 函数未定义 / 语法错) → ExprError
- names 引用同步 (state.vars 修改后下次 eval 用新值)
"""
import sys

import pytest

REPO_ROOT = "/home/hedaas/桌面/Neural Engine"
sys.path.insert(0, f"{REPO_ROOT}/src")

from core.engine.expr import (  # noqa: E402
    ExprDispatcher, ExprError, BUILTIN_FUNCS,
)


class FakeState:
    """v0 GameState 子集——只暴露 .vars 属性。"""

    def __init__(self, vars: dict | None = None):
        self.vars = vars if vars is not None else {}


# 1. 基础 bool 求值
class TestEvalBool:
    def test_纯_python_表达式(self):
        s = FakeState({"p_tall": 20})
        d = ExprDispatcher(s)
        assert d.eval_bool("p_tall > 18") is True

    def test_纯_python_false(self):
        s = FakeState({"p_tall": 10})
        d = ExprDispatcher(s)
        assert d.eval_bool("p_tall > 18") is False

    def test_chinese_关键字(self):
        s = FakeState({"p_tall": 20, "p_age": 1})
        d = ExprDispatcher(s)
        assert d.eval_bool("p_tall 大于等于 18 且 p_age 等于 1") is True

    def test_或(self):
        s = FakeState({"a": 0, "b": 1})
        d = ExprDispatcher(s)
        assert d.eval_bool("a 等于 1 或 b 等于 1") is True

    def test_非(self):
        s = FakeState({"a": 0})
        d = ExprDispatcher(s)
        assert d.eval_bool("非 a 等于 1") is True  # not (a==1) = not False = True


# 2. int 求值
class TestEvalInt:
    def test_算术(self):
        s = FakeState({"x": 5})
        d = ExprDispatcher(s)
        assert d.eval_int("x + 3") == 8

    def test_函数调用(self):
        s = FakeState({"p_name": "张三"})
        d = ExprDispatcher(s)
        assert d.eval_int("len(p_name) + 1") == 3  # "张三" UTF-8 长度是 2

    def test_int_转换(self):
        s = FakeState({"p_str": "42"})
        d = ExprDispatcher(s)
        assert d.eval_int("int(p_str) * 2") == 84


# 3. 错误路径
class TestErrorPaths:
    def test_变量未定义_抛_ExprError(self):
        s = FakeState({})
        d = ExprDispatcher(s)
        with pytest.raises(ExprError):
            d.eval_bool("p_missing 等于 1")

    def test_除零_抛_ExprError(self):
        s = FakeState({})
        d = ExprDispatcher(s)
        with pytest.raises(ExprError):
            d.eval_bool("1 / 0")

    def test_翻译失败_抛_DSLSyntaxError(self):
        from core.engine.expr import DSLSyntaxError
        s = FakeState({})
        d = ExprDispatcher(s)
        with pytest.raises(DSLSyntaxError):
            d.eval_bool("")


# 4. names 引用同步
class TestNamesSync:
    def test_state_vars_修改后_dispatcher_看到新值(self):
        """names 是引用——state.vars 修改后 dispatcher.eval 必须用新值。"""
        s = FakeState({"p_tall": 10})
        d = ExprDispatcher(s)
        assert d.eval_bool("p_tall > 18") is False
        # 修改 state.vars (executor 改 vars 的场景)
        s.vars["p_tall"] = 20
        # 下次 eval 必须用新值
        assert d.eval_bool("p_tall > 18") is True


# 5. BUILTIN_FUNCS 注入验证
class TestBuiltinFuncs:
    def test_len_可用(self):
        s = FakeState({"items": [1, 2, 3]})
        d = ExprDispatcher(s)
        assert d.eval_int("len(items)") == 3

    def test_白名单_包含核心函数(self):
        for name in ("len", "int", "str", "bool", "min", "max", "abs", "round"):
            assert name in BUILTIN_FUNCS, f"missing builtin: {name}"
