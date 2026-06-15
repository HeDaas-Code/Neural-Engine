"""v1 表达式子系统错误类。

按 ADR-0003 §3.5:
- ExprError: 表达式求值失败 (运行时兜底用)
- UnsupportedNodeError: simpleeval 遇到不支持的 AST 节点 (fallback 信号)
- DSLSyntaxError: DSL 语法无法翻译成 Python 表达式 (翻译阶段用, 继承 v0 ParserError)
"""
from __future__ import annotations

from core.engine.ast_nodes import ParserError, BlockLocation


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


class DSLSyntaxError(ParserError):
    """DSL 语法无法翻译成 Python 表达式 (翻译阶段用)。

    继承 v0 ParserError——让翻译错误与解析错误共用一种处理路径
    (block_meta 阶段尽早报, 不留到执行阶段)。

    用法:
        raise DSLSyntaxError(
            f"DSL syntax not translatable: {dsl!r}",
            loc=BlockLocation(lineno=lineno, col=1),
        )
    """
