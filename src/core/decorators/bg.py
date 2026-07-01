"""`@bg` 装饰器运行时钩子 —— v3-04（背景图）。

设计（仿 bgm.py 模式）：
- `install()` 注册 `@bg` 钩子到 `core.decorators` 全局 registry
- `handle(evt)`:
  - kind="call" → 解析 args 中的 `src:` 键 → `mgr.set_background(src)`
  - kind="stop" → `mgr.clear_background()`
- 始终记录 `_LAST_BG`（向后兼容 + 测试断言）
- 通过 `set_image_manager(mgr)` 注入 ImageRenderer（MainWindow 构造时）
- mgr 异常被吞掉（hook 不能崩 dispatcher）

DSL 语法：
- `@bg src:forest.png` (call) → 设置背景为 forest.png
- `@bg` (stop) → 清除背景

注意：
- 未注册 mgr 时仅记录 _LAST_BG（v2 行为基线，向后兼容）
- @bg 的 args 用 `key:val` 形式（与 @style 一致），bare arg 会被解析为 stop
"""
from __future__ import annotations

import logging
from typing import Literal, Optional

from core.engine.protocol import DecoratorEvt
from core.decorators import register

logger = logging.getLogger(__name__)


# 模块级状态：[(action, src), ...] —— 始终记录（测试断言 + 向后兼容）
_LAST_BG: list[tuple[Literal["set", "clear"], str]] = []

# v3-04：可选 ImageRenderer 引用（None=仅记录，不实际渲染）
_IMAGE_MANAGER: Optional[object] = None


def install() -> None:
    """注册 `@bg` 钩子到全局 registry。"""
    register("bg", handle)


def set_image_manager(mgr: Optional[object]) -> None:
    """注册 ImageRenderer 实例（v3-04）。

    Args:
        mgr: ImageRenderer 实例（需有 set_background/clear_background 方法）；None=清除

    注册后，`@bg` 调用会转发到 mgr.set_background(src) / mgr.clear_background()。
    """
    global _IMAGE_MANAGER
    _IMAGE_MANAGER = mgr


def get_image_manager() -> Optional[object]:
    """取当前已注册的 ImageRenderer（测试断言用）。"""
    return _IMAGE_MANAGER


def handle(evt: DecoratorEvt) -> None:
    """`@bg` 钩子函数。

    行为：
    - `evt.kind == "call"` → 解析 args 中的 `src:` 键 → 记录 `('set', src)`
      + 若已注册 mgr → 调 `mgr.set_background(src)`
    - `evt.kind == "stop"` → 记录 `('clear', '')`
      + 若已注册 mgr → 调 `mgr.clear_background()`

    mgr 异常被吞掉（hook 不能崩 dispatcher）。
    """
    if evt.kind == "stop":
        _LAST_BG.append(("clear", ""))
        _forward_to_mgr(action="clear", src="")
        return

    # call: 解析 src:path
    src = ""
    for arg in evt.args:
        if arg.startswith("src:"):
            src = arg.split(":", 1)[1].strip()
            break

    if not src:
        # 无 src: 键 → 静默（兼容未来 key:val 扩展）
        return

    _LAST_BG.append(("set", src))
    _forward_to_mgr(action="set", src=src)


def _forward_to_mgr(action: Literal["set", "clear"], src: str) -> None:
    """转发到已注册的 ImageRenderer（v3-04）。

    无 mgr 注册 / mgr 异常 → 静默（不崩 hook）。
    """
    if _IMAGE_MANAGER is None:
        return
    try:
        if action == "set":
            _IMAGE_MANAGER.set_background(src)  # type: ignore[attr-defined]
        else:
            _IMAGE_MANAGER.clear_background()  # type: ignore[attr-defined]
    except Exception as e:
        logger.warning("@bg 转发 ImageRenderer 失败: %s", e)


def get_last_bg() -> list[tuple[str, str]]:
    """取最近一次 `@bg` 调用的记录列表（返回副本）。"""
    return list(_LAST_BG)


def reset_last_bg() -> None:
    """清空最近 bg 记录。**测试隔离用**。"""
    _LAST_BG.clear()


__all__ = [
    "install",
    "handle",
    "get_last_bg",
    "reset_last_bg",
    "set_image_manager",
    "get_image_manager",
]
