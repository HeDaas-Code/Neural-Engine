"""core/engine/bus.py (EngineBus) 单元测试。

EngineBus 是 GUI ↔ Engine 进程间通信的核心双向队列封装，
此前无任何测试覆盖。本测试填补这一关键缺口，锁定：
- Queue 序列化/反序列化契约（JSON + UTF-8）
- put_cmd / get_cmd 与 put_evt / get_evt 消息往返
- close() 排空与关闭行为
- multiprocessing.Queue vs queue.Queue 的正确选择
"""

import sys
import os
import queue as _thread_queue

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, f"{REPO_ROOT}/src")

from core.engine.bus import EngineBus
from core.engine.protocol import (
    LoadChapterCmd,
    UserInputCmd,
    SaveCmd,
    TextEvt,
    ChapterEndEvt,
    RouteEvt,
    LogEvt,
    SaveAckEvt,
)


class TestEngineBusInit:
    """EngineBus 初始化行为。"""

    def test_init_default_uses_multiprocessing_queue(self):
        bus = EngineBus()
        assert bus._cmd_q is not None
        assert bus._evt_q is not None
        assert not isinstance(bus._cmd_q, _thread_queue.Queue)

    def test_init_with_thread_queue(self):
        bus = EngineBus(use_multiprocessing=False)
        assert isinstance(bus._cmd_q, _thread_queue.Queue)
        assert isinstance(bus._evt_q, _thread_queue.Queue)

    def test_init_with_custom_queues(self):
        cmd_q = _thread_queue.Queue()
        evt_q = _thread_queue.Queue()
        bus = EngineBus(cmd_q=cmd_q, evt_q=evt_q, use_multiprocessing=False)
        assert bus._cmd_q is cmd_q
        assert bus._evt_q is evt_q


class TestEngineBusCmd:
    """put_cmd / get_cmd 往返序列化（GUI → Engine）。"""

    def test_put_get_load_chapter_cmd(self):
        bus = EngineBus(use_multiprocessing=False)
        cmd = LoadChapterCmd(path="chapters/chapter01.md")
        bus.put_cmd(cmd)
        result = bus.get_cmd()
        assert isinstance(result, LoadChapterCmd)
        assert result.path == "chapters/chapter01.md"

    def test_put_get_user_input_cmd(self):
        bus = EngineBus(use_multiprocessing=False)
        cmd = UserInputCmd(value="player_choice_a")
        bus.put_cmd(cmd)
        result = bus.get_cmd()
        assert isinstance(result, UserInputCmd)
        assert result.value == "player_choice_a"

    def test_put_get_save_cmd(self):
        bus = EngineBus(use_multiprocessing=False)
        cmd = SaveCmd(slot="checkpoint_01")
        bus.put_cmd(cmd)
        result = bus.get_cmd()
        assert isinstance(result, SaveCmd)
        assert result.slot == "checkpoint_01"

    def test_get_cmd_empty_queue_raises_empty(self):
        bus = EngineBus(use_multiprocessing=False)
        with pytest.raises(_thread_queue.Empty):
            bus._cmd_q.get_nowait()


class TestEngineBusEvt:
    """put_evt / get_evt 往返序列化（Engine → GUI）。"""

    def test_put_get_text_evt(self):
        bus = EngineBus(use_multiprocessing=False)
        evt = TextEvt(content="narrative text", style="narration")
        bus.put_evt(evt)
        result = bus.get_evt()
        assert isinstance(result, TextEvt)
        assert result.content == "narrative text"

    def test_put_get_chapter_end_evt(self):
        bus = EngineBus(use_multiprocessing=False)
        evt = ChapterEndEvt()
        bus.put_evt(evt)
        result = bus.get_evt()
        assert isinstance(result, ChapterEndEvt)

    def test_put_get_route_evt(self):
        bus = EngineBus(use_multiprocessing=False)
        evt = RouteEvt(target="chapter02")
        bus.put_evt(evt)
        result = bus.get_evt()
        assert isinstance(result, RouteEvt)
        assert result.target == "chapter02"

    def test_put_get_log_evt(self):
        bus = EngineBus(use_multiprocessing=False)
        evt = LogEvt(level="info", message="block executed")
        bus.put_evt(evt)
        result = bus.get_evt()
        assert isinstance(result, LogEvt)
        assert result.level == "info"
        assert result.message == "block executed"

    def test_put_get_save_ack_evt(self):
        bus = EngineBus(use_multiprocessing=False)
        evt = SaveAckEvt(slot="slot_1", ok=True)
        bus.put_evt(evt)
        result = bus.get_evt()
        assert isinstance(result, SaveAckEvt)
        assert result.slot == "slot_1"
        assert result.ok is True

    def test_put_get_save_ack_with_error(self):
        bus = EngineBus(use_multiprocessing=False)
        evt = SaveAckEvt(slot="slot_1", ok=False, error="disk full")
        bus.put_evt(evt)
        result = bus.get_evt()
        assert isinstance(result, SaveAckEvt)
        assert result.ok is False
        assert result.error == "disk full"


class TestEngineBusClose:
    """EngineBus.close() 排空与关闭行为。"""

    def test_close_drains_pending_messages(self):
        bus = EngineBus(use_multiprocessing=False)
        bus.put_evt(TextEvt(content="msg1", style="narration"))
        bus.put_evt(TextEvt(content="msg2", style="narration"))
        bus.close()
        with pytest.raises(_thread_queue.Empty):
            bus._evt_q.get_nowait()

    def test_close_with_empty_queue_no_error(self):
        bus = EngineBus(use_multiprocessing=False)
        bus.close()

    def test_close_multiprocessing_queue(self):
        import multiprocessing
        cmd_q = multiprocessing.Queue()
        evt_q = multiprocessing.Queue()
        bus = EngineBus(cmd_q=cmd_q, evt_q=evt_q)
        bus.put_evt(TextEvt(content="test", style="narration"))
        bus.close()


class TestEngineBusSerialization:
    """EngineBus JSON + UTF-8 序列化细节。"""

    def test_utf8_unicode_content(self):
        bus = EngineBus(use_multiprocessing=False)
        evt = TextEvt(content="你好世界", style="narration")
        bus.put_evt(evt)
        result = bus.get_evt()
        assert result.content == "你好世界"

    def test_unicode_special_chars(self):
        bus = EngineBus(use_multiprocessing=False)
        evt = TextEvt(content="café résumé", style="narration")
        bus.put_evt(evt)
        result = bus.get_evt()
        assert result.content == "café résumé"

    def test_multiple_messages_fifo_order(self):
        bus = EngineBus(use_multiprocessing=False)
        bus.put_evt(TextEvt(content="first", style="narration"))
        bus.put_evt(TextEvt(content="second", style="narration"))
        bus.put_evt(TextEvt(content="third", style="narration"))
        r1 = bus.get_evt()
        r2 = bus.get_evt()
        r3 = bus.get_evt()
        assert r1.content == "first"
        assert r2.content == "second"
        assert r3.content == "third"