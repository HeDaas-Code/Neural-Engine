# ADR-0001: 基础版脚本大合集规范（v0 Baseline Script Spec）

- **状态**：已通过（v0 实现基线）
- **日期**：2026-06-14
- **决策者**：项目所有者
- **范围**：剧情脚本 DSL 语法、运行时行为、进程间消息协议

本文档记录 v0 基础版的全部脚本语法、命名空间、运行时语义与进程间协议，作为未来实现的"真理之源"，**防止曲解**。任何后续实现遇到本文档未覆盖的场景，应回退到本文档并扩展。

---

## 1. 术语与命名空间

| 术语 | 含义 |
| --- | --- |
| **章节（Chapter）** | 一个 `.md` 剧本文件，包含一个或多个剧情节点代码块 |
| **剧情节点（Story Node）** | 一段独立的剧情内容单元，对应一个 ` ```neon ` 代码块 |
| **块（Block）** | 剧情节点代码块的全部内容（围栏 ` ```neon ` 起到 ` ``` ` 止） |
| **块内生命周期** | 一个块从 `node start` 起到 `node end` 止 |
| **命名空间 ID** | 节点的元数据标识符（`id:xxx`），用于跨块引用 |
| **变量命名空间** | 块内使用的标识符（next 变量、用户输入、临时值） |

**两个命名空间严格分离**：

- **ID 命名空间** —— `id:xxx`，**只能**出现在 `node start` 之前的元数据区
- **变量命名空间** —— 块内 `node start` 与 `node end` 之间的所有标识符

`c1` 和 `c11` 等标识符在变量命名空间内**没有本质区别**，都是普通变量名。

---

## 2. 章节结构

### 2.1 章节文件 = 一个 `.md` 文件

一个 `.md` 文件 = 一个章节。文件内可包含：

- 普通 Markdown 内容（标题、序言、角色介绍等，渲染为静态展示）
- 任意数量的 ` ```neon ` 代码块（每个对应一个剧情节点）

### 2.2 入口与出口

- **`id:start`** —— 章节入口标记，**全文件唯一**
  - 引擎加载章节后，先扫描所有 `neon` 块，找到 `id:start` 的块作为执行起点
  - 整份文件中 `id:start` 出现多次视为**语法错误**
- **`id:endX`（X 为自然数）** —— 章节出口标记
  - `end` 后必须接一个自然数 X
  - 单结局场景可只写 `id:end`（X 缺省视为 0），但语义上仍属 `endX` 家族
  - 多结局场景必须用 `end1`、`end2`... 区分
  - 同一章节内可声明任意数量的 `endX`

### 2.3 章节路由

`id:endX:chapterYY` —— end 节点内嵌路由目标，**冒号分隔**。

- 第一段 `endX` 是结局编号
- 第二段 `chapterYY` 是路由到的下一章节文件名（不含 `.md` 后缀）
- 引擎执行到 `endX` 时，**作为 `node end` 行为的一部分**广播 `route` 事件，事件 payload 包含目标章节名（从 `id:endX:chapterYY` 的第三段读取）。上层（章节加载器/状态机）订阅 `route` 事件，负责加载新章节文件。

> `route` **不是修饰器**，不是 `@route` 调用；它是 `endX` 节点执行 `node end` 时的内置副作用。

例：

````markdown
```neon
id:end1:chapter02
node start
雨夜过后，你推开门……
node end
```
````

当引擎执行到上面这个块：

1. 渲染"雨夜过后，你推开门……"
2. 执行 `node end` → 检查 `id:end1:chapter02` 的第三段
3. 广播 `{"event": "route", "target": "chapter02"}`

---

## 3. 块（剧情节点代码块）结构

### 3.1 代码块语法

````markdown
```neon
[元数据区]
node start
[块内执行区]
node end
```
````

- **元数据区**：`node start` 之前的所有非空行，仅允许 `id:xxx` 与 `xxx<-next:yyy` 形式的 next 变量声明
- **块内执行区**：`node start` 与 `node end` 之间的全部内容

### 3.2 元数据区

允许的语句：

```
id:xxx                      # 节点 ID（命名空间：ID）
next:yyy                    # 单 next 简写（无变量名）
xxx<-next:yyy               # 多 next 完整声明（命名空间：变量）
```

**`next` 与 `xxx<-next:yyy` 互斥**：单 next 写简写，多 next 必须带变量名。详见 §3.2.1 / §3.2.2 / §3.2.3。

**next 变量声明的语法**：

```
[变量名 <-] next : 节点ID
```

`<-` 左边是**可选的变量名**，有/无变量名代表两种语义。详见 §3.2.1（单 next 简写）与 §3.2.2（多 next 完整形式）。

#### 3.2.1 单 next 简写（无变量名）

```
next : 节点ID
```

- 块内**只有一条** next 声明时，**可以省略变量名**
- 语义：`NEXT = ref(节点ID)` —— 直接指向节点 ID
- 等价于"该节点只有一条出路"

例：

```neon
id:c1
next:c1          # 单 next 简写，NEXT = ref(c1)
node start
你坐在窗边。
node end
```

#### 3.2.2 多 next 完整形式（带变量名）

```
变量名 <- next : 节点ID
```

- 块内**有多条** next 声明时，**必须**带变量名
- 语义：`NEXT = ref(变量名)`，跳转时**经一次查表** 解析为节点 ID
- 变量名存在的意义是**消歧**——多条 next 用变量名区分

例：

```neon
id:c1
t_a <- next : ca
t_b <- next : cb
node start
你听到两声敲门。
node if p_pick [1:t_a, 2:t_b]
node end
```

> 关键不变量：
> - `<-` 冒号**右边**始终是节点 ID（ID 命名空间）
> - `<-` 冒号**左边**始终是变量名（变量命名空间），可省略
> - **单 next** 简写 = NEXT 直达 ID
> - **多 next** 必须 = NEXT 经变量名间接解析到 ID

#### 3.2.3 互斥规则

- 单 next 简写（`next:yyy`）与多 next 完整形式（`xxx<-next:yyy`）**互斥**：
  - 块内有 0 条或 1 条 next 声明时，可写简写（推荐）
  - 块内有 ≥2 条 next 声明时，必须全部带变量名
- 混合写法（如一条简写 + 一条完整）视为**语法错误**

### 3.3 块内执行区

允许的语句按前缀分类：

| 前缀 | 类型 | 例子 |
| --- | --- | --- |
| `node` | 控制流/执行语句 | `node start` / `node end` / `node in ->p` / `node echo p` / `node if cond[a,b]` / `node ce11` |
| `@` | 修饰器 | `@style bgm:rain.mp3` |
| 无前缀 | 普通文本行 | `你醒来时，窗外的雨声很清晰。` |

**`node` 语句集**：

| 语句 | 行为 |
| --- | --- |
| `node start` | 块内执行入口（必须为块内执行区首条非空行） |
| `node end` | 块内执行出口（必须为块内执行区末条非空行） |
| `node in ->var` | 暂停执行，等待 GUI 推送用户输入，存储到变量 `var` |
| `node echo var` | 输出变量 `var` 的当前值（推送给 GUI 显示） |
| `node next_id` | 显式跳转：`NEXT = next_id` |
| `node if cond[a,b]` | 二元条件：cond 成立则执行 a，否则执行 b；a/b 是 next 变量名 |
| `node if var [1:a,2:b,3:c]` | 多元条件：var 等于某值时执行对应语句 |
| `node [a?b:c]` | 简略二元：a 是**条件表达式**（可执行语句，含 `node xxx`），b/c 是**next 变量名**；a 真则 NEXT=ref(b)，否则 NEXT=ref(c) |

**简写规则**：

- `node ce11` 算 `NEXT = ref(ce11)`（即指向 ce11 的 next 变量表项）
- `node if` 列表里的每个分支项 `a`、`b`、`c` 实质是 `node a` 的**简写**——执行时把该项对应的 next 变量值赋给 NEXT
- **分支项内允许省略 `node` 前缀**：分支项可以写成 `node t_a` 的简略形式 `t_a`，也可以写成 `node echo p_pick` 的省略 `node` 前缀形式 `echo p_pick`
- **单独的 `ce11` 不算语句**，不能脱离 `node` 前缀出现在普通执行流（但在分支项列表里可以）

---

## 4. 修饰器（@ 语法）

### 4.1 基本约定

- 所有以 `@` 开头的非空行都是修饰器调用
- 修饰器作用域为**块级**（`node start` ... `node end` 之间），**不跨块继承**
- 同一块内多个修饰器遵循**竞争机制**：后到的同 key 修饰器覆盖前一个，直到遇到该 key 的**休止符**

### 4.2 修饰器语法

**调用**：`@修饰器名 key1:val1, key2:val2, key3`

- 修饰器接收一个 token 序列
- 解析方式由修饰器自身定义
- 逗号 `,` 分隔多个键值对，空格可有可无
- 裸 key（无冒号）也是合法 token（如 `@style bgm` 是关闭 BGM 的休止符）

**休止符**：`@修饰器名 key`（无参数或仅裸 key）

- 等价于清空该 key 的当前值
- 不同修饰器可定义不同的休止语义

### 4.3 多媒体样式需求

修饰器承担多媒体指令的转发，要求支持：

- 单曲循环（loop）
- 单曲结束（once）
- 播放片段（segment）
- 暂停/恢复（pause/resume）
- 切换音轨（cross-fade）

具体参数形式由各修饰器实现定义，**核心是修饰器能广播多媒体事件到 GUI**。

### 4.4 样式类比

修饰器设计类比 CSS：

- 修饰器 ≈ CSS 选择器/属性
- 块级作用域 ≈ CSS 块级作用域
- 竞争机制 ≈ 后定义覆盖前定义
- 休止符 ≈ CSS `unset`/`initial`

---

## 5. 命名空间与跳转机制（运行时）

### 5.1 NEXT 隐藏变量

引擎内部维护一个隐藏变量 `NEXT`，**类型是 next 变量表项的引用**（指向 `变量名 → 节点 ID` 映射表中的某一项）。

- `NEXT` 不是字符串
- `NEXT` 不是节点 ID
- `NEXT` 也不是变量名

`NEXT` 在执行跳转时通过它指向的表项一次性解析出节点 ID（变量名 → ID）。

### 5.2 NEXT 赋值时机

| 情况 | NEXT 引用 |
| --- | --- |
| 块内只有**一个** next 简写（无变量名，如 `next:c1`） | 隐式 `NEXT = ref(c1)`（直达 ID，无变量名） |
| 块内有**多个** next 完整声明（如 `t_a<-next:ca`） | `NEXT = null`（无默认跳转） |
| 执行 `node t_a` | `NEXT = ref(t_a)` |
| 执行 `node if cond[a,b]`（cond 真） | `NEXT = ref(a)` |
| 执行 `node if cond[a,b]`（cond 假） | `NEXT = ref(b)` |

> 跳转时：取 `NEXT` 指向表项的 ID 字段，跳到对应节点块。例如 `NEXT=ref(t_a)` → 取 "ca" → 跳到 `id:ca` 块。单 next 简写时 `NEXT=ref(c1)` 直接拿到 "c1"。

### 5.3 node end 的行为

执行 `node end` 时：

1. 若 `NEXT` 非空：查 next 变量表得到节点 ID，跳转
2. 若 `NEXT` 为空：检查当前块是否带 `id:endX:chapterYY` 标记
   - 是：广播 `route` 事件，payload 含 `chapterYY`
   - 否：广播 `chapter_end` 事件

---

## 6. 注释

块内注释以 `#` 开头，整行作为注释忽略。

````markdown
```neon
id:start
node start
# 这是整行注释（v0 支持）
node echo p_tall
node end
```
````

> v0 范围**只支持整行注释**（行首 `#`，整行忽略）。行尾注释（`node xxx # 注释`）v0 暂不实现，避免误导用户。

---

## 7. 进程间协议（数据总线）

### 7.1 进程模型

- **Engine 进程** —— 独立 Python 进程，负责脚本解析与执行
- **GUI 进程** —— 独立 PyQt6 进程，负责渲染
- 两进程通过 `multiprocessing.Queue`（数据总线）通信
- 所有消息均为 Python `dict`，统一 schema

### 7.2 消息方向

- **GUI → Engine**：命令（command）
- **Engine → GUI**：事件（event）

### 7.3 命令 schema

```python
# GUI 推送到 Engine
{"cmd": "load_chapter", "path": "chapters/chapter01.md"}   # 加载章节
{"cmd": "user_input", "value": "玩家输入的文本"}              # 用户输入回传
{"cmd": "shutdown"}                                          # 优雅退出
```

### 7.4 事件 schema

```python
# Engine 推送到 GUI
{"event": "text", "content": "渲染的文本", "style": "narration"}  # 显示文本
{"event": "prompt_input", "var": "p_tall"}                        # 等待用户输入
{"event": "decorator", "name": "style", "args": [...]}            # 修饰器广播
{"event": "route", "target": "chapter02"}                         # 章节路由
{"event": "chapter_end"}                                          # 章节结束
{"event": "log", "level": "info", "message": "..."}               # 日志
```

### 7.5 数据总线实现

- 双向各一个 `multiprocessing.Queue`
- 序列化：`json.dumps` / `json.loads`（保证跨进程可读、可调试）
- 心跳：v0 暂不实现

---

## 8. MVP 范围（v0 必须实现）

| 特性 | 实现状态 |
| --- | --- |
| `id:xxx` / `id:start` 解析 | 实现 |
| `id:endX` / `id:endX:chapterYY` 解析 | 实现 |
| `next:yyy` 单 next 简写 | 实现 |
| `xxx<-next:yyy` 多 next 完整声明 | 实现 |
| 单 next 简写时 NEXT 隐式 = ref(ID) | 实现 |
| 多 next 时 NEXT = null，待显式 | 实现 |
| `node start` / `node end` | 实现 |
| 普通文本行推送 GUI | 实现 |
| `node in ->var` 等待用户输入 | 实现 |
| `node echo var` 输出变量 | 实现 |
| `node next_id` 显式跳转 | 实现 |
| `node if cond[a,b]` 二元条件 | **打桩**（解析 + 占位执行，不真做流程控制） |
| `node if var [1:a,2:b,3:c]` 多元条件 | **打桩**（解析 + 占位执行） |
| `node [a?b:c]` 简略二元 | **打桩**（解析 + 占位执行） |
| 分支项内省略 `node` 前缀（如 `t_a` / `echo p_pick`） | **打桩**（解析即可） |
| `@xxx key:val` 修饰器调用 | **打桩**（解析 + 广播 `decorator` 事件，GUI 不真渲染） |
| `@xxx key` 休止符 | **打桩**（解析 + 广播休止事件） |
| 章节路由（`id:endX:chapterYY` 触发 `node end` 广播 `route` 事件） | **打桩**（广播 `route` 事件，GUI 忽略） |
| 注释（行首 `#`） | 实现 |

**v0 唯一跑通路径**：`node in ->p_tall` → 玩家输入 → `node echo p_tall` → `node end`

---

## 9. 项目结构（v0）

```
Neural Engine/
├── src/
│   ├── core/                       # 上下文：核心引擎
│   │   ├── CONTEXT.md
│   │   ├── engine/                 # 引擎进程
│   │   │   ├── __init__.py
│   │   │   ├── main.py             # 进程入口
│   │   │   ├── bus.py              # 数据总线
│   │   │   ├── protocol.py         # 消息 schema
│   │   │   ├── interpreter.py      # Markdown + neon 块解析
│   │   │   ├── ast_nodes.py        # AST 节点类型
│   │   │   └── executor.py         # 节点执行器
│   │   └── decorators/             # 修饰器实现
│   │       ├── __init__.py         # 注册表
│   │       └── style.py            # @style 打桩实现
│   ├── runtime/                    # 上下文：运行时（PyQt6 GUI）
│   │   ├── CONTEXT.md
│   │   ├── gui/                    # 窗口进程
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── window.py           # QMainWindow
│   │   │   ├── display.py          # 文本显示区
│   │   │   └── input.py            # 输入框
│   │   └── protocol.py             # 与 core 共用的协议定义
│   └── editor/                     # 上下文：剧情编辑器（v0 不实现）
│       └── CONTEXT.md
├── chapters/
│   └── chapter01.md                # 测试章节
├── docs/
│   ├── adr/
│   │   └── 0001-v0-baseline-script-spec.md   # 本文件
│   └── agents/                     # agent 协作说明
├── tests/
│   └── test_echo.md                # 单元测试用剧本
├── requirements.txt
└── README.md
```

---

## 10. 未来扩展（v0 暂不实现）

- 行尾注释
- 表达式求值（`p_tall + 1`、`p_tall == 1` 实际语义）
- 存档/读档
- 普通 Markdown 渲染
- 真实多媒体播放（`@style` 真实驱动音频/视频）
- 章节图（chapter 之间的 DAG 关系）
- 编辑器（节点图编辑）
- Web/移动端运行时

---

## 11. 关键不变量（任何实现都必须遵守）

1. **ID 与变量命名空间严格分离**——`id:xxx` 只能在 `node start` 之前
2. **块级作用域不跨块继承**——`@` 修饰器状态在 `node end` 时清空
3. **NEXT 是 next 变量表项的引用，不是字符串**——所有 `node xxx` 语法糖最终都把 NEXT 指向对应表项
4. **单 next 自动设 NEXT，多 next 必须显式**——避免歧义
5. **endX 同时承担结局标记 + 路由目标 + 玩家路径记录**——三者绑定，不可拆分
6. **数据总线消息一律 JSON dict**——便于调试与跨语言扩展
7. **单 next 简写（`next:yyy`）与多 next 完整（`xxx<-next:yyy`）互斥**——块内 0/1 条可用简写，≥2 条必须带变量名；混用视为语法错误
8. **v0 仅支持整行注释（行首 `#`）**——行尾注释 / 块注释暂不支持
9. **`<-` 冒号右边是 ID 命名空间，左边是变量命名空间**——单 next 简写时左边省略但语义上直达 ID
10. **分支项内允许省略 `node` 前缀**——`node if cond[1:t_a, 2:echo p]` 合法，等价于 `node t_a` / `node echo p`

---

## 附录 A：v0 全语法演示剧本（chapter01）

> 规范执行样例，**也是 v0 引擎的官方 fixture**。
> 演示 v0 规范支持的全部脚本语法：元数据、单/多 next、`node start`/`end`、文本行、`node in`/`echo`、多元 `node if`、`@style` 修饰器（含休止符）、`id:endX:chapterYY` 路由、`id:endX` 普通结局、整行注释。

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
# 休止符：@style 裸 key 等价于清空 bgm
@style bgm
你没有开门。雨声渐小。
node end
```

```neon
id:end1:chapter02
# 路由标记：endX 后第三段是目标章节名
# node end 时广播 route 事件，payload 含 chapter02
node start
故事停在这里。
node end
```

```neon
id:end2
# 普通结局：endX 后无章节名
# node end 时 NEXT=null，广播 chapter_end 事件
node start
测试结束。
node end
```
````

**剧本覆盖检查清单**：

| 语法 | 演示位置 |
| --- | --- |
| `id:xxx` 普通 ID | `id:start` / `id:c1` / `id:ca` / `id:cb` |
| `next:yyy` 单 next 简写 | 第一个块 |
| `xxx<-next:yyy` 多 next 完整形式 | `id:c1` 块 |
| `node start` / `node end` | 所有块 |
| 普通文本行（无前缀） | 多处 |
| 整行注释 `#` | 元数据区 + 块内 |
| `node in ->var` | `start` / `c1` 块 |
| `node echo var` | `start` 块 |
| 多元 `node if var [1:a,2:b,3:c]` | `c1` 块 |
| 分支项 `3:echo p_pick`（含 echo 简写） | `c1` 块 |
| `@style key:val` 修饰器 | `start` / `ca` 块 |
| `@style key` 休止符 | `cb` 块 |
| `id:endX:chapterYY` 路由 | `id:end1:chapter02` |
| `id:endX` 普通结局 | `id:end2` |
