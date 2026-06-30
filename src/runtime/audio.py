"""音频管理器（BGM/SE/Voice）—— v2 占位。

v2 阶段（EP-07）：仅占位类，不实现 play/stop 方法。
v3+ 落地路径（V2-08 任务）：
- 监听 `DecoratorEvt(name="bgm", kind="call")` → play(bgm_path)
- 监听 `DecoratorEvt(name="bgm", kind="stop")` → stop()
- BGM/SE/Voice 三轨播放
"""
from __future__ import annotations


class AudioManager:
    """音频管理器占位类 —— v3+ 落地。

    v2 阶段：仅暴露类名（EP-07 骨架）。v3+ 任务 V2-08 补
    `play(bgm: str)` / `stop()` 方法（按 EP-06 新增的 `kind` 字段分流）。
    """