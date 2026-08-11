"""core.engine.expr.errors 错误类测试。

ExprError / UnsupportedNodeError 是表达式子系统的错误基石，
整个 dispatcher → custom → executor 链都通过它们来区分
解析期语法错（ParserError）和执行期求值错（ExprError）。

尽管 dispatcher / custom 测试覆盖了错误的使用场景，
但错误类本身的继承层级、消息传递、__cause__ 链契约
没有被独立锁定——本文件填补此缺口。
"""
import pytest

from core.engine.expr.errors import ExprError, UnsupportedNodeError


class TestExprErrorInheritance:
    def test_expr_error_is_runtime_error(self):
        """ExprError 必须继承 RuntimeError，这样 executor 的 except ExprError 能捕获它，
        同时也保持 isinstance(e, RuntimeError) 为真（通用异常处理代码不遗漏）。"""
        assert issubclass(ExprError, RuntimeError)
        assert issubclass(ExprError, Exception)

    def test_unsupported_node_is_expr_error(self):
        """UnsupportedNodeError 必须是 ExprError 的子类，
        这样 executor 的单一 except ExprError 就能兜住所有表达式错误。"""
        assert issubclass(UnsupportedNodeError, ExprError)
        assert issubclass(UnsupportedNodeError, RuntimeError)


class TestExprErrorMessage:
    def test_expr_error_empty_message(self):
        e = ExprError()
        assert str(e) == ""

    def test_expr_error_string_message(self):
        e = ExprError("boom")
        assert str(e) == "boom"

    def test_expr_error_int_message(self):
        e = ExprError(42)
        assert str(e) == "42"

    def test_expr_error_multiple_args(self):
        e = ExprError("a", "b")
        assert str(e) == "('a', 'b')"


class TestUnsupportedNodeErrorMessage:
    def test_unsupported_node_preserves_message(self):
        msg = "simpleeval does not support AST node: ClassDef"
        e = UnsupportedNodeError(msg)
        assert str(e) == msg
        assert isinstance(e, ExprError)


class TestCauseChain:
    def test_raise_from_sets_cause(self):
        root = TypeError("simpleeval hates this node")
        try:
            raise ExprError("wrapped") from root
        except ExprError as e:
            assert e.__cause__ is root
            assert e.args[0] == "wrapped"

    def test_direct_exception_without_from_has_none_cause(self):
        e = ExprError("no handler matched")
        assert e.__cause__ is None
        assert e.__context__ is None


class TestExecutorErrorBoundary:
    def test_expr_error_caught_by_except_expr_error(self):
        caught = None
        try:
            raise ExprError("eval failed")
        except ExprError as e:
            caught = e
        assert caught is not None
        assert isinstance(caught, RuntimeError)

    def test_unsupported_node_caught_by_except_expr_error(self):
        caught = None
        try:
            raise UnsupportedNodeError("AST node not supported")
        except ExprError as e:
            caught = e
        assert isinstance(caught, UnsupportedNodeError)

    def test_expr_error_not_caught_by_generic_value_error(self):
        with pytest.raises(ExprError):
            try:
                raise ExprError("real expression error")
            except ValueError:
                pass


class TestDispatcherExceptionWrappingContract:
    def test_unknown_variable_becomes_expr_error(self):
        from core.engine.expr import ExprDispatcher
        class S:
            def __init__(self): self.vars = {}
        s = S()
        d = ExprDispatcher(s)
        with pytest.raises(ExprError) as exc_info:
            d.eval("undefined_x + 1")
        assert "undefined_x" in str(exc_info.value)
        assert exc_info.value.__cause__ is not None

    def test_division_by_zero_wrapped(self):
        from core.engine.expr import ExprDispatcher
        class S:
            def __init__(self): self.vars = {"x": 1}
        s = S()
        d = ExprDispatcher(s)
        with pytest.raises(ExprError) as exc_info:
            d.eval("1 / 0")
        msg = str(exc_info.value).lower()
        assert "division" in msg or "zerodivision" in msg

    def test_fallback_handler_unhandled_becomes_expr_error(self):
        from core.engine.expr import ExprDispatcher, CustomExecutor
        class S:
            def __init__(self): self.vars = {}
        s = S()
        custom = CustomExecutor(s)
        d = ExprDispatcher(s, custom=custom)
        with pytest.raises(ExprError):
            d.eval("totally_unknown_function()")

    def test_fallback_handler_crashing_becomes_expr_error(self):
        from core.engine.expr import ExprDispatcher, CustomExecutor
        class S:
            def __init__(self): self.vars = {}
        s = S()
        custom = CustomExecutor(s)
        custom.register_evaluator(r"^boom$", lambda expr, vars: vars["missing_key"])
        d = ExprDispatcher(s, custom=custom)
        with pytest.raises(ExprError) as exc_info:
            d.eval("boom")
        assert "fallback" in str(exc_info.value).lower()