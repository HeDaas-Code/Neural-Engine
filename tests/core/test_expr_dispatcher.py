"""v1 ExprDispatcher 测试：simpleeval → fallback 二层调度。

按 ADR-0004 验证:
- eval_bool 返回正确 bool
- eval_int 返回正确 int
- 错误路径 (变量未定义 / 函数未定义 / 语法错) → ExprError
- names 引用同步 (state.vars 修改后下次 eval 用新值)
"""
import pytest

from core.engine.expr import (  # noqa: E402
    ExprDispatcher, CustomExecutor, ExprError, BUILTIN_FUNCS,
)


class FakeState:
    """v0 GameState 子集——只暴露 .vars 属性。"""

    def __init__(self, vars: dict | None = None):
        self.vars = vars if vars is not None else {}


# 1. 基础 bool 求值
class TestEvalBool:
    def test_纯_python_表达式(self):
        s = FakeState({"tall": 20})
        d = ExprDispatcher(s)
        assert d.eval_bool("tall > 18") is True

    def test_复杂表达式(self):
        s = FakeState({"tall": 180, "name": "张三"})
        d = ExprDispatcher(s)
        assert d.eval_bool("tall >= 180 and name == '张三'") is True

    def test_或表达式(self):
        s = FakeState({"a": 1, "b": 2})
        d = ExprDispatcher(s)
        assert d.eval_bool("a == 1 or b == 3") is True


# 2. 基础 int 求值
class TestEvalInt:
    def test_返回_int(self):
        s = FakeState({"count": 5})
        d = ExprDispatcher(s)
        assert d.eval_int("count + 3") == 8

    def test_len_返回_int(self):
        s = FakeState({"items": [1, 2, 3]})
        d = ExprDispatcher(s)
        assert d.eval_int("len(items)") == 3


# 3. 错误路径
class TestErrors:
    def test_变量未定义_抛_ExprError(self):
        s = FakeState({})
        d = ExprDispatcher(s)
        with pytest.raises(ExprError):
            d.eval_bool("undefined_var == 1")

    def test_语法错_抛_ExprError(self):
        s = FakeState({})
        d = ExprDispatcher(s)
        with pytest.raises(ExprError):
            d.eval_bool("")

    def test_函数未定义_走_fallback_再失败_抛_ExprError(self):
        s = FakeState({"x": 1})
        d = ExprDispatcher(s)
        with pytest.raises(ExprError):
            d.eval("undefined_func(x)")


# 4. names 引用同步
class TestNamesSync:
    def test_state_vars_修改后_dispatcher_看到新值(self):
        """names 是引用——state.vars 修改后 dispatcher.eval 必须用新值。"""
        s = FakeState({"tall": 10})
        d = ExprDispatcher(s)
        assert d.eval_bool("tall > 18") is False
        s.vars["tall"] = 20
        assert d.eval_bool("tall > 18") is True


# 5. BUILTIN_FUNCS 注入验证
class TestBuiltinFuncs:
    def test_len_可用(self):
        s = FakeState({"items": [1, 2, 3]})
        d = ExprDispatcher(s)
        assert d.eval_int("len(items)") == 3

    def test_白名单_包含核心函数(self):
        for name in ("len", "int", "str", "bool", "min", "max", "abs", "round"):
            assert name in BUILTIN_FUNCS, f"missing builtin: {name}"


# 6. 其他求值期异常 → ExprError 兜底 (except Exception 分支)
class TestRuntimeErrors:
    def test_除零_抛_ExprError(self):
        """条件中出现除法是合理场景——ZeroDivisionError 必须被包装为 ExprError,
        而非透传绕过 executor._execute_if 的 ExprError 捕获。"""
        s = FakeState({"x": 1})
        d = ExprDispatcher(s)
        with pytest.raises(ExprError):
            d.eval("1 / 0")


# 7. eval_bool 非布尔值的真值化 (bool() 强制)
class TestBoolCoercion:
    def test_非空容器为真(self):
        s = FakeState({"items": [1, 2, 3]})
        d = ExprDispatcher(s)
        assert d.eval_bool("items") is True

    def test_空容器为假(self):
        s = FakeState({"items": []})
        d = ExprDispatcher(s)
        assert d.eval_bool("items") is False


# 8. eval_int 类型截断语义
class TestEvalIntCoercion:
    def test_浮点结果向零截断(self):
        """eval_int 内部走 int(self.eval(expr))；int(3.5)==3 是分支匹配所依赖的语义,
        锁定以防被 round/向上取整等实现替换。"""
        s = FakeState({"n": 7})
        d = ExprDispatcher(s)
        assert d.eval_int("n / 2") == 3


# 9. fallback handler 异常契约 (ADR-0004: 调度链全部失败 → ExprError)
class TestFallbackExceptionContract:
    def test_handler_抛非ExprError_包装为ExprError(self):
        """业务侧 register_evaluator 是扩展点——handler 自身抛 KeyError/ValueError 时,
        ExprDispatcher 必须按契约包装为 ExprError, 否则会绕过 executor._execute_if 的
        ExprError 捕获导致引擎崩溃 (而非走 error LogEvt 路径)。"""
        s = FakeState({})
        custom = CustomExecutor(s)
        custom.register_evaluator(r"^boom$", lambda expr, vars: vars["missing"])  # KeyError
        d = ExprDispatcher(s, custom=custom)
        with pytest.raises(ExprError):
            d.eval("boom")

    def test_handler_抛ExprError_仍为ExprError(self):
        """ExprError 路径保持原有行为 (带 simpleeval 上下文)。"""
        s = FakeState({})
        custom = CustomExecutor(s)  # 无 handler → eval_fallback 抛 ExprError
        d = ExprDispatcher(s, custom=custom)
        with pytest.raises(ExprError):
            d.eval("totally_unknown_expr")
