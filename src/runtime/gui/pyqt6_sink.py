"""PyQt6 事件 sink —— v2-p0（EP-03 + V2-01）。

设计动机：
- v2 阶段**不直接依赖 PyQt6**（CI 不装 PyQt6，D3 决策要求降级路径可跑）
- 用 callback-based 抽象：外部代码传 `evt_handler` callback 进来，
  sink 收到 Event 时调 callback（v3+ 替换为 Qt signal 发射）
- 接口对齐 `core.engine.executor.EventSink` Protocol（put_evt + get_cmd）——
  可直接当 Executor.sink 用

v3+ 替换点：
- `evt_handler` → Qt signal 跨线程发射（`QMetaObject.invokeMethod` + `QueuedConnection`）
- `cmd_source`  → Qt signal 输入（`QLineEdit.returnPressed` 槽函数）
- 内部状态 → QObject 子类化（保留本 callback API 即可让 main window 兼容）

注意：本模块**不**强制 import PyQt6。PyQt6 真实接入在 pyqt6_main.py（任务 3）做。
"""
from __future__ import annotations

from typing import Callable, Optional


# ─── 类型别名 ────────────────────────────────────────────────────────────────


# EventSink Protocol 已存在于 core/engine/executor.py:28，这里仅做类型提示
EventCallback = Callable[[object], None]
CmdSource = Callable[[], object]


# ─── PyQt6Sink ──────────────────────────────────────────────────────────────


class PyQt6Sink:
    """PyQt6 事件 sink（callback-based 抽象，兼容 EventSink Protocol）。

    Args:
        evt_handler: 处理 put_evt 收到的 Event 的回调。v3+ 替换为 Qt signal。
                     None 时静默（v2 默认：PyQt6Sink 未绑定时不抛错）。
        cmd_source:  返回下一个 cmd 的回调（get_cmd 调用）。None 时返回 None。
                     v3+ 替换为 Qt signal 消费者。

    用法（事件-输入闭环）：
        >>> from runtime.gui.pyqt6_input import PyQt6InputSink
        >>> inp = PyQt6InputSink()
        >>> sink = PyQt6Sink(cmd_source=inp.get_cmd)
        >>> inp.submit("hello")
        >>> sink.get_cmd()  # UserInputCmd(value='hello')

    用法（Executor.sink）：
        >>> from core.engine.executor import Executor
        >>> exe = Executor(story, sink)
        >>> exe.run()  # executor 通过 sink.put_evt(evt) 推 Event
    """

    def __init__(
        self,
        evt_handler: Optional[EventCallback] = None,
        cmd_source: Optional[CmdSource] = None,
    ):
        self._evt_handler = evt_handler
        self._cmd_source = cmd_source
        self._closed = False

    # ─── EventSink Protocol 接口 ───

    def put_evt(self, evt) -> None:
        """EventSink Protocol：接收 Event → 调 evt_handler。

        - closed 状态：静默（不再调 handler）
        - evt_handler 未设置：静默（v2 默认）
        - evt_handler 已设置：调 handler(evt)（v3+ 替换为 Qt signal 发射）
        """
        if self._closed:
            return
        if self._evt_handler is None:
            return
        self._evt_handler(evt)

    def get_cmd(self):
        """EventSink Protocol：取下一个 cmd（v3+ 阻塞消费；v2：调 cmd_source）。

        - closed 状态：返回 None
        - cmd_source 未设置：返回 None
        - cmd_source 已设置：返回 cmd_source() 的值
        """
        if self._closed:
            return None
        if self._cmd_source is None:
            return None
        return self._cmd_source()

    # ─── 生命周期 ───

    def close(self) -> None:
        """关闭 sink。close 后 put_evt / get_cmd 都静默。"""
        self._closed = True

    @property
    def is_closed(self) -> bool:
        """是否已关闭（测试 / 调试用）。"""
        return self._closed


__all__ = ["PyQt6Sink", "EventCallback", "CmdSource"]
