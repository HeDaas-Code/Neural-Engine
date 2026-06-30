"""PyQt6 GUI 主入口 —— v2-p0（V2-01 + EP-05）。

设计原则：
1. **模块顶层不 import PyQt6**——D3 决策要求 PyQt6 不可用时模块仍能 import
   （让 `runtime.gui.main` 工厂分发的 `from runtime.gui import pyqt6_main`
   在 PyQt6 未装时也能成功——避免 import 失败污染 CLI 路径）。
2. **`_build_main_window_class()`** 动态构造 MainWindow Qt 子类——返回 type，
   调用方注入 sink / input_sink 依赖。
3. **`_run_with_sinks(bus, sink, input_sink)`** 启动事件循环 + 清理 sink。
   PyQt6 不可用时 raise RuntimeError。
4. **`main(bus)`** 顶层入口——构造 EngineBus + 默认 sink + 调 `_run_with_sinks`。

UI 结构（V2-01 验收）：
- QTextEdit (display) —— 显示 TextEvt
- QLineEdit (input_line) —— 用户输入（returnPressed → submit）
- QPushButton (submit_button) —— 提交按钮（clicked → submit）

事件流：
- PyQt6Sink.put_evt(evt) → MainWindow._handle_evt(evt) → 更新 UI
- QLineEdit.returnPressed / QPushButton.clicked → input_sink.submit(value)
- DecoratorEvt → `core.decorators.dispatch(evt)` → 触发 @style / @bgm 钩子

D5 决策：不引入 asyncio——QThread + 信号槽跨线程通信。
"""
from __future__ import annotations

import sys
from typing import Optional

from core.engine.protocol import (
    TextEvt, PromptInputEvt, DecoratorEvt, RouteEvt, ChapterEndEvt, LogEvt,
)
from runtime.gui.pyqt6_sink import PyQt6Sink
from runtime.gui.pyqt6_input import PyQt6InputSink


# ─── Lazy import 工具 ──────────────────────────────────────────────────────


def _import_pyqt6() -> dict:
    """Lazy import PyQt6 modules。失败时抛 ImportError（让 main() 捕获转 RuntimeError）。

    返回 dict 包含 QApplication / QMainWindow / QTextEdit / QLineEdit / QPushButton /
    QWidget / QVBoxLayout / QObject / Qt / QThread / pyqtSignal。
    """
    from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QTextEdit, QLineEdit,
        QPushButton, QWidget, QVBoxLayout,
    )
    return {
        "QApplication": QApplication,
        "QMainWindow": QMainWindow,
        "QTextEdit": QTextEdit,
        "QLineEdit": QLineEdit,
        "QPushButton": QPushButton,
        "QWidget": QWidget,
        "QVBoxLayout": QVBoxLayout,
        "QObject": QObject,
        "Qt": Qt,
        "QThread": QThread,
        "pyqtSignal": pyqtSignal,
    }


# ─── MainWindow 类工厂 ──────────────────────────────────────────────────────


def _build_main_window_class(qt: Optional[dict] = None):
    """动态构造 MainWindow Qt 子类（继承 qt["QMainWindow"]）。

    关键：MainWindow 类**继承真 Qt 的 QMainWindow**，所以测试用 fake qt 时也能
    通过 isinstance 检查；构造时调 super().__init__() 进入真 QMainWindow 初始化路径。

    Args:
        qt: PyQt6 modules dict（测试可注入 fake）。None 时 lazy import。

    Returns:
        MainWindow class（type）
    """
    if qt is None:
        qt = _import_pyqt6()
    QMainWindow = qt["QMainWindow"]
    QTextEdit = qt["QTextEdit"]
    QLineEdit = qt["QLineEdit"]
    QPushButton = qt["QPushButton"]
    QWidget = qt["QWidget"]
    QVBoxLayout = qt["QVBoxLayout"]

    class MainWindow(QMainWindow):
        """PyQt6 主窗口（V2-01 验收）。"""

        def __init__(self, sink: PyQt6Sink, input_sink: PyQt6InputSink):
            super().__init__()
            # 状态保存
            self._sink = sink
            self._input_sink = input_sink
            self._closed = False

            # UI 标题
            self.setWindowTitle("Neural Engine")

            # central widget + layout
            central = QWidget()
            layout = QVBoxLayout(central)
            self.display = QTextEdit()
            self.display.setReadOnly(True)
            self.input_line = QLineEdit()
            self.submit_button = QPushButton("提交")
            layout.addWidget(self.display)
            layout.addWidget(self.input_line)
            layout.addWidget(self.submit_button)
            self.setCentralWidget(central)

            # 信号槽绑定
            self.input_line.returnPressed.connect(self._on_submit)
            self.submit_button.clicked.connect(self._on_submit)

            # 绑定 sink 的事件 handler —— sink.put_evt(evt) 触发 _handle_evt
            sink._evt_handler = self._handle_evt

            # 自动 show
            self.show()

        # ─── 用户输入路径 ───

        def _on_submit(self) -> None:
            """QLineEdit.returnPressed / QPushButton.clicked → input_sink.submit。"""
            text = self.input_line.text().strip()
            if not text:
                return  # 空文本不提交
            self._input_sink.submit(text)
            self.input_line.clear()

        # ─── 事件渲染路径 ───

        def _handle_evt(self, evt) -> None:
            """PyQt6Sink 收到 Event → 更新 UI（V2-01 验收）。"""
            if isinstance(evt, TextEvt):
                # 文本追加到 display
                self.display.append(evt.content)
            elif isinstance(evt, PromptInputEvt):
                # 允许用户输入
                self.input_line.setEnabled(True)
                self.input_line.setFocus() if hasattr(self.input_line, "setFocus") else None
            elif isinstance(evt, DecoratorEvt):
                # 触发装饰器钩子（@style / @bgm）—— v2 阶段钩子只记录，不渲染
                from core.decorators import dispatch as dispatch_decorator
                dispatch_decorator(evt)
            elif isinstance(evt, RouteEvt):
                # 跨章节 → 关闭窗口
                self.close()
            elif isinstance(evt, ChapterEndEvt):
                # 章节结束 → 关闭窗口
                self.close()
            elif isinstance(evt, LogEvt):
                # 日志：v2 阶段静默（v3+ 可显示在 debug panel）
                pass

        # ─── 生命周期 ───

        def close(self) -> bool:
            self._closed = True
            # 真 QMainWindow.close() 返回 bool（已关闭=成功）
            try:
                return super().close()
            except Exception:
                return True

        @property
        def is_closed(self) -> bool:
            return self._closed

        @property
        def input_sink(self) -> PyQt6InputSink:
            """测试 / 业务用：取 input_sink 实例。"""
            return self._input_sink

    # 给类一个清晰的名字（便于 repr / 调试）
    MainWindow.__name__ = "MainWindow"
    MainWindow.__qualname__ = "MainWindow"
    return MainWindow


# ─── 顶层 main / _run_with_sinks ───────────────────────────────────────────


def _run_with_sinks(bus, sink: PyQt6Sink, input_sink: PyQt6InputSink) -> int:
    """启动 PyQt6 GUI 事件循环。PyQt6 不可用时 raise RuntimeError。

    Args:
        bus: 双向 bus-like（get_evt / put_cmd / close）
        sink: PyQt6Sink（GUI 接收 Event 的入口）
        input_sink: PyQt6InputSink（GUI 推送 UserInputCmd 的出口）

    Returns:
        QApplication.exec() 返回码（0 = 正常退出）
    """
    # PyQt6 不可用 → raise（D3 决策要求 runtime.gui.main 降级 CLI）
    try:
        qt = _import_pyqt6()
    except ImportError as e:
        raise RuntimeError(
            f"PyQt6 未安装，无法启动 GUI: {e}（runtime.gui.main 应降级 CLI fallback）"
        ) from e

    QApplication = qt["QApplication"]
    MainWindowCls = _build_main_window_class(qt)

    # 1. QApplication 单例
    app = QApplication.instance() or QApplication(sys.argv)

    # 2. 主窗口（构造时自动 show + 绑定 sink._evt_handler）
    MainWindowCls(sink=sink, input_sink=input_sink)

    # 3. 进入 Qt 事件循环（阻塞直到窗口关闭）
    rc = app.exec()

    # 4. 清理（防 leak）
    sink.close()
    input_sink.close()
    bus.close()
    return rc


def main(bus=None) -> int:
    """GUI 主入口工厂（D3 决策）。PyQt6 不可用时 raise RuntimeError。

    Args:
        bus: 双向 bus-like（get_evt / put_cmd / close）。None 时自建 EngineBus。

    Returns:
        进程退出码（0 = 正常退出）。
    """
    if bus is None:
        from core.engine.bus import EngineBus
        bus = EngineBus(use_multiprocessing=True)

    # 构造默认 sink / input_sink（生产路径）
    sink = PyQt6Sink()
    input_sink = PyQt6InputSink()

    return _run_with_sinks(bus, sink, input_sink)


__all__ = ["_build_main_window_class", "_run_with_sinks", "main"]


if __name__ == "__main__":
    sys.exit(main())
