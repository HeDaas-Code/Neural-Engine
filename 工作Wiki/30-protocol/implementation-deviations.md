# 30 · 实现 vs 规范偏差（实测版 + CodeGraph 验证）

> **TL;DR**：基于 `src/core/engine/` 7 个 .py 实测代码 vs raw-docs spec 审计 —— 3 条**真实偏差** + 7 条**确认符合** + **4 条 CodeGraph 发现的覆盖盲点**。所有 22 个 GH issue（含 19 ready-for-agent + 2 HITL + 1 父 PRD）都 OPEN，但代码 100% 落地（152/152 测试通过）。

> **CodeGraph 索引**（2026-06-15 由 `codegraph init` 建立，37 文件 / 470 nodes / 1566 edges in 233ms）——本页面所有行号、调用关系、覆盖盲点都来自 `codegraph_explore` / `codegraph_callers` 实时查询。

## 仓库状态（2026-06-15 实测）

| 维度 | 现状 | 出处 |
|---|---|---|
| 当前 HEAD | `1a76382` feat: 落地 v0-issue-19 chapter01 fixture + 端到端集成测试 | `git log` |
| pytest | **152 passed in 1.22s**（0 failed） | `python -m pytest tests/` |
| 提交历史 | 19 个 feat commit（v0-issue-1 ~ v0-issue-19）+ 2 个 docs/初始化 commit | `git log --oneline` |
| 代码量 | `src/core/engine/` 7 个 .py（46 KB）+ `src/runtime/gui/main.py` 1.7 KB | `find src -name "*.py"` |
| 测试 | 16 个测试文件（tests/core/ 15 + tests/integration/ 2 + tests/runtime/ 1） | `find tests -name "*.py"` |
| Fixture | `chapters/chapter01.md`（1622 chars，**与 ADR §附录 A 字节级一致**） | `diff <(cat chapters/chapter01.md) <(raw-docs ADR §附录 A)` |
| Issue 状态 | **22 OPEN**（cursor 提交了代码但**未 close**——owner 动作） | `gh issue list --state open` |
| Issue 完成评论 | 22/22 都有 cursor 的"v0-issue-N 完成"评论（含 commit SHA） | `gh issue view N --comments` |

## 3 条真实偏差（实测发现）

### D-NEW-1 · `CallExpression` 包装类 vs spec 的 `Echo | In` union

| 维度 | 内容 |
|---|---|
| **spec** | v0-issue-2 工程笔记原文："`Branch.target`：`NextDecl(var_name, target_id)` \| `Echo` \| `In`（**省略 `node` 前缀**）" — 用 AST 节点 `Echo` / `In` 直接做 union |
| **实际** | `ast_nodes.py:160-171` 新增 `CallExpression(kind: str, var: str)`（kind="echo"\|"in"），`Branch.target: NextDecl \| CallExpression` |
| **commit** | `9ff1602 feat: 落地 v0-issue-2 AST 节点 dataclass + 错误类` |
| **影响** | 接口形状不同 —— spec 是"AST 节点统一"，实现是"专用包装类型"。**语义等价**（两者都把 echo/in 简写折成可识别的 token），但调用方需要 `target.kind == "echo"` 判断，**不**是 `isinstance(target, Echo)`。 |
| **评估** | 🟡 轻微偏差 —— 不破坏功能，但 spec 的"统一 AST 节点"哲学被破坏。建议：**ADR-0002 接受新设计**，把 `CallExpression` 写进规范（v0 阶段合理简化的产物）。 |

### D-NEW-2 · `ParserError.loc` 变可选

| 维度 | 内容 |
|---|---|
| **spec** | v0-issue-2 工程笔记："错误类：`ParserError(SyntaxError)` 带 `loc: BlockLocation`" |
| **实际** | `ast_nodes.py:202-207`：`ParserError(message, loc: BlockLocation \| None = None)` — `loc` 可选 |
| **commit** | `9ff1602` |
| **影响** | 错误对象**有** `loc` 属性但可能为 `None`。调用方需 `if err.loc is not None` 防御。spec 假设 loc 必填。 |
| **评估** | 🟡 轻微偏差 —— 实现放宽约束（容错更友好）。建议：**ADR-0002 记录放宽决策**。 |

### D1-confirmed · `decorator_state` 清空时机

| 维度 | 内容 |
|---|---|
| **spec** | ADR-0001 §4.1 原文："块级作用域（`node start`...`node end` 之间），不跨块继承；**同一块内多个修饰器遵循竞争机制：后到的同 key 修饰器覆盖前一个，直到遇到该 key 的休止符**" —— **没说在 node end 时清空**，但 §11 不变量 #2 说"块级作用域不跨块继承" |
| **v0-issue-15 工程笔记** | "**v0 在 `run_block` 开头清**，不是在 `End` 时清；**实施 agent 拍板**" |
| **实际** | `executor.py:459`：`self._deco_state.clear()` 在 `run_block` 入口（即 `node start` 之后立即） |
| **commit** | `af90762 feat: 落地 v0-issue-15 修饰器调度 + 块级作用域` |
| **影响** | 与 ADR §11 不变量 #2 不冲突（"不跨块继承"满足），但与"块末清空"直觉不同 —— 实现选择**进入时清**更稳妥（避免一个块末尾的修饰器被下一块继承）。 |
| **评估** | 🔴 **必须 ADR-0002 记录** —— 这是工程笔记里**明确**写为"实施 agent 拍板"的偏差，v0-issue-21 HITL 收尾必须正式登记。 |

## 7 条确认（实测 = spec）

| # | 维度 | spec 出处 | 实测代码 | 评价 |
|---|---|---|---|---|
| OK-1 | `IdStart` 单例式 sentinel | v0-issue-2 spec："单例式 sentinel" | `ast_nodes.py:196` `ID_START = IdStart()` + 模块级 | ✅ 符合 |
| OK-2 | `If.cond` 表示 | v0-issue-11：二元/多元用变量名，简略二元用表达式 | `ast_nodes.py:174` `cond: tuple[str, str]`（kind="var"\|"expr"，name） | ✅ 符合 + **更显式**（区分两种条件） |
| OK-3 | `Block.loc` 字段 | v0-issue-2："`BlockLocation(lineno, col)` 元数据" | `ast_nodes.py:114-119` `Block(... loc: BlockLocation)` | ✅ 符合 |
| OK-4 | `bytes` over wire | ADR §7.5："`json.dumps / json.loads`"（没说 bytes vs str） | `bus.py:250` `json.dumps(...).encode("utf-8")` | ✅ 合理实现（spec 没明确，bytes 更稳） |
| OK-5 | 3 Cmd schema | ADR §7.3：LoadChapterCmd / UserInputCmd / ShutdownCmd | `protocol.py:1422-1457` 三个 dataclass 完整 | ✅ 符合 |
| OK-6 | chapter01 fixture 字节级一致 | v0-issue-19 第 1 条 acceptance | `chapters/chapter01.md` 1622 chars 与 raw-docs ADR §附录 A 一致 | ✅ 符合 |
| OK-7 | pytest 全过 | PRD §11 不变量守护 | 152 passed in 1.22s | ✅ 符合 |

## 关键发现：v0-issue-15 决策的"埋雷"

`decorator_state` 清空时机是**实施 agent 拍板**改的，不是 spec 决策。raw-docs `v0-issue-15-deco-exec.md` 原文：

> **v0 在 `run_block` 开头清，不是在 `End` 时清；**实施 agent 拍板**

这意味着：
1. **v0-issue-21 HITL** 必须把这条决策写进 `docs/adr/0002-v0-engine-implementation.md`（ADR-0002），否则 ADR-0001 §4.1 与实现不一致，**§11 不变量 #2 守护测试**会判实现违反 spec。
2. 如果 owner 不希望 ADR-0001 被推翻，要么回代码（在 `run_block` 末尾清）要么回 spec（接受新决策）。

→ 这正是 owner 必须亲手做 #43 / #44 HITL 的原因 —— **agent 不能替 owner 拍 ADR 决策**。

## CodeGraph 调用关系图（实测）

### 高频被调符号

| 符号 | 位置 | caller 数 | 覆盖测试 |
|---|---|---|---|
| `EngineBus` | `bus.py:18` | **13** callers（main + GUI + tests）| ✅ `test_engine_bus.py` + `test_echo_path.py` |
| `Executor.run` | `executor.py:141` | **28** callers | ✅ 4 个 test_executor_*.py |
| `Executor` class | `executor.py:68` | **36** callers | ✅ 4 个 test_executor_*.py + 集成 |
| `main` (core) | `main.py:67` | 7 callers | ✅ `test_main_entry.py` + `test_gui_protocol.py` |
| `get_evt` | `bus.py:51` | 4 callers（GUI + tests）| ✅ `test_engine_bus.py` |
| `get_cmd` | `bus.py:42` | 3 callers | ✅ `test_engine_bus.py` + `test_echo_path.py` |
| `LoadChapterCmd` | `protocol.py:54` | 3 callers | ✅ `test_engine_bus.py` + `test_protocol_cmd.py` |

### 内部 helper（低 caller 数 = 单独测的必要性）

| 符号 | 位置 | caller 数 | 覆盖测试 |
|---|---|---|---|
| `_emit_decorator` | `executor.py:214` | 1（self）| ⚠️ **no covering tests found** |
| `_validate_target_ids` | `executor.py:84` | 1（self）| ⚠️ **no covering tests found** |
| `_drain` | `bus.py:63` | 1（self）| ⚠️ **no covering tests found** |
| `_close_queue` | `bus.py:74` | 1（self）| ⚠️ **no covering tests found** |
| `_try_spawn_gui` | `main.py:54` | 1（self）| ⚠️ **no covering tests found**（间接通过集成测试覆盖）|

## CodeGraph 发现的 4 条覆盖盲点（新增！）

> **以下盲点**通过 `codegraph_explore` 自动检测 —— 内层 helper 方法，**没有专门的单元测试**覆盖。pytest 152/152 全过 = **间接路径被走过**（helper 在其他测试路径里被调用），但**直接单测缺失**。

### GAP-1 · `EngineBus._drain` / `_close_queue`（`bus.py:63-74`）

| 维度 | 内容 |
|---|---|
| **位置** | `src/core/engine/bus.py:63, 74` |
| **职责** | 队列排空 + 关闭（v0-issue-5 acceptance "close() 排空残留"） |
| **覆盖** | 无直接单测 ——`test_engine_bus.py` 覆盖了 put/get/序列化/错误，但 `_drain` 只被 `close()` 调，路径隐式 |
| **风险** | 如果 `_drain` 实现改坏（比如改循环条件），没有任何单测报错；只有 e2e 流才能暴露 |
| **owner 评估建议** | v0-issue-21 HITL 阶段可选：补 `test_engine_bus.py::test_drain_empty_queue` / `test_close_with_pending_messages` |

### GAP-2 · `Executor._emit_decorator`（`executor.py:214`）

| 维度 | 内容 |
|---|---|
| **位置** | `src/core/engine/executor.py:214` |
| **职责** | 调度 `DecoratorCall` / `DecoratorStop` → `_deco_state` 更新 + `DecoratorEvt` 广播 |
| **覆盖** | **间接**——`test_executor_decorator.py` 测装饰器效果但走 `run_block` 全路径；`_emit_decorator` 不被外部直接调 |
| **风险** | 中等——这是 v0-issue-15 关键实现，**节点执行的核心**。如果 `DecoratorStop` 处理坏（`_deco_state[name].pop(key, None)`），只能从高阶测试看现象 |
| **owner 评估建议** | v0-issue-20 HITL 加直接单测：`test_emit_decorator_call_kv` / `test_emit_decorator_stop_unsets_key` |

### GAP-3 · `Executor._validate_target_ids`（`executor.py:84`）

| 维度 | 内容 |
|---|---|
| **位置** | `src/core/engine/executor.py:84` |
| **职责** | 构造时校验所有 `NextId.target_id` / `NextDecl.target_id` / `If.branches[i].target` 都能在 `story.blocks` 找到 |
| **覆盖** | **间接**——`test_executor_skeleton.py` 测试跨块 ID 校验通过 `Executor(story, sink)` 抛 ValueError 路径；但 `_validate_target_ids` 是私有方法，不被直接测 |
| **风险** | 低——`test_executor_skeleton.py` 已经覆盖 ValueError 抛出；只是 helper 本身没单独单测 |
| **owner 评估建议** | v0-issue-20 HITL 可选补：`test_validate_target_ids_raises_on_unknown_next_decl` |

### GAP-4 · `core.engine.main._try_spawn_gui`（`main.py:54`）

| 维度 | 内容 |
|---|---|
| **位置** | `src/core/engine/main.py:54` |
| **职责** | `subprocess.Popen(["-m", "runtime.gui.main"])` + `FileNotFoundError` 容错 |
| **覆盖** | **间接**——`test_main_entry.py` 测 GUI 不可用降级路径；但 `_try_spawn_gui` 是私有方法 |
| **风险** | 低——降级逻辑只是 `try/except FileNotFoundError` |
| **owner 评估建议** | 可选补 `test_try_spawn_gui_returns_none_when_module_missing` |

### GAP 总评

> **不是 v0 阻塞问题**——pytest 152/152 全过 = 间接覆盖足够。但 CodeGraph 的"no covering tests found"是**真信号**：说明这些 helper 只走"快乐路径"被测，**没有"边界路径"专门单测**（如 `_drain` 空队列 / `_emit_decorator` 嵌套修饰器 / `_validate_target_ids` 多分支冲突）。
>
> v0-issue-20 HITL 阶段 owner 可决定是否补这些单测（ADR-0002 决策：v0 范围还是 v1+）。

## 引用源

- `src/core/engine/` 7 个 .py —— `find src -name "*.py"`（实测全文）
- `chapters/chapter01.md` —— ADR §附录 A 字节级副本
- CodeGraph 索引 —— `codegraph init` 在 `.codegraph/codegraph.db`（1.4 MB SQLite）
- CodeGraph 调用关系 —— `codegraph_callers` / `codegraph_explore` MCP 查询
- ADR-0001 / ADR-0002 / ADR-0003 —— [[raw-docs/ADR-0001-v0-baseline-script-spec]] 等
- 22 + 8 = 30 个 GH issue —— `gh issue list --repo HeDaas-Code/Neural-Engine`
- 19 个 v0 feat commit + 1 个 v1 骨架 commit —— `git log --oneline`（v0 HEAD = `c1844d9`，v1 HEAD = `50747ec`）
- pytest 结果 —— `python -m pytest tests/ -q`（**219 passed**）
- [[40-issues/dashboard]] — 22 v0 + 8 v1 issue 总览（v1 路线图合并在本节）
- [[dependency-graph]] — v0 + v1 双子图

## 路径 B GUI 实测

| 维度 | 内容 |
|---|---|
| **spec** | v0-issue-18：PyQt6 装了走 A，没装走 B；A 用 QMainWindow/QPlainTextEdit/QLineEdit |
| **实际** | **只实现路径 B**（CLI print+input），路径 A 完全没写 —— `runtime/gui/main.py` 1712 字节，纯 print + input |
| **commit** | `33a51ad feat: 落地 v0-issue-18 GUI CLI 占位` |
| **影响** | 路径 A 推迟到 v1（注释里写明："v1 阶段：路径 A（PyQt6 窗口）按 `importlib.util.find_spec("PyQt6")` 切换"）|
| **评估** | 🟢 合理 —— v0 不强装 PyQt6，路径 B 足以验证 EngineBus 协议层。spec 给 A/B/C 三选项，A 在 v0 跳过符合 v0-issue-18 acceptance "PyQt6 可选" 决策。 |

## v1-issue-1 偏差审计（实测 0 偏差）

> **v1-issue-1 骨架 commit `2a83774` 对照 ADR-0003 §3 全部 14 个接口签名 + 错误类继承，0 偏差**。这是 v0（4 偏差）以来第一次"完美对齐 spec"的 commit——实施 agent 明显更克制。

| ADR-0003 §3 接口 | 实现 | 符合 |
|---|---|---|
| `ExprDispatcher(state, custom=None, translator=None)` | `dispatcher.py:32` 签名一致（+ `translator=None` 参数）| ✅ |
| `eval_bool(expr: str) -> bool` | `dispatcher.py:56` 签名一致 | ✅ |
| `eval_int(expr: str) -> int` | `dispatcher.py:72` 签名一致 | ✅ |
| `eval(expr: str) -> object` | `dispatcher.py:76` 签名一致 | ✅ |
| `ExprTranslator(keyword_table=None)` | `translator.py:75` 签名一致 | ✅ |
| `register_keyword(dsl_kw, py_expr)` | `translator.py:79` 签名一致 | ✅ |
| `CustomExecutor(state)` | `custom.py:39` 签名一致 | ✅ |
| `register_function(name, fn)` | `custom.py:46` 签名一致 | ✅ |
| `register_evaluator(pattern, handler)` | `custom.py:72` 签名一致 | ✅ |
| `eval_fallback(py_expr, vars) -> object` | `custom.py:85` 签名一致 | ✅ |
| `BUILTIN_FUNCS` 含 `len/int/str/float/min/max/abs/round/bool` | `builtin_funcs.py:13` 全部 9 个 | ✅ |
| `ExprError` 继承 `RuntimeError` | `errors.py:13` 继承一致 | ✅ |
| `DSLSyntaxError` 继承 `ParserError` | `errors.py:30` 继承一致 | ✅ |
| `UnsupportedNodeError(ExprError)` | `errors.py:22` 继承一致 | ✅ |
| `register_node` v2+ 占位（NotImplementedError）| `custom.py:60` raise NotImplementedError | ✅ |

**实测覆盖**（v1-issue-1 commit `2a83774` 附带的测试）：
- `test_expr_translator.py` — 11 用例（Chinese 关键字 + 简略三元 + keyword_table + 失败路径）
- `test_expr_dispatcher.py` — 10 用例（bool/int/eval/错误类型/names 引用同步）
- `test_expr_custom.py` — 8 用例（register_function/evaluator + eval_fallback 顺序）
- **合计 29 新增 v1 用例**，pytest **219/219 全过**。

**唯一剩余偏差 = 接入卡点**（不是真偏差，是 spec 没要求 v1-issue-1 改 executor）：

| 维度 | 内容 |
|---|---|
| **spec** | ADR-0003 §4 步骤 6：`executor._execute_if` 接 dispatcher（v1-issue-6 范围）|
| **实际** | v1-issue-1 commit **0 行变化** executor.py（`git diff 1a76382..2a83774 -- src/core/engine/executor.py`）|
| **commit** | `2a83774` |
| **影响** | v1-issue-6 是 spec 划清的"v1 闭环卡点"——和 v0-issue-1 留 stage 2+ 解析器一样，**按计划推进**而非偏差 |
| **评估** | 🟢 **符合 spec**——v1-issue-1 spec 没要求改 executor，v1-issue-6 才明确"executor._execute_if 接入 ExprDispatcher" |

→ **v1-issue-6（dispatcher 接入 executor，GH #50）= v1 闭环的唯一卡点**。详见 [[../20-architecture/state-machine#v1-v1-issue-6open-待实现]]。

## v1 实施覆盖（CodeGraph 调用关系，2026-06-15 实测）

```
ExprTranslator.to_python_expr  ←── ExprDispatcher.eval（✅ 内部连通）
ExprDispatcher                  ←── tests/test_expr_dispatcher.py + __init__.py import
                                   （❌ executor._execute_if 没接入）
executor._execute_if            ←── run_block（❌ 仍 v0 打桩）
```

**实测**：`grep -l "from core.engine.expr" src/` → **0 命中**（executor.py 没 import 表达式子系统）。

## 主循环 main.py 装配流程（v0-issue-17 实测）

`core/engine/main.py`（commit `12c2c6c`）6 步装配：

1. `_try_spawn_gui()` —— `subprocess.Popen([sys.executable, "-m", "runtime.gui.main"])` + `FileNotFoundError` 容错
2. `EngineBus(use_multiprocessing=True)` —— default 注入 multiprocessing.Queue
3. GUI 不可用 → `bus.put_evt(LogEvt(level="warning", ...))`
4. `_load_story(chapter_path)` → 5 阶段管线（extract_neon_blocks → parse_block_skeleton → parse_block_meta → parse_next_decls → parse_block_body）
5. `Executor(story, bus).run()` — 阻塞跑完整个故事
6. 收尾：`bus.close()` + `gui_proc.terminate()` + `gui_proc.wait(timeout=2)`

**注意**：main.py **不**消费 `LoadChapterCmd` / `ShutdownCmd`——chapter_path 是 CLI 参数，GUI 进程启动后只通过 EngineBus 收事件 + 发 `UserInputCmd`。这意味着 `LoadChapterCmd` schema 当前**仅被协议层使用**，main 没读它（详见下面 v0-issue-17 偏差段）。

## v0-issue-17 main.py 不读 cmd_q —— 偏差

| 维度 | 内容 |
|---|---|
| **spec** | v0-issue-17 工程笔记："主循环：1. Executor.run() 启动... 3. 收到 ShutdownCmd → 退出 0... GUI 不可用时降级到 headless" |
| **实际** | `main.py:1290-1360` 根本不从 bus.get_cmd() 读 cmd —— 直接加载 CLI arg 的 chapter_path + run |
| **commit** | `12c2c6c feat: 落地 v0-issue-17 core 进程入口 main.py` |
| **影响** | LoadChapterCmd / ShutdownCmd 在 v0 阶段**仅是 schema 文档**，不参与主循环。v1+ 加 GUI 主动发 LoadChapterCmd 时再启用读 cmd_q 路径。 |
| **评估** | 🟡 中等偏差 —— spec 与实现有 gap。但功能上 v0 可工作（CLI 直接传 path）。建议：**ADR-0002 记录简化**（v0 不读 cmd_q，只走 CLI arg）。 |

## v0 实施完成度（实测）

| 阶段 | 数量 | 状态 |
|---|---|---|
| 0 · 骨架（v0-issue-1） | 1 | ✅ done（`08784cc`）|
| 1 · 数据结构 + 协议（v0-issue-2 ~ 5） | 4 | ✅ done（`9ff1602` `03fdb81` `9995247` `98ff479`）|
| 2 · 解析器（v0-issue-6 ~ 12） | 7 | ✅ done（`427567a` `dafb110` `3930f7a` `e242f31` `cdaa634` `430623b` `17eb1b1`）|
| 3 · 执行器（v0-issue-13 ~ 16） | 4 | ✅ done（`c9d0fe1` `7ff4312` `af90762` `abb67ab`）|
| 4 · 入口 + GUI（v0-issue-17 ~ 18） | 2 | ✅ done（`12c2c6c` `33a51ad`）|
| 5 · 端到端（v0-issue-19） | 1 | ✅ done（`1a76382`，chapters/chapter01.md + 集成测试）|
| 6 · HITL 完工（v0-issue-20 ~ 21） | 2 | ⏳ **OPEN**（GH #43 / #44，**owner 必做**）|
| **合计** | **22** | **20 实现完成 + 2 HITL 待 owner** |

## owner 必做（v0-issue-20 #43 + v0-issue-21 #44）

按工作流，owner 需要：

### GH #43 · v0-issue-20 HITL 守护

1. 跑 `python -m pytest tests/` 全绿 → ✅ 已确认（152 passed）
2. 跑 `grep -r '"NEXT"' src/` 0 命中 → 需确认
3. 跑 `grep -r 'pickle\|msgpack' src/` 0 命中 → 需确认
4. 跑 `grep -r 'TODO\|FIXME' src/` 0 命中 → 需确认
5. 写 `docs/audit/v0-invariant-audit.md` 记录结果
6. 逐条勾 §8 MVP 表 18 条（v0-issue-19 acceptance）
7. 在 issue 贴完成评论 + `gh issue close 43`

### GH #44 · v0-issue-21 ADR-0002 完工

1. 写 `docs/adr/0002-v0-engine-implementation.md`，至少包含：
   - **D1-confirmed**：`decorator_state` 在 `run_block` 开头清（v0-issue-15 决策，与 ADR §4.1 不一致 → owner 接受）
   - **D-NEW-1**：`CallExpression` 包装类（v0-issue-2 实际设计，与 spec `Echo | In` union 不一致 → owner 接受）
   - **D-NEW-2**：`ParserError.loc` 变可选（owner 接受放宽）
   - **v0-issue-17 main.py 不读 cmd_q**：v0 简化（owner 接受）
2. `gh issue close 22`（父 PRD）
3. `gh issue close 23-#44`（v0-issue-1 ~ v0-issue-21，22 条）

## 引用源

- `src/core/engine/` 7 个 .py —— `find src -name "*.py"`（实测全文）
- `chapters/chapter01.md` —— ADR §附录 A 字节级副本
- ADR-0001 / ADR-0002 / ADR-0003 —— [[raw-docs/ADR-0001-v0-baseline-script-spec]] 等
- 22 + 8 = 30 个 GH issue —— `gh issue list --repo HeDaas-Code/Neural-Engine`
- 19 个 v0 feat commit + 1 个 v1 骨架 commit —— `git log --oneline`（v0 HEAD = `c1844d9`，v1 HEAD = `50747ec`）
- pytest 结果 —— `python -m pytest tests/ -q`（**219 passed**）
- [[40-issues/dashboard]] — 22 v0 + 8 v1 issue 总览（v1 路线图合并在本节）
- [[dependency-graph]] — v0 + v1 双子图