"""v2-p0 · PyQt6Sink + PyQt6InputSink 测试（EP-03 + V2-01）。

按 V2-01 issue 验收 + PDR §5.1.2 流程图：
- `PyQt6Sink` 实现 `EventSink` Protocol（put_evt + get_cmd）—— mock callback 验证
- `PyQt6InputSink` 接收用户输入 → `UserInputCmd` 排队
- 测试**不依赖真实 PyQt6**（mock callback / queue），让 PyQt6 不可用时也能跑

约束：
- PyQt6 未装时测试仍可跑（v2 阶段 sink 是 Qt-Agnostic 抽象）
- 真实 Qt 控件集成留给 pyqt6_main.py（任务 3）—— 本模块不直接 import PyQt6
"""
from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")


# ─── 1. PyQt6Sink：基础 EventSink 接口 ──────────────────────────────────────


def test_pyqt6_sink_put_evt_calls_evt_handler():
    """put_evt(evt) → evt_handler(evt) 被调用（mock callback 验证）。"""
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from core.engine.protocol import TextEvt

    received: list = []
    sink = PyQt6Sink(evt_handler=lambda e: received.append(e))

    sink.put_evt(TextEvt(content="雨夜。", style="narration"))

    assert len(received) == 1
    assert received[0].content == "雨夜。"


def test_pyqt6_sink_without_handler_silences_event():
    """未设置 evt_handler 时 put_evt 不抛错（v2 默认静默）。"""
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from core.engine.protocol import TextEvt

    sink = PyQt6Sink()  # 无 handler
    # 不抛错
    sink.put_evt(TextEvt(content="x", style="narration"))


def test_pyqt6_sink_dispatches_all_event_types():
    """put_evt 收到 6 种 Event（TextEvt/PromptInputEvt/DecoratorEvt/RouteEvt/ChapterEndEvt/LogEvt）
    都正确转发给 handler。
    """
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from core.engine.protocol import (
        TextEvt, PromptInputEvt, DecoratorEvt, RouteEvt, ChapterEndEvt, LogEvt,
    )

    received: list = []
    sink = PyQt6Sink(evt_handler=lambda e: received.append(e))

    sink.put_evt(TextEvt(content="t", style="narration"))
    sink.put_evt(PromptInputEvt(var="p"))
    sink.put_evt(DecoratorEvt(name="style", args=["color:red"]))
    sink.put_evt(DecoratorEvt(name="bgm", args=["rain.mp3"], kind="stop"))
    sink.put_evt(RouteEvt(target="chapter02"))
    sink.put_evt(ChapterEndEvt())
    sink.put_evt(LogEvt(level="info", message="hello"))

    assert len(received) == 7
    types = [type(e).__name__ for e in received]
    assert types == [
        "TextEvt", "PromptInputEvt", "DecoratorEvt", "DecoratorEvt",
        "RouteEvt", "ChapterEndEvt", "LogEvt",
    ]


def test_pyqt6_sink_get_cmd_returns_none_when_no_source():
    """未设置 cmd_source 时 get_cmd 返回 None（不阻塞、不抛错）。"""
    from runtime.gui.pyqt6_sink import PyQt6Sink

    sink = PyQt6Sink()
    assert sink.get_cmd() is None


def test_pyqt6_sink_get_cmd_uses_cmd_source_callback():
    """设置了 cmd_source → get_cmd 调用 cmd_source() 并返回其值。"""
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from core.engine.protocol import UserInputCmd

    sentinel = UserInputCmd(value="平静")
    sink = PyQt6Sink(cmd_source=lambda: sentinel)
    assert sink.get_cmd() == sentinel


def test_pyqt6_sink_get_cmd_returns_each_call_fresh():
    """cmd_source 每次调用都取新值（队列式：可以递增）。"""
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from core.engine.protocol import UserInputCmd

    queue = [UserInputCmd(value="1"), UserInputCmd(value="2")]
    sink = PyQt6Sink(cmd_source=lambda: queue.pop(0) if queue else None)

    a = sink.get_cmd()
    b = sink.get_cmd()
    assert a.value == "1"
    assert b.value == "2"
    assert sink.get_cmd() is None  # 队列空


# ─── 2. PyQt6Sink：close 行为 ───────────────────────────────────────────────


def test_pyqt6_sink_close_silences_subsequent_events():
    """close() 后 put_evt 不再调 evt_handler。"""
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from core.engine.protocol import TextEvt

    received: list = []
    sink = PyQt6Sink(evt_handler=lambda e: received.append(e))

    sink.put_evt(TextEvt(content="before", style="narration"))
    sink.close()
    sink.put_evt(TextEvt(content="after", style="narration"))

    assert len(received) == 1
    assert received[0].content == "before"


def test_pyqt6_sink_close_makes_get_cmd_return_none():
    """close() 后 get_cmd 永远返回 None。"""
    from runtime.gui.pyqt6_sink import PyQt6Sink

    sink = PyQt6Sink(cmd_source=lambda: "anything")
    sink.close()
    assert sink.get_cmd() is None


# ─── 3. PyQt6Sink：与 EventSink Protocol 兼容 ──────────────────────────────


def test_pyqt6_sink_satisfies_event_sink_protocol():
    """PyQt6Sink 必须实现 EventSink Protocol（executor.py:28）—— duck typing 检查。"""
    from runtime.gui.pyqt6_sink import PyQt6Sink

    sink = PyQt6Sink()
    # 必须有 put_evt 和 get_cmd 两个 callable
    assert callable(getattr(sink, "put_evt", None))
    assert callable(getattr(sink, "get_cmd", None))


def test_pyqt6_sink_works_as_event_sink_for_executor():
    """PyQt6Sink 作为 Executor.sink 跑一个简单 story（验证 Protocol 兼容）。"""
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from core.engine.executor import Executor
    from core.engine.ast_nodes import (
        Story, Block, BlockLocation, Start, End, Text, IdMeta, IdEnd,
    )
    from core.engine.protocol import TextEvt as TextEvtCls

    received: list = []
    sink = PyQt6Sink(evt_handler=lambda e: received.append(e))

    # 构造最小 story：一个块，含 IdMeta(id='start') + IdEnd(x=0) +
    # Start + Text + End（Executor 需要 IdEnd 才能结束）
    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=1)),
        next_table=(),
        body=(Start(), Text(content="雨夜。"), End()),
        loc=BlockLocation(lineno=1, col=1),
    )
    story = Story(blocks=(block,))

    exe = Executor(story, sink)
    exe.run()

    # TextEvt("雨夜。") + ChapterEndEvt（IdEnd 触发）
    text_evts = [e for e in received if isinstance(e, TextEvtCls)]
    assert len(text_evts) == 1
    assert text_evts[0].content == "雨夜。"


# ─── 4. PyQt6InputSink：用户输入接口 ──────────────────────────────────────


def test_pyqt6_input_sink_submit_enqueues_user_input_cmd():
    """submit(value) → 内部 cmd_q 有 UserInputCmd(value=value)。"""
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from core.engine.protocol import UserInputCmd

    inp = PyQt6InputSink()
    inp.submit("平静")

    cmd = inp.drain_cmd()
    assert isinstance(cmd, UserInputCmd)
    assert cmd.value == "平静"


def test_pyqt6_input_sink_drain_cmd_returns_none_when_empty():
    """空 queue 时 drain_cmd 返回 None（非阻塞）。"""
    from runtime.gui.pyqt6_input import PyQt6InputSink

    inp = PyQt6InputSink()
    assert inp.drain_cmd() is None


def test_pyqt6_input_sink_fifo_order():
    """多次 submit → drain_cmd 按 FIFO 顺序返回。"""
    from runtime.gui.pyqt6_input import PyQt6InputSink

    inp = PyQt6InputSink()
    inp.submit("1")
    inp.submit("2")
    inp.submit("3")

    assert inp.drain_cmd().value == "1"
    assert inp.drain_cmd().value == "2"
    assert inp.drain_cmd().value == "3"
    assert inp.drain_cmd() is None


def test_pyqt6_input_sink_close_drops_subsequent_submit():
    """close() 后 submit 不入队（避免 race 写入已关闭的 queue）。"""
    from runtime.gui.pyqt6_input import PyQt6InputSink

    inp = PyQt6InputSink()
    inp.close()
    inp.submit("never")
    assert inp.drain_cmd() is None


def test_pyqt6_input_sink_get_cmd_blocks_until_available():
    """get_cmd() 阻塞直到有 cmd（Qt signal 消费者模式）。"""
    import threading
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from core.engine.protocol import UserInputCmd

    inp = PyQt6InputSink()

    def producer():
        inp.submit("delayed")

    t = threading.Thread(target=producer)
    t.start()
    cmd = inp.get_cmd()  # 阻塞等待
    t.join()
    assert isinstance(cmd, UserInputCmd)
    assert cmd.value == "delayed"


# ─── 5. PyQt6Sink + PyQt6InputSink 集成 ──────────────────────────────────


def test_pyqt6_sink_uses_pyqt6_input_sink_as_cmd_source():
    """PyQt6InputSink 可作为 PyQt6Sink 的 cmd_source（事件-输入闭环）。"""
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from core.engine.protocol import TextEvt, UserInputCmd

    inp = PyQt6InputSink()
    sink = PyQt6Sink(cmd_source=inp.get_cmd)

    # sink 侧收到 TextEvt（不会触发 cmd）
    sink.put_evt(TextEvt(content="hello", style="narration"))
    # 用户输入 → cmd_source 返回
    inp.submit("ok")
    cmd = sink.get_cmd()
    assert isinstance(cmd, UserInputCmd)
    assert cmd.value == "ok"
