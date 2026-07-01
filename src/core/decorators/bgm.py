"""`@bgm` 装饰器运行时钩子 —— v3-03 升级（PDR §5.1.2）。

设计：
- `install()` 注册默认 `@bgm` 钩子到 `core.decorators` 全局 registry
- `handle(evt)` 是钩子本体：
  - v2 阶段：解析 args → 记录 play/stop 调用（_LAST_BGM）
  - v3-03：若通过 `set_audio_manager(mgr)` 注册了 AudioManager，
    则额外调用 `mgr.play(arg)` / `mgr.stop()`（真播放）
- 双轨记录：始终更新 `_LAST_BGM`（向后兼容已有测试）+ 转发到 mgr（v3+）

语义：
- `@bgm rain.mp3` (kind='call') → ('play', 'rain.mp3')：触发播放
- `@bgm rain.mp3` (kind='stop') → ('stop', 'rain.mp3')：停止某 key 的 bgm
- 多 args：每个 arg 一条记录

注意：
- v2 阶段**仅记录**调用，**不**实际调 AudioManager（AudioManager 还是占位）
- v3-03 起：MainWindow 构造时 `bgm.set_audio_manager(AudioManager())` 注册真 mgr
- mgr 可选：未注册时仅记录（v2 行为基线，向后兼容）
- mgr 异常被吞掉（hook 不能崩 dispatcher）
"""
from __future__ import annotations

import logging
from typing import Literal, Optional

from core.engine.protocol import DecoratorEvt
from core.decorators import register

logger = logging.getLogger(__name__)


# 模块级状态：[(action, key), ...] —— 始终记录（v2 行为基线 + v3+ 测试断言）
_LAST_BGM: list[tuple[Literal["play", "stop"], str]] = []

# v3-03：可选 AudioManager 引用（None=仅记录，不实际播放）
_AUDIO_MANAGER: Optional[object] = None


def install() -> None:
    """注册默认 `@bgm` 钩子到全局 registry。"""
    register("bgm", handle)


def set_audio_manager(mgr: Optional[object]) -> None:
    """注册 AudioManager 实例（v3-03）。

    Args:
        mgr: AudioManager 实例（需有 play/stop 方法）；None=清除注册

    注册后，`@bgm` 调用会转发到 mgr.play(arg) / mgr.stop()。
    未注册（默认）时仅记录 _LAST_BGM（v2 行为基线）。
    """
    global _AUDIO_MANAGER
    _AUDIO_MANAGER = mgr


def get_audio_manager() -> Optional[object]:
    """取当前已注册的 AudioManager（测试断言用）。"""
    return _AUDIO_MANAGER


def handle(evt: DecoratorEvt) -> None:
    """默认 `@bgm` 钩子函数。

    行为：
    - `evt.kind == "call"`（默认）→ 每个 arg 一条 `('play', arg)` 记录
      + 若已注册 mgr → 调 `mgr.play(arg, track='bgm')`
    - `evt.kind == "stop"` → 每个 arg 一条 `('stop', arg)` 记录
      + 若已注册 mgr → 调 `mgr.stop(track='bgm')`

    v3-03：始终记录 _LAST_BGM（向后兼容），并转发到 mgr（若已注册）。
    mgr 异常被吞掉（hook 不能崩 dispatcher）。
    """
    action: Literal["play", "stop"] = "play" if evt.kind == "call" else "stop"
    for arg in evt.args:
        _LAST_BGM.append((action, arg))
        _forward_to_mgr(arg, action)


def _forward_to_mgr(arg: str, action: Literal["play", "stop"]) -> None:
    """转发 play/stop 到已注册的 AudioManager（v3-03）。

    无 mgr 注册 / mgr 异常 → 静默（不崩 hook）。
    """
    if _AUDIO_MANAGER is None:
        return
    try:
        if action == "play":
            # @bgm 语义上是 BGM 轨（始终循环）
            _AUDIO_MANAGER.play(arg, track="bgm", loop=True)  # type: ignore[attr-defined]
        else:
            _AUDIO_MANAGER.stop(track="bgm")  # type: ignore[attr-defined]
    except Exception as e:
        logger.warning("@bgm 转发 AudioManager 失败: %s", e)


def get_last_bgm() -> list[tuple[str, str]]:
    """取最近一次 `@bgm` 调用的记录列表（返回副本）。

    每条记录是 `(action, key)` 元组：`action` ∈ `{"play", "stop"}`，`key` 是 arg。
    """
    return list(_LAST_BGM)


def reset_last_bgm() -> None:
    """清空最近 bgm 记录。**测试隔离用**——业务代码不应调用。"""
    _LAST_BGM.clear()


__all__ = [
    "install",
    "handle",
    "get_last_bgm",
    "reset_last_bgm",
    "set_audio_manager",
    "get_audio_manager",
]
