# 阶段三 Issue 列表：方法级审计（Method-Level Audit）

> **关联 PDR**：[`docs/pdr/phase3-method-audit.md`](../pdr/phase3-method-audit.md)
> **审计依据**：[`docs/audit/v2-independent-audit-pm.md`](../audit/v2-independent-audit-pm.md) + [`docs/ROADMAP.md`](../ROADMAP.md)
> **基线**：阶段二已完成（287 passed / 92% 覆盖率 / ruff 30 errors）
> **作者**：pdr-analyst
> **日期**：2026-06-25
> **状态**：待 PM / owner 拍板分派

---

## 0. 概览

**7 个原子 issue**（在 5-7 范围内），按"产出物"组织：

| 类别 | 编号 | 标题 | 估时 | 依赖 | 类型 |
|---|---|---|---|---|---|
| 产出 1 | P3-001 | 编写运行时信息流图（Mermaid flowchart 跨模块追踪） | 3-4 小时 | 无 | docs (markdown + mermaid) |
| 产出 2 | P3-002 | 编写模块依赖图（Mermaid graph + 表格） | 2-3 小时 | 无 | docs (markdown + mermaid) |
| 产出 3 | P3-003 | 编写预留接口清单（≥ 6 个 EP，每个含 v2 用例） | 3-4 小时 | 无 | docs (markdown) |
| 产出 4 | P3-004 | 编写 public API 清单（≥ 50 个 API + 测试覆盖度） | 3-4 小时 | 无 | docs (markdown) |
| 产出 5 | P3-005 | 编写状态空间 + 进程边界附录 | 2-3 小时 | 无 | docs (markdown) |
| 收尾 | P3-006 | 汇总 + 交叉校验 + open questions 文档 | 1-2 小时 | P3-001 ~ P3-005 | docs (markdown) |
| 验收 | P3-007 | 渲染验证（Mermaid 可视）+ diff 校验（src/ 不变） | 30 分钟 | P3-006 | verify |

**依赖关系**：

```
P3-001 ─┐
P3-002 ─┤
P3-003 ─┼─→ P3-006（汇总 + 交叉校验） ─→ P3-007（渲染验证 + diff 校验）
P3-004 ─┤
P3-005 ─┘
```

**5 个核心编写 issue 全部互相独立**（产出不同文件），可由文档撰写者全并行。

**并行窗口**：

```
         ┌─ P3-001 (3-4 小时) ─┐
         ├─ P3-002 (2-3 小时) ─┤
 Window1  ├─ P3-003 (3-4 小时) ─┼─→ Window2 ─→ P3-006 (1-2 小时) ─→ P3-007 (30 分钟)
         ├─ P3-004 (3-4 小时) ─┤
         └─ P3-005 (2-3 小时) ─┘
```

---

## A. 产出物 1（Category info-flow）

### P3-001 · 编写运行时信息流图（Mermaid flowchart 跨模块追踪）

| 项 | 内容 |
|---|---|
| **ID** | P3-001 |
| **类型** | docs（markdown + mermaid） |
| **估时** | M（3-4 小时） |
| **依赖** | 无 |
| **风险** | LOW |
| **GitHub** | 模板待定 |
| **目标** | 落 `docs/audit/phase3-method-audit/01-info-flow.md`，含可渲染 Mermaid flowchart + 关键链路详解 |
| **上下文** | 阶段一/二做了"代码级"审计（修具体 bug）。阶段三前奏升级到"方法级"——需要先把"端到端信息流"画清楚，让 v2 三大功能（PyQt6 GUI / 章节加载器 / 存档）能精准插入。当前 `src/core/engine/` 8 文件 + `src/runtime/gui/main.py` + `src/core/engine/expr/` 6 文件之间存在多链路（解析 → 执行 → 事件总线 → GUI 渲染；用户输入 → 命令总线 → 执行），无单一图表可参考 |

**验收标准**（全部必须通过）：

1. **文件落盘**：`docs/audit/phase3-method-audit/01-info-flow.md` 存在
2. **Mermaid flowchart**：
   - 单图节点数 ≤ 30（超过则拆多张子图）
   - 标注每个节点的源文件 + 行号（如 `Main[main.py:103-173]`）
   - 标注每条边的数据形态（dict / bytes / AST node / event dataclass）
   - GitHub / VSCode preview 直接可见，无 syntax error
3. **总览图**：覆盖 5 条主链路
   - 链路 A：CLI argv → `_load_story` → `extract_neon_blocks` → 4 个 parse_* → Block AST → Story
   - 链路 B：Story → Executor.run → `_execute_block_loop` → `run_block`（9 节点 dispatch）
   - 链路 C：run_block → `_execute_if` → dispatcher.eval_bool → branch select → NEXT 跳转
   - 链路 D：Executor.put_evt → EngineBus.put_evt → JSON → multiprocessing.Queue → GUI.get_evt → 渲染
   - 链路 E：GUI.input → put_cmd(UserInputCmd) → EngineBus.get_cmd → Executor.sink.get_cmd → state.vars 写入
4. **关键链路详解**：每条链路 1-2 页，含：
   - 输入 / 输出 / 中间状态
   - 异常路径（如 `LoadChapterCmd` 走不到——ADR-0002 D-main）
   - 与 ADR-0001 §7 / ADR-0004 §3 / v2 审计 §3.2 的对应
5. **不修改 src/**：git diff 验证 `src/` 为空

**复杂度判断依据**：需读 11 个源文件 + 4 份 ADR + 1 份 v2 审计 + 2 份 ROADMAP，约 5000 行材料。文档撰写者工作量主要在 cross-reference，不是 grep。

---

## B. 产出物 2（Category module-deps）

### P3-002 · 编写模块依赖图（Mermaid graph + 表格详表）

| 项 | 内容 |
|---|---|
| **ID** | P3-002 |
| **类型** | docs（markdown + mermaid） |
| **估时** | M（2-3 小时） |
| **依赖** | 无 |
| **风险** | LOW |
| **GitHub** | 模板待定 |
| **目标** | 落 `docs/audit/phase3-method-audit/02-module-deps.md`，含 Mermaid graph + 表格详表 + 无环验证 |
| **上下文** | v2 审计 §3.2 已手工梳理过模块依赖（无环），但无单一图表 / 表格可参考。v2 章节加载器引入新模块（`ChapterManager`）+ v2 PyQt6 GUI 引入新模块（`QMainWindow` / `QTextEdit` / `QLineEdit`）时，需明确"加在哪一层、不破坏现状"。当前模块清单：`src/core/engine/` 8 文件（ast_nodes / bus / executor / interpreter / main / protocol）+ `src/core/engine/expr/` 6 文件（`__init__` / builtin_funcs / custom / dispatcher / errors / README）+ `src/runtime/gui/main.py` |

**验收标准**（全部必须通过）：

1. **文件落盘**：`docs/audit/phase3-method-audit/02-module-deps.md` 存在
2. **Mermaid graph**：
   - 单图节点数 ≤ 20
   - 边标注 `from X import Y` 的具体符号
   - GitHub / VSCode preview 直接可见，无 syntax error
3. **表格详表**：列出**所有** `import` 关系
   - 源模块 → 目标模块 → 导入符号 → 位置（行号）
   - 至少 30 行（每个文件的 import 关系都列）
   - 区分 `core` / `editor` / `runtime` 三个 CONTEXT 边界
4. **无环验证**：
   - 明确写"v2 审计 §3.2 已确认 0 循环依赖"
   - 列出验证方法（如 `grep -r "from core.engine" src/runtime` 等价扫描）
   - 当前状态：✅ 无环
5. **不修改 src/**：git diff 验证 `src/` 为空

**复杂度判断依据**：模块清单已知（8 + 6 + 1 = 15 个文件），依赖关系相对清晰（v2 审计 §3.2 已梳理）。文档撰写者主要做"可视化 + 表格化"。

---

## C. 产出物 3（Category extension-points）

### P3-003 · 编写预留接口清单（≥ 6 个 EP，每个含 v2 用例）

| 项 | 内容 |
|---|---|
| **ID** | P3-003 |
| **类型** | docs（markdown） |
| **估时** | L（3-4 小时） |
| **依赖** | 无 |
| **风险** | LOW |
| **GitHub** | 模板待定 |
| **目标** | 落 `docs/audit/phase3-method-audit/03-extension-points.md`，≥ 6 个 EP，每个含位置 / signature / 接入点 / 当前用例 / v2 怎么用 / 风险 / 测试覆盖 7 项 |
| **上下文** | ROADMAP §3 P0/P1/P2 全功能规划 + ADR-0003 §3（CustomExecutor / register_function / register_evaluator）+ ADR-0004 §3.4 F4（@LLM-jud 远期）+ v2 审计 P2-A2（`__init__.py` 空文件无 `__all__`）提示了多个 v2 接入点。每个 EP 必须明确"v2 怎么用"——这是本任务的核心增值 |

**验收标准**（全部必须通过）：

1. **文件落盘**：`docs/audit/phase3-method-audit/03-extension-points.md` 存在
2. **EP 数量**：≥ 6 个，建议 8 个（EP-01 ~ EP-08 已列在 PDR §4.3）：
   - **EP-01**：`CustomExecutor.register_function`（剧情自定义函数）
   - **EP-02**：`CustomExecutor.register_evaluator`（自定义表达式 - `@LLM-jud` 钩子）
   - **EP-03**：`EventSink` Protocol（替换 Bus 的替代渲染器）
   - **EP-04**：`BUILTIN_FUNCS` 注释行扩展位（v2 表达式系统增强）
   - **EP-05**：`_try_spawn_gui`（GUI 子进程切换）
   - **EP-06**：`DecoratorEvt` call vs stop 区分（v2 审计 P1-A6 改造位）
   - **EP-07**：`src/runtime/` 预留位（Save/Load/Audio/Video）
   - **EP-08**：`src/core/decorators/` 修饰器运行时钩子预留位
3. **每个 EP 7 项齐全**：
   - 位置（含行号，如 `src/core/engine/expr/custom.py:113-120`）
   - signature（函数/类签名）
   - 接入点（如何调用）
   - 当前用例（已有测试或生产代码引用）
   - v2 怎么用（具体到 ROADMAP §3.X + 代码示例）
   - 风险（LOW / MEDIUM / HIGH + 说明）
   - 测试覆盖（具体测试文件 + 百分比）
4. **v2 改造位引用**：每个 EP 明确引用 ROADMAP §3 具体小节（如 §3.1 / §3.2 / §3.3 / §3.6 / §3.7）
5. **代码示例**：≥ 3 个 EP 含 Python 代码示例（v2 怎么接入）
6. **不修改 src/**：git diff 验证 `src/` 为空

**复杂度判断依据**：每个 EP 需读相关源文件 + 对应 ADR + ROADMAP 对应小节 + 现有测试代码。8 个 EP × 30-45 分钟 ≈ 4-6 小时，下限取 3-4 小时（高效复用 v2 审计 P0/P1/P2 表 + ADR 现成材料）。

---

## D. 产出物 4（Category public-api）

### P3-004 · 编写 public API 清单（≥ 50 个 API + 测试覆盖度）

| 项 | 内容 |
|---|---|
| **ID** | P3-004 |
| **类型** | docs（markdown） |
| **估时** | L（3-4 小时） |
| **依赖** | 无 |
| **风险** | LOW |
| **GitHub** | 模板待定 |
| **目标** | 落 `docs/audit/phase3-method-audit/04-public-api.md`，≥ 50 个 public API，每个含用途 / 调用方 / 测试覆盖 |
| **上下文** | 当前模块 7 个（core.engine 6 + runtime.gui 1），每个模块都有 1-23 个 public 符号。`src/core/engine/expr/__init__.py` 已有 `__all__`（5 个），但其他模块 `__init__.py` 空（P2-A2 已登记）。v2 三大功能开发时，新人需要快速找到"我能调什么、谁在调、有测试吗"——本清单就是新人手册 |

**验收标准**（全部必须通过）：

1. **文件落盘**：`docs/audit/phase3-method-audit/04-public-api.md` 存在
2. **公共 API 数量**：≥ 50 个，建议 ~62 个（按 PDR §4.4 总览速查表）
3. **API 来源**：列出**所有** `from X import Y` 中非 `_` 前缀的 Y
   - 遍历 7 个模块（ast_nodes / bus / executor / interpreter / main / protocol / expr + runtime.gui.main）
   - 含 sentinel 单例（`START` / `END` / `ID_START`）和 kind 常量（`VAR_KIND` / `EXPR_KIND` / `BOOL_EXPR_KIND`）
4. **每个 API 3 项齐全**：
   - 用途（1 句话说明做什么）
   - 调用方（具体哪些模块 import 它）
   - 测试覆盖（100% / 89% / 70% / N/A 明确数字 + 数据来源）
5. **测试覆盖度数据来源**：明确引用阶段二 §5.3 覆盖率报告（如 "92%（阶段二 §5.3 总覆盖率）"）；若阶段三启动后覆盖率变化，标注"待 §5.3 更新"
6. **总览速查表**：末尾表格按模块汇总
   - 7 行（每个模块 1 行）
   - 列：模块 / public 数 / 100% 覆盖 / 备注
   - 总计行：≥ 50 public，≥ 40 100%覆盖
7. **不修改 src/**：git diff 验证 `src/` 为空

**复杂度判断依据**：模块清单已知，每个模块 API 数 ~10 个左右（除 `expr` 5 个 + `protocol` 11 个 + `ast_nodes` 23 个 + `interpreter` 13 个）。覆盖率数据从阶段二 §5.3 表直接复用。文档撰写者主要做"系统化整理"。

---

## E. 产出物 5（Category state-process）

### P3-005 · 编写状态空间 + 进程边界附录

| 项 | 内容 |
|---|---|
| **ID** | P3-005 |
| **类型** | docs（markdown） |
| **估时** | M（2-3 小时） |
| **依赖** | 无 |
| **风险** | LOW |
| **GitHub** | 模板待定 |
| **目标** | 落 `docs/audit/phase3-method-audit/05-state-and-process.md`，含状态空间 4 子节 + 进程边界 5 子节 |
| **上下文** | ADR-0001 §1 + §5 + ADR-0002 D1-confirmed + v2 审计 §3.3 D1 已定义了状态空间与 NEXT 三阶段；ADR-0001 §7 + ADR-0002 D-main + v2 审计 §4.1 P0-S1 已定义了进程边界。但这些定义分散在 3 份 ADR + 1 份审计报告里，v2 章节加载器 / 存档开发时需要"一站式"理解——本附录是新人阅读入口 |

**验收标准**（全部必须通过）：

1. **文件落盘**：`docs/audit/phase3-method-audit/05-state-and-process.md` 存在
2. **状态空间 4 子节**：
   - **1.1 GameState**：字段 / 生命周期 / v2 关注点（vars / path / next_table）
   - **1.2 NEXT 三阶段**：声明 → 竞争 → 应用（ADR-0001 §5.1-5.3）
   - **1.3 ID 命名空间 vs 变量命名空间**：ADR-0001 §1 + §11 不变量 #1
   - **1.4 修饰器块级状态**：`_deco_state` + ADR-0002 D1-confirmed + v2 审计 P1-A6 limitation
3. **进程边界 5 子节**：
   - **2.1 双向 Queue + JSON 序列化**（默认 multiprocessing.Queue + 测试 queue.Queue）
   - **2.2 GUI 子进程 spawn**（`_try_spawn_gui` + Popen + DEVNULL stderr 已知 limitation）
   - **2.3 main 不读 cmd_q**（v0 简化，ADR-0002 D-main）
   - **2.4 _drain / _close_queue 边界**（v2 审计 P1-S2 limitation）
   - **2.5 路径校验**（阶段二 P0-S1，5 项校验）
4. **每节标注 v2 改造位**：明确引用 ROADMAP §3 具体小节或 v2 审计 P1/P2
5. **不修改 src/**：git diff 验证 `src/` 为空

**复杂度判断依据**：状态空间 + 进程边界内容在 ADR + v2 审计中已有，文档撰写者主要做"汇总 + 结构化 + 标注 v2 改造位"。无新调研工作量。

---

## F. 收尾（Category wrap-up）

### P3-006 · 汇总 + 交叉校验 + open questions 文档

| 项 | 内容 |
|---|---|
| **ID** | P3-006 |
| **类型** | docs（markdown） |
| **估时** | M（1-2 小时） |
| **依赖** | P3-001 ~ P3-005 |
| **风险** | LOW |
| **GitHub** | 模板待定 |
| **目标** | 落 `docs/audit/phase3-method-audit/06-open-questions.md`，含 ≥ 3 条"待 PM/owner 拍板"的小决策 |
| **上下文** | 方法级审计期间会发现一些"v2 怎么用"的小决策（如存档 slot 命名、跨章节变量传递策略、@LLM-jud 异步模式），这些不是审计输出能定的——需要 PM/owner 拍板。本 issue 把它们汇总成 open questions 文档 |

**验收标准**（全部必须通过）：

1. **文件落盘**：`docs/audit/phase3-method-audit/06-open-questions.md` 存在
2. **Open Questions 数量**：≥ 3 条，建议 5 条（按 PDR §9 已列 OQ-1 ~ OQ-5）：
   - **OQ-1**：v2 章节加载器用相对路径还是绝对路径？
   - **OQ-2**：存档 slot 是文件名还是 UUID？
   - **OQ-3**：跨章节变量传递：保留还是重置？
   - **OQ-4**：`@LLM-jud` 异步调用阻塞还是 fire-and-forget？
   - **OQ-5**：`EventSink` Protocol 是否需扩 `close()` 方法？
3. **每条 4 项齐全**：
   - 问题（具体场景）
   - 影响（影响哪些 v2 改造）
   - 建议（推荐方案）
   - 决策者（PM / owner / 团队）
4. **交叉校验**：
   - 03-extension-points.md EP-05 ↔ 05-state-and-process.md §2.2 都提到 `_try_spawn_gui` ✓
   - 03 EP-03 ↔ 05 §2 都提到 `EventSink` Protocol ✓
   - 03 EP-06 ↔ 05 §1.4 都提到 `DecoratorEvt` call vs stop limitation ✓
   - 03 EP-01 / EP-02 ↔ 04-public-api.md 都列出 `register_function` / `register_evaluator` ✓
5. **不修改 src/**：git diff 验证 `src/` 为空

**复杂度判断依据**：Open Questions 内容在 PDR §9 已草拟，文档撰写者主要做"汇总 + 校验"。

---

## G. 验收（Category verify）

### P3-007 · 渲染验证（Mermaid 可视）+ diff 校验（src/ 不变）

| 项 | 内容 |
|---|---|
| **ID** | P3-007 |
| **类型** | verify（自动化校验） |
| **估时** | S（30 分钟） |
| **依赖** | P3-006 |
| **风险** | LOW |
| **GitHub** | 模板待定 |
| **目标** | 验证 6 个产出文件全部满足 PDR §5 验收标准——Mermaid 可渲染 + 测试覆盖度数据来源标注 + ROADMAP 引用对齐 + src/ 无 diff |
| **上下文** | 阶段一/二未做"产出物验收"环节，导致 ruff 错误未达预期目标（阶段二 §4.1 偏差）。本任务为方法级审计，需补上"自动校验"环节，避免"产出物看似完成但实际有问题" |

**验收标准**（全部必须通过）：

1. **Mermaid 渲染验证**：
   - 用 `npx -p @mermaid-js/mermaid-cli mmdc -i 01-info-flow.md -o /tmp/test.png` 等价命令（或在线预览）渲染 01-info-flow.md 和 02-module-deps.md
   - 输出 PNG 无 syntax error（仅 stderr 警告可接受）
   - 节点数符合 PDR §5.1（≤ 30 单图）
2. **测试覆盖度数据来源**：
   - grep 04-public-api.md，每个 "100%" / "89%" / "70%" 等数字必须带"（阶段二 §5.3 ...）"或类似来源标注
3. **ROADMAP 引用对齐**：
   - grep 03-extension-points.md，每个 EP 的"v2 怎么用"小节必须含 "ROADMAP §3.X" 引用
4. **src/ 无 diff**：
   - `git status` + `git diff src/` 输出为空
5. **产出文件计数**：
   - `Get-ChildItem docs/audit/phase3-method-audit/` 输出 6 个 .md 文件
6. **不修改 src/**：git diff 验证 `src/` 为空

**复杂度判断依据**：校验命令固定，30 分钟足够。若 Mermaid 渲染失败，需 issue owner 修复并重跑——不属于本 issue 范围。

---

## 附录 A：估时与依赖矩阵

| Issue | 估时 | 依赖 | 可并行 | 风险 | 类别 |
|---|---|---|---|---|---|
| P3-001 | 3-4 小时 | 无 | ✓ Window1 | LOW | info-flow |
| P3-002 | 2-3 小时 | 无 | ✓ Window1 | LOW | module-deps |
| P3-003 | 3-4 小时 | 无 | ✓ Window1 | LOW | extension-points |
| P3-004 | 3-4 小时 | 无 | ✓ Window1 | LOW | public-api |
| P3-005 | 2-3 小时 | 无 | ✓ Window1 | LOW | state-process |
| P3-006 | 1-2 小时 | P3-001~005 | ✗ Window2 | LOW | wrap-up |
| P3-007 | 30 分钟 | P3-006 | ✗ Verify | LOW | verify |
| **合计** | **16-21 小时** | — | — | — | — |

> **优化并行后**：5 个 Window1 issue 全并行，2 个 Window2 issue 串行，总耗时约 4-5 小时（5 个 Window1 中最长）+ 1-2 小时 + 30 分钟 = **5-7 小时**（按并行文档撰写者上限 5 人计算）。

---

## 附录 B：分配建议

| Issue | 推荐执行者 | 理由 |
|---|---|---|
| P3-001 信息流图 | 文档撰写者（高级） | 跨 11 文件追踪 + cross-reference 经验 |
| P3-002 模块依赖图 | 文档撰写者（中级） | 模块清单已知，工作量主要在可视化 |
| P3-003 扩展点清单 | 文档撰写者（高级） | 需 v2 改造视野 + ADR-0003/0004 深度理解 |
| P3-004 public API 清单 | 文档撰写者（中级） | 系统化整理工作 |
| P3-005 状态+进程附录 | 文档撰写者（中级） | ADR + 审计现成材料汇总 |
| P3-006 汇总+open questions | 文档撰写者（高级） | 跨 5 文件交叉校验 |
| P3-007 渲染+diff 验证 | tdd-coder（自动化校验） | 命令固定，可写脚本一次跑 |

---

## 附录 C：不做的（明确排除）

- **不修任何代码** —— 阶段三前奏是 audit/PDR，不动 src/
- **不写 v2 三大功能实现** —— PyQt6 GUI / 章节加载器 / 存档读档的代码属于阶段三后续 PDR
- **不写新 ADR** —— 方法级审计输出物是"理解当前系统"，不引入新决策
- **不跑测试 / 不动 ruff** —— 文档任务，不回归
- **不创建 fix 分支** —— 在 master 上直接落文档
- **不修 v2 P1 / P2 项** —— 见 v2 审计 §6.2 + 阶段二 §6.3 T1-T10（阶段三+ 处理）

---

*哈尼斯 · 2026-06-25 · 阶段三前奏·方法级审计 issue 列表*