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


# 4. DecoratorEvt round-trip with list args（EP-06 起 to_dict 必含 kind 字段）
def test_decorator_evt_round_trip_with_list_args():
    from core.engine.protocol import DecoratorEvt

    evt = DecoratorEvt(name="style", args=["bgm:rain.mp3"])
    d = evt.to_dict()
    # EP-06 扩展：默认 kind="call"，to_dict 必输出（显式优于隐式）
    assert d == {
        "event": "decorator",
        "name": "style",
        "args": ["bgm:rain.mp3"],
        "kind": "call",
    }

    restored = DecoratorEvt.from_dict(d)
    assert restored == evt

    # 多 args
    evt2 = DecoratorEvt(name="style", args=["bgm:rain.mp3", "vol:0.5"])
    d2 = evt2.to_dict()
    assert d2["args"] == ["bgm:rain.mp3", "vol:0.5"]
    assert d2["kind"] == "call"


# ─── v2-skeleton · EP-06 · DecoratorEvt kind 字段（call/stop 区分） ───────────
#
# 设计动机：v3+ AudioManager/VideoPlayer 需要区分"触发"和"停止"两个语义。
# v0 默认行为等价于 kind="call"，所以新增字段采用向后兼容策略：
#   - to_dict 必含 kind（显式优于隐式）
#   - from_dict 缺 kind 时默认 "call"（老 v0 dict 仍能 parse）


# 4a. DecoratorEvt 默认 kind = "call"（向后兼容构造）
def test_decorator_evt_default_kind_is_call():
    """DecoratorEvt() 不传 kind 时默认为 'call'，与 v0 行为一致。"""
    from core.engine.protocol import DecoratorEvt

    evt = DecoratorEvt(name="style", args=["x"])
    assert evt.kind == "call"


# 4b. DecoratorEvt 显式 kind = "stop" 区分
def test_decorator_evt_explicit_kind_stop():
    """显式传 kind='stop' 用于停止语义（如 stop("bgm")）。"""
    from core.engine.protocol import DecoratorEvt

    evt = DecoratorEvt(name="bgm", args=["rain.mp3"], kind="stop")
    d = evt.to_dict()
    assert d == {
        "event": "decorator",
        "name": "bgm",
        "args": ["rain.mp3"],
        "kind": "stop",
    }
    assert DecoratorEvt.from_dict(d) == evt


# 4c. from_dict 缺 kind 字段时默认 "call"（向后兼容关键测试）
def test_decorator_evt_from_dict_missing_kind_defaults_to_call():
    """v0 老 dict 无 kind 字段时，from_dict 必须用默认 'call'（EP-06 向后兼容）。"""
    from core.engine.protocol import DecoratorEvt

    # 模拟 v0 时代的 dict：无 kind 字段
    v0_dict = {"event": "decorator", "name": "style", "args": ["bgm:rain.mp3"]}
    evt = DecoratorEvt.from_dict(v0_dict)
    assert evt.kind == "call"
    assert evt.name == "style"
    assert evt.args == ["bgm:rain.mp3"]


# 4d. from_dict kind 字段非法值抛 ValueError
def test_decorator_evt_from_dict_invalid_kind_raises_value_error():
    """kind 不是 'call' / 'stop' 时必须抛 ValueError（防静默错配）。"""
    from core.engine.protocol import DecoratorEvt

    # "pause" 不在合法字面量里
    with pytest.raises(ValueError):
        DecoratorEvt.from_dict({
            "event": "decorator",
            "name": "bgm",
            "args": ["x"],
            "kind": "pause",
        })

    # int 也不允许
    with pytest.raises(ValueError):
        DecoratorEvt.from_dict({
            "event": "decorator",
            "name": "bgm",
            "args": ["x"],
            "kind": 1,
        })


# 4e. parse_evt 仍能分发 DecoratorEvt（带 kind）
def test_parse_evt_dispatches_decorator_with_kind():
    """parse_evt("decorator") 必须返回 DecoratorEvt 且 kind 字段保留。"""
    from core.engine.protocol import DecoratorEvt, parse_evt

    evt = parse_evt({
        "event": "decorator",
        "name": "bgm",
        "args": ["rain.mp3"],
        "kind": "stop",
    })
    assert isinstance(evt, DecoratorEvt)
    assert evt.kind == "stop"


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
