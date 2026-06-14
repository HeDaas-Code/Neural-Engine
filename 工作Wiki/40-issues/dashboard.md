# 40 · Issue 看板

> **TL;DR**：22 个 GH issue（#22 ~ #44）按 PRD-0001 拆分的 v0 实施任务——**19 条 `ready-for-agent`**（v0-issue-1 ~ 19） + **1 父 PRD #22 `ready-for-human`** + **2 条 `ready-for-human` HITL**（#43 / #44 = v0-issue-20 / 21 守护）。仓库还原后**全部 OPEN**，实现进度 0/22。

## 总览表（GH 编号 → v0-issue 编号）

> **编号说明**：issue 标题里的 `v0-issue-N` 是 v0 实施序列号，**与 GitHub issue 编号不同**——映射关系（按 `gh issue list` 实际抓取）：

| GH # | v0-issue | 标题（缩写） | 标签 | 阶段 | 前置 |
| --- | --- | --- | --- | --- | --- |
| 22 | PRD | v0 基础版引擎实现（PRD）| ready-for-human | meta | — |
| 23 | v0-issue-1 | 仓库骨架 + 包结构 + pytest 配置 | ready-for-agent | 骨架 | — (可立即开工) |
| 24 | v0-issue-2 | AST 节点 dataclass + 错误类 | ready-for-agent | 数据结构 | #23 |
| 25 | v0-issue-3 | 命令 schema dataclass（GUI→Engine 3 条）| ready-for-agent | 协议 | #23 |
| 26 | v0-issue-4 | 事件 schema dataclass（Engine→GUI 6 条）| ready-for-agent | 协议 | #23 |
| 27 | v0-issue-5 | 双向 EngineBus 封装（multiprocessing.Queue + JSON 序列化）| ready-for-agent | 总线 | #25 #26 |
| 28 | v0-issue-6 | neon 围栏块拆分器 | ready-for-agent | 解析器 | #24 |
| 29 | v0-issue-7 | 块级骨架解析（node start/end 边界 + 整行注释跳过）| ready-for-agent | 解析器 | #28 |
| 30 | v0-issue-8 | 元数据区解析（id:xxx / id:start / id:endX / id:endX:chapterYY）| ready-for-agent | 解析器 | #29 |
| 31 | v0-issue-9 | next 声明解析 + 归一化（单 next 简写 + 多 next 完整 + 互斥校验）| ready-for-agent | 解析器 | #30 |
| 32 | v0-issue-10 | 块内语句解析（文本行 + node start/end/in/echo/next_id + 强化首条检查）| ready-for-agent | 解析器 | #29 |
| 33 | v0-issue-11 | node if 解析（二元 / 多元 / 简略二元 / 分支项省略 node 前缀）| ready-for-agent | 解析器 | #31 #32 |
| 34 | v0-issue-12 | @xxx 修饰器行解析（key:val 调用 + key 休止符 + token 列表）| ready-for-agent | 解析器 | #32 |
| 36 | v0-issue-13 | GameState + Executor 骨架 + 内存事件捕获器 | ready-for-agent | 执行器 | #28 #31 |
| 37 | v0-issue-14 | 核心节点执行（Text/In/Echo/NextId）+ NEXT 跳转 + node end 路由决策 | ready-for-agent | 执行器 | #36 |
| 38 | v0-issue-15 | @style 修饰器执行 + 块级作用域（**node start 时清空**，不变量 #2）| ready-for-agent | 修饰器 | #37 |
| 39 | v0-issue-16 | node if 打桩执行 + 跨块 ID 校验 + node end 路由边界 | ready-for-agent | 执行器 | #37 #38 #31 |
| 40 | v0-issue-17 | core 进程入口 main.py（装配 EngineBus + 加载章节 + 命令循环 + GUI 子进程）| ready-for-agent | 入口 | #27 #37 |
| 41 | v0-issue-18 | runtime GUI 占位（PyQt6 可选 / 装了走 Qt 窗口 / 没装走 CLI print+input）| ready-for-agent | GUI | #23 #25 #26 #27 |
| 42 | v0-issue-19 | chapter01 fixture + 端到端集成测试（in→echo→end + 多元 if + 修饰器 + 路由事件）| ready-for-agent | 端到端 | #39 |
| 43 | v0-issue-20 | [HITL] §11 关键不变量自动化守护 + §8 MVP 表逐条勾 | ready-for-human | HITL 守护 | #22 #42 |
| 44 | v0-issue-21 | [HITL] ADR-0002 完工记录 + close 父 #22 | ready-for-human | HITL 完工 | #22 |

**GH 编号跳号**：`#35` 不存在（v0-issue-12 → #34 直接跳到 v0-issue-13 → #36）——可能是 owner 预留或编辑时漏号，不影响依赖。

## 按阶段分类

### 阶段 0（骨架）
- `#23` 仓库骨架

### 阶段 1（数据结构 + 协议 + 总线）
- `#24` AST 节点
- `#25` Cmd / `#26` Evt / `#27` EngineBus

### 阶段 2（解析器，链式依赖）
- `#28` neon 围栏拆分
- `#29` 块级骨架 / `#30` 元数据区 / `#31` next 声明
- `#32` 块内语句 / `#33` node if 解析 / `#34` @xxx 修饰器解析

### 阶段 3（执行器）
- `#36` GameState + Executor 骨架
- `#37` 核心节点执行
- `#38` @style 修饰器执行
- `#39` node if 打桩 + 路由边界

### 阶段 4（入口 + GUI）
- `#40` core 进程入口
- `#41` GUI 占位（三路径）

### 阶段 5（端到端）
- `#42` chapter01 fixture + 集成测试

### 阶段 6（HITL 完工）
- `#43` §11 不变量自动化守护（HITL）
- `#44` ADR-0002 完工记录（HITL）

## 完成度（2026-06-15 仓库还原后）

```
[....................] 0/22（仓库被还原，所有代码待重写）
```

**实际完成**：无（仓库 reset 到 commit `499fcf1`，src/core/runtime/editor 只有 CONTEXT.md）

**下一步可开工**：GH `#23`（v0-issue-1 仓库骨架）——无前置，pytest 配置 + 包结构 + 5 个 `__init__.py` 空文件，~30 分钟工作量。

## 引用源

- 仓库 issue 列表 —— `gh issue list --repo HeDaas-Code/Neural-Engine`
- 22 个 issue body 工程笔记 —— [[raw-docs/工程笔记/]]
  - [[raw-docs/工程笔记/v0-issue-2-ast]] · [[raw-docs/工程笔记/v0-issue-3-cmd]] · [[raw-docs/工程笔记/v0-issue-4-evt]] · [[raw-docs/工程笔记/v0-issue-5-bus]]
  - [[raw-docs/工程笔记/v0-issue-6-neon]] · [[raw-docs/工程笔记/v0-issue-7-skel]] · [[raw-docs/工程笔记/v0-issue-8-meta]] · [[raw-docs/工程笔记/v0-issue-9-next]]
  - [[raw-docs/工程笔记/v0-issue-10-body]] · [[raw-docs/工程笔记/v0-issue-11-if]] · [[raw-docs/工程笔记/v0-issue-12-deco]]
  - [[raw-docs/工程笔记/v0-issue-13-exec]] · [[raw-docs/工程笔记/v0-issue-14-nodes]] · [[raw-docs/工程笔记/v0-issue-15-deco-exec]] · [[raw-docs/工程笔记/v0-issue-16-if-end]]
  - [[raw-docs/工程笔记/v0-issue-17-core-main]] · [[raw-docs/工程笔记/v0-issue-18-gui]] · [[raw-docs/工程笔记/v0-issue-19-fixture]]
  - [[raw-docs/工程笔记/v0-issue-20-invariant]] · [[raw-docs/工程笔记/v0-issue-21-adr]]
  - [[raw-docs/工程笔记/01-parent]] · [[raw-docs/工程笔记/02-skeleton]]
- 父 PRD —— [[raw-docs/PRD-0001-v0-engine-implementation.md]]
- 依赖关系 —— [[dependency-graph]]

→ 相关：[[dependency-graph]] / [[../50-fixtures/chapter01]] / [[../30-protocol/messages]]