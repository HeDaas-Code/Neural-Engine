# 30 · EngineBus 总线封装

> **TL;DR**：把两个 multiprocessing.Queue + JSON 序列化 + 错误包装封到四个方法里——`put_cmd / get_cmd / put_evt / get_evt`。**v0-issue-5 待实现**。

## 公开接口（v0-issue-5）

```python
class EngineBus:
    def __init__(self, cmd_q: Queue, evt_q: Queue):
        ...

    def put_cmd(self, cmd: Cmd) -> None: ...
    def get_cmd(self, timeout: float | None = None) -> Cmd: ...

    def put_evt(self, evt: Evt) -> None: ...
    def get_evt(self, timeout: float | None = None) -> Evt: ...

class ProtocolError(Exception):
    """反序列化失败时抛（包装 ValueError）"""
```

## 内部实现骨架

```python
# src/core/engine/bus.py
import json

class EngineBus:
    def __init__(self, cmd_q, evt_q):
        self._cmd_q = cmd_q
        self._evt_q = evt_q

    def _put(self, q, obj):
        # to_dict → json.dumps
        q.put(json.dumps(obj.to_dict()))

    def _get(self, q, timeout):
        raw = q.get(timeout=timeout)
        d = json.loads(raw)
        # 反序列化：根据 dict["cmd"] 或 dict["event"] 路由到对应 dataclass
        ...

    def put_cmd(self, cmd: Cmd) -> None:
        self._put(self._cmd_q, cmd)

    def get_cmd(self, timeout=None) -> Cmd:
        return self._get(self._cmd_q, timeout)

    def put_evt(self, evt: Evt) -> None:
        self._put(self._evt_q, evt)

    def get_evt(self, timeout=None) -> Evt:
        return self._get(self._evt_q, timeout)
```

## 强约束

1. **统一序列化 `json.dumps` / `json.loads`**——禁止 `pickle` / `eval` / 自定义 codec
2. **`protocol.to_dict / from_dict` 是唯一序列化点**——不绕过 dataclass 直接传 dict
3. **`from_dict` 抛 `ValueError` 时，bus 包装成 `ProtocolError`**——不暴露 JSON 解析细节
4. **`get_*` 默认阻塞**；`timeout` 不为 None 时超时抛 `queue.Empty`（**不重写** `Empty` 异常类型）

## 测试契约（v0-issue-5）

至少 3 个用例：
1. **双向发收**——两个 EngineBus 实例（A 用同一对 Queue 反向）互发互收
2. **序列化往返**——Cmd / Evt 各跑一次 `put → get`，断言字段相等
3. **协议错误包装**——发送非法 dict 让 `from_dict` 抛 `ValueError`，断言 `get_*` 抛 `ProtocolError`

## 内存 fake 队列（测试用 fixture）

`executor` 测试可以用 `queue.Queue`（不是 multiprocessing.Queue）替换，**单进程内**测全事件流：

```python
import queue

def make_test_bus():
    cmd_q, evt_q = queue.Queue(), queue.Queue()
    return EngineBus(cmd_q, evt_q), cmd_q, evt_q

# 测试断言：
bus, _, evt_q = make_test_bus()
Executor(story, bus).run()
assert evt_q.get_nowait() == TextEvt("...")
```

## 与 ADR 的实现要点

| ADR 约束 | 实现体现 |
| --- | --- |
| §7.1 进程模型 | 双向各一个 Queue |
| §7.2 消息方向 | `cmd_q`（GUI→Engine）+ `evt_q`（Engine→GUI）|
| §7.5 JSON 序列化 | `_put` 走 `json.dumps` |
| §11 #6 数据总线一律 JSON | 禁止 `pickle / msgpack` |
| §11 #7 多进程边界 | bus 是唯一跨进程接口 |

## 与其他页的关系

- [[messages]] — 3 Cmd + 6 Evt schema
- [[../20-architecture/multi-process]] — bus 在多进程拓扑中的角色
- [[../10-design/constraints]] — §11 #5 #6 #7 不变量

## 引用源

- ADR-0001 §7 + §11 —— [[raw-docs/ADR-0001-v0-baseline-script-spec]]
- v0-issue-5 工程笔记 —— [[raw-docs/工程笔记/v0-issue-5-bus.md]]
- CONTEXT-core 强约束 —— [[raw-docs/CONTEXT-core.md]]

## 原文快照（核对用）

本 wiki 页是分析层，下面是仓库原文快照以备核对：

- [[raw-docs/ADR-0001-v0-baseline-script-spec §7]]
- [[raw-docs/工程笔记/v0-issue-5-bus.md]]
- [[raw-docs/工程笔记/v0-issue-3-cmd.md]]
- [[raw-docs/工程笔记/v0-issue-4-evt.md]]