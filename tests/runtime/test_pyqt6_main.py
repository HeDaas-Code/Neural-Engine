"""v2-p0 · PyQt6 主窗口测试（V2-01 + EP-05）。

按 V2-01 issue 验收 + PDR §5.1.2 流程图：
- `pyqt6_main._build_main_window_class()` 动态构造 MainWindow Qt 子类
- `pyqt6_main._run_with_sinks(bus, sink, input_sink)` 启动 GUI 事件循环
- `pyqt6_main.main(bus)` 顶层入口

约束：
- PyQt6 **未装**（CI 真实状态）→ 测试用 monkeypatch + fake qt 模块
- `pyqt6_main` 模块**能 import**（顶层不 import PyQt6）
- mock QApplication.exec() 返回 0（不真启动事件循环）
"""
from __future__ import annotations

import os
import sys
import types
from unittest.mock import MagicMock

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")


# ─── Fake Qt Widgets ───────────────────────────────────────────────────────


class FakeSignal:
    """Fake Qt signal —— connect/emit。"""
    def __init__(self):
        self._slots: list = []

    def connect(self, slot):
        self._slots.append(slot)

    def emit(self, *args, **kwargs):
        for slot in self._slots:
            slot(*args, **kwargs)


class FakeQMainWindow:
    """Fake QMainWindow —— 测试用基类。"""
    def __init__(self, *args, **kwargs):
        self._window_title = ""
        self._central_widget = None
        self._shown = False
        self._closed = False

    def setWindowTitle(self, title):
        self._window_title = title

    def setCentralWidget(self, widget):
        self._central_widget = widget

    def show(self):
        self._shown = True

    def close(self):
        self._closed = True


class FakeQTextEdit:
    def __init__(self, *args, **kwargs):
        self._text = ""
        self._read_only = False

    def setReadOnly(self, ro):
        self._read_only = ro

    def append(self, text):
        self._text += text

    def clear(self):
        self._text = ""

    def toPlainText(self):
        return self._text


class FakeQLineEdit:
    def __init__(self, *args, **kwargs):
        self._text = ""
        self._enabled = True
        self.returnPressed = FakeSignal()

    def text(self):
        return self._text

    def setText(self, t):
        self._text = t

    def clear(self):
        self._text = ""

    def setEnabled(self, enabled):
        self._enabled = enabled

    def isEnabled(self):
        return self._enabled


class FakeQPushButton:
    def __init__(self, text="", *args, **kwargs):
        self._text = text
        self._enabled = True
        self.clicked = FakeSignal()

    def setEnabled(self, enabled):
        self._enabled = enabled

    def isEnabled(self):
        return self._enabled

    def text(self):
        return self._text


class FakeQWidget:
    def __init__(self, *args, **kwargs):
        pass


class FakeQVBoxLayout:
    def __init__(self, *args, **kwargs):
        self._widgets: list = []

    def addWidget(self, widget):
        self._widgets.append(widget)

    def count(self):
        return len(self._widgets)

    def itemAt(self, i):
        return MagicMock(widget=lambda: self._widgets[i]) if i < len(self._widgets) else None


class FakeQApplication:
    _instance = None

    def __init__(self, argv):
        self._argv = argv
        self._exec_return = 0
        FakeQApplication._instance = self

    def exec(self):
        return self._exec_return

    @classmethod
    def instance(cls):
        return cls._instance


# ─── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def fake_pyqt6(monkeypatch):
    """注入 fake PyQt6 modules 到 sys.modules + 替换 _build_main_window_class。"""
    qtcore = types.ModuleType("PyQt6.QtCore")
    qtcore.Qt = MagicMock(name="Qt")
    qtcore.QThread = MagicMock(name="QThread")
    qtcore.QObject = MagicMock(name="QObject")
    qtcore.pyqtSignal = MagicMock(name="pyqtSignal", return_value=FakeSignal())

    qtwidgets = types.ModuleType("PyQt6.QtWidgets")
    qtwidgets.QApplication = FakeQApplication
    qtwidgets.QMainWindow = FakeQMainWindow
    qtwidgets.QTextEdit = FakeQTextEdit
    qtwidgets.QLineEdit = FakeQLineEdit
    qtwidgets.QPushButton = FakeQPushButton
    qtwidgets.QWidget = FakeQWidget
    qtwidgets.QVBoxLayout = FakeQVBoxLayout

    pyqt6_pkg = types.ModuleType("PyQt6")
    pyqt6_pkg.QtCore = qtcore
    pyqt6_pkg.QtWidgets = qtwidgets
    monkeypatch.setitem(sys.modules, "PyQt6", pyqt6_pkg)
    monkeypatch.setitem(sys.modules, "PyQt6.QtCore", qtcore)
    monkeypatch.setitem(sys.modules, "PyQt6.QtWidgets", qtwidgets)
    return {"QtCore": qtcore, "QtWidgets": qtwidgets}


# ─── 1. 模块 import 行为 ───────────────────────────────────────────────────


def test_pyqt6_main_module_imports_without_pyqt6():
    """pyqt6_main 模块顶层不 import PyQt6——即使 PyQt6 未装也能 import。"""
    # 删除 PyQt6 sys.modules 缓存
    for k in ("PyQt6", "PyQt6.QtCore", "PyQt6.QtWidgets"):
        sys.modules.pop(k, None)
    sys.modules.pop("runtime.gui.pyqt6_main", None)
    try:
        import runtime.gui.pyqt6_main as mod
        assert mod is not None
        assert hasattr(mod, "main")
        assert hasattr(mod, "_run_with_sinks")
        assert hasattr(mod, "_build_main_window_class")
    finally:
        # 恢复（不影响后续测试）
        pass


def test_run_with_sinks_raises_when_pyqt6_not_installed(monkeypatch):
    """_run_with_sinks 在 PyQt6 不可用时 raise RuntimeError（D3 决策要求 fallback CLI）。"""
    # 强制 PyQt6 不可用
    monkeypatch.delitem(sys.modules, "PyQt6", raising=False)
    monkeypatch.delitem(sys.modules, "PyQt6.QtCore", raising=False)
    monkeypatch.delitem(sys.modules, "PyQt6.QtWidgets", raising=False)

    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from runtime.gui import pyqt6_main

    class FakeBus:
        def get_evt(self): return None
        def put_cmd(self, cmd): pass
        def close(self): pass

    sink = PyQt6Sink()
    input_sink = PyQt6InputSink()

    with pytest.raises(RuntimeError, match="PyQt6"):
        pyqt6_main._run_with_sinks(FakeBus(), sink, input_sink)


# ─── 2. MainWindow 构造与 UI 元素 ──────────────────────────────────────────


def test_main_window_constructs_with_three_widgets(fake_pyqt6):
    """MainWindow 含三个核心 widget：display (QTextEdit) + input (QLineEdit) + submit (QPushButton)。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink

    MainWindowCls = pyqt6_main._build_main_window_class()
    sink = PyQt6Sink()
    input_sink = PyQt6InputSink()
    win = MainWindowCls(sink=sink, input_sink=input_sink)

    assert win is not None
    assert hasattr(win, "display")
    assert hasattr(win, "input_line")
    assert hasattr(win, "submit_button")


def test_main_window_title_is_neural_engine(fake_pyqt6):
    """MainWindow 标题为 'Neural Engine'（V2-01 验收）。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink

    MainWindowCls = pyqt6_main._build_main_window_class()
    win = MainWindowCls(sink=PyQt6Sink(), input_sink=PyQt6InputSink())

    assert win._window_title == "Neural Engine"


def test_main_window_show_called_on_construct(fake_pyqt6):
    """MainWindow 构造时自动 show（V2-01 验收：启动时显示窗口）。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink

    MainWindowCls = pyqt6_main._build_main_window_class()
    win = MainWindowCls(sink=PyQt6Sink(), input_sink=PyQt6InputSink())

    assert win._shown is True


# ─── 3. 用户输入路径：QLineEdit + QPushButton → PyQt6InputSink ─────────────


def test_input_line_return_pressed_submits_user_input_cmd(fake_pyqt6):
    """QLineEdit.returnPressed 信号 → PyQt6InputSink.submit(value)。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from core.engine.protocol import UserInputCmd

    MainWindowCls = pyqt6_main._build_main_window_class()
    sink = PyQt6Sink()
    input_sink = PyQt6InputSink()
    win = MainWindowCls(sink=sink, input_sink=input_sink)

    win.input_line.setText("平静")
    win.input_line.returnPressed.emit()

    cmd = input_sink.drain_cmd()
    assert isinstance(cmd, UserInputCmd)
    assert cmd.value == "平静"
    # 输入框被清空（UX 约定）
    assert win.input_line.text() == ""


def test_input_line_empty_text_does_not_submit(fake_pyqt6):
    """输入框空文本 + 回车 → 不提交（避免空命令）。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink

    MainWindowCls = pyqt6_main._build_main_window_class()
    win = MainWindowCls(sink=PyQt6Sink(), input_sink=PyQt6InputSink())

    win.input_line.returnPressed.emit()
    assert win.input_sink.drain_cmd() is None  # input_sink 属性或 _input_sink


def test_submit_button_clicked_submits_user_input_cmd(fake_pyqt6):
    """QPushButton.clicked 信号 → PyQt6InputSink.submit(value)。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from core.engine.protocol import UserInputCmd

    MainWindowCls = pyqt6_main._build_main_window_class()
    sink = PyQt6Sink()
    input_sink = PyQt6InputSink()
    win = MainWindowCls(sink=sink, input_sink=input_sink)

    win.input_line.setText("1")
    win.submit_button.clicked.emit()

    cmd = input_sink.drain_cmd()
    assert isinstance(cmd, UserInputCmd)
    assert cmd.value == "1"


# ─── 4. 事件路径：PyQt6Sink → MainWindow UI 更新 ──────────────────────────


def test_sink_handler_updates_display_with_text_evt(fake_pyqt6):
    """PyQt6Sink.put_evt(TextEvt) → display.append(content)。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from core.engine.protocol import TextEvt

    MainWindowCls = pyqt6_main._build_main_window_class()
    sink = PyQt6Sink()
    win = MainWindowCls(sink=sink, input_sink=PyQt6InputSink())

    sink.put_evt(TextEvt(content="雨夜。\n", style="narration"))

    assert "雨夜。" in win.display.toPlainText()


def test_sink_handler_prompt_input_enables_input_line(fake_pyqt6):
    """PyQt6Sink.put_evt(PromptInputEvt) → input_line.setEnabled(True)。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from core.engine.protocol import PromptInputEvt

    MainWindowCls = pyqt6_main._build_main_window_class()
    sink = PyQt6Sink()
    win = MainWindowCls(sink=sink, input_sink=PyQt6InputSink())

    sink.put_evt(PromptInputEvt(var="p_mood"))

    assert win.input_line.isEnabled() is True


def test_sink_handler_route_evt_closes_window(fake_pyqt6):
    """PyQt6Sink.put_evt(RouteEvt) → window.close()。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from core.engine.protocol import RouteEvt

    MainWindowCls = pyqt6_main._build_main_window_class()
    sink = PyQt6Sink()
    win = MainWindowCls(sink=sink, input_sink=PyQt6InputSink())

    sink.put_evt(RouteEvt(target="chapter02"))

    assert win._closed is True


def test_sink_handler_chapter_end_closes_window(fake_pyqt6):
    """PyQt6Sink.put_evt(ChapterEndEvt) → window.close()。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from core.engine.protocol import ChapterEndEvt

    MainWindowCls = pyqt6_main._build_main_window_class()
    sink = PyQt6Sink()
    win = MainWindowCls(sink=sink, input_sink=PyQt6InputSink())

    sink.put_evt(ChapterEndEvt())

    assert win._closed is True


def test_sink_handler_decorator_evt_dispatches_to_decorator_hooks(fake_pyqt6):
    """PyQt6Sink.put_evt(DecoratorEvt) → 通过 core.decorators.dispatch() 触发钩子。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from core.engine.protocol import DecoratorEvt
    from core.decorators import style as style_mod
    from core.decorators import bgm as bgm_mod

    MainWindowCls = pyqt6_main._build_main_window_class()
    sink = PyQt6Sink()
    MainWindowCls(sink=sink, input_sink=PyQt6InputSink())

    # 安装钩子（fixture 已经在 core/test_decorator_hooks.py 测；这里再装一次因为隔离）
    style_mod.install()
    bgm_mod.install()

    sink.put_evt(DecoratorEvt(name="style", args=["color:red"]))
    sink.put_evt(DecoratorEvt(name="bgm", args=["rain.mp3"]))

    assert style_mod.get_last_style() == {"color": "red"}
    assert bgm_mod.get_last_bgm() == [("play", "rain.mp3")]


# ─── 5. 生命周期：_run_with_sinks 启停 ────────────────────────────────────


def test_run_with_sinks_starts_and_returns_zero(fake_pyqt6):
    """_run_with_sinks 启动事件循环（mock exec() 返回 0）+ 清理 sink → 返回 0。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink

    class FakeBus:
        def __init__(self):
            self.put_cmd_calls: list = []
            self._evt_idx = 0
            self._evts = [None]  # 立即 None 退出

        def get_evt(self):
            e = self._evts[self._evt_idx]
            self._evt_idx += 1
            return e

        def put_cmd(self, cmd):
            self.put_cmd_calls.append(cmd)

        def close(self):
            pass

    bus = FakeBus()
    sink = PyQt6Sink()
    input_sink = PyQt6InputSink()

    rc = pyqt6_main._run_with_sinks(bus, sink, input_sink)
    assert rc == 0
    # sink 和 input_sink 应被 close（清理）
    assert sink.is_closed is True
    assert input_sink.is_closed is True


def test_run_with_sinks_silences_sink_before_close(fake_pyqt6):
    """_run_with_sinks 关闭后 PyQt6Sink 不再接收 Event（防 leak）。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from core.engine.protocol import TextEvt

    class FakeBus:
        def get_evt(self): return None
        def put_cmd(self, cmd): pass
        def close(self): pass

    received: list = []
    sink = PyQt6Sink(evt_handler=lambda e: received.append(e))
    pyqt6_main._run_with_sinks(FakeBus(), sink, PyQt6InputSink())

    # sink 已关闭 → 后续 put_evt 静默
    sink.put_evt(TextEvt(content="after", style="narration"))
    assert received == []
