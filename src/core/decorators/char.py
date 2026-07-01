"""`@char` 装饰器运行时钩子 —— v3-04（角色立绘）。

设计（仿 bgm.py 模式）：
- `install()` 注册 `@char` 钩子到 `core.decorators` 全局 registry
- `handle(evt)`:
  - kind="call" → 解析 args 中的 `name:`/`src:`/`pos:` 键 → `mgr.set_character(name, src, pos)`
  - kind="stop" → `mgr.remove_character(key)`（key 是 args[0]）
- 始终记录 `_LAST_CHAR`（向后兼容 + 测试断言）
- 通过 `set_image_manager(mgr)` 注入 ImageRenderer（与 @bg 共享同一 mgr）
- mgr 异常被吞掉（hook 不能崩 dispatcher）

DSL 语法：
- `@char name:alice, src:alice.png, pos:left` (call) → 在左侧显示 alice 立绘
- `@char alice` (stop) → 移除 alice 立绘

位置取值：left / center / right（默认 center）
"""
from __future__ import annotations

import logging
from typing import Literal, Optional

from core.engine.protocol import DecoratorEvt
from core.decorators import register

logger = logging.getLogger(__name__)


# 模块级状态：[(action, name, src, pos), ...] —— 始终记录
_LAST_CHAR: list[tuple[Literal["show", "remove"], str, str, str]] = []

# v3-04：可选 ImageRenderer 引用（与 @bg 共享同一实例）
_IMAGE_MANAGER: Optional[object] = None

# 合法位置
_VALID_POS = ("left", "center", "right")


def install() -> None:
    """注册 `@char` 钩子到全局 registry。"""
    register("char", handle)


def set_image_manager(mgr: Optional[object]) -> None:
    """注册 ImageRenderer 实例（v3-04，与 @bg 共享）。

    Args:
        mgr: ImageRenderer 实例（需有 set_character/remove_character 方法）；None=清除
    """
    global _IMAGE_MANAGER
    _IMAGE_MANAGER = mgr


def get_image_manager() -> Optional[object]:
    """取当前已注册的 ImageRenderer（测试断言用）。"""
    return _IMAGE_MANAGER


def handle(evt: DecoratorEvt) -> None:
    """`@char` 钩子函数。

    行为：
    - `evt.kind == "call"` → 解析 name:/src:/pos: → 记录 `('show', name, src, pos)`
      + 若已注册 mgr → 调 `mgr.set_character(name, src, pos)`
    - `evt.kind == "stop"` → args[0] 是角色名 → 记录 `('remove', name, '', '')`
      + 若已注册 mgr → 调 `mgr.remove_character(name)`

    name 缺失时静默返回（必须有 name 才能显示/移除角色）。
    mgr 异常被吞掉（hook 不能崩 dispatcher）。
    """
    if evt.kind == "stop":
        name = evt.args[0] if evt.args else ""
        if not name:
            return
        _LAST_CHAR.append(("remove", name, "", ""))
        _forward_to_mgr(action="remove", name=name, src="", pos="")
        return

    # call: 解析 name:/src:/pos:
    parsed = _parse_char_args(evt.args)
    name = parsed.get("name", "")
    if not name:
        # 无 name: 键 → 无法标识角色，静默
        return
    src = parsed.get("src", "")
    pos = parsed.get("pos", "center")
    if pos not in _VALID_POS:
        pos = "center"

    _LAST_CHAR.append(("show", name, src, pos))
    _forward_to_mgr(action="show", name=name, src=src, pos=pos)


def _parse_char_args(args: list[str]) -> dict[str, str]:
    """解析 @char 的 key:val 参数。"""
    result: dict[str, str] = {}
    for arg in args:
        if ":" in arg:
            k, v = arg.split(":", 1)
            result[k.strip()] = v.strip()
    return result


def _forward_to_mgr(
    action: Literal["show", "remove"], name: str, src: str, pos: str
) -> None:
    """转发到已注册的 ImageRenderer（v3-04）。

    无 mgr 注册 / mgr 异常 → 静默（不崩 hook）。
    """
    if _IMAGE_MANAGER is None:
        return
    try:
        if action == "show":
            _IMAGE_MANAGER.set_character(name, src, pos)  # type: ignore[attr-defined]
        else:
            _IMAGE_MANAGER.remove_character(name)  # type: ignore[attr-defined]
    except Exception as e:
        logger.warning("@char 转发 ImageRenderer 失败: %s", e)


def get_last_char() -> list[tuple[str, str, str, str]]:
    """取最近一次 `@char` 调用的记录列表（返回副本）。"""
    return list(_LAST_CHAR)


def reset_last_char() -> None:
    """清空最近 char 记录。**测试隔离用**。"""
    _LAST_CHAR.clear()


__all__ = [
    "install",
    "handle",
    "get_last_char",
    "reset_last_char",
    "set_image_manager",
    "get_image_manager",
]
