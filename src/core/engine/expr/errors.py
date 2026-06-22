"""v1 表达式子系统错误类。

按 ADR-0004:
- ExprError: 表达式求值失败 (运行时兜底用)
- UnsupportedNodeError: simpleeval 遇到不支持的 AST 节点 (fallback 信号)
"""
from __future__ import annotations


class ExprError(RuntimeError):
    """表达式求值失败 (运行时兜底用)。

    与 ParserError 区别:
    - ParserError: 解析期语法错误 (DSL 文本本身有错)
    - ExprError: 执行期求值错误 (文本合法, 求值失败)
    """


class UnsupportedNodeError(ExprError):
    """simpleeval 遇到不支持的 AST 节点 (fallback 信号)。

    simpleeval 遇不支持节点抛 TypeError——ExprDispatcher 捕获后
    包装成 UnsupportedNodeError 传给 CustomExecutor。
    """
