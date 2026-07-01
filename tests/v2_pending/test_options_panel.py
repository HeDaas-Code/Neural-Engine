"""v3-02 · OptionsPanel + PromptInputEvt.options 测试（#92）。

验证 issue #92 验收点：
- PromptInputEvt 扩展 options 字段
- OptionsPanel 组件：动态生成按钮
- 选项点击 → UserInputCmd(value=索引+1)
- 无 options 降级 QLineEdit（向后兼容）
- DSL 语法 `node in → pick [开门, 不开门]` 解析
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")

from core.engine.protocol import PromptInputEvt, UserInputCmd
from core.engine.ast_nodes import In
from runtime.gui.options_panel import OptionsPanel


# ─── Fake 组件 ──────────────────────────────────────────────────────────────


class FakeSignal:
    def __init__(self):
        self._slots = []
    def connect(self, slot):
        self._slots.append(slot)
    def emit(self, *a, **kw):
        for s in self._slots:
            s(*a, **kw)


class FakeQPushButton:
    """记录 clicked 信号 + text，便于测试触发点击。"""
    def __init__(self, text="", parent=None):
        self._text = text
        self._parent = parent
        self.clicked = FakeSignal()
        self._visible = True

    def text(self):
        return self._text

    def setParent(self, p):
        self._parent = p

    def deleteLater(self):
        pass

    def setVisible(self, v):
        self._visible = v


class FakeLayout:
    def __init__(self):
        self._widgets = []
    def addWidget(self, w):
        self._widgets.append(w)


class FakeInputSink:
    """记录所有 submit 调用。"""
    def __init__(self):
        self.calls = []
    def submit(self, value):
        self.calls.append(value)


# ─── 1. PromptInputEvt.options 协议扩展 ─────────────────────────────────────


class TestPromptInputEvtOptions:
    def test_default_options_empty(self):
        evt = PromptInputEvt(var="pick")
        assert evt.options == ()

    def test_with_options(self):
        evt = PromptInputEvt(var="pick", options=("开门", "不开门"))
        assert evt.options == ("开门", "不开门")

    def test_to_dict_omits_empty_options(self):
        evt = PromptInputEvt(var="pick")
        d = evt.to_dict()
        assert "options" not in d

    def test_to_dict_includes_options(self):
        evt = PromptInputEvt(var="pick", options=("开门", "不开门"))
        d = evt.to_dict()
        assert d["options"] == ["开门", "不开门"]

    def test_from_dict_default_options(self):
        d = {"event": "prompt_input", "var": "pick"}
        evt = PromptInputEvt.from_dict(d)
        assert evt.options == ()

    def test_from_dict_with_options(self):
        d = {"event": "prompt_input", "var": "pick", "options": ["开门", "不开门"]}
        evt = PromptInputEvt.from_dict(d)
        assert evt.options == ("开门", "不开门")

    def test_round_trip(self):
        evt = PromptInputEvt(var="pick", options=("A", "B", "C"))
        d = evt.to_dict()
        evt2 = PromptInputEvt.from_dict(d)
        assert evt == evt2

    def test_from_dict_rejects_non_list_options(self):
        with pytest.raises(ValueError, match="options 应为 list"):
            PromptInputEvt.from_dict({"event": "prompt_input", "var": "x", "options": "not-a-list"})


# ─── 2. In AST 节点 options 字段 ────────────────────────────────────────────


class TestInAstOptions:
    def test_in_default_no_options(self):
        node = In(var="pick")
        assert node.options == ()

    def test_in_with_options(self):
        node = In(var="pick", options=("开门", "不开门"))
        assert node.options == ("开门", "不开门")


# ─── 3. DSL 解析：node in → pick [开门, 不开门] ─────────────────────────────


class TestParseInWithOptions:
    def test_parse_in_with_arrow_and_options(self):
        from core.engine.interpreter import _parse_body_line
        node = _parse_body_line("node in → pick [开门, 不开门]", lineno=1)
        assert isinstance(node, In)
        assert node.var == "pick"
        assert node.options == ("开门", "不开门")

    def test_parse_in_with_dash_arrow_and_options(self):
        from core.engine.interpreter import _parse_body_line
        node = _parse_body_line("node in -> pick [开门, 不开门]", lineno=1)
        assert isinstance(node, In)
        assert node.var == "pick"
        assert node.options == ("开门", "不开门")

    def test_parse_in_without_options_backward_compat(self):
        from core.engine.interpreter import _parse_body_line
        node = _parse_body_line("node in → mood", lineno=1)
        assert isinstance(node, In)
        assert node.var == "mood"
        assert node.options == ()

    def test_parse_in_single_option(self):
        from core.engine.interpreter import _parse_body_line
        node = _parse_body_line("node in → pick [是]", lineno=1)
        assert node.options == ("是",)

    def test_parse_in_options_with_spaces(self):
        from core.engine.interpreter import _parse_body_line
        # 选项内含空格
        node = _parse_body_line("node in → pick [打开门, 不开门]", lineno=1)
        assert node.options == ("打开门", "不开门")

    def test_parse_in_empty_options_raises(self):
        from core.engine.interpreter import _parse_body_line
        from core.engine.ast_nodes import ParserError
        with pytest.raises(ParserError, match="empty options"):
            _parse_body_line("node in → pick [ ]", lineno=1)


# ─── 4. OptionsPanel 组件 ───────────────────────────────────────────────────


class TestOptionsPanel:
    def test_set_options_creates_buttons(self):
        parent = MagicMock()
        layout = FakeLayout()
        input_sink = FakeInputSink()
        qt = {"QPushButton": FakeQPushButton}
        panel = OptionsPanel(parent, layout, input_sink, qt=qt)

        result = panel.set_options(["开门", "不开门"])
        assert result is True
        assert panel.button_count == 2
        assert len(layout._widgets) == 2
        # 按钮文本正确
        assert layout._widgets[0].text() == "开门"
        assert layout._widgets[1].text() == "不开门"

    def test_set_empty_options_returns_false(self):
        panel = OptionsPanel(MagicMock(), FakeLayout(), FakeInputSink(), qt={"QPushButton": FakeQPushButton})
        assert panel.set_options([]) is False
        assert panel.button_count == 0

    def test_button_click_submits_one_based_index(self):
        """点击第 1 个按钮 → submit('1')；第 2 个 → submit('2')。"""
        parent = MagicMock()
        layout = FakeLayout()
        input_sink = FakeInputSink()
        qt = {"QPushButton": FakeQPushButton}
        panel = OptionsPanel(parent, layout, input_sink, qt=qt)
        panel.set_options(["开门", "不开门"])

        # 点击第 1 个按钮（模拟 clicked.emit）
        layout._widgets[0].clicked.emit()
        assert input_sink.calls == ["1"]

        # 点击第 2 个
        layout._widgets[1].clicked.emit()
        assert input_sink.calls == ["1", "2"]

    def test_clear_removes_buttons(self):
        layout = FakeLayout()
        qt = {"QPushButton": FakeQPushButton}
        panel = OptionsPanel(MagicMock(), layout, FakeInputSink(), qt=qt)
        panel.set_options(["A", "B", "C"])
        assert panel.button_count == 3

        panel.clear()
        assert panel.button_count == 0

    def test_set_options_replaces_previous(self):
        """多次 set_options 应替换上一组按钮。"""
        layout = FakeLayout()
        qt = {"QPushButton": FakeQPushButton}
        panel = OptionsPanel(MagicMock(), layout, FakeInputSink(), qt=qt)
        panel.set_options(["A", "B"])
        assert panel.button_count == 2

        panel.set_options(["X", "Y", "Z"])
        assert panel.button_count == 3
        assert layout._widgets[-1].text() == "Z"

    def test_fallback_no_qpushbutton_records_options(self):
        """qt dict 无 QPushButton key → fallback 记录 options（测试断言路径）。"""
        panel = OptionsPanel(MagicMock(), FakeLayout(), FakeInputSink(), qt={})
        result = panel.set_options(["A", "B"])
        assert result is True
        assert panel.button_count == 2  # fallback 记录为 list


# ─── 5. 端到端：options 点击 → UserInputCmd ──────────────────────────────────


class TestOptionsEndToEnd:
    def test_click_option_produces_correct_value_for_if_branch(self):
        """模拟 chapter01_v1 的 pick==1 分支：点击"选项1"应 submit('1')。"""
        from runtime.gui.pyqt6_input import PyQt6InputSink
        layout = FakeLayout()
        qt = {"QPushButton": FakeQPushButton}
        # 用真 PyQt6InputSink（不依赖 Qt）
        input_sink = PyQt6InputSink()
        panel = OptionsPanel(MagicMock(), layout, input_sink, qt=qt)
        panel.set_options(["开门", "不开门"])

        # 点击选项 1
        layout._widgets[0].clicked.emit()

        # 取出 UserInputCmd
        cmd = input_sink.get_cmd()
        assert isinstance(cmd, UserInputCmd)
        assert cmd.value == "1"  # 对应 node if pick == 1 分支
