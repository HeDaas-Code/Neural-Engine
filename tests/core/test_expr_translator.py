"""v1-issue-1 ExprTranslator 测试：DSL → Python 表达式翻译。

按 ADR-0003 §3.2 验证:
- Chinese 关键字替换 (且→and, 或→or, 非→not, 等于→==, 大于→>...)
- 简略 ?: 翻译 (v1 占位)
- 自定义 keyword_table (v2+ 占位)
- 错误捕获 (空字符串)
"""
import sys

import pytest

REPO_ROOT = "/home/hedaas/桌面/Neural Engine"
sys.path.insert(0, f"{REPO_ROOT}/src")

from core.engine.expr import ExprTranslator, DSLSyntaxError  # noqa: E402


# 1. 基础 Chinese 关键字替换
class TestKeywordReplacement:
    def test_且_to_and(self):
        t = ExprTranslator()
        assert t.to_python_expr("p_a 且 p_b") == "p_a and p_b"

    def test_或_to_or(self):
        t = ExprTranslator()
        assert t.to_python_expr("p_a 或 p_b") == "p_a or p_b"

    def test_非_to_not(self):
        t = ExprTranslator()
        assert t.to_python_expr("非 p_a") == "not p_a"

    def test_等于_to_eq(self):
        t = ExprTranslator()
        assert t.to_python_expr("p_a 等于 1") == "p_a == 1"

    def test_大于_to_gt(self):
        t = ExprTranslator()
        assert t.to_python_expr("p_a 大于 0") == "p_a > 0"

    def test_小于_to_lt(self):
        t = ExprTranslator()
        assert t.to_python_expr("p_a 小于 0") == "p_a < 0"

    def test_大于等于_to_ge(self):
        """长的关键字必须先匹配——避免 '大于' 把 '大于等于' 拆了。"""
        t = ExprTranslator()
        result = t.to_python_expr("p_a 大于等于 18")
        assert result == "p_a >= 18"
        assert ">=" in result  # 不是 "> ="

    def test_小于等于_to_le(self):
        t = ExprTranslator()
        assert t.to_python_expr("p_a 小于等于 18") == "p_a <= 18"

    def test_不等于_to_ne(self):
        t = ExprTranslator()
        assert t.to_python_expr("p_a 不等于 0") == "p_a != 0"

    def test_组合_且_或(self):
        t = ExprTranslator()
        result = t.to_python_expr("p_a 大于等于 18 且 p_b 等于 1")
        assert result == "p_a >= 18 and p_b == 1"

    def test_组合_括号(self):
        """复合表达式括号保持。"""
        t = ExprTranslator()
        result = t.to_python_expr("(p_a 大于 0 且 p_b 等于 1) 或 p_c 等于 2")
        # 关键字替换后括号仍在
        assert "(p_a > 0 and p_b == 1) or p_c == 2" == result


# 2. 自定义 keyword_table
class TestCustomKeywordTable:
    def test_register_keyword_via_init(self):
        t = ExprTranslator(keyword_table={"在古代": "p_era==1"})
        assert t.to_python_expr("在古代") == "p_era==1"

    def test_register_keyword_via_method(self):
        t = ExprTranslator()
        t.register_keyword("在古代", "p_era==1")
        assert t.to_python_expr("在古代") == "p_era==1"


# 3. 简略 ?: ternary 翻译
class TestShortcutTernary:
    def test_simple_ternary(self):
        """v1 占位: 形如 a?b:c → (b) if (a) else (c)。"""
        t = ExprTranslator()
        result = t.to_python_expr("p_a?b:c")
        assert "if" in result
        assert "else" in result


# 4. 错误捕获
class TestErrorCases:
    def test_empty_expr_raises(self):
        t = ExprTranslator()
        with pytest.raises(DSLSyntaxError):
            t.to_python_expr("")

    def test_whitespace_only_raises(self):
        t = ExprTranslator()
        with pytest.raises(DSLSyntaxError):
            t.to_python_expr("   ")
