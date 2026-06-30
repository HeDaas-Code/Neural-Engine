"""视频播放器 —— v2 占位。

v2 阶段（EP-07）：仅占位类，不实现 play 方法。
v3+ 落地路径（V2-08 任务）：
- 播放过场动画（mp4/webm）
- 与 TextRenderer 协调：视频播放期间暂停文字流
"""
from __future__ import annotations


class VideoPlayer:
    """视频播放器占位类 —— v3+ 落地。

    v2 阶段：仅暴露类名（EP-07 骨架）。v3+ 任务 V2-08 补
    `play(video: str)` 方法。
    """