"""DebuggerModel —— v4-06 调试器数据模型（#114）。

职责：
- 包装 PreviewController，提供高层调试数据视图（变量 / 路径 / 断点 / 事件）
- 变量查看：当前 vars（实时） + 历史快照序列（暂停点捕获）
- 执行路径：已访问块 id 序列（调用栈语义，每个块都记录）
- 断点列表：委托 BreakpointManager（增删改查）
- 调试事件日志：started/paused/breakpoint/resumed/step/stopped/completed/error
- 监视变量（watch list）：跟踪特定变量当前值
- 表达式求值：对当前变量求值 Python 表达式（immediate window / watch expr）

设计：
- 纯 Python（无 PyQt6 依赖），便于测试 + 与视图层解耦
- 仿 ResourceManager / ChapterManagerModel 的 dataclass + 闭包模式
- 与 PreviewController 集成：
  - on_block_visit 回调记录执行路径（每个块）
  - on_paused 回调记录变量快照 + 暂停事件
  - on_finished 回调记录完成/停止/错误事件
- 线程安全：history/path/events/watch 访问加 Lock（worker 线程写、主线程读）
- 断点 / 控制方法直接委托 PreviewController（已是线程安全）

不变量：
- get_variables / get_variable_history / get_execution_path / get_events /
  get_watched_variables 返回防御性拷贝，外部修改不影响内部状态
- 控制方法（run/pause/resume/step/stop）委托 PreviewController，不重复实现暂停逻辑
- 历史记录有上限（max_history），超出自动裁剪最旧条目（防内存膨胀）
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional

from core.engine.ast_nodes import Story
from editor.preview_controller import (
    PreviewController, BreakpointManager,
    STATUS_IDLE, STATUS_RUNNING, STATUS_PAUSED, STATUS_STOPPED, STATUS_ERROR,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# 调试事件类型常量
# ═══════════════════════════════════════════════════════════════════════


EVENT_STARTED = "started"            # 执行启动
EVENT_PAUSED = "paused"              # 暂停（手动 / 单步）
EVENT_BREAKPOINT = "breakpoint"      # 断点命中
EVENT_RESUMED = "resumed"            # 恢复执行
EVENT_STEP = "step"                  # 单步请求
EVENT_STOPPED = "stopped"            # 已停止（stop 调用）
EVENT_COMPLETED = "completed"        # 执行完成（自然结束）
EVENT_ERROR = "error"                # 执行异常


# 默认历史记录上限（条目数）
DEFAULT_MAX_HISTORY = 1000


# ═══════════════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class VariableSnapshot:
    """变量快照条目（暂停点捕获）。

    Attributes:
        block_id: 捕获时所在块 id（None 表示未知）。
        variables: 变量字典快照（防御性拷贝）。
        path: 执行路径快照（GameState.path 的拷贝）。
        timestamp: 捕获时间戳（time.time()）。
    """
    block_id: Optional[str]
    variables: dict
    path: list
    timestamp: float


@dataclass(frozen=True, slots=True)
class DebugEvent:
    """调试事件条目。

    Attributes:
        kind: 事件类型（EVENT_* 常量之一）。
        block_id: 关联块 id（无关联为 None）。
        message: 人类可读描述。
        timestamp: 事件时间戳（time.time()）。
    """
    kind: str
    block_id: Optional[str]
    message: str
    timestamp: float


# ═══════════════════════════════════════════════════════════════════════
# DebuggerModel
# ═══════════════════════════════════════════════════════════════════════


class DebuggerModel:
    """调试器数据模型（线程安全）。

    包装 PreviewController，提供变量查看 / 执行路径 / 断点管理 / 事件日志 /
    监视变量 / 表达式求值 的高层数据视图。

    用法：
        dbg = DebuggerModel(story, sink)
        dbg.add_breakpoint("c1")
        dbg.add_watch("score")
        dbg.run()                       # 启动执行
        # ... 断点命中后 ...
        vars_now = dbg.get_variables()  # 当前变量
        path = dbg.get_execution_path() # 执行路径
        stack = dbg.get_call_stack(10)  # 最近 10 个块（调用栈）
        events = dbg.get_events()       # 事件日志
        val = dbg.evaluate_expression("score >= 80")  # 表达式求值
        dbg.resume()                    # 继续

    线程模型：
    - 控制方法 + 查询方法从主线程调用
    - 回调（on_block_visit/on_paused/on_finished）在 worker 线程触发，
      内部加 Lock 保护共享数据
    """

    def __init__(
        self,
        story: Optional[Story] = None,
        sink=None,
        *,
        breakpoint_manager: Optional[BreakpointManager] = None,
        max_history: int = DEFAULT_MAX_HISTORY,
    ):
        if max_history < 1:
            raise ValueError(f"max_history must be >= 1, got {max_history}")
        self._max_history = max_history
        self._lock = threading.Lock()
        self._var_history: list[VariableSnapshot] = []
        self._execution_path: list[str] = []
        self._events: list[DebugEvent] = []
        self._watch_list: list[str] = []

        # 创建 PreviewController 并注入回调（DebuggerModel 拥有 controller）
        self._ctrl = PreviewController(
            story,
            sink,
            breakpoint_manager=breakpoint_manager,
            on_paused=self._handle_paused,
            on_finished=self._handle_finished,
            on_block_visit=self._handle_block_visit,
        )

    # ─── 属性 ──────────────────────────────────────────────────────

    @property
    def preview_controller(self) -> PreviewController:
        """暴露底层 PreviewController（高级用法 / 测试用）。"""
        return self._ctrl

    @property
    def status(self) -> str:
        return self._ctrl.status

    @property
    def is_running(self) -> bool:
        return self._ctrl.is_running

    @property
    def is_paused(self) -> bool:
        return self._ctrl.is_paused

    @property
    def max_history(self) -> int:
        return self._max_history

    # ─── 控制方法（委托 PreviewController）──────────────────────────

    def run(self) -> bool:
        """启动执行。成功时记录 started 事件。"""
        ok = self._ctrl.run()
        if ok:
            self._emit_event(EVENT_STARTED, None, "execution started")
        return ok

    def pause(self) -> bool:
        """请求暂停。实际暂停事件由 on_paused 回调记录。"""
        return self._ctrl.pause()

    def resume(self) -> bool:
        """恢复执行。成功时记录 resumed 事件。"""
        ok = self._ctrl.resume()
        if ok:
            self._emit_event(EVENT_RESUMED, None, "execution resumed")
        return ok

    def step(self) -> bool:
        """单步执行一个块。成功时记录 step 事件（暂停事件由回调追加）。"""
        ok = self._ctrl.step()
        if ok:
            self._emit_event(EVENT_STEP, None, "step requested")
        return ok

    def stop(self) -> bool:
        """停止执行。停止事件由 on_finished 回调记录。"""
        return self._ctrl.stop()

    def join(self, timeout: Optional[float] = None) -> bool:
        """等待 worker 线程结束（测试用）。"""
        return self._ctrl.join(timeout=timeout)

    # ─── 断点管理（委托 BreakpointManager）──────────────────────────

    def list_breakpoints(self) -> list:
        """列出所有断点（按 id 排序的副本）。"""
        return self._ctrl.breakpoint_manager.list()

    def add_breakpoint(self, node_id: str) -> bool:
        """添加断点。返回是否新增。"""
        return self._ctrl.breakpoint_manager.add(node_id)

    def remove_breakpoint(self, node_id: str) -> bool:
        """移除断点。返回是否移除。"""
        return self._ctrl.breakpoint_manager.remove(node_id)

    def toggle_breakpoint(self, node_id: str) -> bool:
        """切换断点。返回切换后状态。"""
        return self._ctrl.breakpoint_manager.toggle(node_id)

    def has_breakpoint(self, node_id: str) -> bool:
        """查询断点是否存在。"""
        return self._ctrl.breakpoint_manager.has(node_id)

    def clear_breakpoints(self) -> int:
        """清空所有断点。返回清除数量。"""
        return self._ctrl.breakpoint_manager.clear()

    @property
    def breakpoint_count(self) -> int:
        return len(self._ctrl.breakpoint_manager.list())

    # ─── 变量查看 ──────────────────────────────────────────────────

    def get_variables(self) -> dict:
        """当前变量（实时快照的防御性拷贝）。

        从 PreviewController.get_snapshot() 读取当前块捕获的 vars。
        """
        return dict(self._ctrl.get_snapshot().get("vars", {}))

    def get_variable_history(self, limit: Optional[int] = None) -> list[VariableSnapshot]:
        """变量历史快照序列（暂停点捕获）。

        Args:
            limit: 可选，返回最近 N 条；None 返回全部。
        """
        with self._lock:
            if limit is None:
                return list(self._var_history)
            return list(self._var_history[-limit:])

    def clear_history(self) -> None:
        """清空变量历史 + 执行路径（保留事件日志）。"""
        with self._lock:
            self._var_history.clear()
            self._execution_path.clear()

    # ─── 监视变量（watch list）──────────────────────────────────────

    def add_watch(self, var_name: str) -> bool:
        """添加监视变量。返回是否新增。"""
        if not var_name:
            raise ValueError("watch variable name is empty")
        with self._lock:
            if var_name in self._watch_list:
                return False
            self._watch_list.append(var_name)
            return True

    def remove_watch(self, var_name: str) -> bool:
        """移除监视变量。返回是否移除。"""
        with self._lock:
            if var_name not in self._watch_list:
                return False
            self._watch_list.remove(var_name)
            return True

    def get_watch_list(self) -> list[str]:
        """监视变量名列表（副本）。"""
        with self._lock:
            return list(self._watch_list)

    def get_watched_variables(self) -> dict:
        """监视变量的当前值（{name: value}，未设置的变量值为 None）。"""
        vars_now = self.get_variables()
        with self._lock:
            names = list(self._watch_list)
        return {name: vars_now.get(name) for name in names}

    # ─── 执行路径 / 调用栈 ─────────────────────────────────────────

    def get_execution_path(self) -> list[str]:
        """完整执行路径（已访问块 id 序列，副本）。"""
        with self._lock:
            return list(self._execution_path)

    def get_call_stack(self, depth: int = 10) -> list[str]:
        """调用栈（最近 depth 个块 id，副本）。

        Args:
            depth: 栈深度（最近 N 个块）；默认 10。
        """
        if depth < 0:
            raise ValueError(f"depth must be >= 0, got {depth}")
        with self._lock:
            return list(self._execution_path[-depth:]) if depth > 0 else []

    def get_current_block_id(self) -> Optional[str]:
        """当前块 id（从实时快照读取）。"""
        return self._ctrl.get_snapshot().get("block_id")

    # ─── 事件日志 ──────────────────────────────────────────────────

    def get_events(self, limit: Optional[int] = None) -> list[DebugEvent]:
        """调试事件日志（按时间顺序，副本）。

        Args:
            limit: 可选，返回最近 N 条；None 返回全部。
        """
        with self._lock:
            if limit is None:
                return list(self._events)
            return list(self._events[-limit:])

    def clear_events(self) -> None:
        """清空事件日志。"""
        with self._lock:
            self._events.clear()

    # ─── 表达式求值 ────────────────────────────────────────────────

    def evaluate_expression(self, expr: str):
        """对当前变量求值 Python 表达式（immediate window / watch expr）。

        用 ExprDispatcher 调度（simpleeval → fallback），与执行期 if 表达式一致。
        求值基于当前变量快照（防御性拷贝，不影响执行期状态）。

        Args:
            expr: Python 表达式（如 "score >= 80" / "name == '张'" / "a + b"）。

        Returns:
            求值结果（bool / int / str 等）。

        Raises:
            ExprError: 表达式求值失败。
            ValueError: 表达式为空。
        """
        if not expr or not expr.strip():
            raise ValueError("expression is empty")
        # 延迟导入避免循环依赖 + 减少未用模块加载
        from core.engine.executor import GameState
        from core.engine.expr.dispatcher import ExprDispatcher

        vars_now = self.get_variables()
        # 用快照 vars 构造临时 GameState，求值不影响执行期
        state = GameState(vars=dict(vars_now))
        dispatcher = ExprDispatcher(state)
        return dispatcher.eval(expr)

    # ─── 快照 ──────────────────────────────────────────────────────

    def get_snapshot(self) -> dict:
        """当前完整状态快照（委托 PreviewController，防御性拷贝）。"""
        return self._ctrl.get_snapshot()

    # ─── 内部回调（worker 线程触发）─────────────────────────────────

    def _handle_block_visit(self, block_id: Optional[str], snapshot: dict) -> None:
        """每个块访问回调：记录执行路径。"""
        with self._lock:
            self._execution_path.append(block_id if block_id is not None else "")
            self._trim(self._execution_path)

    def _handle_paused(self, block_id: Optional[str], snapshot: dict) -> None:
        """暂停回调：记录变量快照 + 暂停事件。

        通过查询 BreakpointManager 判定暂停原因（断点 vs 手动/单步）。
        """
        ts = time.time()
        snap = VariableSnapshot(
            block_id=block_id,
            variables=dict(snapshot.get("vars", {})),
            path=list(snapshot.get("path", [])),
            timestamp=ts,
        )
        # 判定原因（不持 self._lock，避免与 bp_mgr 锁交叉）
        is_breakpoint = (
            block_id is not None
            and self._ctrl.breakpoint_manager.has(block_id)
        )
        if is_breakpoint:
            kind = EVENT_BREAKPOINT
            message = f"breakpoint hit at {block_id!r}"
        else:
            kind = EVENT_PAUSED
            message = f"paused at {block_id!r}"
        with self._lock:
            self._var_history.append(snap)
            self._trim(self._var_history)
            self._events.append(DebugEvent(
                kind=kind, block_id=block_id, message=message, timestamp=ts,
            ))
            self._trim(self._events)

    def _handle_finished(self, reason: str) -> None:
        """完成回调：记录 stopped / completed / error 事件。"""
        if reason.startswith("error"):
            self._emit_event(EVENT_ERROR, None, reason)
        elif reason == "completed":
            self._emit_event(EVENT_COMPLETED, None, "execution completed")
        else:  # "stopped" 或其他
            self._emit_event(EVENT_STOPPED, None, "execution stopped")

    # ─── 内部工具 ──────────────────────────────────────────────────

    def _emit_event(
        self,
        kind: str,
        block_id: Optional[str],
        message: str,
        ts: Optional[float] = None,
    ) -> None:
        """记录一条调试事件（线程安全）。"""
        ts = ts if ts is not None else time.time()
        with self._lock:
            self._events.append(DebugEvent(
                kind=kind, block_id=block_id, message=message, timestamp=ts,
            ))
            self._trim(self._events)

    def _trim(self, lst: list) -> None:
        """裁剪列表到 max_history 上限（删除最旧条目）。"""
        overflow = len(lst) - self._max_history
        if overflow > 0:
            del lst[:overflow]


__all__ = [
    "DebuggerModel", "VariableSnapshot", "DebugEvent",
    "EVENT_STARTED", "EVENT_PAUSED", "EVENT_BREAKPOINT",
    "EVENT_RESUMED", "EVENT_STEP", "EVENT_STOPPED",
    "EVENT_COMPLETED", "EVENT_ERROR",
    "DEFAULT_MAX_HISTORY",
]
