# Prototype v0-issue-11：node if 形态推演

## 回答的问题

按 issue body 实现 3 种 `node if` 形态前，需明确 2 个 shape 问题：

1. **`If.cond` 用什么结构表示 "var 模式" / "expr 模式"？**
   v0-issue-2 选 `tuple[str, str]` = (kind, name)：
   - "var" 模式 → cond 字段 = ("var", var_name)
   - "expr" 模式 → cond 字段 = ("expr", expr_text)

2. **`Branch.value` 在二元 / 多元 / 简略二元 三种形态里分别代表什么？**
   - 多元：`value = 数字`（1/2/3...）从 `[1:a,2:b,3:c]` 解析
   - 二元：默认 `value = 0` / `value = 1`（按 ADR 二元只 2 个分支，0 = 真 / 1 = 假）
   - 简略二元：同二元，value = 0 / 1

3. **`Branch.target` 在 `echo p_pick` / `in ->p_mood` 时用什么表示？**
   v0-issue-2 选 `NextDecl | CallExpression`：
   - `echo p_pick` → `CallExpression(kind="echo", var="p_pick")`
   - `in ->p_mood` → `CallExpression(kind="in", var="p_mood")`
   - `node a` / `a`（裸变量）→ `NextDecl(var_name="a", target_id=<查 next_table>)`

## 解析策略（手写解析器·第三段）

### 二元 `node if cond[a,b]`

```
正则：node if (\w+)\[(\w+),(\w+)\]
   ↓
If(
  cond=("var", cond_name),
  branches=[
    Branch(value=0, target=NextDecl(var_name="a", target_id=lookup(a))),
    Branch(value=1, target=NextDecl(var_name="b", target_id=lookup(b))),
  ],
)
```

### 多元 `node if var [1:a,2:b,3:echo p_pick]`

```
正则：node if (\w+) \[([^\]]+)\]
   ↓
分支项 split by `,`：每段形如 "数字:项"
   ↓
项类型：
- 纯变量名 "a" → NextDecl(var_name="a", target_id=lookup(a))
- "echo xxx" → CallExpression(kind="echo", var="xxx")
- "in ->xxx" → CallExpression(kind="in", var="xxx")
- "node echo xxx" / "node in ->xxx" → 去 node 前缀后同上
- 其他 → ParserError
```

### 简略二元 `node [a?b:c]`

```
正则：node \[([^?]+)\?(\w+):(\w+)\]
   ↓
If(
  cond=("expr", a_expr),
  branches=[
    Branch(value=0, target=NextDecl(var_name="b", target_id=lookup(b))),
    Branch(value=1, target=NextDecl(var_name="c", target_id=lookup(c))),
  ],
)
```

## 决定

1. `If.cond = tuple[str, str]`——(kind, name) 按 v0-issue-2
2. `Branch.value` = 0/1（二元/简略）/ 数字（多元）
3. `Branch.target` = `NextDecl | CallExpression` 按 v0-issue-2
4. 用 `re` 解析三种形态 + 字符串 split 解析多元分支项
5. `next_table` 是 `list[NextDecl]`，**查**通过 var_name → NextDecl 映射

## 路由集成（与 v0-issue-10）

v0-issue-10 已在 `_parse_body_line` 处理 `node` 前缀。本 issue 在 v0-issue-10
加 hook：`node if` / `node [...]` 前缀 → 转交 `parse_if_stmt`。
