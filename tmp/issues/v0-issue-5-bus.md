## Parent

#22（PRD-0001 父 issue）

## What to build

`src/core/engine/bus.py` 提供 `EngineBus` 封装双向 `multiprocessing.Queue`（GUI→Engine 一个、Engine→GUI 一个），做 JSON 序列化、命令/事件双向解析。

API：
- `EngineBus(cmd_q: multiprocessing.Queue | None = None, evt_q: multiprocessing.Queue | None = None, *, use_multiprocessing: bool = True)` —— **构造时**支持 default 注入（`None` 时按 `use_multiprocessing` 选 `multiprocessing.Queue` 或 `queue.Queue`）
- `put_cmd(cmd) -> None` —— 序列化：`cmd.to_dict()` → `json.dumps` → `cmd_q.put`
- `get_cmd() -> Cmd` —— 反序列化：`cmd_q.get()` → `json.loads` → `parse_cmd()`；`from_dict` 抛 ValueError 时**直接传播**（**不**包 ProtocolError）
- `put_evt(evt) -> None` —— 同上，方向反
- `get_evt() -> Evt` —— 同上，方向反
- `close() -> None` —— 关闭两个 queue + 排空残留（**不** join thread——multiprocessing.Queue 没有 close-on-GC）

设计要点：
- 内部不引用 `executor` / `interpreter`——**纯叶子**模块
- `multiprocessing.Queue` 与 `queue.Queue` 的统一抽象：`isinstance(q, multiprocessing.Queue)` 判别（**不**用 duck type——multiprocessing.Queue 跨进程必须真 multiprocessing）
- `use_multiprocessing=False` 路径用 `queue.Queue`，给单进程测试用
- **不**做心跳（ADR §7.5 暂不实现）

## Acceptance criteria

- [ ] `from core.engine.bus import EngineBus` import 成功
- [ ] `tests/core/test_engine_bus.py` 覆盖：
  - default 注入：两个 `None` 时按 `use_multiprocessing` 选正确 queue 类型
  - 双向 round-trip：put_cmd → get_cmd 字段一致；put_evt → get_evt 字段一致
  - 序列化：跨进程的 dict 通过 `json.dumps/loads` 正确（用 mock `multiprocessing.Queue` 验证 bytes 形态）
  - 错误传播：`get_cmd` 收到坏 dict 抛 ValueError，**不**被吞
- [ ] `python -m pytest tests/` 全绿（含 v0-issue-3 v0-issue-4 测试）
- [ ] 跨进程 smoke 测试：spawn 一个子进程 + 真 `multiprocessing.Queue`，put/get 一条 cmd 成功（**单测之外**的 ad-hoc 验证即可）

## Blocked by

- #23（v0-issue-1 仓库骨架）
- #25（v0-issue-3 命令 schema）
- #26（v0-issue-4 事件 schema）
