"""`@style` 装饰器运行时钩子 —— v2-p0（PDR §5.1.2）。

设计：
- `install()` 注册默认 `@style` 钩子到 `core.decorators` 全局 registry
- `handle(evt)` 是钩子函数本体（v2 阶段：解析 `key:val` 写入模块级字典）
- v2 阶段**不实际渲染**（PyQt6Sink 接管）；v3+ 接管真实渲染逻辑

key/val 解析约定（PDR §5.1.2）：
- `@style text:rgb:red` → set("text", "rgb:red")
- `@style color:red font:arial size:14` → 分别 set color/font/size
- 无冒号的 arg 被忽略（容错）

stop 语义（v2）：
- `kind == "stop"` 时**不修改状态**——v2 不实现 stop 语义（v3+ 接管）
- 这与 V2-02 issue 文档"v2 仅处理 call；stop v3+ 落地"一致
"""
from __future__ import annotations

from core.engine.protocol import DecoratorEvt

# 暴露 handle 给测试 + install() 注册
from core.decorators import register


# 模块级状态：最近一次 @style 设置的 key → val（v2 占位，PyQt6Sink 可读）
_LAST_STYLE: dict[str, str] = {}


def install() -> None:
    """注册默认 `@style` 钩子到全局 registry。"""
    register("style", handle)


def handle(evt: DecoratorEvt) -> None:
    """默认 `@style` 钩子函数。

    行为：
    - `evt.kind == "stop"` → 静默（v2 不处理 stop）
    - `evt.kind == "call"`（默认）→ 解析每个 `arg` 的 `key:val` 写入 `_LAST_STYLE`

    无冒号的 arg 静默忽略。
    """
    if evt.kind != "call":
        # v2 阶段不处理 stop 语义——v3+ 接管
        return
    for arg in evt.args:
        if ":" not in arg:
            continue  # 容错：跳过无冒号的 arg
        k, v = arg.split(":", 1)
        _LAST_STYLE[k] = v


def get_last_style() -> dict[str, str]:
    """取最近一次 `@style` 设置的 key → val（返回副本，外部修改不影响内部）。

    用于：
    - 测试断言（钩子是否正确解析 key:val）
    - 业务层读取最近样式（如 PyQt6Sink 在渲染 TextEvt 前查询当前 style）
    """
    return dict(_LAST_STYLE)


def reset_last_style() -> None:
    """清空最近 style 状态。**测试隔离用**——业务代码不应调用。"""
    _LAST_STYLE.clear()


__all__ = ["install", "handle", "get_last_style", "reset_last_style"]
