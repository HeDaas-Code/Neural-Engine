"""v2 表达式内置函数白名单测试 (ROADMAP §3.6)。

覆盖 v2 新增 5 个安全包装函数:
- randint / clamp / upper / lower / contains

分两层验证:
1. 直接调用 safe_* 函数 (单元)
2. 经 ExprDispatcher + simpleeval 求值 (集成, 贴近 DSL 真实用法)
"""
import pytest

from core.engine.expr import BUILTIN_FUNCS, ExprDispatcher, ExprError
from core.engine.expr.builtin_funcs import (
    safe_clamp, safe_contains, safe_lower, safe_randint, safe_upper,
)


class FakeState:
    """v0 GameState 子集——只暴露 .vars 属性。"""

    def __init__(self, vars: dict | None = None):
        self.vars = vars if vars is not None else {}


# ============ randint ============
class TestRandint:
    def test_返回值在闭区间内(self):
        for _ in range(200):
            r = safe_randint(1, 6)
            assert 1 <= r <= 6

    def test_单点区间返回自身(self):
        assert safe_randint(5, 5) == 5

    def test_负数区间(self):
        for _ in range(100):
            r = safe_randint(-10, -5)
            assert -10 <= r <= -5

    def test_下界大于上界抛_ValueError(self):
        with pytest.raises(ValueError):
            safe_randint(6, 1)

    def test_非_int_参数抛_TypeError(self):
        with pytest.raises(TypeError):
            safe_randint(1.5, 6)
        with pytest.raises(TypeError):
            safe_randint(1, "6")

    def test_bool_参数被拒绝(self):
        # bool 是 int 子类, 但作为随机边界无意义
        with pytest.raises(TypeError):
            safe_randint(True, 6)


# ============ clamp ============
class TestClamp:
    def test_超出上界裁剪到上界(self):
        assert safe_clamp(15, 0, 10) == 10

    def test_低于下界裁剪到下界(self):
        assert safe_clamp(-3, 0, 10) == 0

    def test_区间内保持原值(self):
        assert safe_clamp(5, 0, 10) == 5

    def test_边界值(self):
        assert safe_clamp(0, 0, 10) == 0
        assert safe_clamp(10, 0, 10) == 10

    def test_浮点数(self):
        assert safe_clamp(3.7, 0.0, 3.5) == 3.5

    def test_下界大于上界抛_ValueError(self):
        with pytest.raises(ValueError):
            safe_clamp(5, 10, 0)


# ============ upper / lower ============
class TestUpperLower:
    def test_upper_基本(self):
        assert safe_upper("abc") == "ABC"

    def test_upper_含数字与符号(self):
        assert safe_upper("a1b2_c3") == "A1B2_C3"

    def test_upper_已是大写(self):
        assert safe_upper("ABC") == "ABC"

    def test_upper_空串(self):
        assert safe_upper("") == ""

    def test_lower_基本(self):
        assert safe_lower("ABC") == "abc"

    def test_lower_含数字与符号(self):
        assert safe_lower("A1B2_C3") == "a1b2_c3"

    def test_upper_非_str_抛_TypeError(self):
        with pytest.raises(TypeError):
            safe_upper(123)
        with pytest.raises(TypeError):
            safe_upper(["a"])

    def test_lower_非_str_抛_TypeError(self):
        with pytest.raises(TypeError):
            safe_lower(123)


# ============ contains ============
class TestContains:
    def test_list_命中(self):
        assert safe_contains([1, 2, 3], 2) is True

    def test_list_未命中(self):
        assert safe_contains([1, 2, 3], 9) is False

    def test_str_子串命中(self):
        assert safe_contains("hello", "ell") is True

    def test_str_子串未命中(self):
        assert safe_contains("hello", "xyz") is False

    def test_dict_键命中(self):
        assert safe_contains({"a": 1, "b": 2}, "a") is True

    def test_dict_键未命中(self):
        assert safe_contains({"a": 1, "b": 2}, "z") is False

    def test_tuple_命中(self):
        assert safe_contains((1, 2, 3), 3) is True

    def test_set_命中(self):
        assert safe_contains({1, 2, 3}, 2) is True

    def test_不可迭代容器抛_TypeError(self):
        with pytest.raises(TypeError):
            safe_contains(123, 1)


# ============ BUILTIN_FUNCS 白名单 ============
class TestWhitelist:
    def test_5_个新函数已注册(self):
        for name in ("randint", "clamp", "upper", "lower", "contains"):
            assert name in BUILTIN_FUNCS, f"missing builtin: {name}"

    def test_核心函数仍在(self):
        # 现有 test_expr_dispatcher 也断言这 8 个, 这里复述防止误删
        for name in ("int", "str", "float", "bool", "len", "min", "max", "abs", "round"):
            assert name in BUILTIN_FUNCS

    def test_白名单不含危险函数(self):
        for danger in ("__import__", "open", "eval", "exec", "compile", "getattr", "setattr"):
            assert danger not in BUILTIN_FUNCS


# ============ 经 ExprDispatcher 集成 (贴近 DSL 用法) ============
class TestViaDispatcher:
    def test_randint_求值在区间内(self):
        d = ExprDispatcher(FakeState({}))
        for _ in range(50):
            r = d.eval_int("randint(1, 6)")
            assert 1 <= r <= 6

    def test_randint_用于_if_表达式(self):
        # ROADMAP §3.6 验收场景: node if randint(1, 6) == 6 [lucky, unlucky]
        d = ExprDispatcher(FakeState({}))
        # 多次求值, 确认始终返回 bool 且语法通路正确
        for _ in range(50):
            assert isinstance(d.eval_bool("randint(1, 6) == 6"), bool)

    def test_clamp_求值(self):
        d = ExprDispatcher(FakeState({}))
        assert d.eval_int("clamp(15, 0, 10)") == 10
        assert d.eval_int("clamp(-3, 0, 10)") == 0
        assert d.eval_int("clamp(5, 0, 10)") == 5

    def test_upper_求值(self):
        d = ExprDispatcher(FakeState({}))
        assert d.eval("upper('abc')") == "ABC"

    def test_lower_求值(self):
        d = ExprDispatcher(FakeState({}))
        assert d.eval("lower('ABC')") == "abc"

    def test_contains_求值_list(self):
        d = ExprDispatcher(FakeState({"items": [1, 2, 3]}))
        assert d.eval_bool("contains(items, 2)") is True
        assert d.eval_bool("contains(items, 9)") is False

    def test_contains_求值_str_子串(self):
        d = ExprDispatcher(FakeState({"msg": "hello"}))
        assert d.eval_bool("contains(msg, 'ell')") is True
        assert d.eval_bool("contains(msg, 'xyz')") is False

    def test_upper_作用于变量(self):
        d = ExprDispatcher(FakeState({"name": "张三"}))
        # 中文无大小写, 但确认变量注入通路工作
        assert d.eval("upper(name)") == "张三"

    def test_函数组合_clamp_包裹_randint(self):
        d = ExprDispatcher(FakeState({}))
        # randint(1, 100) 再 clamp 到 [10, 20]
        for _ in range(50):
            r = d.eval_int("clamp(randint(1, 100), 10, 20)")
            assert 10 <= r <= 20

    def test_错误参数_经_dispatcher_包装为_ExprError(self):
        d = ExprDispatcher(FakeState({}))
        with pytest.raises(ExprError):
            d.eval("randint(6, 1)")  # a > b → ValueError → ExprError
        with pytest.raises(ExprError):
            d.eval("upper(123)")  # 非 str → TypeError → ExprError
        with pytest.raises(ExprError):
            d.eval("contains(123, 1)")  # 不可迭代 → ExprError
