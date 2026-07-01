# Neural Engine 功能路线图

> **日期**：2026-07-01（v2-p0 完工后更新）
> **作者**：哈尼斯（独立第三方审计）
> **基线**：v2-p0 完工，467 tests，3500 行源码 + 7900 行测试
> **详细差距分析**：[GAP-ANALYSIS.md](GAP-ANALYSIS.md)

---

## 1. 现阶段能力总览

### 1.1 已落地

| 层 | 能力 | 状态 |
|---|---|---|
| **DSL 解析** | neon 围栏、块骨架、元数据 id、next 声明（←）、文本行、node in（→）、node echo（含拼接）、node next_id、node if（值匹配 + 表达式求值）、修饰器（@style / @bgm）、整行注释 | ✅ |
| **表达式** | simpleeval 沙箱、变量注入、13 内置函数（int/str/float/bool/len/min/max/abs/round + randint/clamp/upper/lower/contains）、fallback 正则、自定义函数注册 | ✅ |
| **执行器** | Text/In/Echo/NextId/If/Decorator 全节点类型、NEXT 三阶段、块级作用域、跨块跳转、RouteEvt/ChapterEndEvt、target_id 校验、SaveCmd/LoadCmd 拦截 | ✅ |
| **进程协议** | 5 Cmd + 8 Evt + JSON 序列化 + multiprocessing.Queue | ✅ |
| **GUI** | PyQt6 MainWindow（QTextEdit + QLineEdit + QPushButton）、PyQt6Sink/InputSink 适配、CLI 降级、find_spec 探测 | ✅ 骨架 |
| **章节管理** | ChapterManager 跨章节路由、load_chapter_safe 路径校验、shared_state 跨章节状态 | ✅ |
| **存档** | SaveManager save/load/list/delete、GameState 序列化、slot 路径穿越防护 | ✅ |
| **装饰器钩子** | @style / @bgm register + dispatch 框架、kind 字段 call/stop | ✅ 骨架 |
| **测试** | 467 tests、10 不变量、18 MVP 表、v0/v1/v2 端到端 | ✅ |

### 1.2 空壳 / 未落地

| 模块 | 状态 | 说明 |
|---|---|---|
| AudioManager | 空壳 | 只有类名，无 play/stop |
| VideoPlayer | 空壳 | 只有类名，无 play |
| @style 渲染 | 记录不渲染 | 写入字典，PyQt6 不读 |
| @bgm 播放 | 记录不播放 | 写入列表，AudioManager 不调 |
| 存档恢复执行位置 | ❌ | current_block_id 已存但无恢复跑路径 |
| 剧情编辑器 | ❌ | src/editor/ 空目录 |
| 对话框/立绘/背景 | ❌ | 无视觉层 |
| LLM 集成 | ❌ | 无 |

---

## 2. 下一步路线：AVG 最小闭环 → Hacknet 扩展

详见 [GAP-ANALYSIS.md](GAP-ANALYSIS.md) 的完整分析。

### 阶段 1：AVG 最小闭环（1 周）

让引擎从"能跑测试"变成"能玩"。

| # | 任务 | 改动位置 | 优先级 |
|---|---|---|---|
| 1 | 对话框 UI（名字 + 文本框 + 打字机） | `pyqt6_main.py` 重构 | P0 |
| 2 | 选项按钮 UI（替代裸输入数字） | `pyqt6_main.py` + `PromptInputEvt` 扩展 | P0 |
| 3 | AudioManager 真实现（pygame.mixer） | `runtime/audio.py` | P0 |
| 4 | 立绘占位（@style 立绘指令 → 彩色矩形 + 名字） | `pyqt6_main.py` + `@style` 扩展 | P0 |
| 5 | 背景图占位（@style bg → 纯色/渐变） | `pyqt6_main.py` | P0 |

### 阶段 2：体验补全（3-5 天）

| # | 任务 | 说明 |
|---|---|---|
| 6 | 存档截图 + 时间戳 | SaveManager 存 QPixmap + datetime |
| 7 | 历史回看 | TextEvt 累积 → 历史窗口 |
| 8 | 跳过/快进 | 已读标记 + 快进快捷键 |
| 9 | 设置菜单 | 文字速度 / BGM 音量 / 全屏 |

### 阶段 3：Hacknet 扩展（2 周）

在 AVG 基础上叠加终端模拟 + 世界模拟。

| # | 任务 | 说明 |
|---|---|---|
| 10 | 终端模拟器 | 滚动缓冲 + 命令行 + 历史 + Tab 补全 |
| 11 | 命令解析器 + CommandRegistry | scan/connect/probe/ls/cat/hack |
| 12 | 富文本输出 | ANSI color + ASCII art |
| 13 | neon DSL 桥接 | 命令结果 → UserInputCmd → Executor |
| 14 | 虚拟文件系统 | 树结构 + ls/cd/cat/rm |
| 15 | 虚拟网络 | 节点 + 端口 + 连接拓扑 |
| 16 | 进程模拟 | PortHack / crack + 计时器 |
| 17 | 邮件系统 | NPC 邮件 → 任务触发 |

### 阶段 4：远期（可选）

| # | 任务 | 说明 |
|---|---|---|
| 18 | LLM 集成（@LLM-jud 装饰器） | ADR-0004 F4 |
| 19 | 剧情编辑器 | 节点图 GUI |
| 20 | 章节图可视化 | DOT 图 |
| 21 | NPC AI | 独立行为 + 延迟回复 |

---

## 3. 已关闭的旧 issue

这些在 v2-p0 已全部落地，留作记录：

| 旧 # | 内容 | 落地 PR |
|---|---|---|
| 3.1 | PyQt6 GUI 窗口 | v2-p0-gui-first |
| 3.2 | 章节加载器 | v2-p0-chapter |
| 3.3 | 存档/读档 | v2-p0-save |
| 3.6 | 表达式系统增强（randint/clamp/upper/lower/contains） | PR #85 |
| 3.11 | 测试覆盖率提升 | PR #87 |

---

*哈尼斯 · 2026-07-01*
