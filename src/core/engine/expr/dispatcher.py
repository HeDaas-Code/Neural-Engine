"""v1 ExprDispatcher: simpleeval → fallback 二层调度 (按 ADR-0004)。

调度链:
1. simpleeval.SimpleEval.eval(expr) 求值
2. 失败 (TypeError / InvalidExpression) → CustomExecutor.eval_fallback 接管
3. 兜底失败 → ExprError

公开 API:
- ExprDispatcher.eval_bool(expr_str) -> bool
- ExprDispatcher.eval_int(expr_str) -> int
- ExprDispatcher.eval(expr_str) -> Any (底层, 不强制类型)

用法:
    dispatcher = ExprDispatcher(game_state, custom=custom)
    chosen_branch = dispatcher.eval_bool("tall >= 18")  # bool
"""
from __future__ import annotations

from simpleeval import SimpleEval
from simpleeval import InvalidExpression

from core.engine.expr.builtin_funcs import BUILTIN_FUNCS
from core.engine.expr.custom import CustomExecutor
from core.engine.expr.errors import ExprError


class ExprDispatcher:
    """表达式求值调度器: simpleeval → fallback (按 ADR-0004)。"""

    def __init__(
        self,
        state: object,
        custom: CustomExecutor | None = None,
    ) -> None:
        """构造调度器。

        Args:
            state: GameState 实例 (含 .vars 字典)
            custom: 自定义执行器 (None 时自动构造一个空白的)
        """
        self.state = state
        self.custom = custom or CustomExecutor(state)

        # 构造 simpleeval 实例——names 引用 state.vars (实时同步),
        # functions 注入 BUILTIN_FUNCS + custom.functions
        self._evaluator = SimpleEval(
            names=state.vars if hasattr(state, "vars") else {},
            functions={**BUILTIN_FUNCS, **self.custom.functions},
        )

    def eval_bool(self, expr: str) -> bool:
        """求值表达式, 返回 bool。

        同步 names 引用 (state.vars 可能被 executor 修改)。

        Args:
            expr: Python 表达式文本 (如 "tall >= 18 and name == '张'")

        Returns:
            bool 值

        Raises:
            ExprError: simpleeval 失败 + fallback 失败
        """
        return bool(self.eval(expr))

    def eval_int(self, expr: str) -> int:
        """求值表达式, 返回 int (用于 var 匹配——v0 `("var", name)` 形态扩展)。"""
        return int(self.eval(expr))

    def eval(self, expr: str) -> object:
        """求值表达式底层入口, 不强制类型。

        调度链:
        1. simpleeval.eval(expr) → 返回值
        2. TypeError / InvalidExpression → custom.eval_fallback(expr, vars)
        3. 都失败 → ExprError

        Args:
            expr: Python 表达式文本

        Returns:
            求值结果 (simpleeval 返回类型, 通常 bool/int/str)

        Raises:
            ExprError: 调度链全部失败
        """
        # simpleeval 求值
        # 同步 names 引用——state.vars 可能在 executor 中被修改
        self._evaluator.names = self.state.vars if hasattr(self.state, "vars") else {}
        try:
            return self._evaluator.eval(expr)
        except (TypeError, InvalidExpression) as e:
            # TypeError: simpleeval 遇不支持的 AST 节点
            # InvalidExpression: FunctionNotDefined / NameNotDefined / OperatorNotDefined
            #   (剧情自定义函数未注册也走 fallback, 让 CustomExecutor 接管)
            try:
                return self.custom.eval_fallback(
                    expr,
                    self.state.vars if hasattr(self.state, "vars") else {},
                )
            except ExprError:
                # fallback 也不认——重新抛, 带上原始 simpleeval 错误信息
                raise ExprError(
                    f"expression evaluation failed: {expr!r} "
                    f"(simpleeval: {e})"
                ) from e
        except Exception as e:
            # 其他错误 (ZeroDivisionError / ValueError / SyntaxError / NameError...) 直接包装
            raise ExprError(
                f"expression evaluation failed: {expr!r} ({type(e).__name__}: {e})"
            ) from e
