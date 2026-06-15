## Parent

#22（PRD-0001 父 issue）

## What to build

`src/core/engine/executor.py` 第一步：定义 `GameState` dataclass、`Executor` 类骨架 + **内存事件捕获器**（mock bus sink）。

约定：**v0-issue-13 不依赖 #27 EngineBus**——Executor 只接 `EventSink` 抽象接口（Protocol class）。

API：
- `class EventSink(Protocol): def put_evt(self, evt) -> None: ...`
- `class MemoryEventSink: def __init__(self): self.events: list = []; def put_evt(self, evt): self.events.append(evt)`
- `@dataclass class GameState: vars: dict[str, str]; path: list[str]; next_table: dict[str, str]`
  - `vars`：变量表（v0 全按字符串存）
  - `path`：上一节点路径（v0 用于断点恢复，**v0 阶段仅写不读**）
  - `next_table`：next 变量名 → 节点 ID 映射
- `class Executor: def __init__(self, story: Story, sink: EventSink, *, entry_id: str = "start"): self.story = story; self.sink = sink; self.state = GameState(...); ...`
- `Executor.run() -> None` —— 入口；从 `entry_id` 块开始执行；遇到 `node end` 且 NEXT 为空 + `id:endX:chapterYY` 时广播 `RouteEvt`；遇到 `node end` 且 NEXT 为空 + 普通 `id:endX` 时广播 `ChapterEndEvt`；**遇到 `node end` 且 NEXT 非空**时跳转（v0-issue-14 落地）；遇到 `node end` 且无 ID 标记时**抛 RuntimeError**（异常块）
- `Executor.run_block(block: Block) -> None` —— 单块执行入口；v0-issue-13 **只占位**：从 `Start` sentinel 起遍历 body，遇到任何非 sentinel 节点就 `raise NotImplementedError("node not yet implemented in v0-issue-13")`

行为约定（ADR §5.1 + §5.2 + 不变量 #2）：
- 入口块查找：`story.blocks` 中找 `id:start` 那个块；找不到抛 `ValueError("no id:start block in story")`
- NEXT 默认值：进入新块时清空
- `next_table` 来源：当前块的所有 `next_table` 项合并（**v0 不做跨块合并**——只当前块）
- `node end` 时清空 `@` 修饰器状态（不变量 #2，v0-issue-15 落地）

测试用 `MemoryEventSink` 替换 `EngineBus`——v0-issue-13 **不**用真 bus

## Acceptance criteria

- [ ] `from core.engine.executor import GameState, Executor, EventSink, MemoryEventSink` import 成功
- [ ] `from core.engine.executor import RouteEvt, ChapterEndEvt` 全部事件类可从 protocol re-import
- [ ] `tests/core/test_executor_skeleton.py` 覆盖：
  - 构造 `GameState({})` 字段默认值
  - `MemoryEventSink` 累积事件
  - `Executor(story, sink).run()` 找 `id:start` 块 + 遍历到 `Start` sentinel 不抛错
  - 缺 `id:start` → `ValueError`
  - 遍历到 `Text` 节点 → `NotImplementedError`（v0-issue-14 才会实现）
- [ ] `python -m pytest tests/` 全绿
- [ ] `python -c "from core.engine.executor import Executor; from core.engine.bus import EngineBus; ..."` 验证 Executor **不** import EngineBus

## Blocked by

- #23（v0-issue-1 仓库骨架）
- #24（v0-issue-2 AST 节点 dataclass，`Story`/`Block` 来自那里）
- #25（v0-issue-3 命令 schema）
- #26（v0-issue-4 事件 schema，`RouteEvt`/`ChapterEndEvt` 来自那里）
- #29（v0-issue-7 块级骨架）
- #32（v0-issue-10 块内语句，`Text`/`Start` 等来自那里）
- #33（v0-issue-11 node if 解析，`If`/`Branch` 来自那里）
- #34（v0-issue-12 修饰器解析，`DecoratorCall` 来自那里）
