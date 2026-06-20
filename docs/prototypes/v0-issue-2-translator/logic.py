"""v1-issue-2 translator prototype — 纯逻辑模块, 升 v2 translator 时会删除.

问: ExprTranslator 的 Chinese 关键字替换规则, 边界处理对不对?
- '非' 句首 vs '非法' (避免误吃)
- '大于' vs '大于等于' (顺序)
- '且'/'或' 在括号边界 (lookbehind/lookahead)
- collapse 空白

这个 prototype 让用户输入 DSL 字符串, 实时看翻译结果, 验证规则.
"""
from __future__ import annotations

import re

# 替换顺序敏感: 长的先
_BOUNDARY = r"""(?<![一-龥\w])"""  # 左侧: 不是中文/单词字符
# 右侧: 因"且/或"是中缀, "非"是前缀, 单独处理
_KEYWORD_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    # 逻辑（中缀: 右侧跟空白/右括号）
    (re.compile(r"(?<![一-龥\w])且(?=[\s)])"), " and "),
    (re.compile(r"(?<![一-龥\w])或(?=[\s)])"), " or "),
    # 非 是前缀: 右侧跟空白/标识符起始（避免 `非常`/`非法`）
    (re.compile(r"(?<![一-龥\w])非(?=[\s\(]?[a-zA-Z_(])"), "not "),
    # 包含（中缀）
    (re.compile(r"(?<![一-龥\w])包含(?=[\s)])"), " in "),
    # 比较（中文内嵌，直接子串替换）
    (re.compile(r"大于等于"), ">="),
    (re.compile(r"小于等于"), "<="),
    (re.compile(r"不等于"), "!="),
    (re.compile(r"等于"), "=="),
    (re.compile(r"大于"), ">"),
    (re.compile(r"小于"), "<"),
]

_COLLAPSE_WS = re.compile(r"\s+")


def translate_dsl(dsl: str) -> str:
    """把 DSL 翻译成 Python 表达式。"""
    s = dsl.strip()
    if not s:
        raise ValueError("empty DSL expression")
    for pat, repl in _KEYWORD_REPLACEMENTS:
        s = pat.sub(repl, s)
    return _COLLAPSE_WS.sub(" ", s).strip()


# ── 预设测试 case（让 prototype 一启动就摆出"踩坑" case）──
PRESET_CASES: list[tuple[str, str, str]] = [
    # (输入, 期望, 说明)
    ("非 p_a", "not p_a", "句首 `非`"),
    ("非常 p_a", "非常 p_a", "`非常` 不应被吃"),
    ("p_a 大于等于 18", "p_a >= 18", "`大于等于` 不是 `>==`"),
    ("非 p_a 且 p_b", "not p_a and p_b", "句首非 + 中缀且"),
    ("p_a 大于 0 且 p_b 等于 1", "p_a > 0 and p_b == 1", "组合"),
    ("(p_a 大于 0) 或 p_c", "(p_a > 0) or p_c", "括号边界"),
    ("在古代", "在古代", "未知词保留"),
]


def translate_dsl_with_ks(dsl: str, ks: dict[str, str]) -> str:
    """带 keyword_table 的翻译——TUI 用。"""
    for k, v in ks.items():
        dsl = dsl.replace(k, v)
    return translate_dsl(dsl)
