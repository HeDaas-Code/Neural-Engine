"""v0 引擎执行器（Executor）。

v0-issue-13 落地 GameState + Executor 骨架 + MemoryEventSink（mock sink），
不依赖 EngineBus——通过 EventSink Protocol 抽象隔离。

v0-issue-14..16 逐步实现节点调度。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from core.engine.ast_nodes import (
    Story, Block, Start, End, IdMeta, IdEnd,
    Text, In, Echo, NextId, If,
    DecoratorCall, DecoratorStop,
)
from core.engine.protocol import (
    RouteEvt, ChapterEndEvt,
    TextEvt, PromptInputEvt, UserInputCmd,
)


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
        """单块执行：v0-issue-14 实现 Text/In/Echo/NextId。"""
        # 初始化 next_table
        self.state.next_table = {
            d.var_name: d.target_id
            for d in block.next_table
            if d.var_name is not None
        }

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
                    self.state.vars[node.var] = cmd.value
                else:
                    # 阻塞式等待——v0-issue-17 实现；本 issue 抛错
                    raise NotImplementedError(
                        "blocking prompt_input not yet implemented; "
                        "use MemoryInputSink in tests"
                    )
                continue
            if isinstance(node, Echo):
                val = self.state.vars[node.var]  # KeyError if unset
                self.sink.put_evt(TextEvt(content=val, style="narration"))
                continue
            if isinstance(node, NextId):
                self.next = (None, node.target_id)
                continue
            # 留给 v0-issue-15/16
            raise NotImplementedError(
                f"node not yet implemented in v0-issue-14: {type(node).__name__}"
            )

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
