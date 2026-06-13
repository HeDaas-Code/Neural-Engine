# PRD — v0 基础版引擎实现（v0 Baseline Engine Implementation）

> 对应 ADR：`docs/adr/0001-v0-baseline-script-spec.md`
> 上下文：`core`（主）/ `runtime`（GUI 占位）
> 状态：待发布 GitHub Issue · `ready-for-agent`

---

## Problem Statement

中文文字游戏引擎目前只有规范文档（ADR-0001），**没有任何可运行代码**。项目所有者无法：

- 解析 `chapters/chapter01.md` 这种 neon 标记的剧本文件
- 跑通"输入→回显"这一最简交互（v0 唯一跑通路径）
- 验证 §11 列出的 10 条关键不变量是否被正确实施
- 给后续 v0 之外的扩展（存档、编辑器、真实多媒体）提供执行基线

缺一个能 import、能 CLI 跑通 ADR-0001 §8 MVP 范围表的 Python 引擎。

## Solution

按 ADR-0001 §9 项目结构交付一个**多进程 Python 实现**：

- `core` 上下文负责解析 + 执行（无 UI 依赖）
- `runtime` 上下文负责最简 GUI（PyQt6 占位窗）
- 两进程通过 `multiprocessing.Queue` 数据总线通信（ADR §7）
- 端到端 fixture 是 ADR §附录 A 的演示剧本，能完整跑通 v0 唯一路径

实现完成后，作者可运行 `python -m core.engine.main chapters/chapter01.md` 启动引擎并与最简 GUI 互动。

## User Stories

### 解析与加载
1. 作为引擎开发者，我希望 `interpreter` 能解析单文件 `.md` 章节，**只关注** ` ```neon ` 围栏块，忽略其余 Markdown 内容，以便未来能承载长篇剧本
2. 作为引擎开发者，我希望解析器对**整行注释**（行首 `#`）静默跳过，对**混合语句**（简写 + 完整 next）抛出明确错误，以便 v0 唯一跑通路径不出歧义
3. 作为引擎开发者，我希望 `id:start` 在文件内**唯一**，解析时发现多个立即报错，以便后续加载器直接定位入口
4. 作为引擎开发者，我希望 next 变量表是**变量名 → 节点 ID** 的字典，NEXT 是**表项引用**而非字符串，以便 §5 不变量 #3 落地
5. 作为引擎开发者，我希望单 next 简写（`next:yyy`）自动归一化为 `NEXT = ref("yyy")`，多 next 时 `NEXT = None`，以便 §5.2 表准确生效
6. 作为测试作者，我希望解析器对**任意未在 §8 表中出现的语句**抛 `SyntaxError`，以便规范就是实现

### 状态机与执行
7. 作为引擎开发者，我希望 `executor` 维护 `GameState`（变量字典 + 上一节点路径），并在 `node end` 时清空 `@` 修饰器状态，以便 §11 不变量 #2 成立
8. 作为引擎开发者，我希望 `node in ->var` 触发 `prompt_input` 事件、阻塞等待 GUI 推送 `user_input` 命令，以便"输入→回显"路径跑通
9. 作为引擎开发者，我希望 `node echo var` 发送 `text` 事件（payload 含变量值），以便 GUI 收到后渲染
10. 作为引擎开发者，我希望 `node if` 解析为 AST 但**执行打桩**（输出 `log` 事件 + 强制走第一个分支），以便 v0 不真做条件逻辑
11. 作为引擎开发者，我希望 `node end` 严格按 §5.3 行为：NEXT 非空就跳、NEXT 为空且 `id:endX:chapterYY` 广播 `route`、否则广播 `chapter_end`

### 数据总线与协议
12. 作为引擎开发者，我希望 `bus.put_cmd(cmd)` / `bus.get_evt()` 是**唯一**的跨进程接口，序列化统一用 `json.dumps`，以便 §7.5 落地
13. 作为协议使用者，我希望 §7.3 / §7.4 列出的每条命令/事件都有**Python dataclass** 定义与 `to_dict` / `from_dict`，以便 IDE 自动补全、编译期捕获字段名错误
14. 作为 GUI 开发者，我希望订阅事件时只看到 `event` 字段名 + 业务字段，**不看到**序列化痕迹，以便 UI 代码与协议解耦

### 修饰器
15. 作为引擎开发者，我希望 `@style key:val` 与 `@style key`（休止符）都广播 `decorator` 事件、payload 含原始 token 列表，以便 GUI 占位实现只打印、不真渲染

### GUI（runtime 占位）
16. 作为玩家，我希望 GUI 在收到 `text` 事件时**追加一行文本**到滚动区
17. 作为玩家，我希望 GUI 在收到 `prompt_input` 事件时**激活输入框**，回车后推送 `user_input` 命令
18. 作为引擎开发者，我希望 GUI 进程**对未实现事件**（`decorator` / `route` / `chapter_end` / `log`）静默忽略或仅打日志，不抛异常

### 端到端 fixture
19. 作为项目所有者，我希望 `chapters/chapter01.md`（即 ADR 附录 A 的剧本）能被解析、加载、`node in ->p_mood` 后输入"平静"、回显"平静"、再到 `c1` 选择 1 跳到 `ca`，**整链路可重放**，以便 v0 完工
20. 作为 CI，我希望 `tests/test_echo.md` 与 `chapters/chapter01.md` 各有一个自动化用例，断言事件流符合预期

### 关键不变量守护
21. 作为代码审查者，我希望仓库内**没有第 3 方 NEXT 字符串字面量**——`grep -r '"NEXT"' src/` 应为 0 命中，以便 §11 不变量 #3 不会悄悄被破坏
22. 作为代码审查者，我希望所有跨块引用的 next 变量名都在元数据区有对应声明——孤儿引用立即 `NameError`

## Implementation Decisions

### 总体架构

- **两个独立 Python 进程**：`core/engine/main.py` 与 `runtime/gui/main.py`（符合 ADR §7.1）
- **`multiprocessing.Queue` 双向队列**（GUI→Engine 一个、Engine→GUI 一个）
- **Python 3.11+**（使用 `tomllib` 暂不需要，但用 `dict[str, Any]` 类型注解）
- **GUI 框架**：PyQt6（如 ADR §9）

### 模块清单

| 模块 | 路径 | 职责 | 接口深度 |
| ---- | ---- | ---- | -------- |
| `interpreter` | `src/core/engine/interpreter.py` | 解析 `.md` → `Story` 对象 | deep：单入口 `parse_chapter(path) -> Story`，隐藏 Markdown / neon 拆分、tokenize、AST 构造 |
| `ast_nodes` | `src/core/engine/ast_nodes.py` | AST 节点 dataclass | shallow：纯数据结构 |
| `executor` | `src/core/engine/executor.py` | 状态机 + 节点执行 | deep：单入口 `Executor(story, bus).run()`，内部封装变量表、NEXT 引用、@ 状态 |
| `protocol` | `src/core/engine/protocol.py` | 消息 dataclass | shallow：与 `runtime/protocol.py` 共享（按 ADR §9 标注的复用） |
| `bus` | `src/core/engine/bus.py` | 跨进程队列封装 | deep：单入口 `EngineBus(cmd_q, evt_q).put_cmd / get_evt`，内部封装序列化 |
| `main` | `src/core/engine/main.py` | 进程入口 | shallow：装配 + 启动循环 |
| `decorators.style` | `src/core/decorators/style.py` | `@style` 注册 | shallow |
| `gui.window` | `src/runtime/gui/window.py` | PyQt6 QMainWindow | medium：单类，主线程事件循环 |
| `gui.display` | `src/runtime/gui/display.py` | 文本追加组件 | shallow |
| `gui.input` | `src/runtime/gui/input.py` | 输入框 + 提交逻辑 | shallow |
| `gui.main` | `src/runtime/gui/main.py` | GUI 进程入口 | shallow |

### 关键 schema（来自 ADR §7，经 prototype 校对）

消息统一为 `dict`（JSON 可序列化），字段命名 `snake_case`：

**命令（GUI → Engine）**
- `{"cmd": "load_chapter", "path": "chapters/chapter01.md"}`
- `{"cmd": "user_input", "value": "玩家输入"}`
- `{"cmd": "shutdown"}`

**事件（Engine → GUI）**
- `{"event": "text", "content": "...", "style": "narration"}`
- `{"event": "prompt_input", "var": "p_mood"}`
- `{"event": "decorator", "name": "style", "args": ["bgm:rain.mp3"]}`
- `{"event": "route", "target": "chapter02"}`
- `{"event": "chapter_end"}`
- `{"event": "log", "level": "info", "message": "..."}`

`@style key` 休止符编码为 `{"event": "decorator", "name": "style", "args": ["key"]}`（无冒号，GUI 据此判休止）。

`id:endX:chapterYY` 在 `node end` 时拆出第三段作为 `route.target`；只有第三段存在才广播 `route`，否则广播 `chapter_end`（来自 ADR §5.3 + §2.3，原型验证过）。

### NEXT 引用语义

`NEXT` 内部表示为 `tuple[str, str] | None`：`("var_name", "node_id")` 或 `None`。`executor` 持有一张 next 变量字典（`dict[str, str]`），跳转时**取 NEXT 指向表项的 value**（节点 ID）。

- 单 next 简写 `next:c1` → `NEXT = (None, "c1")`（无变量名但语义上直达 ID）
- `t_a <- next: ca` → next 变量表 `{"t_a": "ca"}`；`node t_a` → `NEXT = ("t_a", "ca")`
- 多元 `node if p_pick [1:t_a, 2:t_b, 3:echo p_pick]` → 分支项 `3:echo p_pick` 解析为 `NEXT = ("echo", None)`（echo 节点的引用占位，打桩期不真跳），由 executor 收到时打印 `log` 事件

> 来源：原型手写一版 executor 验证了 `(var, id)` 元组足够，不必引入引用类型。`echo` 在分支项里语义是"执行 echo 再继续"，当前 v0 直接走"假装 echo 完成，继续走第 1 分支"打桩。

### node if 打桩策略

v0 不真做条件判断：
- 解析时构造 `IfNode(cond, branches: list[tuple[value, target]])`
- 执行时**永远选第一个分支**（value 最小的），广播 `log` 事件说明"条件打桩"
- 这样 v0 跑通路径不会因为条件失败卡住，同时不掩盖语法错误

### 状态机边界

- `GameState` = `dict[str, str]`（变量表，v0 全部按字符串存）
- `node end` 时**清空** `@` 修饰器状态（不变量 #2）
- 跨块不继承任何变量以外的运行时状态

### 错误处理

- **解析期**错误：抛 `SyntaxError` + 行号
- **执行期**错误：广播 `log(level="error", message=...)` + 进程退出码 1
- **未实现事件**：GUI 静默忽略（v0 不真渲染的多媒体）

## Testing Decisions

### 优秀测试的标准

- **只测外部行为**（事件流、最终状态、退出码），不测内部数据结构
- 解析器测试用 fixture 剧本 + 断言 AST / `Story` 形状
- 执行器测试用**事件流捕获器**（替换 `bus.get_evt` 为列表），断言发出事件序列
- 端到端测试用 subprocess + 临时 FIFO 模拟 GUI，断言 GUI 收到的事件

### 要写测试的模块

| 模块 | 测试类型 | fixture |
| ---- | -------- | ------- |
| `interpreter` | 单元 | `tests/parser/inputs/*.neon` + 期望 AST |
| `executor` | 单元 | 内存中的 `Story` + 捕获事件流 |
| `bus` + `protocol` | 单元 | 双向 Queue 互发 + 序列化往返 |
| `decorators/style` | 单元 | 直接调用 + 断言 `decorator` 事件 |
| 端到端 | 集成 | `chapters/chapter01.md` + subprocess |

### 关键 fixture

- `tests/parser/inputs/single_next.neon` —— 1 块单 next
- `tests/parser/inputs/multi_next.neon` —— 1 块 3 个 next
- `tests/parser/inputs/end_route.neon` —— `id:end1:chapter02` 解析
- `tests/parser/inputs/invalid_mixed.neon` —— 期望 `SyntaxError`
- `tests/test_echo.md` —— §6 示例的 echo 路径
- `chapters/chapter01.md` —— ADR 附录 A 的全语法演示

## Out of Scope（v0 不做）

- 真实多媒体播放（BGM / SE / 视频）
- 普通 Markdown 渲染（v0 只跑通 neon 块）
- 表达式求值（`p_tall + 1` 实际语义）
- 存档 / 读档
- 章节图 DAG 编辑器
- 行尾注释 / 块注释
- 条件表达式真值
- 多章节串联的 GUI 路由处理（GUI 收到 `route` 仅打日志）
- 移动 / Web 端

## Further Notes

- ADR-0001 §8 是**实现完成标准**的权威列表——本 PRD 完成后，§8 表中所有"实现"项应可在 fixture 上端到端跑通，所有"打桩"项应解析成功且不抛异常
- §11 关键不变量应**全部有自动化测试守护**（用户故事 #21、#22）
- 任何与 ADR-0001 冲突的实现决策必须**先回到 ADR 修订**，再写代码
- 完成后 `gh issue close <本 PRD 编号>`，并在 `docs/adr/0002-v0-engine-implementation.md` 写入"实现完成"记录
