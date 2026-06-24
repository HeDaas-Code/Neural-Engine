"""v1 ExprDispatcher 测试：simpleeval → fallback 二层调度。

按 ADR-0004 验证:
- eval_bool 返回正确 bool
- eval_int 返回正确 int
- 错误路径 (变量未定义 / 函数未定义 / 语法错) → ExprError
- names 引用同步 (state.vars 修改后下次 eval 用新值)
"""
import pytest

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


# 6. D4 修法: except 子句收窄到 NameNotDefined / FunctionNotDefined / OperatorNotDefined
class TestExceptNarrowing:
    """D4 修法验证: dispatcher 第一层 except 不再捕获通用 InvalidExpression 基类。

    ADR-0004 B2: TypeError 捕获应收窄到 NameNotDefined / FunctionNotDefined
    (本仓库额外加 OperatorNotDefined, 同属 InvalidExpression 的具体子类)。

    新契约:
    - NameNotDefined / FunctionNotDefined / OperatorNotDefined → 走 fallback
    - 其它 InvalidExpression 子类 (含直接抛 InvalidExpression) → 落兜底 except,
      包装为 ExprError 时保留原异常类型名
    """

    def test_NameNotDefined_走_fallback_后_抛_ExprError(self):
        """NameNotDefined 是白名单子类, 应被 except 直接捕获并走 fallback。"""
        from simpleeval import NameNotDefined

        s = FakeState({})
        d = ExprDispatcher(s)

        # 注入 mock: 让 _evaluator.eval 直接抛 NameNotDefined
        def _raise(expre):
            raise NameNotDefined("undefined_var", expre)

        d._evaluator.eval = _raise

        with pytest.raises(ExprError) as exc_info:
            d.eval("undefined_var")
        # __cause__ 应保留为 NameNotDefined 实例
        assert isinstance(exc_info.value.__cause__, NameNotDefined)

    def test_FunctionNotDefined_走_fallback_后_抛_ExprError(self):
        """FunctionNotDefined 是白名单子类, 应被 except 直接捕获并走 fallback。"""
        from simpleeval import FunctionNotDefined

        s = FakeState({})
        d = ExprDispatcher(s)

        def _raise(expre):
            raise FunctionNotDefined("undef_func", expre)

        d._evaluator.eval = _raise

        with pytest.raises(ExprError) as exc_info:
            d.eval("undef_func()")
        assert isinstance(exc_info.value.__cause__, FunctionNotDefined)

    def test_OperatorNotDefined_走_fallback_后_抛_ExprError(self):
        """OperatorNotDefined 是白名单子类, 应被 except 直接捕获并走 fallback。"""
        from simpleeval import OperatorNotDefined

        s = FakeState({})
        d = ExprDispatcher(s)

        def _raise(expre):
            raise OperatorNotDefined("@@", expre)

        d._evaluator.eval = _raise

        with pytest.raises(ExprError) as exc_info:
            d.eval("a @@ b")
        assert isinstance(exc_info.value.__cause__, OperatorNotDefined)

    def test_通用_InvalidException_子类_落入兜底_except(self):
        """D4 核心: 通用 InvalidExpression (或未白名单子类) 落入兜底 except。

        旧 except (TypeError, InvalidExpression) 会捕获通用 InvalidExpression。
        新 except (TypeError, NameNotDefined, FunctionNotDefined, OperatorNotDefined)
        不再捕获——落兜底 except 包装为 ExprError, 消息中应保留原异常类型名。
        """
        from simpleeval import InvalidExpression

        class _OtherInvalid(InvalidExpression):
            """模拟 simpleeval 未来新增的 InvalidExpression 子类 (不在白名单)。"""
            pass

        s = FakeState({})
        d = ExprDispatcher(s)

        def _raise(expre):
            raise _OtherInvalid("custom invalid message")

        d._evaluator.eval = _raise

        with pytest.raises(ExprError) as exc_info:
            d.eval("custom_expr")
        # 兜底 except 把异常类型名写入消息
        msg = str(exc_info.value)
        assert "OtherInvalid" in msg or "InvalidExpression" in msg, (
            f"兜底 except 应包含异常类型名, 实际消息: {msg!r}"
        )
        # __cause__ 保留为原异常
        assert isinstance(exc_info.value.__cause__, _OtherInvalid)

    def test_eval_显式引用_三个白名单异常类(self):
        """D4 契约: dispatcher.eval 的 except 子句应显式引用 NameNotDefined / FunctionNotDefined / OperatorNotDefined。

        防止将来有人把 except 子句退回到 InvalidExpression 基类。
        检验方法: 用 ast 解析 eval 函数源码, 找到 except handler,
        检查 handler.type 是包含三个具体异常类的 Tuple。
        """
        import ast
        import inspect
        import textwrap
        from core.engine.expr import dispatcher as dispatcher_mod

        source = textwrap.dedent(inspect.getsource(dispatcher_mod.ExprDispatcher.eval))
        tree = ast.parse(source)
        func_def = tree.body[0]
        assert isinstance(func_def, (ast.FunctionDef, ast.AsyncFunctionDef))

        # 收集所有 except handler 的捕获类型
        caught_types: set[str] = set()

        class _Visitor(ast.NodeVisitor):
            def visit_ExceptHandler(self, node):
                if node.type is not None:
                    if isinstance(node.type, ast.Tuple):
                        for elt in node.type.elts:
                            if isinstance(elt, ast.Name):
                                caught_types.add(elt.id)
                    elif isinstance(node.type, ast.Name):
                        caught_types.add(node.type.id)
                self.generic_visit(node)

        _Visitor().visit(func_def)

        # 三个具体异常类必须在 except 子句中
        for cls in ("NameNotDefined", "FunctionNotDefined", "OperatorNotDefined"):
            assert cls in caught_types, (
                f"except 子句应显式捕获 {cls}, 实际捕获: {caught_types}"
            )
