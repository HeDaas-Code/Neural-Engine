"""v0/v1 引擎执行器（Executor）。

v0-issue-13 落地 GameState + Executor 骨架 + MemoryEventSink（mock sink），
不依赖 EngineBus——通过 EventSink Protocol 抽象隔离。

v0-issue-14..16 逐步实现节点调度。
v1 (ADR-0004): _execute_if 接入 ExprDispatcher 真求值。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from core.engine.ast_nodes import (
    Story, Block, Start, End, IdMeta, IdEnd,
    Text, In, Echo, NextId, If, Branch, CallExpression, NextDecl,
    DecoratorCall, DecoratorStop,
)
from core.engine.protocol import (
    RouteEvt, ChapterEndEvt,
    TextEvt, PromptInputEvt, UserInputCmd,
    DecoratorEvt, LogEvt,
)
from core.engine.expr import ExprDispatcher, ExprError


class EventSink(Protocol):
    """事件 sink 抽象接口（v0-issue-13 引入，v0-issue-17 替换为 EngineBus）。"""
    def put_evt(self, evt) -> None: ...
    def get_cmd(self): ...  # v0-issue-14 引入；返回 None 表示无输入


class MemoryEventSink:
    """测试用内存事件 sink——累积所有事件。"""

    def __init__(self):
        self.events: list = []

    def put_evt(self, evt) -> None:
        self.events.append(evt)

    def get_cmd(self):  # 默认无输入
        return None


class MemoryInputSink(MemoryEventSink):
    """测试用输入 sink——按预设顺序消费 UserInputCmd。"""

    def __init__(self, inputs: list[str] = None):
        super().__init__()
        self._inputs = list(inputs) if inputs else []
        self._idx = 0

    def get_cmd(self):
        if self._idx < len(self._inputs):
            v = self._inputs[self._idx]
            self._idx += 1
            return UserInputCmd(value=v)
        return None


@dataclass
class GameState:
    """执行期状态（v0 全字符串变量）。"""
    vars: dict = field(default_factory=dict)
    path: list = field(default_factory=list)
    next_table: dict = field(default_factory=dict)


class Executor:
    """v0 引擎执行器。

    入口 id:start 块，按 Start→...→End 顺序调度节点。
    """

    def __init__(self, story: Story, sink: EventSink, *, entry_id: str = "start"):
        self.story = story
        self.sink = sink
        self.state = GameState()
        self._entry_id = entry_id
        self.next: tuple = None  # NEXT 跳转目标
        self._deco_state: dict = {}  # v0-issue-15 修饰器状态 {name: {key: val}}
        self._dispatcher = ExprDispatcher(self.state)
        # 跨块 ID 校验：所有 next_table target_id + NextId 目标 + if 分支目标 必须在 story
        self._validate_target_ids()

    def _validate_target_ids(self) -> None:
        """构造时一次性校验所有 target_id 在 story 内能找到。"""
        all_ids = set()
        for block in self.story.blocks:
            for item in block.meta:
                if isinstance(item, IdMeta):
                    all_ids.add(item.id)
        # 收集所有 target_id
        targets: list[tuple[str, int]] = []  # (target_id, lineno)
        for block in self.story.blocks:
            for d in block.next_table:
                if d.target_id:
                    targets.append((d.target_id, d.lineno))
            for node in block.body:
                if isinstance(node, NextId):
                    targets.append((node.target_id, 0))
        for tid, lineno in targets:
            if tid not in all_ids:
                loc_str = f" at line {lineno}" if lineno else ""
                raise ValueError(
                    f"unknown target id {tid!r}{loc_str}"
                )
        # v0-issue-16: If 分支项是 NextDecl 的 target_id
        for block in self.story.blocks:
            for node in block.body:
                if isinstance(node, If):
                    for branch in node.branches:
                        if isinstance(branch.target, NextDecl):
                            if branch.target.target_id not in all_ids:
                                raise ValueError(
                                    f"unknown target id {branch.target.target_id!r} "
                                    f"in if branch at line {branch.target.lineno}"
                                )

    def _find_entry_block(self) -> Block:
        """找 entry_id 块（默认 'start'）。"""
        for block in self.story.blocks:
            for item in block.meta:
                if isinstance(item, IdMeta) and item.id == self._entry_id:
                    return block
        raise ValueError(f"no id:{self._entry_id} block in story")

    def _find_block_by_id(self, block_id: str) -> Block:
        """按 id 找块。"""
        for block in self.story.blocks:
            for item in block.meta:
                if isinstance(item, IdMeta) and item.id == block_id:
                    return block
        raise ValueError(f"no id:{block_id} block in story")

    def _get_end_marker(self, block: Block) -> IdEnd | None:
        """取块内 id:endX 标记（v0 单 end 假设）。"""
        for item in block.meta:
            if isinstance(item, IdEnd):
                return item
        return None

    def run(self) -> None:
        """从 entry 块开始执行。"""
        entry_block = self._find_entry_block()
        self._execute_block_loop(entry_block)

    def _execute_block_loop(self, start_block: Block) -> None:
        """跑当前块 + 按 NEXT 跳到下一块 + 循环。"""
        current = start_block
        while current is not None:
            self.next = None
            self.run_block(current)
            current = self._next_block(current)

    def _next_block(self, current: Block) -> Block | None:
        """根据 self.next 决定下一块；None 表示停止。"""
        if self.next is None:
            return None
        _, target_id = self.next
        return self._find_block_by_id(target_id)

    def run_block(self, block: Block) -> None:
        """单块执行：v0-issue-14 实现 Text/In/Echo/NextId，v0-issue-15 修饰器。"""
        # v0-issue-15: 块级作用域——进入时清空（不变量 #2）
        self._deco_state.clear()
        # 初始化 next_table
        self.state.next_table = {
            d.var_name: d.target_id
            for d in block.next_table
            if d.var_name is not None
        }
        # bare next（var_name=None）→ NEXT 直接指向（ADR-0001 §5.1）
        bare_decls = [d for d in block.next_table if d.var_name is None]
        if len(bare_decls) == 1:
            self.next = (None, bare_decls[0].target_id)
        else:
            self.next = None  # 多 next 或无 next → 等待竞争

        for node in block.body:
            if isinstance(node, Start):
                continue
            if isinstance(node, End):
                self._handle_end(block)
                return
            if isinstance(node, Text):
                self.sink.put_evt(TextEvt(content=node.content, style="narration"))
                continue
            if isinstance(node, In):
                self.sink.put_evt(PromptInputEvt(var=node.var))
                cmd = self.sink.get_cmd()
                if cmd is not None:
                    # 尝试 int 转换，失败则保留字符串
                    raw = cmd.value
                    try:
                        self.state.vars[node.var] = int(raw)
                    except (ValueError, TypeError):
                        self.state.vars[node.var] = raw
                else:
                    # 阻塞式等待——v0-issue-17 实现；本 issue 抛错
                    raise NotImplementedError(
                        "blocking prompt_input not yet implemented; "
                        "use MemoryInputSink in tests"
                    )
                continue
            if isinstance(node, Echo):
                # ADR-0004 G4: echo 支持拼接
                if node.parts:
                    # 拼接模式：每个 part 如果是变量名则取值，否则当文本
                    pieces = []
                    for p in node.parts:
                        if p in self.state.vars:
                            pieces.append(str(self.state.vars[p]))
                        else:
                            pieces.append(p)
                    self.sink.put_evt(TextEvt(content="".join(pieces), style="narration"))
                else:
                    val = self.state.vars[node.var]  # KeyError if unset
                    self.sink.put_evt(TextEvt(content=val, style="narration"))
                continue
            if isinstance(node, NextId):
                self.next = (None, node.target_id)
                continue
            if isinstance(node, DecoratorCall):
                self._emit_decorator(node)
                continue
            if isinstance(node, DecoratorStop):
                self._emit_decorator(node)
                continue
            if isinstance(node, If):
                self._execute_if(node)
                continue
            # 留给未来
            raise NotImplementedError(
                f"node not yet implemented: {type(node).__name__}"
            )

    def _emit_decorator(self, deco) -> None:
        """v0-issue-15: 调度修饰器调用 / 休止符。"""
        if isinstance(deco, DecoratorCall):
            for arg in deco.args:
                if ":" in arg:
                    k, v = arg.split(":", 1)
                    self._deco_state.setdefault(deco.name, {})[k] = v
            self.sink.put_evt(DecoratorEvt(name=deco.name, args=list(deco.args)))
        elif isinstance(deco, DecoratorStop):
            if deco.name in self._deco_state:
                self._deco_state[deco.name].pop(deco.key, None)
            self.sink.put_evt(DecoratorEvt(name=deco.name, args=[deco.key]))

    def _execute_if(self, if_node: If) -> None:
        """v1 (ADR-0004): node if 真求值。

        cond[0] == "var": 值匹配——取 state.vars[cond[1]] 的值，匹配 branch.value
        cond[0] == "expr": Python 表达式——dispatcher.eval_bool 求值，
                          True → branches[0], False → branches[1] (二元)
                          多元分支按值匹配
        """
        kind, expr = if_node.cond
        chosen = None

        if kind == "expr":
            # Python 表达式求值
            try:
                result = self._dispatcher.eval(expr)
            except ExprError as e:
                self.sink.put_evt(LogEvt(
                    level="error",
                    message=f"node if expr failed: {e}",
                ))
                raise
            # 二元: True → branches[0], False → branches[1]
            if len(if_node.branches) == 2:
                chosen = if_node.branches[0] if result else if_node.branches[1]
            else:
                # 多元: result 当值匹配
                for b in if_node.branches:
                    if b.value == result:
                        chosen = b
                        break
                if chosen is None:
                    raise RuntimeError(
                        f"node if: no branch matched value {result!r}"
                    )
        else:
            # "var" 值匹配（v0 兼容）
            var_name = expr
            val = self.state.vars.get(var_name)
            # 尝试 int 匹配
            try:
                val_int = int(val)
            except (ValueError, TypeError):
                val_int = val
            for b in if_node.branches:
                if b.value == val_int:
                    chosen = b
                    break
            if chosen is None:
                raise RuntimeError(
                    f"node if: no branch matched value {val!r} for var {var_name!r}"
                )

        self.sink.put_evt(LogEvt(
            level="info",
            message=f"node if: chose branch {chosen.value}",
        ))
        # 解析分支目标
        target = chosen.target
        if isinstance(target, NextDecl):
            self.next = (target.var_name, target.target_id)
        elif isinstance(target, CallExpression):
            # echo / in：广播对应事件
            if target.kind == "echo":
                val = self.state.vars.get(target.var, "")
                self.sink.put_evt(TextEvt(content=val, style="narration"))
            elif target.kind == "in":
                self.sink.put_evt(PromptInputEvt(var=target.var))
            return  # 不走下面的 NextDecl/CallExpression 分支

    def _handle_end(self, block: Block) -> None:
        """处理 node end：NEXT 跳转 / RouteEvt / ChapterEndEvt / RuntimeError。"""
        if self.next is not None:
            # NEXT 跳转——不做 RouteEvt，run() 主循环负责跳
            return
        end_marker = self._get_end_marker(block)
        if end_marker is None:
            raise RuntimeError(
                f"block ended with empty NEXT and no endX marker"
            )
        if end_marker.route_chapter is not None:
            self.sink.put_evt(RouteEvt(target=end_marker.route_chapter))
        else:
            self.sink.put_evt(ChapterEndEvt())
