"""v4-01 · NodeGraphModel 节点图数据模型测试（#109）。

验证 issue #109 模型层验收点：
- Block → NodeData / EdgeData 转换（id / preview / type / edges）
- 节点类型分类（normal / branch / route / ending / entry）
- NodeGraphModel 增删节点 / 增删边 / 移动 / 级联删除
- 自动布局（分层 + 无严重重叠）
- 序列化 roundtrip
- story_to_graph 端到端（chapter01_v1.md）

纯 Python 测试（无 PyQt6 依赖）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")

from core.engine.ast_nodes import (
    Block, BlockLocation, IdMeta, IdEnd, NextDecl, Text, In, Echo, If, Branch,
    NextId, Start, End,
)
from core.engine.main import _load_story
from editor.node_graph_model import (
    NodeData, EdgeData, NodeGraphModel,
    TYPE_NORMAL, TYPE_BRANCH, TYPE_ROUTE, TYPE_ENDING, TYPE_ENTRY,
    TYPE_COLORS, NODE_WIDTH, NODE_HEIGHT,
    extract_block_id, extract_block_preview, classify_block,
    block_to_edges, block_to_node, story_to_graph,
)


# ─── 辅助：构造 Block ──────────────────────────────────────────────────────


def _make_block(meta=(), next_table=(), body=()) -> Block:
    """构造 Block（自动在 body 首尾加 Start/End sentinel）。"""
    full_body = (Start(),) + tuple(body) + (End(),)
    return Block(meta=tuple(meta), next_table=tuple(next_table),
                 body=full_body, loc=BlockLocation(lineno=1, col=1))


# ═══════════════════════════════════════════════════════════════════════
# 1. classify_block —— 5 种节点类型
# ═══════════════════════════════════════════════════════════════════════


def test_classify_entry_block():
    """id:start → TYPE_ENTRY。"""
    block = _make_block(meta=(IdMeta(id="start", lineno=1),), body=(Text("雨夜。"),))
    assert classify_block(block) == TYPE_ENTRY


def test_classify_normal_block():
    """普通 id + Text → TYPE_NORMAL。"""
    block = _make_block(meta=(IdMeta(id="c1", lineno=1),), body=(Text("文本。"),))
    assert classify_block(block) == TYPE_NORMAL


def test_classify_branch_block():
    """含 If → TYPE_BRANCH。"""
    if_node = If(cond=("expr", "pick==1"), branches=(
        Branch(value=0, target=NextDecl(var_name=None, target_id="ca")),
        Branch(value=1, target=NextDecl(var_name=None, target_id="cb")),
    ))
    block = _make_block(meta=(IdMeta(id="c1", lineno=1),), body=(Text("x"), if_node))
    assert classify_block(block) == TYPE_BRANCH


def test_classify_route_block():
    """id:end1:chapter02 → TYPE_ROUTE。"""
    block = _make_block(meta=(IdEnd(x=1, route_chapter="chapter02", lineno=1),))
    assert classify_block(block) == TYPE_ROUTE


def test_classify_ending_block_with_x():
    """id:end1（无 chapter）→ TYPE_ENDING。"""
    block = _make_block(meta=(IdEnd(x=1, route_chapter=None, lineno=1),))
    assert classify_block(block) == TYPE_ENDING


def test_classify_ending_block_bare_end():
    """id:end（无 x 无 chapter）→ TYPE_ENDING。"""
    block = _make_block(meta=(IdEnd(x=None, route_chapter=None, lineno=1),))
    assert classify_block(block) == TYPE_ENDING


def test_classify_priority_route_over_branch():
    """IdEnd(route) 优先于 If（即便有 If 也是 route）。"""
    if_node = If(cond=("expr", "x"), branches=(Branch(0, NextDecl(None, "y")),))
    block = _make_block(
        meta=(IdEnd(x=1, route_chapter="ch2", lineno=1),),
        body=(if_node,),
    )
    assert classify_block(block) == TYPE_ROUTE


# ═══════════════════════════════════════════════════════════════════════
# 2. extract_block_id
# ═══════════════════════════════════════════════════════════════════════


def test_extract_id_from_idmeta():
    block = _make_block(meta=(IdMeta(id="c1", lineno=1),))
    assert extract_block_id(block) == "c1"


def test_extract_id_start():
    block = _make_block(meta=(IdMeta(id="start", lineno=1),))
    assert extract_block_id(block) == "start"


def test_extract_id_from_end_with_x():
    block = _make_block(meta=(IdEnd(x=3, route_chapter=None, lineno=1),))
    assert extract_block_id(block) == "end3"


def test_extract_id_from_end_bare():
    block = _make_block(meta=(IdEnd(x=None, route_chapter=None, lineno=1),))
    assert extract_block_id(block) == "end"


def test_extract_id_from_route():
    block = _make_block(meta=(IdEnd(x=2, route_chapter="chapter05", lineno=1),))
    assert extract_block_id(block) == "end2:chapter05"


def test_extract_id_none_when_empty_meta():
    block = _make_block(meta=(), body=(Text("x"),))
    assert extract_block_id(block) is None


# ═══════════════════════════════════════════════════════════════════════
# 3. extract_block_preview
# ═══════════════════════════════════════════════════════════════════════


def test_preview_first_text():
    block = _make_block(body=(Text("雨夜。\n"), Text("第二行。\n")))
    assert extract_block_preview(block) == "雨夜。"


def test_preview_truncates_long_text():
    long_text = "这是一个非常非常非常非常非常长的文本内容超过二十四字符"
    block = _make_block(body=(Text(long_text + "\n"),))
    preview = extract_block_preview(block)
    assert preview.endswith("…")
    assert len(preview) == 25  # 24 字符 + …


def test_preview_in_node():
    block = _make_block(body=(In(var="mood", options=()),))
    assert extract_block_preview(block) == "[输入] mood"


def test_preview_echo_node():
    block = _make_block(body=(Echo(var="p_mood"),))
    assert extract_block_preview(block) == "[echo]"


def test_preview_if_node():
    if_node = If(cond=("expr", "x"), branches=(Branch(0, NextDecl(None, "y")),))
    block = _make_block(body=(if_node,))
    assert extract_block_preview(block) == "[分支]"


def test_preview_empty_body():
    block = _make_block(body=())
    assert extract_block_preview(block) == ""


# ═══════════════════════════════════════════════════════════════════════
# 4. block_to_edges
# ═══════════════════════════════════════════════════════════════════════


def test_edges_from_next_table_bare():
    """next:yyy → 边 label=""。"""
    block = _make_block(
        meta=(IdMeta(id="start", lineno=1),),
        next_table=(NextDecl(var_name=None, target_id="c1"),),
    )
    edges = block_to_edges(block)
    assert len(edges) == 1
    assert edges[0].source_id == "start"
    assert edges[0].target_id == "c1"
    assert edges[0].label == ""


def test_edges_from_next_table_named():
    """var←next:yyy → 边 label="var"。"""
    block = _make_block(
        meta=(IdMeta(id="c1", lineno=1),),
        next_table=(
            NextDecl(var_name="t_a", target_id="ca"),
            NextDecl(var_name="t_b", target_id="cb"),
        ),
    )
    edges = block_to_edges(block)
    assert len(edges) == 2
    labels = sorted(e.label for e in edges)
    assert labels == ["t_a", "t_b"]


def test_edges_from_if_branches():
    """If.branches (NextDecl) → 边 label=str(value)。"""
    if_node = If(
        cond=("expr", "pick==1"),
        branches=(
            Branch(value=1, target=NextDecl(var_name="t_a", target_id="ca")),
            Branch(value=2, target=NextDecl(var_name="t_b", target_id="cb")),
        ),
    )
    block = _make_block(meta=(IdMeta(id="c1", lineno=1),), body=(if_node,))
    edges = block_to_edges(block)
    assert len(edges) == 2
    targets = sorted(e.target_id for e in edges)
    assert targets == ["ca", "cb"]
    labels = sorted(e.label for e in edges)
    assert labels == ["1", "2"]


def test_edges_from_nextid():
    """body 内 NextId → 边 label=""。"""
    block = _make_block(
        meta=(IdMeta(id="c1", lineno=1),),
        body=(NextId(target_id="c2"),),
    )
    edges = block_to_edges(block)
    assert len(edges) == 1
    assert edges[0].target_id == "c2"


def test_edges_dedup_same_source_target_label():
    """同 (source, target, label) 去重。"""
    if_node = If(
        cond=("expr", "x"),
        branches=(
            Branch(1, NextDecl(var_name=None, target_id="ca")),
            Branch(2, NextDecl(var_name=None, target_id="ca")),  # 同 target
        ),
    )
    block = _make_block(
        meta=(IdMeta(id="c1", lineno=1),),
        next_table=(NextDecl(var_name=None, target_id="ca"),),  # 又一条到 ca
        body=(if_node,),
    )
    edges = block_to_edges(block)
    # 到 ca 的：next_table(label="") + branch1(label="1") + branch2(label="2")
    # next_table label="" 和 branch label="1"/"2" 不同 → 3 条
    assert len(edges) == 3
    labels = sorted(e.label for e in edges)
    assert labels == ["", "1", "2"]


def test_edges_no_id_returns_empty():
    block = _make_block(meta=(), body=(Text("x"),))
    assert block_to_edges(block) == []


# ═══════════════════════════════════════════════════════════════════════
# 5. block_to_node
# ═══════════════════════════════════════════════════════════════════════


def test_block_to_node_full():
    block = _make_block(
        meta=(IdMeta(id="start", lineno=1),),
        body=(Text("雨夜。\n"),),
    )
    node = block_to_node(block)
    assert node is not None
    assert node.id == "start"
    assert node.title == "start"
    assert node.preview == "雨夜。"
    assert node.node_type == TYPE_ENTRY
    assert node.x == 0.0 and node.y == 0.0


def test_block_to_node_no_id_returns_none():
    block = _make_block(meta=(), body=(Text("x"),))
    assert block_to_node(block) is None


# ═══════════════════════════════════════════════════════════════════════
# 6. story_to_graph —— 端到端 chapter01_v1.md
# ═══════════════════════════════════════════════════════════════════════


def test_story_to_graph_chapter01_v1():
    """chapter01_v1.md → 节点图：含 start / c1 / ca / cb / end 节点 + 边。"""
    chapter_path = Path(REPO_ROOT) / "chapters" / "chapter01_v1.md"
    story = _load_story(str(chapter_path))
    model = story_to_graph(story)

    # 节点：start, c1, ca, cb, end（chapter01_v1 有 5 个块）
    assert model.node_count >= 4
    node_ids = {n.id for n in model.get_nodes()}
    assert "start" in node_ids
    assert "c1" in node_ids
    assert "ca" in node_ids
    assert "cb" in node_ids

    # start 是 entry
    start = model.get_node("start")
    assert start is not None
    assert start.node_type == TYPE_ENTRY
    assert "雨夜" in start.preview

    # start → c1 边（next: c1）
    out_edges = model.get_out_edges("start")
    targets = {e.target_id for e in out_edges}
    assert "c1" in targets

    # c1 → ca / cb 边（If 分支）
    c1_out = model.get_out_edges("c1")
    c1_targets = {e.target_id for e in c1_out}
    assert "ca" in c1_targets
    assert "cb" in c1_targets

    # 自动布局已执行（坐标非全 0）
    nodes = model.get_nodes()
    assert any(n.x != 0.0 or n.y != 0.0 for n in nodes)


def test_story_to_graph_auto_layout_no_overlap():
    """自动布局后，同层节点 x 不同（无严重重叠）。"""
    chapter_path = Path(REPO_ROOT) / "chapters" / "chapter01_v1.md"
    story = _load_story(str(chapter_path))
    model = story_to_graph(story)

    # 检查：任意两节点中心距离 > NODE_WIDTH/2（同层水平间距足够）
    nodes = model.get_nodes()
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            a, b = nodes[i], nodes[j]
            # 同 y 层 → x 差应 > NODE_WIDTH
            if abs(a.y - b.y) < 1.0:
                assert abs(a.x - b.x) >= NODE_WIDTH * 0.9, (
                    f"节点 {a.id} 与 {b.id} 同层 x 太近: {a.x} vs {b.x}"
                )


def test_story_to_graph_entry_at_layer_zero():
    """入口节点应在 y=0 层。"""
    chapter_path = Path(REPO_ROOT) / "chapters" / "chapter01_v1.md"
    story = _load_story(str(chapter_path))
    model = story_to_graph(story)
    start = model.get_node("start")
    assert start is not None
    assert start.y == 0.0


# ═══════════════════════════════════════════════════════════════════════
# 7. NodeGraphModel —— 节点操作
# ═══════════════════════════════════════════════════════════════════════


def test_model_add_node():
    model = NodeGraphModel()
    node = NodeData(id="n1", title="n1", preview="x", node_type=TYPE_NORMAL)
    assert model.add_node(node) is True
    assert model.node_count == 1
    assert model.has_node("n1")


def test_model_add_node_duplicate():
    model = NodeGraphModel()
    node = NodeData(id="n1", title="n1", preview="x", node_type=TYPE_NORMAL)
    model.add_node(node)
    assert model.add_node(node) is False  # 重复
    assert model.node_count == 1


def test_model_remove_node():
    model = NodeGraphModel()
    model.add_node(NodeData(id="n1", title="n1", preview="x", node_type=TYPE_NORMAL))
    assert model.remove_node("n1") is True
    assert model.node_count == 0
    assert not model.has_node("n1")


def test_model_remove_node_nonexistent():
    model = NodeGraphModel()
    assert model.remove_node("nope") is False


def test_model_remove_node_cascades_edges():
    """删节点 → 关联出入边全删。"""
    model = NodeGraphModel()
    model.add_node(NodeData(id="a", title="a", preview="", node_type=TYPE_NORMAL))
    model.add_node(NodeData(id="b", title="b", preview="", node_type=TYPE_NORMAL))
    model.add_node(NodeData(id="c", title="c", preview="", node_type=TYPE_NORMAL))
    model.add_edge(EdgeData(source_id="a", target_id="b"))
    model.add_edge(EdgeData(source_id="b", target_id="c"))
    assert model.edge_count == 2

    assert model.remove_node("b") is True
    assert model.edge_count == 0  # a→b 和 b→c 都删


def test_model_move_node():
    model = NodeGraphModel()
    model.add_node(NodeData(id="n1", title="n1", preview="", node_type=TYPE_NORMAL))
    assert model.move_node("n1", 100, 50) is True
    node = model.get_node("n1")
    assert node.x == 100.0 and node.y == 50.0


def test_model_move_node_nonexistent():
    model = NodeGraphModel()
    assert model.move_node("nope", 1, 2) is False


def test_model_update_node_title():
    model = NodeGraphModel()
    model.add_node(NodeData(id="n1", title="n1", preview="old", node_type=TYPE_NORMAL))
    assert model.update_node("n1", title="新标题") is True
    node = model.get_node("n1")
    assert node.title == "新标题"
    assert node.preview == "old"  # 未改


def test_model_update_node_preview():
    model = NodeGraphModel()
    model.add_node(NodeData(id="n1", title="n1", preview="old", node_type=TYPE_NORMAL))
    assert model.update_node("n1", preview="new") is True
    assert model.get_node("n1").preview == "new"


def test_model_get_node_returns_copy():
    """get_node 返回副本，外部修改不影响模型。"""
    model = NodeGraphModel()
    model.add_node(NodeData(id="n1", title="orig", preview="", node_type=TYPE_NORMAL))
    node = model.get_node("n1")
    # frozen dataclass 不能改字段，但验证返回的是新对象
    assert node is not model._nodes["n1"]


# ═══════════════════════════════════════════════════════════════════════
# 8. NodeGraphModel —— 边操作
# ═══════════════════════════════════════════════════════════════════════


def test_model_add_edge():
    model = NodeGraphModel()
    model.add_node(NodeData(id="a", title="a", preview="", node_type=TYPE_NORMAL))
    model.add_node(NodeData(id="b", title="b", preview="", node_type=TYPE_NORMAL))
    assert model.add_edge(EdgeData(source_id="a", target_id="b", label="")) is True
    assert model.edge_count == 1


def test_model_add_edge_missing_endpoint():
    model = NodeGraphModel()
    model.add_node(NodeData(id="a", title="a", preview="", node_type=TYPE_NORMAL))
    # target 不存在
    assert model.add_edge(EdgeData(source_id="a", target_id="b")) is False
    # source 不存在
    assert model.add_edge(EdgeData(source_id="x", target_id="a")) is False
    assert model.edge_count == 0


def test_model_add_edge_parallel_allowed():
    """同 source→target 不同 label 的平行边允许。"""
    model = NodeGraphModel()
    model.add_node(NodeData(id="a", title="a", preview="", node_type=TYPE_NORMAL))
    model.add_node(NodeData(id="b", title="b", preview="", node_type=TYPE_NORMAL))
    model.add_edge(EdgeData(source_id="a", target_id="b", label="1"))
    model.add_edge(EdgeData(source_id="a", target_id="b", label="2"))
    assert model.edge_count == 2


def test_model_remove_edge():
    model = NodeGraphModel()
    model.add_node(NodeData(id="a", title="a", preview="", node_type=TYPE_NORMAL))
    model.add_node(NodeData(id="b", title="b", preview="", node_type=TYPE_NORMAL))
    model.add_edge(EdgeData(source_id="a", target_id="b", label="x"))
    assert model.remove_edge("a", "b", "x") == 1
    assert model.edge_count == 0


def test_model_remove_edge_no_match():
    model = NodeGraphModel()
    model.add_node(NodeData(id="a", title="a", preview="", node_type=TYPE_NORMAL))
    model.add_node(NodeData(id="b", title="b", preview="", node_type=TYPE_NORMAL))
    model.add_edge(EdgeData(source_id="a", target_id="b", label="x"))
    assert model.remove_edge("a", "b", "y") == 0  # label 不匹配
    assert model.edge_count == 1


def test_model_get_out_in_edges():
    model = NodeGraphModel()
    model.add_node(NodeData(id="a", title="a", preview="", node_type=TYPE_NORMAL))
    model.add_node(NodeData(id="b", title="b", preview="", node_type=TYPE_NORMAL))
    model.add_node(NodeData(id="c", title="c", preview="", node_type=TYPE_NORMAL))
    model.add_edge(EdgeData(source_id="a", target_id="b"))
    model.add_edge(EdgeData(source_id="b", target_id="c"))

    out_b = model.get_out_edges("b")
    assert len(out_b) == 1 and out_b[0].target_id == "c"

    in_b = model.get_in_edges("b")
    assert len(in_b) == 1 and in_b[0].source_id == "a"


def test_model_find_entry_nodes():
    model = NodeGraphModel()
    model.add_node(NodeData(id="start", title="start", preview="", node_type=TYPE_ENTRY))
    model.add_node(NodeData(id="c1", title="c1", preview="", node_type=TYPE_NORMAL))
    model.add_node(NodeData(id="start2", title="s2", preview="", node_type=TYPE_ENTRY))
    entries = model.find_entry_nodes()
    assert entries == ["start", "start2"]


# ═══════════════════════════════════════════════════════════════════════
# 9. 自动布局
# ═══════════════════════════════════════════════════════════════════════


def test_auto_layout_empty_model():
    model = NodeGraphModel()
    model.auto_layout()  # 不应抛错
    assert model.node_count == 0


def test_auto_layout_single_node():
    model = NodeGraphModel()
    model.add_node(NodeData(id="n1", title="n1", preview="", node_type=TYPE_ENTRY))
    model.auto_layout()
    node = model.get_node("n1")
    assert node.x == 0.0 and node.y == 0.0


def test_auto_layout_chain():
    """a→b→c 链式：a 层 0，b 层 1，c 层 2。"""
    model = NodeGraphModel()
    for nid in ("a", "b", "c"):
        model.add_node(NodeData(id=nid, title=nid, preview="",
                                node_type=TYPE_ENTRY if nid == "a" else TYPE_NORMAL))
    model.add_edge(EdgeData(source_id="a", target_id="b"))
    model.add_edge(EdgeData(source_id="b", target_id="c"))
    model.auto_layout()

    a, b, c = model.get_node("a"), model.get_node("b"), model.get_node("c")
    assert a.y == 0.0
    assert b.y > a.y
    assert c.y > b.y


def test_auto_layout_isolated_node_goes_bottom():
    """孤立节点放最底层。"""
    model = NodeGraphModel()
    model.add_node(NodeData(id="start", title="s", preview="", node_type=TYPE_ENTRY))
    model.add_node(NodeData(id="c1", title="c1", preview="", node_type=TYPE_NORMAL))
    model.add_node(NodeData(id="iso", title="iso", preview="", node_type=TYPE_NORMAL))
    model.add_edge(EdgeData(source_id="start", target_id="c1"))
    model.auto_layout()

    iso = model.get_node("iso")
    c1 = model.get_node("c1")
    assert iso.y > c1.y  # 孤立在最底层


# ═══════════════════════════════════════════════════════════════════════
# 10. 序列化 roundtrip
# ═══════════════════════════════════════════════════════════════════════


def test_serialization_roundtrip():
    model = NodeGraphModel()
    model.add_node(NodeData(id="a", title="A", preview="x", node_type=TYPE_ENTRY, x=10, y=20))
    model.add_node(NodeData(id="b", title="B", preview="y", node_type=TYPE_BRANCH, x=30, y=40))
    model.add_edge(EdgeData(source_id="a", target_id="b", label="lbl"))

    data = model.to_dict()
    model2 = NodeGraphModel.from_dict(data)

    assert model2.node_count == 2
    assert model2.edge_count == 1
    a2 = model2.get_node("a")
    assert a2.title == "A" and a2.x == 10 and a2.y == 20 and a2.node_type == TYPE_ENTRY
    b2 = model2.get_node("b")
    assert b2.node_type == TYPE_BRANCH
    edges = model2.get_edges()
    assert edges[0].label == "lbl"


# ═══════════════════════════════════════════════════════════════════════
# 11. 类型颜色 & 常量
# ═══════════════════════════════════════════════════════════════════════


def test_type_colors_all_types_covered():
    """5 种类型都有颜色。"""
    for t in (TYPE_NORMAL, TYPE_BRANCH, TYPE_ROUTE, TYPE_ENDING, TYPE_ENTRY):
        assert t in TYPE_COLORS
        assert TYPE_COLORS[t].startswith("#")


def test_node_dimensions_positive():
    assert NODE_WIDTH > 0 and NODE_HEIGHT > 0


# ═══════════════════════════════════════════════════════════════════════
# 12. 模块导入（无 PyQt6 依赖）
# ═══════════════════════════════════════════════════════════════════════


def test_module_imports_without_pyqt6():
    """editor.node_graph_model 不依赖 PyQt6（D3 决策延伸）。"""
    import importlib
    mod = importlib.import_module("editor.node_graph_model")
    assert hasattr(mod, "NodeGraphModel")
    assert hasattr(mod, "story_to_graph")
