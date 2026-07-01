# Neural Engine 差距分析

> **日期**：2026-07-01
> **作者**：哈尼斯（独立第三方审计）
> **基线**：v2-p0 完工，467 tests，3500 行源码 + 7900 行测试
> **目标**：评估离 Hacknet 式交互游戏 / 最小 AVG 引擎的差距

---

## 1. 现阶段能力总览（v2-p0 完工后）

### 1.1 已落地能力

| 层 | 能力 | 实现状态 |
|---|---|---|
| **DSL 解析** | neon 代码块提取、块骨架、元数据 id、next 声明（← / <-）、文本行、node in（→ / ->）、node echo（含拼接）、node next_id、node if（值匹配 + 表达式求值）、修饰器（@style / @bgm）、整行注释 | ✅ 全部 |
| **表达式** | simpleeval 沙箱求值、变量注入、内置函数 13 个（int/str/float/bool/len/min/max/abs/round + randint/clamp/upper/lower/contains）、fallback 正则匹配、自定义函数注册 | ✅ 全部 |
| **执行器** | Text 输出、In 输入（int 自动转换）、Echo 输出（含拼接）、NextId 跳转、If 真求值（二元 + 多元）、修饰器广播、NEXT 三阶段、块级作用域、跨块跳转、RouteEvt 章节路由、ChapterEndEvt、target_id 校验、SaveCmd/LoadCmd 拦截 | ✅ 全部 |
| **进程协议** | 5 Cmd（LoadChapter / UserInput / Shutdown / Save / Load）+ 8 Evt（Text / PromptInput / Decorator / Route / ChapterEnd / Log / SaveAck / LoadAck）+ JSON 序列化 + multiprocessing.Queue | ✅ 全部 |
| **GUI** | PyQt6 MainWindow（QTextEdit + QLineEdit + QPushButton）、PyQt6Sink / PyQt6InputSink 适配、CLI 降级、find_spec 探测 | ✅ 骨架 |
| **章节管理** | ChapterManager 跨章节路由、load_chapter_safe 路径校验、shared_state 跨章节状态共享 | ✅ |
| **存档** | SaveManager save/load/list/delete、GameState.to_dict/from_dict、slot 路径穿越防护 | ✅ |
| **装饰器钩子** | @style / @bgm 注册 + dispatch 框架、kind 字段区分 call/stop | ✅ 骨架（不真渲染） |
| **音频/视频** | AudioManager / VideoPlayer 占位类 | ❌ 空壳 |
| **测试** | 467 tests、10 不变量、18 MVP 表、v0/v1/v2 端到端 | ✅ |

### 1.2 未落地 / 空壳

| 模块 | 状态 | 说明 |
|---|---|---|
| AudioManager | 空壳 | 只有类名，无 play/stop |
| VideoPlayer | 空壳 | 只有类名，无 play |
| @style 渲染 | 记录不渲染 | 写入 `_LAST_STYLE` 字典，PyQt6 不读 |
| @bgm 播放 | 记录不播放 | 写入 `_LAST_BGM` 列表，AudioManager 不调 |
| 存档恢复执行位置 | ❌ | `current_block_id` 已存但无恢复跑路径 |
| 剧情编辑器 | ❌ | `src/editor/` 空目录 |
| LLM 集成 | ❌ | 无 |

---

## 2. 目标 A：Hacknet 式游戏引擎

### 2.1 Hacknet 是什么

Hacknet 是一款**终端模拟黑客游戏**，核心体验：
- 玩家在模拟终端里输入命令（`scan`、`connect`、`probe`、`hack`、`decrypt`）
- 文件系统浏览（`ls`、`cd`、`cat`、`rm`）
- 程序执行（`PortHack`、`crack`）
- 邮件系统（NPC 发任务、剧情推进）
- 实时时钟 + 任务倒计时
- 节点图（网络拓扑可视化）
- 富文本终端输出（彩色、进度条、ASCII art）

**本质**：不是传统 AVG，是**命令行交互 + 剧情脚本驱动 + 实时模拟**的混合体。

### 2.2 能力差距矩阵

| 能力域 | Hacknet 需求 | Neural Engine 现状 | 差距 |
|---|---|---|---|
| **终端 UI** | 滚动终端、命令行输入、历史回溯、Tab 补全 | QTextEdit + QLineEdit | ⚠️ 有基础控件，缺终端行为模拟 |
| **命令解析** | 自由文本命令 → 解析 → 执行 | 无（只有 `node in` 等待输入） | 🔴 完全缺失 |
| **文件系统模拟** | 虚拟 FS（ls/cd/cat/rm/cp/mkdir） | 无 | 🔴 完全缺失 |
| **网络节点模拟** | IP 地址、端口、连接拓扑 | 无 | 🔴 完全缺失 |
| **进程/程序模拟** | PortHack / crack / monitor | 无 | 🔴 完全缺失 |
| **邮件系统** | NPC 邮件 → 任务触发 | 无 | 🔴 完全缺失 |
| **实时时钟** | 计时器、倒计时任务 | 无 | 🔴 完全缺失 |
| **剧情脚本** | 节点 → 条件分支 → 结局 | ✅ 有（neon DSL） | ✅ 核心能力已具备 |
| **变量系统** | 全局状态、任务进度 | ✅ `state.vars` | ✅ |
| **条件分支** | 检查任务完成 → 开支线 | ✅ `node if expr` | ✅ |
| **跨章节路由** | 任务完成 → 新章节 | ✅ `RouteEvt` + `ChapterManager` | ✅ |
| **存档/读档** | 保存进度 | ✅ `SaveManager` | ✅ |
| **富文本输出** | 彩色文本、ASCII art、进度条 | ❌ 只有纯文本 `TextEvt` | 🔴 缺失 |
| **NPC 交互** | NPC 独立行为、实时回复 | ❌ 无 NPC 概念 | 🔴 缺失 |
| **多结局** | 支线 + 结局路由 | ✅ `id:endX:chapterYY` | ✅ |
| **音频** | BGM + 音效 | ⚠️ 钩子有，不播放 | ⚠️ 接线即用 |
| **成就/统计** | 任务完成记录 | ❌ | 🔴 缺失 |

### 2.3 差距总结

**已具备**（约 30%）：剧情脚本引擎的核心——DSL 解析、条件分支、变量系统、跨章节路由、存档。这是 Hacknet 的"剧情骨架"层。

**完全缺失**（约 70%）：

1. **终端交互层**（Hacknet 的核心体验）
   - 命令解析器：自由文本 → cmd + args
   - 命令注册表：`scan` / `connect` / `probe` / `ls` / `cat` ...
   - 命令历史 + Tab 补全
   - 终端输出格式化（颜色、对齐、ASCII art）

2. **世界模拟层**
   - 虚拟文件系统（树结构 + 文件内容）
   - 虚拟网络（节点 + 端口 + 连接拓扑）
   - 进程模拟（黑客程序 + 防火墙 + 计时器）

3. **实时系统**
   - 时钟 + 计时器事件
   - 异步任务（NPC 延迟回复、后台破解进度）

4. **UI 增强**
   - 富文本渲染（HTML/ANSI color）
   - 节点图可视化（网络拓扑）
   - 分屏（终端 + 文件浏览器 + 邮件）

### 2.4 从 Neural Engine 到 Hacknet 的路径

Neural Engine 的 neon DSL 是**剧情节点流**，Hacknet 是**命令驱动**。两者的架构差异：

```
Hacknet 架构:
  玩家输入命令 → 命令解析器 → 世界状态变更 → 终端输出 + 剧情检查
                                                    ↓
                                              剧情触发 → neon 节点流

Neural Engine 架构:
  neon 节点流 → TextEvt → 玩家读
  node in → PromptInputEvt → 玩家输入 → 继续节点流
```

**关键差异**：Hacknet 是**玩家驱动**（玩家主动输入命令触发剧情），Neural Engine 是**脚本驱动**（脚本控制流程，玩家只在 `node in` 时被动响应）。

**桥接方案**：在 Executor 和 GUI 之间加一个**命令层**：

```
玩家输入 → CommandParser → 
  ├─ 注册命令（scan/connect/ls...）→ WorldState 变更 → TerminalOutput
  └─ 剧情命令 → 转为 UserInputCmd → Executor 处理
```

这意味着：
1. GUI 侧需要一个终端模拟器（替代当前的 QTextEdit + QLineEdit）
2. 需要一个 CommandRegistry + WorldState 模块
3. neon DSL 的 `node in` 可以复用——但输入值来自命令解析器而非裸输入

---

## 3. 目标 B：最小 AVG 游戏引擎

### 3.1 AVG 引擎的核心需求

参考 Ren'Py / KiriKiri / TyranoBuilder 等成熟 AVG 引擎：

| 能力域 | 成熟 AVG 标准 | Neural Engine 现状 | 差距 |
|---|---|---|---|
| **剧本格式** | 纯文本/脚本标签 | Markdown + neon DSL | ✅ 有自己的方式，够用 |
| **文本显示** | 逐字/逐行打字机效果、名字+对话框 | 纯文本追加到 QTextEdit | ⚠️ 缺打字机、对话框 |
| **角色立绘** | 多图层、表情切换、位置移动 | 无 | 🔴 完全缺失 |
| **背景图** | 场景切换、过渡动画 | 无 | 🔴 完全缺失 |
| **BGM/音效** | 播放/停止/淡入淡出 | 钩子有，不播放 | ⚠️ 接线即用 |
| **语音** | 语音文件播放 | 无 | 🔴 缺失 |
| **选项菜单** | 多选项按钮、悬停效果 | `node in` 输入数字 | ⚠️ 能用但体验差 |
| **存档/读档** | 多槽位+截图+时间戳 | ✅ JSON 存档 | ⚠️ 缺截图+时间戳 |
| **CG 图鉴** | 解锁/浏览 | 无 | 🔴 缺失 |
| **历史回看** | 已读文本回看 | 无 | 🔴 缺失 |
| **跳过/快进** | 已读自动跳过 | 无 | 🔴 缺失 |
| **设置菜单** | 文字速度/音量/全屏 | 无 | 🔴 缺失 |
| **过渡效果** | 淡入淡出/溶解/滑动 | 无 | 🔴 缺失 |
| **变量+条件分支** | 全局变量、if 分支 | ✅ | ✅ |
| **跨章节路由** | 章节跳转 | ✅ | ✅ |
| **多结局** | 结局路由 | ✅ | ✅ |

### 3.2 差距总结

**已具备**（约 35%）：剧本解析、变量系统、条件分支、章节路由、存档——AVG 的"逻辑层"基本到位。

**缺失**（约 65%）：

1. **视觉层**（AVG 的核心体验）
   - 角色立绘系统（多图层 + 表情 + 位置）
   - 背景图系统（场景切换 + 过渡动画）
   - 对话框 UI（名字 + 文本框 + 打字机效果）
   - 选项按钮 UI（替代裸输入数字）

2. **音频层**
   - AudioManager 真实现（BGM 播放/停止/淡入淡出）
   - 音效播放（SE）
   - 语音播放（Voice）

3. **UX 层**
   - 历史文本回看
   - 跳过/快进
   - 设置菜单（文字速度/音量/全屏）
   - CG 图鉴

4. **存档增强**
   - 截图
   - 时间戳
   - 自动存档

---

## 4. 两个目标的对比

| 维度 | Hacknet 式 | 最小 AVG |
|---|---|---|
| 离现状的距离 | ~70% 需新建 | ~65% 需新建 |
| 现有能力复用率 | ~30% | ~35% |
| 新建模块复杂度 | 高（终端模拟 + 世界模拟） | 中（立绘 + 对话框 + 音频） |
| 最大缺口 | 命令解析 + 世界模拟 | 立绘 + 对话框 + 音频 |
| 工期估算 | 3-4 周 | 2-3 周 |
| 市场参考 | Hacknet, Uplink, Midnight Protocol | Ren'Py, KiriKiri |

**关键观察**：两个目标的"逻辑层"都已完成（剧本 + 变量 + 分支 + 路由 + 存档）。差异全在"表现层"和"交互层"。

---

## 5. 推荐路线

### 路线 A：先做 AVG（推荐）

**理由**：
1. Neural Engine 的 neon DSL 本质就是 AVG 脚本流，架构对齐
2. AVG 的视觉层（立绘 + 对话框 + 音频）是 Hacknet 终端模拟的前置依赖
3. 工期更短（2-3 周），能更快看到可玩的东西
4. 做完 AVG 后，再叠加命令层 + 世界模拟 → Hacknet 式

### 路线 B：直奔 Hacknet

**理由**：
1. 目标明确，不会陷入 AVG 的 UI 细节泥潭
2. 终端 UI 比立绘系统简单（QTextEdit 就能跑）
3. 但世界模拟 + 命令解析是全新架构，风险高

### 路线 C：AVG 最小闭环 → Hacknet 扩展

**阶段 1**（1 周）：AVG 最小闭环
- 对话框 UI（名字 + 文本 + 打字机）
- 立绘占位（彩色矩形 + 名字）
- AudioManager 真实现（pygame.mixer）
- 选项按钮 UI

**阶段 2**（1 周）：存档增强 + UX
- 存档截图 + 时间戳
- 历史回看
- 跳过/快进
- 设置菜单

**阶段 3**（2 周）：Hacknet 扩展
- 终端模拟器（替代对话框）
- 命令解析器 + CommandRegistry
- 虚拟文件系统
- 虚拟网络拓扑
- 实时时钟 + 异步任务

**总工期**：4 周

---

## 6. 如果只做最小 AVG，需要做什么

按优先级排列，每一项都是可独立交付的：

### P0：让游戏能看能玩（1 周）

| # | 任务 | 改动文件 | 说明 |
|---|---|---|---|
| 1 | 对话框 UI | `runtime/gui/pyqt6_main.py` | 名字标签 + 文本框 + 打字机效果，替代裸 QTextEdit.append |
| 2 | 选项按钮 UI | `runtime/gui/pyqt6_main.py` | `PromptInputEvt` 触发选项按钮而非输入框 |
| 3 | AudioManager 真实现 | `runtime/audio.py` | pygame.mixer 播放 BGM/SE，@bgm 钩子接入 |
| 4 | 立绘占位 | `runtime/gui/pyqt6_main.py` | @style 立绘指令 → 彩色矩形 + 名字标签 |
| 5 | 背景图占位 | `runtime/gui/pyqt6_main.py` | @style bg 指令 → 纯色/渐变背景 |

### P1：基础体验补全（3-5 天）

| # | 任务 | 说明 |
|---|---|---|
| 6 | 存档截图 + 时间戳 | SaveManager 存 QPixmap + datetime |
| 7 | 历史回看 | TextEvt 累积 → 历史窗口 |
| 8 | 跳过/快进 | 已读标记 + 快进快捷键 |
| 9 | 设置菜单 | 文字速度 / BGM 音量 / 全屏 |

### P2：锦上添花（可选）

| # | 任务 | 说明 |
|---|---|---|
| 10 | 过渡动画 | 淡入淡出 / 溶解 |
| 11 | CG 图鉴 | 解锁状态 + 浏览 |
| 12 | 语音播放 | Voice 文件 + 字幕同步 |

---

## 7. 如果做 Hacknet 式，需要做什么

### P0：终端核心（1.5 周）

| # | 任务 | 说明 |
|---|---|---|
| 1 | 终端模拟器 | 滚动缓冲 + 命令行 + 历史 + Tab 补全 |
| 2 | 命令解析器 | 自由文本 → cmd + args |
| 3 | CommandRegistry | 注册 scan/connect/probe/ls/cat/hack 等命令 |
| 4 | 富文本输出 | ANSI color / HTML 渲染 + ASCII art |
| 5 | neon DSL 桥接 | 命令结果 → UserInputCmd → Executor |

### P1：世界模拟（1.5 周）

| # | 任务 | 说明 |
|---|---|---|
| 6 | 虚拟文件系统 | 树结构 + 文件内容 + ls/cd/cat/rm |
| 7 | 虚拟网络 | 节点 + 端口 + 连接拓扑 |
| 8 | 进程模拟 | PortHack / crack / monitor + 计时器 |
| 9 | 邮件系统 | NPC 邮件 → 任务触发 → neon 节点流 |

### P2：深度体验（1 周）

| # | 任务 | 说明 |
|---|---|---|
| 10 | 节点图可视化 | 网络拓扑 GUI |
| 11 | 实时时钟 | 计时器 + 倒计时任务 |
| 12 | 成就/统计 | 任务完成记录 |
| 13 | NPC AI | NPC 独立行为 + 延迟回复 |

---

## 8. 结论

Neural Engine 现在是一个**有完整逻辑内核但缺表现层的剧本引擎**。

- **逻辑内核**（剧本解析 + 变量 + 分支 + 路由 + 存档）已完成，467 测试守护
- **表现层**几乎为零（PyQt6 窗口能弹但只追加深文本，无立绘/背景/音频/对话框/打字机）
- **交互层**只有 `node in` 等待裸输入，无命令解析/选项按钮/终端模拟

**离最小 AVG**：缺一个对话框 + 立绘 + 音频的实现，约 2-3 周。
**离 Hacknet**：在 AVG 基础上再叠一个终端模拟 + 世界模拟，约再 2-3 周。

**建议**：走路线 C（AVG 最小闭环 → Hacknet 扩展），4 周内能从"能跑测试"到"能玩"。

---

*哈尼斯 · 2026-07-01*
