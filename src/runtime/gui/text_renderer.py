"""TextRenderer —— v3-01 AVG 对话框渲染组件。

职责：
- 接收 TextEvt → 富文本 HTML 渲染到 QTextEdit
- 打字机效果：QTimer 逐字追加（可配置 char/ms 速度）
- 名字标签：speaker 字段 → 渲染为「名字」+ 对话
- @style 应用：读取当前 style 状态（color/font/size）应用到 display
- 点击/空格跳过打字机动画（立即显示全文）
- is_typing 属性供 MainWindow 查询（打字机进行中禁用输入框）

设计：
- 不直接 import PyQt6（lazy import），便于测试注入 fake qt
- 接受 QTextEdit 实例（由 MainWindow 注入），不自己创建 widget
- 打字机用 QTimer.singleShot 递归调度，每 tick 追加一个字
- @style 全局应用：setStyleSheet 到 display（QTextEdit 全局生效）
  这样打字机逐字 insertPlainText 时颜色自动正确
"""
from __future__ import annotations

import html as html_mod
from typing import Optional

from core.engine.protocol import TextEvt


# 默认打字机速度（ms/char）
DEFAULT_CHAR_DELAY_MS = 40


def _build_style_css(style: dict) -> str:
    """从 style dict 构造 CSS 字符串（用于 QTextEdit.setStyleSheet）。

    支持 color / font / size 三键（@style 装饰器约定）。
    """
    parts = []
    if "color" in style:
        parts.append(f"color: {html_mod.escape(style['color'])}")
    if "font" in style:
        parts.append(f"font-family: {html_mod.escape(style['font'])}")
    if "size" in style:
        size = style["size"]
        try:
            int(size)
            parts.append(f"font-size: {size}px")
        except (ValueError, TypeError):
            parts.append(f"font-size: {html_mod.escape(str(size))}")
    return "; ".join(parts)


def _build_html(content: str, speaker: str) -> str:
    """构造富文本 HTML 片段（不含 style，style 由 display 全局承担）。

    - speaker 非空 → <p><b>名字</b>：content</p>
    - speaker 空 → <p>content</p>（旁白）
    """
    esc = html_mod.escape(content)
    if speaker:
        esc_speaker = html_mod.escape(speaker)
        return f"<p><b>{esc_speaker}</b>：{esc}</p>"
    return f"<p>{esc}</p>"


class TextRenderer:
    """AVG 对话框文本渲染器（v3-01）。

    用法（MainWindow 集成）：
        renderer = TextRenderer(display_widget, char_delay_ms=40)
        renderer.apply_style({"color": "red"})  # @style 后调用
        renderer.render(TextEvt(content="雨夜。", speaker="旁白"))
        if renderer.is_typing:
            renderer.skip()  # 跳过动画

    线程安全：QTimer 必须在 GUI 线程调用。
    """

    def __init__(
        self,
        display_widget,
        char_delay_ms: int = DEFAULT_CHAR_DELAY_MS,
        qt: Optional[dict] = None,
    ):
        """Args:
            display_widget: QTextEdit（或 fake）实例，需 append/insertPlainText/toPlainText/setStyleSheet
            char_delay_ms: 打字机每字延迟（ms），<=0 无打字机效果（直接 append 全文）
            qt: 可选 PyQt6 modules dict（测试注入 fake）。None 时 lazy import QTimer。
        """
        self._display = display_widget
        self._char_delay_ms = char_delay_ms
        self._qt = qt
        self._timer = None
        self._pending_plain = ""  # 打字机待显示的纯文本
        self._pending_speaker = ""  # 打字机待显示的 speaker
        self._shown_chars = 0

    @property
    def is_typing(self) -> bool:
        """打字机是否进行中。"""
        return self._timer is not None

    def apply_style(self, style: dict) -> None:
        """应用 @style 到 display（全局）。

        style 是 core.decorators.style.get_last_style() 的返回值。
        支持 color / font / size 三键。
        """
        css = _build_style_css(style)
        try:
            if css:
                self._display.setStyleSheet(f"QTextEdit {{ {css} }}")
            else:
                # 空 style → 清除（恢复默认）
                self._display.setStyleSheet("")
        except Exception:
            # fake display 可能没 setStyleSheet
            pass

    def render(self, evt: TextEvt) -> None:
        """渲染一个 TextEvt。

        - 若有未完成的打字机，先 skip 它（显示上一条全文）
        - char_delay_ms > 0 → 启动打字机；<=0 → 直接 append 全文 HTML
        """
        # 若有未完成的打字机，先跳过（立即显示上一条全文）
        if self.is_typing:
            self.skip()

        if self._char_delay_ms <= 0 or not evt.content:
            # 无打字机：直接 append 完整 HTML
            self._append_html(_build_html(evt.content, evt.speaker))
            return

        # 启动打字机
        # 名字标签：打字机开始前先 append speaker 前缀（<p><b>名字</b>：）
        # 然后逐字 append content
        if evt.speaker:
            import html as h
            prefix = f"<p><b>{h.escape(evt.speaker)}</b>："
            self._append_html(prefix)
            # 留一个未闭合的 <p>，content 逐字 append 后闭合
            # —— QTextEdit 会自动闭合标签，逐字 append 后 display 状态不一致。
            # 权衡：v3-01 打字机时 speaker 前缀一次性显示，content 逐字。
            # 结束时不追加 </p>（QTextEdit 自动处理）。
        self._pending_plain = html_mod.escape(evt.content)
        self._pending_speaker = evt.speaker
        self._shown_chars = 0
        self._schedule_next_tick()

    def skip(self) -> None:
        """跳过打字机动画，立即显示全文。

        若不在打字机中，no-op。
        """
        if not self.is_typing:
            return
        self._stop_timer()
        # 立即显示剩余文本（plain，style 由全局 setStyleSheet 承担）
        remaining = self._pending_plain[self._shown_chars:]
        if remaining:
            self._insert_plain(remaining)
        self._pending_plain = ""
        self._pending_speaker = ""
        self._shown_chars = 0

    def _schedule_next_tick(self) -> None:
        """调度下一个打字机 tick。"""
        QTimer = self._get_qtimer()
        if QTimer is None:
            # 无 QTimer（测试 fake 未 inject）→ fallback 直接显示全文
            self._insert_plain(self._pending_plain)
            self._pending_plain = ""
            return
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(self._char_delay_ms)

    def _on_tick(self) -> None:
        """打字机 tick：追加一个字符。"""
        if self._shown_chars >= len(self._pending_plain):
            self._stop_timer()
            self._pending_plain = ""
            return
        ch = self._pending_plain[self._shown_chars]
        self._shown_chars += 1
        self._insert_plain(ch)
        self._schedule_next_tick()

    def _stop_timer(self) -> None:
        """停止当前打字机 timer。"""
        if self._timer is not None:
            try:
                self._timer.stop()
            except Exception:
                pass
            self._timer = None

    def _append_html(self, html: str) -> None:
        """安全 append HTML 到 display（兼容 fake）。"""
        try:
            self._display.append(html)
        except Exception:
            self._insert_plain(html)

    def _insert_plain(self, text: str) -> None:
        """安全 insertPlainText（兼容 fake）。"""
        try:
            self._display.insertPlainText(text)
        except Exception:
            try:
                self._display.append(text)
            except Exception:
                pass

    def _get_qtimer(self):
        """lazy 取 QTimer（从注入的 qt dict 或 importlib）。"""
        if self._qt is not None:
            return self._qt.get("QTimer")
        try:
            from PyQt6.QtCore import QTimer
            return QTimer
        except ImportError:
            return None


__all__ = ["TextRenderer", "DEFAULT_CHAR_DELAY_MS", "_build_html", "_build_style_css"]
