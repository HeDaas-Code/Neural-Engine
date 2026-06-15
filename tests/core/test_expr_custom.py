"""v1-issue-1 CustomExecutor 测试：simpleeval fallback + 业务侧扩展钩子。

按 ADR-0003 §3.3 验证:
- register_function 注入剧情自定义函数
- register_evaluator 走正则匹配
- eval_fallback 顺序匹配 _expr_handlers
- 都不匹配 → ExprError
- register_node (v2+ 占位) 抛 NotImplementedError
"""
import sys

import pytest

REPO_ROOT = "/home/hedaas/桌面/Neural Engine"
sys.path.insert(0, f"{REPO_ROOT}/src")

from core.engine.expr import (  # noqa: E402
    CustomExecutor, ExprDispatcher, ExprError,
)


class FakeState:
    def __init__(self, vars: dict | None = None):
        self.vars = vars if vars is not None else {}


# 1. register_function
class TestRegisterFunction:
    def test_注册后_simpleeval_可调(self):
        s = FakeState({"p_id": 5})
        custom = CustomExecutor(s)
        custom.register_function("is_quest_done", lambda n: n > 3)
        d = ExprDispatcher(s, custom=custom)
        assert d.eval_bool("is_quest_done(p_id)") is True

    def test_未注册_函数_走_fallback(self):
        s = FakeState({})
        custom = CustomExecutor(s)
        # 不注册 is_quest_done, simpleeval 找不到函数
        d = ExprDispatcher(s, custom=custom)
        # 没有 handler → 抛 ExprError
        with pytest.raises(ExprError):
            d.eval("is_quest_done(5)")


# 2. register_evaluator
class TestRegisterEvaluator:
    def test_正则匹配_接管求值(self):
        s = FakeState({})
        custom = CustomExecutor(s)
        custom.register_evaluator(r"^is_quest_done\(\d+\)$", lambda expr, vars: True)
        d = ExprDispatcher(s, custom=custom)
        assert d.eval("is_quest_done(5)") is True

    def test_正则不匹配_抛_ExprError(self):
        s = FakeState({})
        custom = CustomExecutor(s)
        custom.register_evaluator(r"^chapter_\d+_done$", lambda expr, vars: True)
        d = ExprDispatcher(s, custom=custom)
        # is_quest_done 不匹配 chapter_X_done
        with pytest.raises(ExprError):
            d.eval("is_quest_done(5)")

    def test_顺序匹配_先注册先匹配(self):
        """_expr_handlers 按注册顺序匹配——v2+ 业务可控制优先级。"""
        s = FakeState({})
        custom = CustomExecutor(s)
        custom.register_evaluator(r"^foo$", lambda expr, vars: "first")
        custom.register_evaluator(r"^foo$", lambda expr, vars: "second")
        d = ExprDispatcher(s, custom=custom)
        # simpleeval "foo" 会抛 NameNotDefined → fallback 第一个 handler
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


# 3. v2+ 占位
class TestV2Placeholders:
    def test_register_node_抛_NotImplementedError(self):
        custom = CustomExecutor(FakeState())
        with pytest.raises(NotImplementedError):
            custom.register_node(object, lambda x, v: x)
