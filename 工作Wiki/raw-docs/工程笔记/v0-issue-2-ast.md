## Parent

#22（PRD-0001 父 issue）

## What to build

`src/core/engine/ast_nodes.py` 提供 AST 节点 dataclass + 自定义错误类，**纯数据结构层**（不解析、不执行）。

覆盖 §3 块结构 + §3.3 块内执行区 + §5 NEXT 引用：

- `Node` 基类（dataclass, frozen=True, slots=True）
- 元数据区：`IdMeta(id: str)`、`IdStart`（单例式 sentinel）、`IdEnd(x: int, route_chapter: str | None)`
- next 声明：`NextDecl(var_name: str | None, target_id: str)` —— `var_name=None` 表示单 next 简写直达 ID
- 块结构：`Story(blocks: list[Block])` + `Block(meta: list, next_table: list[NextDecl], body: list[Node])` + `BlockLocation(lineno, col)`
- 块内执行区：
  - `Start` / `End`（sentinel）
  - `Text(content: str)`
  - `In(var: str)` / `Echo(var: str)`
  - `NextId(target_id: str)`
  - `If(cond, branches: list[Branch])` + `Branch(value: int, target: NextDecl | Echo | In)`
  - `DecoratorCall(name: str, args: list[str])` + `DecoratorStop(name: str, key: str)`
- 错误类：`ParserError(SyntaxError)` 带 `loc: BlockLocation`

设计要点：
- 用 `dataclass(frozen=True, slots=True)`
- 不引用 executor、interpreter、bus——**纯叶子模块**，只被其他模块 import
- 字段命名 snake_case（不变量 #6 延伸）

## Acceptance criteria

- [ ] `python -c "from core.engine.ast_nodes import Story, Block, Start, End, Text, In, Echo, NextId, If, Branch, NextDecl, IdMeta, IdStart, IdEnd, DecoratorCall, DecoratorStop, ParserError"` 全部 import 成功
- [ ] 所有 dataclass 都是 frozen + slots
- [ ] 自带 round-trip 测试：`tests/core/test_ast_shapes.py` 至少 5 个断言（构造、字段、相等性、frozen、loc）
- [ ] `python -m pytest tests/` 全绿

## Blocked by

- #23（v0-issue-1 仓库骨架）
