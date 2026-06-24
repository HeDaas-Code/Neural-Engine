"""v1 表达式子系统内置函数白名单 (按 ADR-0003 §3.4)。

simpleeval.functions 注入此白名单——DSL 创作者只能调这些函数,
不能调 os.system / __import__ 等危险函数。

v2+ 扩展位: 剧情自定义函数 (rand_scene / chapter_done) 由 CustomExecutor.register_function 注入,
不进本白名单 (避免污染"引擎内置"语义)。
"""
from __future__ import annotations

from typing import Callable

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
    # v2+ 扩展位:
    # "randint": safe_randint,  # 受控随机
    # "clamp": safe_clamp,      # 范围裁剪
}
