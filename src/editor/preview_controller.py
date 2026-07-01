"""PreviewController —— v4-03 实时预览 + 断点调试（#111）。

职责：
- `BreakpointManager`：线程安全断点集合（增删改查）
- `PreviewController`：编排 Executor 在 worker 线程运行 + 跨线程暂停/继续/单步/停止
- 块级状态快照：before_block 钩子捕获 (block_id, vars, path) 供 GUI 读取

设计：
- 纯 Python（无 PyQt6 依赖），便于测试 + 与 PyQt6 面板层解耦
- Executor 加 before_block 钩子（executor.py:121,200）→ 本模块注入
- 跨线程同步：threading.Event（暂停/恢复）+ bool flag（停止/单步）+ Lock（状态）
- Story 来源：直接接 Story 对象（可由 DslSync.parse_source(source) 或内存构造）

控制语义：
- run()：启动 worker 线程，立即运行
- pause()：请求暂停（下次 before_block 生效）
- resume()：从断点/暂停继续，清 step 模式
- step()：单步执行 1 块后再次暂停（保持 step 模式）
- stop()：停止 worker 线程（join 2s）

不变量：
- before_block 钩子在 worker 线程内调用，可抛 _StopExecution 跳出 run
- get_snapshot() 返回防御性拷贝，GUI 线程安全读取
- 断点/单步/暂停三者在 before_block 内统一判定
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Optional, Callable

from core.engine.ast_nodes import Story, Block, IdMeta, IdEnd
from core.engine.executor import Executor, GameState

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# 控制流异常
# ═══════════════════════════════════════════════════════════════════════


class _StopExecution(Exception):
    """控制流异常：停止 Executor（由 PreviewController.stop() 触发，worker 内捕获）。"""
    pass


# ═══════════════════════════════════════════════════════════════════════
# 预览状态常量
# ═══════════════════════════════════════════════════════════════════════


STATUS_IDLE = "idle"          # 未启动
STATUS_RUNNING = "running"    # 运行中
STATUS_PAUSED = "paused"      # 已暂停（断点命中 / 单步 / 手动 pause）
STATUS_STOPPED = "stopped"    # 已停止（stop 调用或执行完成）
STATUS_ERROR = "error"        # 执行异常


# ═══════════════════════════════════════════════════════════════════════
# BreakpointManager
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class BreakpointManager:
    """线程安全断点管理器。

    用法：
        bpm = BreakpointManager()
        bpm.add("c1")           # 在 c1 块设断点
        bpm.has("c1")           # True
        bpm.toggle("c1")        # False（已移除）
        bpm.list()              # []
    """
    _breakpoints: set = field(default_factory=set)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, node_id: str) -> bool:
        """添加断点。返回是否新增（已存在返回 False）。"""
        with self._lock:
            if node_id in self._breakpoints:
                return False
            self._breakpoints.add(node_id)
            return True

    def remove(self, node_id: str) -> bool:
        """移除断点。返回是否移除（不存在返回 False）。"""
        with self._lock:
            if node_id not in self._breakpoints:
                return False
            self._breakpoints.discard(node_id)
            return True

    def has(self, node_id: str) -> bool:
        """查询断点是否存在。"""
        with self._lock:
            return node_id in self._breakpoints

    def toggle(self, node_id: str) -> bool:
        """切换断点。返回切换后状态（True=已添加，False=已移除）。"""
        with self._lock:
            if node_id in self._breakpoints:
                self._breakpoints.discard(node_id)
                return False
            self._breakpoints.add(node_id)
            return True

    def clear(self) -> int:
        """清空所有断点。返回清除数量。"""
        with self._lock:
            count = len(self._breakpoints)
            self._breakpoints.clear()
            return count

    def list(self) -> list:
        """列出所有断点（按 id 排序的副本）。"""
        with self._lock:
            return sorted(self._breakpoints)


# ═══════════════════════════════════════════════════════════════════════
# PreviewController
# ═══════════════════════════════════════════════════════════════════════


class PreviewController:
    """实时预览编排器（线程安全）。

    - 从 Story 启 worker 线程跑 Executor
    - 断点：before_block 钩子检查 BreakpointManager，命中则 Event.wait() 暂停
    - 控制：run / pause / resume / step / stop
    - 状态查询：get_snapshot() 返回当前块 id + 变量字典快照

    用法：
        ctrl = PreviewController(story, sink)
        ctrl.set_breakpoint("c1")
        ctrl.run()                    # 启动 worker 线程
        # ... 断点命中后（on_paused 回调通知）...
        snap = ctrl.get_snapshot()    # 查看变量
        ctrl.resume()                 # 继续执行
        ctrl.stop()                   # 停止

    线程模型：
    - Executor 跑在 worker 线程（daemon=True）
    - 控制方法从主线程调用，通过 Event + flag 同步
    - sink 必须实现 EventSink 协议（put_evt + get_cmd）
    """

    def __init__(
        self,
        story: Story,
        sink,
        breakpoint_manager: Optional[BreakpointManager] = None,
        on_paused: Optional[Callable[[str, dict], None]] = None,
        on_finished: Optional[Callable[[str], None]] = None,
        on_block_visit: Optional[Callable[[str, dict], None]] = None,
    ):
        self._story = story
        self._sink = sink
        self._bp_mgr = breakpoint_manager or BreakpointManager()
        self._on_paused = on_paused          # (block_id, snapshot) -> None
        self._on_finished = on_finished      # (reason) -> None
        # v4-06: 每个块访问回调（执行路径追踪用）；默认 None（不影响 v4-03 行为）
        self._on_block_visit = on_block_visit

        # 跨线程同步
        self._pause_event = threading.Event()
        self._pause_event.set()  # 初始可执行
        self._stop_flag = False
        self._pause_requested = False
        self._step_mode = False
        self._lock = threading.Lock()
        self._snapshot_lock = threading.Lock()

        # 状态
        self._status: str = STATUS_IDLE
        self._current_block_id: Optional[str] = None
        self._snapshot: dict = {}
        self._thread: Optional[threading.Thread] = None
        self._executor: Optional[Executor] = None

    # ─── 属性查询 ──────────────────────────────────────────────────

    @property
    def status(self) -> str:
        with self._lock:
            return self._status

    @property
    def is_running(self) -> bool:
        return self.status == STATUS_RUNNING

    @property
    def is_paused(self) -> bool:
        return self.status == STATUS_PAUSED

    @property
    def breakpoint_manager(self) -> BreakpointManager:
        return self._bp_mgr

    # ─── 断点便捷方法 ──────────────────────────────────────────────

    def set_breakpoint(self, node_id: str) -> None:
        self._bp_mgr.add(node_id)

    def remove_breakpoint(self, node_id: str) -> None:
        self._bp_mgr.remove(node_id)

    def toggle_breakpoint(self, node_id: str) -> bool:
        return self._bp_mgr.toggle(node_id)

    # ─── 状态快照 ──────────────────────────────────────────────────

    def get_snapshot(self) -> dict:
        """取当前状态快照（线程安全防御性拷贝）。

        Returns:
            {"block_id": str|None, "vars": dict, "path": list, "status": str}
        """
        with self._snapshot_lock:
            return {
                "block_id": self._current_block_id,
                "vars": dict(self._snapshot.get("vars", {})),
                "path": list(self._snapshot.get("path", [])),
                "status": self._status,
            }

    # ─── 生命周期控制 ──────────────────────────────────────────────

    def run(self) -> bool:
        """启动预览（worker 线程跑 Executor）。已运行/暂停返回 False。"""
        with self._lock:
            if self._status in (STATUS_RUNNING, STATUS_PAUSED):
                return False
            self._status = STATUS_RUNNING
            self._stop_flag = False
            self._pause_requested = False
            self._step_mode = False
            self._pause_event.set()

        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        return True

    def pause(self) -> bool:
        """请求暂停（下次 before_block 生效）。运行中返回 True。"""
        with self._lock:
            if self._status != STATUS_RUNNING:
                return False
            self._step_mode = False
            self._pause_requested = True
            return True

    def resume(self) -> bool:
        """恢复执行（从断点/暂停继续，清 step 模式）。已暂停返回 True。"""
        with self._lock:
            if self._status != STATUS_PAUSED:
                return False
            self._status = STATUS_RUNNING
            self._step_mode = False
            self._pause_event.set()
            return True

    def step(self) -> bool:
        """单步执行一个块（从断点/暂停继续，执行 1 块后再次暂停）。已暂停返回 True。"""
        with self._lock:
            if self._status != STATUS_PAUSED:
                return False
            self._status = STATUS_RUNNING
            self._step_mode = True  # 保持 step 模式，下次 before_block 再暂停
            self._pause_event.set()
            return True

    def stop(self) -> bool:
        """停止预览（worker 线程退出）。运行/暂停中返回 True。"""
        with self._lock:
            if self._status in (STATUS_IDLE, STATUS_STOPPED, STATUS_ERROR):
                return False
            self._stop_flag = True
            self._step_mode = False
            self._pause_event.set()  # 放行阻塞

        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        with self._lock:
            self._status = STATUS_STOPPED
        if self._on_finished is not None:
            self._on_finished("stopped")
        return True

    def join(self, timeout: Optional[float] = None) -> bool:
        """等待 worker 线程结束（测试用）。返回是否已结束。"""
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            return not self._thread.is_alive()
        return True

    # ─── worker 线程 ──────────────────────────────────────────────

    def _worker(self) -> None:
        """worker 线程入口：构造 Executor + run。"""
        try:
            self._executor = Executor(
                self._story,
                self._sink,
                before_block=self._on_before_block,
            )
            self._executor.run()
            with self._lock:
                self._status = STATUS_STOPPED
            if self._on_finished is not None:
                self._on_finished("completed")
        except _StopExecution:
            with self._lock:
                self._status = STATUS_STOPPED
            if self._on_finished is not None:
                self._on_finished("stopped")
        except Exception as e:
            logger.exception("PreviewController worker error")
            with self._lock:
                self._status = STATUS_ERROR
            if self._on_finished is not None:
                self._on_finished(f"error: {e}")

    def _on_before_block(self, block: Block, state: GameState) -> None:
        """Executor 块级钩子：检查停止/断点/单步/手动暂停，捕获状态快照。"""
        # 1. 检查停止
        if self._stop_flag:
            raise _StopExecution()

        # 2. 提取 block_id
        block_id = self._extract_block_id(block)

        # 3. 捕获状态快照（供 GUI 线程读取）
        snapshot = {
            "block_id": block_id,
            "vars": dict(state.vars),
            "path": list(state.path),
        }
        with self._snapshot_lock:
            self._current_block_id = block_id
            self._snapshot = snapshot

        # v4-06: 每个块访问回调（执行路径追踪用）；在暂停判定前触发，
        # 确保每个被访问块都被记录（无论是否暂停）
        if self._on_block_visit is not None:
            try:
                self._on_block_visit(block_id, snapshot)
            except Exception:
                logger.exception("on_block_visit callback error")

        # 4. 判定是否暂停
        should_pause = False
        pause_reason = None
        with self._lock:
            if self._pause_requested:
                should_pause = True
                pause_reason = "manual"
                self._pause_requested = False
            elif self._step_mode:
                should_pause = True
                pause_reason = "step"
            elif self._bp_mgr.has(block_id):
                should_pause = True
                pause_reason = "breakpoint"

        # 5. 暂停阻塞
        if should_pause:
            with self._lock:
                self._status = STATUS_PAUSED
            # 通知 GUI（在 worker 线程内调用，GUI 需自行 marshal 到主线程）
            if self._on_paused is not None:
                try:
                    self._on_paused(block_id, snapshot)
                except Exception:
                    logger.exception("on_paused callback error")
            # 清除事件再等待：确保 wait() 真正阻塞（run() 初始 set() 不会泄漏）
            self._pause_event.clear()
            # 阻塞直到 resume/step/stop
            self._pause_event.wait()

            # 恢复后检查停止
            if self._stop_flag:
                raise _StopExecution()

            with self._lock:
                self._status = STATUS_RUNNING
            # step 模式下保持 _step_mode=True（下次 before_block 再暂停）
            # resume 已将 _step_mode 设为 False

    @staticmethod
    def _extract_block_id(block: Block) -> Optional[str]:
        """从 Block.meta 提取节点 id（IdMeta.id 或合成的 end id）。

        与 node_graph_model.extract_block_id 逻辑一致（独立实现避免循环依赖）。
        """
        for item in block.meta:
            if isinstance(item, IdMeta):
                return item.id
        for item in block.meta:
            if isinstance(item, IdEnd):
                if item.route_chapter is not None:
                    return (f"end{item.x}:{item.route_chapter}"
                            if item.x is not None else f"end:{item.route_chapter}")
                return f"end{item.x}" if item.x is not None else "end"
        return None


__all__ = [
    "BreakpointManager", "PreviewController",
    "STATUS_IDLE", "STATUS_RUNNING", "STATUS_PAUSED",
    "STATUS_STOPPED", "STATUS_ERROR",
]
