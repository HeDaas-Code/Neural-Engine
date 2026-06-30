"""PyQt6 用户输入 sink —— v2-p0（EP-03 + V2-01）。

设计动机：
- v2 阶段**不直接依赖 PyQt6**（callback-based 抽象）
- 外部代码（如 pyqt6_main.py 的 `QLineEdit.returnPressed` 槽函数）
  调 `submit(value)` 把用户输入包成 `UserInputCmd` 推入内部 queue
- 测试可直接调 submit / drain_cmd 验证（无需 Qt）

接口分层：
- `submit(value)` ← Qt 信号槽触发（v3+ 接管后由 Qt signal 调用）
- `drain_cmd()`  ← 非阻塞取下一个 cmd（test / v3+ Qt signal consumer）
- `get_cmd()`    ← 阻塞取下一个 cmd（EventSink Protocol · executor 调用）

线程安全：
- 内部用 `queue.Queue`（线程安全），与 PyQt6 主线程/QThread 消费者无冲突
- D5 决策：不引入 asyncio（本模块用 threading 原生 Queue）
"""
from __future__ import annotations

import queue as _thread_queue

from core.engine.protocol import UserInputCmd


class PyQt6InputSink:
    """PyQt6 用户输入 sink（thread-safe queue + UserInputCmd 包装）。

    用法：
        >>> inp = PyQt6InputSink()
        >>> inp.submit("hello")  # 模拟 QLineEdit 回车
        >>> inp.drain_cmd()
        UserInputCmd(value='hello')

    v3+ 接管：pyqt6_main.py 的 QLineEdit.returnPressed 信号连接到一个槽函数，
    该槽函数内部调 `input_sink.submit(text)`——本类无需修改。
    """

    def __init__(self):
        self._cmd_q: _thread_queue.Queue = _thread_queue.Queue()
        self._closed = False

    # ─── Qt 信号槽入口（v3+ 由 QLineEdit 触发） ───

    def submit(self, value: str) -> None:
        """Qt 信号槽调此方法把用户输入转成 UserInputCmd 入队。

        - closed 状态：静默丢弃（防 race 写入已关闭的 queue）
        - 否则：包成 UserInputCmd(value=value) 推入内部 queue
        """
        if self._closed:
            return
        self._cmd_q.put(UserInputCmd(value=value))

    # ─── cmd 消费（D5 决策：不用 asyncio，用 threading 原生 Queue） ───

    def drain_cmd(self):
        """非阻塞取下一个 cmd。无 cmd 时返回 None。

        用途：测试 / v3+ Qt signal consumer（事件循环里轮询）。
        """
        if self._closed:
            return None
        try:
            return self._cmd_q.get_nowait()
        except _thread_queue.Empty:
            return None

    def get_cmd(self):
        """阻塞取下一个 cmd。无 cmd 时阻塞直到 submit 被调。

        用途：Executor 主循环调用（executor.py:193 `cmd = self.sink.get_cmd()`）。
        与 EventSink Protocol 兼容（PyQt6Sink.cmd_source = PyQt6InputSink.get_cmd）。
        """
        if self._closed:
            return None
        return self._cmd_q.get()

    # ─── 生命周期 ───

    def close(self) -> None:
        """关闭 input sink。close 后 submit 静默丢弃。"""
        self._closed = True

    @property
    def is_closed(self) -> bool:
        """是否已关闭（测试 / 调试用）。"""
        return self._closed


__all__ = ["PyQt6InputSink"]
