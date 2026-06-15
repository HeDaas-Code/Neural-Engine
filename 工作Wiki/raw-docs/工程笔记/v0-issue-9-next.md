## Parent

#22（PRD-0001 父 issue）

## What to build

`src/core/engine/interpreter.py` 的**第四阶段**：解析元数据区中的 next 声明 + 归一化处理 + 互斥校验。

API：
- `parse_next_decls(meta_lines: list[str], start_lineno: int) -> list[NextDecl]`
- 复用 v0-issue-2 的 `NextDecl(var_name: str | None, target_id: str)`

行为约定（ADR §3.2.1 / §3.2.2 / §3.2.3 + 不变量 #7）：
- **单 next 简写**（`next:yyy`）：块内 0 条或 1 条时允许 → `NextDecl(var_name=None, target_id="yyy")`
- **多 next 完整**（`xxx<-next:yyy`）：块内 ≥2 条时**必须**全部带变量名 → `NextDecl(var_name="xxx", target_id="yyy")`
- **混合**（一条简写 + 一条带变量名）→ `ParserError("mixed next syntax at line N")`
- **单 next 时写带变量名**合法（语义等价）——**不**报错
- **多 next 时写简写** → `ParserError("bare 'next:' not allowed with N>1 next decls at line N")`
- 变量名 / 节点 ID 命名规则：snake_case + 不能以 `node` 开头 + 不含冒号 / 空格 / 尖括号（**不**做严格 regex 校验，留给 executor——本 issue 范围）
- 重复变量名 → `ParserError("duplicate next var 'xxx' at line N")`
- 重复目标 ID（多 next 都指向同一 ID）合法——**不**报错

## Acceptance criteria

- [ ] `from core.engine.interpreter import parse_next_decls` import 成功
- [ ] `tests/core/test_next_decls.py` 覆盖：
  - 1 条 `next:yyy`（单 next 简写）→ `NextDecl(None, "yyy")`
  - 1 条 `xxx<-next:yyy`（单 next 带变量名）→ `NextDecl("xxx", "yyy")`
  - 2 条 `xxx<-next:yyy` + `zzz<-next:www`（多 next）→ `[NextDecl("xxx","yyy"), NextDecl("zzz","www")]`
  - 混合（1 简写 + 1 带变量名）→ ParserError
  - 多 next + 1 条简写 → ParserError
  - 重复变量名 → ParserError
- [ ] `python -m pytest tests/` 全绿

## Blocked by

- #23（v0-issue-1 仓库骨架）
- #24（v0-issue-2 AST 节点 dataclass，`NextDecl` 来自那里）
- #28（v0-issue-6 neon 围栏拆分）
- #29（v0-issue-7 块级骨架）
