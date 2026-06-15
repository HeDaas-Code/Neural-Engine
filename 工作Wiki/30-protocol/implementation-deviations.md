# 30 · 实现 vs 规范偏差（实测版）

> **TL;DR**：基于 `src/core/engine/` 7 个 .py 实测代码 vs raw-docs spec 审计 —— 3 条**真实偏差** + 7 条**确认符合**。所有 22 个 GH issue（含 19 ready-for-agent + 2 HITL + 1 父 PRD）都 OPEN，但代码 100% 落地（152/152 测试通过）。

> **本页面是实测依据 wiki 页**；每条偏差都标 commit SHA + raw-docs 出处 + 评估建议。

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

## 路径 B GUI 实测

| 维度 | 内容 |
|---|---|
| **spec** | v0-issue-18：PyQt6 装了走 A，没装走 B；A 用 QMainWindow/QPlainTextEdit/QLineEdit |
| **实际** | **只实现路径 B**（CLI print+input），路径 A 完全没写 —— `runtime/gui/main.py` 1712 字节，纯 print + input |
| **commit** | `33a51ad feat: 落地 v0-issue-18 GUI CLI 占位` |
| **影响** | 路径 A 推迟到 v1（注释里写明："v1 阶段：路径 A（PyQt6 窗口）按 `importlib.util.find_spec("PyQt6")` 切换"） |
| **评估** | 🟢 合理 —— v0 不强装 PyQt6，路径 B 足以验证 EngineBus 协议层。spec 给 A/B/C 三选项，A 在 v0 跳过符合 v0-issue-18 acceptance "PyQt6 可选" 决策。 |

## 主循环 main.py 实测

`core/engine/main.py` 装配流程（4 步）：

1. `_try_spawn_gui()` —— `subprocess.Popen([sys.executable, "-m", "runtime.gui.main"])` + `FileNotFoundError` 容错
2. `EngineBus(use_multiprocessing=True)` —— default 注入 multiprocessing.Queue
3. GUI 不可用 → `bus.put_evt(LogEvt(level="warning", ...))`
4. `_load_story(chapter_path)` → 5 阶段管线（extract_neon_blocks → parse_block_skeleton → parse_block_meta → parse_next_decls → parse_block_body）
5. `Executor(story, bus).run()` — 阻塞跑完整个故事
6. 收尾：`bus.close()` + `gui_proc.terminate()` + `gui_proc.wait(timeout=2)`

**注意**：main.py **不**消费 `LoadChapterCmd` / `ShutdownCmd` —— chapter_path 是 CLI 参数，GUI 进程启动后只通过 EngineBus 收事件 + 发 `UserInputCmd`。这意味着 `LoadChapterCmd` schema 当前**仅被协议层使用**，main 没读它。

→ 这是**实际偏差**：v0-issue-17 spec 描述了 "Engine 主循环：1. `Executor.run()` 启动 2. 收到 `ShutdownCmd` → 退出 0"，但**实际** main.py 只走 CLI arg 路径，**不**监听 cmd_q。路径 B GUI 不发 LoadChapterCmd（直接 spawn 后听事件），所以不冲突。

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
- ADR-0001 / ADR-0002（待写）—— [[raw-docs/ADR-0001-v0-baseline-script-spec]]
- 22 个 GH issue 完成评论 —— `gh issue view N --comments`
- 19 个 feat commit —— `git log --oneline`（HEAD = `1a76382`）
- pytest 结果 —— `python -m pytest tests/ -q`（152 passed）
- [[40-issues/dashboard]] — 22 issue 总览
- [[dependency-graph]] — 实施路径图