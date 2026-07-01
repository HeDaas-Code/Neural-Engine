"""v3-07 · ReadMarks 已读标记 + AutoModeController 测试（#97）。

验证 issue #97 验收点：
- ReadMarks：mark / is_read / count / clear / get_all
- ReadMarks 持久化：save / load（JSON）
- ReadMarks.mark_evt 从 TextEvt 提取 content
- AutoModeController：auto_mode / skip_mode 状态切换
- AutoModeController：notify_text_complete + on_advance 回调
- AutoModeController：cancel / reset / 防抖
- AutoModeController：QTimer 注入路径
- MainWindow 集成：TextEvt → mark + skip_mode 跳过打字机 + Auto 推进
- MainWindow close 时 reset AutoMode
"""
from __future__ import annotations

import json
import os
import sys
import types
from unittest.mock import MagicMock

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")


# ═══════════════════════════════════════════════════════════════════════
# 1. ReadMarks 基础测试
# ═══════════════════════════════════════════════════════════════════════


def test_read_marks_constructs_empty():
    """ReadMarks 默认构造 → 空。"""
    from runtime.gui.read_marks import ReadMarks
    m = ReadMarks()
    assert m.is_empty is True
    assert m.count == 0
    assert m.get_all() == []


def test_read_marks_mark_returns_true_for_new():
    """mark 新文本 → True，count +1。"""
    from runtime.gui.read_marks import ReadMarks
    m = ReadMarks()
    assert m.mark("雨夜。") is True
    assert m.count == 1
    assert m.is_empty is False


def test_read_marks_mark_returns_false_for_duplicate():
    """mark 重复文本 → False，count 不增。"""
    from runtime.gui.read_marks import ReadMarks
    m = ReadMarks()
    m.mark("foo")
    assert m.mark("foo") is False
    assert m.count == 1


def test_read_marks_mark_empty_string_silent():
    """mark("") → False，不加入。"""
    from runtime.gui.read_marks import ReadMarks
    m = ReadMarks()
    assert m.mark("") is False
    assert m.mark(None) is False  # type: ignore
    assert m.count == 0


def test_read_marks_is_read():
    """is_read 查询。"""
    from runtime.gui.read_marks import ReadMarks
    m = ReadMarks()
    m.mark("hello")
    assert m.is_read("hello") is True
    assert m.is_read("world") is False


def test_read_marks_clear():
    """clear → 清空。"""
    from runtime.gui.read_marks import ReadMarks
    m = ReadMarks()
    m.mark("a")
    m.mark("b")
    m.clear()
    assert m.count == 0
    assert m.is_read("a") is False


def test_read_marks_get_all_sorted():
    """get_all 返回 sorted 列表（断言稳定）。"""
    from runtime.gui.read_marks import ReadMarks
    m = ReadMarks()
    m.mark("banana")
    m.mark("apple")
    m.mark("cherry")
    assert m.get_all() == ["apple", "banana", "cherry"]


def test_read_marks_mark_evt():
    """mark_evt 从 TextEvt 提取 content。"""
    from runtime.gui.read_marks import ReadMarks
    from core.engine.protocol import TextEvt
    m = ReadMarks()
    assert m.mark_evt(TextEvt(content="foo", style="narration")) is True
    assert m.is_read("foo") is True


def test_read_marks_mark_evt_none_silent():
    """mark_evt(None) → False。"""
    from runtime.gui.read_marks import ReadMarks
    m = ReadMarks()
    assert m.mark_evt(None) is False  # type: ignore
    assert m.count == 0


# ═══════════════════════════════════════════════════════════════════════
# 2. ReadMarks 持久化测试
# ═══════════════════════════════════════════════════════════════════════


def test_read_marks_save_to_file(tmp_path):
    """save → JSON 文件写入。"""
    from runtime.gui.read_marks import ReadMarks
    f = tmp_path / "marks.json"
    m = ReadMarks(marks_file=f)
    m.mark("alpha")
    m.mark("beta")
    assert m.save() is True
    assert f.exists()
    data = json.loads(f.read_text(encoding="utf-8"))
    assert data == ["alpha", "beta"]


def test_read_marks_load_from_file(tmp_path):
    """构造时加载已存在的文件。"""
    from runtime.gui.read_marks import ReadMarks
    f = tmp_path / "marks.json"
    f.write_text(json.dumps(["gamma", "delta"], ensure_ascii=False), encoding="utf-8")
    m = ReadMarks(marks_file=f)
    assert m.count == 2
    assert m.is_read("gamma") is True
    assert m.is_read("delta") is True


def test_read_marks_save_no_file_returns_false():
    """无 marks_file 时 save → False。"""
    from runtime.gui.read_marks import ReadMarks
    m = ReadMarks()
    assert m.save() is False


def test_read_marks_load_missing_file_silent(tmp_path):
    """加载不存在的文件 → 静默（不抛错）。"""
    from runtime.gui.read_marks import ReadMarks
    f = tmp_path / "nonexistent.json"
    m = ReadMarks(marks_file=f)
    assert m.count == 0


def test_read_marks_load_corrupt_json_silent(tmp_path):
    """加载损坏的 JSON → 静默。"""
    from runtime.gui.read_marks import ReadMarks
    f = tmp_path / "bad.json"
    f.write_text("not valid json {{{", encoding="utf-8")
    m = ReadMarks(marks_file=f)
    assert m.count == 0


def test_read_marks_load_non_list_silent(tmp_path):
    """加载非 list JSON → 静默。"""
    from runtime.gui.read_marks import ReadMarks
    f = tmp_path / "obj.json"
    f.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    m = ReadMarks(marks_file=f)
    assert m.count == 0


def test_read_marks_save_creates_parent_dir(tmp_path):
    """save 自动创建父目录。"""
    from runtime.gui.read_marks import ReadMarks
    f = tmp_path / "subdir" / "nested" / "marks.json"
    m = ReadMarks(marks_file=f)
    m.mark("x")
    assert m.save() is True
    assert f.exists()


def test_read_marks_roundtrip(tmp_path):
    """save → 新实例 load → 数据一致。"""
    from runtime.gui.read_marks import ReadMarks
    f = tmp_path / "rt.json"
    m1 = ReadMarks(marks_file=f)
    m1.mark("apple")
    m1.mark("banana")
    m1.mark("cherry")
    m1.save()
    # 新实例加载
    m2 = ReadMarks(marks_file=f)
    assert m2.count == 3
    assert m2.get_all() == ["apple", "banana", "cherry"]


# ═══════════════════════════════════════════════════════════════════════
# 3. AutoModeController 状态切换测试
# ═══════════════════════════════════════════════════════════════════════


def test_auto_mode_default_off():
    """AutoModeController 默认状态：auto=False, skip=False。"""
    from runtime.gui.auto_mode import AutoModeController
    c = AutoModeController()
    assert c.auto_mode is False
    assert c.skip_mode is False
    assert c.has_pending is False


def test_auto_mode_toggle_auto():
    """toggle_auto → 切换状态。"""
    from runtime.gui.auto_mode import AutoModeController
    c = AutoModeController()
    assert c.toggle_auto() is True
    assert c.auto_mode is True
    assert c.toggle_auto() is False
    assert c.auto_mode is False


def test_auto_mode_toggle_skip():
    """toggle_skip → 切换状态。"""
    from runtime.gui.auto_mode import AutoModeController
    c = AutoModeController()
    assert c.toggle_skip() is True
    assert c.skip_mode is True
    assert c.toggle_skip() is False


def test_auto_mode_set_auto():
    """set_auto 显式设置。"""
    from runtime.gui.auto_mode import AutoModeController
    c = AutoModeController()
    c.set_auto(True)
    assert c.auto_mode is True
    c.set_auto(True)  # 已开 → 不变
    assert c.auto_mode is True
    c.set_auto(False)
    assert c.auto_mode is False


def test_auto_mode_set_skip():
    """set_skip 显式设置。"""
    from runtime.gui.auto_mode import AutoModeController
    c = AutoModeController()
    c.set_skip(True)
    assert c.skip_mode is True


def test_auto_mode_set_auto_delay():
    """set_auto_delay 设置延迟（负数归零）。"""
    from runtime.gui.auto_mode import AutoModeController
    c = AutoModeController(auto_delay_ms=1000)
    assert c.auto_delay_ms == 1000
    c.set_auto_delay(2000)
    assert c.auto_delay_ms == 2000
    c.set_auto_delay(-5)
    assert c.auto_delay_ms == 0


def test_auto_mode_toggle_auto_off_cancels_pending():
    """关闭 Auto 时若有 pending 计时，一并取消。"""
    from runtime.gui.auto_mode import AutoModeController
    c = AutoModeController(auto_delay_ms=0)
    c.set_auto(True)
    # 不实际调度 pending（无 QTimer，delay=0 立即推进）
    c.set_auto(False)
    assert c.has_pending is False


def test_auto_mode_reset():
    """reset → 关闭 Auto/Skip + 取消 pending。"""
    from runtime.gui.auto_mode import AutoModeController
    c = AutoModeController()
    c.set_auto(True)
    c.set_skip(True)
    c.reset()
    assert c.auto_mode is False
    assert c.skip_mode is False


# ═══════════════════════════════════════════════════════════════════════
# 4. AutoModeController notify_text_complete 测试
# ═══════════════════════════════════════════════════════════════════════


def test_notify_text_complete_noop_when_auto_off():
    """Auto 关闭时 notify_text_complete 不触发。"""
    calls = []
    c = __import__("runtime.gui.auto_mode", fromlist=["AutoModeController"]).AutoModeController(
        on_advance=lambda: calls.append(1),
        auto_delay_ms=0,
    )
    c.notify_text_complete()
    assert calls == []


def test_notify_text_complete_immediate_when_delay_zero():
    """Auto 开 + delay=0 → 立即同步推进。"""
    from runtime.gui.auto_mode import AutoModeController
    calls = []
    c = AutoModeController(
        on_advance=lambda: calls.append("adv"),
        auto_delay_ms=0,
    )
    c.set_auto(True)
    c.notify_text_complete()
    assert calls == ["adv"]
    assert c.has_pending is False


def test_notify_text_complete_immediate_when_no_qtimer():
    """Auto 开 + delay>0 + 无 QTimer → fallback 立即推进。"""
    from runtime.gui.auto_mode import AutoModeController
    calls = []
    c = AutoModeController(
        on_advance=lambda: calls.append("adv"),
        auto_delay_ms=500,
        qt={},  # 空 dict → _get_qtimer 返回 None
    )
    c.set_auto(True)
    c.notify_text_complete()
    assert calls == ["adv"]


def test_notify_text_complete_debounce():
    """已有 pending 时再调 notify_text_complete → 防抖（不重复调度）。"""
    from runtime.gui.auto_mode import AutoModeController

    class FakeTimer:
        def __init__(self):
            self.started = False
            self.stopped = False
            self.timeout = type("S", (), {"connect": lambda self, s: None})()

        def setSingleShot(self, b): pass
        def start(self, ms): self.started = True
        def stop(self): self.stopped = True

    timer_inst = FakeTimer()
    timer_inst.timeout = type("Sig", (), {"connect": lambda self, s: setattr(self, "_s", s)})()
    QTimerCls = lambda: timer_inst  # noqa: E731
    calls = []
    c = AutoModeController(
        on_advance=lambda: calls.append(1),
        auto_delay_ms=500,
        qt={"QTimer": QTimerCls},
    )
    c.set_auto(True)
    c.notify_text_complete()
    assert c.has_pending is True
    c.notify_text_complete()  # 防抖
    assert c.has_pending is True


def test_cancel_stops_pending():
    """cancel → 取消 pending 计时。"""
    from runtime.gui.auto_mode import AutoModeController

    class FakeTimer:
        def __init__(self):
            self.stopped = False
            self.timeout = type("S", (), {"connect": lambda self, s: None})()

        def setSingleShot(self, b): pass
        def start(self, ms): pass
        def stop(self): self.stopped = True

    timer_inst = FakeTimer()
    QTimerCls = lambda: timer_inst  # noqa: E731
    c = AutoModeController(
        on_advance=lambda: None,
        auto_delay_ms=500,
        qt={"QTimer": QTimerCls},
    )
    c.set_auto(True)
    c.notify_text_complete()
    assert c.has_pending is True
    c.cancel()
    assert c.has_pending is False
    assert timer_inst.stopped is True


def test_on_advance_exception_swallowed():
    """on_advance 抛异常 → 静默吞掉（不污染调用方）。"""
    from runtime.gui.auto_mode import AutoModeController

    def bad():
        raise RuntimeError("boom")

    c = AutoModeController(on_advance=bad, auto_delay_ms=0)
    c.set_auto(True)
    # 不应抛
    c.notify_text_complete()
    assert c.has_pending is False


def test_set_on_advance_runtime_rebind():
    """set_on_advance 运行时替换回调。"""
    from runtime.gui.auto_mode import AutoModeController
    calls_a = []
    calls_b = []
    c = AutoModeController(on_advance=lambda: calls_a.append(1), auto_delay_ms=0)
    c.set_auto(True)
    c.notify_text_complete()
    assert calls_a == [1]
    c.set_on_advance(lambda: calls_b.append(2))
    c.notify_text_complete()
    assert calls_b == [2]


# ═══════════════════════════════════════════════════════════════════════
# 5. AutoModeController QTimer 集成测试
# ═══════════════════════════════════════════════════════════════════════


class FakeQTimerForAuto:
    """Fake QTimer —— 记录调用 + 可手动触发 timeout。"""
    instances: list = []

    def __init__(self):
        self._slot = None
        self._started = False
        self._stopped = False
        self._delay_ms = None
        FakeQTimerForAuto.instances.append(self)

    def setSingleShot(self, b):
        self._single = b

    def start(self, ms):
        self._started = True
        self._delay_ms = ms

    def stop(self):
        self._stopped = True

    @property
    def timeout(self):
        # 返回带 connect 方法的 fake signal
        sig = self
        class _Sig:
            def connect(self_inner, slot):
                sig._slot = slot
        return _Sig()

    def fire_timeout(self):
        """测试手动触发 timeout（模拟定时器到期）。"""
        if self._slot is not None:
            self._slot()


def test_notify_text_complete_uses_qtimer_when_available():
    """Auto 开 + delay>0 + 有 QTimer → 启动单次定时器。"""
    FakeQTimerForAuto.instances = []
    from runtime.gui.auto_mode import AutoModeController
    calls = []
    c = AutoModeController(
        on_advance=lambda: calls.append("adv"),
        auto_delay_ms=800,
        qt={"QTimer": FakeQTimerForAuto},
    )
    c.set_auto(True)
    c.notify_text_complete()
    assert c.has_pending is True
    assert len(FakeQTimerForAuto.instances) == 1
    t = FakeQTimerForAuto.instances[0]
    assert t._started is True
    assert t._delay_ms == 800
    assert t._stopped is False
    # 手动触发定时器
    t.fire_timeout()
    assert calls == ["adv"]
    assert c.has_pending is False


# ═══════════════════════════════════════════════════════════════════════
# 6. MainWindow 集成测试
# ═══════════════════════════════════════════════════════════════════════


# ─── Fake Qt Widgets（与 test_pyqt6_main.py 一致风格）─────────────────


class FakeSignal:
    def __init__(self):
        self._slots: list = []

    def connect(self, slot):
        self._slots.append(slot)


class FakeQMainWindowMW:
    def __init__(self, *a, **kw):
        self._window_title = ""
        self._shown = False
        self._closed = False

    def setWindowTitle(self, t): self._window_title = t
    def setCentralWidget(self, w): pass
    def show(self): self._shown = True
    def close(self): self._closed = True


class FakeQTextEditMW:
    def __init__(self, *a, **kw):
        self._text = ""
        self._read_only = False
        self._style_sheet = ""

    def setReadOnly(self, ro): self._read_only = ro
    def append(self, t): self._text += t
    def insertPlainText(self, t): self._text += t
    def setStyleSheet(self, css): self._style_sheet = css
    def toPlainText(self): return self._text
    def clear(self): self._text = ""


class FakeQLineEditMW:
    def __init__(self, *a, **kw):
        self._text = ""
        self._enabled = True
        self._visible = True
        self.returnPressed = FakeSignal()

    def text(self): return self._text
    def setText(self, t): self._text = t
    def clear(self): self._text = ""
    def setEnabled(self, e): self._enabled = e
    def setVisible(self, v): self._visible = v
    def setFocus(self): pass


class FakeQPushButtonMW:
    def __init__(self, t="", *a, **kw):
        self._text = t
        self._visible = True
        self.clicked = FakeSignal()

    def setVisible(self, v): self._visible = v
    def setEnabled(self, e): pass
    def setParent(self, p): pass
    def deleteLater(self): pass


class FakeQWidgetMW:
    def __init__(self, *a, **kw): pass


class FakeQVBoxLayoutMW:
    def __init__(self, *a, **kw):
        self._widgets: list = []

    def addWidget(self, w): self._widgets.append(w)


class FakeQLabelMW:
    def __init__(self, *a, **kw):
        self._pixmap = None

    def setPixmap(self, pm): self._pixmap = pm
    def setScaledContents(self, b): pass
    def setAlignment(self, a): pass
    def clear(self): self._pixmap = None
    def setParent(self, p): pass
    def deleteLater(self): pass
    def show(self): pass


class FakeQPixmapMW:
    def __init__(self, path=""):
        self._path = path


@pytest.fixture
def fake_pyqt6_mw(monkeypatch):
    """注入 fake PyQt6（MainWindow 集成测试用，含 QLabel/QPixmap for ImageRenderer）。"""
    qt = {
        "QMainWindow": FakeQMainWindowMW,
        "QTextEdit": FakeQTextEditMW,
        "QLineEdit": FakeQLineEditMW,
        "QPushButton": FakeQPushButtonMW,
        "QWidget": FakeQWidgetMW,
        "QVBoxLayout": FakeQVBoxLayoutMW,
        "QLabel": FakeQLabelMW,
        "QPixmap": FakeQPixmapMW,
    }
    return qt


def _make_main_window(qt, **kwargs):
    """构造 MainWindow 实例（注入 fake qt + 已 reset 装饰器状态）。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    # 清装饰器全局状态
    from core.decorators import clear
    from core.decorators import bgm as bgm_mod
    from core.decorators import bg as bg_mod
    from core.decorators import char as char_mod
    clear()
    bgm_mod.set_audio_manager(None)
    bg_mod.set_image_manager(None)
    char_mod.set_image_manager(None)
    MainWindowCls = pyqt6_main._build_main_window_class(qt=qt, **kwargs)
    sink = PyQt6Sink()
    input_sink = PyQt6InputSink()
    return MainWindowCls(sink=sink, input_sink=input_sink)


@pytest.fixture(autouse=True)
def _reset_decorator_state():
    """每个测试前后清空装饰器全局状态。"""
    from core.decorators import clear
    from core.decorators import bgm as bgm_mod
    from core.decorators import bg as bg_mod
    from core.decorators import char as char_mod
    clear()
    bgm_mod.set_audio_manager(None)
    bg_mod.set_image_manager(None)
    char_mod.set_image_manager(None)
    yield
    clear()
    bgm_mod.set_audio_manager(None)
    bg_mod.set_image_manager(None)
    char_mod.set_image_manager(None)


def test_main_window_has_read_marks(fake_pyqt6_mw):
    """MainWindow 构造时创建 ReadMarks 实例。"""
    win = _make_main_window(fake_pyqt6_mw, char_delay_ms=0)
    assert win.read_marks is not None
    assert win.read_marks.count == 0


def test_main_window_has_auto_mode(fake_pyqt6_mw):
    """MainWindow 构造时创建 AutoModeController 实例。"""
    win = _make_main_window(fake_pyqt6_mw, char_delay_ms=0)
    assert win.auto_mode is not None
    assert win.auto_mode.auto_mode is False
    assert win.auto_mode.skip_mode is False


def test_main_window_text_evt_marks_read(fake_pyqt6_mw):
    """TextEvt → read_marks.mark_evt 标记已读。"""
    from core.engine.protocol import TextEvt
    win = _make_main_window(fake_pyqt6_mw, char_delay_ms=0)
    win._handle_evt(TextEvt(content="雨夜。", style="narration"))
    assert win.read_marks.is_read("雨夜。") is True
    assert win.read_marks.count == 1


def test_main_window_multiple_text_evt_accumulates_marks(fake_pyqt6_mw):
    """多条 TextEvt → 累积已读标记。"""
    from core.engine.protocol import TextEvt
    win = _make_main_window(fake_pyqt6_mw, char_delay_ms=0)
    win._handle_evt(TextEvt(content="a"))
    win._handle_evt(TextEvt(content="b"))
    win._handle_evt(TextEvt(content="c"))
    assert win.read_marks.count == 3


def test_main_window_skip_mode_skips_typewriter(fake_pyqt6_mw):
    """skip_mode 开启时 TextRenderer.render 后立即 skip（无打字机动画）。"""
    from core.engine.protocol import TextEvt
    win = _make_main_window(fake_pyqt6_mw, char_delay_ms=40)  # 启用打字机
    win.auto_mode.set_skip(True)
    win._handle_evt(TextEvt(content="hello"))
    # 打字机应已被 skip（is_typing=False）
    assert win._text_renderer.is_typing is False


def test_main_window_auto_mode_advances_after_text(fake_pyqt6_mw):
    """Auto 模式 + delay=0 → TextEvt 后立即触发推进（submit 空串）。"""
    from core.engine.protocol import TextEvt
    submitted = []
    win = _make_main_window(fake_pyqt6_mw, char_delay_ms=0)
    # 替换 input_sink.submit 捕获推进
    win._input_sink.submit = lambda v: submitted.append(v)
    # AutoModeController delay=0 + 开启 Auto
    win.auto_mode.set_auto_delay(0)
    win.auto_mode.set_auto(True)
    win._handle_evt(TextEvt(content="foo"))
    assert submitted == [""]


def test_main_window_auto_mode_off_does_not_advance(fake_pyqt6_mw):
    """Auto 关闭时 TextEvt 不自动推进。"""
    from core.engine.protocol import TextEvt
    submitted = []
    win = _make_main_window(fake_pyqt6_mw, char_delay_ms=0)
    win._input_sink.submit = lambda v: submitted.append(v)
    # Auto 保持关闭
    win._handle_evt(TextEvt(content="foo"))
    assert submitted == []


def test_main_window_auto_mode_skipped_when_options_visible(fake_pyqt6_mw):
    """OptionsPanel 有按钮时 _auto_advance 不推进（避免误选）。"""
    from core.engine.protocol import TextEvt, PromptInputEvt
    submitted = []
    win = _make_main_window(fake_pyqt6_mw, char_delay_ms=0)
    win._input_sink.submit = lambda v: submitted.append(v)
    win.auto_mode.set_auto_delay(0)
    win.auto_mode.set_auto(True)
    # 先触发 PromptInputEvt 显示 options
    win._handle_evt(PromptInputEvt(var="x", options=("选A", "选B")))
    assert win._options_panel.button_count > 0
    # 直接调 _auto_advance（模拟 Auto 触发）
    win._auto_advance()
    assert submitted == []  # 不应推进


def test_main_window_on_submit_cancels_auto_pending(fake_pyqt6_mw):
    """用户手动提交 → 取消 Auto 待推进。"""
    from runtime.gui.auto_mode import AutoModeController

    class FakeTimer:
        def __init__(self):
            self.stopped = False
            self.timeout = type("S", (), {"connect": lambda self, s: None})()

        def setSingleShot(self, b): pass
        def start(self, ms): pass
        def stop(self): self.stopped = True

    timer_inst = FakeTimer()
    QTimerCls = lambda: timer_inst  # noqa: E731
    win = _make_main_window(
        fake_pyqt6_mw, char_delay_ms=0,
        auto_mode_controller=AutoModeController(
            on_advance=lambda: None, auto_delay_ms=500, qt={"QTimer": QTimerCls},
        ),
    )
    win.auto_mode.set_auto(True)
    # 制造 pending（通过 notify_text_complete 需要 TextEvt）
    from core.engine.protocol import TextEvt
    win._handle_evt(TextEvt(content="x"))
    assert win.auto_mode.has_pending is True
    # 用户手动输入并提交
    win.input_line.setText("manual")
    win._on_submit()
    assert win.auto_mode.has_pending is False


def test_main_window_close_resets_auto_mode(fake_pyqt6_mw):
    """close 时 auto_mode.reset 被调用（关闭 Auto/Skip + 取消 pending）。"""
    win = _make_main_window(fake_pyqt6_mw, char_delay_ms=0)
    win.auto_mode.set_auto(True)
    win.auto_mode.set_skip(True)
    win.close()
    assert win.auto_mode.auto_mode is False
    assert win.auto_mode.skip_mode is False


def test_main_window_injected_read_marks_used(fake_pyqt6_mw):
    """注入自定义 ReadMarks → MainWindow 用它（不 lazy 创建）。"""
    from runtime.gui.read_marks import ReadMarks
    custom = ReadMarks()
    custom.mark("preexisting")
    win = _make_main_window(
        fake_pyqt6_mw, char_delay_ms=0, read_marks=custom,
    )
    assert win.read_marks is custom
    assert win.read_marks.is_read("preexisting") is True


def test_main_window_injected_auto_mode_used(fake_pyqt6_mw):
    """注入自定义 AutoModeController → MainWindow 用它。"""
    from runtime.gui.auto_mode import AutoModeController
    custom = AutoModeController(on_advance=lambda: None, auto_delay_ms=0)
    win = _make_main_window(
        fake_pyqt6_mw, char_delay_ms=0, auto_mode_controller=custom,
    )
    assert win.auto_mode is custom


# ═══════════════════════════════════════════════════════════════════════
# 7. 模块导入测试
# ═══════════════════════════════════════════════════════════════════════


def test_read_marks_module_imports():
    """read_marks 模块可独立 import（无 PyQt6 依赖）。"""
    # 强制无 PyQt6
    for k in list(sys.modules):
        if k.startswith("PyQt6"):
            sys.modules.pop(k, None)
    from runtime.gui.read_marks import ReadMarks
    assert ReadMarks is not None


def test_auto_mode_module_imports():
    """auto_mode 模块可独立 import（无 PyQt6 依赖）。"""
    for k in list(sys.modules):
        if k.startswith("PyQt6"):
            sys.modules.pop(k, None)
    from runtime.gui.auto_mode import AutoModeController
    assert AutoModeController is not None


def test_auto_mode_default_delay_constant():
    """DEFAULT_AUTO_DELAY_MS 常量导出。"""
    from runtime.gui.auto_mode import DEFAULT_AUTO_DELAY_MS
    assert isinstance(DEFAULT_AUTO_DELAY_MS, int)
    assert DEFAULT_AUTO_DELAY_MS > 0
