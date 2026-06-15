"""v0 GUI 占位（路径 B：CLI print+input，不依赖 PyQt6）。

v0 阶段不强装 PyQt6——CLI 占位足以验证 EngineBus 协议层。
v1 阶段：路径 A（PyQt6 窗口）按 `importlib.util.find_spec("PyQt6")` 切换。
"""
from __future__ import annotations

import sys

from core.engine.protocol import (
    TextEvt, PromptInputEvt, DecoratorEvt, RouteEvt, ChapterEndEvt, LogEvt,
    UserInputCmd,
)


def main(bus=None) -> int:
    """GUI 主循环：拿事件 → 打印 / input → put_cmd。

    Args:
        bus: 双向 EngineBus-like（get_evt / put_cmd / close）。None 时自建。
    """
    if bus is None:
        from core.engine.bus import EngineBus
        bus = EngineBus(use_multiprocessing=True)

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
