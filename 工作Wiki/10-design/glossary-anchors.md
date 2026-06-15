# 10 · 自创名词索引（glossary → raw-docs 锚点）

> **TL;DR**：本页面是 Neural Engine 所有**自创词 / 专门定义**的**反向索引**——从词反查权威原文（raw-docs）的位置。**每个自创词在 raw-docs 里有锚点**，在这里一次查全。

## 使用方式

- 看到一个 wiki 术语但忘了出处 → 查本页
- 写 issue / 写 wiki 时引用自创词 → 复制这里的锚点格式
- 校对 vault 时发现某 wiki 用了自创词但没 raw-docs 锚点 → 补到对应 wiki 页（**每页第一次出现该自创词必须挂锚点**）

## 自创名词 → 原文锚点

### neon DSL 族（脚本格式）

| 自创词 | 出处（原文） | 备注 |
| --- | --- | --- |
| **neon 块** | [[raw-docs/ADR-0001-v0-baseline-script-spec §3]] | ` ```neon ``` ` 围栏 |
| **neon DSL** | [[raw-docs/ADR-0001-v0-baseline-script-spec §3.3]] | 受限声明式 DSL |
| **neon 围栏** | [[raw-docs/ADR-0001-v0-baseline-script-spec §3]] | = neon 块 |
| **块内执行区** | [[raw-docs/ADR-0001-v0-baseline-script-spec §3]] | `node start` 与 `node end` 之间 |
| **块内生命周期** | [[raw-docs/ADR-0001-v0-baseline-script-spec §1]] | 节点从 `node start` 到 `node end` |
| **元数据区** | [[raw-docs/ADR-0001-v0-baseline-script-spec §3]] | `node start` 之前 |
| **块级作用域** | [[raw-docs/ADR-0001-v0-baseline-script-spec §4.1]] | `@` 修饰器作用域 |

### 命名空间族

| 自创词 | 出处（原文） | 备注 |
| --- | --- | --- |
| **命名空间 ID** | [[raw-docs/ADR-0001-v0-baseline-script-spec §1]] | `id:xxx` 命名空间 |
| **ID 命名空间** | [[raw-docs/ADR-0001-v0-baseline-script-spec §1]] | 元数据区 |
| **变量命名空间** | [[raw-docs/ADR-0001-v0-baseline-script-spec §1]] | 块内 |
| **next 变量表** | [[raw-docs/ADR-0001-v0-baseline-script-spec §3.2]] | 块级字典 |
| **next 变量名** | [[raw-docs/ADR-0001-v0-baseline-script-spec §3.2]] | `t_a` / `p_mood` 等 |
| **NEXT 引用** | [[raw-docs/ADR-0001-v0-baseline-script-spec §5.1]] | `(var, id)` 元组 |

### 修饰器族

| 自创词 | 出处（原文） | 备注 |
| --- | --- | --- |
| **`@` 修饰器** | [[raw-docs/ADR-0001-v0-baseline-script-spec §4]] | `@style bgm:rain.mp3` |
| **休止符** | [[raw-docs/ADR-0001-v0-baseline-script-spec §4.2]] | `@style bgm`（裸 key）|
| **装饰器状态** / **decorator_state** | [[raw-docs/CONTEXT-core.md]] | 块级，node start 时清空 |

### 协议族

| 自创词 | 出处（原文） | 备注 |
| --- | --- | --- |
| **数据总线** | [[raw-docs/ADR-0001-v0-baseline-script-spec §7.5]] | 双向 Queue |
| **EngineBus** | [[raw-docs/ADR-0001-v0-baseline-script-spec §7.5]] | 总线封装类 |
| **事件** / **Evt** | [[raw-docs/ADR-0001-v0-baseline-script-spec §7.4]] | Engine → GUI |
| **命令** / **Cmd** | [[raw-docs/ADR-0001-v0-baseline-script-spec §7.3]] | GUI → Engine |

### 状态机族

| 自创词 | 出处（原文） | 备注 |
| --- | --- | --- |
| **游戏状态** / **GameState** | [[raw-docs/CONTEXT-core.md]] | 变量字典 |
| **条件打桩** | [[raw-docs/ADR-0001-v0-baseline-script-spec §8]] | `node if` v0 不真做 |

### AST 节点族（v0-issue-2）

| 自创词 | 出处（原文） | 备注 |
| --- | --- | --- |
| **Story** | [[raw-docs/工程笔记/v0-issue-2-ast.md]] | 解析产物 |
| **Block** | [[raw-docs/工程笔记/v0-issue-2-ast.md]] | `(meta, next_table, body)` 三段 |
| **BlockLocation** | [[raw-docs/工程笔记/v0-issue-2-ast.md]] | `(lineno, col)` 元数据 |
| **ParserError** | [[raw-docs/工程笔记/v0-issue-2-ast.md]] | `SyntaxError` 子类，带 `loc` |
| **NextDecl** | [[raw-docs/工程笔记/v0-issue-2-ast.md]] | `(var_name, target_id)` |
| **IdMeta / IdStart / IdEnd** | [[raw-docs/工程笔记/v0-issue-2-ast.md]] | 元数据区节点 |
| **DecoratorCall / DecoratorStop** | [[raw-docs/工程笔记/v0-issue-2-ast.md]] | `@xxx` 节点 |

### 类型代名词

| 自创词 | 出处（原文） | 备注 |
| --- | --- | --- |
| **深模块** | [[raw-docs/CONTEXT-core.md]] | deep interface |
| **shallow** | [[raw-docs/CONTEXT-core.md]] | = 数据结构层 |
| **快照** / **snapshot** | [[raw-docs/CONTEXT-core.md]] | v0 不实现 |

### v1 表达式子系统族（ADR-0003 新增，已落地 v1-issue-1 骨架）

| 自创词 | 出处（原文） | 备注 |
| --- | --- | --- |
| **表达式子系统** / **expr subpackage** | [[raw-docs/ADR-0003-v1-expression-subsystem §2 决策 2]] | v1 新增子包 `src/core/engine/expr/`（commit `2a83774`）|
| **ExprTranslator** | [[raw-docs/ADR-0003-v1-expression-subsystem §3.2]] | DSL 文本 → Python 表达式字符串翻译器（`expr/translator.py`）|
| **ExprDispatcher** | [[raw-docs/ADR-0003-v1-expression-subsystem §3.1]] | translator → simpleeval → fallback 三层调度（`expr/dispatcher.py`，**已实现**但**未接入 executor**——v1-issue-6 OPEN）|
| **CustomExecutor** | [[raw-docs/ADR-0003-v1-expression-subsystem §3.3]] | simpleeval 兜底 + 业务侧扩展钩子（`expr/custom.py`）|
| **ExprError** | [[raw-docs/ADR-0003-v1-expression-subsystem §3.5]] | 表达式求值失败（`RuntimeError` 子类，`expr/errors.py:13`）|
| **DSLSyntaxError** | [[raw-docs/ADR-0003-v1-expression-subsystem §3.5]] | DSL 翻译失败（`ParserError` 子类，`expr/errors.py:30`，**继承 v0 ParserError**）|
| **UnsupportedNodeError** | [[raw-docs/ADR-0003-v1-expression-subsystem §3.5]] | simpleeval 不支持 AST 节点（`ExprError` 子类，`expr/errors.py:22`）|
| **BUILTIN_FUNCS** | [[raw-docs/ADR-0003-v1-expression-subsystem §3.4]] | 9 个函数白名单（`len/int/str/float/min/max/abs/round/bool`，`expr/builtin_funcs.py:13`）|
| **三层调度** | [[raw-docs/ADR-0003-v1-expression-subsystem §2 决策 3]] | translator → simpleeval → CustomExecutor fallback |
| **bool_expr kind** | [[raw-docs/ADR-0003-v1-expression-subsystem §2 决策 4]] | `If.cond = ("bool_expr", expr_str)` 形态（v1-issue-5 OPEN，AST 还没加）|
| **range kind** | [[raw-docs/ADR-0003-v1-expression-subsystem §2 决策 4]] | `If.cond = ("range", (lo, hi))` 形态（v2+，**v1 不实现**）|
| **keyword_table** | [[raw-docs/ADR-0003-v1-expression-subsystem §3.2]] | DSL 自定义中缀命名映射（`translator.register_keyword`，v2+ 扩展位）|
| **register_function** | [[raw-docs/ADR-0003-v1-expression-subsystem §3.3]] | `CustomExecutor.register_function(name, fn)`——剧情自定义函数 |
| **register_evaluator** | [[raw-docs/ADR-0003-v1-expression-subsystem §3.3]] | `CustomExecutor.register_evaluator(pattern, handler)`——正则匹配的 fallback handler |
| **register_node** | [[raw-docs/ADR-0003-v1-expression-subsystem §3.3]] | `CustomExecutor.register_node(kind, handler)`——**v2+ 占位**（v1 抛 NotImplementedError）|
| **eval_fallback** | [[raw-docs/ADR-0003-v1-expression-subsystem §3.3]] | `CustomExecutor.eval_fallback(py_expr, vars) -> object`——simpleeval 失败时按注册顺序匹配 |
| **eval_bool / eval_int / eval** | [[raw-docs/ADR-0003-v1-expression-subsystem §3.1]] | `ExprDispatcher` 的三个公开求值入口（`expr/dispatcher.py:56/72/76`）|
| **to_python_expr** | [[raw-docs/ADR-0003-v1-expression-subsystem §3.2]] | `ExprTranslator.to_python_expr(dsl) -> str`——DSL → Python 字符串 |
| **Chinese 关键字** | [[raw-docs/ADR-0003-v1-expression-subsystem §3.2]] | `且→and / 或→or / 非→not / 等于→== / 大于→> / 大于等于→>= / 小于→< / 小于等于→<= / 不等于→!= / 包含→in`（`translator.py:35`）|
| **简略三元** | [[raw-docs/ADR-0003-v1-expression-subsystem §3.2]] | `a?b:c → (b) if (a) else (c)`（`translator.py:58`，**只翻译顶层**）|

> **v1 状态锚点**（2026-06-15 实测）：上述 v1 自创词除 `bool_expr kind` 和 `range kind`（AST 扩展）外，其余都已在 [[raw-docs/ADR-0003-v1-expression-subsystem]]（commit `2a83774`）中落地。**唯一剩余工作 = `executor._execute_if` 接入 dispatcher**（v1-issue-6，GH #50），预计 ~30 行 executor.py 改动。

### 强约束 / 软约束族

| 自创词 | 出处（原文） | 备注 |
| --- | --- | --- |
| **强约束** | [[raw-docs/CONTEXT-core.md]] | 7 条（core 无 UI / NEXT 非字符串 等）|
| **强约束**（§11 不变量角度） | [[raw-docs/ADR-0001-v0-baseline-script-spec §11]] | 10 条不变量 |

## 写作约定（vault 内首次出现自创词时）

**规则**：每篇 wiki 页第一次出现某个自创词时，**必须**挂 raw-docs 锚点链接（指向该词原文定义章节）。

格式：

```markdown
... NEXT 引用（[[raw-docs/ADR-0001-v0-baseline-script-spec §5.1]]）...
```

**不强制**：如果一个 wiki 页已经引过一次 raw-docs 锚点（比如顶部有"原文快照"section），后续同一术语可以不重复挂锚点——但**首次出现**必须有。

## 自检方法（人工，一次性）

不写脚本——改完 vault 后人工扫一遍：

```bash
# 1. 是否有孤岛：列出入度 = 0 的 wiki 页
#    在 README 或 00-index 里补一条 [[wiki-page]] 引用即可
#
# 2. 是否有未挂锚点的自创词首次出现：grep 自创词所在行，
#    看前后 ~150 字符有没有 [[raw-docs/...]]
#
# 3. raw-docs 文件是否全被引：grep -l raw-docs/<文件名> 看谁引了
#    任何 raw-docs 文件应至少被一篇 wiki 引
```

## 与其他页的关系

- [[terminology]] — 术语表（按"明确用 / 不要用"组织），每行带 raw-docs 锚点
- [[namespace-semantics]] — 命名空间语义详解（ID vs 变量 + NEXT 元组两槽）
- [[constraints]] — 强约束清单（每条引用 CONTEXT-core 原文）
- [[design-philosophy]] — 四个根原则（每个原则的术语都指回 raw-docs）

## 引用源

- ADR-0001 全文 —— [[raw-docs/ADR-0001-v0-baseline-script-spec]]
- CONTEXT-core 全文 —— [[raw-docs/CONTEXT-core.md]]
- CONTEXT-runtime / CONTEXT-editor —— [[raw-docs/CONTEXT-runtime.md]] / [[raw-docs/CONTEXT-editor.md]]
- v0-issue-2 AST 节点定义 —— [[raw-docs/工程笔记/v0-issue-2-ast.md]]
- 术语表（中英对照）—— [[terminology]]