"""v0-issue-14 节点调度测试 + MemoryInputSink。

按 issue #37 acceptance criteria 验证 Text/In/Echo/NextId 节点 + NEXT 跳转。
"""
import sys

import pytest

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")

from core.engine.executor import (  # noqa: E402
    GameState, Executor, MemoryEventSink, MemoryInputSink,
)
from core.engine.ast_nodes import (  # noqa: E402
    Story, Block, BlockLocation, IdMeta, IdEnd, NextDecl,
    Start, End, Text, NextId, In, Echo,
)
from core.engine.protocol import (  # noqa: E402
    TextEvt, PromptInputEvt, ChapterEndEvt, RouteEvt, UserInputCmd,
)


def _loc(lineno: int = 1) -> BlockLocation:
    return BlockLocation(lineno=lineno, col=1)


# 1. Text 节点
def test_text_node_emits_text_evt():
    # v0 简化：自然结束 = 块末 self.next=None + 有 id:end（无 chapter）→ ChapterEndEvt
    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=2)),
        next_table=(),
        body=(Start(), Text(content="雨夜。\n"), End()),
        loc=_loc(),
    )
    story = Story(blocks=(block,))
    sink = MemoryEventSink()
    exe = Executor(story, sink)
    exe.run()
    # events: TextEvt + ChapterEndEvt
    assert len(sink.events) == 2
    assert isinstance(sink.events[0], TextEvt)
    assert sink.events[0].content == "雨夜。\n"
    assert sink.events[0].style == "narration"
    assert isinstance(sink.events[1], ChapterEndEvt)


# 2. In 节点
def test_in_node_prompts_and_writes_var():
    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=2)),
        next_table=(),
        body=(Start(), In(var="p_mood"), End()),
        loc=_loc(),
    )
    story = Story(blocks=(block,))
    sink = MemoryInputSink(inputs=["平静"])
    exe = Executor(story, sink)
    exe.run()
    # events: PromptInputEvt, ChapterEndEvt
    assert len(sink.events) == 2
    assert isinstance(sink.events[0], PromptInputEvt)
    assert sink.events[0].var == "p_mood"
    # vars: p_mood=平静
    assert exe.state.vars == {"p_mood": "平静"}


# 3. Echo 节点
def test_echo_node_emits_var_value():
    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=2)),
        next_table=(),
        body=(Start(), In(var="p_mood"), Echo(var="p_mood"), End()),
        loc=_loc(),
    )
    story = Story(blocks=(block,))
    sink = MemoryInputSink(inputs=["雨"])
    exe = Executor(story, sink)
    exe.run()
    # events: PromptInputEvt, TextEvt(雨), ChapterEndEvt
    assert len(sink.events) == 3
    assert isinstance(sink.events[1], TextEvt)
    assert sink.events[1].content == "雨"


# 4. Echo 变量未设
def test_echo_node_unset_var_raises_key_error():
    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=2)),
        next_table=(),
        body=(Start(), Echo(var="undefined"), End()),
        loc=_loc(),
    )
    story = Story(blocks=(block,))
    sink = MemoryEventSink()
    exe = Executor(story, sink)
    with pytest.raises(KeyError):
        exe.run()


# 5. NextId 设 next
def test_next_id_sets_next_target():
    # NextId 后 End，且有 id:end0（c1 存在作为 next 目标）
    start_block = Block(
        meta=(IdMeta(id="start", lineno=1),),
        next_table=(),
        body=(Start(), NextId(target_id="c1"), End()),
        loc=_loc(),
    )
    c1_block = Block(
        meta=(IdMeta(id="c1", lineno=10), IdEnd(x=0, route_chapter=None, lineno=11)),
        next_table=(),
        body=(Start(), End()),
        loc=_loc(10),
    )
    story = Story(blocks=(start_block, c1_block))
    sink = MemoryEventSink()
    exe = Executor(story, sink)
    # 跑完：start 块 NextId → 跳 c1 块 → c1 块 End 发 ChapterEndEvt
    exe.run()
    assert len(sink.events) == 1
    assert isinstance(sink.events[0], ChapterEndEvt)


# 6. bare next 跳转
def test_bare_next_block_jumps_to_target():
    # start 块 next: c1，c1 块只有 Start/Text/End + id:end0
    start_block = Block(
        meta=(IdMeta(id="start", lineno=1),),
        next_table=(NextDecl(var_name=None, target_id="c1", lineno=2),),
        body=(Start(), NextId(target_id="c1"), End()),
        loc=_loc(),
    )
    c1_block = Block(
        meta=(IdMeta(id="c1", lineno=10), IdEnd(x=0, route_chapter=None, lineno=11)),
        next_table=(),
        body=(Start(), Text(content="end\n"), End()),
        loc=_loc(10),
    )
    story = Story(blocks=(start_block, c1_block))
    sink = MemoryEventSink()
    exe = Executor(story, sink)
    exe.run()
    # events: TextEvt("end\n") + ChapterEndEvt
    assert len(sink.events) == 2
    assert isinstance(sink.events[0], TextEvt)
    assert sink.events[0].content == "end\n"
    assert isinstance(sink.events[1], ChapterEndEvt)


# 7. NEXT 空 + id:end route chapter
def test_empty_next_with_end_marker_chapter_emits_route():
    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=1, route_chapter="ch02", lineno=2)),
        next_table=(),
        body=(Start(), End()),
        loc=_loc(),
    )
    story = Story(blocks=(block,))
    sink = MemoryEventSink()
    exe = Executor(story, sink)
    exe.run()
    assert len(sink.events) == 1
    assert isinstance(sink.events[0], RouteEvt)
    assert sink.events[0].target == "ch02"


# 8. NEXT 空 + id:end 无 chapter
def test_empty_next_with_end_marker_no_chapter_emits_chapter_end():
    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=2)),
        next_table=(),
        body=(Start(), End()),
        loc=_loc(),
    )
    story = Story(blocks=(block,))
    sink = MemoryEventSink()
    exe = Executor(story, sink)
    exe.run()
    assert len(sink.events) == 1
    assert isinstance(sink.events[0], ChapterEndEvt)


# 9. NEXT 空 + 无 id:end → RuntimeError
def test_empty_next_without_end_marker_raises_runtime_error():
    block = Block(
        meta=(IdMeta(id="start", lineno=1),),  # 无 id:end
        next_table=(),
        body=(Start(), Text(content="hi\n"), End()),
        loc=_loc(),
    )
    story = Story(blocks=(block,))
    sink = MemoryEventSink()
    exe = Executor(story, sink)
    with pytest.raises(RuntimeError):
        exe.run()


# 10. NextId 目标 ID 找不到
def test_next_id_target_id_not_in_story_raises_value_error():
    start_block = Block(
        meta=(IdMeta(id="start", lineno=1),),
        next_table=(),
        body=(Start(), NextId(target_id="nonexistent"), End()),
        loc=_loc(),
    )
    story = Story(blocks=(start_block,))
    sink = MemoryEventSink()
    # 构造时就校验：目标 ID 不在 story → ValueError
    with pytest.raises(ValueError):
        Executor(story, sink)


# 11. MemoryInputSink 顺序消费
def test_memory_input_sink_consumes_inputs_in_order():
    sink = MemoryInputSink(inputs=["a", "b", "c"])
    cmd1 = sink.get_cmd()
    cmd2 = sink.get_cmd()
    cmd3 = sink.get_cmd()
    cmd4 = sink.get_cmd()
    assert isinstance(cmd1, UserInputCmd) and cmd1.value == "a"
    assert isinstance(cmd2, UserInputCmd) and cmd2.value == "b"
    assert isinstance(cmd3, UserInputCmd) and cmd3.value == "c"
    assert cmd4 is None


# 12. Echo 拼接 (ADR-0004 G4): parts 模式——变量值 + 字面量拼接输出
def test_echo_parts_concatenates_var_and_literal():
    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=2)),
        next_table=(),
        body=(Start(), In(var="p_mood"), Echo(parts=("p_mood", "，我知道了。")), End()),
        loc=_loc(),
    )
    story = Story(blocks=(block,))
    sink = MemoryInputSink(inputs=["雨"])
    exe = Executor(story, sink)
    exe.run()
    text_evts = [e for e in sink.events if isinstance(e, TextEvt)]
    assert len(text_evts) == 1
    assert text_evts[0].content == "雨，我知道了。"
    assert text_evts[0].style == "narration"


# 13. Echo 拼接：part 不在 vars 中按字面量原样输出
def test_echo_parts_treats_unknown_part_as_literal():
    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=2)),
        next_table=(),
        body=(Start(), Echo(parts=("你好", "，世界。")), End()),
        loc=_loc(),
    )
    story = Story(blocks=(block,))
    sink = MemoryEventSink()
    exe = Executor(story, sink)
    exe.run()
    text_evts = [e for e in sink.events if isinstance(e, TextEvt)]
    assert len(text_evts) == 1
    assert text_evts[0].content == "你好，世界。"


# 14. In 节点 int 转换：纯数字输入存为 int（影响下游 node if 值匹配）
def test_in_node_stores_numeric_input_as_int():
    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=2)),
        next_table=(),
        body=(Start(), In(var="p_pick"), End()),
        loc=_loc(),
    )
    story = Story(blocks=(block,))
    sink = MemoryInputSink(inputs=["3"])
    exe = Executor(story, sink)
    exe.run()
    assert exe.state.vars["p_pick"] == 3
    assert isinstance(exe.state.vars["p_pick"], int)
