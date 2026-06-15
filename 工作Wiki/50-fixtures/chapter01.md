# 50 · chapter01 fixture（ADR 附录 A）

> **TL;DR**：ADR-0001 附录 A 给的演示剧本——v0 的官方 fixture，**字节级一致**是 v0-issue-19 acceptance 标准。端到端测试（v0-issue-19）会在此 fixture 上验证事件流。

## 完整剧本（搬运）

> ⚠️ 注意：v0 fixture 与 ADR 附录 A **必须字节级一致**（v0-issue-19 acceptance 第 1 条）。任何差异视为对规范的偏离，需先回 ADR 修订。

````markdown
# 第一章：雨夜

> 这是 v0 MVP 测试章节的源文件。
> 引擎 v0 实现完成后，应可正确解析并执行此文件。

本章为 v0 全语法演示章节。

```neon
id:start
# 入口块：单 next 简写，NEXT = ref(c1)，直达下一节点
next:c1
node start
# 引擎开始执行——以下三行是普通文本行
雨夜。
雨声从破旧窗户的缝隙中渗入。
你坐在窗边，听着雨声。
# @style 修饰器：v0 阶段仅广播到 GUI，不真渲染
@style bgm:rain.mp3
# 等待用户输入，存到普通变量 p_mood
node in ->p_mood
# 回声：把 p_mood 推送给 GUI 显示
node echo p_mood
node end
```

```neon
id:c1
# 多 next 演示：必须带变量名，NEXT=null，待显式设置
t_a<-next:ca
t_b<-next:cb
node start
你听到门外传来两声敲门。
node in ->p_pick
# 多元条件：p_pick 是普通变量，对应 1/2
# 3 分支演示把 echo 当 next 变量名：执行 echo 节点（演示用，实际游戏不太会这么写）
node if p_pick [1:t_a,2:t_b,3:echo p_pick]
node end
```

```neon
id:ca
node start
# 切换音轨
@style bgm:storm.mp3
你打开门，雨中站着一个人。
node end
```

```neon
id:cb
node start
...（ADR 附录 A 后续块，本文件后续）...
```
````

## 完整事件流期望（输入序列 `["平静", "1"]`）

> ⚠️ **v0 vs v1 双版本**——v0 阶段 `node if` 走打桩（永远选第一分支）；v1-issue-6 完成后走 dispatcher 真求值（按输入值选分支）。**当前生效 = v0 打桩**。

### v0 事件流（`executor._execute_if` 走打桩路径）

```
LoadChapterCmd("chapters/chapter01.md")

# === id:start 块 ===
TextEvt("雨夜。", "narration")
TextEvt("雨声从破旧窗户的缝隙中渗入。", "narration")
TextEvt("你坐在窗边，听着雨声。", "narration")
DecoratorEvt("style", ["bgm:rain.mp3"])
PromptInputEvt("p_mood")
# GUI 发 UserInputCmd("平静")
TextEvt("平静", "echo")
# node end → NEXT=(None,"c1") 跳 c1

# === id:c1 块 ===
TextEvt("你听到门外传来两声敲门。", "narration")
PromptInputEvt("p_pick")
# GUI 发 UserInputCmd("1")
LogEvt("info", "条件打桩")
# node if 永远选第一分支 → NEXT=ref(t_a)=(None,"ca") 跳 ca

# === id:ca 块 ===
DecoratorEvt("style", ["bgm:storm.mp3"])
TextEvt("你打开门，雨中站着一个人。", "narration")
# node end → NEXT=null + id:ca 是普通 id（无 chapterYY）→ ChapterEndEvt

ChapterEndEvt
```

### v1 事件流（v1-issue-6 完成后，dispatcher 真求值）

```
LoadChapterCmd("chapters/chapter01.md")

# === id:start 块 === （同 v0）
...
PromptInputEvt("p_mood")
# GUI 发 UserInputCmd("平静")
TextEvt("平静", "echo")
# node end → NEXT=(None,"c1") 跳 c1

# === id:c1 块 ===
TextEvt("你听到门外传来两声敲门。", "narration")
PromptInputEvt("p_pick")
# GUI 发 UserInputCmd("1")
# v1-issue-6: dispatcher.eval_bool("p_pick == 1") → True
# 选 branch(value=1, target=t_a) → NEXT=(t_a, ca) 跳 ca

# === id:ca 块 === （同 v0）
...
ChapterEndEvt
```

### v1 真分支覆盖的输入序列

| 输入序列 | v0 走 | v1 走 | 说明 |
| --- | --- | --- | --- |
| `["平静", "1"]` | ca（永远第一分支）| ca | v0/v1 巧合一致 |
| `["平静", "2"]` | ca（永远第一分支）| **cb** | v1 真分支生效 |
| `["平静", "3"]` | ca（永远第一分支）| **echo p_pick** | v1 真分支生效（fallback 文本回显）|

**v1 验收脚本**（v1-issue-7 OPEN）：

```python
import io
from core.engine.executor import Executor, MemoryEventSink
from core.engine.interpreter import parse_chapter
from core.engine.ast_nodes import Story
from core.engine.expr import ExprDispatcher, CustomExecutor

state = ...  # GameState
custom = CustomExecutor(state)
dispatcher = ExprDispatcher(state, custom=custom)

story = parse_chapter(open("chapters/chapter01.md").read())
# 在 Executor 构造时注入 dispatcher（v1-issue-6 接入点）
exe = Executor(story, sink, dispatcher=dispatcher)
exe.run()

# 断言：输入 "2" 走 cb 而不是 ca
# 断言：TextEvt 序列里 cb 块的内容出现（"..." 在 ADR 附录 A 后续块）
```

## fixture 涵盖的语法点

| 语法点 | 出现位置 | 验收对应 issue |
| --- | --- | --- |
| 单 next 简写 | id:start `next:c1` | `#31` (v0-issue-9) |
| 多 next 完整声明 | id:c1 `t_a<-next:ca` | `#31` (v0-issue-9) |
| `id:start` 唯一 | 文件唯一 | `#30` (v0-issue-8) |
| 普通文本行 → TextEvt narration | "雨夜。" 三行 | `#32` (v0-issue-10) |
| `@style key:val` | id:start `@style bgm:rain.mp3` | `#34` (v0-issue-12) |
| `node in ->var` | `node in ->p_mood` | `#37` (v0-issue-14) |
| `node echo var` | `node echo p_mood` | `#37` (v0-issue-14) |
| `node if var [...]` 多元 | `node if p_pick [...]` | `#33` (v0-issue-11) / **v1-issue-6 真求值**|
| 分支项内 echo 占位 | `3:echo p_pick` | `#33` (v0-issue-11) |
| 整行注释 | `# 入口块：...` | `#29` (v0-issue-7) |
| node end + NEXT 跳转 | id:start 末尾 | `#37` (v0-issue-14) |
| 普通 `node end` 广播 chapter_end | id:ca 末尾 | `#39` (v0-issue-16) |

→ 相关：[[../40-issues/dashboard#v1-表达式子系统-prd-0002--adr-0003]] / [[../40-issues/dependency-graph]] / [[../20-architecture/state-machine#v1-v1-issue-6open-待实现]] / `#42` (v0-issue-19) / `#51` (v1-issue-7)

## 引用源

- ADR-0001 附录 A —— [[raw-docs/ADR-0001-v0-baseline-script-spec]]
- v0-issue-19 工程笔记 —— [[raw-docs/工程笔记/v0-issue-19-fixture.md]]
- ADR-0003 v1 表达式子系统 —— [[raw-docs/ADR-0003-v1-expression-subsystem §2 决策 4]]（`If.cond` kind 扩展）