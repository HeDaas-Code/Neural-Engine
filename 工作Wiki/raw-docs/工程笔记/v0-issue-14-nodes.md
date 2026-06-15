## Parent

#22（PRD-0001 父 issue）

## What to build

`src/core/engine/executor.py` 第二步：实现核心执行节点（`Text` / `In` / `Echo` / `NextId`）+ NEXT 跳转逻辑 + 块结束处理（`node end` 行为，**不含**修饰器 / if 打桩）。

API（v0-issue-13 已定义，本 issue 填充）：
- `Executor.run_block(block: Block) -> None` 完整实现
- `Executor.run_story() -> None` 顶层循环：`run_block(start_block)` → 块结束处理 → 找下一块 → `run_block` → ...

具体节点行为（ADR §3.3 + §5 + §7.4）：

- `Text(content)` → `sink.put_evt(TextEvt(content=content, style="narration"))`
- `In(var)` →
  1. `sink.put_evt(PromptInputEvt(var=var))`
  2. **v0 阶段**：直接抛 `NotImplementedError("blocking prompt_input not yet implemented; use MemoryInputSink in tests")`——**阻塞等待**留给 v0-issue-17 core main（用真 EngineBus 跨进程 GUI）实现
  3. 测试时用 `MemoryInputSink` mock：先 `put_evt(PromptInputEvt)`，再 `MemoryInputSink.inject(UserInputCmd)` → Executor 收到 `UserInputCmd.value` 写入 `state.vars[var]`
- `Echo(var)` → `sink.put_evt(TextEvt(content=state.vars[var], style="narration"))`（变量未设时抛 `KeyError`）
- `NextId(target_id)` → `self.next = (None, target_id)`（**NEXT 隐式设**）

NEXT 跳转逻辑（ADR §5.2 + §5.3）：
- 进入新块时 `self.next = None`
- `run_block` 末尾（遇到 `End` sentinel）时：
  - 若 `self.next` 非空：查 `state.next_table[current_var] = target_id`（`self.next` 是 `(var_name, target_id)` 或 `(None, target_id)`），跳到对应 `id:target_id` 块
  - 若 `self.next` 为空 + 当前块有 `IdEnd(route_chapter=...)` → `sink.put_evt(RouteEvt(target=route_chapter))`，**停**（v0-issue-17 决定 route 后续行为）
  - 若 `self.next` 为空 + 当前块有 `IdEnd(route_chapter=None)` → `sink.put_evt(ChapterEndEvt())`，**停**
  - 若 `self.next` 为空 + 当前块**无** `IdEnd` → 抛 `RuntimeError("block <id> ended with empty NEXT and no endX marker")`

跨块 ID 校验：
- `id:start` 全文件唯一（`story.blocks` 内只 1 个）——v0-issue-13 已检查
- `NextId(target_id)` / `next:xxx` 的 `target_id` / 简写 ID / 多元 if 分支的 next 变量值 → 必须能在 `story.blocks` 找到对应 `id:xxx` 块；找不到抛 `ValueError("unknown target id 'xxx' at line N")`
- **本 issue 实现**：构造 `Executor(story, sink)` 时做一次性校验

输入接口（**新加**，配合 In 节点的 mock）：
- `class EventSink(Protocol)` 加 `get_cmd() -> Cmd | None`（v0-issue-13 已定义）——本 issue **不**实现，**只**为 `MemoryInputSink` 实现
- `class MemoryInputSink(MemoryEventSink): def __init__(self, inputs: list[str] = []): super().__init__(); self._inputs = list(inputs); self._idx = 0; def get_cmd(self) -> Cmd | None: if self._idx < len(self._inputs): v = self._inputs[self._idx]; self._idx += 1; return UserInputCmd(value=v); return None`

测试用 `MemoryInputSink` + `MemoryEventSink` 替代 `EngineBus`——**不**测跨进程

## Acceptance criteria

- [ ] `from core.engine.executor import MemoryInputSink` import 成功
- [ ] `tests/core/test_executor_nodes.py` 覆盖：
  - `Text` 节点 → `TextEvt` 发出
  - `In` 节点 + `MemoryInputSink` 输入 "平静" → 写入 `state.vars["p_mood"]="平静"`
  - `Echo` 节点 → `TextEvt(content="平静")` 发出
  - `NextId` 节点 → `self.next` 正确设置
  - 单 next 简写块：块末 NEXT 非空 → 跳到下一块
  - 块末 NEXT 空 + `id:end` → `ChapterEndEvt`
  - 块末 NEXT 空 + `id:end1:chapter02` → `RouteEvt(target="chapter02")`
  - 块末 NEXT 空 + 无 end 标记 → `RuntimeError`
  - `Echo` 变量未设 → `KeyError`
  - `NextId` 目标 ID 找不到 → `ValueError`（构造时校验）
- [ ] `python -m pytest tests/` 全绿

## Blocked by

- #24（v0-issue-2 AST 节点 dataclass）
- #25（v0-issue-3 命令 schema，`UserInputCmd` 来自那里）
- #26（v0-issue-4 事件 schema，`TextEvt`/`PromptInputEvt`/`RouteEvt`/`ChapterEndEvt` 来自那里）
- #32（v0-issue-10 块内语句，节点实例来自那里）
- #36（v0-issue-13 Executor 骨架，`EventSink`/`GameState`/`Executor` 来自那里）
