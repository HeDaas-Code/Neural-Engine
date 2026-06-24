# Neural Engine 功能路线图

> **日期**：2026-06-23
> **作者**：哈尼斯（独立第三方审计）
> **基线**：v1 重构完工（PR #66 已合并），211 tests passed

---

## 1. 现阶段代码能力总览

### 1.1 解析器（interpreter.py）

| 能力 | 语法 | 状态 |
|---|---|---|
| neon 围栏提取 | ` ```neon ... ``` ` | ✅ |
| 块骨架（start/end 边界） | `node start` / `node end` | ✅ |
| 元数据区 id 解析 | `id:xxx` / `id:start` / `id:endX` / `id:endX:chapterYY` | ✅ |
| next 声明（单/多） | `next:yyy` / `var ← next : yyy` | ✅（← 和 <- 双兼容） |
| 块内文本行 | 普通文字 → `Text(content)` | ✅ |
| node in | `node in → var` | ✅（→ 和 -> 双兼容） |
| node echo | `node echo var` / `node echo var + 文本` | ✅（v1 新增拼接） |
| node next_id | `node xxx` → `NextId(target_id)` | ✅ |
| node if（值匹配） | `node if var [1:a, 2:b]` | ✅ |
| node if（表达式二元） | `node if pick == 1 [a, b]` | ✅（v1 新增） |
| node if（表达式多元） | `node if pick == 1 [1:a, 2:b]` | ✅（v1 新增） |
| node if（简略二元） | `node [expr?a:b]` | ✅ |
| 修饰器调用 | `@style key:val, key2:val2` | ✅ |
| 修饰器休止符 | `@style key` | ✅ |
| 整行注释 | `# 注释` | ✅ |

### 1.2 执行器（executor.py）

| 能力 | 状态 | 说明 |
|---|---|---|
| Text 输出 | ✅ | `TextEvt(content, style="narration")` |
| In 输入 | ✅ | `PromptInputEvt` → 等待 `UserInputCmd`，自动 int 转换 |
| Echo 变量输出 | ✅ | `TextEvt(content=vars[var])` |
| Echo 拼接输出 | ✅（v1） | parts 依次取值/字面量拼接 |
| NextId 跳转 | ✅ | `NEXT = (None, target_id)` |
| If 值匹配（v0 兼容） | ✅ | `cond=("var", name)` → 按值选 branch |
| If 表达式求值 | ✅（v1） | `cond=("expr", "pick==1")` → dispatcher.eval → bool → branch |
| 修饰器广播 | ✅ | `DecoratorEvt` 广播到 sink |
| 块级作用域清空 | ✅ | `run_block` 入口 `_deco_state.clear()` |
| NEXT 三阶段 | ✅ | 声明 → 竞争 → end 锁定 |
| 跨块跳转 | ✅ | `_execute_block_loop` 循环 |
| RouteEvt 章节路由 | ✅ | `id:endX:chapterYY` → `RouteEvt(target)` |
| ChapterEndEvt | ✅ | `id:endX`（无 chapter）→ `ChapterEndEvt` |
| target_id 校验 | ✅ | 构造时一次性扫描所有目标 |

### 1.3 表达式子系统（expr/）

| 能力 | 状态 | 说明 |
|---|---|---|
| simpleeval 求值 | ✅ | 原生 Python 语法 |
| 变量注入 | ✅ | `state.vars` 实时同步 |
| 内置函数白名单 | ✅ | `int/str/float/bool/len/min/max/abs/round` |
| fallback 机制 | ✅ | `CustomExecutor.eval_fallback` |
| 自定义函数注册 | ✅ | `CustomExecutor.register_function` |
| 自定义表达式注册 | ✅ | `CustomExecutor.register_evaluator`（正则匹配） |
| 沙箱安全 | ✅ | 白名单函数 + simpleeval AST 限制 |

### 1.4 进程间协议（protocol.py + bus.py）

| 消息 | 方向 | 状态 |
|---|---|---|
| `LoadChapterCmd` | GUI→Engine | ✅ |
| `UserInputCmd` | GUI→Engine | ✅ |
| `ShutdownCmd` | GUI→Engine | ✅ |
| `TextEvt` | Engine→GUI | ✅ |
| `PromptInputEvt` | Engine→GUI | ✅ |
| `DecoratorEvt` | Engine→GUI | ✅ |
| `RouteEvt` | Engine→GUI | ✅ |
| `ChapterEndEvt` | Engine→GUI | ✅ |
| `LogEvt` | Engine→GUI | ✅ |
| JSON 序列化 | 双向 | ✅ |
| multiprocessing.Queue | 双向 | ✅ |
| queue.Queue（测试注入） | 双向 | ✅ |

### 1.5 GUI（runtime/gui/main.py）

| 能力 | 状态 |
|---|---|
| CLI 占位渲染（路径 B） | ✅ |
| headless 降级 | ✅ |
| PyQt6 窗口（路径 A） | ❌ 推迟到 v2 |

### 1.6 测试覆盖

| 维度 | 数量 |
|---|---|
| 总测试数 | 211 |
| 单元测试 | ~180 |
| 端到端测试 | 3 文件（v0 echo path + v0 chapter01 + v1 e2e） |
| 不变量守护 | 10 条（§11） |
| MVP 表 | 18 条（§8） |

---

## 2. 未实现 / 已知限制

### 2.1 ADR-0004 偏差（阶段一已修复）

| # | 偏差 | 影响 / 修复状态 |
|---|---|---|
| D1 | 不加 `bool_expr` kind，用 expr + branches 数量判断 | ✅ **已修复（2026-06-24）**：新增 BOOL_EXPR_KIND + 防御性断言 |
| D2 | G5 修饰器结构化参数未实现 | ✅ **已修复（2026-06-24，MVP）**：interpreter 支持 `[item1,item2,...]` 顶层列表 |
| D4 | TypeError 捕获未收窄到 NameNotDefined | ✅ **已修复（2026-06-24，路径 A）**：收窄到 InvalidExpression 子类 + 字符串过滤 fallback |
| D5 | simpleeval 版本未锁定 | ✅ **已修复（2026-06-24）**：pyproject.toml 锁定 `simpleeval==1.0.7` |

### 2.2 设计中标注"远期"的

| # | 特性 | 来源 |
|---|---|---|
| F4 | `@LLM-jud(...)` 装饰器框架 | ADR-0004 §4 阶段 5 |
| G5 | 修饰器结构化参数 `text:[rgb:red,Px:12]` | ADR-0004 §4 阶段 4 |

### 2.3 v0 遗留

| 特性 | 说明 |
|---|---|
| PyQt6 GUI 窗口 | v0-issue-18 路径 A，推迟到 v2 |
| 真实多媒体播放 | `@style bgm:rain.mp3` 只广播事件，不真播放 |
| 章节图 DAG | 章节间路由只是广播 `RouteEvt`，无上层加载器 |
| 存档/读档 | 无 |
| 行尾注释 | v0 只支持整行注释 |

---

## 3. 下一步功能分析

按优先级和依赖关系排列。

### P0：核心体验闭环（让引擎能真正"玩"）

#### 3.1 PyQt6 GUI 窗口（v2-issue-1）

**痛点**：当前只有 CLI print，无法验证视觉体验。

**范围**：
- `QMainWindow` + 文本显示区（QTextEdit）+ 输入框（QLineEdit）
- 订阅 EngineBus 事件 → 渲染
- 用户输入 → `UserInputCmd` 推送
- `importlib.util.find_spec("PyQt6")` 切换 CLI/PyQt6

**依赖**：无
**估时**：2-3 天
**验收**：`python3 -m core.engine.main chapters/chapter01_v1.md` 弹出窗口，文本正常显示，输入框可交互。

#### 3.2 章节加载器（v2-issue-2）

**痛点**：`RouteEvt` 广播后无人处理，跨章节跳转实际不工作。

**范围**：
- 上层 `ChapterManager` 订阅 `RouteEvt`
- 收到 `route` → 加载新章节 `.md` → 新建 Executor → run
- 章节图元数据（可选：`chapters/index.yaml`）

**依赖**：无
**验收**：`chapter01.md` → `id:end1:chapter02` → 自动加载 `chapters/chapter02.md`。

#### 3.3 存档/读档系统（v2-issue-3）

**痛点**：玩家进度无法保存。

**范围**：
- `GameState` 序列化 → JSON 文件
- `SaveCmd` / `LoadCmd` 新增命令
- 引擎启动时检查存档 → 恢复 `state.vars` + 当前块位置

**依赖**：3.2（章节加载器，需要恢复章节位置）
**验收**：游戏中途保存 → 重启 → 读档 → 恢复到保存前状态。

### P1：DSL 表达力扩展

#### 3.4 修饰器结构化参数（G5 补完）

**痛点**：`@style text:[rgb:red,Px:12],bgm:start:1.mp3` 无法解析。

**范围**：
- `parse_decorator` 扩展：参数值支持 `[item1,item2,...]` 列表语法
- `DecoratorCall.args` 从 `tuple[str,...]` 扩展为支持嵌套结构
- `DecoratorEvt` 序列化适配

**依赖**：无
**验收**：`@style text:[rgb:red,Px:12]` 正确解析为 `{"text": ["rgb:red", "Px:12"]}`。

#### 3.5 变量持久化与跨块传递

**痛点**：当前 `GameState.vars` 在块间保持，但无显式声明机制。`node in` 输入的变量是隐式全局的。

**范围**：
- `global` / `local` 变量声明语法（可选）
- 或：保持隐式全局，但在文档中明确语义

**依赖**：无
**风险**：改动小，主要是设计决策。

#### 3.6 表达式系统增强

**痛点**：`BUILTIN_FUNCS` 只有 8 个基础函数，缺随机、字符串操作等。

**范围**：
- `randint(min, max)` — 受控随机
- `clamp(val, lo, hi)` — 范围裁剪
- `upper(s)` / `lower(s)` — 字符串变换
- `contains(container, item)` — 包含判断
- simpleeval 版本锁定（D5 偏差修复）

**依赖**：无
**验收**：`node if randint(1, 6) == 6 [lucky, unlucky]` 正确求值。

### P2：LLM 集成（远期）

#### 3.7 `@LLM-jud` 装饰器框架（F4）

**痛点**：`node if @LLM-jud(P-text, 是否积极情感)[0:n1, 1:n2]` 无法求值。

**范围**：
- `LLMJudDecorator` 类：调用外部 LLM API
- `ExprDispatcher` 集成：表达式中的 `@LLM-jud(...)` 识别 → 装饰器调用 → 结果注入
- 异步处理：LLM 调用是 I/O，不阻塞引擎循环
- 缓存层：相同输入复用结果

**依赖**：3.6（表达式系统增强）
**风险**：API key 管理、延迟、成本。
**验收**：`node if @LLM-jud(p_mood, 是否积极情感)[0:t_a, 1:t_b]` 正确调用 LLM 并分支。

#### 3.8 LLM 驱动的 NPC 对话

**痛点**：当前 echo 只能输出预设文本，无法动态生成。

**范围**：
- `node llm prompt` 新节点类型
- 上下文注入：state.vars + 对话历史
- 人格模板系统（与 Mortis 框架对接？）

**依赖**：3.7
**风险**：与 Mortis 的集成边界需要明确。

### P3：工具链与生态

#### 3.9 剧情编辑器

**痛点**：手写 Markdown + neon 块容易出错。

**范围**：
- 节点图 GUI（节点 = 块，边 = next 跳转）
- 实时预览引擎执行
- 语法高亮 + 自动补全
- `src/editor/` 已有占位

**依赖**：3.1（PyQt6 GUI 基础）
**估时**：1-2 周

#### 3.10 章节图可视化

**痛点**：多章节路由关系不可视。

**范围**：
- `chapters/index.yaml` → DOT 图
- 或：扫描所有 `.md` 文件的 `id:endX:chapterYY` → 自动生成 DAG

**依赖**：3.2（章节加载器）

#### 3.11 测试覆盖率提升

**痛点**：4 个 internal helper 缺边界单测。

**范围**：
- `EngineBus._drain` / `_close_queue` 边界测试
- `Executor._emit_decorator` / `_validate_target_ids` 边界测试
- `main._try_spawn_gui` mock 测试

**依赖**：无

---

## 4. 推荐执行顺序

```
v2 阶段 1：核心体验闭环
  ├─ 3.1 PyQt6 GUI 窗口
  ├─ 3.2 章节加载器
  └─ 3.3 存档/读档
        ↓
v2 阶段 2：DSL 表达力
  ├─ 3.4 修饰器结构化参数（G5 补完）
  ├─ 3.6 表达式系统增强
  └─ 3.5 变量持久化语义明确
        ↓
v2 阶段 3：LLM 集成（可选）
  ├─ 3.7 @LLM-jud 装饰器
  └─ 3.8 LLM NPC 对话
        ↓
v2 阶段 4：工具链
  ├─ 3.9 剧情编辑器
  ├─ 3.10 章节图可视化
  └─ 3.11 测试覆盖率
```

**建议**：先做 3.1（PyQt6）+ 3.2（章节加载器），让引擎能真正跑起来。这两个做完后，后续所有功能都能在真窗口里验证，迭代效率大幅提升。

---

*哈尼斯 · 2026-06-23*
