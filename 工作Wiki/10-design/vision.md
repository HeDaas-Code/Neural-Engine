# 10 · 项目愿景与定位

> **TL;DR**：让中文创作者写"会动的小说"——剧本是 Markdown，剧情节点用 neon DSL 标记，运行时把 BGM/立绘/分支串起来。v0 只跑通"输入→回显"这条最小路径，剩余功能按规范排队实现。

## 项目定位

**类比三件套**：

| 引擎 | 类比 | Neural Engine 角色 |
| --- | --- | --- |
| Ink / Inkle | 同类型剧情 DSL | 参考其 DSL 思路，但用中文关键字 + neon 围栏块 |
| Ren'Py | 视觉小说引擎 | 提供运行时 + 渲染，但 v0 只做剧情脚本层 |
| Twine | 可视化分支编辑 | 未来 `editor` 上下文（v0 不实现）面向这个角色 |

**差异化**（仓库 desc + CLAUDE.md）：
- **中文原生**——关键字 / 文档 / issue / commit 全中文（变量名保留英文）
- **Markdown 内嵌**——剧本是 .md，可直接放小说网站 / Notion 阅读
- **多进程架构**——core 无 UI 依赖，未来可换 Web 端、移动端

## 范围分层（按 ADR-0001 §8 / §10）

**v0 in scope**（[ADR-0001 §8](raw-docs/ADR-0001-v0-baseline-script-spec)）：
- neon 块解析（`id:xxx` / `next:yyy` / `node xxx` / `@xxx` / `#` 注释）
- 单/多 next、NEXT 引用语义、`node in / echo / end` 执行
- 协议（3 Cmd + 6 Evt）
- `@style` 修饰器**打桩**（解析 + 广播事件，不真渲染）
- `node if` **打桩**（永远走第一分支 + log）
- 三路径 GUI（PyQt6 / CLI / pytest）

**out of scope**（v0 不做）：
- 真实多媒体播放（BGM / SE / 视频）
- 普通 Markdown 渲染
- 表达式求值
- 存档 / 读档
- 章节图 DAG 编辑器
- 行尾注释 / 块注释
- 多章节 GUI 路由处理

## v0 角色分工（来自 v0-issue-1 / v0-issue-20 / v0-issue-21）

| 角色 | 谁 | 任务 |
| --- | --- | --- |
| **项目所有者** | HeDaas-Code | 写规范、定取舍、跑端到端验收（GH #43 / #44 HITL）|
| **实现 agent** | AI agent | 按 `ready-for-agent` issue 顺序交付（GH #23 ~ #42）|
| **HITL agent** | 项目所有者 + AI 协作 | §11 不变量守护（GH #43）+ ADR-0002 完工记录（GH #44）|

## 关键里程碑

1. **M1（v0 完工 ✅）**——22/22 GH issue 全部 closed（commit `125f237`），182/182 测试通过，docs/adr/0002-v0-engine-implementation.md + docs/audit/v0-invariant-audit.md 发布。
2. **M2（v1 表达式子系统 ⏳ 部分）**——v1-issue-1 骨架已完成（commit `2a83774`，219/219 测试通过）；**v1-issue-5/6/7 真实现仍 OPEN**——executor 接入 dispatcher + chapter01.md 真求值。**关键卡点：GH #50**。详见 [[../60-v1-roadmap]]
3. **M3（编辑器）**——`src/editor/` 起新上下文，节点图可视化
4. **M4（跨平台）**——runtime 上下文拆 Web / 移动端

## 仓库状态（2026-06-15 v1 骨架 + v0 闭环）

- HEAD `50747ec docs: 新增 PRD-0002 v1 表达式子系统 + GH issue 追踪`（cursor）
- v0 部分：HEAD `c1844d9 v0 闭环状态同步`
- src/core/engine/ 7 个 .py + **新 src/core/engine/expr/ 6 个 .py**（v1-issue-1 骨架）
- chapters/chapter01.md（与 ADR §附录 A 字节级一致）
- 219 个 pytest 全过（v0 182 + v1-issue-1 骨架 37）
- 22 个 v0 GH issue CLOSED + 8 个 v1 issue OPEN
- 详见 [[../40-issues/dashboard]] + [[../60-v1-roadmap]] + `docs/adr/0002-v0-engine-implementation.md` + `docs/adr/0003-v1-expression-subsystem.md`

→ 相关：[[design-philosophy]] / [[../20-architecture/overview]] / `#43` `#44`