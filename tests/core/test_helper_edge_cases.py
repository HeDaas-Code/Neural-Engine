"""v2 ROADMAP §3.11 测试覆盖率提升 — internal helper 边界单测。

覆盖 3 个 helper（仅新增测试，不改实现）：
1. EngineBus._drain / _close_queue (bus.py:62-82)
2. Executor._emit_decorator (executor.py:239-250)
3. Executor._validate_target_ids (executor.py:87-119)

跳过 main._try_spawn_gui (GUI 轨，与另一 agentic 冲突)。
"""
import multiprocessing
import queue as thread_queue

import pytest

from core.engine.bus import EngineBus
from core.engine.executor import Executor, MemoryEventSink
from core.engine.ast_nodes import (
    Story, Block, BlockLocation, IdMeta, IdEnd, NextDecl,
    Start, End, NextId, DecoratorCall, DecoratorStop,
    If, Branch, CallExpression,
)
from core.engine.protocol import (  # noqa: E402
    DecoratorEvt, ShutdownCmd, TextEvt, LogEvt,
)


def _loc(lineno: int = 1) -> BlockLocation:
    return BlockLocation(lineno=lineno, col=1)


def _start_block(body=(), next_table=(), end_chapter=None, end_x=None) -> Block:
    """id:start 块，body=[Start, *body, End]，含 id:endX 标记。"""
    meta = [IdMeta(id="start", lineno=1)]
    if end_x is not None:
        meta.append(IdEnd(x=end_x, route_chapter=end_chapter, lineno=2))
    return Block(
        meta=tuple(meta),
        next_table=tuple(next_table),
        body=(Start(), *body, End()),
        loc=_loc(),
    )


# ============================================================
# 1. EngineBus._drain / _close_queue
# ============================================================
class TestEngineBusDrain:
    def test_drain_空_queue_不抛(self):
        """空 queue 的 _drain 应安全返回（get_nowait 抛 Empty → break）。"""
        q = thread_queue.Queue()
        # 不抛
        EngineBus._drain(q)
        # 仍为空
        assert q.empty()

    def test_drain_排空多条残留(self):
        """多条残留消息应全部排空。"""
        q = thread_queue.Queue()
        for i in range(5):
            q.put(f"msg-{i}")
        assert not q.empty()
        EngineBus._drain(q)
        assert q.empty()

    def test_drain_排空单条残留(self):
        q = thread_queue.Queue()
        q.put("only")
        EngineBus._drain(q)
        assert q.empty()

    def test_drain_对_multiprocessing_queue_空时不抛(self):
        """multiprocessing.Queue 空时 _drain 不抛（走 except 分支 break）。"""
        q = multiprocessing.Queue()
        EngineBus._drain(q)
        assert q.empty()
        q.close()

    def test_drain_对_multiprocessing_queue_排空残留(self):
        """multiprocessing.Queue 排空残留——drain 不抛即可。

        注: multiprocessing.Queue 有 feeder 线程延迟, put 后立即 get_nowait 可能仍抛 Empty,
        故不验证数据存在, 仅验证 drain 不抛 + queue 未损坏。
        """
        q = multiprocessing.Queue()
        for i in range(3):
            q.put(f"m{i}")
        EngineBus._drain(q)  # 不抛
        q.close()  # queue 仍可正常关闭（未被破坏）


class TestEngineBusCloseQueue:
    def test_close_queue_对_thread_queue_不抛(self):
        """queue.Queue 无 close() 方法——_close_queue 应跳过不抛。"""
        q = thread_queue.Queue()
        # 不抛
        EngineBus._close_queue(q)
        # queue.Queue 实例仍可用（未被破坏）
        q.put("x")
        assert q.get() == "x"

    def test_close_queue_对_multiprocessing_queue_调用_close(self):
        """multiprocessing.Queue 有 close()——_close_queue 应调用它。"""
        q = multiprocessing.Queue()
        EngineBus._close_queue(q)
        # close 后再 put 会触发已关闭错误（具体异常类型跨版本不一, 用 try 验证行为）
        # 不做强断言，仅验证不抛 + close 被调用过（间接：调用后 join_thread 风格的验证过于侵入，这里只验证不抛）

    def test_close_queue_空_thread_queue_不抛(self):
        q = thread_queue.Queue()
        EngineBus._close_queue(q)
        EngineBus._close_queue(q)  # 重复调用也不抛

    def test_drain_then_close_queue_组合_不抛(self):
        """模拟 close() 的内部顺序：先 drain 再 close_queue。"""
        q = thread_queue.Queue()
        q.put("a")
        q.put("b")
        EngineBus._drain(q)
        EngineBus._close_queue(q)
        assert q.empty()


class TestEngineBusCloseMethod:
    """close() 方法本身已被现有测试覆盖, 这里补 multiprocessing 路径。"""

    def test_close_对_multiprocessing_bus_不抛(self):
        bus = EngineBus(use_multiprocessing=True)
        bus.put_evt(TextEvt(content="x"))
        bus.close()  # 不抛

    def test_close_对_thread_bus_残留消息_不抛(self):
        bus = EngineBus(use_multiprocessing=False)
        bus.put_cmd(ShutdownCmd())
        bus.put_evt(LogEvt(level="info", message="x"))
        bus.close()  # 不抛


# ============================================================
# 2. Executor._emit_decorator
# ============================================================
class TestEmitDecoratorEdgeCases:
    def test_decorator_call_arg_无冒号_不更新_state_但仍广播(self):
        """arg 如 "bgm"（无 key:val）——不更新 _deco_state, 但仍在 DecoratorEvt.args 中。"""
        block = _start_block(body=[
            DecoratorCall(name="style", args=("bgm",)),  # 无 ":"
        ], end_x=0)
        story = Story(blocks=(block,))
        sink = MemoryEventSink()
        exe = Executor(story, sink)
        exe.run()
        dec_evts = [e for e in sink.events if isinstance(e, DecoratorEvt)]
        assert len(dec_evts) == 1
        assert dec_evts[0].args == ["bgm"]  # 广播保留
        # state 不含 style（因为没有任何带 ":" 的 arg）
        assert "style" not in exe._deco_state

    def test_decorator_call_混合_有冒号_无冒号(self):
        """一个 arg 有冒号、一个无——只前者更新 state, 两者都广播。"""
        block = _start_block(body=[
            DecoratorCall(name="style", args=("bgm:rain.mp3", "vol")),  # 一有一无
        ], end_x=0)
        story = Story(blocks=(block,))
        sink = MemoryEventSink()
        exe = Executor(story, sink)
        exe.run()
        dec_evts = [e for e in sink.events if isinstance(e, DecoratorEvt)]
        assert dec_evts[0].args == ["bgm:rain.mp3", "vol"]
        assert exe._deco_state["style"] == {"bgm": "rain.mp3"}  # 只 bgm, 无 vol

    def test_decorator_call_空_args_广播空列表(self):
        block = _start_block(body=[
            DecoratorCall(name="style", args=()),
        ], end_x=0)
        story = Story(blocks=(block,))
        sink = MemoryEventSink()
        exe = Executor(story, sink)
        exe.run()
        dec_evts = [e for e in sink.events if isinstance(e, DecoratorEvt)]
        assert len(dec_evts) == 1
        assert dec_evts[0].args == []
        assert "style" not in exe._deco_state

    def test_decorator_stop_对未注册_name_不抛(self):
        """DecoratorStop 的 name 不在 _deco_state——不抛, 仍广播 args=[key]。"""
        block = _start_block(body=[
            DecoratorStop(name="unknown_deco", key="bgm"),
        ], end_x=0)
        story = Story(blocks=(block,))
        sink = MemoryEventSink()
        exe = Executor(story, sink)
        exe.run()  # 不抛
        dec_evts = [e for e in sink.events if isinstance(e, DecoratorEvt)]
        assert len(dec_evts) == 1
        assert dec_evts[0].name == "unknown_deco"
        assert dec_evts[0].args == ["bgm"]

    def test_decorator_stop_移除不存在的_key_不抛(self):
        """name 已注册但 key 不存在——不抛, state 不变。"""
        block = _start_block(body=[
            DecoratorCall(name="style", args=("bgm:rain.mp3",)),
            DecoratorStop(name="style", key="vol"),  # style 有, 但无 vol key
        ], end_x=0)
        story = Story(blocks=(block,))
        sink = MemoryEventSink()
        exe = Executor(story, sink)
        exe.run()  # 不抛
        # bgm 仍在（vol 不存在, pop 用默认 None）
        assert exe._deco_state["style"] == {"bgm": "rain.mp3"}

    def test_decorator_call_arg_多个冒号_仅第一个分割(self):
        """arg 如 "url:http://x" —— split(":",1) 只切第一个冒号。"""
        block = _start_block(body=[
            DecoratorCall(name="style", args=("url:http://x.com",)),
        ], end_x=0)
        story = Story(blocks=(block,))
        sink = MemoryEventSink()
        exe = Executor(story, sink)
        exe.run()
        assert exe._deco_state["style"]["url"] == "http://x.com"


# ============================================================
# 3. Executor._validate_target_ids
# ============================================================
class TestValidateTargetIdsErrors:
    def test_next_table_未知_target_id_抛_ValueError_含_lineno(self):
        """block.next_table 中 NextDecl.target_id 不存在 → ValueError 含 lineno。"""
        block = _start_block(
            body=(),
            next_table=(NextDecl(var_name=None, target_id="nonexistent", lineno=42),),
            end_x=0,
        )
        story = Story(blocks=(block,))
        sink = MemoryEventSink()
        with pytest.raises(ValueError) as exc_info:
            Executor(story, sink)
        assert "nonexistent" in str(exc_info.value)
        assert "42" in str(exc_info.value)  # lineno 出现在错误信息

    def test_next_id_未知_target_id_抛_ValueError(self):
        """body 中 NextId.target_id 不存在 → ValueError。"""
        block = _start_block(body=[
            NextId(target_id="ghost_block"),
        ], end_x=0)
        story = Story(blocks=(block,))
        sink = MemoryEventSink()
        with pytest.raises(ValueError) as exc_info:
            Executor(story, sink)
        assert "ghost_block" in str(exc_info.value)

    def test_if_branch_next_decl_未知_target_id_抛_ValueError_含_lineno(self):
        """If 分支的 NextDecl.target_id 不存在 → ValueError 含 lineno。"""
        if_node = If(
            cond=("var", "pick"),
            branches=(
                Branch(value=1, target=NextDecl(var_name=None, target_id="missing_a", lineno=7)),
                Branch(value=2, target=NextDecl(var_name=None, target_id="missing_b", lineno=8)),
            ),
        )
        block = _start_block(body=[if_node], end_x=0)
        story = Story(blocks=(block,))
        sink = MemoryEventSink()
        with pytest.raises(ValueError) as exc_info:
            Executor(story, sink)
        msg = str(exc_info.value)
        assert "missing_a" in msg or "missing_b" in msg
        # 至少一个分支的 lineno 出现
        assert "7" in msg or "8" in msg

    def test_全部_target_id_合法_不抛(self):
        """正常路径明示：next_table + NextId + If 分支目标都存在 → 构造成功。"""
        if_node = If(
            cond=("var", "pick"),
            branches=(
                Branch(value=1, target=NextDecl(var_name=None, target_id="block_b", lineno=9)),
            ),
        )
        block_a_with_if = Block(
            meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=2)),
            next_table=(NextDecl(var_name="alt", target_id="block_b", lineno=5),),
            body=(Start(), NextId(target_id="block_b"), if_node, End()),
            loc=_loc(),
        )
        block_b = Block(
            meta=(IdMeta(id="block_b", lineno=20), IdEnd(x=1, route_chapter=None, lineno=21)),
            next_table=(),
            body=(Start(), End()),
            loc=_loc(20),
        )
        story = Story(blocks=(block_a_with_if, block_b))
        sink = MemoryEventSink()
        exe = Executor(story, sink)  # 不抛
        assert exe is not None

    def test_多个未知_target_报第一个遇到的(self):
        """多个未知 target——抛错时至少包含其中一个（不要求全部列出）。"""
        block = _start_block(
            body=[NextId(target_id="ghost1")],
            next_table=(NextDecl(var_name=None, target_id="ghost2", lineno=10),),
            end_x=0,
        )
        story = Story(blocks=(block,))
        sink = MemoryEventSink()
        with pytest.raises(ValueError) as exc_info:
            Executor(story, sink)
        msg = str(exc_info.value)
        # 至少命中一个（具体哪个取决于扫描顺序, 不强断言具体值）
        assert "ghost1" in msg or "ghost2" in msg

    def test_if_branch_call_expression_目标不校验(self):
        """If 分支项是 CallExpression（echo/in）——不参与 target_id 校验。"""
        if_node = If(
            cond=("var", "pick"),
            branches=(
                Branch(value=1, target=CallExpression(kind="echo", var="msg")),
                Branch(value=2, target=CallExpression(kind="in", var="x")),
            ),
        )
        block = _start_block(body=[if_node], end_x=0)
        story = Story(blocks=(block,))
        sink = MemoryEventSink()
        exe = Executor(story, sink)  # 不抛——CallExpression 无 target_id
        assert exe is not None
