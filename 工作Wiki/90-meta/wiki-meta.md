# 90 · 工作 Wiki 元信息

> **TL;DR**：本工作 Wiki 自身的来龙去脉——什么时候建的、追踪到哪一步、下一步更新什么。

## 创建背景（2026-06-15 仓库还原后）

- **触发事件**：用户还原代码库，导致之前的 `Neural Engine-vault/` 被覆盖
- **用户指令**："重新按照工作流生成一下，这此 vault 命名为工作 Wiki，并提交 github，同时作为项目 Wiki 而存在"
- **策略调整**：
  1. 名称：`Neural Engine-vault/` → **`工作Wiki/`**（中文名）
  2. 位置：项目根下 `工作Wiki/`（之前在仓库外）
  3. 提交：**GitHub main 分支** + **GitHub Wiki 引擎**双推送
  4. 角色：本地分析载体 **+** 项目 Wiki 双重身份

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

## 与上一轮的区别

| 维度 | 上一轮（Neural Engine-vault/）| 本轮（工作Wiki/）|
| --- | --- | --- |
| 命名 | Neural Engine-vault | **工作Wiki**（中文）|
| 位置 | 仓库内但 .gitignore | **仓库内但会被 commit**（作为项目 Wiki）|
| 提交 GitHub | 否 | **是**（main + wiki 分支双推）|
| Issue 体系 | 18 个 GH #2~#21 + v0-issue-N | **22 个 GH #22~#44** + v0-issue-1~21 |
| HITL 数量 | 1（#15）| **2**（#43 / #44）|
| 还原前实现 | 53 测试通过 | **0**（仓库被还原）|
| GUI 路径 | 单路径（PyQt6 占位）| **三路径**（PyQt6 / CLI / pytest）|
| 包结构 | `src.core.engine` | **`core.engine`**（不带 `src.` 前缀）|

## 待办（wiki 视角）

| 任务 | 触发 | 动作 |
| --- | --- | --- |
| 跟踪 issue 实现 | 用户开始做 `#23` | 在 wiki 加 `40-issues/in-progress.md` 记当前进度 |
| 跟踪 ADR-0002 | `#44` 发布 | 加 `10-design/v1-changelog.md` 记实现偏差 |
| 跟踪 runtime | core 完工时 | 读 [[raw-docs/CONTEXT-runtime.md]] |
| 跟踪 editor | v2+ 启动时 | 读 [[raw-docs/CONTEXT-editor.md]] |

## 双向引用状态

- 17 个 wiki 页 + 32 个 raw-docs = **49 个 .md 文件**
- 0 个孤岛（目标）
- 100+ raw-docs 锚点引用（目标）

## 引用源

- 工作流 —— [[~/.hermes/vault/工作流程 - Cursor Hermes 协作.md]]
- 上一轮 vault（已删除）—— `~/桌面/Neural Engine/Neural Engine-vault/`（覆盖前）