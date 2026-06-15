"""v1 CustomExecutor: simpleeval fallback + 业务侧扩展钩子 (按 ADR-0003 §3.3)。

职责:
- simpleeval 失败时接管求值 (UnsupportedNodeError 触发)
- 业务侧可通过 register_* 注册:
  - 剧情自定义函数 (rand_scene / chapter_done)
  - 自定义 AST 节点 (v2+ 拓展)
  - 自定义表达式 (register_evaluator 走正则匹配)
- eval_fallback 顺序: _expr_handlers 正则 → 抛 ExprError

v1 阶段仅实现:
- register_function / register_evaluator
- eval_fallback 占位 (v2 拓展节点级 handler)

v2+ 扩展:
- register_node 支持自定义 AST 节点
- 异步表达式支持
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

        # ExprDispatcher 内部捕获 UnsupportedNodeError 后调:
        result = custom.eval_fallback(py_expr, state.vars)
    """

    def __init__(self, state: object) -> None:
        # state 类型为 GameState, 但本模块不强依赖 (避免循环 import)
        self.state = state
        self.functions: dict[str, Callable] = {}
        # (compiled_pattern, handler) 列表, 按注册顺序匹配
        self._expr_handlers: list[tuple[re.Pattern[str], Callable]] = []

    def register_function(self, name: str, fn: Callable) -> None:
        """注册剧情自定义函数。

        例: custom.register_function("rand_scene", lambda: random.randint(1, 5))

        ExprDispatcher 构造时会把本表注入到 simpleeval.functions——本方法
        仅是声明, 实际生效在 dispatcher.eval_* 调用时。

        Args:
            name: 函数名 (DSL 中可调)
            fn: 函数实现
        """
        self.functions[name] = fn

    def register_node(self, node_kind: type, handler: Callable) -> None:
        """注册自定义 AST 节点 handler (v2+ 拓展位, v1 阶段仅占位)。

        Args:
            node_kind: simpleeval AST 节点类型 (如 ast.Call)
            handler: (ast_node, vars) -> Any
        """
        # v1 占位, 不做实现——保持接口稳定, v2 再实现
        raise NotImplementedError(
            "CustomExecutor.register_node is v2+ feature, not yet implemented"
        )

    def register_evaluator(self, pattern: str, handler: Callable) -> None:
        """注册自定义表达式 (走正则匹配)。

        ExprDispatcher 在 simpleeval 失败时按本表**注册顺序**匹配,
        第一个匹配上的 handler 接管求值。

        Args:
            pattern: 正则表达式字符串
            handler: (py_expr: str, vars: dict) -> Any
        """
        compiled = re.compile(pattern)
        self._expr_handlers.append((compiled, handler))

    def eval_fallback(self, py_expr: str, vars: dict) -> object:
        """simpleeval 失败时调用: 按 _expr_handlers 顺序匹配正则。

        Args:
            py_expr: ExprTranslator 翻译后的 Python 表达式
            vars: GameState.vars 快照

        Returns:
            handler 返回值 (ExprDispatcher 期望 bool 或 int)

        Raises:
            ExprError: 所有 handler 都不匹配
        """
        for pattern, handler in self._expr_handlers:
            if pattern.match(py_expr):
                return handler(py_expr, vars)
        raise ExprError(
            f"unsupported expression (no handler matched): {py_expr!r}"
        )
