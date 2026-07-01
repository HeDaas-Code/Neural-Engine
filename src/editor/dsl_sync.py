"""DslSync —— v4-02 节点图 ↔ neon 源码 双向同步（#110）。

职责：
- `story_to_source(story)`：AST → neon markdown 源码（unparser，全保真）
- `graph_to_source(model)`：NodeGraphModel → 最小 neon 源码（结构导出）
- `parse_source(source)`：neon 源码字符串 → Story（_load_story 的文本版）
- `DslSync`：双向同步编排（源码变更→重建图；图变更→重建源码，保留已有块体）

双向同步策略（update_from_graph）：
- 解析旧源码 → {node_id: Block} 映射（保留完整 body：Text/In/Echo/If/装饰器）
- 对新 model 的每个节点：
  - node_id 在旧块中 → 复用旧 body，但 next_table 用新出边覆盖
  - node_id 是新增 → 生成最小块（preview 作 Text）
- 旧块中不在新 model 的 node_id → 丢弃
- 序列化合并结果 → 新源码

不变量：
- story_to_source 输出能被 parse_source 重新解析为等价 Story（lineno 归一后相等）
- graph_to_source 输出能被 parse_source 解析，story_to_graph 后节点/边结构一致
"""
from __future__ import annotations

import logging
from typing import Optional

from core.engine.ast_nodes import (
    Block, Story, IdMeta, IdEnd, IdStart, NextDecl, BlockLocation,
    Start, End, Text, In, Echo, NextId, If, Branch, CallExpression,
    DecoratorCall, DecoratorStop,
)
from core.engine.interpreter import (
    extract_neon_blocks, parse_block_skeleton, parse_block_meta,
    parse_next_decls, parse_block_body,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# parse_source：源码字符串 → Story
# ═══════════════════════════════════════════════════════════════════════


def parse_source(source: str) -> Story:
    """neon 源码字符串 → Story（_load_story 的文本版，无需文件路径）。"""
    blocks_text = extract_neon_blocks(source)
    blocks: list[Block] = []
    for nb in blocks_text:
        skel, _ = parse_block_skeleton(nb.content, lineno=nb.lineno)
        meta = parse_block_meta(skel.meta_lines, start_lineno=nb.lineno)
        next_decls = parse_next_decls(skel.meta_lines, start_lineno=nb.lineno)
        body = parse_block_body(
            skel.body_lines,
            start_lineno=nb.lineno,
            block_meta=meta,
            next_table=next_decls,
        )
        blocks.append(Block(
            meta=tuple(meta.ids),
            next_table=tuple(next_decls),
            body=tuple(body),
            loc=nb.loc,
        ))
    return Story(blocks=tuple(blocks))


# ═══════════════════════════════════════════════════════════════════════
# story_to_source：AST → neon 源码（unparser）
# ═══════════════════════════════════════════════════════════════════════


def story_to_source(story: Story) -> str:
    """Story AST → neon markdown 源码（围栏块用 \\n\\n 分隔）。

    全保真：保留 id/next/body 所有节点类型（Text/In/Echo/NextId/If/装饰器）。
    注释和空行不保留（解析期已丢弃）。
    """
    parts = [_block_to_source(b) for b in story.blocks]
    return "\n\n".join(parts) + "\n"


def _block_to_source(block: Block) -> str:
    lines = ["```neon"]
    # 元数据区：id: 行（meta）+ next 声明（next_table）
    for m in block.meta:
        s = _meta_to_source(m)
        if s:
            lines.append(s)
    for nd in block.next_table:
        lines.append(_next_decl_to_source(nd))
    # 执行区
    lines.append("node start")
    for node in block.body:
        s = _body_node_to_source(node)
        if s is not None:
            lines.append(s)
    lines.append("node end")
    lines.append("```")
    return "\n".join(lines)


def _meta_to_source(m) -> str:
    """元数据项 → 源码行。"""
    if isinstance(m, IdMeta):
        return f"id:{m.id}"
    if isinstance(m, IdEnd):
        if m.x is None and m.route_chapter is None:
            return "id:end"
        if m.x is not None and m.route_chapter is None:
            return f"id:end{m.x}"
        if m.x is not None and m.route_chapter is not None:
            return f"id:end{m.x}:{m.route_chapter}"
        # x=None + route（解析器不产生，best-effort）
        return f"id:end:{m.route_chapter}"
    if isinstance(m, IdStart):
        return "id:start"
    return ""


def _next_decl_to_source(nd: NextDecl) -> str:
    """next 声明 → 源码行。bare 用 `next: x`，named 用 v1 箭头 `v ← next : x`。"""
    if nd.var_name is None:
        return f"next: {nd.target_id}"
    return f"{nd.var_name} ← next : {nd.target_id}"


def _body_node_to_source(node) -> Optional[str]:
    """执行区节点 → 源码行。Start/End sentinel 返回 None（由 _block_to_source 显式发）。"""
    if isinstance(node, (Start, End)):
        return None
    if isinstance(node, Text):
        return node.content
    if isinstance(node, In):
        if node.options:
            return f"node in → {node.var} [{', '.join(node.options)}]"
        return f"node in → {node.var}"
    if isinstance(node, Echo):
        if node.parts:
            return f"node echo {' + '.join(node.parts)}"
        return f"node echo {node.var}"
    if isinstance(node, NextId):
        return f"node {node.target_id}"
    if isinstance(node, If):
        return _if_to_source(node)
    if isinstance(node, DecoratorCall):
        return f"@{node.name} {','.join(node.args)}" if node.args else f"@{node.name}"
    if isinstance(node, DecoratorStop):
        return f"@{node.name} {node.key}" if node.key else f"@{node.name}"
    return None


def _if_to_source(node: If) -> str:
    """If → 源码行。

    二元形式（2 分支 + values (0,1) + 全 NextDecl）：`node if <cond> [a,b]`（无空格）
    多元形式：`node if <cond> [0:item, 1:item, ...]`
    """
    cond_kind, cond_val = node.cond
    cond_str = cond_val
    branches = node.branches

    # 二元简写：2 分支 + values 严格 (0,1) + 全 NextDecl target
    if (len(branches) == 2
            and branches[0].value == 0 and branches[1].value == 1
            and all(isinstance(b.target, NextDecl) for b in branches)):
        a = branches[0].target.var_name
        b = branches[1].target.var_name
        return f"node if {cond_str} [{a},{b}]"

    # 多元形式
    items = [f"{br.value}:{_branch_item_to_source(br.target)}" for br in branches]
    return f"node if {cond_str} [{', '.join(items)}]"


def _branch_item_to_source(target) -> str:
    """分支项 → 源码片段。"""
    if isinstance(target, NextDecl):
        return target.var_name or ""
    if isinstance(target, CallExpression):
        if target.kind == "echo":
            return f"echo {target.var}"
        if target.kind == "in":
            return f"in -> {target.var}"
    return ""


# ═══════════════════════════════════════════════════════════════════════
# graph_to_source：NodeGraphModel → 最小 neon 源码
# ═══════════════════════════════════════════════════════════════════════


def graph_to_source(model) -> str:
    """NodeGraphModel → 最小 neon 源码（每节点一个块）。

    约束：
    - 单出边无 label → bare `next: x`
    - 多出边或有 label → named `v ← next : x`（label 作 var_name，无 label 生成 n1/n2）
    - 多出边时所有 next 必须命名（解析器互斥校验）
    - var_name 去重（同 label 追加索引）
    - 跳过纯数字 label 的边（来自 If.branch value，不是真正的 next_table 项）
    """
    parts = []
    for node in model.get_nodes():  # 按 id 排序
        lines = ["```neon"]
        lines.append(f"id:{node.id}")
        out_edges = model.get_out_edges(node.id)
        for nd in _edges_to_next_decls(out_edges):
            lines.append(_next_decl_to_source(nd))
        lines.append("node start")
        if node.preview:
            lines.append(node.preview)
        lines.append("node end")
        lines.append("```")
        parts.append("\n".join(lines))
    return "\n\n".join(parts) + "\n" if parts else ""


# ═══════════════════════════════════════════════════════════════════════
# DslSync：双向同步编排
# ═══════════════════════════════════════════════════════════════════════


class DslSync:
    """节点图 ↔ neon 源码 双向同步编排器。

    用法：
        sync = DslSync(source=md_text)   # 从源码初始化（自动建 model）
        sync.update_from_source(new_md)  # 源码改了 → 重建 model
        sync.update_from_graph(new_model)  # 图改了 → 重建源码（保留已有块体）

    同步语义：
    - source→graph：全保真解析（story_to_graph，preview 取首 Text）
    - graph→source：保留旧块体（Text/In/Echo/If/装饰器），用新图的 next_table 覆盖出边；
      新增节点用 preview 生成最小块；删除节点的块丢弃。
    """

    def __init__(self, source: str = "", model=None):
        from editor.node_graph_model import NodeGraphModel, story_to_graph
        self._source = source
        if model is not None:
            self._model = model
        elif source:
            self._model = story_to_graph(parse_source(source))
        else:
            self._model = NodeGraphModel()

    @property
    def source(self) -> str:
        return self._source

    @property
    def model(self):
        return self._model

    def update_from_source(self, source: str) -> None:
        """源码变更 → 重建 model（全保真解析）。"""
        from editor.node_graph_model import story_to_graph
        self._source = source
        self._model = story_to_graph(parse_source(source))

    def update_from_graph(self, model) -> None:
        """图变更 → 重建源码（保留旧块体，用新图 next_table 覆盖出边）。"""
        self._model = model
        self._source = self._sync_graph_to_source(model, self._source)

    @staticmethod
    def _sync_graph_to_source(model, old_source: str) -> str:
        """把 model 的结构变更同步到 old_source（保留已有块体）。

        - 旧源码解析为 {node_id: Block}（保留 body）
        - 新 model 每个节点：复用旧块体或生成最小块；next_table 用新出边覆盖
        - 旧块中不在新 model 的节点：丢弃
        - If.branches 中引用已删除 var_name 的分支会被丢弃（避免悬空引用导致重解析失败）
        """
        # 1. 解析旧源码 → {node_id: Block}
        old_blocks: dict[str, Block] = {}
        if old_source.strip():
            try:
                old_story = parse_source(old_source)
                from editor.node_graph_model import extract_block_id
                for b in old_story.blocks:
                    nid = extract_block_id(b)
                    if nid is not None:
                        old_blocks[nid] = b
            except Exception as e:
                logger.warning("DslSync: 旧源码解析失败，按全新生成: %s", e)
                old_blocks = {}

        # 2. 对新 model 每个节点合并
        from editor.node_graph_model import NodeData, EdgeData
        new_blocks: list[Block] = []
        for node in model.get_nodes():  # 按 id 排序
            old_b = old_blocks.get(node.id)
            if old_b is not None:
                # 复用旧 body + meta（id 行），next_table 用新出边覆盖
                out_edges = model.get_out_edges(node.id)
                new_next_table = _edges_to_next_decls(out_edges)
                new_var_names = {nd.var_name for nd in new_next_table if nd.var_name}
                # 过滤 If.branches：丢弃引用已删除 var_name 的分支；
                # 若 If 全部分支被丢弃则整个 If 节点丢弃（避免空 If 重解析失败）
                new_body = _filter_body_for_next_table(old_b.body, new_var_names)
                new_blocks.append(Block(
                    meta=old_b.meta,
                    next_table=tuple(new_next_table),
                    body=tuple(new_body),
                    loc=old_b.loc,
                ))
            else:
                # 新节点 → 最小块
                out_edges = model.get_out_edges(node.id)
                new_next_table = _edges_to_next_decls(out_edges)
                body: list = [Start()]
                if node.preview:
                    body.append(Text(node.preview))
                body.append(End())
                new_blocks.append(Block(
                    meta=tuple(_node_id_to_meta(node.id)),
                    next_table=tuple(new_next_table),
                    body=tuple(body),
                    loc=BlockLocation(lineno=0, col=1),
                ))

        return story_to_source(Story(blocks=tuple(new_blocks)))


def _is_if_branch_label(label: str) -> bool:
    """检测 label 是否纯数字（来自 If.branch value 的边）。

    block_to_edges 对 If.branches 用 str(br.value) 作 label，
    这些边不是真正的 next_table 项，序列化时应跳过。
    """
    return bool(label) and label.isdigit()


def _edges_to_next_decls(edges) -> list[NextDecl]:
    """EdgeData 列表 → NextDecl 列表（label作 var_name，去重）。

    跳过纯数字 label 的边（这些来自 If.branch value，不是真正的 next_table 项）。
    """
    # 过滤掉 If.branch value 边（label 为纯数字）
    real_edges = [e for e in edges if not _is_if_branch_label(e.label)]
    used: set[str] = set()
    decls: list[NextDecl] = []
    for i, e in enumerate(real_edges):
        if len(real_edges) == 1 and not e.label:
            decls.append(NextDecl(var_name=None, target_id=e.target_id))
            continue
        base = e.label or f"n{i + 1}"
        name = base
        k = 1
        while name in used:
            name = f"{base}_{k}"
            k += 1
        used.add(name)
        decls.append(NextDecl(var_name=name, target_id=e.target_id))
    return decls


def _filter_body_for_next_table(body, var_names: set[str]) -> list:
    """过滤 body 中 If.branches，保留引用现存 var_name 的分支。

    - CallExpression 分支：始终保留（无 var_name 引用）
    - NextDecl 分支：var_name 在新 next_table 才保留
    - If 所有分支都被丢弃 → 整个 If 节点丢弃（避免空 If 重解析失败）
    """
    new_body = []
    for node in body:
        if isinstance(node, If):
            new_branches = []
            for br in node.branches:
                if isinstance(br.target, CallExpression):
                    new_branches.append(br)
                elif isinstance(br.target, NextDecl):
                    if br.target.var_name in var_names:
                        new_branches.append(br)
            if new_branches:
                new_body.append(If(cond=node.cond, branches=tuple(new_branches)))
            # else: 整个 If 丢弃
        else:
            new_body.append(node)
    return new_body


def _node_id_to_meta(node_id: str):
    """node_id 字符串 → meta 元组（IdMeta 或 IdEnd）。

    node_id 形如 "start" / "c1" / "end" / "end1" / "end1:chapter02"。
    """
    if node_id == "start":
        return [IdMeta(id="start", lineno=0)]
    if node_id == "end":
        return [IdEnd(x=None, route_chapter=None, lineno=0)]
    if node_id.startswith("end"):
        rest = node_id[3:]
        if ":" in rest:
            x_part, chapter = rest.split(":", 1)
            if x_part.isdigit():
                return [IdEnd(x=int(x_part), route_chapter=chapter, lineno=0)]
            # end:chapter（无 x）— 不规范但 best-effort
            return [IdEnd(x=None, route_chapter=rest, lineno=0)]
        if rest.isdigit():
            return [IdEnd(x=int(rest), route_chapter=None, lineno=0)]
    # 普通 id
    return [IdMeta(id=node_id, lineno=0)]


__all__ = [
    "parse_source", "story_to_source", "graph_to_source", "DslSync",
]
