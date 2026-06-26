"""v2 GUI 入口工厂：按 PyQt6 可用性切换主入口（D3 决策）。

设计要点：
1. **find_spec 暴露为模块属性**（`runtime.gui.main.find_spec`）—— 测试可 monkeypatch，
   未来 V2-01 PyQt6 任务也能用同一机制注入测试 fake。
2. **工厂分发（D3）**：
   - 有 PyQt6 且 `runtime.gui.pyqt6_main` 已建 → 走 PyQt6 主循环
   - PyQt6 在但 `pyqt6_main.py` 还没建（V2-01 后续任务） → 降级 CLI
   - PyQt6 未装 → 走 v0 CLI 占位主循环
3. **降级安全**：PyQt6 分支的 import 用 try/except 包起来，
   任何 ImportError 都不会污染 CLI 路径。
"""
from __future__ import annotations

import importlib.util
import sys

from core.engine.protocol import (
    TextEvt, PromptInputEvt, DecoratorEvt, RouteEvt, ChapterEndEvt, LogEvt,
    UserInputCmd,
)


# 暴露为模块属性（不是 importlib.util.find_spec 全局函数）—— 让测试可 monkeypatch
find_spec = importlib.util.find_spec


def _has_pyqt6_main() -> bool:
    """探测 PyQt6 + pyqt6_main.py 是否同时就绪。"""
    if find_spec("PyQt6") is None:
        return False
    try:
        # 即便 PyQt6 spec 在，pyqt6_main.py 是 V2-01 后续任务建的——
        # 探测路径必须能容忍缺它的情况。
        from runtime.gui import pyqt6_main  # noqa: F401
    except ImportError:
        return False
    return True


def main(bus=None) -> int:
    """GUI 主入口工厂。

    Args:
        bus: 双向 EngineBus-like（get_evt / put_cmd / close）。None 时自建。

    Returns:
        进程退出码（0 = 正常退出）。

    分发逻辑：
    - PyQt6 全栈就绪 → `runtime.gui.pyqt6_main.main(bus)`
    - 其他情况 → v0 CLI 占位主循环
    """
    if bus is None:
        from core.engine.bus import EngineBus
        bus = EngineBus(use_multiprocessing=True)

    if _has_pyqt6_main():
        # 延迟 import：避免 PyQt6 import 失败时污染 CLI 路径
        from runtime.gui.pyqt6_main import main as _pyqt_main
        return _pyqt_main(bus)

    return _cli_main(bus)


def _cli_main(bus) -> int:
    """v0 CLI 占位主循环：print + input → put_cmd。

    v0 阶段不依赖 PyQt6，CLI 占位足以验证 EngineBus 协议层。
    v2 阶段被工厂分发作为 fallback 路径。
    """
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