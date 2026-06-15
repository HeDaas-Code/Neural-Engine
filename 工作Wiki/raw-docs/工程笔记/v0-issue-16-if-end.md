## Parent

#22（PRD-0001 父 issue）

## What to build

`src/core/engine/executor.py` 第四步：实现 `node if` 打桩执行（v0 不真做条件）+ 跨块 ID 校验（NextDecl / NextId / 分支项）+ 块结束时 NEXT 路由决策的边界补全。

API（在 v0-issue-14 基础上补全）：
- `Executor._execute_if(if_node: If) -> None` 节点处理
- `Executor._resolve_next(branch: Branch) -> tuple[str | None, str | None]` 把 `Branch` 解析为 `(var_name, target_id)` 元组
- `Executor._validate_target_ids() -> None` **构造时**一次性校验所有 `NextId.target_id` / `NextDecl.target_id` / `If.branches[i].target` 都能在 `story.blocks` 找到——v0-issue-14 部分实现，本 issue 完整

`node if` 打桩行为（ADR §8 表中"打桩"项）：
- 不管条件真假，**永远选第一个分支**（`branches[0]`）
- 选完后：
  - 若分支项是 `NextDecl(var_name, target_id)` → `self.next = (var_name, target_id)`，**不**额外广播（v0 不暴露条件真假）
  - 若分支项是 `("echo", None)`（分支项里写 `echo p_pick`） → 模拟"先 echo 再继续"：广播 `TextEvt(content=state.vars.get("p_pick", ""))` + 然后 `self.next = (None, "c1")`（**走第一分支目标块**——v0 打桩约定）
  - 若分支项是 `("in", ...)` 同理模拟
- 强制**额外**广播 `LogEvt(level="info", message=f"node if stubbed: chose branch {branches[0].value}")`——给打桩期可观测性

错误：
- `next:xxx` 中 `xxx` 找不到 → `ValueError`（构造时校验，v0-issue-14 已部分实现）
- `NextId(target_id="xxx")` 中 `xxx` 找不到 → `ValueError`（同上）
- `If.branches[i]` 是 `("echo", None)` 时 `p_pick` 变量未设 → 抛 `KeyError`（**不**在构造时校验——echo 是运行时）

## Acceptance criteria

- [ ] `tests/core/test_executor_if.py` 覆盖：
  - 多元 `node if var [1:t_a, 2:t_b, 3:echo p_pick]` + 设 `var=1` → 永远选 t_a + LogEvt 广播
  - 多元 + 设 `var=3` → 选 echo 占位 + 广播 TextEvt + next 走第一分支
  - 二元 `node if cond[a,b]` → 永远选 a + LogEvt
  - 简略二元 `node [a?b:c]` → 永远选 b（第一分支）+ LogEvt
  - 构造时校验：`next:unknown_id` → `ValueError`
  - 构造时校验：`If` 分支项 target 找不到 → `ValueError`
- [ ] `python -m pytest tests/` 全绿

## Blocked by

- #24（v0-issue-2 AST 节点 dataclass）
- #26（v0-issue-4 事件 schema，`LogEvt` 来自那里）
- #33（v0-issue-11 node if 解析）
- #36（v0-issue-13 Executor 骨架）
- #37（v0-issue-14 核心节点执行 + NEXT 跳转 + 块结束路由）
