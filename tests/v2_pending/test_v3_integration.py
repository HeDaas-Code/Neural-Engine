"""v3-09 · v3 全功能集成测试（#99）。

验证 v3-01 ~ v3-08 所有功能在 chapter01_v1.md 全流程中协同工作：

v3-01 TextRenderer  ── 打字机 + 名字标签 + @style
v3-02 OptionsPanel  ── PromptInputEvt.options → 按钮
v3-03 AudioManager   ── @bgm 装饰器 → 三轨播放
v3-04 ImageRenderer  ── @bg/@char 装饰器 → 背景图 + 立绘
v3-05 SaveSlotDialog ── 存档截图（此处仅验 SaveManager 截图字段）
v3-06 BackLog        ── TextEvt → backlog.add → HistoryDialog
v3-07 ReadMarks      ── TextEvt → mark + AutoMode + Skip
v3-08 SettingsDialog ── SettingsManager + apply_to_*

测试策略：
- 用 fake PyQt6（CI 无 PyQt6 环境）
- 跑 chapter01_v1.md 全流程
- 验证：display 文本 / backlog 累积 / read_marks / settings 应用 / auto_mode 状态
"""
from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))


# ─── Fake Qt Widgets（复用 e2e 风格）───────────────────────────────────


class FakeSignal:
    def __init__(self):
        self._slots: list = []

    def connect(self, slot):
        self._slots.append(slot)

    def emit(self, *args, **kwargs):
        for slot in self._slots:
            slot(*args, **kwargs)


class FakeQMainWindow:
    def __init__(self, *a, **kw):
        self._window_title = ""
        self._shown = False
        self._closed = False

    def setWindowTitle(self, t): self._window_title = t
    def setCentralWidget(self, w): pass
    def show(self): self._shown = True
    def close(self): self._closed = True


class FakeQTextEdit:
    def __init__(self, *a, **kw):
        self._text = ""
        self._style_sheet = ""

    def setReadOnly(self, ro): pass
    def append(self, t): self._text += t
    def insertPlainText(self, t): self._text += t
    def setStyleSheet(self, css): self._style_sheet = css
    def toPlainText(self): return self._text
    def clear(self): self._text = ""


class FakeQLineEdit:
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


class FakeQPushButton:
    def __init__(self, t="", *a, **kw):
        self._text = t
        self._visible = True
        self.clicked = FakeSignal()

    def setVisible(self, v): self._visible = v
    def setEnabled(self, e): pass
    def setParent(self, p): pass
    def deleteLater(self): pass


class FakeQWidget:
    def __init__(self, *a, **kw): pass


class FakeQVBoxLayout:
    def __init__(self, *a, **kw):
        self._widgets: list = []

    def addWidget(self, w): self._widgets.append(w)


class FakeQLabel:
    def __init__(self, *a, **kw):
        self._pixmap = None

    def setPixmap(self, pm): self._pixmap = pm
    def setScaledContents(self, b): pass
    def setAlignment(self, a): pass
    def clear(self): self._pixmap = None
    def setParent(self, p): pass
    def deleteLater(self): pass
    def show(self): pass


class FakeQPixmap:
    def __init__(self, path=""):
        self._path = path

    @classmethod
    def fromLocalFile(cls, path):
        return cls(path)


@pytest.fixture
def fake_pyqt6_v3(monkeypatch):
    """注入 fake PyQt6 modules（v3 集成测试用）。"""
    qt = {
        "QMainWindow": FakeQMainWindow,
        "QTextEdit": FakeQTextEdit,
        "QLineEdit": FakeQLineEdit,
        "QPushButton": FakeQPushButton,
        "QWidget": FakeQWidget,
        "QVBoxLayout": FakeQVBoxLayout,
        "QLabel": FakeQLabel,
        "QPixmap": FakeQPixmap,
    }
    return qt


@pytest.fixture(autouse=True)
def _reset_all_state(tmp_path, monkeypatch):
    """每个测试前后：清装饰器状态 + 重置 home 目录（避免污染 ~/.neural-engine）。"""
    # 重定向 HOME 到 tmp_path，避免 SettingsManager 默认路径污染
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    from core.decorators import clear
    from core.decorators import style as style_mod
    from core.decorators import bgm as bgm_mod
    from core.decorators import bg as bg_mod
    from core.decorators import char as char_mod
    clear()
    style_mod.reset_last_style()
    bgm_mod.reset_last_bgm()
    bg_mod.reset_last_bg()
    char_mod.reset_last_char()
    bgm_mod.set_audio_manager(None)
    bg_mod.set_image_manager(None)
    char_mod.set_image_manager(None)
    yield
    clear()
    style_mod.reset_last_style()
    bgm_mod.reset_last_bgm()
    bg_mod.reset_last_bg()
    char_mod.reset_last_char()
    bgm_mod.set_audio_manager(None)
    bg_mod.set_image_manager(None)
    char_mod.set_image_manager(None)


# ═══════════════════════════════════════════════════════════════════════
# 1. v3 全功能端到端：chapter01_v1.md 全流程
# ═══════════════════════════════════════════════════════════════════════


def test_v3_e2e_chapter01_full_flow_with_all_components(fake_pyqt6_v3, tmp_path):
    """chapter01_v1.md 全流程 + v3-01~v3-08 所有组件协同。

    验证点：
    - v3-01 TextRenderer：display 累积剧情文本
    - v3-06 BackLog：backlog 累积所有 TextEvt
    - v3-07 ReadMarks：read_marks 标记已显示文本
    - v3-08 SettingsManager：构造时应用到 text_renderer / auto_mode
    - v3-03 AudioManager：构造时创建 + 注册到 @bgm 钩子
    - v3-04 ImageRenderer：构造时创建 + 注册到 @bg/@char 钩子
    - 章节正常结束 → window.close()
    """
    # 1. 加载章节
    from core.engine.main import _load_story
    chapter_path = REPO_ROOT / "chapters" / "chapter01_v1.md"
    story = _load_story(str(chapter_path))

    # 2. 安装装饰器钩子
    from core.decorators import style as style_mod
    from core.decorators import bgm as bgm_mod
    style_mod.install()
    bgm_mod.install()

    # 3. 构造 MainWindow（带自定义 settings 文件路径避免污染 home）
    from runtime.settings import SettingsManager
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({
        "text_speed": 0,  # 关闭打字机（同步路径，便于断言）
        "auto_delay": 0,
    }), encoding="utf-8")

    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink

    sink = PyQt6Sink()
    input_sink = PyQt6InputSink()
    # 预填 cmd queue（剧情需要 mood + pick）
    input_sink.submit("平静")
    input_sink.submit("1")
    sink._cmd_source = input_sink.drain_cmd

    MainWindowCls = pyqt6_main._build_main_window_class(
        qt=fake_pyqt6_v3,
        settings_manager=SettingsManager(settings_file=settings_file),
    )
    window = MainWindowCls(sink=sink, input_sink=input_sink)

    # 4. 跑 Executor
    from core.engine.executor import Executor
    exe = Executor(story, sink)
    exe.run()

    # 5. 验证 v3-01 TextRenderer：display 含剧情文本
    text = window.display.toPlainText()
    assert "雨夜。" in text
    assert "你听到门外传来两声敲门。" in text
    assert "你打开门，雨中站着一个人。" in text

    # 6. 验证 v3-06 BackLog：累积所有 TextEvt
    assert window.backlog.count > 0
    backlog_texts = [e["text"] for e in window.backlog.get_entries()]
    assert any("雨夜" in t for t in backlog_texts)
    assert any("敲门" in t for t in backlog_texts)

    # 7. 验证 v3-07 ReadMarks：标记已读文本
    # 注意：Text.content 保留行尾 \n（splitlines(keepends=True)），故用子串匹配
    assert window.read_marks.count > 0
    read_texts = window.read_marks.get_all()
    assert any("雨夜" in t for t in read_texts)
    assert any("敲门" in t for t in read_texts)

    # 8. 验证 v3-08 SettingsManager：text_speed=0 应用到 text_renderer
    assert window._text_renderer._char_delay_ms == 0
    # auto_delay=0 应用到 auto_mode
    assert window.auto_mode.auto_delay_ms == 0

    # 9. 验证 v3-03 AudioManager：已创建 + 注册到 @bgm 钩子
    assert window.audio_manager is not None

    # 10. 验证 v3-04 ImageRenderer：已创建 + 注册到 @bg/@char 钩子
    assert window.image_renderer is not None

    # 11. 验证 window 已关闭（ChapterEndEvt 触发）
    assert window._closed is True


# ═══════════════════════════════════════════════════════════════════════
# 2. v3-06 + v3-07 协同：BackLog 与 ReadMarks 同时累积
# ═══════════════════════════════════════════════════════════════════════


def test_v3_backlog_and_read_marks_accumulate_together(fake_pyqt6_v3):
    """同一 TextEvt → backlog.add + read_marks.mark_evt 同时触发。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from core.engine.protocol import TextEvt

    sink = PyQt6Sink()
    MainWindowCls = pyqt6_main._build_main_window_class(qt=fake_pyqt6_v3, char_delay_ms=0)
    win = MainWindowCls(sink=sink, input_sink=PyQt6InputSink())

    # 发 3 个 TextEvt
    win._handle_evt(TextEvt(content="alpha", style="narration"))
    win._handle_evt(TextEvt(content="beta", speaker="bob", style="dialog"))
    win._handle_evt(TextEvt(content="gamma", style="narration"))

    # backlog 应累积 3 条
    assert win.backlog.count == 3
    # read_marks 应标记 3 条
    assert win.read_marks.count == 3
    assert win.read_marks.is_read("alpha") is True
    assert win.read_marks.is_read("beta") is True
    assert win.read_marks.is_read("gamma") is True


# ═══════════════════════════════════════════════════════════════════════
# 3. v3-07 + v3-08 协同：Settings 应用到 AutoMode
# ═══════════════════════════════════════════════════════════════════════


def test_v3_settings_apply_to_auto_mode_on_construct(fake_pyqt6_v3, tmp_path):
    """构造时 settings.auto_delay → auto_mode.auto_delay_ms。"""
    from runtime.settings import SettingsManager
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink

    f = tmp_path / "s.json"
    f.write_text(json.dumps({"auto_delay": 3000}), encoding="utf-8")

    sink = PyQt6Sink()
    MainWindowCls = pyqt6_main._build_main_window_class(
        qt=fake_pyqt6_v3, char_delay_ms=0,
        settings_manager=SettingsManager(settings_file=f),
    )
    win = MainWindowCls(sink=sink, input_sink=PyQt6InputSink())

    assert win.auto_mode.auto_delay_ms == 3000


def test_v3_apply_settings_after_change(fake_pyqt6_v3, tmp_path):
    """apply_settings → 重新推送配置到运行时组件。"""
    from runtime.settings import SettingsManager
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink

    f = tmp_path / "s.json"
    sink = PyQt6Sink()
    MainWindowCls = pyqt6_main._build_main_window_class(
        qt=fake_pyqt6_v3, char_delay_ms=0,
        settings_manager=SettingsManager(settings_file=f),
    )
    win = MainWindowCls(sink=sink, input_sink=PyQt6InputSink())

    # 初始 text_speed=40
    assert win._text_renderer._char_delay_ms == 40

    # 改 settings 后 apply
    win.settings.set("text_speed", 15)
    win.apply_settings()
    assert win._text_renderer._char_delay_ms == 15


# ═══════════════════════════════════════════════════════════════════════
# 4. v3-07 Auto 模式端到端：Auto 开启时 TextEvt → 自动推进
# ═══════════════════════════════════════════════════════════════════════


def test_v3_auto_mode_advances_on_text_complete(fake_pyqt6_v3):
    """Auto 开启 + delay=0 → TextEvt 触发后立即 submit 空串。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from core.engine.protocol import TextEvt

    sink = PyQt6Sink()
    input_sink = PyQt6InputSink()
    MainWindowCls = pyqt6_main._build_main_window_class(qt=fake_pyqt6_v3, char_delay_ms=0)
    win = MainWindowCls(sink=sink, input_sink=input_sink)

    submitted = []
    win._input_sink.submit = lambda v: submitted.append(v)

    # 开启 Auto + delay=0
    win.auto_mode.set_auto_delay(0)
    win.auto_mode.set_auto(True)

    win._handle_evt(TextEvt(content="foo"))
    assert submitted == [""]  # 立即触发推进


def test_v3_skip_mode_skips_typewriter(fake_pyqt6_v3):
    """Skip 模式开启 → TextRenderer.render 后立即 skip。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from core.engine.protocol import TextEvt

    sink = PyQt6Sink()
    MainWindowCls = pyqt6_main._build_main_window_class(
        qt=fake_pyqt6_v3, char_delay_ms=40,  # 启用打字机
    )
    win = MainWindowCls(sink=sink, input_sink=PyQt6InputSink())

    # 开启 Skip
    win.auto_mode.set_skip(True)
    win._handle_evt(TextEvt(content="hello world"))
    # 打字机应已被 skip
    assert win._text_renderer.is_typing is False


# ═══════════════════════════════════════════════════════════════════════
# 5. v3-06 HistoryDialog 集成：show_history 返回含 backlog 的 dialog
# ═══════════════════════════════════════════════════════════════════════


def test_v3_show_history_returns_dialog_with_backlog(fake_pyqt6_v3):
    """show_history → HistoryDialog 含当前 backlog 条目。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from core.engine.protocol import TextEvt
    from runtime.gui.history_dialog import _build_history_dialog_class

    sink = PyQt6Sink()
    MainWindowCls = pyqt6_main._build_main_window_class(qt=fake_pyqt6_v3, char_delay_ms=0)
    win = MainWindowCls(sink=sink, input_sink=PyQt6InputSink())

    win._handle_evt(TextEvt(content="hello", speaker="alice"))
    win._handle_evt(TextEvt(content="world"))

    # 构造 HistoryDialog 用 fake qt
    from tests.v2_pending.test_backlog_history import (
        _FakeQDialog as BHFakeQDialog,
        _FakeQVBoxLayout as BHFakeQVBoxLayout,
        _FakeQHBoxLayout as BHFakeQHBoxLayout,
        _FakeQLabel as BHFakeQLabel,
        _FakeQPushButton as BHFakeQPushButton,
        _FakeQWidget as BHFakeQWidget,
        _FakeQScrollArea as BHFakeQScrollArea,
    )
    history_qt = {
        "QDialog": BHFakeQDialog, "QVBoxLayout": BHFakeQVBoxLayout,
        "QHBoxLayout": BHFakeQHBoxLayout, "QLabel": BHFakeQLabel,
        "QPushButton": BHFakeQPushButton, "QWidget": BHFakeQWidget,
        "QScrollArea": BHFakeQScrollArea,
    }
    dialog = win.show_history(qt_override=history_qt)
    assert dialog.entry_count == 2


# ═══════════════════════════════════════════════════════════════════════
# 6. v3-08 SettingsDialog 集成：show_settings 返回含当前值的 dialog
# ═══════════════════════════════════════════════════════════════════════


def test_v3_show_settings_returns_dialog_with_current_values(fake_pyqt6_v3, tmp_path):
    """show_settings → SettingsDialog 含当前 settings 值。"""
    from runtime.settings import SettingsManager
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink

    f = tmp_path / "s.json"
    f.write_text(json.dumps({"text_speed": 25, "auto_delay": 800}), encoding="utf-8")

    sink = PyQt6Sink()
    MainWindowCls = pyqt6_main._build_main_window_class(
        qt=fake_pyqt6_v3, char_delay_ms=0,
        settings_manager=SettingsManager(settings_file=f),
    )
    win = MainWindowCls(sink=sink, input_sink=PyQt6InputSink())

    # 用 SettingsDialog 测试的 fake qt
    from tests.v2_pending.test_settings import (
        FakeQDialogS, FakeQVBoxLayoutS, FakeQHBoxLayoutS, FakeQFormLayoutS,
        FakeQLabelS, FakeQPushButtonS, FakeQWidgetS,
        FakeQSpinBoxS, FakeQDoubleSpinBoxS, FakeQCheckBoxS,
    )
    settings_qt = {
        "QDialog": FakeQDialogS, "QVBoxLayout": FakeQVBoxLayoutS,
        "QHBoxLayout": FakeQHBoxLayoutS, "QFormLayout": FakeQFormLayoutS,
        "QLabel": FakeQLabelS, "QPushButton": FakeQPushButtonS,
        "QWidget": FakeQWidgetS, "QSpinBox": FakeQSpinBoxS,
        "QDoubleSpinBox": FakeQDoubleSpinBoxS, "QCheckBox": FakeQCheckBoxS,
    }
    dialog = win.show_settings(qt_override=settings_qt)
    s = dialog.get_settings()
    assert s["text_speed"] == 25
    assert s["auto_delay"] == 800


# ═══════════════════════════════════════════════════════════════════════
# 7. v3-08 Settings 持久化 roundtrip：save → 重启 → load
# ═══════════════════════════════════════════════════════════════════════


def test_v3_settings_persist_across_sessions(fake_pyqt6_v3, tmp_path):
    """settings save → 新 MainWindow 加载同文件 → 配置一致。"""
    from runtime.settings import SettingsManager
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink

    f = tmp_path / "s.json"

    # 第一次：构造 + 改配置 + 保存
    sink1 = PyQt6Sink()
    MainWindowCls1 = pyqt6_main._build_main_window_class(
        qt=fake_pyqt6_v3, char_delay_ms=0,
        settings_manager=SettingsManager(settings_file=f),
    )
    win1 = MainWindowCls1(sink=sink1, input_sink=PyQt6InputSink())
    win1.settings.set("text_speed", 12)
    win1.settings.set("auto_delay", 999)
    win1.settings.save()
    win1.close()

    # 第二次：新 MainWindow 加载同文件
    sink2 = PyQt6Sink()
    MainWindowCls2 = pyqt6_main._build_main_window_class(
        qt=fake_pyqt6_v3, char_delay_ms=0,
        settings_manager=SettingsManager(settings_file=f),
    )
    win2 = MainWindowCls2(sink=sink2, input_sink=PyQt6InputSink())

    # 配置应一致
    assert win2.settings.get("text_speed") == 12
    assert win2.settings.get("auto_delay") == 999
    # 已应用到 text_renderer
    assert win2._text_renderer._char_delay_ms == 12
    # 已应用到 auto_mode
    assert win2.auto_mode.auto_delay_ms == 999


# ═══════════════════════════════════════════════════════════════════════
# 8. v3-05 存档截图 + v3-06 BackLog 协同：存档时含 backlog 状态
# ═══════════════════════════════════════════════════════════════════════


def test_v3_save_with_screenshot_and_backlog_independent(fake_pyqt6_v3, tmp_path):
    """存档截图（PNG bytes）与 backlog 累积独立工作。"""
    from runtime.save import SaveManager
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from core.engine.protocol import TextEvt
    from core.engine.executor import GameState

    save_dir = tmp_path / "saves"
    mgr = SaveManager(save_dir=save_dir)

    sink = PyQt6Sink()
    MainWindowCls = pyqt6_main._build_main_window_class(qt=fake_pyqt6_v3, char_delay_ms=0)
    win = MainWindowCls(sink=sink, input_sink=PyQt6InputSink())

    # 累积几条文本
    win._handle_evt(TextEvt(content="foo"))
    win._handle_evt(TextEvt(content="bar"))
    assert win.backlog.count == 2

    # 模拟存档（含假截图 bytes）
    state = GameState()
    state.vars["mood"] = "平静"
    fake_screenshot = b"\x89PNG\r\n\x1a\nfake_png_bytes"
    mgr.save("01", state, screenshot=fake_screenshot)

    # 验证：截图 + JSON 都写入
    assert (save_dir / "01.json").exists()
    assert (save_dir / "01.png").exists()
    assert mgr.get_screenshot("01") == fake_screenshot

    # backlog 不受存档影响（独立内存状态）
    assert win.backlog.count == 2


# ═══════════════════════════════════════════════════════════════════════
# 9. v3 全组件 close 清理：关闭时无 leak
# ═══════════════════════════════════════════════════════════════════════


def test_v3_close_resets_all_runtime_state(fake_pyqt6_v3):
    """close → 清理 audio_manager / image_renderer / auto_mode 状态。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink

    sink = PyQt6Sink()
    MainWindowCls = pyqt6_main._build_main_window_class(qt=fake_pyqt6_v3, char_delay_ms=0)
    win = MainWindowCls(sink=sink, input_sink=PyQt6InputSink())

    # 开启 Auto/Skip
    win.auto_mode.set_auto(True)
    win.auto_mode.set_skip(True)

    win.close()

    # close 后 auto_mode 应被 reset
    assert win.auto_mode.auto_mode is False
    assert win.auto_mode.skip_mode is False
    # window 标记关闭
    assert win._closed is True


# ═══════════════════════════════════════════════════════════════════════
# 10. v3 完整功能清单：所有 property 都可访问
# ═══════════════════════════════════════════════════════════════════════


def test_v3_main_window_exposes_all_v3_components(fake_pyqt6_v3):
    """MainWindow 暴露所有 v3 组件 property（v3-01 ~ v3-08）。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink

    sink = PyQt6Sink()
    MainWindowCls = pyqt6_main._build_main_window_class(qt=fake_pyqt6_v3, char_delay_ms=0)
    win = MainWindowCls(sink=sink, input_sink=PyQt6InputSink())

    # v3-01 TextRenderer（通过 _text_renderer 访问）
    assert win._text_renderer is not None
    # v3-02 OptionsPanel（通过 _options_panel 访问）
    assert win._options_panel is not None
    # v3-03 AudioManager
    assert win.audio_manager is not None
    # v3-04 ImageRenderer
    assert win.image_renderer is not None
    # v3-06 BackLog
    assert win.backlog is not None
    # v3-07 ReadMarks + AutoModeController
    assert win.read_marks is not None
    assert win.auto_mode is not None
    # v3-08 SettingsManager
    assert win.settings is not None

    # 公开方法
    assert callable(getattr(win, "show_history", None))
    assert callable(getattr(win, "show_settings", None))
    assert callable(getattr(win, "apply_settings", None))


# ═══════════════════════════════════════════════════════════════════════
# 11. v3 模块独立性：所有新模块可独立 import（无 PyQt6）
# ═══════════════════════════════════════════════════════════════════════


def test_v3_all_modules_import_without_pyqt6():
    """v3 新增模块都能在无 PyQt6 环境下 import。"""
    for k in list(sys.modules):
        if k.startswith("PyQt6"):
            sys.modules.pop(k, None)
    sys.modules["PyQt6"] = None  # type: ignore

    try:
        # 纯 Python 模块
        from runtime.gui.backlog import BackLog
        from runtime.gui.read_marks import ReadMarks
        from runtime.gui.auto_mode import AutoModeController
        from runtime.settings import SettingsManager
        # 工厂模块（顶层不 import PyQt6）
        from runtime.gui.text_renderer import TextRenderer
        from runtime.gui.options_panel import OptionsPanel
        from runtime.gui.image_renderer import ImageRenderer
        from runtime.gui.screenshot import ScreenshotManager
        from runtime.gui.history_dialog import _build_history_dialog_class
        from runtime.gui.save_slot_dialog import _build_save_slot_dialog_class
        from runtime.gui.settings_dialog import _build_settings_dialog_class

        assert BackLog is not None
        assert ReadMarks is not None
        assert AutoModeController is not None
        assert SettingsManager is not None
        assert TextRenderer is not None
        assert OptionsPanel is not None
        assert ImageRenderer is not None
        assert ScreenshotManager is not None
        assert _build_history_dialog_class is not None
        assert _build_save_slot_dialog_class is not None
        assert _build_settings_dialog_class is not None
    finally:
        sys.modules.pop("PyQt6", None)
