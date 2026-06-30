"""Neural Engine 运行时层。

v2 落地模块：
- save (V2-07 · 当前 EP-07 占位类) —— 存档/读档
- gui (V2-01) —— 渲染入口（CLI / PyQt6 工厂分发）

v3+ 落地占位模块（V2-08 任务接管，本任务仅暴露类名）：
- audio (BGM/SE/Voice) —— 音频管理
- video —— 视频播放器

EP-07 骨架：本文件从空占位升级为导出 3 个占位类
（SaveManager / AudioManager / VideoPlayer），让后续 GUI/章节/存档 feature
任务并行时不打架。
"""
from runtime.audio import AudioManager
from runtime.save import SaveManager
from runtime.video import VideoPlayer

__all__ = ["SaveManager", "AudioManager", "VideoPlayer"]