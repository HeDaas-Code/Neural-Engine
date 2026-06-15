"""v0-issue-16 node if 打桩测试。

按 issue #39 acceptance criteria 验证 if 节点调度 + 跨块 ID 校验。
"""
import sys

import pytest

REPO_ROOT = "/home/hedaas/桌面/Neural Engine"
sys.path.insert(0, f"{REPO_ROOT}/src")

from core.engine.executor import Executor, MemoryEventSink, MemoryInputSink  # noqa: E402
from core.engine.ast_nodes import (  # noqa: E402
    Story, Block, BlockLocation, IdMeta, IdEnd, NextDecl,
    Start, End, Text, NextId, If, Branch, CallExpression,
    In as AstIn, Echo as AstEcho,
)
from core.engine.protocol import (  # noqa: E402
    TextEvt, LogEvt, ChapterEndEvt, PromptInputEvt, UserInputCmd,
)


def _loc(lineno: int = 1) -> BlockLocation:
    return BlockLocation(lineno=lineno, col=1)


# 1. 多元 if 打桩
def test_multi_if_stub_picks_first_branch():
    # node if var [1:t_a, 2:t_b]  + vars var=1
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
    # LogEvt + 跳 ca + ChapterEndEvt
    log_evts = [e for e in sink.events if isinstance(e, LogEvt)]
    assert len(log_evts) == 1
    assert "chose branch 1" in log_evts[0].message
    # ca 块被跳到（产生 1 个 ChapterEndEvt from ca）
    chapter_ends = [e for e in sink.events if isinstance(e, ChapterEndEvt)]
    assert len(chapter_ends) == 1


# 2. 二元 if 打桩
def test_binary_if_stub_picks_first_branch():
    if_node = If(
        cond=("var", "cond"),
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


# 3. 简略二元
def test_shortcut_if_stub_picks_first_branch():
    # v1-issue-6: 简略二元现在走 dispatcher 真求值. 设 state.vars["a"]=0 走 False 分支.
    if_node = If(
        cond=("expr", "a"),
        branches=(
            Branch(value=0, target=NextDecl(var_name="b", target_id="cb", lineno=3)),
            Branch(value=1, target=NextDecl(var_name="c", target_id="cc", lineno=4)),
        ),
    )
    block_b = Block(
        meta=(IdMeta(id="cb", lineno=10), IdEnd(x=0, route_chapter=None, lineno=11)),
        next_table=(),
        body=(Start(), End()),
        loc=_loc(10),
    )
    block_c = Block(
        meta=(IdMeta(id="cc", lineno=12), IdEnd(x=0, route_chapter=None, lineno=13)),
        next_table=(),
        body=(Start(), End()),
        loc=_loc(12),
    )
    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=2)),
        next_table=(
            NextDecl(var_name="b", target_id="cb", lineno=2),
            NextDecl(var_name="c", target_id="cc", lineno=3),
        ),
        body=(Start(), if_node, End()),
        loc=_loc(),
    )
    story = Story(blocks=(block, block_b, block_c))
    sink = MemoryEventSink()
    exe = Executor(story, sink)
    exe.state.vars["a"] = 0  # v1-issue-6: 让 dispatcher.eval_bool("a") 返回 False 走 value=0
    exe.run()
    log_evts = [e for e in sink.events if isinstance(e, LogEvt)]
    # v1: expr 真求值, 单条 info log (无 warning)
    info_logs = [e for e in log_evts if e.level == "info"]
    assert len(info_logs) == 1
    assert "chose branch 0" in info_logs[0].message


# 4. 多元 if + echo 第一分支 → TextEvt
def test_multi_if_with_echo_in_first_emits_text_evt():
    # 3:echo p_pick 第一分支——v0 走 echo 模拟 + self.next=None
    if_node = If(
        cond=("var", "var"),
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
    sink = MemoryInputSink(inputs=["雨"])
    exe = Executor(story, sink)
    exe.run()
    # events: PromptInputEvt, TextEvt("雨"), LogEvt, ChapterEndEvt
    log_evts = [e for e in sink.events if isinstance(e, LogEvt)]
    assert len(log_evts) == 1


# 5. 总是广播 LogEvt
def test_if_always_emits_log_evt():
    if_node = If(
        cond=("var", "cond"),
        branches=(
            Branch(value=0, target=NextDecl(var_name="a", target_id="ca", lineno=3)),
        ),
    )
    block_a = Block(
        meta=(IdMeta(id="ca", lineno=10), IdEnd(x=0, route_chapter=None, lineno=11)),
        next_table=(),
        body=(Start(), End()),
        loc=_loc(10),
    )
    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=2)),
        next_table=(NextDecl(var_name="a", target_id="ca", lineno=2),),
        body=(Start(), if_node, End()),
        loc=_loc(),
    )
    story = Story(blocks=(block, block_a))
    sink = MemoryEventSink()
    exe = Executor(story, sink)
    exe.run()
    log_evts = [e for e in sink.events if isinstance(e, LogEvt)]
    assert len(log_evts) == 1
    assert "node if: chose branch" in log_evts[0].message  # v1-issue-6: 不再 stub


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


# 8. v1-issue-6 新增: bool_expr 真求值
# 现状 v0 永远选第一分支; v1 dispatcher 接管选 branch 逻辑.
# 构造 manual If(cond=("bool_expr", "...")) 直接测 executor 行为 (绕过解析器)
def test_bool_expr_if_picks_correct_branch_true():
    """`p_score 大于 50` 真时选 value=1 分支 (高分组)"""
    if_node = If(
        cond=("bool_expr", "p_score 大于 50"),
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
    exe.state.vars["p_score"] = 60  # 走 True 分支 (value=1)
    exe.run()
    log_evts = [e for e in sink.events if isinstance(e, LogEvt)]
    info_logs = [e for e in log_evts if e.level == "info"]
    assert len(info_logs) == 1
    assert "chose branch 1" in info_logs[0].message
    chapter_ends = [e for e in sink.events if isinstance(e, ChapterEndEvt)]
    assert len(chapter_ends) == 1


def test_bool_expr_if_picks_correct_branch_false():
    """`p_score 大于 50` 假时选 value=0 分支 (低分组)"""
    if_node = If(
        cond=("bool_expr", "p_score 大于 50"),
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
    exe.state.vars["p_score"] = 30  # 走 False 分支 (value=0)
    exe.run()
    log_evts = [e for e in sink.events if isinstance(e, LogEvt)]
    info_logs = [e for e in log_evts if e.level == "info"]
    assert len(info_logs) == 1
    assert "chose branch 0" in info_logs[0].message


def test_var_if_value_match_still_works_v0_compat():
    """v0 `("var", name)` 形态——值匹配, 不进 dispatcher, v0 fixture 不受影响"""
    if_node = If(
        cond=("var", "p_choice"),
        branches=(
            Branch(value=1, target=NextDecl(var_name="a", target_id="ca", lineno=3)),
            Branch(value=2, target=NextDecl(var_name="b", target_id="cb", lineno=4)),
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
    exe.state.vars["p_choice"] = 2
    exe.run()
    log_evts = [e for e in sink.events if isinstance(e, LogEvt)]
    info_logs = [e for e in log_evts if e.level == "info"]
    assert len(info_logs) == 1
    assert "chose branch 2" in info_logs[0].message

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


# 8. v1-issue-6 新增: bool_expr 真求值
# 现状 v0 永远选第一分支; v1 dispatcher 接管选 branch 逻辑.
# 构造 manual If(cond=("bool_expr", "...")) 直接测 executor 行为 (绕过解析器)
def test_bool_expr_if_picks_correct_branch_true():
    """`p_score 大于 50` 真时选 value=1 分支 (高分组)"""
    if_node = If(
        cond=("bool_expr", "p_score 大于 50"),
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
    exe.state.vars["p_score"] = 60  # 走 True 分支 (value=1)
    exe.run()
    log_evts = [e for e in sink.events if isinstance(e, LogEvt)]
    info_logs = [e for e in log_evts if e.level == "info"]
    assert len(info_logs) == 1
    assert "chose branch 1" in info_logs[0].message
    chapter_ends = [e for e in sink.events if isinstance(e, ChapterEndEvt)]
    assert len(chapter_ends) == 1


def test_bool_expr_if_picks_correct_branch_false():
    """`p_score 大于 50` 假时选 value=0 分支 (低分组)"""
    if_node = If(
        cond=("bool_expr", "p_score 大于 50"),
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
    exe.state.vars["p_score"] = 30  # 走 False 分支 (value=0)
    exe.run()
    log_evts = [e for e in sink.events if isinstance(e, LogEvt)]
    info_logs = [e for e in log_evts if e.level == "info"]
    assert len(info_logs) == 1
    assert "chose branch 0" in info_logs[0].message


def test_var_if_value_match_still_works_v0_compat():
    """v0 `("var", name)` 形态——值匹配, 不进 dispatcher, v0 fixture 不受影响"""
    if_node = If(
        cond=("var", "p_choice"),
        branches=(
            Branch(value=1, target=NextDecl(var_name="a", target_id="ca", lineno=3)),
            Branch(value=2, target=NextDecl(var_name="b", target_id="cb", lineno=4)),
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
    exe.state.vars["p_choice"] = 2
    exe.run()
    log_evts = [e for e in sink.events if isinstance(e, LogEvt)]
    info_logs = [e for e in log_evts if e.level == "info"]
    assert len(info_logs) == 1
    assert "chose branch 2" in info_logs[0].message