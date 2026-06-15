# 作者侧写

> **TL;DR**：项目所有者 HeDaas-Code，独立开发者。2026-06-14 发布 ADR-0001 + 22 个 v0-issue 草稿，**2026-06-15 cursor 一口气落地 19 个 feat commit**——v0 代码 100% 完成（152/152 测试通过），剩 2 HITL（#43 不变量守护 + #44 ADR-0002 完工）等 owner 手工关。

## 推断画像（基于仓库信号）

- **GitHub 账号**：HeDaas-Code（gh CLI 已 auth）
- **创建日期**：2026-06-14 当天一次性把 ADR-0001 + PRD-0001 + 22 个实现 issue 全发出来——典型的"先把规范钉死，再让 agent 干活"工作流
- **协作偏好**：用 `ready-for-agent` / `ready-for-human` 双标签拆分——v0 让 AI agent 主驾，自己只参与必要的 HITL 环节（GH #43 / #44）
- **沟通风格**：issue body 用中文 + 英文术语混排；规范文档全中文；commit message 规定中文（CLAUDE.md）
- **设计品味**：
  - 命名空间严格分离（ID vs 变量）——非平凡的语法设计
  - NEXT 用"引用"而非字符串——避免跳转逻辑爆炸
  - CSS 化的修饰器——横切关注点的优雅方案
  - DSL 即规范——未识别语句直接报错
- **质量门**：`§11 关键不变量` 全部有守护测试（v0-issue-20）+ 完工记录（v0-issue-21 ADR-0002）
- **架构洁癖**：core 与 runtime 完全分离 + 协议 dataclass 共享——可扩展 Web/移动端的伏笔
- **工程实践**：
  - v0-issue-18 三路径 GUI 决策（不强装 PyQt6）——务实（**实际只实现路径 B**，A 推到 v1）
  - v0-issue-15 改 decorator_state 在 `run_block` 开头清（v0-issue-15 决策，**与 ADR §4.1 不一致**）——这是 v0-issue-21 HITL 必须解决的 ADR 偏差
  - v0-issue-20 HITL grep 守护（`"NEXT"` / `pickle` / `TODO` 三条）——自动化不变量
  - **新发现**：v0-issue-2 实施时把 spec 的 `Branch.target: NextDecl | Echo | In` 改成了 `NextDecl | CallExpression(kind, var)` —— 这是 v0 阶段合理简化，owner 需在 ADR-0002 接受
- **2026-06-15 行为**：还原代码库 → 触发工作 Wiki 重建 → cursor 实施完成 → 现在要求更新 wiki 对齐实测 —— **接受失败并重来 + 验证一致性的工程文化**

## 推断的开发环境（来自本机痕迹）

- 本机有 `gh` 已 login（HeDaas-Code）→ GitHub 协作流程顺
- 工程工具齐全（codegraph / hermes / claude / mmx）—— agent-first 工作流
- Zorin OS / Ubuntu 24.04 + Zorin GDM
- 工具链 PATH：`/home/hedaas/.nvm/versions/node/v24.15.0/bin/codegraph`（npm 全局），systemd unit 走 user 级

## 协作建议（与作者/agent 工作流）

1. **永远不绕过 owner**——`ready-for-human` issue 必须 owner 亲自做（GH #43 / #44）
2. **代码改动前先查 ADR**——`docs/agents/domain.md` 明文要求
3. **§11 不变量是硬约束**——任何 issue 实现都要回头验证
4. **HITL 段不替 owner 决定**——#43 / #44 涉及 grep 守护验收 + ADR-0002 偏差 review，agent 不擅自发布
5. **新术语先入 `CONTEXT.md`**——避免 wiki 漂移
6. **接受失败并重来**——仓库还原后立即重新启动，不要停在"之前做好了"的情绪里
7. **不替 owner 拍 ADR 决策**——发现 spec 偏差时**记录但不擅自决定**，留到 HITL 阶段由 owner 拍板

→ 相关：[[wiki-meta]] / [[../30-protocol/implementation-deviations]] / [[../10-design/design-philosophy]]