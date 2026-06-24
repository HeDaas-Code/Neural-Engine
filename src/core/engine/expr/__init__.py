"""v1 表达式子系统骨架。

本子包负责"Python 表达式 → bool/int" 求值,
与 interpreter(解析) / executor(执行) 平行, 不依赖 UI 层。

模块结构:
- errors: 表达式求值错误类
- builtin_funcs: simpleeval 函数白名单
- custom: simpleeval 兜底 + 业务侧扩展钩子
- dispatcher: simpleeval → fallback 调度

公开 API (按 ADR-0004):
- ExprDispatcher: 调度器入口
- CustomExecutor: fallback 钩子
- ExprError / UnsupportedNodeError: 错误类
- BUILTIN_FUNCS: 函数白名单常量
"""
from core.engine.expr.errors import (
    ExprError,
    UnsupportedNodeError,
)
from core.engine.expr.builtin_funcs import BUILTIN_FUNCS
from core.engine.expr.custom import CustomExecutor
from core.engine.expr.dispatcher import ExprDispatcher

__all__ = [
    "ExprDispatcher",
    "CustomExecutor",
    "ExprError",
    "UnsupportedNodeError",
    "BUILTIN_FUNCS",
]
