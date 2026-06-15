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

1. **M1（v0 代码完成 ✅）**——v0-issue-1 ~ v0-issue-19 全部代码已落地（commit `1a76382`），152/152 测试通过。**剩 HITL**：owner 跑 GH #43（不变量守护 3 条 grep + 写 `docs/audit/v0-invariant-audit.md`）+ GH #44（写 `docs/adr/0002-v0-engine-implementation.md` 登记 4 条偏差 + `gh issue close 22..44`）
2. **M2（真实运行时）**——`@style` 真接音视频、`node if` 真做条件、章节路由真加载下一章
3. **M3（编辑器）**——`src/editor/` 起新上下文，节点图可视化
4. **M4（跨平台）**——runtime 上下文拆 Web / 移动端

## 仓库状态（2026-06-15 实测：v0 已落地）

- HEAD `1a76382 feat: 落地 v0-issue-19 chapter01 fixture + 端到端集成测试`
- src/core/engine/ 7 个 .py + chapters/chapter01.md（与 ADR §附录 A 字节级一致）
- 152 个 pytest 全过（v0-issue-1 ~ v0-issue-19 全部 done）
- 22 个 GH issue 全 OPEN 但 cursor 都发了完成评论
- 详见 [[../40-issues/dashboard]] + [[../30-protocol/implementation-deviations]]

→ 相关：[[design-philosophy]] / [[../20-architecture/overview]] / `#43` `#44`