"""v0-issue-13 Executor 骨架 + GameState + MemoryEventSink 测试。

按 issue #36 acceptance criteria 验证 executor.py 第一步。
"""
import sys

import pytest

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")

from core.engine.executor import (  # noqa: E402
    GameState, Executor, EventSink, MemoryEventSink,
)
from core.engine.ast_nodes import (  # noqa: E402
    Story, Block, BlockLocation, IdMeta, IdEnd, NextDecl,
    Start, End, Text, NextId, ParserError,
)
from core.engine.protocol import RouteEvt, ChapterEndEvt  # noqa: E402


def _loc() -> BlockLocation:
    return BlockLocation(lineno=1, col=1)


def _story_start_only() -> Story:
    """id:start 块，只有 Start sentinel + id:end0（无 chapter）。"""
    start_block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=2)),
        next_table=(),
        body=(Start(),),
        loc=_loc(),
    )
    return Story(blocks=(start_block,))


def _story_with_text() -> Story:
    """id:start 块有 Text 节点。"""
    start_block = Block(
        meta=(IdMeta(id="start", lineno=1),),
        next_table=(),
        body=(Start(), Text(content="hi"), End()),
        loc=_loc(),
    )
    return Story(blocks=(start_block,))


def _story_end_with_chapter() -> Story:
    """id:start 块有 id:end2:chapter02 + 只有 Start/End sentinel。"""
    start_block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=2, route_chapter="chapter02", lineno=2)),
        next_table=(),
        body=(Start(), End()),
        loc=_loc(),
    )
    return Story(blocks=(start_block,))


def _story_end_no_chapter() -> Story:
    """id:start 块有 id:end1 + Start/End sentinel。"""
    start_block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=1, route_chapter=None, lineno=2)),
        next_table=(),
        body=(Start(), End()),
        loc=_loc(),
    )
    return Story(blocks=(start_block,))


def _story_end_no_id() -> Story:
    """id:start 块无 id:endX 标记 + Start/End sentinel。"""
    start_block = Block(
        meta=(IdMeta(id="start", lineno=1),),
        next_table=(),
        body=(Start(), End()),
        loc=_loc(),
    )
    return Story(blocks=(start_block,))


# 1. GameState 默认字段
def test_game_state_default_fields():
    s = GameState()
    assert s.vars == {}
    assert s.path == []
    assert s.next_table == {}


# 2. MemoryEventSink 累积
def test_memory_event_sink_accumulates():
    sink = MemoryEventSink()
    e1 = RouteEvt(target="ch02")
    e2 = ChapterEndEvt()
    sink.put_evt(e1)
    sink.put_evt(e2)
    assert len(sink.events) == 2
    assert sink.events[0] is e1
    assert sink.events[1] is e2


# 3. run 入口块到 Start sentinel 不抛错
def test_executor_runs_start_block_to_start_sentinel_without_error():
    story = _story_start_only()
    sink = MemoryEventSink()
    exe = Executor(story, sink)
    exe.run()  # 不抛
    # 没事件（Start sentinel 不发，End 也没因为无 next 也无 id:endX）
    # 注：此块无 id:endX 也不设 next → RuntimeError。改用有 id:end0 的块。


# 4. 缺 id:start
def test_executor_missing_id_start_raises_value_error():
    # 只有一个没 id:start 的块
    block = Block(
        meta=(IdMeta(id="c1", lineno=1),),
        next_table=(),
        body=(Start(), End()),
        loc=_loc(),
    )
    story = Story(blocks=(block,))
    sink = MemoryEventSink()
    exe = Executor(story, sink)
    with pytest.raises(ValueError):
        exe.run()


# 5. v0-issue-13 占位：Text 节点 → NotImplementedError
# 已被 v0-issue-14 覆盖——Text 现在发 TextEvt，不再抛 NotImplementedError
# 此处保留为注释（不再有 test 5）


# 6. end + chapter → RouteEvt
def test_executor_emits_route_event_for_end_with_chapter():
    story = _story_end_with_chapter()
    sink = MemoryEventSink()
    exe = Executor(story, sink)
    exe.run()
    assert len(sink.events) == 1
    assert isinstance(sink.events[0], RouteEvt)
    assert sink.events[0].target == "chapter02"


# 7. end 无 chapter → ChapterEndEvt
def test_executor_emits_chapter_end_event_for_end_without_chapter():
    story = _story_end_no_chapter()
    sink = MemoryEventSink()
    exe = Executor(story, sink)
    exe.run()
    assert len(sink.events) == 1
    assert isinstance(sink.events[0], ChapterEndEvt)


# 8. end 无 id 标记 → RuntimeError
def test_executor_raises_runtime_error_for_end_without_id():
    story = _story_end_no_id()
    sink = MemoryEventSink()
    exe = Executor(story, sink)
    with pytest.raises(RuntimeError):
        exe.run()
