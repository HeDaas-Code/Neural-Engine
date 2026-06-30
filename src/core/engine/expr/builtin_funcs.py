"""v1/v2 表达式子系统内置函数白名单 (按 ADR-0003 §3.4 + ROADMAP §3.6)。

simpleeval.functions 注入此白名单——DSL 创作者只能调这些函数,
不能调 os.system / __import__ 等危险函数。

v2 (ROADMAP §3.6) 新增 5 个安全包装函数:
- randint  受控随机 (不暴露 random 模块本体)
- clamp    范围裁剪
- upper    字符串大写
- lower    字符串小写
- contains 包含判断

剧情自定义函数 (rand_scene / chapter_done) 仍由 CustomExecutor.register_function 注入,
不进本白名单 (避免污染"引擎内置"语义)。
"""
from __future__ import annotations

import random
from typing import Callable


def safe_randint(a: int, b: int) -> int:
    """受控随机整数——闭区间 [a, b] (ROADMAP §3.6)。

    Args:
        a: 下界 (含)
        b: 上界 (含)

    Returns:
        [a, b] 内随机整数

    Raises:
        TypeError: a/b 非 int (bool 虽是 int 子类但作为边界无意义, 一并拒绝)
        ValueError: a > b
    """
    if isinstance(a, bool) or isinstance(b, bool):
        raise TypeError("randint 边界必须为 int, 不能是 bool")
    if not isinstance(a, int) or not isinstance(b, int):
        raise TypeError("randint 边界必须为 int")
    if a > b:
        raise ValueError(f"randint 下界 {a} 大于上界 {b}")
    return random.randint(a, b)


def safe_clamp(val, lo, hi):
    """范围裁剪——val 限制在 [lo, hi] 内 (ROADMAP §3.6)。

    val < lo → lo; val > hi → hi; 否则 val 本身。

    Raises:
        ValueError: lo > hi
        TypeError: 三者类型不可比较 (如 str 与 int 混用)
    """
    if lo > hi:
        raise ValueError(f"clamp 下界 {lo} 大于上界 {hi}")
    return max(lo, min(val, hi))


def safe_upper(s: str) -> str:
    """字符串大写 (ROADMAP §3.6)。"""
    if not isinstance(s, str):
        raise TypeError("upper 参数必须为 str")
    return s.upper()


def safe_lower(s: str) -> str:
    """字符串小写 (ROADMAP §3.6)。"""
    if not isinstance(s, str):
        raise TypeError("lower 参数必须为 str")
    return s.lower()


def safe_contains(container, item) -> bool:
    """包含判断——item in container (ROADMAP §3.6)。

    支持 list / tuple / str / dict / set 等可迭代容器。

    Raises:
        TypeError: container 不支持 in 判断 (如 int)
    """
    try:
        return item in container
    except TypeError as e:
        raise TypeError(
            f"contains 第一个参数不支持 in 判断: {type(container).__name__}"
        ) from e


BUILTIN_FUNCS: dict[str, Callable] = {
    # 类型转换
    "int": int,
    "str": str,
    "float": float,
    "bool": bool,
    # 容器 / 序列
    "len": len,
    "min": min,
    "max": max,
    # 数值
    "abs": abs,
    "round": round,
    # v2 (ROADMAP §3.6) 安全包装函数
    "randint": safe_randint,    # 受控随机
    "clamp": safe_clamp,        # 范围裁剪
    "upper": safe_upper,        # 字符串大写
    "lower": safe_lower,        # 字符串小写
    "contains": safe_contains,  # 包含判断
}
