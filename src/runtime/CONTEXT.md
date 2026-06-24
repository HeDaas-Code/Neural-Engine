# Runtime — 运行时

本上下文包含文字游戏在各平台的运行表现层。

## 核心概念

### 存档系统

- **存档（Save）**：将 `GameState` 序列化后持久化到存储介质
- **读档（Load）**：从存储中恢复游戏状态并还原进度
- **存档槽位（Save Slot）**：物理存储上的一个存档位置（通常是文件或云端键值）
- **元数据（Metadata）**：存档的附加信息（游玩时长、截图、存档时间）

### 渲染层

- **文字渲染（Text Rendering）**：支持富文本、表情符号、逐字打印（typewriter effect）
- **立绘渲染（Character Rendering）**：角色立绘的显示、淡入淡出、位置控制
- **背景渲染（Background Rendering）**：场景图片的切换和过渡效果

### 音视频

- **背景音乐（BGM）**：循环播放的配乐
- **音效（SE）**：短音效（点击、场景切换等）
- **语音（Voice）**：角色的对话配音
- **视频（Video）**：过场动画

### 跨平台

- **平台抽象层（Platform Abstraction Layer）**：屏蔽不同平台（PC/Web/移动/主机）的差异
- **输入处理（Input Handling）**：鼠标、触摸、手柄的统一输入接口

## 关键类型

| 类型 | 描述 |
| ---- | ---- |
| `SaveManager` | 存档/读档管理 |
| `TextRenderer` | 文字渲染器 |
| `AudioManager` | 音频管理器（BGM/SE/Voice） |
| `VideoPlayer` | 视频播放器 |
| `PlatformBridge` | 平台抽象桥接层 |

## 术语表

- **不要用**：存盘点、读档点（用 save slot 代替）
- **明确用**：save/load（存档/读档）、BGM、SE（sound effect）、voice（语音）

## 架构约束

- 运行时层**依赖于 core**（读取 GameState 进行渲染），但不反向依赖
- 存档格式应考虑**向前兼容**，新增变量不影响旧存档的可读性
- 跨平台代码集中在本层，上层（core/editor）无需关心平台差异
