"""AutoModeController —— v3-07 Auto 模式 + 快进状态机（#97）。

职责：
- Auto 模式：文本渲染完成后自动推进（按 auto_delay_ms 延迟）
- Skip 模式：跳过打字机动画（文本一次性显示）
- 状态机：toggle_auto / toggle_skip / set_auto_delay
- 通过 on_advance 回调通知"该推进了"（MainWindow 决定如何推进）
- 通过 on_text_complete 由 TextRenderer 渲染结束时调用

设计：
- 核心状态用纯 Python 管理（auto_mode/skip_mode/pending）
- QTimer 仅用于"延迟推进"调度，可选注入（测试用 fake 或 None）
- 无 QTimer 时 notify_text_complete 立即同步调 on_advance
- cancel() 在用户手动操作 / 新 TextEvt 来时调用，避免误推进

集成点（MainWindow）：
- 构造时创建 AutoModeController（注入 on_advance=input_sink.submit("")）
- 用户按 Ctrl / 按钮触发 toggle_auto / toggle_skip
- TextRenderer.render 完成时若 skip_mode → 直接调 renderer.skip()
- _handle_evt(TextEvt) 后调 controller.notify_text_complete()
  （controller 内部判断 auto_mode，决定是否调度推进）
- 用户手动提交时 controller.cancel()
"""
from __future__ import annotations

import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


# 默认 Auto 模式推进延迟（ms）—— 文本渲染完成后等多久推进
DEFAULT_AUTO_DELAY_MS = 1500


class AutoModeController:
    """v3-07 Auto 模式 + 快进状态机。

    用法：
        ctrl = AutoModeController(
            on_advance=lambda: input_sink.submit(""),  # 推进回调
            auto_delay_ms=1500,
            qt=qt_dict,  # 可选，含 QTimer
        )
        ctrl.toggle_auto()  # 开启 Auto
        # ... TextRenderer.render 完成 →
        ctrl.notify_text_complete()  # 内部调度延迟推进
        # 用户手动操作时：
        ctrl.cancel()  # 取消待推进
    """

    def __init__(
        self,
        on_advance: Optional[Callable[[], None]] = None,
        auto_delay_ms: int = DEFAULT_AUTO_DELAY_MS,
        qt: Optional[dict] = None,
    ):
        """Args:
            on_advance: Auto 模式触发推进时的回调（通常 submit 空字符串 / 触发"下一步"）。
            auto_delay_ms: Auto 模式下文本完成后等待多久再推进。
            qt: 可选 PyQt6 modules dict（含 QTimer）。None 时 lazy import。
        """
        self._on_advance = on_advance
        self._auto_delay_ms = max(0, auto_delay_ms)
        self._qt = qt
        self._auto_mode = False
        self._skip_mode = False
        self._timer = None  # pending auto-advance timer
        self._pending = False  # 是否有待推进

    # ─── 状态查询 ───

    @property
    def auto_mode(self) -> bool:
        """Auto 模式是否开启。"""
        return self._auto_mode

    @property
    def skip_mode(self) -> bool:
        """Skip 模式是否开启（跳过打字机）。"""
        return self._skip_mode

    @property
    def has_pending(self) -> bool:
        """是否有待推进的 Auto 计时。"""
        return self._pending

    @property
    def auto_delay_ms(self) -> int:
        return self._auto_delay_ms

    # ─── 状态切换 ───

    def toggle_auto(self) -> bool:
        """切换 Auto 模式。返回切换后的状态。

        关闭 Auto 时若有 pending 推进，一并取消。
        """
        self._auto_mode = not self._auto_mode
        if not self._auto_mode:
            self.cancel()
        return self._auto_mode

    def toggle_skip(self) -> bool:
        """切换 Skip 模式。返回切换后的状态。"""
        self._skip_mode = not self._skip_mode
        return self._skip_mode

    def set_auto(self, enabled: bool) -> None:
        """显式设置 Auto 模式（不依赖当前状态）。"""
        if enabled != self._auto_mode:
            self.toggle_auto()

    def set_skip(self, enabled: bool) -> None:
        """显式设置 Skip 模式。"""
        self._skip_mode = enabled

    def set_auto_delay(self, ms: int) -> None:
        """设置 Auto 推进延迟（ms，<0 视为 0）。"""
        self._auto_delay_ms = max(0, ms)

    def set_on_advance(self, callback: Callable[[], None]) -> None:
        """替换 on_advance 回调（运行时重绑定）。"""
        self._on_advance = callback

    # ─── 事件触发 ───

    def notify_text_complete(self) -> None:
        """文本渲染完成通知。Auto 模式开启时调度延迟推进。

        - Auto 关闭 → no-op
        - Auto 开启 + delay=0 → 立即同步推进
        - Auto 开启 + delay>0 + 有 QTimer → 单次定时器
        - Auto 开启 + delay>0 + 无 QTimer → 立即同步推进（fallback）
        """
        if not self._auto_mode:
            return
        # 已有待推进 → 不重复调度（防抖）
        if self._pending:
            return
        if self._auto_delay_ms <= 0:
            self._fire_advance()
            return
        QTimer = self._get_qtimer()
        if QTimer is None:
            # 无 QTimer（测试 fake 未 inject）→ fallback 立即推进
            self._fire_advance()
            return
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fire_advance)
        self._timer.start(self._auto_delay_ms)
        self._pending = True

    def cancel(self) -> None:
        """取消待推进的 Auto 计时（用户手动操作 / 新事件来时调）。"""
        self._stop_timer()
        self._pending = False

    def reset(self) -> None:
        """完全重置（关闭 Auto/Skip + 取消 pending）。"""
        self._auto_mode = False
        self._skip_mode = False
        self.cancel()

    # ─── 内部方法 ─────────────────────────────────────────────────────────

    def _fire_advance(self) -> None:
        """触发推进回调。"""
        self._stop_timer()
        self._pending = False
        if self._on_advance is not None:
            try:
                self._on_advance()
            except Exception as e:
                logger.warning("AutoMode on_advance failed: %s", e)

    def _stop_timer(self) -> None:
        """停止当前 pending timer。"""
        if self._timer is not None:
            try:
                self._timer.stop()
            except Exception:
                pass
            self._timer = None

    def _get_qtimer(self):
        """lazy 取 QTimer（注入 qt dict 优先；否则 importlib）。"""
        if self._qt is not None:
            return self._qt.get("QTimer")
        try:
            from PyQt6.QtCore import QTimer
            return QTimer
        except ImportError:
            return None


__all__ = ["AutoModeController", "DEFAULT_AUTO_DELAY_MS"]
