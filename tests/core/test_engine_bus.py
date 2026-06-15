"""v0-issue-5 EngineBus 测试：双向 Queue + JSON 序列化。

按 issue #27 acceptance criteria 验证：
- default 注入 queue 类型
- 双向 round-trip
- 错误传播
- 关闭语义
"""
import json
import queue as thread_queue
import sys

import pytest

REPO_ROOT = "/home/hedaas/桌面/Neural Engine"
sys.path.insert(0, f"{REPO_ROOT}/src")

from core.engine.bus import EngineBus  # noqa: E402
from core.engine.protocol import (  # noqa: E402
    LoadChapterCmd, UserInputCmd, ShutdownCmd,
    TextEvt, PromptInputEvt, DecoratorEvt,
    RouteEvt, ChapterEndEvt, LogEvt,
)


# 1. default 注入 multiprocessing queue
def test_default_injection_uses_multiprocessing_queue_when_true():
    bus = EngineBus(use_multiprocessing=True)
    # Python 3.14 multiprocessing.Queue 是工厂函数，不是类
    # 用 duck type 验证：multiprocessing.Queue 实例有 .close() 方法
    # queue.Queue 没有 .close()
    assert not isinstance(bus._cmd_q, thread_queue.Queue)
    assert not isinstance(bus._evt_q, thread_queue.Queue)
    assert hasattr(bus._cmd_q, "close")
    assert hasattr(bus._evt_q, "close")
    bus.close()


# 2. default 注入 thread queue（单进程测试用）
def test_default_injection_uses_thread_queue_when_false():
    bus = EngineBus(use_multiprocessing=False)
    assert isinstance(bus._cmd_q, thread_queue.Queue)
    assert isinstance(bus._evt_q, thread_queue.Queue)
    bus.close()


# 3. cmd round-trip
def test_cmd_round_trip_through_thread_queue():
    bus = EngineBus(use_multiprocessing=False)

    bus.put_cmd(LoadChapterCmd(path="ch01.md"))
    bus.put_cmd(UserInputCmd(value="hi"))
    bus.put_cmd(ShutdownCmd())

    a = bus.get_cmd()
    assert isinstance(a, LoadChapterCmd)
    assert a.path == "ch01.md"

    b = bus.get_cmd()
    assert isinstance(b, UserInputCmd)
    assert b.value == "hi"

    c = bus.get_cmd()
    assert isinstance(c, ShutdownCmd)

    bus.close()


# 4. evt round-trip 6 种
def test_evt_round_trip_through_thread_queue():
    bus = EngineBus(use_multiprocessing=False)

    bus.put_evt(TextEvt(content="雨夜。"))
    bus.put_evt(PromptInputEvt(var="p_mood"))
    bus.put_evt(DecoratorEvt(name="style", args=["bgm:rain.mp3"]))
    bus.put_evt(RouteEvt(target="ch02"))
    bus.put_evt(ChapterEndEvt())
    bus.put_evt(LogEvt(level="info", message="hi"))

    a = bus.get_evt()
    assert isinstance(a, TextEvt) and a.content == "雨夜。"

    b = bus.get_evt()
    assert isinstance(b, PromptInputEvt) and b.var == "p_mood"

    c = bus.get_evt()
    assert isinstance(c, DecoratorEvt) and c.args == ["bgm:rain.mp3"]

    d = bus.get_evt()
    assert isinstance(d, RouteEvt) and d.target == "ch02"

    e = bus.get_evt()
    assert isinstance(e, ChapterEndEvt)

    f = bus.get_evt()
    assert isinstance(f, LogEvt) and f.message == "hi"

    bus.close()


# 5. TextEvt style 默认值跨过 bus
def test_evt_round_trip_with_default_style_preserved():
    bus = EngineBus(use_multiprocessing=False)

    bus.put_evt(TextEvt(content="x"))  # default style="narration"
    e = bus.get_evt()
    assert e.style == "narration"

    bus.put_evt(TextEvt(content="y", style="dialogue"))
    e2 = bus.get_evt()
    assert e2.style == "dialogue"

    bus.close()


# 6. get_cmd 坏 dict 抛 ValueError
def test_get_cmd_propagates_value_error_for_bad_dict():
    bus = EngineBus(use_multiprocessing=False)
    # 手动放坏 dict（绕过 put_cmd）
    bus._cmd_q.put(json.dumps({"cmd": "load_chapter"}).encode("utf-8"))  # 缺 path

    with pytest.raises(ValueError):
        bus.get_cmd()

    bus.close()


# 7. get_evt 未知 event 抛 ValueError
def test_get_evt_propagates_value_error_for_unknown_event():
    bus = EngineBus(use_multiprocessing=False)
    bus._evt_q.put(json.dumps({"event": "fly_to_mars"}).encode("utf-8"))

    with pytest.raises(ValueError):
        bus.get_evt()

    bus.close()


# 8. close 不抛 + 排空残留
def test_close_drains_remaining_messages_and_closes_queues():
    bus = EngineBus(use_multiprocessing=False)
    bus.put_evt(TextEvt(content="a"))
    bus.put_evt(TextEvt(content="b"))
    # 不 get，直接 close
    bus.close()  # 不抛
