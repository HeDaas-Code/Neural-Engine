# PDR：阶段一·独立审计 + v1 偏差修复

> **项目**：Neural Engine（中文文字游戏引擎）
> **阶段**：阶段一（在 v2 P0 之前）
> **作者**：pdr-analyst
> **日期**：2026-06-24
> **状态**：待 owner 拍板
> **基线**：v0 基础版 + v1 表达式重构已完工（PR #66 已合并，211/211 tests passed）

---

## 1. 背景与动机

Neural Engine 的 v0（基础版）和 v1（表达式重构）已经按照 ADR-0001 ~ ADR-0004 实施完成并闭环：

- 19 个 v0 issue（#23-#42）全部关闭
- v1 重构 PR #66 已合并
- pytest 全绿：211/211 PASSED
- §8 MVP 表 18/18、§11 不变量 10/10 全部守护
- 2026-06-22 哈尼斯已对 v1 阶段做过一轮独立审计（`docs/audit/v1-independent-audit-hanice.md`）
- 2026-06-22 已登记 6 条 v1 偏差（`docs/adr/0004-appendix-deviations.md`）

但**哈尼斯的那次审计只覆盖 v1 阶段**，且视角混合（安全/质量/架构在同一份报告里）。Owner 拍板要求：

> 范围：v0+v1 完工代码做**新一轮独立审计** + 修 v1 偏差
> 审计视角（全要）：**代码质量/架构**、**安全/沙箱**、**可测试性/工程化**
> 产出：审计报告 Markdown + 修复 diff
> 节奏：**分阶段**，阶段一拍板后再进 v2 P0

本次 PDR 就是为这个"阶段一"做的需求规格说明。

---

## 2. 目标

**核心目标**：在 v2 P0 启动前，对 v0+v1 完工代码做一次**三视角独立审计** + 修复 4 条 v1 偏差，确保代码基线在进入 v2 之前足够健壮。

**子目标**（按优先级）：

| 优先级 | 子目标 | 度量 |
|---|---|---|
| P0 | 三个视角的独立审计完成 | 三个审计文档 + 一份合并报告（`docs/audit/v2-independent-audit-pm.md`） |
| P0 | 修 4 条 v1 偏差（D1/D2/D4/D5） | 4 个 commit/PR + 偏差附录更新 |
| P1 | 全量回归测试通过 | 211+ tests 仍 PASSED（或更多） |
| P1 | 基线指标量化 | 覆盖率报告 + ruff 扫描 + 依赖锁定 |
| P2 | 审计发现并入 ROADMAP | 新发现的 issue 进入下一轮 PDR 候选 |

---

## 3. 范围

### 3.1 包含（In Scope）

#### A. 项目基线建立

- 安装项目依赖（`pip install -e .[dev]`）
- 跑通全量测试，确认 211/211 PASSED
- `ruff` 静态扫描（如未配置先初始化）
- `pytest-cov` 覆盖率报告输出
- 锁定 `pyproject.toml` 当前实际安装的依赖版本

#### B. 三视角独立审计

对 v0+v1 完工代码做三个**独立视角**的审计，三个视角可以由同一审计人/不同审计人执行，**视角分离**是关键：

| 视角 | 关注点 | 输出 |
|---|---|---|
| **代码质量/架构** | 模块分层、循环依赖、命名空间、复杂度、ADR 一致性、可读性 | 视角 1 报告段 |
| **安全/沙箱** | simpleeval 沙箱、修饰器执行边界、跨进程序列化安全、错误信息泄露 | 视角 2 报告段 |
| **可测试性/工程化** | 测试覆盖、CI 友好性、fixture 设计、mock 难度、文档/代码同步 | 视角 3 报告段 |

三个视角完成后**合并**为一份 `docs/audit/v2-independent-audit-pm.md`，与 v1 哈尼斯审计并列。

#### C. 修复 v1 偏差（4 条）

- **D1**：`If.cond` 不加 `bool_expr` kind（用 expr + branches 数量判断）—— 决策待 owner 拍板
- **D2**：G5 修饰器结构化参数 `@style text:[rgb:red,Px:12]` 未实现 —— 需补
- **D4**：`TypeError` 捕获未收窄到 `NameNotDefined`（simpleeval API 限制）—— 需探索替代方案
- **D5**：`simpleeval` 版本未锁定（pyproject.toml 仍 `>=1.0`）—— 直接锁

### 3.2 不包含（Out of Scope）

明确**不做**的事（留给 v2 阶段）：

- ❌ PyQt6 GUI 窗口（ROADMAP §3.1）
- ❌ 章节加载器（ROADMAP §3.2）
- ❌ 存档/读档系统（ROADMAP §3.3）
- ❌ `@LLM-jud` 装饰器框架（F4 远期）
- ❌ 表达式系统增强（randint/clamp/upper 等）
- ❌ 变量持久化语义明确
- ❌ 编辑器、章节图可视化
- ❌ D3（If.cond 类型注解 union 化）和 D6（@LLM-jud）—— 远期
- ❌ 重构 v0 既有偏差（ADR-0002 §5 的 4 条已闭环）
- ❌ 推到原仓 GitHub（owner 已说明主域名 443 超时，本地 commit 即可）

---

## 4. 验收标准

### 4.1 硬性验收（必须达成）

1. **基线**：3 条命令可复现成功
   - `python3 -m pip install -e .[dev]` 成功
   - `python3 -m pytest tests/ -q` 输出 `211 passed`
   - `python3 -m pytest tests/ --cov=src --cov-report=term-missing` 生成覆盖率报告

2. **审计报告**：`docs/audit/v2-independent-audit-pm.md` 存在，包含
   - 三视角各一段独立发现
   - 每条发现含：等级（CRITICAL/HIGH/MEDIUM/LOW/INFO）、位置、证据、建议
   - 总体评级 + 与 v1 哈尼斯审计的对照
   - 新发现的待办 issue 候选列表

3. **4 条偏差修复**：
   - D5：pyproject.toml 锁定 simpleeval 到具体版本
   - D1：ast_nodes.py 显式登记 `bool_expr` kind 决策（修或显式接受）
   - D4：dispatcher.py 异常捕获按 simpleeval 1.x 实际异常类型收窄
   - D2：interpreter.py + ast_nodes.py 支持 `@style text:[a,b,c]` 解析 + executor 适配

4. **回归测试**：修复后 211+ tests 仍全绿

5. **文档同步**：
   - `docs/adr/0004-appendix-deviations.md` 标注偏差已修复
   - 必要时 `ADR-0001` §4.1、§3.2、§11 同步修订
   - `docs/ROADMAP.md` §2.1 偏差表状态更新

### 4.2 软性验收（建议达成）

- ruff 扫描 0 error
- 测试覆盖率 ≥ 当前基线（建议 ≥ 85%，待基线确认）
- 审计报告被 owner 签字接受
- 新发现的高优先级 issue 进入 v2 路线图

---

## 5. 边界

### 5.1 文件边界

| 允许改 | 不允许改 |
|---|---|
| `src/core/engine/**/*.py` | `chapters/chapter01.md`（v0 fixture） |
| `tests/**/*.py` | `docs/adr/0001-v0-baseline-script-spec.md`（v0 真理之源） |
| `pyproject.toml` / `requirements*.txt` | `chapters/chapter01_v1.md`（v1 fixture，v0 兼容验证） |
| `docs/adr/0004-appendix-deviations.md` | `README.md` 总状态表（除非验收确实完成） |
| `docs/ROADMAP.md` §2.1 偏差表 | 既有 v0 偏差（ADR-0002 §5） |
| `docs/audit/v2-independent-audit-pm.md`（新增） | owner 私有的 GitHub 仓库 |

### 5.2 行为边界

- 保持 v0 端到端路径可跑（`tests/integration/test_echo_path.py`）
- 保持 v1 端到端路径可跑（`tests/integration/test_v1_e2e.py`）
- 保持双箭头容忍（← / <- 和 → / ->）
- 保持双命名空间分离（id 命名空间 vs 变量命名空间）
- 保持 simpleeval 白名单（`BUILTIN_FUNCS`）不增不减
- 保持 core 上下文无 UI 依赖（不 import PyQt6）

### 5.3 时间边界

| 项 | 预算 |
|---|---|
| 阶段一总周期 | 5-7 个工作日（取决于并行度） |
| 基线建立 | 0.5 天 |
| 三视角审计 | 2-3 天（可并行） |
| 偏差修复 | 2-3 天（与审计并行或串行） |
| 合并 + 文档同步 | 0.5 天 |

---

## 6. 关键决策

### 决策 1：审计与修复并行而非串行

**理由**：审计是"读"代码，修复是"写"代码，二者作用面**不重叠**（审计产出文档，修复产出 diff）。强行串行会拉长周期。

**约束**：
- 审计输出基于**当前代码**（含 v1 完工态），与 4 条偏差共存
- 修复 D5/D1/D4 时（仅触及 pyproject.toml / ast_nodes.py / dispatcher.py），审计**已结束**的视角不应再改这些文件
- 修复 D2 时（触及 interpreter.py + executor.py）需要重跑审计视角 1 的相关发现是否仍成立

### 决策 2：D1 的两种处理路径

D1 偏差的本质是"用 `("expr", ...)` + branches 数量判断"代替 `("bool_expr", ...)` 第三种 kind。

**路径 A（推荐）**：接受偏差但**显式登记**到 ADR-0004 §1.2 D1 行，将"branches 数量判断"补一句规范说明（"二元 if 通过 branches 长度为 2 判定"），并在 executor 加 `assert len(branches) == 2` 做 defense-in-depth。

**路径 B**：实现 `bool_expr` kind（增加 type union 复杂度，但更显式）。

**拍板项**：等 owner 在阶段一拍板时选定。PDR 默认按**路径 A** 实施（D1 复杂度估为 S，仅文档 + 注释 + 断言）。

### 决策 3：D2 修饰器结构化参数的范围

G5 完整语法是 `@style text:[rgb:red,Px:12],bgm:start:1.mp3`。完整实现涉及：
- 解析器：参数值支持 `[item1,item2,...]` 列表 + 嵌套
- AST：`DecoratorCall.args` 扩展为 `tuple[str | list, ...]`
- Executor：列表参数展开为多个事件/合并处理
- GUI：不真渲染（v0 风格广播即可）
- 测试：3-5 个新单测 + fixture 扩展

**最小可行（MVP）实现**：仅支持 `@style key:[a,b,c]` 形式（顶层参数值为列表），不嵌套。理由：v0/v1 阶段 GUI 仍不真渲染修饰器，结构化参数只影响协议层，没必要做复杂嵌套。

### 决策 4：审计文档格式

与 v1 哈尼斯审计（`v1-independent-audit-hanice.md`）保持风格一致：
- 执行摘要表
- 分章节（安全/质量/架构）
- 每条发现含等级 + 位置 + 证据 + 修复建议
- 复杂度热点（如有）
- 总体评价

但**视角分离**是本次新增要求——三段独立，每段都给出可独立阅读的发现。

### 决策 5：覆盖率基线

`pytest-cov` 当前可能未运行。阶段一首次输出覆盖率基线，**不设硬性目标**，仅记录 + 供 v2 阶段参考。如发现某核心模块（如 `executor.py`）覆盖率 < 80%，应作为审计发现。

---

## 7. 风险

| # | 风险 | 等级 | 缓解措施 |
|---|---|---|---|
| R-1 | 审计周期过长（>3 天），与修复并行期重叠导致审计需要返工 | MEDIUM | 决策 1 约束：审计与修复在文件级别不重叠；D2 修复后只重审相关小节 |
| R-2 | D2 G5 改动量大，引入新偏差 | MEDIUM | MVP 实现 + 严格按 ADR 走，偏差直接登记 |
| R-3 | D4 收窄异常捕获时，发现 simpleeval 1.x 实际无细分异常类型可收 | MEDIUM | 走 fallback 路径 + 在 commit message 显式登记尝试过程 |
| R-4 | 覆盖率基线低于预期，引发"先补测试" vs "先修偏差"优先级争议 | LOW | 决策 5：仅记录不设硬性目标；覆盖率补测归入 v2 候选 |
| R-5 | 审计发现 vs 哈尼斯 v1 审计结论不一致 | LOW | 明确本次审计"视角分离"是新要求，不与 v1 审计做硬对照；以本文档为本次基线 |
| R-6 | 简单评估未识别所有偏差（如 D3/D6 也需修） | LOW | 决策 3/2 已显式处理 D1/D2；D3/D6 明确不做，登记到 ROADMAP §2.2 远期 |
| R-7 | owner 拍板延迟，阶段一卡住 | LOW | 决策 2 默认路径 A，可独立推进 |
| R-8 | simpleeval 版本锁定后未来 v2 表达式系统增强（randint 等）需要升级版本 | LOW | 决策 5：锁到当前已验证可用的 minor 版本；升级走正常 PR 流程 |

---

## 8. 依赖关系

### 8.1 Issue 间依赖图

```
P1-001（基线建立，L）
    │
    ├──→ P1-002（架构审计，M） ─┐
    ├──→ P1-003（安全审计，M） ─┼─→ P1-005（合并审计报告，S）
    └──→ P1-004（工程化审计，M）┘
    
    ├──→ P1-006（修 D5，S） ──────┐
    ├──→ P1-007（修 D1，S） ──────┤
    ├──→ P1-008（修 D4，S-M）─────┼─→ P1-010（回归 + 文档同步，S）
    └──→ P1-009（修 D2，L） ──────┘
```

### 8.2 可并行 issue

**三审计互相并行**：P1-002 / P1-003 / P1-004 可由三人同时进行（同一审计人也行，但**视角不混**）。

**修复互相并行**：P1-006 / P1-007 / P1-008 涉及不同文件（pyproject.toml / ast_nodes.py / dispatcher.py），可并行；P1-009（D2）独立但文件大，建议独立窗口。

**审计与修复并行**：P1-006/007/008 修复期间审计已进行中的视角不应再访问这些文件；D2 修复完成后应回检 P1-002 视角 1 的相关小节。

### 8.3 关键里程碑

| 里程碑 | 完成条件 | 估时 |
|---|---|---|
| **M1**：基线 ready | P1-001 完成 | 0.5 天 |
| **M2**：三视角审计 raw 报告 ready | P1-002/003/004 完成 | 2-3 天 |
| **M3**：审计合并完成 | P1-005 完成 | 0.5 天 |
| **M4**：4 条偏差修复完成 | P1-006/007/008/009 完成 | 2-3 天 |
| **M5**：阶段一验收通过 | P1-010 完成（211+ tests + ruff 0 error + 文档同步） | 0.5 天 |

**M1 → M5 串行**，M2 与 M4 内部**并行**。

---

## 9. Open Questions（需 PM/owner 拍板）

> 这些问题在阶段一拍板时**必须**有结论，否则相关 issue 阻塞。

- **OQ-1**：D1 处理路径选 A（接受 + 显式登记）还是 B（实现 bool_expr kind）？—— 默认 A
- **OQ-2**：D2 范围是 MVP（仅顶层列表）还是完整（嵌套）？—— 默认 MVP
- **OQ-3**：D4 收窄异常时如发现 simpleeval 1.x 无细分类型，是否接受保持现状 + 显式登记"simpleeval API 限制"？—— 默认是
- **OQ-4**：审计是否覆盖测试代码？还是只覆盖生产代码？—— 默认只覆盖生产代码 + 关键测试 fixture
- **OQ-5**：基线是否要求 `mypy` / `pyright` 静态类型检查？项目目前无 mypy 配置—— 默认不要求
- **OQ-6**：阶段一拍板后是否需要 owner 对合并审计报告签字？—— 默认需要
- **OQ-7**：阶段一拍板后，PM 是否需要更新 ROADMAP.md 把"v2 P0"改为"v2 P1"（或保持原样）？—— 默认保持原样，等阶段一验收后再调
- **OQ-8**：审计发现的新 issue 是本阶段一处理，还是进入 v2 P0 候选？—— 默认后者

---

## 10. 引用

- **ADR-0001**：`docs/adr/0001-v0-baseline-script-spec.md`（v0 规范基线）
- **ADR-0002**：`docs/adr/0002-v0-engine-implementation.md`（v0 完工 + 4 条偏差）
- **ADR-0003**：`docs/adr/0003-v1-expression-subsystem.md`（v1 表达式设计）
- **ADR-0004**：`docs/adr/0004-v1-refactor-design.md`（v1 重构设计）
- **ADR-0004 附录**：`docs/adr/0004-appendix-deviations.md`（v1 偏差 6 条登记）
- **v1 独立审计**：`docs/audit/v1-independent-audit-hanice.md`（哈尼斯 2026-06-22）
- **ROADMAP**：`docs/ROADMAP.md`（v2 路线图 + 偏差表）
- **CLAUDE.md / CONTEXT-MAP.md**：项目协作约定

---

## 11. 变更记录

| 日期 | 作者 | 变更 |
|---|---|---|
| 2026-06-24 | pdr-analyst | 初稿 |

---

*阶段一拍板前请确认 §9 全部 Open Questions。拍板后此 PDR 与 `docs/issues/phase1-audit-and-fixes.md` 一并作为实施依据。*
