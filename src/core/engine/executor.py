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
from core.engine.protocol import RouteEvt, ChapterEndEvt


class EventSink(Protocol):
    """事件 sink 抽象接口（v0-issue-13 引入，v0-issue-17 替换为 EngineBus）。"""
    def put_evt(self, evt) -> None: ...


class MemoryEventSink:
    """测试用内存事件 sink——累积所有事件。"""

    def __init__(self):
        self.events: list = []

    def put_evt(self, evt) -> None:
        self.events.append(evt)


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

    def _find_entry_block(self) -> Block:
        """找 entry_id 块（默认 'start'）。"""
        for block in self.story.blocks:
            for item in block.meta:
                if isinstance(item, IdMeta) and item.id == self._entry_id:
                    return block
        raise ValueError(f"no id:{self._entry_id} block in story")

    def _get_end_marker(self, block: Block) -> IdEnd | None:
        """取块内 id:endX 标记（v0 单 end 假设）。"""
        for item in block.meta:
            if isinstance(item, IdEnd):
                return item
        return None

    def run(self) -> None:
        """从 entry 块开始执行。"""
        entry_block = self._find_entry_block()
        self.run_block(entry_block)

    def run_block(self, block: Block) -> None:
        """单块执行（v0-issue-13 占位）。"""
        # 初始化 next_table
        self.state.next_table = {
            d.var_name: d.target_id
            for d in block.next_table
            if d.var_name is not None
        }

        for node in block.body:
            if isinstance(node, Start):
                continue  # sentinel
            if isinstance(node, End):
                # node end：发 RouteEvt 或 ChapterEndEvt，或 RuntimeError
                end_marker = self._get_end_marker(block)
                if end_marker is None:
                    raise RuntimeError(
                        f"node end without id:end marker at line {block.loc.lineno}"
                    )
                if end_marker.route_chapter is not None:
                    self.sink.put_evt(RouteEvt(target=end_marker.route_chapter))
                else:
                    self.sink.put_evt(ChapterEndEvt())
                return
            # v0-issue-13 占位：任何非 sentinel 节点 → NotImplementedError
            raise NotImplementedError(
                f"node not yet implemented in v0-issue-13: {type(node).__name__}"
            )
