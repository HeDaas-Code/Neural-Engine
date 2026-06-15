## Parent

#22（PRD-0001 父 issue）

## What to build

`src/core/engine/interpreter.py` 的**第六阶段**：解析 `node if` 各种形态（二元 / 多元 / 简略二元）+ 分支项内 `node` 前缀省略支持。

API：
- `parse_if_stmt(line: str, lineno: int, *, next_table: list[NextDecl]) -> If`
- 复用 v0-issue-2 的 `If` / `Branch` dataclass + `NextDecl`

支持的形态（ADR §3.3 + 不变量 #10）：
- **二元条件**：`node if cond[a,b]` —— `cond` 是变量名，`a` / `b` 是 next 变量名（必须在 `next_table` 中）
  - 语义：`cond` 真 → `NEXT = ref(a)`，否则 → `NEXT = ref(b)`
  - → `If(cond=("var","cond"), branches=[Branch(0,NextDecl("a",...)), Branch(1,NextDecl("b",...))])`
- **多元条件**：`node if var [1:a,2:b,3:c]` —— 变量名 + 值映射列表
  - 分支项 `a` / `b` / `c` 必须是 `next_table` 中的变量名
  - 特殊：`3:echo p_pick` —— 分支项是 `echo p_pick` 这种**省略 `node` 前缀**的简写
  - → `If(cond=("var","var"), branches=[Branch(1,NextDecl("a",...)), Branch(2,NextDecl("b",...)), Branch(3,("echo",None))])`
- **简略二元**：`node [a?b:c]` —— `a` 是条件表达式（含 `node xxx` 的可执行语句），`b` / `c` 是 next 变量名
  - v0 **打桩**：构造 AST 但 executor 永远走第一分支（v0-issue-18 落地）
  - → `If(cond=("expr","a"), branches=[Branch(0,NextDecl("b",...)), Branch(1,NextDecl("c",...))])`

分支项内省略 `node` 前缀支持（不变量 #10）：
- 解析时若分支项形如 `node xxx` → 拆 `xxx` 当 next 变量名
- 解析时若分支项形如 `echo p_pick` → 识别为 `echo` 关键字，存为 `("echo", None)` 占位
- 解析时若分支项形如 `in ->p_mood` → 同上识别为 `in`
- 解析时若分支项形如 `xxx`（裸变量名）→ 当 next 变量名

错误：
- 未知关键字（既不是 next 变量名也不是 `echo`/`in` 关键字）→ `ParserError("unknown branch '...' at line N")`
- 二元条件缺 `[a,b]` 形式 → `ParserError("malformed 'node if' at line N")`
- 多元条件缺 `[1:a,2:b,...]` 形式 → 同上
- 分支项内 `b` / `c` 不在 `next_table` → `ParserError("unknown next var 'b' at line N")`

**v0-issue-10 已实现**：`node if` 之前由 v0-issue-10 抛 "unrecognized" ——本 issue 通过在 v0-issue-10 内部 hook 或在 v0-issue-10 + 本 issue 配合下，把 `node if` 路由到 `parse_if_stmt`。具体路由方式由实施 agent 决定（**推荐**：v0-issue-10 检测 `node if` 前缀就转交本 issue 的 `parse_if_stmt`）

## Acceptance criteria

- [ ] `from core.engine.interpreter import parse_if_stmt` import 成功
- [ ] `tests/core/test_if_parse.py` 覆盖：
  - 二元 `node if cond[a,b]` → `If(cond=("var","cond"), branches=[...])`
  - 多元 `node if var [1:a,2:b,3:echo p_pick]` → 含 `echo` 占位
  - 简略二元 `node [a?b:c]` → `If(cond=("expr","a"), branches=[...])`
  - 分支项 `node a` / `node echo p` / `echo p` / `in ->p` 各种省略形式
  - 分支项变量名不在 next_table → ParserError
  - 二元缺 `[a,b]` → ParserError
  - 多元缺 `[1:a,2:b,...]` → ParserError
- [ ] `python -m pytest tests/` 全绿

## Blocked by

- #24（v0-issue-2 AST 节点 dataclass，`If`/`Branch` 来自那里）
- #29（v0-issue-7 块级骨架）
- #31（v0-issue-9 next 归一，`NextDecl` / next_table 来自那里）
- #32（v0-issue-10 块内语句，`node if` 路由点）
