## Parent

#22（PRD-0001 父 issue）

## What to build

`src/core/engine/interpreter.py` 的**第五阶段**：解析块内执行区语句，输出 `list[Node]`。

API：
- `parse_block_body(body_lines: list[str], start_lineno: int, *, block_meta: BlockMeta) -> list[Node]`
- 复用 v0-issue-2 的 AST 节点 dataclass

行为约定（ADR §3.3 + §2.2）：

**块内执行区首条非空行必须是 `node start`**（v0-issue-7 已二分）——本 issue **强化**这个检查：若 `body_lines[0] != "node start"` 抛 `ParserError`（v0-issue-7 不做严格首条是中间步骤，本 issue 落地）

支持的语句：
- `node start` / `node end`：sentinel，**本 issue 不解析为 AST 节点**（仅校验）——返回的 `list[Node]` 包含 `Start` 在首位、`End` 在末位
- `node in ->var` → `In(var="var")`（`->` 可有空格）
- `node echo var` → `Echo(var="var")`
- `node next_id` → `NextId(target_id="next_id")`（**注意**：target_id 必须能解析为块 ID，**本 issue 不做跨块 ID 解析**，只解析语法；跨块 ID 校验留给 v0-issue-16 Executor）
- 普通文本行（无前缀）→ `Text(content=line)`
- 整行注释（`^\s*#`）——v0-issue-7 已跳，本 issue 看不到
- `@xxx` 修饰器行 → **本 issue 不解析**，留给 v0-issue-12

未识别的前缀（除 `@xxx` / `node` 之外）→ `ParserError("unrecognized statement at line N: '...'")`

**`node if` 解析**留给 v0-issue-11（独立 issue 拆出）
**`node [a?b:c]` 简略二元**也留给 v0-issue-11

跨块校验（`id:start` 整文件唯一）——本 issue **不**做，留给 v0-issue-16 块装配时统一处理

## Acceptance criteria

- [ ] `from core.engine.interpreter import parse_block_body` import 成功
- [ ] `tests/core/test_block_body.py` 覆盖：
  - 全语句类型（`node start` / 文本行 / `node in` / `node echo` / `node next_id` / `node end`）
  - `node in ->p_mood` 与 `node in->p_mood` 两种格式都接受
  - 普通文本行 → `Text`
  - `@xxx` 行**保留**原样（不抛错）——留给 v0-issue-12 处理
  - 缺 `node start`（首条不是）→ ParserError
  - 缺 `node end` → ParserError（v0-issue-7 已做，本 issue 二次确认）
  - 未识别前缀（如 `xxx yyy`） → ParserError
- [ ] `python -m pytest tests/` 全绿

## Blocked by

- #23（v0-issue-1 仓库骨架）
- #24（v0-issue-2 AST 节点 dataclass）
- #29（v0-issue-7 块级骨架）
- #30（v0-issue-8 元数据区解析）
- #31（v0-issue-9 next 归一）
