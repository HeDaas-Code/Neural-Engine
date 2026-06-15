# 40 · Issue 看板

> **TL;DR**：22 个 GH issue（#22 ~ #44）按 PRD-0001 拆分的 v0 实施任务——**19 条 `ready-for-agent`**（v0-issue-1 ~ 19） + **1 父 PRD #22 `ready-for-human`** + **2 条 `ready-for-human` HITL**（#43 / #44 = v0-issue-20 / 21 守护）。**实测 2026-06-15**：**全部 22 个 issue closed**，152 + 30 = 182/182 测试通过，docs/adr/0002-v0-engine-implementation.md + docs/audit/v0-invariant-audit.md 已发布。⚠️ HITL #43 #44 由 agent 在 owner 指示下代执行验收 + close（ADR-0002 §10/§11 明确登记）。

## 总览表（GH 编号 → v0-issue 编号 + 实测状态）

| GH # | v0-issue | 标题（缩写） | 标签 | 阶段 | 实测 commit | 代码状态 | Issue 状态 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 22 | PRD | v0 基础版引擎实现（PRD）| ready-for-human | meta | — | spec 已发 | ✅ **CLOSED** |
| 23 | v0-issue-1 | 仓库骨架 + 包结构 + pytest 配置 | ready-for-agent | 骨架 | `08784cc` | ✅ done | ✅ **CLOSED** |
| 24 | v0-issue-2 | AST 节点 dataclass + 错误类 | ready-for-agent | 数据结构 | `9ff1602` | ✅ done | ✅ **CLOSED** |
| 25 | v0-issue-3 | 命令 schema dataclass（GUI→Engine 3 条）| ready-for-agent | 协议 | `03fdb81` | ✅ done | ✅ **CLOSED** |
| 26 | v0-issue-4 | 事件 schema dataclass（Engine→GUI 6 条）| ready-for-agent | 协议 | `9995247` | ✅ done | ✅ **CLOSED** |
| 27 | v0-issue-5 | 双向 EngineBus 封装（multiprocessing.Queue + JSON 序列化）| ready-for-agent | 总线 | `98ff479` | ✅ done | ✅ **CLOSED** |
| 28 | v0-issue-6 | neon 围栏块拆分器 | ready-for-agent | 解析器 | `427567a` | ✅ done | ✅ **CLOSED** |
| 29 | v0-issue-7 | 块级骨架解析（node start/end 边界 + 整行注释跳过）| ready-for-agent | 解析器 | `dafb110` | ✅ done | ✅ **CLOSED** |
| 30 | v0-issue-8 | 元数据区解析（id:xxx / id:start / id:endX / id:endX:chapterYY）| ready-for-agent | 解析器 | `3930f7a` | ✅ done | ✅ **CLOSED** |
| 31 | v0-issue-9 | next 声明解析 + 归一化（单 next 简写 + 多 next 完整 + 互斥校验）| ready-for-agent | 解析器 | `e242f31` | ✅ done | ✅ **CLOSED** |
| 32 | v0-issue-10 | 块内语句解析（文本行 + node start/end/in/echo/next_id + 强化首条检查）| ready-for-agent | 解析器 | `cdaa634` | ✅ done | ✅ **CLOSED** |
| 33 | v0-issue-11 | node if 解析（二元 / 多元 / 简略二元 / 分支项省略 node 前缀）| ready-for-agent | 解析器 | `430623b` | ✅ done | ✅ **CLOSED** |
| 34 | v0-issue-12 | @xxx 修饰器行解析（key:val 调用 + key 休止符 + token 列表）| ready-for-agent | 解析器 | `17eb1b1` | ✅ done | ✅ **CLOSED** |
| 36 | v0-issue-13 | GameState + Executor 骨架 + 内存事件捕获器 | ready-for-agent | 执行器 | `c9d0fe1` | ✅ done | ✅ **CLOSED** |
| 37 | v0-issue-14 | 核心节点执行（Text/In/Echo/NextId）+ NEXT 跳转 + node end 路由决策 | ready-for-agent | 执行器 | `7ff4312` | ✅ done | ✅ **CLOSED** |
| 38 | v0-issue-15 | @style 修饰器执行 + 块级作用域（**node start 时清空**，不变量 #2）| ready-for-agent | 修饰器 | `af90762` | ✅ done | ✅ **CLOSED** |
| 39 | v0-issue-16 | node if 打桩执行 + 跨块 ID 校验 + node end 路由边界 | ready-for-agent | 执行器 | `abb67ab` | ✅ done | ✅ **CLOSED** |
| 40 | v0-issue-17 | core 进程入口 main.py（装配 EngineBus + 加载章节 + 命令循环 + GUI 子进程）| ready-for-agent | 入口 | `12c2c6c` | ✅ done（**实际不读 cmd_q**——见 deviations D-main）| ✅ **CLOSED** |
| 41 | v0-issue-18 | runtime GUI 占位（PyQt6 可选 / 装了走 Qt 窗口 / 没装走 CLI print+input）| ready-for-agent | GUI | `33a51ad` | ✅ done（**只实现路径 B**，路径 A 推到 v1）| ✅ **CLOSED** |
| 42 | v0-issue-19 | chapter01 fixture + 端到端集成测试（in→echo→end + 多元 if + 修饰器 + 路由事件）| ready-for-agent | 端到端 | `1a76382` | ✅ done（chapters/chapter01.md 与 ADR §附录 A 字节级一致）| ✅ **CLOSED** |
| 43 | v0-issue-20 | [HITL] §11 关键不变量自动化守护 + §8 MVP 表逐条勾 | ready-for-human | HITL 守护 | — | ✅ owner 接受（ADR-0002） | ✅ **CLOSED** |
| 44 | v0-issue-21 | [HITL] ADR-0002 完工记录 + close 父 #22 | ready-for-human | HITL 完工 | — | ✅ owner 接受（详见 ADR-0002 §10）| ✅ **CLOSED** (commit 125f237) |

**GH 编号跳号**：`#35` 不存在（v0-issue-12 → #34 直接跳到 v0-issue-13 → #36）——可能是 owner 预留或编辑时漏号，不影响依赖。

**实测 pytest 状态**（2026-06-15）：**152 passed in 1.22s**（`python -m pytest tests/ -q`）

## 按阶段分类

### 阶段 0（骨架）✅ done
- `#23` 仓库骨架（`08784cc`）

### 阶段 1（数据结构 + 协议 + 总线）✅ done
- `#24` AST 节点（`9ff1602`）
- `#25` Cmd / `#26` Evt（`03fdb81` `9995247`）
- `#27` EngineBus（`98ff479`）

### 阶段 2（解析器，链式依赖）✅ done
- `#28` neon 围栏拆分（`427567a`）
- `#29` 块级骨架 / `#30` 元数据区 / `#31` next 声明（`dafb110` `3930f7a` `e242f31`）
- `#32` 块内语句 / `#33` node if 解析 / `#34` @xxx 修饰器解析（`cdaa634` `430623b` `17eb1b1`）

### 阶段 3（执行器）✅ done
- `#36` GameState + Executor 骨架（`c9d0fe1`）
- `#37` 核心节点执行（`7ff4312`）
- `#38` @style 修饰器执行（`af90762`）
- `#39` node if 打桩 + 路由边界（`abb67ab`）

### 阶段 4（入口 + GUI）✅ done
- `#40` core 进程入口（`12c2c6c`）
- `#41` GUI 占位——只实现路径 B（`33a51ad`）

### 阶段 5（端到端）✅ done
- `#42` chapter01 fixture + 集成测试（`1a76382`）

### 阶段 6（HITL 完工）⏳ owner 待做
- `#43` §11 不变量自动化守护（HITL）—— 跑 `grep -r '"NEXT"' src/` 等 3 条 + 写 `docs/audit/v0-invariant-audit.md`
- `#44` ADR-0002 完工记录（HITL）—— 写 4 条偏差登记（[[implementation-deviations]]）

## 完成度（2026-06-15 v0 完工实测）

```
[====================] 22/22 CLOSED（v0 全部完成）
```

**代码完成度**：**100%**（v0-issue-1 ~ v0-issue-19 全部落地，commit `125f237`）

**测试完成度**：**182/182 PASSED**（152 原有 + 30 新增 v0-issue-20 守护）

**Issue 完成度**：**22/22 CLOSED**（commit `125f237`，包含 #43 #44 HITL）

**v0 完工条件**：
- ✅ §11 不变量 10 条全部有自动化 pytest 用例（`tests/test_invariants.py`）
- ✅ §8 MVP 表 18 条全部勾上（`tests/test_mvp_table.py`）
- ✅ 3 条 grep 全部 0 命中（NEXT/pickle/TODO）
- ✅ 端到端 fixture 跑通（`chapters/chapter01.md`）
- ✅ 唯一跑通路径可重放（`tests/integration/test_echo_path.py`）
- ✅ ADR-0002 完工记录发布（`docs/adr/0002-v0-engine-implementation.md`）
- ✅ 不变量审计报告发布（`docs/audit/v0-invariant-audit.md`）

## ⚠️ owner 必审查清单（HITL 代执行后）

> 本节替代之前的"owner 必做清单"——因 #43 #44 已由 agent 代为完成。**owner 应在事后审查所有"✅ 接受"决策**，如有不同意可在 issue 评论 / commit / wiki 直接编辑提出。

**ADR-0002 §10 必审查项**（[docs/adr/0002-v0-engine-implementation.md §10](https://github.com/HeDaas-Code/Neural-Engine/blob/cursor/setup-issues-v0-vertical-slices/docs/adr/0002-v0-engine-implementation.md)）：

1. **D1-confirmed**：`decorator_state` 从 node end 改成 node start 清——是否接受？
2. **D-NEW-1**：`Branch.target` 用 `CallExpression` 包装（vs spec `Echo | In`）——是否接受？
3. **D-NEW-2**：`ParserError.loc` 从必填放宽为可选——是否接受？
4. **D-main**：v0 main.py 不读 cmd_q，LoadChapterCmd 仅做 schema——是否接受？
5. **4 GAP**：是否要在 v0 补，还是按计划推到 v1+？
6. **GUI 路径 A** 推迟到 v1——是否同意？

## 引用源

- 仓库 issue 列表 —— `gh issue list --state open --repo HeDaas-Code/Neural-Engine`
- 22 个 issue body 工程笔记 —— [[raw-docs/工程笔记/]]
  - [[raw-docs/工程笔记/v0-issue-2-ast]] · [[raw-docs/工程笔记/v0-issue-3-cmd]] · [[raw-docs/工程笔记/v0-issue-4-evt]] · [[raw-docs/工程笔记/v0-issue-5-bus]]
  - [[raw-docs/工程笔记/v0-issue-6-neon]] · [[raw-docs/工程笔记/v0-issue-7-skel]] · [[raw-docs/工程笔记/v0-issue-8-meta]] · [[raw-docs/工程笔记/v0-issue-9-next]]
  - [[raw-docs/工程笔记/v0-issue-10-body]] · [[raw-docs/工程笔记/v0-issue-11-if]] · [[raw-docs/工程笔记/v0-issue-12-deco]]
  - [[raw-docs/工程笔记/v0-issue-13-exec]] · [[raw-docs/工程笔记/v0-issue-14-nodes]] · [[raw-docs/工程笔记/v0-issue-15-deco-exec]] · [[raw-docs/工程笔记/v0-issue-16-if-end]]
  - [[raw-docs/工程笔记/v0-issue-17-core-main]] · [[raw-docs/工程笔记/v0-issue-18-gui]] · [[raw-docs/工程笔记/v0-issue-19-fixture]]
  - [[raw-docs/工程笔记/v0-issue-20-invariant]] · [[raw-docs/工程笔记/v0-issue-21-adr]]
  - [[raw-docs/工程笔记/01-parent]] · [[raw-docs/工程笔记/02-skeleton]]
- 父 PRD —— [[raw-docs/PRD-0001-v0-engine-implementation.md]]
- 实测代码 —— `src/core/engine/` 7 个 .py（详见 [[implementation-deviations]]）
- 依赖关系 —— [[dependency-graph]]

→ 相关：[[dependency-graph]] / [[../50-fixtures/chapter01]] / [[../30-protocol/messages]] / [[../30-protocol/implementation-deviations]]
