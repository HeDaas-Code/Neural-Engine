# 工作 Wiki — Neural Engine 项目分析 + 设计 Wiki

> **目的**：追踪 Neural Engine 的设计与实现进展。**只读仓库**，对 src/ 代码**不**做任何改动（除工程笔记中明确允许的 demo）。
> **约定**：用 `[[wikilinks]]` 互相引用——写一个 wiki 词条（双中括号包起来的页面名）；每篇顶部一个 TL;DR；issue / ADR 引用走 `[[raw-docs/ADR-0001-v0-baseline-script-spec §5.3]]`、`#23` 这种短形式。

## 索引

### 设计层（10-design）
- [[00-index/README]] — 入口地图（仓库速览 + 主题路径）
- [[10-design/vision]] — 项目愿景与定位
- [[10-design/design-philosophy]] — 设计哲学（命名空间分离 / 引用即跳转 / CSS 化的修饰器 / DSL 即规范）
- [[10-design/namespace-semantics]] — **命名空间语义核心澄清**（ID vs 变量 / NEXT 元组的两槽 / next_var_table 是桥）
- [[10-design/terminology]] — 术语表（中英对照 + "不要用"清单）
- [[10-design/glossary-anchors]] — **自创名词索引**（词 → raw-docs 锚点反向表）
- [[10-design/constraints]] — **强约束清单**（core 无 UI / NEXT 非字符串 / 命名空间分离 / @ 不跨块 等）

### 架构层（20-architecture）
- [[20-architecture/overview]] — 三上下文架构（core / editor / runtime）+ v0 实施路径
- [[20-architecture/ast-nodes]] — AST 节点 dataclass 设计（v0-issue-2）
- [[20-architecture/multi-process]] — 多进程 + 数据总线模型
- [[20-architecture/state-machine]] — 状态机 / GameState / decorator_state

### 协议层（30-protocol）
- [[30-protocol/messages]] — Cmd/Evt 全清单 + JSON schema
- [[30-protocol/bus]] — EngineBus 封装（v0-issue-5 已实现）
- [[30-protocol/implementation-deviations]] — **实测代码 vs spec 偏差**（3 偏差 + 7 确认）

### 任务层（40-issues）
- [[40-issues/dashboard]] — 22 v0 + 8 v1 issue 总览 + 完成度 + **v1 路线图（合并到本节）**
- [[40-issues/dependency-graph]] — issue 依赖关系图（v0 + v1 双子图）

### 验证层（50-fixtures）
- [[50-fixtures/chapter01]] — ADR 附录 A 剧本分析 + 期望事件流（**v0 打桩 + v1 真分支两版本**）

### 元信息（90-meta）
- [[90-meta/wiki-meta]] — 本工作 Wiki 自身的元信息（创建背景 + 文件清单 + 与上一轮区别）
- [[90-meta/about-author]] — 作者画像推断

### 原文快照（raw-docs，核对用）
- [[raw-docs/ADR-0001-v0-baseline-script-spec]] — **ADR-0001** v0 脚本规范（权威）
- [[raw-docs/PRD-0001-v0-engine-implementation]] — **PRD-0001** v0 引擎实现
- [[raw-docs/ADR-0003-v1-expression-subsystem]] — **ADR-0003** v1 表达式子系统架构（v1-issue-1 已落地）
- [[raw-docs/CONTEXT-core]] — **core** 上下文术语表 + 强约束
- [[raw-docs/CONTEXT-editor]] — **editor** 上下文术语表
- [[raw-docs/CONTEXT-runtime]] — **runtime** 上下文术语表
- [[raw-docs/domain]] — **domain.md** agent 协作规则 + ADR 冲突提示
- [[raw-docs/issue-tracker]] — issue 跟踪规则
- [[raw-docs/triage-labels]] — 5 类 triage 标签
- [[raw-docs/CLAUDE]] — **CLAUDE.md** 项目说明 + agent 工具链
- [[raw-docs/CONTEXT-MAP]] — **CONTEXT-MAP.md** 上下文映射表
- [[raw-docs/工程笔记/v0-issue-1-skel]] ~ `[[raw-docs/工程笔记/v0-issue-21-adr]]` — 22 个 issue body 工程笔记

## 写作约定

- **中文为主**，技术术语保留英文
- 每个文件 80~300 行，单一主题；超长就拆
- TL;DR 必填，3 行以内
- 引用 ADR 用 `[[raw-docs/ADR-0001-v0-baseline-script-spec §5.3]]`（**raw-docs 路径 + 章节**）
- 引用 CONTEXT 用 `[[raw-docs/CONTEXT-core]]`
- 引用 issue 用 `#23`（裸号，对应 v0-issue-1）
- 引用工程笔记用 `[[raw-docs/工程笔记/v0-issue-2-ast]]`
- 引用 vault 内页用 `[[10-design/vision]]`（相对路径）
- 修改仓库**任何**文件前先回查 [[10-design/constraints]]（强约束清单）

## 双向引用规则

> **vault 设计原则**：每页至少要有 1 条入链（被其他页引用）+ 1 条出链（引用其他页）。raw-docs 里 32 个原文快照**必须**被至少一篇 wiki 页显式引用（用 `raw-docs/...` 路径），不能纯快照当死页。

执行状态：见 [[90-meta/wiki-meta#双向引用状态]]。

## 阅读路径建议

1. **新人入门**：[[00-index/README]] → [[10-design/vision]] → [[10-design/namespace-semantics]]
2. **准备实现**：GH `#23` 开工前必读 [[10-design/constraints]] + [[raw-docs/ADR-0001-v0-baseline-script-spec]] 全文
3. **HITL 完工**：`#43` / `#44` 前必读 [[40-issues/dashboard]] + [[50-fixtures/chapter01]] + [[10-design/glossary-anchors]]

## 提交状态

- ✅ 本地仓库 `工作Wiki/` 目录
- ✅ 双推：main 分支（`origin/cursor/setup-issues-v0-vertical-slices` @ `125f237`）+ wiki 分支（`origin/wiki`）
- ✅ **v0 全部完成（2026-06-15）**：22/22 GH issues closed + 182/182 测试通过
- ✅ **docs/adr/0002-v0-engine-implementation.md** + **docs/audit/v0-invariant-audit.md** 发布
- ✅ **v1-issue-1 表达式子系统骨架（2026-06-15）**：commit `2a83774` 落地 `src/core/engine/expr/` 6 个 .py + 37 个新测试 + 219/219 测试通过
- ⚠️ **v1 闭环（GH #49-#51）OPEN**：`executor._execute_if` 接入 `ExprDispatcher` 是唯一卡点——预计 ~30 行 executor.py 改动即可闭环。详见 [[40-issues/dashboard#v1-表达式子系统-prd-0002--adr-0003]]
- ⚠️ **owner 必审查（v0）**：ADR-0002 §10 列了 6 个 agent 越权代做的接受决策（详见 [docs/adr/0002-v0-engine-implementation.md §10](https://github.com/HeDaas-Code/Neural-Engine/blob/cursor/setup-issues-v0-vertical-slices/docs/adr/0002-v0-engine-implementation.md)）
- ⚠️ **owner 必审查（v1）**：v1-issue-1 0 偏差（ADR-0003 §3 全 14 接口对照）——详见 [[30-protocol/implementation-deviations#v1-issue-1-偏差审计-实测-0-偏差]]
- 📌 **wiki 维护节奏**：v0 已闭环 + v1-issue-1 骨架已闭环；**v1 真分支（#49-#51）由 owner 决定启动时机**，启动时再回来更新 dashboard / chapter01 验证脚本段