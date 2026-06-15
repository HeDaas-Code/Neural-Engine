"""v1 DSL 表达式 → Python 表达式翻译器 (按 ADR-0003 §3.2)。

职责:
- Chinese 关键字 → Python 关键字 (且→and, 或→or, 非→not, 等于→==, 大于→>...)
- 简略 ?: → Python ternary
- DSL 自定义中缀命名 (在古代→p_era==1 via keyword table)

失败抛 DSLSyntaxError (继承 ParserError, 让翻译错误与解析错误共用处理路径)。

v1 阶段仅实现:
- 中文字段名 → Python 变量 (p_开头的简单映射)
- Chinese 关键字替换
- 简略 ?: 翻译

v2+ 扩展:
- 范围检查 (1~10 → 0/1)
- 自定义剧情命名空间
- 复杂中缀 (在 古代 → p_era==1)
"""
from __future__ import annotations

import re

from core.engine.expr.errors import DSLSyntaxError


# Chinese → Python 关键字替换表 (按 ADR-0003 §3.2)
#
# 关键约束:
# - `且`/`或` 是中缀: 两侧必须有空白或括号边界
# - `非` 是前缀: 左侧边界同, 右侧只跟空白/标识符起始
# - 比较 (`大于`/`等于` 等): 当前 v1 用直接子串替换, 不用 lookbehind/lookahead
#   (中文字符之间不会有英文标识符, 直接替换安全)
# - 顺序敏感: 长的关键字必须先 (`大于等于` 在 `大于` 之前), 避免误拆
_KEYWORD_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    # 逻辑: 中缀需 lookbehind/lookahead 边界
    # 左侧用 `(?<![\w])` ——"前面不是单词字符", 允许句首/括号/逗号/空白
    # 右侧用 `(?=[\s)])` ——"后面是空白或右括号" (中缀)
    (re.compile(r"(?<![\w])且(?=[\s)])"), " and "),
    (re.compile(r"(?<![\w])或(?=[\s)])"), " or "),
    # 非 是前缀: 左侧边界同, 右侧只跟空白/标识符起始 (避免误吃 `非常` 之类)
    (re.compile(r"(?<![\w])非(?=[\sa-zA-Z_(])"), "not "),
    # 包含: 中缀, 同 且/或
    (re.compile(r"(?<![\w])包含(?=[\s)])"), " in "),
    # 比较: 中文字符之间无英文干扰, 直接子串替换
    (re.compile(r"大于等于"), ">="),
    (re.compile(r"小于等于"), "<="),
    (re.compile(r"不等于"), "!="),
    (re.compile(r"等于"), "=="),
    (re.compile(r"大于"), ">"),
    (re.compile(r"小于"), "<"),
]


# 简略二元 ?: 翻译 (node [a?b:c] 形式)
# 注意: 这层翻译在 interpreter.parse_if_stmt 阶段已做 (走 SHORTCUT_IF_RE),
# ExprTranslator 主要处理 cond 字符串里的中缀 ?:  (v2+)
_SHORTCUT_TERNARY_RE = re.compile(
    r"^\s*(?P<a>[^?]+?)\?(?P<b>[^:]+):(?P<c>.+)\s*$"
)


# 重复空白合并 (避免 Chinese 关键字替换后 `  and  ` 双倍空格)
_COLLAPSE_WS = re.compile(r"\s+")


# 字符串字面量保护 (按 docs/prototypes/v0-issue-2-translator/NOTES.md 结论 4)
# 扫描 "..." / '...' 区间, 替换为不可见 PUA 占位符 (U+E000 私有区),
# 让关键字替换跳过这些位置, 跑完再还原.
_STRING_LITERAL_RE = re.compile(r'"[^"\n]*"|\'[^\'\n]*\'')
_SENTINEL = "\ue000"  # PUA 起始字符


def _protect_string_literals(s: str) -> tuple[str, list[str]]:
    """把字符串字面量替换为 PUA 占位符。

    Returns:
        (替换后字符串, 原文字面量列表)
    """
    protected: list[str] = []

    def _stash(m: re.Match[str]) -> str:
        token = _SENTINEL + str(len(protected)) + _SENTINEL
        protected.append(m.group(0))
        return token

    return _STRING_LITERAL_RE.sub(_stash, s), protected


def _restore_string_literals(s: str, protected: list[str]) -> str:
    """把 PUA 占位符还原为原文字面量。"""
    for i, original in enumerate(protected):
        s = s.replace(_SENTINEL + str(i) + _SENTINEL, original)
    return s


class ExprTranslator:
    """DSL 文本 → Python 表达式字符串。

    用法:
        translator = ExprTranslator()
        py_expr = translator.to_python_expr("p_tall 等于 1 且 p_name 包含 张")  # "p_tall==1 and '张' in p_name"
    """

    def __init__(self, keyword_table: dict[str, str] | None = None) -> None:
        # 业务方可在 __init__ 后用 register_keyword 扩展
        self._keyword_table: dict[str, str] = dict(keyword_table or {})

    def register_keyword(self, dsl_kw: str, py_expr: str) -> None:
        """注册 DSL 自定义中缀 (v2+ 扩展位)。

        例: translator.register_keyword("在古代", "p_era==1")
        """
        self._keyword_table[dsl_kw] = py_expr

    def to_python_expr(self, dsl: str) -> str:
        """翻译 DSL 文本 → Python 表达式字符串。

        Args:
            dsl: DSL 表达式文本 (如 "p_tall 等于 1 且 p_age 包含 18")

        Returns:
            Python 表达式字符串 (如 "p_tall==1 and '18' in p_age")

        Raises:
            DSLSyntaxError: DSL 语法无法翻译
        """
        s = dsl.strip()
        if not s:
            raise DSLSyntaxError("empty DSL expression")

        # 0. 字符串字面量保护 (NOTES 结论 4)
        s, protected = _protect_string_literals(s)

        # 1. 简略 ?: 翻译 (v1 占位, v2 拓展)
        m = _SHORTCUT_TERNARY_RE.match(s)
        if m:
            a, b, c = m.group("a").strip(), m.group("b").strip(), m.group("c").strip()
            py_a = self._apply_keyword_replacements(a)
            result = f"({b}) if ({py_a}) else ({c})"
        else:
            # 2. Chinese 关键字替换
            result = self._apply_keyword_replacements(s)

        # 3. 用户自定义 keyword_table
        for dsl_kw, py_expr in self._keyword_table.items():
            result = result.replace(dsl_kw, py_expr)

        # 4. 还原字符串字面量
        return _restore_string_literals(result, protected)

    def _apply_keyword_replacements(self, s: str) -> str:
        """按 _KEYWORD_REPLACEMENTS 表逐条替换 Chinese 关键字。

        替换后用 _COLLAPSE_WS 把多余空白压成单空格 (避免 `\\s and \\s` 替换后变 `  and  `)。
        """
        result = s
        for pattern, repl in _KEYWORD_REPLACEMENTS:
            result = pattern.sub(repl, result)
        # collapse 重复空白 + 去首尾空白
        return _COLLAPSE_WS.sub(" ", result).strip()
