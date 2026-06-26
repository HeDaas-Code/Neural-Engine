"""装饰器运行时钩子注册表 + dispatcher。

v2-p0 设计（PDR phase3-v2p0.md §5.1.2 + V2-02 issue）：
- 全局 registry：装饰器名 → handler 函数
- handler 签名：`Callable[[DecoratorEvt], None]`
- `dispatch(DecoratorEvt)` → 调用对应 handler；无 handler 时**静默**（不抛错）
- 后注册覆盖前注册（last-write-wins）
- 测试钩子：提供 `unregister` / `clear` / `get_hook` 供测试隔离使用

注意：本模块**不**知道具体装饰器含义（style/bgm/...），仅提供
注册+分发机制。具体钩子在 `style.py` / `bgm.py` 等子模块实现，
通过 `register()` 注入到本 registry。
"""
from __future__ import annotations

from typing import Callable, Optional

from core.engine.protocol import DecoratorEvt


# 模块级 registry —— name → handler
_HOOKS: dict[str, Callable[[DecoratorEvt], None]] = {}


def register(name: str, handler: Callable[[DecoratorEvt], None]) -> None:
    """注册装饰器钩子。后注册覆盖前注册（last-write-wins）。

    Args:
        name: 装饰器名（对应 `DecoratorEvt.name`，如 "style" / "bgm"）
        handler: 钩子函数，签名 `(DecoratorEvt) -> None`
    """
    _HOOKS[name] = handler


def unregister(name: str) -> bool:
    """移除装饰器钩子。返回是否原本存在。

    Args:
        name: 装饰器名

    Returns:
        True 表示原本注册并已移除；False 表示原本就不存在。
    """
    return _HOOKS.pop(name, None) is not None


def clear() -> None:
    """清空所有装饰器钩子。**测试隔离用**——业务代码不应调用。"""
    _HOOKS.clear()


def dispatch(evt: DecoratorEvt) -> bool:
    """调度装饰器事件到对应钩子。

    Args:
        evt: `DecoratorEvt`

    Returns:
        True 表示有钩子处理；False 表示无钩子（静默忽略）。
    """
    handler = _HOOKS.get(evt.name)
    if handler is None:
        return False
    handler(evt)
    return True


def get_hook(name: str) -> Optional[Callable[[DecoratorEvt], None]]:
    """取已注册的钩子（仅测试 / 调试用，业务代码不应依赖此 API）。"""
    return _HOOKS.get(name)


__all__ = ["register", "unregister", "clear", "dispatch", "get_hook"]
