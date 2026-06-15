# PRD — v1 表达式子系统（v1 Expression Subsystem）

> 对应 ADR：`docs/adr/0003-v1-expression-subsystem.md`
> 上下文：`core`（主）
> 状态：待发布 GitHub Issue · `ready-for-agent`

---

## Problem Statement

ADR-0001 §3.2 规定 `node if` 语法（二元 / 多元 / 简略二元），ADR-0002 §偏差登记 记录 v0 的 `_execute_if` **打桩实现**（永远选第一分支）。

v0 阶段故意不打桩——`If` 节点正确建立，`If.cond` 已有 `("var"|"expr", name)` 形态，`parser.py` 能解析各种条件写法，但 `executor._execute_if` 只是硬编码 `branches[0]`。

v1 要把"打桩"替换成**真求值**：给定 `p_tall >= 18 且 p_age == 1` 这类表达式，引擎必须知道选哪个分支。

## Solution

按 ADR-0003 §1 决策，交付**表达式子系统**（`src/core/engine/expr/`）：

- `ExprTranslator`：DSL 文本（含中文字段名）→ Python 表达式字符串
- `ExprDispatcher`：三层调度（translator → simpleeval → CustomExecutor fallback）
- `CustomExecutor`：simpleeval 兜底 + 业务侧扩展钩子
- `executor._execute_if` 接入 `ExprDispatcher`，按 `If.cond` 形态真选分支
- `If.cond` 扩 `"bool_expr"` / `"range"` 两种 kind（ADR-0003 §4 决策 4）

实现完成后，`chapters/chapter01.md` 中的 `node if` 能**真求值**并走对应分支，`executor._execute_if` 不再是打桩。

## User Stories

### 表达式翻译
1. 作为引擎开发者，我希望 `ExprTranslator.to_python_expr("p_tall 大于等于 18")` 返回 `"p_tall >= 18"`，以便 DSL 不被 simpleeval Python 语法约束
2. 作为引擎开发者，我希望 `ExprTranslator` 能处理 Chinese 关键字（`且`/`或`/`非`/`等于`/`大于`/`小于`/`大于等于`/`小于等于`/`不等于`），以便剧本作者用自然中文写条件
3. 作为剧情创作者，我希望 `ExprTranslator` 支持自定义中缀命名（`translator.register_keyword("在古代", "p_era==1")`），以便 v2+ 扩展 DSL 语义
4. 作为引擎开发者，我希望翻译失败的 DSL 抛 `DSLSyntaxError`（继承 `ParserError`），以便**解析阶段尽早报错**，不在执行阶段静默失败

### 表达式求值
5. 作为引擎开发者，我希望 `ExprDispatcher.eval_bool("p_tall 大于等于 18 且 p_age 等于 1")` 返回正确 bool，以便 `executor._execute_if` 能做条件分支选择
6. 作为引擎开发者，我希望 `ExprDispatcher` 内置函数白名单（`len`/`int`/`str`/`bool`/`min`/`max`/`abs`/`round`），以便剧本表达式可以调这些函数
7. 作为引擎开发者，我希望 `ExprDispatcher` 同步 `state.vars` 引用（每次 `eval` 前更新 `SimpleEval.names`），以便 executor 修改变量后下次 `eval` 看到新值
8. 作为测试作者，我希望 `ExprDispatcher` 对未定义变量 / 除零 / 语法错抛 `ExprError`，以便错误有明确类型

### 错误分层
9. 作为引擎开发者，我希望 simpleeval **UnsupportedNode（TypeError）** 和 **FunctionNotDefined（InvalidExpression）** 两种失败都走 `CustomExecutor.eval_fallback`，以便剧情自定义函数（如 `is_quest_done(5)`）能兜底
10. 作为业务开发者，我希望通过 `CustomExecutor.register_function(name, fn)` 注册剧情自定义函数，`ExprDispatcher` 把它注入 simpleeval.functions 后可直接调用
11. 作为业务开发者，我希望通过 `CustomExecutor.register_evaluator(pattern, handler)` 注册正则匹配处理器，`CustomExecutor.eval_fallback` 按注册顺序匹配，第一个命中者接管求值

### If 节点扩 kind
12. 作为引擎开发者，我希望 `If.cond = ("bool_expr", "p_tall 大于等于 18")` 时 `executor._execute_if` 调用 `dispatcher.eval_bool()`，以便 v0 的 `node if expr` 简略二元能真求值
13. 作为引擎开发者，我希望 `If.cond = ("var", "p_tall")` 旧形态（v0 兼容）仍走"值匹配"逻辑（`state.vars[p_tall] == branch.value`），**不进 dispatcher**，以便 v0 既有 fixture 不受影响
14. 作为引擎开发者，我希望 `If.cond = ("range", (lo, hi))` 时按范围匹配分支，以便 v2+ 支持 `1~10:ce_ok, else:ce_ng` 语法

### 端到端
15. 作为项目所有者，我希望 `chapters/chapter01.md` 中 `node [p_score 大于 50?ce_high:ce_low]` 能在 `p_score=60` 时走 `ce_high`、`p_score=30` 时走 `ce_low`，整链路可重放
16. 作为 CI，我希望 `tests/core/test_expr_*.py`（3 个文件）与 `tests/core/test_executor_if.py`（v1 升级）有自动化断言，断言 `dispatcher.eval_bool` 与 `executor._execute_if` 行为一致

## Implementation Decisions

### 总体架构

- **`src/core/engine/expr/` 子包**（ADR-0003 §2 决策 2），与 `interpreter/` / `executor/` 平级
- **simpleeval>=1.0** 运行时依赖（写入 `pyproject.toml`）
- **Python 3.11+**（simpleeval 要求）
- v0 `interpreter.py` **不改动公开 API**（仅顶部加 v1 指针注释）

### 实施步骤（按 ADR-0003 §4）

| Step | 内容 | GH issue |
| --- | --- | --- |
| 1 | 建 `expr/` 子包骨架 + `__init__` + `errors.py` + `builtin_funcs.py` | **v1-issue-1 ✅ 已落地** |
| 2 | `ExprTranslator` 拓展（Chinese 关键字 / keyword_table） | v1-issue-2 |
| 3 | `CustomExecutor` 完整 register_* 实现 | v1-issue-3 |
| 4 | `ExprDispatcher` 完整三层调度 | v1-issue-4 |
| 5 | `If.cond` 扩 `"bool_expr"` / `"range"` 两种 kind | v1-issue-5 |
| 6 | `executor._execute_if` 接入 `ExprDispatcher` | v1-issue-6 |
| 7 | 端到端：`chapter01.md` 真求值 + 走真分支 | v1-issue-7 |

### 模块清单

| 模块 | 路径 | 职责 |
| --- | --- | --- |
| 错误类 | `expr/errors.py` | `ExprError` / `DSLSyntaxError` / `UnsupportedNodeError` |
| 函数白名单 | `expr/builtin_funcs.py` | `BUILTIN_FUNCS` 常量 |
| 翻译器 | `expr/translator.py` | DSL → Python 表达式字符串 |
| fallback 钩子 | `expr/custom.py` | `CustomExecutor`（register_function / register_evaluator / eval_fallback） |
| 调度器 | `expr/dispatcher.py` | `ExprDispatcher`（translator → simpleeval → fallback） |
| if 节点 | `ast_nodes.py` | `If.cond` 新增 kind |

## Acceptance Criteria

- [ ] `ExprTranslator.to_python_expr("p_tall 大于等于 18 且 p_age 等于 1")` → `"p_tall >= 18 and p_age == 1"`
- [ ] `ExprDispatcher.eval_bool("p_tall >= 18")` 在 `state.vars["p_tall"]=20` 时返回 `True`
- [ ] `ExprDispatcher` 遇未注册函数 `is_quest_done(5)` 走 `CustomExecutor.eval_fallback`
- [ ] `CustomExecutor.register_function("rand_scene", fn)` 后 `dispatcher.eval("rand_scene()")` 直接调 fn
- [ ] v0 `If.cond = ("var", "p_tall")` 旧形态**不走** dispatcher（v0 fixture 不受影响）
- [ ] `chapter01.md` 的 `node [p_score 大于 50?ce_high:ce_low]` 在 `p_score=60` 时走 `ce_high`
- [ ] 219 → 全部（含 v1 新增）测试通过

## Out of Scope（v1 不做）

- 范围匹配 `1~10`（v2+）
- 自定义 AST 节点（`register_node`，v2+）
- 异步表达式（v3+）
- 表达式缓存 / LRU（性能优化，v3+）
- 其他求值器（asteval / 手写 mini，暂不需要）
- 插件系统（v3+ 才可能需要）

## Further Notes

- ADR-0003 §5 **不变量守护**是本 PRD 完成后的代码审查依据——任何与 ADR-0003 不一致必须**显式登记**到 ADR-0004
- 本 PRD **不涉及** GUI / runtime 改动——`ExprDispatcher` 纯 core 层，无 UI 依赖
- 完成后在 `docs/adr/` 写 ADR-0004（v1 表达式子系统实现完工记录）
