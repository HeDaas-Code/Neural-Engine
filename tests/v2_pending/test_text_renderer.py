"""v3-01 · TextRenderer + 对话框 UI 测试（#91）。

验证 issue #91 验收点：
- TextRenderer 类：接收 TextEvt → 富文本渲染
- 打字机效果：逐字显示（用 char_delay_ms=0 关闭真 QTimer，测同步路径）
- 名字标签：speaker 字段 → 名字 + 对话
- @style 应用：color/font/size 应用到 display
- 点击/空格跳过打字机动画（is_typing + skip）
- 打字机进行中禁用输入框

测试策略：
- char_delay_ms=0 → 关闭打字机，直接 append 全文 HTML（同步可断言）
- char_delay_ms>0 + 无 QTimer 注入 → fallback 直接显示全文（测 fallback 路径）
- 真 QTimer 路径由 v3-09 集成测试覆盖（需 Qt 事件循环）
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")

from core.engine.protocol import TextEvt, DecoratorEvt
from runtime.gui.text_renderer import (
    TextRenderer, DEFAULT_CHAR_DELAY_MS,
    _build_html, _build_style_css,
)


# ─── Fake QTextEdit（增强版，支持 insertPlainText/setStyleSheet/mousePressEvent）───


class FakeDisplay:
    """Fake QTextEdit —— 记录所有调用。"""
    def __init__(self):
        self.text = ""
        self.style_sheet = ""
        self.append_calls: list[str] = []
        self.insert_calls: list[str] = []
        self.mousePressEvent = None  # MainWindow 会覆盖

    def append(self, text):
        self.text += text
        self.append_calls.append(text)

    def insertPlainText(self, text):
        self.text += text
        self.insert_calls.append(text)

    def setStyleSheet(self, css):
        self.style_sheet = css

    def toPlainText(self):
        return self.text

    def setReadOnly(self, ro):
        pass


# ─── 1. _build_html 单元测试 ────────────────────────────────────────────────


class TestBuildHtml:
    def test_narration_no_speaker(self):
        html = _build_html("雨夜。", "")
        assert html == "<p>雨夜。</p>"

    def test_with_speaker(self):
        html = _build_html("你好。", "Alice")
        assert "<b>Alice</b>" in html
        assert "你好。" in html

    def test_html_escape(self):
        html = _build_html("<script>x</script>", "")
        assert "<script>" not in html  # 应被转义
        assert "&lt;script&gt;" in html


# ─── 2. _build_style_css 单元测试 ───────────────────────────────────────────


class TestBuildStyleCss:
    def test_empty_style(self):
        assert _build_style_css({}) == ""

    def test_color_only(self):
        css = _build_style_css({"color": "red"})
        assert "color: red" in css

    def test_font_and_size(self):
        css = _build_style_css({"font": "Arial", "size": "14"})
        assert "font-family: Arial" in css
        assert "font-size: 14px" in css

    def test_size_non_numeric(self):
        css = _build_style_css({"size": "large"})
        assert "font-size: large" in css


# ─── 3. TextRenderer 无打字机模式（char_delay_ms=0）────────────────────────


class TestTextRendererNoTyping:
    def test_render_narration_appends_html(self):
        display = FakeDisplay()
        r = TextRenderer(display, char_delay_ms=0)
        r.render(TextEvt(content="雨夜。", speaker=""))
        assert "雨夜。" in display.text
        assert not r.is_typing

    def test_render_with_speaker(self):
        display = FakeDisplay()
        r = TextRenderer(display, char_delay_ms=0)
        r.render(TextEvt(content="你好。", speaker="Alice"))
        assert "Alice" in display.text
        assert "你好。" in display.text

    def test_render_empty_content_no_crash(self):
        display = FakeDisplay()
        r = TextRenderer(display, char_delay_ms=0)
        r.render(TextEvt(content="", speaker=""))
        # 空 content 不应崩
        assert not r.is_typing


# ─── 4. TextRenderer 打字机 fallback（无 QTimer 注入）──────────────────────


class TestTextRendererTypingFallback:
    def test_typing_fallback_no_qtimer_shows_full_text(self):
        """char_delay_ms>0 但无 QTimer → fallback 直接显示全文。"""
        display = FakeDisplay()
        # qt=None 且 PyQt6 未装 → _get_qtimer 返回 None → fallback
        r = TextRenderer(display, char_delay_ms=40, qt={})  # qt dict 无 QTimer key
        r.render(TextEvt(content="雨夜。", speaker=""))
        # fallback 路径：直接 insertPlainText 全文
        assert "雨夜。" in display.text
        assert not r.is_typing


# ─── 5. TextRenderer apply_style ────────────────────────────────────────────


class TestTextRendererApplyStyle:
    def test_apply_color_sets_stylesheet(self):
        display = FakeDisplay()
        r = TextRenderer(display, char_delay_ms=0)
        r.apply_style({"color": "red"})
        assert "color: red" in display.style_sheet

    def test_apply_empty_style_clears_stylesheet(self):
        display = FakeDisplay()
        display.style_sheet = "color: red"
        r = TextRenderer(display, char_delay_ms=0)
        r.apply_style({})
        assert display.style_sheet == ""

    def test_apply_font_size(self):
        display = FakeDisplay()
        r = TextRenderer(display, char_delay_ms=0)
        r.apply_style({"font": "Arial", "size": "16"})
        assert "font-family: Arial" in display.style_sheet
        assert "font-size: 16px" in display.style_sheet


# ─── 6. TextRenderer skip 行为 ──────────────────────────────────────────────


class TestTextRendererSkip:
    def test_skip_when_not_typing_is_noop(self):
        display = FakeDisplay()
        r = TextRenderer(display, char_delay_ms=0)
        r.skip()  # 不在打字机中，no-op
        assert display.text == ""

    def test_skip_shows_remaining_text(self):
        """模拟打字机进行中：手动设 _pending 状态后 skip。"""
        display = FakeDisplay()
        r = TextRenderer(display, char_delay_ms=40, qt={})
        # 手动构造打字机进行中状态（绕过 QTimer）
        r._pending_plain = "雨夜。"
        r._shown_chars = 1  # 已显示 1 字
        r._timer = object()  # 假装 timer 在跑
        r.skip()
        # 剩余 "夜。" 应被显示
        assert "夜。" in display.text
        assert not r.is_typing


# ─── 7. DEFAULT_CHAR_DELAY_MS 常量 ──────────────────────────────────────────


def test_default_char_delay_ms_is_positive():
    """默认打字机速度应 >0（验收：打字机效果开启）。"""
    assert DEFAULT_CHAR_DELAY_MS > 0
    assert DEFAULT_CHAR_DELAY_MS == 40


# ─── 8. TextEvt speaker 字段（v3-01 协议扩展）──────────────────────────────


class TestTextEvtSpeaker:
    def test_textevt_default_speaker_empty(self):
        evt = TextEvt(content="雨夜。")
        assert evt.speaker == ""

    def test_textevt_with_speaker(self):
        evt = TextEvt(content="你好。", speaker="Alice")
        assert evt.speaker == "Alice"

    def test_textevt_to_dict_omits_empty_speaker(self):
        """空 speaker 不序列化（向后兼容老协议）。"""
        evt = TextEvt(content="雨夜。")
        d = evt.to_dict()
        assert "speaker" not in d

    def test_textevt_to_dict_includes_speaker(self):
        evt = TextEvt(content="你好。", speaker="Alice")
        d = evt.to_dict()
        assert d["speaker"] == "Alice"

    def test_textevt_from_dict_default_speaker(self):
        """老协议无 speaker 字段 → from_dict 默认空串。"""
        d = {"event": "text", "content": "雨夜。", "style": "narration"}
        evt = TextEvt.from_dict(d)
        assert evt.speaker == ""

    def test_textevt_from_dict_with_speaker(self):
        d = {"event": "text", "content": "你好。", "style": "dialogue", "speaker": "Alice"}
        evt = TextEvt.from_dict(d)
        assert evt.speaker == "Alice"

    def test_textevt_round_trip(self):
        evt = TextEvt(content="你好。", speaker="Bob")
        d = evt.to_dict()
        evt2 = TextEvt.from_dict(d)
        assert evt == evt2


# ─── 9. DecoratorEvt @style → TextRenderer 集成（用真 style 钩子）──────────


class TestStyleDecoratorIntegration:
    def test_style_decorator_updates_last_style(self):
        """@style color:red 装饰器应更新 style 钩子的 _LAST_STYLE。"""
        from core.decorators.style import handle, get_last_style, reset_last_style
        reset_last_style()
        evt = DecoratorEvt(name="style", args=["color:red", "size:16"], kind="call")
        handle(evt)
        style = get_last_style()
        assert style["color"] == "red"
        assert style["size"] == "16"
        reset_last_style()

    def test_renderer_reads_last_style(self):
        """TextRenderer.apply_style 应能消费 get_last_style() 的返回值。"""
        from core.decorators.style import handle, get_last_style, reset_last_style
        reset_last_style()
        handle(DecoratorEvt(name="style", args=["color:blue"], kind="call"))
        display = FakeDisplay()
        r = TextRenderer(display, char_delay_ms=0)
        r.apply_style(get_last_style())
        assert "color: blue" in display.style_sheet
        reset_last_style()
