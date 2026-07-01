"""v3-06 · BackLog 历史累积 + HistoryDialog 测试（#96）。

验证 issue #96 验收点：
- BackLog.add(TextEvt) → 累积历史条目
- BackLog.get_entries() → list[dict]（含 text/speaker/style/ts）
- BackLog 容量上限 + FIFO 丢弃
- BackLog.clear() / latest() / count
- HistoryDialog 网格显示历史条目
- HistoryDialog.set_entries / refresh_from
- MainWindow 集成：TextEvt → backlog.add + show_history()
"""
from __future__ import annotations

import os
import sys
import time
import types
from unittest.mock import MagicMock

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")


# ═══════════════════════════════════════════════════════════════════════
# 1. BackLog 基础测试
# ═══════════════════════════════════════════════════════════════════════


def test_backlog_constructs_empty():
    """BackLog 默认构造 → 空。"""
    from runtime.gui.backlog import BackLog
    bl = BackLog()
    assert bl.is_empty is True
    assert bl.count == 0
    assert len(bl) == 0
    assert bl.get_entries() == []


def test_backlog_add_text_evt():
    """add(TextEvt) → 累积 1 条。"""
    from runtime.gui.backlog import BackLog
    from core.engine.protocol import TextEvt

    bl = BackLog()
    bl.add(TextEvt(content="雨夜。", style="narration"))
    assert bl.count == 1
    entries = bl.get_entries()
    assert entries[0]["text"] == "雨夜。"
    assert entries[0]["style"] == "narration"
    assert "ts" in entries[0]


def test_backlog_add_text_evt_with_speaker():
    """add(TextEvt with speaker) → speaker 字段被记录。"""
    from runtime.gui.backlog import BackLog
    from core.engine.protocol import TextEvt

    bl = BackLog()
    bl.add(TextEvt(content="你好。", speaker="alice", style="dialog"))
    entries = bl.get_entries()
    assert entries[0]["speaker"] == "alice"
    assert entries[0]["style"] == "dialog"


def test_backlog_add_text_direct():
    """add_text(text, speaker, style) → 直接追加。"""
    from runtime.gui.backlog import BackLog
    bl = BackLog()
    bl.add_text("直接文本。", speaker="bob", style="dialog")
    entries = bl.get_entries()
    assert entries[0]["text"] == "直接文本。"
    assert entries[0]["speaker"] == "bob"


def test_backlog_add_none_silent():
    """add(None) → 静默（不抛错）。"""
    from runtime.gui.backlog import BackLog
    bl = BackLog()
    bl.add(None)
    assert bl.count == 0


def test_backlog_multiple_entries():
    """累积多条。"""
    from runtime.gui.backlog import BackLog
    from core.engine.protocol import TextEvt

    bl = BackLog()
    for i in range(5):
        bl.add(TextEvt(content=f"第{i}行。"))
    assert bl.count == 5
    entries = bl.get_entries()
    assert entries[0]["text"] == "第0行。"
    assert entries[4]["text"] == "第4行。"


def test_backlog_get_entries_returns_copy():
    """get_entries() 返回副本（外部修改不影响内部）。"""
    from runtime.gui.backlog import BackLog
    from core.engine.protocol import TextEvt

    bl = BackLog()
    bl.add(TextEvt(content="原始。"))
    entries = bl.get_entries()
    entries[0]["text"] = "篡改。"
    # 内部不变
    assert bl.get_entries()[0]["text"] == "原始。"


def test_backlog_clear():
    """clear() → 清空。"""
    from runtime.gui.backlog import BackLog
    from core.engine.protocol import TextEvt

    bl = BackLog()
    bl.add(TextEvt(content="x"))
    bl.clear()
    assert bl.is_empty is True
    assert bl.count == 0


def test_backlog_latest():
    """latest(n) → 最近 n 条。"""
    from runtime.gui.backlog import BackLog
    from core.engine.protocol import TextEvt

    bl = BackLog()
    for i in range(10):
        bl.add(TextEvt(content=f"行{i}"))
    latest = bl.latest(3)
    assert len(latest) == 3
    assert latest[0]["text"] == "行7"
    assert latest[2]["text"] == "行9"


def test_backlog_latest_zero_returns_empty():
    """latest(0) → []。"""
    from runtime.gui.backlog import BackLog
    bl = BackLog()
    bl.add_text("x")
    assert bl.latest(0) == []


def test_backlog_latest_more_than_count():
    """latest(n) n > count → 返回全部。"""
    from runtime.gui.backlog import BackLog
    bl = BackLog()
    bl.add_text("a")
    bl.add_text("b")
    latest = bl.latest(10)
    assert len(latest) == 2


def test_backlog_max_entries_fifo():
    """max_entries=3 → 超出时丢弃最旧（FIFO）。"""
    from runtime.gui.backlog import BackLog
    from core.engine.protocol import TextEvt

    bl = BackLog(max_entries=3)
    bl.add(TextEvt(content="第一"))
    bl.add(TextEvt(content="第二"))
    bl.add(TextEvt(content="第三"))
    bl.add(TextEvt(content="第四"))  # 触发丢弃

    assert bl.count == 3
    entries = bl.get_entries()
    assert entries[0]["text"] == "第二"  # 第一被丢弃
    assert entries[2]["text"] == "第四"


def test_backlog_max_entries_zero_means_unlimited():
    """max_entries=0 → 无限。"""
    from runtime.gui.backlog import BackLog
    bl = BackLog(max_entries=0)
    for i in range(300):
        bl.add_text(f"x{i}")
    assert bl.count == 300


def test_backlog_max_entries_negative_means_unlimited():
    """max_entries<0 → 无限。"""
    from runtime.gui.backlog import BackLog
    bl = BackLog(max_entries=-1)
    for i in range(300):
        bl.add_text(f"y{i}")
    assert bl.count == 300


def test_backlog_default_max_entries_200():
    """默认 max_entries=200。"""
    from runtime.gui.backlog import BackLog
    bl = BackLog()
    assert bl.max_entries == 200


def test_backlog_ts_is_float():
    """ts 字段是 float（Unix timestamp）。"""
    from runtime.gui.backlog import BackLog
    from core.engine.protocol import TextEvt

    bl = BackLog()
    before = time.time()
    bl.add(TextEvt(content="x"))
    after = time.time()
    ts = bl.get_entries()[0]["ts"]
    assert isinstance(ts, float)
    assert before <= ts <= after


# ═══════════════════════════════════════════════════════════════════════
# 2. HistoryDialog（fake PyQt6 fixture）
# ═══════════════════════════════════════════════════════════════════════


class _FakeSignal:
    def __init__(self):
        self._slots: list = []

    def connect(self, slot):
        self._slots.append(slot)

    def emit(self, *a, **kw):
        for s in self._slots:
            s(*a, **kw)


class _FakeQDialog:
    def __init__(self, *a, **kw):
        self._title = ""
        self._accepted = False
        self._rejected = False

    def setWindowTitle(self, t): self._title = t
    def accept(self): self._accepted = True
    def reject(self): self._rejected = True


class _FakeQLabel:
    def __init__(self, text=""):
        self._text = text
        self._parent = None

    def setText(self, t): self._text = t
    def setParent(self, p): self._parent = p
    def deleteLater(self): pass


class _FakeQPushButton:
    def __init__(self, text=""):
        self._text = text
        self.clicked = _FakeSignal()


class _FakeQWidget:
    def __init__(self, *a, **kw):
        self._parent = None

    def setParent(self, p): self._parent = p
    def deleteLater(self): pass


class _FakeQVBoxLayout:
    def __init__(self, *a, **kw):
        self._widgets: list = []

    def addWidget(self, w): self._widgets.append(w)
    def addLayout(self, l): pass
    def addStretch(self, n): pass

    def count(self):
        return len(self._widgets)

    def takeAt(self, i):
        if i >= len(self._widgets):
            return None
        w = self._widgets.pop(i)

        class _Item:
            def widget(self_inner):
                return w
        return _Item()


class _FakeQHBoxLayout:
    def __init__(self, *a, **kw):
        self._widgets: list = []

    def addWidget(self, w): self._widgets.append(w)
    def addStretch(self, n=0): pass


class _FakeQScrollArea:
    def __init__(self, *a, **kw):
        self._widget = None
        self._resizable = False

    def setWidgetResizable(self, b): self._resizable = b
    def setWidget(self, w): self._widget = w


@pytest.fixture
def fake_pyqt6_history(monkeypatch):
    """注入 fake PyQt6 modules for HistoryDialog。"""
    qtcore = types.ModuleType("PyQt6.QtCore")
    qtcore.Qt = MagicMock()
    qtcore.pyqtSignal = MagicMock(return_value=_FakeSignal())

    qtwidgets = types.ModuleType("PyQt6.QtWidgets")
    qtwidgets.QDialog = _FakeQDialog
    qtwidgets.QVBoxLayout = _FakeQVBoxLayout
    qtwidgets.QHBoxLayout = _FakeQHBoxLayout
    qtwidgets.QLabel = _FakeQLabel
    qtwidgets.QPushButton = _FakeQPushButton
    qtwidgets.QWidget = _FakeQWidget
    qtwidgets.QScrollArea = _FakeQScrollArea

    pyqt6_pkg = types.ModuleType("PyQt6")
    pyqt6_pkg.QtCore = qtcore
    pyqt6_pkg.QtWidgets = qtwidgets
    monkeypatch.setitem(sys.modules, "PyQt6", pyqt6_pkg)
    monkeypatch.setitem(sys.modules, "PyQt6.QtCore", qtcore)
    monkeypatch.setitem(sys.modules, "PyQt6.QtWidgets", qtwidgets)
    return {
        "QDialog": _FakeQDialog, "QVBoxLayout": _FakeQVBoxLayout,
        "QHBoxLayout": _FakeQHBoxLayout, "QLabel": _FakeQLabel,
        "QPushButton": _FakeQPushButton, "QWidget": _FakeQWidget,
        "QScrollArea": _FakeQScrollArea, "Qt": qtcore.Qt,
        "pyqtSignal": qtcore.pyqtSignal,
    }


def test_history_dialog_constructs(fake_pyqt6_history):
    """HistoryDialog 构造 → 含关闭按钮。"""
    from runtime.gui.history_dialog import _build_history_dialog_class
    DialogCls = _build_history_dialog_class(qt=fake_pyqt6_history)
    dialog = DialogCls()
    assert dialog is not None
    assert dialog._title == "历史回看"
    assert hasattr(dialog, "_close_btn")
    assert hasattr(dialog, "_content_layout")


def test_history_dialog_set_entries_rebuilds_list(fake_pyqt6_history):
    """set_entries(entries) → 重建 label 列表。"""
    from runtime.gui.history_dialog import _build_history_dialog_class
    DialogCls = _build_history_dialog_class(qt=fake_pyqt6_history)
    dialog = DialogCls()

    entries = [
        {"text": "雨夜。", "speaker": None, "style": "narration", "ts": time.time()},
        {"text": "你好。", "speaker": "alice", "style": "dialog", "ts": time.time()},
    ]
    dialog.set_entries(entries)

    assert dialog.entry_count == 2
    assert len(dialog._entry_labels) == 2


def test_history_dialog_set_empty_entries(fake_pyqt6_history):
    """set_entries([]) → 空列表。"""
    from runtime.gui.history_dialog import _build_history_dialog_class
    DialogCls = _build_history_dialog_class(qt=fake_pyqt6_history)
    dialog = DialogCls()
    dialog.set_entries([])
    assert dialog.entry_count == 0
    assert len(dialog._entry_labels) == 0


def test_history_dialog_set_none_entries(fake_pyqt6_history):
    """set_entries(None) → 空列表（不抛错）。"""
    from runtime.gui.history_dialog import _build_history_dialog_class
    DialogCls = _build_history_dialog_class(qt=fake_pyqt6_history)
    dialog = DialogCls()
    dialog.set_entries(None)
    assert dialog.entry_count == 0


def test_history_dialog_label_with_speaker(fake_pyqt6_history):
    """有 speaker → label 文本含 "[speaker] text"。"""
    from runtime.gui.history_dialog import _build_history_dialog_class
    DialogCls = _build_history_dialog_class(qt=fake_pyqt6_history)
    dialog = DialogCls()
    dialog.set_entries([
        {"text": "你好。", "speaker": "alice", "style": "dialog", "ts": None},
    ])
    label = dialog._entry_labels[0]
    assert "[alice] 你好。" in label._text


def test_history_dialog_label_without_speaker(fake_pyqt6_history):
    """无 speaker → label 文本只有 text。"""
    from runtime.gui.history_dialog import _build_history_dialog_class
    DialogCls = _build_history_dialog_class(qt=fake_pyqt6_history)
    dialog = DialogCls()
    dialog.set_entries([
        {"text": "雨夜。", "speaker": None, "style": "narration", "ts": None},
    ])
    label = dialog._entry_labels[0]
    assert label._text == "雨夜。"


def test_history_dialog_label_with_timestamp(fake_pyqt6_history):
    """有 ts → label 文本含 "(HH:MM:SS)"。"""
    from runtime.gui.history_dialog import _build_history_dialog_class
    from datetime import datetime

    DialogCls = _build_history_dialog_class(qt=fake_pyqt6_history)
    dialog = DialogCls()
    ts = time.time()
    dialog.set_entries([
        {"text": "x", "speaker": None, "style": None, "ts": ts},
    ])
    label = dialog._entry_labels[0]
    ts_str = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
    assert ts_str in label._text


def test_history_dialog_refresh_from_backlog(fake_pyqt6_history):
    """refresh_from(backlog) → 从 BackLog 取条目。"""
    from runtime.gui.history_dialog import _build_history_dialog_class
    from runtime.gui.backlog import BackLog
    from core.engine.protocol import TextEvt

    bl = BackLog()
    bl.add(TextEvt(content="第一行。"))
    bl.add(TextEvt(content="第二行。", speaker="alice"))

    DialogCls = _build_history_dialog_class(qt=fake_pyqt6_history)
    dialog = DialogCls()
    dialog.refresh_from(bl)

    assert dialog.entry_count == 2
    assert dialog._entry_labels[0]._entry_text == "第一行。"
    assert dialog._entry_labels[1]._entry_speaker == "alice"


def test_history_dialog_refresh_from_none(fake_pyqt6_history):
    """refresh_from(None) → 空列表。"""
    from runtime.gui.history_dialog import _build_history_dialog_class
    DialogCls = _build_history_dialog_class(qt=fake_pyqt6_history)
    dialog = DialogCls()
    dialog.refresh_from(None)
    assert dialog.entry_count == 0


def test_history_dialog_get_entries_returns_copy(fake_pyqt6_history):
    """get_entries() 返回副本。"""
    from runtime.gui.history_dialog import _build_history_dialog_class
    DialogCls = _build_history_dialog_class(qt=fake_pyqt6_history)
    dialog = DialogCls()
    dialog.set_entries([{"text": "x", "speaker": None, "style": None, "ts": None}])
    entries = dialog.get_entries()
    entries[0]["text"] = "篡改"
    assert dialog.get_entries()[0]["text"] == "x"


def test_history_dialog_close_button_accepts(fake_pyqt6_history):
    """点关闭按钮 → accept。"""
    from runtime.gui.history_dialog import _build_history_dialog_class
    DialogCls = _build_history_dialog_class(qt=fake_pyqt6_history)
    dialog = DialogCls()
    dialog._on_close()
    assert dialog._accepted is True


def test_history_dialog_build_raises_runtime_error_when_no_pyqt6(monkeypatch):
    """qt=None + PyQt6 import 失败 → RuntimeError。"""
    from runtime.gui import history_dialog
    monkeypatch.setitem(sys.modules, "PyQt6.QtCore", None)
    monkeypatch.setitem(sys.modules, "PyQt6.QtWidgets", None)

    with pytest.raises(RuntimeError, match="PyQt6"):
        history_dialog._build_history_dialog_class(qt=None)


def test_history_dialog_module_imports_without_pyqt6():
    """history_dialog 模块顶层不 import PyQt6。"""
    for k in ("PyQt6", "PyQt6.QtCore", "PyQt6.QtWidgets"):
        sys.modules.pop(k, None)
    sys.modules.pop("runtime.gui.history_dialog", None)
    try:
        import runtime.gui.history_dialog as mod
        assert mod is not None
        assert hasattr(mod, "_build_history_dialog_class")
    finally:
        pass


# ═══════════════════════════════════════════════════════════════════════
# 3. MainWindow 集成（BackLog + show_history）
# ═══════════════════════════════════════════════════════════════════════


# 复用 test_pyqt6_main.py 的 fake qt 结构
class _MwFakeSignal:
    def __init__(self):
        self._slots: list = []

    def connect(self, slot):
        self._slots.append(slot)

    def emit(self, *a, **kw):
        for s in self._slots:
            s(*a, **kw)


class _MwFakeQMainWindow:
    def __init__(self, *a, **kw):
        self._title = ""
        self._central = None
        self._shown = False
        self._closed = False

    def setWindowTitle(self, t): self._title = t
    def setCentralWidget(self, w): self._central = w
    def show(self): self._shown = True
    def close(self): self._closed = True


class _MwFakeQTextEdit:
    def __init__(self, *a, **kw): self._text = ""
    def setReadOnly(self, ro): pass
    def append(self, t): self._text += t
    def clear(self): self._text = ""
    def toPlainText(self): return self._text


class _MwFakeQLineEdit:
    def __init__(self, *a, **kw):
        self._text = ""
        self._enabled = True
        self._visible = True
        self.returnPressed = _MwFakeSignal()
    def text(self): return self._text
    def setText(self, t): self._text = t
    def clear(self): self._text = ""
    def setEnabled(self, e): self._enabled = e
    def setVisible(self, v): self._visible = v
    def setFocus(self): pass


class _MwFakeQPushButton:
    def __init__(self, text="", *a, **kw):
        self._text = text
        self._visible = True
        self.clicked = _MwFakeSignal()
    def setVisible(self, v): self._visible = v


class _MwFakeQWidget:
    def __init__(self, *a, **kw): pass


class _MwFakeQVBoxLayout:
    def __init__(self, *a, **kw):
        self._widgets: list = []
    def addWidget(self, w): self._widgets.append(w)


class _MwFakeQApplication:
    _instance = None
    def __init__(self, argv): _MwFakeQApplication._instance = self
    def exec(self): return 0
    @classmethod
    def instance(cls): return cls._instance


@pytest.fixture
def fake_pyqt6_mw(monkeypatch):
    """fake PyQt6 for MainWindow tests (with QLabel/QPixmap for ImageRenderer)."""
    from unittest.mock import MagicMock

    class _FakeQLabel:
        def __init__(self, *a, **kw):
            self._pixmap = None
        def setPixmap(self, pm): self._pixmap = pm
        def setScaledContents(self, b): pass
        def setAlignment(self, a): pass
        def clear(self): self._pixmap = None
        def setParent(self, p): pass
        def deleteLater(self): pass
        def show(self): pass

    class _FakeQPixmap:
        def __init__(self, path=""): self._path = path

    qtcore = types.ModuleType("PyQt6.QtCore")
    qtcore.Qt = MagicMock()
    qtcore.QThread = MagicMock()
    qtcore.QObject = MagicMock()
    qtcore.pyqtSignal = MagicMock(return_value=_MwFakeSignal())

    qtgui = types.ModuleType("PyQt6.QtGui")
    qtgui.QPixmap = _FakeQPixmap

    qtwidgets = types.ModuleType("PyQt6.QtWidgets")
    qtwidgets.QApplication = _MwFakeQApplication
    qtwidgets.QMainWindow = _MwFakeQMainWindow
    qtwidgets.QTextEdit = _MwFakeQTextEdit
    qtwidgets.QLineEdit = _MwFakeQLineEdit
    qtwidgets.QPushButton = _MwFakeQPushButton
    qtwidgets.QWidget = _MwFakeQWidget
    qtwidgets.QVBoxLayout = _MwFakeQVBoxLayout
    qtwidgets.QLabel = _FakeQLabel

    pyqt6_pkg = types.ModuleType("PyQt6")
    pyqt6_pkg.QtCore = qtcore
    pyqt6_pkg.QtWidgets = qtwidgets
    pyqt6_pkg.QtGui = qtgui
    monkeypatch.setitem(sys.modules, "PyQt6", pyqt6_pkg)
    monkeypatch.setitem(sys.modules, "PyQt6.QtCore", qtcore)
    monkeypatch.setitem(sys.modules, "PyQt6.QtGui", qtgui)
    monkeypatch.setitem(sys.modules, "PyQt6.QtWidgets", qtwidgets)
    return {
        "QApplication": _MwFakeQApplication, "QMainWindow": _MwFakeQMainWindow,
        "QTextEdit": _MwFakeQTextEdit, "QLineEdit": _MwFakeQLineEdit,
        "QPushButton": _MwFakeQPushButton, "QWidget": _MwFakeQWidget,
        "QVBoxLayout": _MwFakeQVBoxLayout, "QLabel": _FakeQLabel,
        "QPixmap": _FakeQPixmap, "Qt": qtcore.Qt,
    }


def test_main_window_creates_backlog_by_default(fake_pyqt6_mw):
    """MainWindow 默认创建 BackLog 实例。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from runtime.gui.backlog import BackLog

    MainWindowCls = pyqt6_main._build_main_window_class()
    win = MainWindowCls(sink=PyQt6Sink(), input_sink=PyQt6InputSink())
    assert isinstance(win.backlog, BackLog)


def test_main_window_accepts_injected_backlog(fake_pyqt6_mw):
    """backlog 参数注入 → MainWindow 用注入的实例。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from runtime.gui.backlog import BackLog

    injected = BackLog(max_entries=50)
    MainWindowCls = pyqt6_main._build_main_window_class(backlog=injected)
    win = MainWindowCls(sink=PyQt6Sink(), input_sink=PyQt6InputSink())
    assert win.backlog is injected


def test_main_window_text_evt_accumulates_in_backlog(fake_pyqt6_mw):
    """MainWindow 接收 TextEvt → backlog.add 被调。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from core.engine.protocol import TextEvt

    MainWindowCls = pyqt6_main._build_main_window_class()
    win = MainWindowCls(sink=PyQt6Sink(), input_sink=PyQt6InputSink())

    win._sink.put_evt(TextEvt(content="第一行。", style="narration"))
    win._sink.put_evt(TextEvt(content="第二行。", speaker="alice", style="dialog"))

    assert win.backlog.count == 2
    entries = win.backlog.get_entries()
    assert entries[0]["text"] == "第一行。"
    assert entries[1]["speaker"] == "alice"


def test_main_window_show_history_returns_dialog(fake_pyqt6_mw, monkeypatch):
    """show_history(qt_override) → 返回 HistoryDialog 实例（含当前 backlog）。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from core.engine.protocol import TextEvt

    # 注入 HistoryDialog 用的 fake qt（含 QDialog/QScrollArea 等）
    history_qt = {
        "QDialog": _FakeQDialog, "QVBoxLayout": _FakeQVBoxLayout,
        "QHBoxLayout": _FakeQHBoxLayout, "QLabel": _FakeQLabel,
        "QPushButton": _FakeQPushButton, "QWidget": _FakeQWidget,
        "QScrollArea": _FakeQScrollArea,
    }

    MainWindowCls = pyqt6_main._build_main_window_class()
    win = MainWindowCls(sink=PyQt6Sink(), input_sink=PyQt6InputSink())
    win._sink.put_evt(TextEvt(content="历史文本。"))

    dialog = win.show_history(qt_override=history_qt)
    assert dialog is not None
    assert dialog.entry_count == 1
    assert dialog._entry_labels[0]._entry_text == "历史文本。"


def test_main_window_show_history_empty_backlog(fake_pyqt6_mw):
    """空 backlog → show_history 返回空 dialog。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink

    history_qt = {
        "QDialog": _FakeQDialog, "QVBoxLayout": _FakeQVBoxLayout,
        "QHBoxLayout": _FakeQHBoxLayout, "QLabel": _FakeQLabel,
        "QPushButton": _FakeQPushButton, "QWidget": _FakeQWidget,
        "QScrollArea": _FakeQScrollArea,
    }

    MainWindowCls = pyqt6_main._build_main_window_class()
    win = MainWindowCls(sink=PyQt6Sink(), input_sink=PyQt6InputSink())

    dialog = win.show_history(qt_override=history_qt)
    assert dialog.entry_count == 0


# ═══════════════════════════════════════════════════════════════════════
# 4. 端到端：chapter01 → MainWindow → BackLog → HistoryDialog
# ═══════════════════════════════════════════════════════════════════════


def test_e2e_chapter01_accumulates_history(fake_pyqt6_mw):
    """chapter01_v1.md 全流程跑完后 → backlog 含所有 TextEvt 文本。"""
    from core.engine.main import _load_story
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from runtime.gui import pyqt6_main
    from core.engine.executor import Executor
    from core.decorators import style as style_mod

    style_mod.install()

    chapter_path = os.path.join(REPO_ROOT, "chapters", "chapter01_v1.md")
    story = _load_story(chapter_path)

    sink = PyQt6Sink()
    input_sink = PyQt6InputSink()
    input_sink.submit("平静")
    input_sink.submit("1")
    sink._cmd_source = input_sink.drain_cmd

    MainWindowCls = pyqt6_main._build_main_window_class()
    win = MainWindowCls(sink=sink, input_sink=input_sink)

    exe = Executor(story, sink)
    exe.run()

    # backlog 应累积所有 TextEvt（雨夜/雨声/坐在窗边/echo/敲门/打开门）
    assert win.backlog.count > 0
    texts = [e["text"] for e in win.backlog.get_entries()]
    assert any("雨夜" in t for t in texts)
    assert any("敲门" in t for t in texts)
    assert any("打开门" in t for t in texts)
