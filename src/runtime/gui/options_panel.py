"""OptionsPanel —— v3-02 选项按钮列表组件。

职责：
- 接收 PromptInputEvt.options → 动态生成 QPushButton 列表
- 按钮点击 → 调 input_sink.submit(str(索引+1))（与 node if pick==N 语义对齐）
- 无 options 时不显示（MainWindow 降级到 QLineEdit）

设计：
- 不直接 import PyQt6（lazy），便于测试注入 fake qt
- 接受 parent widget + layout（由 MainWindow 注入）
- 接受 input_sink（PyQt6InputSink）回调提交
"""
from __future__ import annotations

from typing import Optional


class OptionsPanel:
    """v3-02 选项按钮面板。

    用法（MainWindow 集成）：
        panel = OptionsPanel(parent_widget, layout, input_sink, qt=qt)
        panel.set_options(["开门", "不开门"])  # PromptInputEvt.options
        # 用户点击按钮 → input_sink.submit("1") 或 "2"
        panel.clear()  # 清空按钮（下一条文本前调用）
    """

    def __init__(self, parent_widget, layout, input_sink, qt: Optional[dict] = None):
        """Args:
            parent_widget: 父 QWidget（按钮的 parent）
            layout: QVBoxLayout/QVBoxLayout-like（addWidget 方法）
            input_sink: PyQt6InputSink（submit 方法）
            qt: 可选 PyQt6 modules dict（测试注入 fake）
        """
        self._parent = parent_widget
        self._layout = layout
        self._input_sink = input_sink
        self._qt = qt
        self._buttons: list = []  # 当前显示的 QPushButton 列表

    def set_options(self, options) -> bool:
        """设置选项列表，动态生成按钮。

        Args:
            options: list/tuple of str（选项文本）

        Returns:
            True —— 成功生成按钮（options 非空）
            False —— options 为空（调用方应降级到 QLineEdit）

        点击任意按钮 → input_sink.submit(str(index+1))（1-based 索引）。
        """
        self.clear()
        if not options:
            return False

        QPushButton = self._get_qpushbutton()
        if QPushButton is None:
            # 测试 fake 无 QPushButton → 记录 options 供断言
            self._buttons = list(options)
            return True

        for i, opt_text in enumerate(options):
            btn = QPushButton(opt_text, self._parent)
            # 捕获索引（闭包陷阱：用默认参数）
            # Qt clicked 信号会传 bool 参数，但测试 FakeSignal 可能不传 → 用 *args 容错
            btn.clicked.connect(lambda *args, idx=i: self._on_click(idx))
            self._layout.addWidget(btn)
            self._buttons.append(btn)
        return True

    def clear(self) -> None:
        """清空所有按钮。"""
        for btn in self._buttons:
            try:
                btn.setParent(None)  # 从父 widget 移除
            except Exception:
                pass
            try:
                btn.deleteLater()  # Qt 内存回收
            except Exception:
                pass
        self._buttons = []

    def _on_click(self, index: int) -> None:
        """按钮点击 → 提交 1-based 索引。"""
        # node if pick == 1 语义：pick 存储的是 1-based 索引
        self._input_sink.submit(str(index + 1))

    def _get_qpushbutton(self):
        """lazy 取 QPushButton。"""
        if self._qt is not None:
            return self._qt.get("QPushButton")
        try:
            from PyQt6.QtWidgets import QPushButton
            return QPushButton
        except ImportError:
            return None

    @property
    def button_count(self) -> int:
        """当前按钮数（测试断言用）。"""
        return len(self._buttons)


__all__ = ["OptionsPanel"]
