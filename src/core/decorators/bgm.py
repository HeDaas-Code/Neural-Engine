"""`@bgm` 装饰器运行时钩子 —— v2-p0（PDR §5.1.2）。

设计：
- `install()` 注册默认 `@bgm` 钩子到 `core.decorators` 全局 registry
- `handle(evt)` 是钩子函数本体（v2 阶段：解析 args → 记录 play/stop 调用）
- v2 阶段**不实际播放/停止音频**（AudioManager 占位类，v3+ 接管真实播放）

语义：
- `@bgm rain.mp3` (kind='call') → ('play', 'rain.mp3')：触发播放
- `@bgm rain.mp3` (kind='stop') → ('stop', 'rain.mp3')：停止某 key 的 bgm
- 多 args：每个 arg 一条记录

注意：
- v2 仅**记录**调用，**不**实际调 AudioManager（AudioManager 还是占位）
- v3+ 接管时，`handle` 内部改为调 `runtime.audio.AudioManager().play(path)`
- 本设计保证 v3+ 替换不影响 dispatcher 接口
"""
from __future__ import annotations

from typing import Literal

from core.engine.protocol import DecoratorEvt
from core.decorators import register


# 模块级状态：[(action, key), ...] —— v2 占位（AudioManager v3+ 接管）
_LAST_BGM: list[tuple[Literal["play", "stop"], str]] = []


def install() -> None:
    """注册默认 `@bgm` 钩子到全局 registry。"""
    register("bgm", handle)


def handle(evt: DecoratorEvt) -> None:
    """默认 `@bgm` 钩子函数。

    行为：
    - `evt.kind == "call"`（默认）→ 每个 arg 一条 `('play', arg)` 记录
    - `evt.kind == "stop"` → 每个 arg 一条 `('stop', arg)` 记录

    v2 阶段只记录，不实际播放。v3+ 替换为 AudioManager.play / .stop 调用。
    """
    action: Literal["play", "stop"] = "play" if evt.kind == "call" else "stop"
    for arg in evt.args:
        _LAST_BGM.append((action, arg))


def get_last_bgm() -> list[tuple[str, str]]:
    """取最近一次 `@bgm` 调用的记录列表（返回副本）。

    每条记录是 `(action, key)` 元组：`action` ∈ `{"play", "stop"}`，`key` 是 arg。
    """
    return list(_LAST_BGM)


def reset_last_bgm() -> None:
    """清空最近 bgm 记录。**测试隔离用**——业务代码不应调用。"""
    _LAST_BGM.clear()


__all__ = ["install", "handle", "get_last_bgm", "reset_last_bgm"]
