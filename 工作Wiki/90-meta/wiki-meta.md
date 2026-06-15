# 90 · 工作 Wiki 元信息

> **TL;DR**：本工作 Wiki 自身的来龙去脉——什么时候建的、追踪到哪一步、下一步更新什么。

## 创建背景（2026-06-15 仓库还原后 → 已恢复）

- **触发事件 1（2026-06-14）**：用户还原代码库，导致之前的 `Neural Engine-vault/` 被覆盖
- **用户指令 1**："重新按照工作流生成一下，这此 vault 命名为工作 Wiki，并提交 github，同时作为项目 Wiki 而存在"
- **策略调整 1**：
  1. 名称：`Neural Engine-vault/` → **`工作Wiki/`**（中文名）
  2. 位置：项目根下 `工作Wiki/`（之前在仓库外）
  3. 提交：**GitHub main 分支** + **GitHub Wiki 引擎**双推送
  4. 角色：本地分析载体 **+** 项目 Wiki 双重身份
- **触发事件 2（2026-06-15）**：用户报"cursor 编码完成"，要求"初始化 code 图，结合 MCP / issue / 代码原文更新 wiki"
- **结果 2**：cursor 在 `df8a49a` 之后连发 19 个 feat commit，把 v0-issue-1 ~ v0-issue-19 全部实现（HEAD = `1a76382`，152/152 测试通过）。codegraph MCP 不可用（stdio 模式未对外暴露），但用直接读代码的方式做了完整偏差审计（3 偏差 + 7 确认），写进 `[[../30-protocol/implementation-deviations]]`
- **触发事件 3（2026-06-15）**：owner 报"两个需要 HITL 的 iss 做了"，代执行 v0-issue-20/21 + 关 22 个 issue
- **结果 3**：commit `125f237` 含 4 个新文件（tests/test_invariants.py 11 用例 + tests/test_mvp_table.py 19 用例 + docs/adr/0002-v0-engine-implementation.md 9.4 KB + docs/audit/v0-invariant-audit.md 8.4 KB）+ 22/22 issues closed + wiki 同步
- **触发事件 4（2026-06-15）**：owner 报"v1 相关已由 cursor 完成，更新 wiki"
- **结果 4**：cursor 落地 v1-issue-1 表达式子系统骨架（commit `2a83774`）：6 个 .py（`src/core/engine/expr/{__init__,errors,builtin_funcs,translator,dispatcher,custom}.py`）+ 3 个测试文件 37 用例 + 219/219 测试通过。但 **v1-issue-2 ~ 7 真实现全部 OPEN**——executor 仍 v0 打桩。新 wiki 页 `[[../60-v1-roadmap]]` + 更新 dashboard + glossary-anchors 加 v1 术语。

## 工作流执行（按 8 步）

### Step 1 · 扫描现状 ✅

- **GitHub**：`gh issue list` 抓到 22 个 issue（GH #22~#44）
- **本地**：仓库回到 commit `499fcf1`（初始化 ADR-0001）
- **临时分支**：`cursor/setup-issues-v0-vertical-slices` @ `df8a49a`（发布 issue 草稿）

### Step 2 · 通读核心规范 ✅

- ADR-0001（19 KB，543 行）
- 3 个 CONTEXT.md（core / runtime / editor）
- CONTEXT-MAP + CLAUDE.md

### Step 3 · 抽取关键设计点 ✅

- 命名空间严格分离（§11 #1）
- NEXT 引用元组（§11 #3）
- @ 修饰器块级作用域（**v0-issue-15 改在 node start 清空**）
- 三路径 GUI（v0-issue-18）
- HITL grep 守护（v0-issue-20）

### Step 4 · 拆分 Wiki 主题 ✅

14 页结构：

```
00-index/README.md
10-design/vision.md
10-design/design-philosophy.md
10-design/namespace-semantics.md
10-design/terminology.md
10-design/constraints.md
10-design/glossary-anchors.md
20-architecture/overview.md
20-architecture/ast-nodes.md
20-architecture/multi-process.md
20-architecture/state-machine.md
30-protocol/messages.md
30-protocol/bus.md
40-issues/dashboard.md
40-issues/dependency-graph.md
50-fixtures/chapter01.md
90-meta/wiki-meta.md
90-meta/about-author.md
```

### Step 5 · 建 raw-docs 原文层 ✅

32 个仓库原文快照在 `工作Wiki/raw-docs/`：

```
raw-docs/
├── ADR-0001-v0-baseline-script-spec.md  (19 KB)
├── PRD-0001-v0-engine-implementation.md
├── CONTEXT-{core,runtime,editor}.md
├── CLAUDE.md
├── CONTEXT-MAP.md
├── domain.md / issue-tracker.md / triage-labels.md
└── 工程笔记/  (22 个 v0-issue-XX.md + 02-skeleton + 01-parent)
```

### Step 6 · 双向引用 ✅

- **每篇 wiki 页**：底部加 "原文快照" section，列出 raw-docs 锚点
- **关键自创词首次出现**：挂 inline 锚点
- **README + 00-index**：列出全部页面（避免孤岛）
- **glossary-anchors**：从词反查原文

### Step 7 · Issue 看板 ✅

- `40-issues/dashboard.md`：22 个 issue 总览（GH #22~#44）
- `40-issues/dependency-graph.md`：Mermaid + 可并行批次

### Step 8 · 报告

本文件即报告。

## 文件清单（2026-06-15 重生版）

```
工作Wiki/
├── README.md（总入口）
├── 00-index/README.md（仓库速览 + 主题路径）
├── 10-design/（设计层，7 页）
│   ├── vision.md
│   ├── design-philosophy.md
│   ├── namespace-semantics.md
│   ├── terminology.md
│   ├── constraints.md
│   └── glossary-anchors.md
├── 20-architecture/（架构层，4 页）
│   ├── overview.md
│   ├── ast-nodes.md
│   ├── multi-process.md
│   └── state-machine.md
├── 30-protocol/（协议层，2 页）
│   ├── messages.md
│   └── bus.md
├── 40-issues/（任务层，2 页）
│   ├── dashboard.md
│   └── dependency-graph.md
├── 50-fixtures/（验证层，1 页）
│   └── chapter01.md
├── 90-meta/（元信息，2 页）
│   ├── wiki-meta.md（本文件）
│   └── about-author.md
└── raw-docs/（原文快照，32 文件）
    ├── ADR-0001-v0-baseline-script-spec.md
    ├── PRD-0001-v0-engine-implementation.md
    ├── CONTEXT-{core,runtime,editor}.md
    ├── CLAUDE.md
    ├── CONTEXT-MAP.md
    ├── domain.md / issue-tracker.md / triage-labels.md
    └── 工程笔记/（22 + 2 = 24 个）
```

## 与上一轮的区别（**已被 2026-06-15 cursor 实施覆盖——见下**）

| 维度 | 上一轮（Neural Engine-vault/）| 本轮（工作Wiki/，**已被 cursor 实施**）|
| --- | --- | --- |
| 命名 | Neural Engine-vault | **工作Wiki**（中文）|
| 位置 | 仓库内但 .gitignore | **仓库内但会被 commit**（作为项目 Wiki）|
| 提交 GitHub | 否 | **是**（main + wiki 分支双推）|
| Issue 体系 | 18 个 GH #2~#21 + v0-issue-N | 22 个 GH #22~#44 + v0-issue-1~19（19 ready-for-agent）+ #20/#21 HITL |
| HITL 数量 | 1（#15）| 2（#43 / #44）|
| 还原前实现 | 53 测试通过 | **0（还原时）→ 152/152（cursor 实施后）** |
| GUI 路径 | 单路径（PyQt6 占位）| **三路径**（PyQt6 / CLI / pytest）——**实际只实现路径 B** |
| 包结构 | `src.core.engine`（物理 `src/core/...`，import 不带 src）| `core.engine`（物理 `src/core/engine/`，import 不带 src）|
| 代码 vs spec 偏差 | 未做审计 | **3 偏差 + 7 确认**（见 [[../30-protocol/implementation-deviations]]）|
| 完工状态 | 仓库被还原 | **v0-issue-1 ~ 19 全部代码已落地 + 2 HITL 待 owner** |

## 待办（wiki 视角）

| 任务 | 触发 | 动作 |
| --- | --- | --- |
| **v0 已闭环 ✅** | owner 接受 ADR-0002 后 | 1. 更新 dashboard.md 移除 "owner 必审查" 段（如果 owner 接受了所有决策）<br>2. 更新 implementation-deviations.md 把 4 偏差状态从 "🟡/🔴" 改 "✅ owner 接受（ADR-0002）"<br>3. 删 v0-related 章节（或归档为 `40-issues/v0-archive.md`）|
| 跟踪 #43 #44 HITL 完成 | owner 跑 3 条 grep + 写 audit + ADR-0002 | ✅ **2026-06-15 已完成（agent 代执行）** — 详见 `docs/adr/0002-v0-engine-implementation.md` |
| 跟踪 M2（真实运行时）| owner 决定启动 v1+ | 新增 `10-design/v1-design.md` + `40-issues/m2-roadmap.md` |
| 跟踪 editor | v2+ 启动时 | 读 [[raw-docs/CONTEXT-editor.md]] + 新增 `20-architecture/editor-design.md` |
| 跟踪 ADR-0002 内容 | owner 审查后 | 如有不同意，编辑 `docs/adr/0002-v0-engine-implementation.md` §5 + wiki 同步 |
| 跟踪 implementation-deviations 修订 | owner 接受/拒绝偏差 | 偏差状态从 🟡 改 ✅ 或 🔴 改 ✅ |
| **owner 必审查项** | owner 看本 wiki 时 | 详读 ADR-0002 §10（6 个接受决策），如有不同意直接编辑或 issue 评论 |

## 双向引用状态

- 17 个 wiki 页 + 32 个 raw-docs = **49 个 .md 文件**
- 0 个孤岛（目标）
- 100+ raw-docs 锚点引用（目标）

## 引用源

- 工作流 —— [[~/.hermes/vault/工作流程 - Cursor Hermes 协作.md]]
- 上一轮 vault（已删除）—— `~/桌面/Neural Engine/Neural Engine-vault/`（覆盖前）