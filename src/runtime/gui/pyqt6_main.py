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

import os
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
    QWidget / QVBoxLayout / QLabel / QPixmap / QObject / Qt / QThread / pyqtSignal。
    """
    from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
    from PyQt6.QtGui import QPixmap
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QTextEdit, QLineEdit,
        QPushButton, QWidget, QVBoxLayout, QLabel,
    )
    return {
        "QApplication": QApplication,
        "QMainWindow": QMainWindow,
        "QTextEdit": QTextEdit,
        "QLineEdit": QLineEdit,
        "QPushButton": QPushButton,
        "QWidget": QWidget,
        "QVBoxLayout": QVBoxLayout,
        "QLabel": QLabel,
        "QPixmap": QPixmap,
        "QObject": QObject,
        "Qt": Qt,
        "QThread": QThread,
        "pyqtSignal": pyqtSignal,
    }


# ─── MainWindow 类工厂 ──────────────────────────────────────────────────────


def _build_main_window_class(
    qt: Optional[dict] = None,
    char_delay_ms: int = 40,
    audio_manager: Optional[object] = None,
    image_renderer: Optional[object] = None,
    backlog: Optional[object] = None,
    read_marks: Optional[object] = None,
    auto_mode_controller: Optional[object] = None,
    settings_manager: Optional[object] = None,
    chapters_root: str = "chapters",
):
    """动态构造 MainWindow Qt 子类（继承 qt["QMainWindow"]）。

    关键：MainWindow 类**继承真 Qt 的 QMainWindow**，所以测试用 fake qt 时也能
    通过 isinstance 检查；构造时调 super().__init__() 进入真 QMainWindow 初始化路径。

    Args:
        qt: PyQt6 modules dict（测试可注入 fake）。None 时 lazy import。
        char_delay_ms: v3-01 打字机每字延迟（ms），<=0 关闭打字机效果。
        audio_manager: v3-03 AudioManager 实例（测试可注入 fake）。
            None 时 lazy 创建真 AudioManager（PyQt6.QtMultimedia 未装则降级 no-op）。
        image_renderer: v3-04 ImageRenderer 实例（测试可注入 fake）。
            None 时 lazy 创建真 ImageRenderer（PyQt6 未装则降级 no-op）。
        backlog: v3-06 BackLog 实例（测试可注入 fake）。
            None 时 lazy 创建真 BackLog（纯 Python，无 PyQt6 依赖）。
        read_marks: v3-07 ReadMarks 实例（测试可注入 fake）。
            None 时 lazy 创建真 ReadMarks（纯 Python，内存模式无持久化）。
        auto_mode_controller: v3-07 AutoModeController 实例（测试可注入 fake）。
            None 时 lazy 创建（注入 on_advance=提交空串触发推进 + qt dict）。
        settings_manager: v3-08 SettingsManager 实例（测试可注入 fake）。
            None 时 lazy 创建（默认 ~/.neural-engine/settings.json，无文件用默认值）。
            构造后会应用到 text_renderer / auto_mode / audio_manager。
        chapters_root: v3-03/v3-04 音频/图片文件解析根目录。

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
        """PyQt6 主窗口（V2-01 验收 + v3-01 对话框 + v3-03 音频）。"""

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

            # v3-01: TextRenderer（打字机 + 名字标签 + @style 应用）
            from runtime.gui.text_renderer import TextRenderer
            self._text_renderer = TextRenderer(
                self.display, char_delay_ms=char_delay_ms, qt=qt,
            )

            # v3-02: OptionsPanel（选项按钮列表，PromptInputEvt.options 非空时显示）
            from runtime.gui.options_panel import OptionsPanel
            self._options_panel = OptionsPanel(central, layout, input_sink, qt=qt)
            # 初始：QLineEdit + submit_button 可用（无 options 时降级路径）
            # options 来时会隐藏 input_line，改显 OptionsPanel

            # v3-03: AudioManager（BGM/SE/Voice 三轨，@bgm 转发到此）
            # 注入或 lazy 创建；注册到 bgm 装饰器让 @bgm call/stop 转发
            from runtime.audio import AudioManager
            from core.decorators import bgm as bgm_mod
            if audio_manager is not None:
                self._audio_manager = audio_manager
            else:
                self._audio_manager = AudioManager(chapters_root=chapters_root)
            self._audio_manager_owned = audio_manager is None
            # 注册到 @bgm 钩子（让 DecoratorEvt @bgm → mgr.play/stop）
            bgm_mod.set_audio_manager(self._audio_manager)

            # v3-04: ImageRenderer（背景图 + 角色立绘，@bg/@char 转发到此）
            # 注入或 lazy 创建；注册到 bg/char 装饰器
            from runtime.gui.image_renderer import ImageRenderer
            from core.decorators import bg as bg_mod
            from core.decorators import char as char_mod
            if image_renderer is not None:
                self._image_renderer = image_renderer
            else:
                self._image_renderer = ImageRenderer(
                    central, layout, qt=qt, chapters_root=chapters_root,
                )
            bg_mod.set_image_manager(self._image_renderer)
            char_mod.set_image_manager(self._image_renderer)

            # v3-06: BackLog（历史文本累积，TextEvt → backlog.add）
            # 注入或 lazy 创建（纯 Python，无 PyQt6 依赖）
            from runtime.gui.backlog import BackLog
            if backlog is not None:
                self._backlog = backlog
            else:
                self._backlog = BackLog()

            # v3-07: ReadMarks（已读标记，TextEvt → mark）
            # 注入或 lazy 创建（纯 Python，内存模式无持久化）
            from runtime.gui.read_marks import ReadMarks
            if read_marks is not None:
                self._read_marks = read_marks
            else:
                self._read_marks = ReadMarks()

            # v3-07: AutoModeController（Auto 模式 + Skip 快进）
            # 注入或 lazy 创建（注入 on_advance=提交空串触发推进 + qt dict）
            from runtime.gui.auto_mode import AutoModeController
            if auto_mode_controller is not None:
                self._auto_mode = auto_mode_controller
            else:
                self._auto_mode = AutoModeController(
                    on_advance=self._auto_advance,
                    qt=qt,
                )

            # v3-08: SettingsManager（全局配置持久化）
            # 注入或 lazy 创建（默认 ~/.neural-engine/settings.json）
            from runtime.settings import SettingsManager
            if settings_manager is not None:
                self._settings = settings_manager
            else:
                self._settings = SettingsManager()
            # 应用配置到运行时组件（char_delay_ms / auto_delay / 音量）
            try:
                self._settings.apply_to_text_renderer(self._text_renderer)
                self._settings.apply_to_auto_mode(self._auto_mode)
                self._settings.apply_to_audio_manager(self._audio_manager)
            except Exception:
                pass

            # 信号槽绑定
            self.input_line.returnPressed.connect(self._on_submit)
            self.submit_button.clicked.connect(self._on_submit)
            # v3-01: display 点击跳过打字机动画
            self.display.mousePressEvent = self._on_display_click

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
            # v3-07: 用户手动操作 → 取消 Auto 待推进
            try:
                self._auto_mode.cancel()
            except Exception:
                pass
            self._input_sink.submit(text)
            self.input_line.clear()

        def _on_display_click(self, event) -> None:
            """v3-01: 点击 display 区域 → 跳过打字机动画。"""
            if self._text_renderer.is_typing:
                self._text_renderer.skip()

        def _auto_advance(self) -> None:
            """v3-07: Auto 模式推进回调 —— 提交空串触发"下一步"。

            引擎收到空 UserInputCmd 时通常表示"继续"（取决于 In 节点处理）。
            注意：OptionsPanel 显示中不自动推进（需用户选）。
            """
            try:
                # 若 OptionsPanel 当前有按钮 → 不自动推进（避免误选）
                if self._options_panel.button_count > 0:
                    return
                self._input_sink.submit("")
            except Exception:
                pass

        # ─── 事件渲染路径 ───

        def _handle_evt(self, evt) -> None:
            """PyQt6Sink 收到 Event → 更新 UI。"""
            if isinstance(evt, TextEvt):
                # v3-02: 新文本开始 → 清空上一轮 options 按钮
                self._options_panel.clear()
                # v3-06: 累积到历史 BackLog（在渲染前记录原始 evt）
                try:
                    self._backlog.add(evt)
                except Exception:
                    pass
                # v3-07: Skip 模式 → 跳过打字机（render 后立即 skip）
                # （render 会启动打字机；若 skip_mode 则立刻显示全文）
                self._text_renderer.render(evt)
                if self._auto_mode.skip_mode and self._text_renderer.is_typing:
                    self._text_renderer.skip()
                # v3-07: 标记已读
                try:
                    self._read_marks.mark_evt(evt)
                except Exception:
                    pass
                # v3-07: Auto 模式 → 文本渲染完成通知（内部判断是否调度推进）
                try:
                    self._auto_mode.notify_text_complete()
                except Exception:
                    pass
            elif isinstance(evt, PromptInputEvt):
                # v3-01: 打字机进行中禁用输入（动画结束才能交互）
                if self._text_renderer.is_typing:
                    self._text_renderer.skip()
                # v3-02: 有 options → 显示 OptionsPanel，隐藏 QLineEdit
                if evt.options:
                    self.input_line.setEnabled(False)
                    self.input_line.setVisible(False)
                    try:
                        self.submit_button.setVisible(False)
                    except Exception:
                        pass
                    self._options_panel.set_options(evt.options)
                else:
                    # 无 options → 降级 QLineEdit 自由输入（向后兼容）
                    self.input_line.setEnabled(True)
                    self.input_line.setVisible(True)
                    try:
                        self.submit_button.setVisible(True)
                    except Exception:
                        pass
                    self.input_line.setFocus() if hasattr(self.input_line, "setFocus") else None
            elif isinstance(evt, DecoratorEvt):
                # 触发装饰器钩子（@style / @bgm）
                from core.decorators import dispatch as dispatch_decorator
                dispatch_decorator(evt)
                # v3-01: @style 装饰器 → 应用到 TextRenderer
                if evt.name == "style" and evt.kind == "call":
                    from core.decorators.style import get_last_style
                    self._text_renderer.apply_style(get_last_style())
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
            # v3-03: 关窗时停止所有音频 + 清除 bgm 装饰器注册（防 leak / 测试隔离）
            try:
                self._audio_manager.stop()
            except Exception:
                pass
            try:
                from core.decorators import bgm as bgm_mod
                bgm_mod.set_audio_manager(None)
            except Exception:
                pass
            # v3-04: 清空图片 + 清除 bg/char 装饰器注册
            try:
                self._image_renderer.clear()
            except Exception:
                pass
            try:
                from core.decorators import bg as bg_mod
                from core.decorators import char as char_mod
                bg_mod.set_image_manager(None)
                char_mod.set_image_manager(None)
            except Exception:
                pass
            # v3-07: 关窗时取消 Auto 待推进 + 重置状态（防 leak / 测试隔离）
            try:
                self._auto_mode.reset()
            except Exception:
                pass
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

        @property
        def audio_manager(self) -> object:
            """v3-03: 取 AudioManager 实例（测试断言用）。"""
            return self._audio_manager

        @property
        def image_renderer(self) -> object:
            """v3-04: 取 ImageRenderer 实例（测试断言用）。"""
            return self._image_renderer

        @property
        def backlog(self) -> object:
            """v3-06: 取 BackLog 实例（测试断言用）。"""
            return self._backlog

        @property
        def read_marks(self) -> object:
            """v3-07: 取 ReadMarks 实例（测试断言用）。"""
            return self._read_marks

        @property
        def auto_mode(self) -> object:
            """v3-07: 取 AutoModeController 实例（测试断言用）。"""
            return self._auto_mode

        @property
        def settings(self) -> object:
            """v3-08: 取 SettingsManager 实例（测试断言用）。"""
            return self._settings

        def show_history(self, qt_override: Optional[dict] = None):
            """v3-06: 构造并返回 HistoryDialog（含当前 backlog 条目）。

            不直接 exec() —— 调用方决定何时显示（测试可拦截返回值）。

            Args:
                qt_override: PyQt6 modules dict（测试注入 fake，需含
                    QDialog/QVBoxLayout/QHBoxLayout/QLabel/QPushButton/QWidget/QScrollArea）。
                    None 时 HistoryDialog 工厂自行 lazy import 真 PyQt6。

            Returns:
                HistoryDialog 实例（已 set_entries，未 exec）。

            Raises:
                RuntimeError: PyQt6 不可用（HistoryDialog 工厂抛）。
            """
            from runtime.gui.history_dialog import _build_history_dialog_class
            # qt_override=None 时让 HistoryDialog 工厂自行 lazy import
            # （MainWindow 的 qt dict 不含 QDialog/QScrollArea 等 dialog 专用类）
            DialogCls = _build_history_dialog_class(qt=qt_override)
            dialog = DialogCls(parent=self)
            dialog.refresh_from(self._backlog)
            return dialog

        def show_settings(self, qt_override: Optional[dict] = None):
            """v3-08: 构造并返回 SettingsDialog（含当前 settings 值）。

            不直接 exec() —— 调用方决定何时显示（测试可拦截返回值）。
            用户确认后调用方应：
                if dialog.was_accepted:
                    new = dialog.get_settings()
                    self._settings.set_many(new)
                    self._settings.save()
                    # 重新应用到运行时组件
                    self._settings.apply_to_text_renderer(self._text_renderer)
                    self._settings.apply_to_auto_mode(self._auto_mode)
                    self._settings.apply_to_audio_manager(self._audio_manager)

            Args:
                qt_override: PyQt6 modules dict（测试注入 fake，需含
                    QDialog/QVBoxLayout/QHBoxLayout/QFormLayout/QLabel/QPushButton/
                    QWidget/QSpinBox/QDoubleSpinBox/QCheckBox）。
                    None 时 SettingsDialog 工厂自行 lazy import 真 PyQt6。

            Returns:
                SettingsDialog 实例（已 set_settings，未 exec）。

            Raises:
                RuntimeError: PyQt6 不可用（SettingsDialog 工厂抛）。
            """
            from runtime.gui.settings_dialog import _build_settings_dialog_class
            DialogCls = _build_settings_dialog_class(qt=qt_override)
            dialog = DialogCls(settings_manager=self._settings, parent=self)
            return dialog

        def apply_settings(self) -> None:
            """v3-08: 重新应用 settings 到运行时组件（settings 改动后调）。

            调 self._settings.apply_to_* 把 text_speed / auto_delay / 音量等
            推送到 TextRenderer / AutoMode / AudioManager。
            """
            try:
                self._settings.apply_to_text_renderer(self._text_renderer)
                self._settings.apply_to_auto_mode(self._auto_mode)
                self._settings.apply_to_audio_manager(self._audio_manager)
            except Exception:
                pass

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
    # 无显示后端（headless CI / SSH 无 DISPLAY）→ 自动切 offscreen 平台插件
    # （Qt 行业默认：QPA_PLATFORM 不在 + DISPLAY 不在 → offscreen，避免 abort）
    if (
        not sys.platform.startswith("win")
        and "QT_QPA_PLATFORM" not in os.environ
        and not os.environ.get("DISPLAY")
        and QApplication.instance() is None
    ):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
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
