# 00 · 索引

> **TL;DR**：仓库 = ADR-0001 规范 + 22 个 GH issue 排队（GH #22~#44，v0-issue-1~21）；本工作 Wiki 把"项目是什么 / 为什么这样设计 / 接下来做什么"压缩到 14 个页里。

## 项目一句话

中文文字游戏引擎，**DSL 即规范**（ADR-0001）→ Python 多进程实现（v0）→ 三路径 GUI 占位（PyQt6 / CLI / pytest）。

## 仓库速览（2026-06-15 实测：cursor 已完成 v0 实施）

| 维度 | 现状 |
|---|---|
| Repo | [HeDaas-Code/Neural-Engine](https://github.com/HeDaas-Code/Neural-Engine) · 公开 · main 分支 |
| 作者 | HeDaas-Code |
| 当前 HEAD | `1a76382 feat: 落地 v0-issue-19 chapter01 fixture + 端到端集成测试` |
| 仓库初始化 commit | `499fcf1 chore: 初始化仓库 + ADR-0001 规范 + PRD-0001` |
| 临时分支 | `cursor/setup-issues-v0-vertical-slices`（HEAD `1a76382`，已 push）|
| 代码 | **`src/core/engine/` 7 个 .py + `src/runtime/gui/main.py` + `src/core/decorators/`（空包）**——v0-issue-1 ~ 19 全部落地 |
| 文档 | ADR-0001（19 KB）+ PRD-0001（已转 issue #22）+ CLAUDE.md + CONTEXT-MAP.md |
| 工程笔记 | 22 个 v0-issue-XX.md 在 `tmp/issues/`（Cursor 产出，本 wiki raw-docs/工程笔记/ 拷贝了）|
| Issue 队列 | GH #22~#44（22 个，**全部 CLOSED** ✅）|
| 测试 | **182/182 passed in 8.04s**（152 原有 + 30 新增 v0-issue-20 守护）|
| 实现进度 | **22/22**（v0 全部闭环）|

## 主题路径

```
10-design/         → 为什么这样设计（哲学 / 命名空间 / 强约束 / 自创名词索引）
20-architecture/   → 代码怎么落地（模块布局 / AST / 状态机 / 多进程 / main.py）
30-protocol/       → 跨进程说什么（Cmd / Evt / EngineBus）
40-issues/         → 下一步做什么（看板 / 依赖图 / 验收标准）
50-fixtures/       → 怎么验（ADR 附录 A 剧本分析 / 端到端期望事件流）
90-meta/           → 工作 Wiki 自身（创建背景 / 文件清单 / 双向引用状态）
raw-docs/          → 仓库原文快照（ADR / CONTEXT / PRD / 工程笔记，**核对用**）
```

## 14 页速览

### 设计层（10-design）
- [[10-design/vision]] — 项目愿景与定位
- [[10-design/design-philosophy]] — 四个根原则
- [[10-design/namespace-semantics]] — **命名空间语义核心澄清**（ID vs 变量 / NEXT 元组的两槽）
- [[10-design/terminology]] — 术语表 + "不要用"清单
- [[10-design/glossary-anchors]] — 自创名词 → raw-docs 锚点反向索引
- [[10-design/constraints]] — 强约束清单（7 条 + §11 不变量 10 条）

### 架构层（20-architecture）
- [[20-architecture/overview]] — 三上下文 + v0 实施路径
- [[20-architecture/ast-nodes]] — AST 节点 dataclass 设计（v0-issue-2）
- [[20-architecture/multi-process]] — 进程拓扑 + 装配
- [[20-architecture/state-machine]] — GameState / decorator_state / NEXT

### 协议层（30-protocol）
- [[30-protocol/messages]] — 3 Cmd + 6 Evt schema
- [[30-protocol/bus]] — EngineBus 双向 Queue 封装
- [[30-protocol/implementation-deviations]] — **实测代码 vs spec 偏差**（3 偏差 + 7 确认）

### 任务层（40-issues）
- [[40-issues/dashboard]] — 22 个 issue 总览 + 完成度
- [[40-issues/dependency-graph]] — issue 依赖图 + 可并行批次

### 验证层（50-fixtures）
- [[50-fixtures/chapter01]] — ADR 附录 A 剧本分析 + 期望事件流

### 入口
- [[README]] — 本页（vault 总入口）

### 元信息（90-meta）
- [[90-meta/wiki-meta]] — 本工作 Wiki 的创建背景 + 文件清单 + 双向引用状态
- [[90-meta/about-author]] — 作者画像推断

## 三句话讲完 v0

1. **剧本** = `.md` 文件内嵌 ` ```neon ``` ` 代码块（v0 只认这块）
2. **执行** = core 进程解析 → executor 走 NEXT 引用跳转 → 通过 EngineBus 把事件丢给 GUI
3. **唯一跑通路径** = `node in ->p_mood` → 等输入 → `node echo p_mood` → `node end`

→ 展开看 [[../10-design/vision]]、[[../20-architecture/overview]]、[[../10-design/namespace-semantics]]（命名空间核心）、`#43` `#44`（HITL 完工关卡）

## 阅读路径建议

1. **新人入门**：[[10-design/vision]] → [[10-design/namespace-semantics]] → [[10-design/terminology]]
2. **准备实现**（v0-issue-1 开工前）：[[10-design/constraints]] + [[raw-docs/ADR-0001-v0-baseline-script-spec]] 全文
3. **HITL 完工**（v0-issue-20/21 前）：[[40-issues/dashboard]] + [[50-fixtures/chapter01]]