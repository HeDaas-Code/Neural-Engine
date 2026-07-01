"""NodeGraphModel —— v4-01 节点图数据模型（#109）。

职责：
- 把 neon Story（解析后的 Block 列表）转换为节点图数据（NodeData + EdgeData）
- 提供节点类型分类（normal / branch / route / ending / entry）
- 提供基础图操作：增删节点、增删边、移动节点位置
- 提供自动布局（分层布局，避免严重重叠）
- 纯 Python（无 PyQt6 依赖），便于测试 + 与视图层解耦

设计：
- NodeData / EdgeData 用 frozen+slots dataclass（不可变，仿 ast_nodes 风格）
- NodeGraphModel 可变（持 dict[id→NodeData] + list[EdgeData]），位置可改
- classify_block 基于 Block.meta（IdEnd → route/ending）+ Block.body（If → branch）
- 边来源：next_table（NextDecl）+ body 内 If.branches（NextDecl）+ body 内 NextId

集成点（视图层 node_graph_view.py）：
- 视图从 NodeGraphModel 读 nodes/edges 渲染
- 用户拖拽 → model.move_node(id, x, y)
- 用户新建 → model.add_node / add_edge
- 双击编辑 → model.get_node(id) 取数据 + 更新 title/preview
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from typing import Optional

from core.engine.ast_nodes import (
    Block, Story, IdMeta, IdEnd, If, NextId, NextDecl, Branch, Text, Echo, In,
    Start, End, DecoratorCall, DecoratorStop, CallExpression,
)

logger = logging.getLogger(__name__)


# ─── 节点类型常量 ───────────────────────────────────────────────────────────

# normal: 普通节点（Text/Echo/In/NextId，无 If）
# branch: 分支节点（含 If）
# route:  路由节点（id:endX:chapterYY → 跨章节）
# ending: 结局节点（id:end / id:endX → 本章节结局）
# entry:  入口节点（id:start）—— 优先级高于 normal
TYPE_NORMAL = "normal"
TYPE_BRANCH = "branch"
TYPE_ROUTE = "route"
TYPE_ENDING = "ending"
TYPE_ENTRY = "entry"

# 类型 → 显示颜色（hex，视图层用；模型层只存字符串，不依赖 Qt）
TYPE_COLORS: dict[str, str] = {
    TYPE_ENTRY: "#4a9eff",   # 蓝
    TYPE_NORMAL: "#9aa0a6",  # 灰
    TYPE_BRANCH: "#f9a825",  # 橙
    TYPE_ROUTE: "#8e44ad",   # 紫
    TYPE_ENDING: "#e74c3c",  # 红
}

# 节点默认尺寸（视图层渲染用；模型层存位置不存尺寸）
NODE_WIDTH = 160
NODE_HEIGHT = 64


# ─── 数据结构 ───────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class NodeData:
    """节点图中的一个节点（对应一个 neon Block）。

    Attributes:
        id: 节点 ID（Block 的 id:start / id:xxx / id:endX）；新建无源时为生成 id。
        title: 节点标题（默认=id，双击编辑可改显示名）。
        preview: 首行文本预览（截断到 ~24 字符）。
        node_type: TYPE_* 常量。
        x / y: 画布坐标（视图层渲染位置）。
    """
    id: str
    title: str
    preview: str
    node_type: str
    x: float = 0.0
    y: float = 0.0


@dataclass(frozen=True, slots=True)
class EdgeData:
    """节点图中的一条边（对应一个 next 跳转 / If 分支 / NextId）。

    Attributes:
        source_id: 起点节点 ID。
        target_id: 终点节点 ID。
        label: 边标签（命名 next 的 var_name / If 分支的 value；空=普通 next）。
    """
    source_id: str
    target_id: str
    label: str = ""


# ─── Block → 节点图 转换工具 ────────────────────────────────────────────────


def extract_block_id(block: Block) -> Optional[str]:
    """从 Block.meta 提取节点 ID。

    优先级：IdMeta.id（含 "start"）> IdEnd 的合成 id。
    IdEnd 无显式 id 字段，按约定合成 "end" / "endX" / "endX:chapterYY"。
    """
    for item in block.meta:
        if isinstance(item, IdMeta):
            return item.id
    # 仅 IdEnd（如 id:end / id:end1:chapter02）
    for item in block.meta:
        if isinstance(item, IdEnd):
            if item.route_chapter is not None:
                return f"end{item.x}:{item.route_chapter}" if item.x is not None else f"end:{item.route_chapter}"
            return f"end{item.x}" if item.x is not None else "end"
    return None


def extract_block_preview(block: Block) -> str:
    """取 Block.body 首个 Text 内容作为预览（截断到 24 字符，去行尾空白）。"""
    for node in block.body:
        if isinstance(node, Text):
            text = node.content.strip()
            if len(text) > 24:
                return text[:24] + "…"
            return text
    # 无 Text → 看 In/Echo 提示
    for node in block.body:
        if isinstance(node, In):
            return f"[输入] {node.var}"
        if isinstance(node, Echo):
            return "[echo]"
        if isinstance(node, If):
            return "[分支]"
    return ""


def classify_block(block: Block) -> str:
    """分类 Block 类型 → TYPE_* 常量。

    优先级：entry（id:start）> route（id:endX:chapterYY）> ending（id:end/endX）
            > branch（含 If）> normal。
    """
    # 1. 检查 IdEnd（route / ending）
    for item in block.meta:
        if isinstance(item, IdEnd):
            if item.route_chapter is not None:
                return TYPE_ROUTE
            return TYPE_ENDING
    # 2. 检查 entry（id:start）
    for item in block.meta:
        if isinstance(item, IdMeta) and item.id == "start":
            return TYPE_ENTRY
    # 3. 检查 branch（含 If）
    for node in block.body:
        if isinstance(node, If):
            return TYPE_BRANCH
    # 4. 默认 normal
    return TYPE_NORMAL


def block_to_edges(block: Block) -> list[EdgeData]:
    """从 Block 提取所有出边（next_table + If.branches + NextId）。

    去重：同 (source, target, label) 只保留一条。
    忽略 target_id 指向不存在节点的情况（视图层会标记悬空边，模型层照存）。
    """
    source_id = extract_block_id(block)
    if source_id is None:
        return []
    edges: list[EdgeData] = []
    seen: set[tuple[str, str, str]] = set()

    def _add(target_id: str, label: str) -> None:
        key = (source_id, target_id, label)
        if key in seen:
            return
        seen.add(key)
        edges.append(EdgeData(source_id=source_id, target_id=target_id, label=label))

    # 1. next_table（NextDecl）
    for decl in block.next_table:
        _add(decl.target_id, decl.var_name or "")

    # 2. body 内 If.branches（Branch.target 为 NextDecl 时）
    for node in block.body:
        if isinstance(node, If):
            for br in node.branches:
                if isinstance(br.target, NextDecl):
                    _add(br.target.target_id, str(br.value))

    # 3. body 内 NextId（显式跳转 node xxx）
    for node in block.body:
        if isinstance(node, NextId):
            _add(node.target_id, "")

    return edges


def block_to_node(block: Block) -> Optional[NodeData]:
    """Block → NodeData（位置默认 0,0，需后续 layout）。无 id 返回 None。"""
    nid = extract_block_id(block)
    if nid is None:
        return None
    return NodeData(
        id=nid,
        title=nid,
        preview=extract_block_preview(block),
        node_type=classify_block(block),
    )


def story_to_graph(story: Story) -> "NodeGraphModel":
    """从 Story 构造 NodeGraphModel（含节点 + 边 + 自动布局）。"""
    model = NodeGraphModel()
    for block in story.blocks:
        node = block_to_node(block)
        if node is not None:
            model.add_node(node)
    for block in story.blocks:
        for edge in block_to_edges(block):
            model.add_edge(edge)
    model.auto_layout()
    return model


# ─── NodeGraphModel ─────────────────────────────────────────────────────────


class NodeGraphModel:
    """节点图可变模型（持节点 dict + 边 list）。

    用法：
        model = NodeGraphModel()
        model.add_node(NodeData(id="start", title="start", preview="雨夜。", node_type=TYPE_ENTRY))
        model.add_edge(EdgeData(source_id="start", target_id="c1"))
        model.move_node("start", 100, 50)
        model.remove_node("start")  # 同时移除关联边

        # 从 Story 构造
        model = story_to_graph(story)

    约定：
    - 节点 id 唯一（add_node 重复 id → False，不覆盖）
    - 边不去重（允许平行边：同 source→target 多 label）；但 story_to_graph 内部去重
    - remove_node 级联删除关联边
    - 所有查询返回副本（防外部修改）
    """

    def __init__(self):
        self._nodes: dict[str, NodeData] = {}
        self._edges: list[EdgeData] = []

    # ─── 节点操作 ──────────────────────────────────────────────────────

    def add_node(self, node: NodeData) -> bool:
        """新增节点。重复 id → False（不覆盖）。"""
        if node.id in self._nodes:
            return False
        self._nodes[node.id] = node
        return True

    def remove_node(self, node_id: str) -> bool:
        """删除节点 + 级联删除关联边。不存在 → False。"""
        if node_id not in self._nodes:
            return False
        del self._nodes[node_id]
        self._edges = [
            e for e in self._edges
            if e.source_id != node_id and e.target_id != node_id
        ]
        return True

    def move_node(self, node_id: str, x: float, y: float) -> bool:
        """移动节点位置。不存在 → False。"""
        node = self._nodes.get(node_id)
        if node is None:
            return False
        self._nodes[node_id] = replace(node, x=float(x), y=float(y))
        return True

    def update_node(self, node_id: str, title: Optional[str] = None,
                    preview: Optional[str] = None) -> bool:
        """更新节点 title / preview（双击编辑用）。不存在 → False。"""
        node = self._nodes.get(node_id)
        if node is None:
            return False
        new_title = title if title is not None else node.title
        new_preview = preview if preview is not None else node.preview
        self._nodes[node_id] = replace(node, title=new_title, preview=new_preview)
        return True

    def get_node(self, node_id: str) -> Optional[NodeData]:
        """取节点（返回副本）。不存在 → None。"""
        node = self._nodes.get(node_id)
        return replace(node) if node is not None else None

    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    # ─── 边操作 ──────────────────────────────────────────────────────

    def add_edge(self, edge: EdgeData) -> bool:
        """新增边。要求 source/target 节点存在，否则 False。
        允许平行边（同 source→target 不同 label）。
        """
        if edge.source_id not in self._nodes or edge.target_id not in self._nodes:
            return False
        self._edges.append(edge)
        return True

    def remove_edge(self, source_id: str, target_id: str, label: str = "") -> int:
        """删除匹配的边（同 source/target/label）。返回删除数。"""
        before = len(self._edges)
        self._edges = [
            e for e in self._edges
            if not (e.source_id == source_id and e.target_id == target_id and e.label == label)
        ]
        return before - len(self._edges)

    # ─── 查询 ──────────────────────────────────────────────────────

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    def get_nodes(self) -> list[NodeData]:
        """取所有节点（按 id 排序，返回副本列表）。"""
        return [replace(self._nodes[k]) for k in sorted(self._nodes.keys())]

    def get_edges(self) -> list[EdgeData]:
        """取所有边（返回副本列表）。"""
        return [replace(e) for e in self._edges]

    def get_out_edges(self, node_id: str) -> list[EdgeData]:
        """取节点的所有出边。"""
        return [replace(e) for e in self._edges if e.source_id == node_id]

    def get_in_edges(self, node_id: str) -> list[EdgeData]:
        """取节点的所有入边。"""
        return [replace(e) for e in self._edges if e.target_id == node_id]

    def find_entry_nodes(self) -> list[str]:
        """找所有入口节点（TYPE_ENTRY）。无入口时返回空列表。"""
        return sorted([
            nid for nid, n in self._nodes.items() if n.node_type == TYPE_ENTRY
        ])

    # ─── 自动布局 ──────────────────────────────────────────────────────

    def auto_layout(self, dx: float = 220, dy: float = 120) -> None:
        """分层自动布局（BFS from entry，避免严重重叠）。

        策略：
        - 入口节点放第 0 层；无入口时按 id 排序首个放第 0 层
        - BFS 沿出边分层，每层 y += dy
        - 同层节点按 x 索引排列，x = index * dx（中心对齐偏移在视图层做）
        - 孤立节点（无边连接）放最底层
        """
        if not self._nodes:
            return

        # 1. 找根节点（入口 or 有出边但无入边）
        roots = self.find_entry_nodes()
        # 计算入度 + 出度
        in_degree = {nid: 0 for nid in self._nodes}
        out_degree = {nid: 0 for nid in self._nodes}
        for e in self._edges:
            if e.target_id in in_degree:
                in_degree[e.target_id] += 1
            if e.source_id in out_degree:
                out_degree[e.source_id] += 1
        # 有出边但无入边的节点作为额外根（避免被遗漏）
        for nid in self._nodes:
            if in_degree[nid] == 0 and out_degree[nid] > 0 and nid not in roots:
                roots.append(nid)
        # 真正孤立节点（无入无出）单独收集，放最底层
        isolated = [nid for nid in self._nodes
                    if in_degree[nid] == 0 and out_degree[nid] == 0 and nid not in roots]

        # 2. BFS 分层
        layer: dict[str, int] = {}
        queue = [(r, 0) for r in roots]
        visited: set[str] = set()
        while queue:
            nid, depth = queue.pop(0)
            if nid in visited:
                # 已访问但新路径更深 → 取最大深度（保证下游层级足够深）
                if depth > layer.get(nid, 0):
                    layer[nid] = depth
                else:
                    continue
            else:
                visited.add(nid)
                layer[nid] = depth
            for e in self.get_out_edges(nid):
                if e.target_id in self._nodes:
                    queue.append((e.target_id, depth + 1))

        # 3. 环中节点（有边但 BFS 未达）放最底层；真正孤立节点也放最底层
        max_layer = max(layer.values()) if layer else -1
        # 环中节点（有边连接但未从 roots 可达）
        cyclic = [nid for nid in self._nodes
                  if nid not in layer and nid not in isolated]
        for nid in sorted(isolated) + sorted(cyclic):
            max_layer += 1
            layer[nid] = max_layer

        # 4. 按 layer 分组，同层按 id 排序，分配坐标
        by_layer: dict[int, list[str]] = {}
        for nid, depth in layer.items():
            by_layer.setdefault(depth, []).append(nid)
        for depth in by_layer:
            by_layer[depth].sort()

        for depth, nids in by_layer.items():
            count = len(nids)
            for idx, nid in enumerate(nids):
                # 同层水平居中：x = (idx - count/2) * dx
                x = (idx - (count - 1) / 2.0) * dx
                y = depth * dy
                node = self._nodes[nid]
                self._nodes[nid] = replace(node, x=x, y=y)

    # ─── 序列化 ──────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """序列化为 dict（JSON 友好）。"""
        return {
            "nodes": [
                {
                    "id": n.id, "title": n.title, "preview": n.preview,
                    "node_type": n.node_type, "x": n.x, "y": n.y,
                }
                for n in self.get_nodes()
            ],
            "edges": [
                {"source_id": e.source_id, "target_id": e.target_id, "label": e.label}
                for e in self.get_edges()
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NodeGraphModel":
        """从 dict 反序列化（to_dict 的逆）。"""
        model = cls()
        for n in data.get("nodes", []):
            model.add_node(NodeData(
                id=n["id"], title=n.get("title", n["id"]),
                preview=n.get("preview", ""), node_type=n.get("node_type", TYPE_NORMAL),
                x=float(n.get("x", 0.0)), y=float(n.get("y", 0.0)),
            ))
        for e in data.get("edges", []):
            model.add_edge(EdgeData(
                source_id=e["source_id"], target_id=e["target_id"],
                label=e.get("label", ""),
            ))
        return model


__all__ = [
    "NodeData", "EdgeData", "NodeGraphModel",
    "TYPE_NORMAL", "TYPE_BRANCH", "TYPE_ROUTE", "TYPE_ENDING", "TYPE_ENTRY",
    "TYPE_COLORS", "NODE_WIDTH", "NODE_HEIGHT",
    "extract_block_id", "extract_block_preview", "classify_block",
    "block_to_edges", "block_to_node", "story_to_graph",
]
