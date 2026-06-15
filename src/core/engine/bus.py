"""v0 双向 EngineBus：封装 multiprocessing.Queue / queue.Queue + JSON 序列化。

按 ADR §7.3 / §7.4 落地 GUI ↔ Engine 进程间通信。
- put_cmd / get_cmd: GUI → Engine
- put_evt / get_evt: Engine → GUI
- to_dict / from_dict 已在 protocol.py 落地；本模块只做 JSON 包装
- ValueError 从 parse_cmd / parse_evt 直接传播（不包装）
"""
from __future__ import annotations

import json
import multiprocessing
import queue as _thread_queue

from core.engine.protocol import parse_cmd, parse_evt


class EngineBus:
    """双向 Queue + JSON 序列化封装。

    Args:
        cmd_q: GUI → Engine 队列；None 时按 use_multiprocessing 注入默认
        evt_q: Engine → GUI 队列；同上
        use_multiprocessing: True → multiprocessing.Queue；False → queue.Queue
    """

    def __init__(
        self,
        cmd_q=None,
        evt_q=None,
        *,
        use_multiprocessing: bool = True,
    ):
        factory = multiprocessing.Queue if use_multiprocessing else _thread_queue.Queue
        self._cmd_q = cmd_q if cmd_q is not None else factory()
        self._evt_q = evt_q if evt_q is not None else factory()

    def put_cmd(self, cmd) -> None:
        """GUI → Engine：序列化 cmd 并入队。"""
        self._cmd_q.put(json.dumps(cmd.to_dict()).encode("utf-8"))

    def get_cmd(self):
        """GUI → Engine：出队 + 反序列化 + parse_cmd。"""
        raw = self._cmd_q.get()
        return parse_cmd(json.loads(raw.decode("utf-8")))

    def put_evt(self, evt) -> None:
        """Engine → GUI：序列化 evt 并入队。"""
        self._evt_q.put(json.dumps(evt.to_dict()).encode("utf-8"))

    def get_evt(self):
        """Engine → GUI：出队 + 反序列化 + parse_evt。"""
        raw = self._evt_q.get()
        return parse_evt(json.loads(raw.decode("utf-8")))

    def close(self) -> None:
        """关闭两个 queue + 排空残留。"""
        for q in (self._cmd_q, self._evt_q):
            self._drain(q)
            self._close_queue(q)

    @staticmethod
    def _drain(q) -> None:
        """排空 q 中残留消息（非阻塞）。"""
        # multiprocessing.Queue 没有 drain；用 get_nowait 循环
        while True:
            try:
                q.get_nowait()
            except (_thread_queue.Empty, Exception):
                # multiprocessing.Empty 是 _thread_queue.Empty 的别名
                break

    @staticmethod
    def _close_queue(q) -> None:
        """关闭 q（如果支持 close）。"""
        # multiprocessing.Queue 是工厂函数生成的实例，有 .close() 方法
        # queue.Queue 无 .close()
        if hasattr(q, "close") and callable(getattr(q, "close")):
            # 区分：multiprocessing.Queue 的 close 接收 ctx 参数；queue.Queue 无 close
            # 鸭子类型：有 close 且不是 queue.Queue 即关闭
            if not isinstance(q, _thread_queue.Queue):
                q.close()
