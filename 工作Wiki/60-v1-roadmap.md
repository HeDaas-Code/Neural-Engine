# 60 · v1 路线图与实施状态

> **TL;DR**：v1 表达式子系统（ADR-0003 / PRD-0002）**只完成了 v1-issue-1（骨架）**——6 个 .py 子包 + 37 个测试通过（219/219 全绿）。**v1-issue-2 ~ 7（真实现）全部 OPEN 未做**——executor 仍走 v0 打桩路径，`chapter01.md` 的 `node if` 还没真求值。

> **本页面是 v1 项目的 wiki 入口**。维护规则同 [[../30-protocol/implementation-deviations]] —— 每条事实都有 raw-docs / commit / CodeGraph 出处。

## v1 实施状态（2026-06-15 实测）

| v1-issue | GH # | 标题 | 状态 | 实施 commit | 测试 |
|---|---|---|---|---|---|
| 父 PRD | #53 | PRD: v1 表达式子系统 | ❌ OPEN | — | — |
| v1-issue-1 | #52 | 表达式子系统骨架 (ADR-0003) | ✅ done | `2a83774` | 37 用例 |
| v1-issue-2 | #46 | ExprTranslator 拓展（Chinese 关键字 + keyword_table）| ⚠️ **OPEN（被骨架超额完成）** | `2a83774`（骨架 commit 内已实现）| 11 用例覆盖 |
| v1-issue-3 | #47 | CustomExecutor 完整实现 | ⚠️ **OPEN（被骨架超额完成）** | `2a83774`（骨架 commit 内已实现）| 8 用例覆盖 |
| v1-issue-4 | #48 | ExprDispatcher 完整三层调度 | ⚠️ **OPEN（被骨架超额完成）** | `2a83774`（骨架 commit 内已实现）| 10 用例覆盖 |
| v1-issue-5 | #49 | If.cond 扩 bool_expr + range kind | ❌ **OPEN（未做）** | — | 0 用例 |
| v1-issue-6 | #50 | executor._execute_if 接入 ExprDispatcher | ❌ **OPEN（未做）** | — | 0 用例 |
| v1-issue-7 | #51 | 端到端 chapter01.md 真求值 + 测试全绿 | ❌ **OPEN（未做）** | — | 0 用例 |
| cursor 自评 | #54 | feat(expr): v1-issue-1 ... | ❌ OPEN（cursor "实施完成"评论，但实际只骨架） | — | — |

**实测 2026-06-15**：**219/219 PASSED**（152 v0 + 30 v0-issue-20 守护 + 37 v1-issue-1 骨架）。但 v0-issue-20 §8 MVP 表新增的 if 打桩测试**仍叫 `_stub_*`**——v1 真求值测试没加。

## 关键事实

### 1. v1-issue-1 是骨架，但超额完成了 v1-issue-2/3/4

`2a83774 feat(expr): 落地 v1-issue-1 表达式子系统骨架 (ADR-0003)` commit 内容：

| 模块 | 状态 | 备注 |
|---|---|---|
| `expr/__init__.py` | ✅ 真实现 | 公开 API 聚合 |
| `expr/errors.py` | ✅ 真实现 | `ExprError` / `DSLSyntaxError` / `UnsupportedNodeError` |
| `expr/builtin_funcs.py` | ✅ 真实现 | 9 个函数白名单 |
| `expr/translator.py` | ✅ **真实现**（不在骨架范围）| Chinese 关键字 + 简略三元 + keyword_table |
| `expr/dispatcher.py` | ✅ **真实现**（不在骨架范围）| translator → simpleeval → fallback 三层调度 + 错误捕获 |
| `expr/custom.py` | ✅ **真实现**（不在骨架范围）| register_function / register_evaluator / eval_fallback |

→ **v1-issue-2/3/4 的真实现已在骨架 commit 里做完**（spec 超额 1.5 倍）。剩下没做的只是 v1-issue-5/6/7（dispatcher 接入 executor + end-to-end 真求值）。

### 2. dispatcher 没接入 executor —— 这是 v1 真正的剩余工作

**CodeGraph 调用关系**（实测 2026-06-15）：

```
ExprTranslator.to_python_expr  ←── ExprDispatcher.eval（✅ 内部连通）
ExprDispatcher                  ←── 只有测试文件调用（❌ executor 没接入）
executor._execute_if            ←── run_block（❌ 仍 v0 打桩）
```

`git diff 1a76382 HEAD -- src/core/engine/executor.py` —— **0 行变化**。`executor.py:227` 仍是 v0 打桩的 `chosen = if_node.branches[0]`。

→ **v1-issue-6（dispatcher 接入 executor） = v1 闭环的关键卡点**。

### 3. v1-issue-1 commit 不动 executor 是合理的——spec 划清边界

ADR-0003 §3 明确：

> v0 `interpreter.py` **不改动公开 API**（仅顶部加 v1 指针注释）
> 与 v0 模块的关系：executor.py 依赖 expr/，_execute_if 调用 dispatcher.eval_bool

**但 ADR 没硬性约束 v1-issue-1 必须改 executor**。v1-issue-6 才明确"executor._execute_if 接入 ExprDispatcher"。

→ v1-issue-1 commit 不改 executor **符合 spec**，v1-issue-6 才是真正动 executor 的卡点。

### 4. 文档/Issue 不匹配 —— cursor 写"实施完成"但实际只做骨架

`#54 feat(expr): v1-issue-1 表达式子系统骨架 (ADR-0003)` body 写"closes #52 + #53"——但 cursor **没**调 `gh issue close`，所有 issue 仍 OPEN。

→ 跟 v0 一样的问题：cursor **用 `gh issue comment` 发完成报告，但没 `gh issue close`**。**owner 必做**手工 close 或调 agent 代关。

### 5. v1 依赖链路 + 剩余工作

```
v1-issue-1 ✅  骨架 + 超额完成 (2/3/4)
    ↓
v1-issue-5 ❌  If.cond 扩 bool_expr / range kind
    ↓
v1-issue-6 ❌  executor._execute_if 接 dispatcher  ← 真正卡点
    ↓
v1-issue-7 ❌  端到端 chapter01.md 真求值
    ↓
HITL ❓       ADR-0004 完工记录 + 偏差登记
```

**最少剩余工作量**：
- **v1-issue-5**：interpreter.py 改 1 处（parse_if_stmt 增 `bool_expr` kind）；ast_nodes.py 加新 If 形态——~30 行
- **v1-issue-6**：executor.py 改 1 处（_execute_if 分流按 kind）；~30 行
- **v1-issue-7**：test_executor_if.py 改 7 条（`test_*_stub_*` 改名 `test_*_eval_*` 加新断言）；chapter01.md 不动（已是 fixture 副本）；~50 行
- **总**：3 个 issue × ~50 行 = 1-2 小时

## v1-issue-1 偏差审计（实测 vs ADR-0003）

> **全是 ✅ 符合 spec**——v1-issue-1 commit 的所有实现都对照过 ADR-0003 §3 接口签名，**没有偏差**。这点和 v0 4 条偏差不同——v1 实施更克制。

| ADR-0003 §3 接口 | 实现 | 符合 |
|---|---|---|
| `ExprDispatcher(state, custom=None, translator=None)` | `dispatcher.py:32` 签名一致 | ✅ |
| `eval_bool(expr: str) -> bool` | `dispatcher.py:56` 签名一致 | ✅ |
| `eval_int(expr: str) -> int` | `dispatcher.py:72` 签名一致 | ✅ |
| `eval(expr: str) -> object` | `dispatcher.py:76` 签名一致 | ✅ |
| `ExprTranslator(keyword_table=None)` | `translator.py` 签名一致 | ✅ |
| `register_keyword(dsl_kw, py_expr)` | `translator.py:73` 签名一致 | ✅ |
| `CustomExecutor(state)` | `custom.py:30` 签名一致 | ✅ |
| `register_function(name, fn)` | `custom.py:39` 签名一致 | ✅ |
| `register_evaluator(pattern, handler)` | `custom.py:56` 签名一致 | ✅ |
| `eval_fallback(py_expr, vars) -> object` | `custom.py:67` 签名一致 | ✅ |
| `BUILTIN_FUNCS` 含 `len/int/str/float/min/max/abs/round/bool` | `builtin_funcs.py:11` 全部 9 个 | ✅ |
| `ExprError` 继承 `RuntimeError` | `errors.py:15` 继承一致 | ✅ |
| `DSLSyntaxError` 继承 `ParserError` | `errors.py:29` 继承一致 | ✅ |
| `UnsupportedNodeError(ExprError)` | `errors.py:23` 继承一致 | ✅ |
| `register_node` v2+ 占位（NotImplementedError）| `custom.py:50` raise NotImplementedError | ✅ |

**v1-issue-1 的 0 偏差** —— 这是 v0 以来第一次"完美对齐 spec"的 commit。

## v1 剩余工作与 owner 决策

### A. 决策：剩余 6 个 issue 由谁做？

| 路径 | 谁 | 时间 | 风险 |
|---|---|---|---|
| **owner 自己** | 你手写 executor.py 改 ~30 行 | ~1-2 小时 | 低 |
| **cursor 续做** | 在 Cursor IDE 里继续 v1-issue-5/6/7 | ~1-2 小时 | 低（cursor 已写好 prompt 上下文）|
| **agent 代做** | Hermes agent 写代码 + owner review | **不推荐**——你的主要任务约定是"维护 Wiki + 审计"，不写代码 |

### B. 决策：HITL（ADR-0004）写不写？

| 选项 | 含义 |
|---|---|
| **写** | v1-issue-8 HITL：跑 dispatcher 真求值 + 写 `docs/adr/0004-v1-expression-implementation.md` |
| **不写** | v0 一样用 ADR-0002 模板套；但 v1-issue-1 0 偏差，ADR-0004 可能很薄 |

### C. 决策：v1-issue-2/3/4 要不要 close？

| 选项 | 含义 |
|---|---|
| **close** | 因为骨架 commit 已超额实现这些 |
| **留 OPEN** | 等 v1 完整闭环（5/6/7 done）后再统一关 |

## CodeGraph 调用关系图（v1 实施后实测）

```
┌────────────────────────────────────────────┐
│ tests/ (37 用例)                          │
│   test_expr_translator.py                  │
│   test_expr_dispatcher.py                  │
│   test_expr_custom.py                      │
└──────────┬─────────────────────────────────┘
           ↓ 通过 import
┌────────────────────────────────────────────┐
│ src/core/engine/expr/                     │
│   __init__.py (公开 API)                   │
│   errors.py (3 错误类)                     │
│   builtin_funcs.py (BUILTIN_FUNCS)         │
│   translator.py ←── dispatcher.eval        │
│   custom.py ←── dispatcher.eval (fallback) │
│   dispatcher.py (SimpleEval 注入)          │
└──────────┬─────────────────────────────────┘
           ↓ v1-issue-6 接入点（❌ 未做）
┌────────────────────────────────────────────┐
│ src/core/engine/executor.py:227           │
│   _execute_if  ── 还是 v0 打桩！          │
│   chosen = if_node.branches[0]            │
└────────────────────────────────────────────┘
```

**红线**：v1-issue-6 是 v1 闭环的**唯一卡点**。

## 引用源

- ADR-0003 v1 表达式子系统架构：`docs/adr/0003-v1-expression-subsystem.md`
- PRD-0002 v1 表达式子系统：`docs/prds/0002-v1-expression-subsystem.md`
- v1-issue-1 commit：`2a83774 feat(expr): 落地 v1-issue-1 表达式子系统骨架 (ADR-0003)`
- 6 个 .py 子包：`src/core/engine/expr/`
- 3 个测试文件：`tests/core/test_expr_{translator,dispatcher,custom}.py`
- 8 个 GH issue：`gh issue list --repo HeDaas-Code/Neural-Engine | grep v1-issue`
- [[dashboard]] — 22 v0 + 8 v1 issue 列表
- [[../30-protocol/implementation-deviations]] — v0 偏差登记（v1 暂无偏差）