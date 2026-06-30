"""v1 (ADR-0004) node if 真求值测试。

验证 if 节点调度 + 跨块 ID 校验 + 表达式求值。
"""
import pytest

from core.engine.executor import Executor, MemoryEventSink, MemoryInputSink  # noqa: E402
from core.engine.ast_nodes import (  # noqa: E402
    Story, Block, BlockLocation, IdMeta, IdEnd, NextDecl,
    Start, End, Text, NextId, If, Branch, CallExpression,
    In as AstIn, Echo as AstEcho,
)
from core.engine.protocol import (  # noqa: E402
    TextEvt, LogEvt, ChapterEndEvt, PromptInputEvt, UserInputCmd,
)
from core.engine.expr import ExprError  # noqa: E402


def _loc(lineno: int = 1) -> BlockLocation:
    return BlockLocation(lineno=lineno, col=1)


# 1. 多元 if 值匹配
def test_multi_if_value_match():
    if_node = If(
        cond=("var", "var"),
        branches=(
            Branch(value=1, target=NextDecl(var_name="t_a", target_id="ca", lineno=5)),
            Branch(value=2, target=NextDecl(var_name="t_b", target_id="cb", lineno=6)),
        ),
    )
    block_a = Block(
        meta=(IdMeta(id="ca", lineno=10), IdEnd(x=0, route_chapter=None, lineno=11)),
        next_table=(),
        body=(Start(), End()),
        loc=_loc(10),
    )
    block_b = Block(
        meta=(IdMeta(id="cb", lineno=12), IdEnd(x=0, route_chapter=None, lineno=13)),
        next_table=(),
        body=(Start(), End()),
        loc=_loc(12),
    )
    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=2)),
        next_table=(
            NextDecl(var_name="t_a", target_id="ca", lineno=2),
            NextDecl(var_name="t_b", target_id="cb", lineno=3),
        ),
        body=(Start(), AstIn(var="var"), if_node, End()),
        loc=_loc(),
    )
    story = Story(blocks=(block, block_a, block_b))
    sink = MemoryInputSink(inputs=["1"])
    exe = Executor(story, sink)
    exe.run()
    log_evts = [e for e in sink.events if isinstance(e, LogEvt)]
    assert len(log_evts) == 1
    assert "chose branch 1" in log_evts[0].message
    chapter_ends = [e for e in sink.events if isinstance(e, ChapterEndEvt)]
    assert len(chapter_ends) == 1


# 2. 二元 if 表达式求值
def test_binary_if_expr_true():
    if_node = If(
        cond=("expr", "cond == 1"),
        branches=(
            Branch(value=0, target=NextDecl(var_name="a", target_id="ca", lineno=3)),
            Branch(value=1, target=NextDecl(var_name="b", target_id="cb", lineno=4)),
        ),
    )
    block_a = Block(
        meta=(IdMeta(id="ca", lineno=10), IdEnd(x=0, route_chapter=None, lineno=11)),
        next_table=(),
        body=(Start(), End()),
        loc=_loc(10),
    )
    block_b = Block(
        meta=(IdMeta(id="cb", lineno=12), IdEnd(x=0, route_chapter=None, lineno=13)),
        next_table=(),
        body=(Start(), End()),
        loc=_loc(12),
    )
    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=2)),
        next_table=(
            NextDecl(var_name="a", target_id="ca", lineno=2),
            NextDecl(var_name="b", target_id="cb", lineno=3),
        ),
        body=(Start(), if_node, End()),
        loc=_loc(),
    )
    story = Story(blocks=(block, block_a, block_b))
    sink = MemoryEventSink()
    exe = Executor(story, sink)
    # cond 未设置 → NameNotDefined → fallback 失败 → ExprError
    # 需要先设置 cond
    exe.state.vars["cond"] = 1
    exe.run()
    log_evts = [e for e in sink.events if isinstance(e, LogEvt)]
    assert len(log_evts) == 1
    assert "chose branch 0" in log_evts[0].message  # True → branches[0]


# 3. 二元 if 表达式求值 False
def test_binary_if_expr_false():
    if_node = If(
        cond=("expr", "cond == 1"),
        branches=(
            Branch(value=0, target=NextDecl(var_name="a", target_id="ca", lineno=3)),
            Branch(value=1, target=NextDecl(var_name="b", target_id="cb", lineno=4)),
        ),
    )
    block_a = Block(
        meta=(IdMeta(id="ca", lineno=10), IdEnd(x=0, route_chapter=None, lineno=11)),
        next_table=(),
        body=(Start(), End()),
        loc=_loc(10),
    )
    block_b = Block(
        meta=(IdMeta(id="cb", lineno=12), IdEnd(x=0, route_chapter=None, lineno=13)),
        next_table=(),
        body=(Start(), End()),
        loc=_loc(12),
    )
    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=2)),
        next_table=(
            NextDecl(var_name="a", target_id="ca", lineno=2),
            NextDecl(var_name="b", target_id="cb", lineno=3),
        ),
        body=(Start(), if_node, End()),
        loc=_loc(),
    )
    story = Story(blocks=(block, block_a, block_b))
    sink = MemoryEventSink()
    exe = Executor(story, sink)
    exe.state.vars["cond"] = 0
    exe.run()
    log_evts = [e for e in sink.events if isinstance(e, LogEvt)]
    assert len(log_evts) == 1
    assert "chose branch 1" in log_evts[0].message  # False → branches[1]


# 4. 多元 if + echo 分支
def test_multi_if_with_echo_branch():
    if_node = If(
        cond=("var", "p_pick"),
        branches=(
            Branch(value=3, target=CallExpression(kind="echo", var="p_pick")),
        ),
    )
    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=2)),
        next_table=(),
        body=(Start(), AstIn(var="p_pick"), AstEcho(var="p_pick"), if_node, End()),
        loc=_loc(),
    )
    story = Story(blocks=(block,))
    sink = MemoryInputSink(inputs=["3"])
    exe = Executor(story, sink)
    exe.run()
    log_evts = [e for e in sink.events if isinstance(e, LogEvt)]
    assert len(log_evts) == 1


# 4b. 简略二元 if (shortcut: cond ? a : b → expr 求值)
def test_shortcut_if_expr():
    """简略二元: expr 求值 True → branches[0], False → branches[1]。"""
    if_node = If(
        cond=("expr", "cond == 1"),
        branches=(
            Branch(value=0, target=NextDecl(var_name="a", target_id="ca", lineno=3)),
            Branch(value=1, target=NextDecl(var_name="b", target_id="cb", lineno=4)),
        ),
    )
    block_a = Block(
        meta=(IdMeta(id="ca", lineno=10), IdEnd(x=0, route_chapter=None, lineno=11)),
        next_table=(),
        body=(Start(), End()),
        loc=_loc(10),
    )
    block_b = Block(
        meta=(IdMeta(id="cb", lineno=12), IdEnd(x=0, route_chapter=None, lineno=13)),
        next_table=(),
        body=(Start(), End()),
        loc=_loc(12),
    )
    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=2)),
        next_table=(
            NextDecl(var_name="a", target_id="ca", lineno=2),
            NextDecl(var_name="b", target_id="cb", lineno=3),
        ),
        body=(Start(), if_node, End()),
        loc=_loc(),
    )
    story = Story(blocks=(block, block_a, block_b))
    sink = MemoryEventSink()
    exe = Executor(story, sink)
    exe.state.vars["cond"] = 1
    exe.run()
    log_evts = [e for e in sink.events if isinstance(e, LogEvt)]
    assert len(log_evts) >= 1
    assert "chose branch 0" in log_evts[0].message  # True → branches[0]


# 5. 总是广播 LogEvt
def test_if_always_emits_log_evt():
    if_node = If(
        cond=("expr", "True"),
        branches=(
            Branch(value=0, target=NextDecl(var_name="a", target_id="ca", lineno=3)),
            Branch(value=1, target=NextDecl(var_name="b", target_id="cb", lineno=4)),
        ),
    )
    block_a = Block(
        meta=(IdMeta(id="ca", lineno=10), IdEnd(x=0, route_chapter=None, lineno=11)),
        next_table=(),
        body=(Start(), End()),
        loc=_loc(10),
    )
    block_b = Block(
        meta=(IdMeta(id="cb", lineno=12), IdEnd(x=0, route_chapter=None, lineno=13)),
        next_table=(),
        body=(Start(), End()),
        loc=_loc(12),
    )
    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=2)),
        next_table=(
            NextDecl(var_name="a", target_id="ca", lineno=2),
            NextDecl(var_name="b", target_id="cb", lineno=3),
        ),
        body=(Start(), if_node, End()),
        loc=_loc(),
    )
    story = Story(blocks=(block, block_a, block_b))
    sink = MemoryEventSink()
    exe = Executor(story, sink)
    exe.run()
    log_evts = [e for e in sink.events if isinstance(e, LogEvt)]
    assert len(log_evts) == 1
    assert "chose branch 0" in log_evts[0].message


# 6. 构造时校验 next:xxx
def test_constructor_validates_next_decl_target_id():
    block = Block(
        meta=(IdMeta(id="start", lineno=1),),
        next_table=(NextDecl(var_name="t_a", target_id="nonexistent", lineno=2),),
        body=(Start(), End()),
        loc=_loc(),
    )
    story = Story(blocks=(block,))
    sink = MemoryEventSink()
    with pytest.raises(ValueError):
        Executor(story, sink)


# 7. 构造时校验 If 分支 target
def test_constructor_validates_if_branch_target_id():
    if_node = If(
        cond=("var", "cond"),
        branches=(
            Branch(value=0, target=NextDecl(var_name="a", target_id="nonexistent", lineno=3)),
        ),
    )
    block = Block(
        meta=(IdMeta(id="start", lineno=1),),
        next_table=(NextDecl(var_name="a", target_id="nonexistent", lineno=2),),
        body=(Start(), if_node, End()),
        loc=_loc(),
    )
    story = Story(blocks=(block,))
    sink = MemoryEventSink()
    with pytest.raises(ValueError):
        Executor(story, sink)


def _end_block(block_id: str, lineno: int) -> Block:
    """构造一个仅含 id + id:end0 的终态块（供 if 跳转目标用）。"""
    return Block(
        meta=(IdMeta(id=block_id, lineno=lineno), IdEnd(x=0, route_chapter=None, lineno=lineno + 1)),
        next_table=(),
        body=(Start(), End()),
        loc=_loc(lineno),
    )


# 8. 多元 if 表达式值匹配 (ADR-0004): expr 求值结果按 branch.value 匹配（非二元路径）
def test_multi_if_expr_value_match():
    if_node = If(
        cond=("expr", "pick"),
        branches=(
            Branch(value=1, target=NextDecl(var_name="a", target_id="ca", lineno=3)),
            Branch(value=2, target=NextDecl(var_name="b", target_id="cb", lineno=4)),
            Branch(value=3, target=NextDecl(var_name="c", target_id="cc", lineno=5)),
        ),
    )
    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=2)),
        next_table=(
            NextDecl(var_name="a", target_id="ca", lineno=2),
            NextDecl(var_name="b", target_id="cb", lineno=3),
            NextDecl(var_name="c", target_id="cc", lineno=4),
        ),
        body=(Start(), if_node, End()),
        loc=_loc(),
    )
    story = Story(blocks=(block, _end_block("ca", 10), _end_block("cb", 12), _end_block("cc", 14)))
    sink = MemoryEventSink()
    exe = Executor(story, sink)
    exe.state.vars["pick"] = 2
    exe.run()
    log_evts = [e for e in sink.events if isinstance(e, LogEvt)]
    assert len(log_evts) == 1
    assert "chose branch 2" in log_evts[0].message
    assert any(isinstance(e, ChapterEndEvt) for e in sink.events)


# 9. 多元 if expr 求值结果无匹配分支 → RuntimeError
def test_multi_if_expr_no_branch_matched_raises():
    if_node = If(
        cond=("expr", "pick"),
        branches=(
            Branch(value=1, target=NextDecl(var_name="a", target_id="ca", lineno=3)),
            Branch(value=2, target=NextDecl(var_name="b", target_id="cb", lineno=4)),
            Branch(value=3, target=NextDecl(var_name="c", target_id="cc", lineno=5)),
        ),
    )
    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=2)),
        next_table=(
            NextDecl(var_name="a", target_id="ca", lineno=2),
            NextDecl(var_name="b", target_id="cb", lineno=3),
            NextDecl(var_name="c", target_id="cc", lineno=4),
        ),
        body=(Start(), if_node, End()),
        loc=_loc(),
    )
    story = Story(blocks=(block, _end_block("ca", 10), _end_block("cb", 12), _end_block("cc", 14)))
    sink = MemoryEventSink()
    exe = Executor(story, sink)
    exe.state.vars["pick"] = 99
    with pytest.raises(RuntimeError):
        exe.run()


# 10. var 值匹配无结果 → RuntimeError
def test_var_if_no_branch_matched_raises():
    if_node = If(
        cond=("var", "var"),
        branches=(
            Branch(value=1, target=NextDecl(var_name="a", target_id="ca", lineno=3)),
            Branch(value=2, target=NextDecl(var_name="b", target_id="cb", lineno=4)),
        ),
    )
    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=2)),
        next_table=(
            NextDecl(var_name="a", target_id="ca", lineno=2),
            NextDecl(var_name="b", target_id="cb", lineno=3),
        ),
        body=(Start(), if_node, End()),
        loc=_loc(),
    )
    story = Story(blocks=(block, _end_block("ca", 10), _end_block("cb", 12)))
    sink = MemoryEventSink()
    exe = Executor(story, sink)
    exe.state.vars["var"] = 99
    with pytest.raises(RuntimeError):
        exe.run()


# 11. if 分支为 CallExpression(kind="in") → 广播 PromptInputEvt 且不跳转
def test_if_branch_in_target_emits_prompt_input():
    if_node = If(
        cond=("expr", "True"),
        branches=(
            Branch(value=0, target=CallExpression(kind="in", var="p_mood")),
            Branch(value=1, target=CallExpression(kind="echo", var="unused")),
        ),
    )
    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=2)),
        next_table=(),
        body=(Start(), if_node, End()),
        loc=_loc(),
    )
    story = Story(blocks=(block,))
    sink = MemoryEventSink()
    exe = Executor(story, sink)
    exe.run()
    prompt_evts = [e for e in sink.events if isinstance(e, PromptInputEvt)]
    assert len(prompt_evts) == 1
    assert prompt_evts[0].var == "p_mood"
    # in 分支 return 不跳转 → 继续到 End → ChapterEndEvt
    assert any(isinstance(e, ChapterEndEvt) for e in sink.events)


# 12. if expr 求值失败 → 广播 error 级 LogEvt 并重新抛出 ExprError
def test_if_expr_failure_emits_error_log_and_reraises():
    if_node = If(
        cond=("expr", "undefined_var == 1"),
        branches=(
            Branch(value=0, target=NextDecl(var_name="a", target_id="ca", lineno=3)),
            Branch(value=1, target=NextDecl(var_name="b", target_id="cb", lineno=4)),
        ),
    )
    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=2)),
        next_table=(
            NextDecl(var_name="a", target_id="ca", lineno=2),
            NextDecl(var_name="b", target_id="cb", lineno=3),
        ),
        body=(Start(), if_node, End()),
        loc=_loc(),
    )
    story = Story(blocks=(block, _end_block("ca", 10), _end_block("cb", 12)))
    sink = MemoryEventSink()
    exe = Executor(story, sink)
    with pytest.raises(ExprError):
        exe.run()
    error_logs = [e for e in sink.events if isinstance(e, LogEvt) and e.level == "error"]
    assert len(error_logs) == 1
    assert "node if expr failed" in error_logs[0].message
