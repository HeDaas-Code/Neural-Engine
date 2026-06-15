## Parent

#22（PRD-0001 父 issue）

## What to build

`src/core/engine/protocol.py` 提供 §7.3 命令 dataclass（GUI → Engine 方向）。

3 条命令：
- `LoadChapterCmd(path: str)` → `{"cmd": "load_chapter", "path": "..."}`
- `UserInputCmd(value: str)` → `{"cmd": "user_input", "value": "..."}`
- `ShutdownCmd()` → `{"cmd": "shutdown"}`

每条 dataclass 提供：
- `to_dict() -> dict`（**只**返回 dict，不做 json.dumps——序列化由 bus 负责）
- `@classmethod from_dict(cls, d: dict) -> Self`（**只**做字段拷贝，不做 json.loads）
- 字段名严格匹配 ADR §7.3 snake_case
- 抛 `ValueError` 当字段缺失或类型错（**不**用 ProtocolError——本轮 spec 决策）

外加 `parse_cmd(d: dict) -> Cmd` 工厂函数：按 `d["cmd"]` 字段分发到对应 from_dict。

## Acceptance criteria

- [ ] `from core.engine.protocol import LoadChapterCmd, UserInputCmd, ShutdownCmd, parse_cmd` import 成功
- [ ] `tests/core/test_protocol_cmd.py` 覆盖：
  - 3 条 dataclass round-trip（to_dict → from_dict 字段一致）
  - `parse_cmd` 按 `cmd` 字段正确分发
  - 字段缺失 / 字段类型错 抛 `ValueError`
  - **不**做 json 序列化测试（本 issue 边界）
- [ ] `python -m pytest tests/` 全绿

## Blocked by

- #23（v0-issue-1 仓库骨架）
- #24（v0-issue-2 AST 节点 dataclass）
