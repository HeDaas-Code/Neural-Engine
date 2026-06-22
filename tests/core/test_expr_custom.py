"""v1 CustomExecutor 测试：simpleeval fallback + 业务侧扩展钩子。

按 ADR-0004 验证:
- register_function 注入剧情自定义函数
- register_evaluator 走正则匹配
- eval_fallback 顺序匹配 _expr_handlers
- 都不匹配 → ExprError
"""
import pytest

from core.engine.expr import (  # noqa: E402
    CustomExecutor, ExprDispatcher, ExprError,
)


class FakeState:
    def __init__(self, vars: dict | None = None):
        self.vars = vars if vars is not None else {}


# 1. register_function
class TestRegisterFunction:
    def test_注册后_simpleeval_可调(self):
        s = FakeState({"p_id": 1})
        custom = CustomExecutor(s)
        custom.register_function("is_question", lambda x: x == 1)
        d = ExprDispatcher(s, custom=custom)
        assert d.eval_bool("is_question(p_id)") is True

    def test_多个函数注册(self):
        s = FakeState({"a": 3, "b": 5})
        custom = CustomExecutor(s)
        custom.register_function("add", lambda x, y: x + y)
        custom.register_function("double", lambda x: x * 2)
        d = ExprDispatcher(s, custom=custom)
        assert d.eval_int("add(a, b)") == 8
        assert d.eval_int("double(a)") == 6


# 2. register_evaluator (fallback 正则)
class TestRegisterEvaluator:
    def test_simpleeval_失败时_走_fallback(self):
        s = FakeState({"p_id": 99})
        custom = CustomExecutor(s)
        custom.register_evaluator(
            r"^get_p_id$",
            lambda expr, vars: vars["p_id"],
        )
        d = ExprDispatcher(s, custom=custom)
        assert d.eval("get_p_id") == 99

    def test_多个_handler_按注册顺序匹配(self):
        s = FakeState({})
        custom = CustomExecutor(s)
        custom.register_evaluator(r"^foo$", lambda expr, vars: "first")
        custom.register_evaluator(r"^foo$", lambda expr, vars: "second")
        d = ExprDispatcher(s, custom=custom)
        assert d.eval("foo") == "first"

    def test_handler_接收_vars(self):
        s = FakeState({"p_id": 99})
        custom = CustomExecutor(s)
        custom.register_evaluator(
            r"^get_p_id$",
            lambda expr, vars: vars["p_id"],
        )
        d = ExprDispatcher(s, custom=custom)
        assert d.eval("get_p_id") == 99

    def test_无_handler_匹配_抛_ExprError(self):
        s = FakeState({})
        custom = CustomExecutor(s)
        d = ExprDispatcher(s, custom=custom)
        with pytest.raises(ExprError):
            d.eval("unknown_expr")
