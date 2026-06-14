# 10 · 强约束清单

> **TL;DR**：core / executor / 协议层有 7 条**绝对不能违反**的强约束——违反任何一条 ADR-0001 §11 不变量守护测试（v0-issue-20 HITL）就会挂。

> **本页面是 wiki 速查版**；权威定义见 [[raw-docs/ADR-0001-v0-baseline-script-spec §11]]（不变量）+ [[raw-docs/CONTEXT-core.md]]（core 强约束映射）。

## 7 条强约束

| # | 强约束 | 落地位置 | 守护方式 |
| --- | --- | --- | --- |
| **#1** | **core 无 UI 依赖**——禁止 `import PyQt6 / tkinter / 任何 GUI 框架` | `core/**/*.py` import 列表 | code review + CI lint |
| **#2** | **命名空间严格分离**——`id:xxx` 只能在 `node start` 之前的元数据区 | `core/engine/interpreter.py` | `tests/parser/`（v0-issue-7/8/10/11）|
| **#3** | **NEXT 是引用不是字符串**——`executor` 内禁止出现 `NEXT = "node_id"` 字面量赋值；NEXT 必须从 next_var_table 取 ID | `core/engine/executor.py` | **v0-issue-20 HITL**：`grep -r '"NEXT"' src/` = 0 命中（pytest 用例）|
| **#4** | **`@` 状态不跨块继承**——`executor` 在 `node start` 时清空修饰器状态表 | `Executor.run()` 的 `Start` 分支 | `tests/executor/test_style_scope.py`（v0-issue-15）|
| **#5** | **数据总线消息一律 JSON dict**——禁止 dataclass 直接跨进程传输；`protocol.to_dict / from_dict` 是唯一序列化点 | `core/engine/bus.py` + `protocol.py` | `tests/core/test_engine_bus.py`（v0-issue-5）|
| **#6** | **错误处理统一**——解析期错误抛 `ParserError(SyntaxError)` 带 `loc: BlockLocation`；执行期错误广播 `log(level="error", ...)` + 进程退出码 1 | `interpreter.py` + `executor.py` | 各 parser/executor 测试 + v0-issue-20 §11 #8 守护 |
| **#7** | **多进程边界**——GUI ↔ core 之间**只能**通过数据总线通信；禁止共享内存 / 全局变量 / 文件锁 | `core/engine/main.py` + `runtime/gui/main.py` 装配流程 | code review |

## §11 关键不变量（10 条）的工程映射

[ADR-0001 §11](raw-docs/ADR-0001-v0-baseline-script-spec) 列了 10 条不变量，每条都对应到 v0 实现的具体守护位置（[v0-issue-20 HITL 验收](raw-docs/工程笔记/v0-issue-20-invariant.md)）：

| 不变量 | 内容 | 实现守护 |
| --- | --- | --- |
| #1 | ID 与变量命名空间严格分离 | 强约束 #2 + v0-issue-8 解析器 |
| #2 | 块级作用域不跨块继承 | 强约束 #4 + v0-issue-15 |
| #3 | NEXT 是 next 变量表项的引用，不是字符串 | 强约束 #3 + **v0-issue-20 §11 #3 grep 守护**：`grep -r '"NEXT"' src/` |
| #4 | 单 next 自动设 NEXT，多 next 必须显式 | v0-issue-9 解析器 + 单 next 简写归一化 |
| #5 | endX 同时承担结局标记 + 路由目标 + 玩家路径记录 | `IdEnd(x, route_chapter)` 字段（v0-issue-8）|
| #6 | 数据总线消息一律 JSON dict | 强约束 #5 + **v0-issue-20 §11 #6 grep 守护**：`grep -r 'pickle\|msgpack' src/` = 0 |
| #7 | 单 next 简写与多 next 完整互斥 | v0-issue-9 |
| #8 | v0 仅支持整行注释（行首 `#`） | v0-issue-7 + v0-issue-10 块内解析 |
| #9 | `<-` 冒号右边是 ID 命名空间，左边是变量命名空间 | v0-issue-9 |
| #10 | 分支项内允许省略 `node` 前缀 | v0-issue-11 `node if` 解析 |

## 软约束（设计原则 / 不强制）

| 软约束 | 含义 |
| --- | --- |
| 深模块优先 | `parse_chapter / Executor.run / EngineBus.put_cmd` 是 deep 接口；AST/protocol/decorator handler 是 shallow |
| 可测试性 | `interpreter/executor/bus` 允许替换数据总线为内存 Queue（fixture 测试）|
| 协议稳定 | 消息 schema 公布后**不向后兼容**改；新增字段用可选键 |
| 可扩展语言 | `@` 修饰器走注册表；新增 `@voice/@bg` 不修改 executor |
| 跨上下文术语 | 引用领域概念时用 CONTEXT.md 术语表里"明确用"的词汇，不用"不要用"清单里的同义词 |

## HITL 守护（v0-issue-20 §11）

[v0-issue-20](raw-docs/工程笔记/v0-issue-20-invariant.md) HITL 验收要跑 **3 条 grep**：

```bash
# 不变量 #3：禁止 NEXT 字符串字面量
grep -r '"NEXT"' src/             # 应为 0 命中

# 不变量 #6：禁止 pickle / msgpack 等非 JSON 序列化
grep -r 'pickle\|msgpack' src/    # 应为 0 命中

# PRD 硬约束：禁止 TODO / FIXME 残留
grep -r 'TODO\|FIXME' src/        # 应为 0 命中
```

每条都写一个 pytest 用例：执行 `subprocess.run(...)` + 断言 exit code 1（grep 没命中时）。

## ADR 冲突处理（来自 domain.md ADR 冲突提示）

> **当代码决策与现有 ADR 矛盾时**，**显式标注**而非静默覆盖：
>
> > _与 ADR-0001 §5.3 的决策冲突——但值得重新讨论，理由是……_

→ 修改路径：先 [[raw-docs/ADR-0001-v0-baseline-script-spec]]（如需），再写 `docs/adr/0002-v0-engine-implementation.md` 记录偏离（v0-issue-21 HITL）。

## 与其他页的关系

- [[namespace-semantics]] — 强约束 #2/#3 的语义层细化（命名空间 + NEXT 元组两槽）
- [[state-machine]] — 强约束 #4 的运行时表现（node start 清空 decorator_state）
- [[../20-architecture/multi-process]] — 强约束 #5/#7 的拓扑表现
- [[terminology]] — "不要用"清单与软约束"跨上下文术语"对齐

## 引用源

- ADR-0001 §11（关键不变量）—— [[raw-docs/ADR-0001-v0-baseline-script-spec]]
- `src/core/CONTEXT.md` 强约束小节 —— [[raw-docs/CONTEXT-core.md]]
- `docs/agents/domain.md` ADR 冲突提示 —— [[raw-docs/domain.md]]
- v0-issue-20 HITL 守护清单 —— [[raw-docs/工程笔记/v0-issue-20-invariant.md]]
- [[40-issues/dashboard]] — issue 完成度跟踪