"""v1 CustomExecutor: simpleeval fallback + 业务侧扩展钩子 (按 ADR-0004)。

职责:
- simpleeval 失败时接管求值
- 业务侧可通过 register_* 注册:
  - 剧情自定义函数 (rand_scene / chapter_done)
  - 自定义表达式 (register_evaluator 走正则匹配)
- eval_fallback 顺序: _expr_handlers 正则 → 抛 ExprError
"""
from __future__ import annotations

import re
from typing import Callable

from core.engine.expr.errors import ExprError


class CustomExecutor:
    """simpleeval fallback + 业务侧扩展钩子。

    用法:
        custom = CustomExecutor(state)
        custom.register_function("rand_scene", lambda: random.randint(1, 5))
        custom.register_evaluator(r"chapter_\\d+_done", lambda expr, vars: ...)

        # ExprDispatcher 内部捕获失败后调:
        result = custom.eval_fallback(expr, state.vars)
    """

    def __init__(self, state: object) -> None:
        self.state = state
        self.functions: dict[str, Callable] = {}
        self._expr_handlers: list[tuple[re.Pattern[str], Callable]] = []

    def register_function(self, name: str, fn: Callable) -> None:
        """注册剧情自定义函数。

        Args:
            name: 函数名 (表达式中可调)
            fn: 函数实现
        """
        self.functions[name] = fn

    def register_evaluator(self, pattern: str, handler: Callable) -> None:
        """注册自定义表达式 (走正则匹配)。

        Args:
            pattern: 正则表达式字符串
            handler: (expr: str, vars: dict) -> Any
        """
        compiled = re.compile(pattern)
        self._expr_handlers.append((compiled, handler))

    def eval_fallback(self, expr: str, vars: dict) -> object:
        """simpleeval 失败时调用: 按 _expr_handlers 顺序匹配正则。

        Args:
            expr: Python 表达式文本
            vars: GameState.vars 快照

        Returns:
            handler 返回值 (ExprDispatcher 期望 bool 或 int)

        Raises:
            ExprError: 所有 handler 都不匹配
        """
        for pattern, handler in self._expr_handlers:
            if pattern.match(expr):
                return handler(expr, vars)
        raise ExprError(
            f"unsupported expression (no handler matched): {expr!r}"
        )
