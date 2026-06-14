# 作者侧写

> **TL;DR**：项目所有者 HeDaas-Code，独立开发者，2026-06-13 启动 v0 规范，2026-06-15 仓库被还原。

## 推断画像（基于仓库信号）

- **GitHub 账号**：HeDaas-Code（gh CLI 已 auth）
- **创建日期**：2026-06-13 当天一次性把 ADR-0001 + PRD-0001 + 22 个实现 issue 全发出来——典型的"先把规范钉死，再让 agent 干活"工作流
- **协作偏好**：用 `ready-for-agent` / `ready-for-human` 双标签拆分——v0 想让 AI agent 主驾，自己只参与必要的 HITL 环节（GH #43 / #44）
- **沟通风格**：issue body 用中文 + 英文术语混排；规范文档全中文；commit message 规定中文（CLAUDE.md）
- **设计品味**：
  - 命名空间严格分离（ID vs 变量）——非平凡的语法设计
  - NEXT 用"引用"而非字符串——避免跳转逻辑爆炸
  - CSS 化的修饰器——横切关注点的优雅方案
  - DSL 即规范——未识别语句直接报错
- **质量门**：`§11 关键不变量` 全部有守护测试（v0-issue-20）+ 完工记录（v0-issue-21 ADR-0002）
- **架构洁癖**：core 与 runtime 完全分离 + 协议 dataclass 共享——可扩展 Web/移动端的伏笔
- **工程实践**：
  - v0-issue-18 三路径 GUI 决策（不强装 PyQt6）——务实
  - v0-issue-15 改 decorator_state 在 node start 清空（不是 ADR §4.1 写的 node end）——owner 有自己的实现决策权
  - v0-issue-20 HITL grep 守护（"NEXT" / pickle / TODO 三条）——自动化不变量
- **2026-06-15 行为**：还原代码库 → 重启 v0 实施；明确说"重新按照工作流生成"——**接受失败并重来的工程文化**

## 推断的开发环境（来自本机痕迹）

- 本机有 `gh` 已 login（HeDaas-Code）→ GitHub 协作流程顺
- 工程工具齐全（codegraph / hermes / claude / mmx）—— agent-first 工作流
- Zorin OS / Ubuntu 24.04 + Zorin GDM

## 协作建议（与作者/agent 工作流）

1. **永远不绕过 owner**——`ready-for-human` issue 必须 owner 亲自做（GH #43 / #44）
2. **代码改动前先查 ADR**——`docs/agents/domain.md` 明文要求
3. **§11 不变量是硬约束**——任何 issue 实现都要回头验证
4. **HITL 段不替 owner 决定**——#43 / #44 涉及 grep 守护验收 + ADR-0002 偏差 review，agent 不擅自发布
5. **新术语先入 `CONTEXT.md`**——避免 wiki 漂移
6. **接受失败并重来**——仓库还原后立即重新启动，不要停在"之前做好了"的情绪里

→ 相关：[[wiki-meta]] / [[../10-design/design-philosophy]]