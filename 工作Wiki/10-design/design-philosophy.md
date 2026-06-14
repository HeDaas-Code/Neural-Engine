# 10 · 设计哲学

> **TL;DR**：四个根原则决定了 Neural Engine 看起来"古怪"的那些点——**命名空间分离 / 引用即跳转 / CSS 化的修饰器 / DSL 即规范**。

## 原则 1 · 命名空间严格分离

**为什么**：剧本里既要有"节点 id"（跨块跳转用）又要有"变量名"（块内临时值）。混在一起就会出现"id `c1` 被局部变量 shadow"的歧义。

**怎么做**（[ADR-0001 §1](raw-docs/ADR-0001-v0-baseline-script-spec)，§11 不变量 #1）：
- `id:xxx` **只能**出现在 `node start` 之前的元数据区
- `node start` 与 `node end` 之间**只能**用变量名（next 变量 / 用户输入 / 临时值）
- 解析器在 `node start` 后遇到 `id:xxx` 必须报错

**结果**：可以用 `c1` 和 `c11` 当变量名——它们和节点 id 在不同命名空间，互不干扰。

→ **命名空间语义细节**：见 [[namespace-semantics]]。

## 原则 2 · 引用即跳转（NEXT 不是字符串）

**为什么**：如果 `NEXT` 是 `"c1"` 这种字符串，相当于把"目标节点"硬编码进了执行路径；分支、修饰器、跨章节路由每加一种跳转方式都得改 executor。

**怎么做**（[ADR-0001 §5.1](raw-docs/ADR-0001-v0-baseline-script-spec)，§11 不变量 #3）：
- NEXT 是 **next 变量表项的引用**，类型 `tuple[str | None, str | None]`——`(var_name, node_id)`
- 跳转时一次性查表取 ID
- 单 next 简写时 `NEXT = (None, "c1")`（无变量名但直达 ID）
- 多 next 时 `NEXT = null`，等显式 `node t_a` 才赋值
- **禁止 `NEXT = "xxx"` 字面量赋值**——有自动化 grep 守护（v0-issue-20 §11 #3）

**结果**：分支项 `1:t_a, 2:t_b, 3:echo p_pick` 都走"取 NEXT 引用 → 查表"的同一条跳转路径，分支逻辑零特例。

## 原则 3 · CSS 化的修饰器

**为什么**：剧情脚本里"BGM 切换 / 立绘淡入 / 字幕样式"这种横切关注点很多，OOP 继承或显式语句会爆炸。

**怎么做**（[ADR-0001 §4](raw-docs/ADR-0001-v0-baseline-script-spec) + §11 不变量 #2）：
- `@修饰器名 key:val` —— 类似 CSS `property: value`
- 块级作用域（`node start`...`node end` 之间）
- 竞争机制（后到覆盖前到）
- 休止符 `@修饰器名 key`（裸 key，无冒号）—— 类似 CSS `unset`
- 未来扩展 `@voice` `@bg` 等只需在 `core/decorators/` 注册 handler，**executor 零修改**

**结果**：作者写剧本时像写 CSS，runtime 实现时按注册表分发，多媒体团队和引擎团队解耦。

## 原则 4 · DSL 即规范

**为什么**：剧情脚本是创作者面对的"用户界面"。DSL 不能有"实现定义行为"——要么规范写明，要么报错。

**怎么做**（[ADR-0001 §3.3](raw-docs/ADR-0001-v0-baseline-script-spec) + §6 + 不变量 #8）：
- ADR-0001 §8 是**实现完成标准**的权威列表
- 块内只允许 ADR §8 表中出现的语句；未识别语句（`print` / `goto` / `set`）直接 SyntaxError（v0-issue-10）
- 行内注释（`node xxx # 注释`）v0 不支持，**整个语句视为非法**

**结果**：测试可以断言"任何未列在 §8 表中的语句都必须报错"，DSL 行为可枚举、可测试、可文档化。

## 取舍对照（决策可见）

| 取舍 | 选了 | 放弃的 | 理由 |
| --- | --- | --- | --- |
| DSL 关键字 | 中文 | 英文 | 中文创作者优先；变量名仍英文保持 IDE 友好 |
| 单 next 简写 | 允许 | 必须完整 | `c1` 这种简单节点写 `next:c1` 比 `t_a<-next:c1` 友好 |
| `node if` 实现 | v0 打桩 | 真做条件 | v0 路径不需要条件；先跑通 + 不掩盖语法错误 |
| 跨进程通信 | multiprocessing.Queue | 共享内存 | 调试可读、跨语言、未来可换 Web |
| GUI 实现 | 三路径 | 强装 PyQt6 | v0 不强 GUI 依赖；CI 跳过 GUI 测试 |
| 注释 | 只整行 `#` | 行尾 + 块注释 | 行尾注释的边界条件太多，v0 不引入 |

→ 相关：[[terminology]] / [[../20-architecture/state-machine]] / [[../20-architecture/multi-process]]