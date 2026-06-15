## Parent

#22（PRD-0001 父 issue）

## What to build

`src/core/engine/protocol.py` 同模块追加 §7.4 事件 dataclass（Engine → GUI 方向）。

6 条事件：
- `TextEvt(content: str, style: str = "narration")` → `{"event": "text", "content": "...", "style": "narration"}`
- `PromptInputEvt(var: str)` → `{"event": "prompt_input", "var": "..."}`
- `DecoratorEvt(name: str, args: list[str])` → `{"event": "decorator", "name": "...", "args": [...]}`
- `RouteEvt(target: str)` → `{"event": "route", "target": "..."}`
- `ChapterEndEvt()` → `{"event": "chapter_end"}`
- `LogEvt(level: str, message: str)` → `{"event": "log", "level": "...", "message": "..."}`

约定与 v0-issue-3 一致：
- `to_dict() / from_dict()` 不做 json 序列化
- 字段缺失 / 类型错抛 `ValueError`
- `parse_evt(d: dict) -> Evt` 工厂函数按 `event` 字段分发

继承 v0-issue-3 的 `ProtocolError` 决策（**保留**在 `protocol.py` 内，**不**在 v0-issue-5 bus 里新定义——本轮修正：v0-issue-3 决定不引入 ProtocolError，v0-issue-4 沿用）。

## Acceptance criteria

- [ ] `from core.engine.protocol import TextEvt, PromptInputEvt, DecoratorEvt, RouteEvt, ChapterEndEvt, LogEvt, parse_evt` 全部 import
- [ ] `tests/core/test_protocol_evt.py` 覆盖：6 条 round-trip + `parse_evt` 分发 + 字段缺失抛 ValueError
- [ ] `python -m pytest tests/` 全绿（含 v0-issue-3 的 cmd 测试）

## Blocked by

- #23（v0-issue-1 仓库骨架）
- #24（v0-issue-2 AST 节点 dataclass）
- #25（v0-issue-3 命令 schema）
