# 10 · 术语表

> **TL;DR**：ADR-0001 §1 + core/CONTEXT.md 术语表的"明确用 / 不要用"清单——写 issue / 改 wiki 时不要混用。

## 中英对照（"明确用"清单）

> **"出处"列**都是可点击的 raw-docs 锚点——跳到 ADR-0001 对应章节或 CONTEXT-core 原文。每个术语都是 Neural Engine 的**自创词或专门定义**，以 raw-docs 为权威。

| 中文 | 英文 | 出处（权威原文） | 反例（不要用） |
| --- | --- | --- | --- |
| 剧情 | Story | [[raw-docs/ADR-0001-v0-baseline-script-spec §1]] | ~~故事线~~ ~~剧情线~~ |
| 章节 | Chapter | [[raw-docs/ADR-0001-v0-baseline-script-spec §1]] | ~~关卡~~ |
| 剧情节点 / 节点 | Story Node / Node | [[raw-docs/ADR-0001-v0-baseline-script-spec §1]] | ~~剧情片段~~ |
| 块（剧情节点代码块） | Block | [[raw-docs/ADR-0001-v0-baseline-script-spec §1]] | ~~代码块~~ |
| neon 块 | neon block | [[raw-docs/ADR-0001-v0-baseline-script-spec §3]] | 围栏块 |
| 块内执行区 | Block Body | [[raw-docs/ADR-0001-v0-baseline-script-spec §3.3]] | 内容区 |
| 块内生命周期 | Block Lifecycle | [[raw-docs/ADR-0001-v0-baseline-script-spec §1]] | 节点流程 |
| 元数据区 | Metadata Region | [[raw-docs/ADR-0001-v0-baseline-script-spec §3]] | 头部 |
| 命名空间 ID | ID Namespace | [[raw-docs/ADR-0001-v0-baseline-script-spec §1]] | 节点命名空间 |
| 变量命名空间 | Variable Namespace | [[raw-docs/ADR-0001-v0-baseline-script-spec §1]] | 局部命名空间 |
| NEXT 引用 | NEXT reference | [[raw-docs/ADR-0001-v0-baseline-script-spec §5.1]] | ~~NEXT 字符串~~ ~~NEXT 值~~ |
| next 变量表 | next_var_table | [[raw-docs/ADR-0001-v0-baseline-script-spec §3.2]] | next 映射 |
| 单 next 简写 | single-next shorthand | [[raw-docs/ADR-0001-v0-baseline-script-spec §3.2.1]] | 单跳 |
| 多 next 完整形式 | multi-next full form | [[raw-docs/ADR-0001-v0-baseline-script-spec §3.2.2]] | 命名 next |
| `@` 修饰器 | decorator | [[raw-docs/ADR-0001-v0-baseline-script-spec §4]] | 注解 |
| 休止符 | terminator | [[raw-docs/ADR-0001-v0-baseline-script-spec §4.2]] | 清空符 |
| 块级作用域 | block scope | [[raw-docs/ADR-0001-v0-baseline-script-spec §4.1]] | 局部作用域 |
| 装饰器状态 | decorator_state | [[raw-docs/CONTEXT-core.md]] | 修饰器状态表 |
| 游戏状态 | GameState | [[raw-docs/CONTEXT-core.md]] | 全局状态 |
| 事件 | Event / Evt | [[raw-docs/ADR-0001-v0-baseline-script-spec §7.4]] | 消息 |
| 命令 | Command / Cmd | [[raw-docs/ADR-0001-v0-baseline-script-spec §7.3]] | 请求 |
| 数据总线 | DataBus / EngineBus | [[raw-docs/ADR-0001-v0-baseline-script-spec §7.5]] | 消息总线 |
| 快照（未来用） | snapshot | [[raw-docs/CONTEXT-core.md]] | 存档状态 |

## 数据类型代号（v0 已敲定，v0-issue-2）

> 这些是**实现期**会出现的类型名（dataclass / 类），不是用户自创术语但**与术语表强耦合**。

| 名字 | 类型 | 权威出处 | 出现处 |
| --- | --- | --- | --- |
| `Story` | 解析产物（`dataclass(frozen=True, slots=True)`） | [[raw-docs/工程笔记/v0-issue-2-ast.md]] | `core/engine/ast_nodes.py` |
| `Block` | `(meta, next_table, body)` 三段 dataclass | [[raw-docs/工程笔记/v0-issue-2-ast.md]] | `core/engine/ast_nodes.py` |
| `BlockLocation` | `(lineno, col)` 元数据 | [[raw-docs/工程笔记/v0-issue-2-ast.md]] | 错误定位 |
| `Node` 基类 | `dataclass(frozen=True, slots=True)` | [[raw-docs/工程笔记/v0-issue-2-ast.md]] | AST 节点统一基类 |
| `Start` / `End` | sentinel（单例式） | [[raw-docs/工程笔记/v0-issue-2-ast.md]] | 块边界 |
| `Text(content)` | 文本行节点 | [[raw-docs/工程笔记/v0-issue-2-ast.md]] | 普通文本 |
| `In(var)` / `Echo(var)` | 输入/输出节点 | [[raw-docs/工程笔记/v0-issue-2-ast.md]] | 用户输入与回显 |
| `NextId(target_id)` | 显式跳转 | [[raw-docs/工程笔记/v0-issue-2-ast.md]] | NEXT 赋值 |
| `If(cond, branches)` | 条件节点（打桩） | [[raw-docs/工程笔记/v0-issue-2-ast.md]] | `node if` |
| `Branch(value, target)` | 条件分支项 | [[raw-docs/工程笔记/v0-issue-2-ast.md]] | `node if` 列表项 |
| `NextDecl(var_name, target_id)` | next 声明 | [[raw-docs/工程笔记/v0-issue-2-ast.md]] | 元数据区 |
| `IdMeta(id)` / `IdStart` / `IdEnd(x, route_chapter)` | 元数据节点 | [[raw-docs/工程笔记/v0-issue-2-ast.md]] | `id:xxx` 元数据 |
| `DecoratorCall(name, args)` / `DecoratorStop(name, key)` | 修饰器节点 | [[raw-docs/工程笔记/v0-issue-2-ast.md]] | `@xxx` |
| `ParserError(SyntaxError)` | 解析期错误（带 `loc: BlockLocation`） | [[raw-docs/工程笔记/v0-issue-2-ast.md]] | 解析器抛出 |
| `decorator_state` | `dict[str, list[str]]` | [[raw-docs/ADR-0001-v0-baseline-script-spec §4.1]] | 块级，node start 时清空 |
| `GameState` | `dict[str, str]` | [[raw-docs/ADR-0001-v0-baseline-script-spec §5.3]] | 变量字典 |
| `Evt` / `Cmd` | dataclass 子类 | [[raw-docs/ADR-0001-v0-baseline-script-spec §7.4]] / [[raw-docs/ADR-0001-v0-baseline-script-spec §7.3]] | 6 + 3 = 9 个具体类 |
| `EngineBus` | 封装两个 Queue | [[raw-docs/ADR-0001-v0-baseline-script-spec §7.5]] | `bus.py` |

### v1 数据类型代号（ADR-0003 / commit `2a83774` 已落地 v1-issue-1 骨架）

> 这些是 v1 表达式子系统的具体类 / 常量 / 错误类。**v1-issue-1 骨架阶段已全部落地**（6 个 .py + 37 个测试）；**未接入 executor**（v1-issue-6 OPEN）。

| 名字 | 类型 | 权威出处 | 出现处 |
| --- | --- | --- | --- |
| `ExprDispatcher` | 类（translator→simpleeval→fallback 调度器）| [[raw-docs/ADR-0003-v1-expression-subsystem §3.1]] | `core/engine/expr/dispatcher.py:32` |
| `ExprDispatcher.eval_bool(expr: str) -> bool` | 方法 | [[raw-docs/ADR-0003-v1-expression-subsystem §3.1]] | `dispatcher.py:56` |
| `ExprDispatcher.eval_int(expr: str) -> int` | 方法 | [[raw-docs/ADR-0003-v1-expression-subsystem §3.1]] | `dispatcher.py:72` |
| `ExprDispatcher.eval(expr: str) -> object` | 方法（底层入口）| [[raw-docs/ADR-0003-v1-expression-subsystem §3.1]] | `dispatcher.py:76` |
| `ExprTranslator` | 类（DSL → Python 翻译器）| [[raw-docs/ADR-0003-v1-expression-subsystem §3.2]] | `core/engine/expr/translator.py:67` |
| `ExprTranslator.to_python_expr(dsl: str) -> str` | 方法 | [[raw-docs/ADR-0003-v1-expression-subsystem §3.2]] | `translator.py:86` |
| `ExprTranslator.register_keyword(dsl_kw, py_expr)` | 方法 | [[raw-docs/ADR-0003-v1-expression-subsystem §3.2]] | `translator.py:79` |
| `CustomExecutor` | 类（fallback + 业务侧扩展）| [[raw-docs/ADR-0003-v1-expression-subsystem §3.3]] | `core/engine/expr/custom.py:27` |
| `CustomExecutor.register_function(name, fn)` | 方法 | [[raw-docs/ADR-0003-v1-expression-subsystem §3.3]] | `custom.py:46` |
| `CustomExecutor.register_evaluator(pattern, handler)` | 方法 | [[raw-docs/ADR-0003-v1-expression-subsystem §3.3]] | `custom.py:72` |
| `CustomExecutor.register_node(kind, handler)` | 方法（v2+ 占位，v1 抛 NotImplementedError）| [[raw-docs/ADR-0003-v1-expression-subsystem §3.3]] | `custom.py:60` |
| `CustomExecutor.eval_fallback(py_expr, vars) -> object` | 方法 | [[raw-docs/ADR-0003-v1-expression-subsystem §3.3]] | `custom.py:85` |
| `BUILTIN_FUNCS` | `dict[str, Callable]`（9 个函数白名单）| [[raw-docs/ADR-0003-v1-expression-subsystem §3.4]] | `core/engine/expr/builtin_funcs.py:13` |
| `ExprError` | `RuntimeError` 子类 | [[raw-docs/ADR-0003-v1-expression-subsystem §3.5]] | `core/engine/expr/errors.py:13` |
| `UnsupportedNodeError` | `ExprError` 子类（simpleeval fallback 信号）| [[raw-docs/ADR-0003-v1-expression-subsystem §3.5]] | `core/engine/expr/errors.py:22` |
| `DSLSyntaxError` | `ParserError` 子类（继承 v0）| [[raw-docs/ADR-0003-v1-expression-subsystem §3.5]] | `core/engine/expr/errors.py:30` |

> **命名空间映射**：变量命名空间出现在 `GameState`、`next_var_table` 键、`next_ref.var` 槽；ID 命名空间出现在 `Node.id`、`next_var_table` 值、`next_ref.id` 槽、`route_target`、ADR-0001 `id:xxx` 元数据。详见 [[namespace-semantics]]。

## "不要用"清单（v0 不实现 / v1 已实现）

| 概念 | 为什么不要 | 未来怎么用 |
| --- | --- | --- |
| ~~故事线~~ / ~~关卡~~ / ~~剧情线~~ | 概念混用 story/chapter/node | 用 story / chapter / node |
| ~~剧情快照~~ / ~~撤销栈~~ / ~~可逆状态~~ | v0 不实现 | 未来用 snapshot |
| ~~嵌入脚本~~ / ~~代码块~~ | v0 是 neon DSL | 用 neon DSL / 块内执行区 |
| `Node` 子类（OOP）| v0 用 dataclass AST | 未来若要扩展 |
| ~~NodeGraph~~ | v0 不实现 | 编辑器上下文用 |
| ~~表达式求值器~~ | v0 不真做条件（**`executor._execute_if` 永远选第一分支**——v0-issue-16 打桩）| **v1 已实现**（v1-issue-1 骨架 ✅，v1-issue-6 接入 executor 后真分支生效）|
| 存档序列化 | v0 不实现 | v2+ |

## ID 命名 vs 变量命名的微妙之处

ADR §1 强调：`c1` 和 `c11` 在**变量命名空间**里没区别，都是普通变量名。

例子（来自 ADR 附录 A）：
```
node if p_pick [1:t_a, 2:t_b, 3:echo p_pick]
```
- `1` / `2` / `3` —— 字面值（被解析为分支比较值）
- `t_a` / `t_b` / `echo` —— **next 变量名**（在 `next_var_table` 里查节点 ID）
- `p_pick` —— 用户输入变量名（存到 `GameState`）

→ 相关：[[vision]] / [[design-philosophy]] / [[../20-architecture/state-machine]] / [[../20-architecture/ast-nodes]]