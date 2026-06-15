# 00 · 索引

> **TL;DR**：仓库 = ADR-0001 v0 规范 + ADR-0003 v1 表达式子系统 + 22 v0 GH issue（**全闭环**） + 8 v1 GH issue（**骨架 1/8 完成**）；本工作 Wiki 把"项目是什么 / 为什么这样设计 / 接下来做什么"压缩到 **14 个页** 里（v1 信息已合并，无独立 v1 章节）。

## 项目一句话

中文文字游戏引擎，**DSL 即规范**（ADR-0001）→ Python 多进程实现（v0）→ 表达式真求值（v1，**部分**）→ 三路径 GUI 占位（PyQt6 / CLI / pytest）。

## 仓库速览（2026-06-15 实测）

| 维度 | 现状 |
|---|---|
| Repo | [HeDaas-Code/Neural-Engine](https://github.com/HeDaas-Code/Neural-Engine) · 公开 · main 分支 |
| 作者 | HeDaas-Code |
| 当前 HEAD（main） | `0962e75 Merge pull request #45`（v0 闭环已 merge）|
| v0 闭环 HEAD | `c1844d9 feat(wiki): v0 闭环状态同步` |
| v1 骨架 HEAD（worktree）| `cf4f8a7 feat(wiki): v1 表达式子系统路线图`（feature/v1-design）|
| 代码（v0 + v1）| `src/core/engine/` 7 个 .py 主体 + **`src/core/engine/expr/` 6 个 .py 子包**（v1-issue-1 骨架）+ `src/runtime/gui/main.py` + `src/core/decorators/`（空包）|
| 文档 | ADR-0001（v0 规范）+ ADR-0002（v0 完工，✅ owner 接受 6 项）+ **ADR-0003（v1 表达式子系统，✅ 0 偏差）** + PRD-0001/0002 + CLAUDE.md + CONTEXT-MAP.md |
| 工程笔记 | 22 个 v0-issue-XX.md 在 `tmp/issues/`（Cursor 产出，本 wiki raw-docs/工程笔记/ 拷贝了）|
| Issue 队列 | GH #22~#44（22 v0，**全部 CLOSED** ✅） + #46~#54（8 v1，**全部 OPEN** ⚠️）|
| 测试 | **219/219 passed in 5.76s**（152 v0 原有 + 30 v0-issue-20 守护 + 37 v1-issue-1 骨架）|
| 实现进度 | **v0：22/22 闭环**（100%）+ **v1：1/8 骨架完成（12.5%）**——5 个真实现 OPEN（v1-issue-2/3/4 已被骨架 commit 超额实现，#5/6/7 未做）|

## 主题路径

```
10-design/         → 为什么这样设计（哲学 / 命名空间 / 强约束 / 自创名词索引 / 术语表 + 数据类型代号）
20-architecture/   → 代码怎么落地（模块布局 / AST / 状态机 / 多进程 / main.py）
30-protocol/       → 跨进程说什么（Cmd / Evt / EngineBus / 实现偏差）
40-issues/         → 下一步做什么（看板 / 依赖图，含 v0 + v1 子图）
50-fixtures/       → 怎么验（ADR 附录 A 剧本分析 / 端到端期望事件流 / v1 真分支期望）
90-meta/           → 工作 Wiki 自身（创建背景 / 文件清单 / 双向引用状态）
raw-docs/          → 仓库原文快照（ADR / CONTEXT / PRD / 工程笔记，**核对用**）
```

## 14 页速览

### 设计层（10-design）
- [[10-design/vision]] — 项目愿景与定位
- [[10-design/design-philosophy]] — 四个根原则
- [[10-design/namespace-semantics]] — **命名空间语义核心澄清**（ID vs 变量 / NEXT 元组的两槽）
- [[10-design/terminology]] — 术语表 + 数据类型代号（**含 v1 expr 子系统代号**）
- [[10-design/glossary-anchors]] — 自创名词 → raw-docs 锚点反向索引（**含 v1 族**）
- [[10-design/constraints]] — 强约束清单（7 条 + §11 不变量 10 条）

### 架构层（20-architecture）
- [[20-architecture/overview]] — 三上下文 + v0/v1 实施路径 + **expr/ 子包布局**
- [[20-architecture/ast-nodes]] — AST 节点 dataclass 设计（v0-issue-2 + **v1 If.cond 扩 kind**）
- [[20-architecture/multi-process]] — 进程拓扑 + 装配
- [[20-architecture/state-machine]] — GameState / decorator_state / NEXT / **node if 真求值（v1-issue-6 接入点）**

### 协议层（30-protocol）
- [[30-protocol/messages]] — 3 Cmd + 6 Evt schema
- [[30-protocol/bus]] — EngineBus 双向 Queue 封装
- [[30-protocol/implementation-deviations]] — **实测代码 vs spec 偏差**（v0 3 偏差 + 7 确认 + 4 GAP + **v1 0 偏差 + 1 接入卡点**）

### 任务层（40-issues）
- [[40-issues/dashboard]] — 22 v0 + 8 v1 issue 总览 + 完成度 + **v1 路线图（合并）**
- [[40-issues/dependency-graph]] — issue 依赖关系图（**v0 + v1 双子图**）

### 验证层（50-fixtures）
- [[50-fixtures/chapter01]] — ADR 附录 A 剧本分析 + 期望事件流（**v0 打桩 + v1 真分支两版本**）

### 入口
- [[README]] — 本页（vault 总入口）

### 元信息（90-meta）
- [[90-meta/wiki-meta]] — 本工作 Wiki 的创建背景 + 文件清单 + 双向引用状态
- [[90-meta/about-author]] — 作者画像推断

## 三句话讲完 v0

1. **剧本** = `.md` 文件内嵌 ` ```neon ``` ` 代码块（v0 只认这块）
2. **执行** = core 进程解析 → executor 走 NEXT 引用跳转 → 通过 EngineBus 把事件丢给 GUI
3. **唯一跑通路径** = `node in ->p_mood` → 等输入 → `node echo p_mood` → `node end`

## 一句话讲完 v1（当前状态）

> **v1-issue-1 骨架（commit `2a83774`）已完成**——`src/core/engine/expr/` 6 个 .py 子包 + 37 用例；`ExprDispatcher` 接受 `state.vars` + 三层调度（translator → simpleeval → fallback）真实现。**`executor._execute_if` 仍走 v0 打桩路径**——chapter01.md 的 `node if p_pick [...]` 永远选第一分支，**唯一卡点 = v1-issue-6**（dispatcher 接入 executor），预计 ~30 行代码 + ~50 行测试即可闭环。详见 [[40-issues/dashboard#v1-表达式子系统-prd-0002--adr-0003]]。

## 阅读路径建议

1. **新人入门**：[[10-design/vision]] → [[10-design/namespace-semantics]] → [[10-design/terminology]]
2. **v0 准备实现**（已闭环）：GH `#23` 开工前必读 [[10-design/constraints]] + [[raw-docs/ADR-0001-v0-baseline-script-spec]] 全文
3. **v1 准备实现**（当前阶段）：[[40-issues/dashboard#v1-表达式子系统-prd-0002--adr-0003]] → [[raw-docs/ADR-0003-v1-expression-subsystem]] 全文 → [[30-protocol/implementation-deviations#v1-issue-1-偏差审计-0-偏差]] → GH `#50` (v1-issue-6) 唯一卡点
4. **HITL 完工**（v0-issue-20/21 已闭环）：[[40-issues/dashboard]] + [[50-fixtures/chapter01]] + [[10-design/glossary-anchors]]