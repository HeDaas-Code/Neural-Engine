"""v4-02 · DslSync 节点图 ↔ neon 源码 双向同步测试（#110）。

验证 issue #110 验收点：
- parse_source：源码字符串 → Story（_load_story 文本版）
- story_to_source：AST → neon 源码（全保真 unparser）
  - 各节点类型：IdMeta/IdEnd/NextDecl/Text/In/Echo/NextId/If/DecoratorCall/DecoratorStop
  - roundtrip：parse → unparse → parse 后 AST 等价（lineno 归一）
- graph_to_source：NodeGraphModel → 最小 neon 源码（结构导出）
- DslSync：双向编排
  - source→graph：全保真解析
  - graph→source：保留已有块体 + 应用节点增删
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from dataclasses import replace

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")

from core.engine.ast_nodes import (
    Block, BlockLocation, Story, IdMeta, IdEnd, IdStart,
    NextDecl, Start, End, Text, In, Echo, NextId, If, Branch,
    CallExpression, DecoratorCall, DecoratorStop,
)
from editor.dsl_sync import (
    parse_source, story_to_source, graph_to_source, DslSync,
)
from editor.node_graph_model import (
    NodeGraphModel, NodeData, EdgeData, story_to_graph,
    TYPE_NORMAL, TYPE_ENTRY, TYPE_ENDING, TYPE_BRANCH, TYPE_ROUTE,
    extract_block_id,
)


# ═══════════════════════════════════════════════════════════════════════
# 辅助：构造 Block + 递归 lineno 归一
# ═══════════════════════════════════════════════════════════════════════


def _make_block(meta=(), next_table=(), body=()) -> Block:
    full_body = (Start(),) + tuple(body) + (End(),)
    return Block(meta=tuple(meta), next_table=tuple(next_table),
                 body=full_body, loc=BlockLocation(lineno=1, col=1))


def _normalize(obj):
    """递归归一 lineno（IdMeta/IdEnd/NextDecl/BlockLocation/Start/End → 0）。"""
    if isinstance(obj, Story):
        return Story(blocks=tuple(_normalize(b) for b in obj.blocks))
    if isinstance(obj, Block):
        return Block(
            meta=tuple(_normalize(m) for m in obj.meta),
            next_table=tuple(_normalize(n) for n in obj.next_table),
            body=tuple(_normalize(n) for n in obj.body),
            loc=BlockLocation(lineno=0, col=1),
        )
    if isinstance(obj, IdMeta):
        return IdMeta(id=obj.id, lineno=0)
    if isinstance(obj, IdEnd):
        return IdEnd(x=obj.x, route_chapter=obj.route_chapter, lineno=0)
    if isinstance(obj, NextDecl):
        return NextDecl(var_name=obj.var_name, target_id=obj.target_id, lineno=0)
    if isinstance(obj, Start):
        return Start(lineno=0)
    if isinstance(obj, End):
        return End(lineno=0)
    if isinstance(obj, If):
        return If(
            cond=obj.cond,
            branches=tuple(
                Branch(value=b.value, target=_normalize(b.target)) for b in obj.branches
            ),
        )
    # Text/In/Echo/NextId/CallExpression/DecoratorCall/DecoratorStop — 无 lineno
    return obj


def _read_chapter(name: str) -> str:
    return Path(REPO_ROOT, "chapters", name).read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════
# 1. parse_source
# ═══════════════════════════════════════════════════════════════════════


def test_parse_source_basic():
    """单块源码 → Story（1 block, id:start）。"""
    src = "```neon\nid:start\nnext: c1\nnode start\n雨夜。\nnode end\n```\n"
    story = parse_source(src)
    assert len(story.blocks) == 1
    block = story.blocks[0]
    assert isinstance(block.meta[0], IdMeta)
    assert block.meta[0].id == "start"
    assert len(block.next_table) == 1
    assert block.next_table[0].target_id == "c1"


def test_parse_source_multiple_blocks():
    """多块源码 → Story（按围栏顺序）。"""
    src = (
        "```neon\nid:start\nnext: c1\nnode start\nA\nnode end\n```\n\n"
        "```neon\nid:c1\nnode start\nB\nnode end\n```\n"
    )
    story = parse_source(src)
    assert len(story.blocks) == 2
    assert story.blocks[0].meta[0].id == "start"
    assert story.blocks[1].meta[0].id == "c1"


def test_parse_source_matches_load_story():
    """parse_source(text) 与 _load_story(path) 等价（chapter01_v1.md）。"""
    from core.engine.main import _load_story
    src = _read_chapter("chapter01_v1.md")
    s1 = parse_source(src)
    s2 = _load_story(str(Path(REPO_ROOT, "chapters", "chapter01_v1.md")))
    assert _normalize(s1) == _normalize(s2)


# ═══════════════════════════════════════════════════════════════════════
# 2. story_to_source —— 各节点类型 unparse
# ═══════════════════════════════════════════════════════════════════════


def test_story_to_source_id_meta_and_bare_next():
    """IdMeta + bare NextDecl → `id:start` + `next: c1`。"""
    block = _make_block(
        meta=(IdMeta(id="start", lineno=1),),
        next_table=(NextDecl(var_name=None, target_id="c1"),),
        body=(Text("雨夜。"),),
    )
    src = story_to_source(Story(blocks=(block,)))
    assert "id:start" in src
    assert "next: c1" in src
    assert "node start" in src
    assert "雨夜。" in src
    assert "node end" in src


def test_story_to_source_named_next_v1_arrow():
    """命名 NextDecl → `t_a ← next : ca`（v1 箭头）。"""
    block = _make_block(
        meta=(IdMeta(id="c1", lineno=1),),
        next_table=(
            NextDecl(var_name="t_a", target_id="ca"),
            NextDecl(var_name="t_b", target_id="cb"),
        ),
        body=(Text("x"),),
    )
    src = story_to_source(Story(blocks=(block,)))
    assert "t_a ← next : ca" in src
    assert "t_b ← next : cb" in src


def test_story_to_source_id_end_variants():
    """IdEnd 三种形态：end / endN / endN:chapterYY。"""
    b1 = _make_block(meta=(IdEnd(x=None, route_chapter=None),))
    b2 = _make_block(meta=(IdEnd(x=1, route_chapter=None),))
    b3 = _make_block(meta=(IdEnd(x=2, route_chapter="chapter02"),))
    src = story_to_source(Story(blocks=(b1, b2, b3)))
    assert "id:end\n" in src or "id:end" in src
    assert "id:end1" in src
    assert "id:end2:chapter02" in src


def test_story_to_source_in_node():
    """In 节点 → `node in → var` / `node in → var [opts]`。"""
    b1 = _make_block(body=(In(var="mood"),))
    b2 = _make_block(body=(In(var="pick", options=("a", "b")),))
    src = story_to_source(Story(blocks=(b1, b2)))
    assert "node in → mood" in src
    assert "node in → pick [a, b]" in src


def test_story_to_source_echo_var_and_parts():
    """Echo：单变量 → `node echo v`；拼接 → `node echo a + b`。"""
    b1 = _make_block(body=(Echo(var="mood"),))
    b2 = _make_block(body=(Echo(parts=("mood", "是啊。")),))
    src = story_to_source(Story(blocks=(b1, b2)))
    assert "node echo mood" in src
    assert "node echo mood + 是啊。" in src


def test_story_to_source_next_id():
    """NextId → `node <target>`。"""
    b = _make_block(body=(NextId(target_id="scene2"),))
    src = story_to_source(Story(blocks=(b,)))
    assert "node scene2" in src


def test_story_to_source_if_binary():
    """二元 If（2 NextDecl 分支，values 0,1）→ `node if cond [a,b]`（无空格）。"""
    block = _make_block(
        meta=(IdMeta(id="c1", lineno=1),),
        next_table=(
            NextDecl(var_name="t_a", target_id="ca"),
            NextDecl(var_name="t_b", target_id="cb"),
        ),
        body=(
            If(cond=("expr", "pick == 1"), branches=(
                Branch(value=0, target=NextDecl(var_name="t_a", target_id="ca")),
                Branch(value=1, target=NextDecl(var_name="t_b", target_id="cb")),
            )),
        ),
    )
    src = story_to_source(Story(blocks=(block,)))
    assert "node if pick == 1 [t_a,t_b]" in src


def test_story_to_source_if_multi_with_call_expr():
    """多元 If 含 CallExpression 分支 → `node if cond [0:echo x, 1:in -> y]`。"""
    block = _make_block(
        body=(
            If(cond=("var", "pick"), branches=(
                Branch(value=1, target=CallExpression(kind="echo", var="x")),
                Branch(value=2, target=CallExpression(kind="in", var="y")),
            )),
        ),
    )
    src = story_to_source(Story(blocks=(block,)))
    assert "node if pick [1:echo x, 2:in -> y]" in src


def test_story_to_source_decorator_call_and_stop():
    """DecoratorCall → `@name args`；DecoratorStop → `@name key` / `@name`。"""
    b1 = _make_block(body=(DecoratorCall(name="style", args=("bgm:rain.mp3",)),))
    b2 = _make_block(body=(DecoratorStop(name="style", key="bgm"),))
    b3 = _make_block(body=(DecoratorStop(name="style", key=""),))
    src = story_to_source(Story(blocks=(b1, b2, b3)))
    assert "@style bgm:rain.mp3" in src
    assert "@style bgm" in src


# ═══════════════════════════════════════════════════════════════════════
# 3. story_to_source roundtrip（chapter01_v1.md）
# ═══════════════════════════════════════════════════════════════════════


def test_roundtrip_chapter01_v1_normalized_equal():
    """chapter01_v1.md → parse → unparse → parse → 归一后 AST 等价。"""
    src = _read_chapter("chapter01_v1.md")
    story1 = parse_source(src)
    src2 = story_to_source(story1)
    story2 = parse_source(src2)
    assert _normalize(story1) == _normalize(story2)


def test_roundtrip_chapter01_v0_normalized_equal():
    """chapter01.md（v0 形态，含 route/endX/多元 If）→ roundtrip 等价。"""
    src = _read_chapter("chapter01.md")
    story1 = parse_source(src)
    src2 = story_to_source(story1)
    story2 = parse_source(src2)
    assert _normalize(story1) == _normalize(story2)


def test_roundtrip_double_unparse_stable():
    """二次 unparse 稳定：unparse(parse(unparse(src))) == unparse(parse(src))。"""
    src = _read_chapter("chapter01_v1.md")
    s1 = parse_source(story_to_source(parse_source(src)))
    s2 = parse_source(story_to_source(s1))
    assert _normalize(s1) == _normalize(s2)


# ═══════════════════════════════════════════════════════════════════════
# 4. graph_to_source
# ═══════════════════════════════════════════════════════════════════════


def test_graph_to_source_minimal_model():
    """最小 model（2 节点 + 1 边）→ 合法 neon 源码。"""
    m = NodeGraphModel()
    m.add_node(NodeData(id="start", title="start", preview="雨夜。", node_type=TYPE_ENTRY))
    m.add_node(NodeData(id="c1", title="c1", preview="敲门。", node_type=TYPE_NORMAL, x=0, y=120))
    m.add_edge(EdgeData(source_id="start", target_id="c1"))
    src = graph_to_source(m)
    # 能重新解析
    story = parse_source(src)
    assert len(story.blocks) == 2
    ids = [b.meta[0].id if b.meta else None for b in story.blocks]
    assert "start" in ids and "c1" in ids


def test_graph_to_source_single_bare_next():
    """单出边无 label → bare `next: x`。"""
    m = NodeGraphModel()
    m.add_node(NodeData(id="a", title="a", preview="", node_type=TYPE_NORMAL))
    m.add_node(NodeData(id="b", title="b", preview="", node_type=TYPE_NORMAL, x=220, y=0))
    m.add_edge(EdgeData(source_id="a", target_id="b"))
    src = graph_to_source(m)
    assert "next: b" in src
    assert "← next" not in src  # 无命名 next


def test_graph_to_source_multi_named_next():
    """多出边 → 全命名（互斥校验），label 作 var_name。"""
    m = NodeGraphModel()
    m.add_node(NodeData(id="hub", title="hub", preview="", node_type=TYPE_BRANCH))
    m.add_node(NodeData(id="a", title="a", preview="", node_type=TYPE_NORMAL))
    m.add_node(NodeData(id="b", title="b", preview="", node_type=TYPE_NORMAL))
    m.add_edge(EdgeData(source_id="hub", target_id="a", label="left"))
    m.add_edge(EdgeData(source_id="hub", target_id="b", label="right"))
    src = graph_to_source(m)
    assert "left ← next : a" in src
    assert "right ← next : b" in src
    # 能重新解析（命名 next 互斥校验通过）
    story = parse_source(src)
    assert len(story.blocks) == 3


def test_graph_to_source_roundtrip_nodes_preserved():
    """graph_to_source → parse → story_to_graph 后节点 id 保留。"""
    m = NodeGraphModel()
    m.add_node(NodeData(id="start", title="start", preview="p1", node_type=TYPE_ENTRY))
    m.add_node(NodeData(id="mid", title="mid", preview="p2", node_type=TYPE_NORMAL, x=0, y=120))
    m.add_node(NodeData(id="end", title="end", preview="p3", node_type=TYPE_ENDING, x=0, y=240))
    m.add_edge(EdgeData(source_id="start", target_id="mid"))
    m.add_edge(EdgeData(source_id="mid", target_id="end"))
    src = graph_to_source(m)
    story = parse_source(src)
    m2 = story_to_graph(story)
    ids = {n.id for n in m2.get_nodes()}
    assert {"start", "mid", "end"}.issubset(ids)


def test_graph_to_source_empty_model():
    """空 model → 空字符串。"""
    m = NodeGraphModel()
    assert graph_to_source(m) == ""


# ═══════════════════════════════════════════════════════════════════════
# 5. DslSync —— 双向编排
# ═══════════════════════════════════════════════════════════════════════


def test_dsl_sync_init_from_source():
    """从源码初始化 → 自动构造 model（节点 + 边）。"""
    src = _read_chapter("chapter01_v1.md")
    sync = DslSync(source=src)
    assert sync.source == src
    assert sync.model.node_count >= 4
    node_ids = {n.id for n in sync.model.get_nodes()}
    assert "start" in node_ids
    assert "c1" in node_ids


def test_dsl_sync_init_empty():
    """空初始化 → 空 model + 空源码。"""
    sync = DslSync()
    assert sync.source == ""
    assert sync.model.node_count == 0


def test_dsl_sync_update_from_source_rebuilds_model():
    """源码变更 → model 重建。"""
    sync = DslSync()
    src = _read_chapter("chapter01_v1.md")
    sync.update_from_source(src)
    assert sync.model.node_count >= 4
    assert "start" in {n.id for n in sync.model.get_nodes()}


def test_dsl_sync_update_from_graph_preserves_existing_body():
    """图变更（不动现有节点）→ 源码保留原有块体。

    用 chapter01_v1.md 初始化，update_from_graph 传回同结构的 model，
    源码应保留 If / Echo / 装饰器等原 body。
    """
    src = _read_chapter("chapter01_v1.md")
    sync = DslSync(source=src)
    # 传回同一个 model（无结构变更）
    sync.update_from_graph(sync.model)
    new_src = sync.source
    # 原 body 关键内容保留
    assert "node if pick == 1" in new_src
    assert "node echo mood" in new_src
    assert "@style bgm:rain.mp3" in new_src
    assert "雨夜。" in new_src


def test_dsl_sync_update_from_graph_adds_node():
    """图新增节点 → 源码新增块（preview 作 Text）。"""
    src = _read_chapter("chapter01_v1.md")
    sync = DslSync(source=src)
    original_block_count = len(parse_source(sync.source).blocks)

    # 在 model 上新增节点
    new_model = sync.model
    new_model.add_node(NodeData(id="new_scene", title="new_scene",
                                preview="新场景。", node_type=TYPE_NORMAL, x=500, y=500))
    sync.update_from_graph(new_model)

    new_blocks = parse_source(sync.source).blocks
    assert len(new_blocks) == original_block_count + 1
    new_ids = {extract_block_id(b) for b in new_blocks}
    assert "new_scene" in new_ids
    # 新块含 preview 作 Text
    new_block = next(b for b in new_blocks if extract_block_id(b) == "new_scene")
    texts = [n.content for n in new_block.body if isinstance(n, Text)]
    assert any("新场景" in t for t in texts)


def test_dsl_sync_update_from_graph_removes_node():
    """图删除节点 → 源码对应块消失。"""
    src = _read_chapter("chapter01_v1.md")
    sync = DslSync(source=src)
    original_block_count = len(parse_source(sync.source).blocks)

    new_model = sync.model
    # 删除 cb 节点（chapter01_v1 有 cb 块）
    assert new_model.has_node("cb")
    new_model.remove_node("cb")
    sync.update_from_graph(new_model)

    new_blocks = parse_source(sync.source).blocks
    assert len(new_blocks) == original_block_count - 1
    new_ids = {extract_block_id(b) for b in new_blocks}
    assert "cb" not in new_ids


def test_dsl_sync_roundtrip_source_graph_source():
    """source → graph → source'：原有节点 id 全保留，body 关键内容保留。"""
    src = _read_chapter("chapter01_v1.md")
    sync = DslSync(source=src)
    sync.update_from_graph(sync.model)
    # 重新解析同步后的源码
    story = parse_source(sync.source)
    ids = {extract_block_id(b) for b in story.blocks}
    # 原 chapter01_v1 的节点都在
    assert "start" in ids
    assert "c1" in ids


def test_dsl_sync_update_from_graph_keeps_unreachable_blocks():
    """孤立节点（无入无出边）也生成块。"""
    sync = DslSync()
    m = NodeGraphModel()
    m.add_node(NodeData(id="lonely", title="lonely", preview="孤块。", node_type=TYPE_NORMAL))
    sync.update_from_graph(m)
    story = parse_source(sync.source)
    assert any(extract_block_id(b) == "lonely" for b in story.blocks)


# ═══════════════════════════════════════════════════════════════════════
# 6. 模块导入
# ═══════════════════════════════════════════════════════════════════════


def test_dsl_sync_module_exports():
    """dsl_sync 公开 API 齐全。"""
    from editor import dsl_sync
    for name in ("parse_source", "story_to_source", "graph_to_source", "DslSync"):
        assert hasattr(dsl_sync, name)
