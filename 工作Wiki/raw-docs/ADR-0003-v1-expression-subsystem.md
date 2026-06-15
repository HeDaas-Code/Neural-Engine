# ADR-0003: v1 表达式子系统架构（v1 Expression Subsystem）

- **状态**：已通过（v1 设计基线，**子包骨架阶段**）
- **日期**：2026-06-15
- **决策者**：项目所有者
- **范围**：v1 `node if` 条件表达式求值、DSL 翻译、simpleeval 集成、CustomExecutor fallback

本文档记录 v1 表达式子系统的**架构决策**：
1. **simpleeval 是主力求值器**——覆盖 95% 场景
2. **CustomExecutor 是 fallback**——后期剧情自定义函数 / 特殊 AST 节点走它
3. **ExprTranslator 做 DSL→Python 翻译**——让 DSL 不被 simpleeval 语法约束
4. **模块归属：`src/core/engine/expr/` 子包**——与 decorators/ 同级，与 interpreter/executor 平级

## 1. 背景

ADR-0001 §3.2 规定 v0 `node if` 语法：

| 形态 | 示例 |
| --- | --- |
| 二元 | `node if p_tall==1 [ce1,ce2]` |
| 多元 | `node if p_tall [1:ce1, 2:ce2, 3:echo p]` |
| 简略二元 | `node [p_tall?ce1:ce2]` |

v0 实现（`core/engine/interpreter.py::parse_if_stmt` + `executor.py::_execute_if`）：
- **解析**：If 节点正确建立，`cond: (kind, name)` 形态支持 "var" / "expr"
- **执行**：**v0 打桩**——`_execute_if` 永远选 `branches[0]`，**不真求值**

v1 要把"打桩"换成"真求值"。面临**4 个求值器候选**：

| 候选 | 优点 | 缺点 | 决策 |
| --- | --- | --- | --- |
| `simpleeval` | 零依赖、白名单、5 行接入 | 不支持 list/dict 字面量、lambda | ✅ **主力** |
| `asteval` | 更接近 Python | 过度设计、API 重 | ❌ v1 不选 |
| 手写 Mini | 完全可控 | 工程量大、bug 多 | ❌ 不造轮子 |
| `ast.literal_eval`+ wrapper | 零依赖 | 等于手写 simpleeval 30% | ❌ 复用差 |

但 simpleeval 不是万能——**后期 v2/v3 会有特殊需求**：
- 剧情自定义函数（`rand_scene()` / `chapter_done()`）
- 自定义 AST 节点（如 `[在古代:ce1, else:ce2]`）
- 跨章节变量持久化、异步表达式

**结论**：simpleeval 是主力，**留 fallback 接口**给后期扩展。

## 2. 决策

### 决策 1: simpleeval 是主力

理由：覆盖 v1 DSL 100% 场景（`==` / `>=` / `and` / `or` / `not` / 函数调用），
零依赖，5 行接入，安全白名单。

`pyproject.toml` 新增依赖：

```toml
simpleeval>=0.9
```

### 决策 2: 表达式子系统独立成 `core.engine.expr` 子包

**架构约束**（来自 `src/core/CONTEXT.md` §架构约束）：
- "核心引擎应当**无 UI 依赖**，纯逻辑层"
- "脚本语言设计应考虑**安全性**，避免执行任意代码"
- core 上下文包含"**条件表达式**"——本子包正是归属

**v0 痛点**：`interpreter.py` 662 行偏大，v1 借机拆分。

**子包结构**：

```
src/core/engine/expr/
├── __init__.py        # 公开 API: ExprDispatcher / ExprTranslator / CustomExecutor / ExprError
├── errors.py          # ExprError / DSL syntax error / UnsupportedNode
├── builtin_funcs.py   # 内置函数白名单 (len/int/str/float/min/max/abs/round/bool)
├── translator.py      # ExprTranslator: DSL 文本 → Python 表达式字符串
├── dispatcher.py      # ExprDispatcher: translator → simpleeval → fallback 调度
├── custom.py          # CustomExecutor: simpleeval 兜底 + 业务扩展钩子
└── README.md          # 子系统使用说明
```

**与 v0 模块的关系**：

| 模块 | 职责 | 依赖 expr/ |
| --- | --- | --- |
| `interpreter.py` | 解析（DSL 文本 → AST 节点） | 否（仅在 if 解析时**调用** translator） |
| `ast_nodes.py` | AST 数据类 | 否（只加新 `If.cond` kind） |
| `executor.py` | 执行（AST → 事件） | 是（`_execute_if` 调用 dispatcher.eval_bool） |
| `expr/` | 求值（表达式 → bool/int） | 仅依赖 simpleeval |

**与 v0 decorators/ 子包的关系**：decorators/ 是 `@xxx` 修饰器运行时钩子的预留位，**与表达式平行**。**不混用**。

### 决策 3: 三层兜底

```
DSL 表达式文本
  → ExprTranslator.to_python_expr() 翻译成 Python
  → simpleeval.SimpleEval.eval() 求值
  → 失败（TypeError UnsupportedNode） → CustomExecutor.eval_fallback()
  → 都不认 → ExprError
```

**翻译失败**抛 `ParserError`（**解析阶段**尽早报，不在执行阶段）
**simpleeval 失败**走 `CustomExecutor`（执行阶段**运行时 fallback**）
**fallback 失败**抛 `ExprError`（执行阶段，最终兜底）

### 决策 4: If.cond 扩 4 种 kind

| kind | payload | 含义 | 走法 |
| --- | --- | --- | --- |
| `"var"` (v0) | 变量名 | 单变量名 | `state.vars[cond] == branch.value` |
| `"expr"` (v0) | 表达式 | 简略二元 `[a?b:c]` | dispatcher 求 bool |
| `"bool_expr"` (v1) | 表达式 | 多元 `[1:ce1, 2:ce2]` 条件 | dispatcher 求 bool |
| `"range"` (v1) | `(lo, hi)` | 范围匹配 | `lo <= v <= hi` |

`("var", "p_tall")` **v0 兼容**——仍走"值匹配"逻辑，**不进 dispatcher**

### 决策 5: 不做插件系统

simpleeval 是 95% 场景唯一选择，**没有"可换求值器"的市场需求**。
v1 写死 simpleeval，**CustomExecutor 留接口**给业务侧扩展（不暴露成 entry_points）。
v3+ 若有第三方求值器需求，**整个 `expr/` 子包可重构为插件系统**，外部 import 路径不变。

## 3. 子包接口签名

### 3.1 ExprDispatcher

```python
class ExprDispatcher:
    """求值调度器: translator → simpleeval → fallback。

    用法:
        dispatcher = ExprDispatcher(state)
        chosen = dispatcher.eval_bool(cond_expr_str)  # bool
        chosen_value = dispatcher.eval_int(cond_expr_str)  # int (用于 var match)
    """

    def __init__(
        self,
        state: GameState,
        custom: CustomExecutor | None = None,
    ) -> None: ...

    def eval_bool(self, expr: str) -> bool: ...
    def eval_int(self, expr: str) -> int: ...
```

### 3.2 ExprTranslator

```python
class ExprTranslator:
    """DSL 文本 → Python 表达式字符串。

    翻译范围:
    - Chinese 关键字 → Python 关键字 (且→and, 或→or, 非→not, 等于→==, 大于→>...)
    - 简略 ?: → Python ternary
    - DSL 自定义中缀命名 (在古代→p_era==1 via keyword table)

    失败抛 ParserError("DSL syntax not translatable: ...")
    """

    def __init__(self, keyword_table: dict[str, str] | None = None) -> None: ...

    def to_python_expr(self, dsl: str) -> str: ...

    def register_keyword(self, dsl_kw: str, py_expr: str) -> None: ...
```

### 3.3 CustomExecutor

```python
class CustomExecutor:
    """simpleeval fallback + 业务侧扩展钩子。

    业务侧可通过 register_* 扩展:
    - register_function(name, fn): 剧情自定义函数
    - register_node(node_kind, handler): 自定义 AST 节点
    - register_evaluator(expr_pattern, handler): 自定义表达式

    eval_fallback 顺序:
    1. _expr_handlers 顺序匹配正则
    2. 都不匹配 → 抛 ExprError
    """

    def __init__(self, state: GameState) -> None: ...

    def register_function(self, name: str, fn: Callable) -> None: ...
    def register_node(self, node_kind: type, handler: Callable) -> None: ...
    def register_evaluator(self, pattern: str, handler: Callable) -> None: ...

    def eval_fallback(self, py_expr: str, vars: dict) -> bool: ...
```

### 3.4 builtin_funcs

```python
BUILTIN_FUNCS: dict[str, Callable] = {
    "len": len, "int": int, "str": str, "float": float,
    "min": min, "max": max, "abs": abs,
    "round": round, "bool": bool,
    # v2+: "randint": safe_randint, "clamp": safe_clamp
}
```

### 3.5 errors

```python
class ExprError(RuntimeError):
    """表达式求值失败 (运行时兜底用)。"""

class UnsupportedNodeError(ExprError):
    """simpleeval 遇到不支持的 AST 节点 (fallback 信号)。"""

class DSLSyntaxError(ParserError):  # 继承 v0 ParserError
    """DSL 语法无法翻译成 Python 表达式 (翻译阶段用)。"""
```

## 4. 实施步骤

| 步骤 | 内容 | GH issue |
| --- | --- | --- |
| 1 | 建 `expr/` 子包骨架 + `__init__` + `errors.py` + `builtin_funcs.py` | v1-issue-1 |
| 2 | 写 `ExprTranslator` 骨架 + 中文关键字翻译表 | v1-issue-2 |
| 3 | 写 `CustomExecutor` 骨架 + 3 种 register 接口 | v1-issue-3 |
| 4 | 写 `ExprDispatcher` 骨架 + 三层兜底 | v1-issue-4 |
| 5 | `If.cond` 扩 `"bool_expr"` / `"range"` 两种 kind | v1-issue-5 |
| 6 | `executor._execute_if` 接 dispatcher | v1-issue-6 |
| 7 | 端到端：chapter01.md 真求值 + 走真分支 | v1-issue-7 |
| 8 | `interpreter.py` re-export 保持向后兼容 | v1-issue-8 |

## 5. 不变量守护

| 不变量 | 守护手段 |
| --- | --- |
| 核心引擎无 UI 依赖 | expr/ 不 import 任何 GUI / runtime / editor 模块 |
| 表达式求值安全 | simpleeval 白名单 + CustomExecutor 函数白名单 |
| DSL 语法错尽早报 | ExprTranslator 失败抛 ParserError（**解析阶段**拦截） |
| v0 向后兼容 | `("var", "p_tall")` v0 形态仍走"值匹配"，不强制走 dispatcher |
| 子包解耦 | expr/ 可独立 import + 单测，**不依赖 interpreter/executor** |
| ADR 一致性 | v1 实现中任何与本 ADR 不一致，**显式登记**到 ADR-0004 |

## 6. ADR 冲突与偏差

**v0 (ADR-0001 §3.2) 与本 ADR 的关系**：
- **不冲突**——本 ADR 是 v0 的**求值器层**补全（v0 只规定语法，未规定求值器实现）
- v0 `If.cond = ("var", name)` / `("expr", name)` 形态**保留**——本 ADR 仅**扩展**为 4 种 kind

**与 CONTEXT-MAP.md 的关系**：
- core 上下文**包含**条件表达式子系统（"脚本系统"小节第 4 条）
- 本 ADR 落地 = core 上下文的"条件表达式"由"v0 占位"升级到"v1 完整"

## 7. 引用

- **ADR-0001** §3.2——`node if` 语法
- **ADR-0002**——v0 引擎实现完工记录
- **CONTEXT-MAP.md**——core 上下文包含"条件表达式"
- **src/core/CONTEXT.md**——架构约束（无 UI / 安全性 / 可逆性）
- **pyproject.toml**——simpleeval 依赖登记
