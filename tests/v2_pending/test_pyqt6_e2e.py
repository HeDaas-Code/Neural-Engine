"""v2-p0 · PyQt6 GUI 端到端集成测试（chapter01_v1.md）。

按 PDR §5.1.3 验收：
- `chapters/chapter01_v1.md` 加载 → Executor.run() → PyQt6Sink 接收事件 → MainWindow 更新 UI
- 用户输入 → PyQt6InputSink → Executor.get_cmd() → 走剧情分支
- 装饰器钩子被触发（@style + @bgm）

测试用 fake PyQt6（PyQt6 未装环境），验证完整事件-输入闭环。
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))


# ─── Fake Qt Widgets（复用 test_pyqt6_main.py 的 fake）─────────────────────


class FakeSignal:
    def __init__(self):
        self._slots: list = []

    def connect(self, slot):
        self._slots.append(slot)

    def emit(self, *args, **kwargs):
        for slot in self._slots:
            slot(*args, **kwargs)


class FakeQMainWindow:
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

    def setReadOnly(self, ro):
        pass

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

    def setFocus(self):
        pass


class FakeQPushButton:
    def __init__(self, text="", *args, **kwargs):
        self._text = text
        self.clicked = FakeSignal()


class FakeQWidget:
    def __init__(self, *args, **kwargs):
        pass


class FakeQVBoxLayout:
    def __init__(self, *args, **kwargs):
        self._widgets: list = []

    def addWidget(self, widget):
        self._widgets.append(widget)


class FakeQApplication:
    _instance = None

    def __init__(self, argv):
        FakeQApplication._instance = self

    def exec(self):
        return 0

    @classmethod
    def instance(cls):
        return cls._instance


@pytest.fixture
def fake_pyqt6(monkeypatch):
    """注入 fake PyQt6 modules 到 sys.modules。"""
    qtcore = types.ModuleType("PyQt6.QtCore")
    qtcore.Qt = MagicMock()
    qtcore.QThread = MagicMock()
    qtcore.QObject = MagicMock()
    qtcore.pyqtSignal = MagicMock(return_value=FakeSignal())

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


@pytest.fixture(autouse=True)
def _reset_decorator_registry():
    """每个测试前后清空 core.decorators registry + style/bgm 状态。"""
    from core.decorators import clear
    from core.decorators import style as style_mod
    from core.decorators import bgm as bgm_mod
    clear()
    style_mod.reset_last_style()
    bgm_mod.reset_last_bgm()
    yield
    clear()
    style_mod.reset_last_style()
    bgm_mod.reset_last_bgm()


# ─── 1. 集成：chapter01_v1.md → GUI 全流程 ────────────────────────────────


def test_pyqt6_e2e_chapter01_v1_full_flow(fake_pyqt6):
    """chapter01_v1.md → PyQt6 GUI 端到端流程：
    - 加载章节（_load_story）
    - 启动 Executor + PyQt6Sink + PyQt6InputSink + MainWindow
    - 预填 cmd queue：用户输入 "平静"（mood）+ "1"（pick → ca 分支）
    - Executor 顺序消费 → 走完剧情
    - 验证：display 文本 + window.close() + 装饰器钩子触发
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

    # 3. 构造 PyQt6Sink + PyQt6InputSink
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from runtime.gui import pyqt6_main

    sink = PyQt6Sink()
    input_sink = PyQt6InputSink()

    # 4. 预填 cmd queue（剧情需要 2 个输入：mood + pick）
    input_sink.submit("平静")  # 第一个 node in → mood
    input_sink.submit("1")     # 第二个 node in → pick

    # 5. cmd_source 绑定到 input_sink.drain_cmd（同步非阻塞消费）
    sink._cmd_source = input_sink.drain_cmd

    # 6. 构造 MainWindow（构造时 sink._evt_handler 被绑定）
    MainWindowCls = pyqt6_main._build_main_window_class()
    window = MainWindowCls(sink=sink, input_sink=input_sink)

    # 7. 跑 Executor
    from core.engine.executor import Executor
    exe = Executor(story, sink)
    exe.run()

    # 8. 验证：display 显示完整剧情文本
    display_text = window.display.toPlainText()

    # start 块：3 行文本
    assert "雨夜。" in display_text
    assert "雨声从破旧窗户的缝隙中渗入。" in display_text
    assert "你坐在窗边，听着雨声。" in display_text

    # echo 节点拼接："平静" + "，是啊。" → "平静，是啊。"
    # 实际 chapter01_v1.md 第 15 行是 "node echo mood + ，是啊。"
    # Echo 节点 parts = ("p_mood", "，是啊。") → "平静，是啊。"
    assert "，是啊。" in display_text

    # c1 块（跳转后）
    assert "你听到门外传来两声敲门。" in display_text

    # ca 分支（if pick == 1 → t_a → ca）
    assert "你打开门，雨中站着一个人。" in display_text
    # cb 分支不应出现
    assert "你没有开门" not in display_text

    # 9. 验证：window 已关闭（ChapterEndEvt 触发）
    assert window._closed is True

    # 10. 验证：装饰器钩子触发
    # @style bgm:rain.mp3 → _LAST_STYLE["bgm"] = "rain.mp3"
    # @style bgm:storm.mp3 → _LAST_STYLE["bgm"] = "storm.mp3"（覆盖）
    style_state = style_mod.get_last_style()
    assert style_state.get("bgm") == "storm.mp3"

    # @bgm 是 chapter01 里没有直接用，但通过 @style bgm:rain.mp3 触发？
    # 实际 chapter01_v1.md 只有 @style，没有 @bgm。
    # 所以 _LAST_BGM 应该是空的。
    assert bgm_mod.get_last_bgm() == []


def test_pyqt6_e2e_chapter01_v1_pick_2_goes_to_cb(fake_pyqt6):
    """用户输入 "2" → if pick == 1 不匹配 → 走 t_b → cb 分支。

    注意：chapter01_v1.md `node if pick == 1 [t_a, t_b]` 是 EXPR_KIND（值匹配）。
    if pick == 1: state.vars["pick"] = 2，1 不匹配 → 选 t_b → cb 块。
    """
    from core.engine.main import _load_story
    from core.decorators import style as style_mod
    style_mod.install()

    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from runtime.gui import pyqt6_main

    chapter_path = REPO_ROOT / "chapters" / "chapter01_v1.md"
    story = _load_story(str(chapter_path))

    sink = PyQt6Sink()
    input_sink = PyQt6InputSink()
    # mood = "平静"，pick = "2" → cb 分支
    input_sink.submit("平静")
    input_sink.submit("2")
    sink._cmd_source = input_sink.drain_cmd

    MainWindowCls = pyqt6_main._build_main_window_class()
    window = MainWindowCls(sink=sink, input_sink=input_sink)

    from core.engine.executor import Executor
    exe = Executor(story, sink)
    exe.run()

    display_text = window.display.toPlainText()

    # cb 分支
    assert "你没有开门。雨声渐小。" in display_text
    # ca 分支不应出现
    assert "你打开门，雨中站着一个人。" not in display_text
    # window 已关闭
    assert window._closed is True

    # @style bgm（cb 第 44 行 `@style bgm` 无冒号 arg）—— v2 静默忽略
    style_state = style_mod.get_last_style()
    # cb 块第 44 行 `@style bgm` 无冒号 → 不修改 _LAST_STYLE
    # 但 ca 没走到，所以 storm.mp3 不在
    assert "storm" not in style_state.get("bgm", "")


def test_pyqt6_e2e_event_sequence_dispatches_to_main_window(fake_pyqt6):
    """事件序列：TextEvt → PromptInputEvt → TextEvt → ... → ChapterEndEvt
    都正确通过 sink → MainWindow → UI 更新。
    """
    from core.engine.main import _load_story

    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from runtime.gui import pyqt6_main

    chapter_path = REPO_ROOT / "chapters" / "chapter01_v1.md"
    story = _load_story(str(chapter_path))

    sink = PyQt6Sink()
    input_sink = PyQt6InputSink()
    input_sink.submit("平静")
    input_sink.submit("1")
    sink._cmd_source = input_sink.drain_cmd

    MainWindowCls = pyqt6_main._build_main_window_class()
    window = MainWindowCls(sink=sink, input_sink=input_sink)

    # 收集所有经过 sink 的 evt（用 fake handler 替换 + 收集）
    received: list = []
    original_handler = sink._evt_handler
    def collector(evt):
        received.append(evt)
        original_handler(evt)  # 仍然调 UI 更新
    sink._evt_handler = collector

    from core.engine.executor import Executor
    exe = Executor(story, sink)
    exe.run()

    # 验证事件序列
    types = [type(e).__name__ for e in received]

    # 至少有：3 个 TextEvt（雨夜/雨声/坐在窗边）+ DecoratorEvt(@style bgm:rain) +
    #         PromptInputEvt(mood) + TextEvt(echo 拼接) +
    #         TextEvt(敲门) + PromptInputEvt(pick) +
    #         DecoratorEvt(@style bgm:storm) + TextEvt(打开门) + ChapterEndEvt
    assert "TextEvt" in types
    assert "PromptInputEvt" in types
    assert "DecoratorEvt" in types
    assert "ChapterEndEvt" in types

    # window 应已关闭
    assert window._closed is True


# ─── 2. 单独验证：MainWindow 接收各 evt 类型 ────────────────────────────────


def test_pyqt6_main_window_displays_multiple_text_evts(fake_pyqt6):
    """MainWindow 接收多个 TextEvt → display 累积显示。"""
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from runtime.gui import pyqt6_main
    from core.engine.protocol import TextEvt

    sink = PyQt6Sink()
    MainWindowCls = pyqt6_main._build_main_window_class()
    win = MainWindowCls(sink=sink, input_sink=PyQt6InputSink())

    sink.put_evt(TextEvt(content="第一行。\n", style="narration"))
    sink.put_evt(TextEvt(content="第二行。\n", style="narration"))
    sink.put_evt(TextEvt(content="第三行。\n", style="narration"))

    text = win.display.toPlainText()
    assert "第一行。" in text
    assert "第二行。" in text
    assert "第三行。" in text


def test_pyqt6_main_window_decorator_evt_triggers_installed_hooks(fake_pyqt6):
    """MainWindow 接收 DecoratorEvt → 自动触发已安装的装饰器钩子（无需手动 dispatch）。"""
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from runtime.gui import pyqt6_main
    from core.engine.protocol import DecoratorEvt
    from core.decorators import style as style_mod
    from core.decorators import bgm as bgm_mod

    style_mod.install()
    bgm_mod.install()

    sink = PyQt6Sink()
    MainWindowCls = pyqt6_main._build_main_window_class()
    MainWindowCls(sink=sink, input_sink=PyQt6InputSink())

    sink.put_evt(DecoratorEvt(name="style", args=["color:red", "size:14"]))
    sink.put_evt(DecoratorEvt(name="bgm", args=["rain.mp3"]))

    assert style_mod.get_last_style() == {"color": "red", "size": "14"}
    assert bgm_mod.get_last_bgm() == [("play", "rain.mp3")]
