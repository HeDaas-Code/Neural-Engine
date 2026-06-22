"""v0-issue-4 事件 schema dataclass 测试。

按 issue #26 acceptance criteria 验证 6 条事件（Engine→GUI）的 round-trip
+ parse_evt 分发 + 错误处理。
"""
import sys

import pytest

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")


# 1. TextEvt round-trip 默认 style
def test_text_evt_round_trip_with_default_style():
    from core.engine.protocol import TextEvt

    evt = TextEvt(content="雨夜。")
    d = evt.to_dict()
    assert d == {"event": "text", "content": "雨夜。", "style": "narration"}

    restored = TextEvt.from_dict(d)
    assert restored == evt


# 2. TextEvt round-trip 显式 style
def test_text_evt_round_trip_with_explicit_style():
    from core.engine.protocol import TextEvt

    evt = TextEvt(content="敲门声。", style="dialogue")
    d = evt.to_dict()
    assert d["style"] == "dialogue"

    restored = TextEvt.from_dict(d)
    assert restored.style == "dialogue"


# 3. PromptInputEvt round-trip
def test_prompt_input_evt_round_trip():
    from core.engine.protocol import PromptInputEvt

    evt = PromptInputEvt(var="p_mood")
    d = evt.to_dict()
    assert d == {"event": "prompt_input", "var": "p_mood"}

    restored = PromptInputEvt.from_dict(d)
    assert restored == evt


# 4. DecoratorEvt round-trip with list args
def test_decorator_evt_round_trip_with_list_args():
    from core.engine.protocol import DecoratorEvt

    evt = DecoratorEvt(name="style", args=["bgm:rain.mp3"])
    d = evt.to_dict()
    assert d == {"event": "decorator", "name": "style", "args": ["bgm:rain.mp3"]}

    restored = DecoratorEvt.from_dict(d)
    assert restored == evt

    # 多 args
    evt2 = DecoratorEvt(name="style", args=["bgm:rain.mp3", "vol:0.5"])
    d2 = evt2.to_dict()
    assert d2["args"] == ["bgm:rain.mp3", "vol:0.5"]


# 5. DecoratorEvt args 传 tuple / set 抛 ValueError
def test_decorator_evt_from_dict_wrong_args_type_raises_value_error():
    from core.engine.protocol import DecoratorEvt

    # tuple 而非 list
    with pytest.raises(ValueError):
        DecoratorEvt.from_dict({
            "event": "decorator", "name": "style", "args": ("bgm:rain.mp3",)
        })

    # set 而非 list
    with pytest.raises(ValueError):
        DecoratorEvt.from_dict({
            "event": "decorator", "name": "style", "args": {"bgm:rain.mp3"}
        })

    # list 元素是 int 而非 str
    with pytest.raises(ValueError):
        DecoratorEvt.from_dict({
            "event": "decorator", "name": "style", "args": [42]
        })


# 6. RouteEvt round-trip
def test_route_evt_round_trip():
    from core.engine.protocol import RouteEvt

    evt = RouteEvt(target="chapter02")
    d = evt.to_dict()
    assert d == {"event": "route", "target": "chapter02"}

    restored = RouteEvt.from_dict(d)
    assert restored == evt


# 7. ChapterEndEvt round-trip（空字段）
def test_chapter_end_evt_round_trip():
    from core.engine.protocol import ChapterEndEvt

    evt = ChapterEndEvt()
    d = evt.to_dict()
    assert d == {"event": "chapter_end"}

    restored = ChapterEndEvt.from_dict(d)
    assert restored == evt


# 8. LogEvt round-trip
def test_log_evt_round_trip():
    from core.engine.protocol import LogEvt

    evt = LogEvt(level="info", message="hello")
    d = evt.to_dict()
    assert d == {"event": "log", "level": "info", "message": "hello"}

    restored = LogEvt.from_dict(d)
    assert restored == evt


# 9. parse_evt 按 event 字段分发
def test_parse_evt_dispatches_by_event_field():
    from core.engine.protocol import (
        TextEvt, PromptInputEvt, DecoratorEvt, RouteEvt, ChapterEndEvt, LogEvt,
        parse_evt,
    )

    a = parse_evt({"event": "text", "content": "x"})
    assert isinstance(a, TextEvt)

    b = parse_evt({"event": "prompt_input", "var": "p"})
    assert isinstance(b, PromptInputEvt)

    c = parse_evt({"event": "decorator", "name": "style", "args": ["x"]})
    assert isinstance(c, DecoratorEvt)

    d_evt = parse_evt({"event": "route", "target": "ch02"})
    assert isinstance(d_evt, RouteEvt)

    e = parse_evt({"event": "chapter_end"})
    assert isinstance(e, ChapterEndEvt)

    f = parse_evt({"event": "log", "level": "info", "message": "x"})
    assert isinstance(f, LogEvt)


# 10. parse_evt 未知 event 抛 ValueError
def test_parse_evt_unknown_raises_value_error():
    from core.engine.protocol import parse_evt

    with pytest.raises(ValueError):
        parse_evt({"event": "fly_to_mars"})


# 11. 字段缺失抛 ValueError（多种事件各取一例）
def test_from_dict_missing_field_raises_value_error():
    from core.engine.protocol import TextEvt, LogEvt, DecoratorEvt

    # TextEvt 缺 content
    with pytest.raises(ValueError):
        TextEvt.from_dict({"event": "text", "style": "narration"})

    # LogEvt 缺 message
    with pytest.raises(ValueError):
        LogEvt.from_dict({"event": "log", "level": "info"})

    # DecoratorEvt 缺 name
    with pytest.raises(ValueError):
        DecoratorEvt.from_dict({"event": "decorator", "args": ["x"]})
