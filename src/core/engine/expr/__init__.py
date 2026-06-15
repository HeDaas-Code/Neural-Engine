"""v1 表达式子系统骨架。

本子包负责"DSL 表达式文本 → bool/int" 求值,
与 interpreter(解析) / executor(执行) 平行, 不依赖 UI 层。

模块结构:
- errors: 表达式求值 + DSL 翻译错误类
- builtin_funcs: simpleeval 函数白名单
- translator: DSL 文本 → Python 表达式字符串
- custom: simpleeval 兜底 + 业务侧扩展钩子
- dispatcher: translator → simpleeval → fallback 调度

公开 API (按 ADR-0003 §3):
- ExprDispatcher: 调度器入口
- ExprTranslator: DSL 翻译器
- CustomExecutor: fallback 钩子
- ExprError / DSLSyntaxError / UnsupportedNodeError: 错误类
- BUILTIN_FUNCS: 函数白名单常量
"""
from core.engine.expr.errors import (
    ExprError,
    UnsupportedNodeError,
    DSLSyntaxError,
)
from core.engine.expr.builtin_funcs import BUILTIN_FUNCS
from core.engine.expr.translator import ExprTranslator
from core.engine.expr.custom import CustomExecutor
from core.engine.expr.dispatcher import ExprDispatcher

__all__ = [
    "ExprDispatcher",
    "ExprTranslator",
    "CustomExecutor",
    "ExprError",
    "UnsupportedNodeError",
    "DSLSyntaxError",
    "BUILTIN_FUNCS",
]
