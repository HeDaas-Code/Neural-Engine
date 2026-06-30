"""v0/v2 GUI 入口（路径 B：CLI print+input；路径 A：PyQt6 窗口）。

v0 阶段不强装 PyQt6——CLI 占位足以验证 EngineBus 协议层。
v2-p0 (EP-05/D3): 按 `importlib.util.find_spec("PyQt6")` 探测，spec 在则尝试
  走 `runtime.gui.pyqt6_main`（V2-01 后续任务）；spec 不在或 pyqt6_main 缺失
  → 降级到 v0 CLI 占位主循环，不抛 ImportError。

关键设计：
- `find_spec` 必须作为模块属性暴露（D3 决策），供测试 monkeypatch 切换探测路径。
- 降级路径不抛 ImportError/FileNotFoundError；现有 CLI 行为保留。
"""
from __future__ import annotations

import importlib.util
import sys

from core.engine.protocol import (
    TextEvt, PromptInputEvt, DecoratorEvt, RouteEvt, ChapterEndEvt, LogEvt,
    UserInputCmd,
)

# D3 决策：把 find_spec 暴露为模块属性，供测试 monkeypatch 切换 PyQt6 探测路径。
# 默认指向真正的 importlib.util.find_spec（未 mock 时正常工作）。
find_spec = importlib.util.find_spec


def _has_pyqt6() -> bool:
    """探测 PyQt6 是否可用（通过 find_spec，不实际 import）。"""
    try:
        return find_spec("PyQt6") is not None
    except Exception:
        return False


def _try_pyqt6_main(bus) -> int | None:
    """尝试走 PyQt6 主循环。

    Returns:
        int —— PyQt6 主循环退出码（成功路径）。
        None —— PyQt6 不可用或 pyqt6_main 模块缺失/失败，调用方降级到 CLI。

    D3 决策：任何失败路径（ImportError / RuntimeError / PyQt6 实际未装）
    都降级到 CLI 占位，不抛错给调用方。
    """
    if not _has_pyqt6():
        return None
    try:
        from runtime.gui import pyqt6_main  # type: ignore[import-not-found]
    except ImportError:
        # V2-01 后续任务还没建 pyqt6_main.py → 降级到 CLI
        return None
    try:
        return pyqt6_main.main(bus=bus)
    except (RuntimeError, ImportError):
        # PyQt6 spec 在但实际 import 失败 / GUI 启动失败 → 降级到 CLI
        return None


def main(bus=None) -> int:
    """GUI 主循环：拿事件 → 打印 / input → put_cmd。

    v2-p0: 优先尝试 PyQt6 路径；不可用降级到 v0 CLI 占位。

    Args:
        bus: 双向 EngineBus-like（get_evt / put_cmd / close）。None 时自建。
    """
    # v2-p0: 先尝试 PyQt6 路径（V2-01 落地后生效；当前降级到 CLI）
    if bus is not None:
        rc = _try_pyqt6_main(bus)
        if rc is not None:
            return rc

    if bus is None:
        from core.engine.bus import EngineBus
        bus = EngineBus(use_multiprocessing=True)
        # 自建 bus 时也尝试 PyQt6
        rc = _try_pyqt6_main(bus)
        if rc is not None:
            return rc

    # v0 CLI 占位主循环（PyQt6 不可用 / pyqt6_main 缺失 时降级）
    while True:
        evt = bus.get_evt()
        if evt is None:
            # v0 阶段：bus 空表示无更多事件——退出循环
            break
        if isinstance(evt, TextEvt):
            print(f"[text] {evt.content}", end="")
        elif isinstance(evt, PromptInputEvt):
            print(f"[prompt_input] {evt.var}")
            val = input()
            bus.put_cmd(UserInputCmd(value=val))
        elif isinstance(evt, DecoratorEvt):
            # v0 静默
            pass
        elif isinstance(evt, RouteEvt):
            print(f"[route → {evt.target}]")
            bus.close()
            return 0
        elif isinstance(evt, ChapterEndEvt):
            print("[chapter end]")
            bus.close()
            return 0
        elif isinstance(evt, LogEvt):
            # v0 静默
            pass
        else:
            print(f"[unknown event] {evt!r}")

    bus.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
