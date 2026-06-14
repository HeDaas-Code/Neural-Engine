# 30 · 消息协议

> **TL;DR**：3 Cmd + 6 Evt，全部 JSON dict，`snake_case` 字段，schema 一旦发布不向后兼容改。

## GUI → Engine（Cmd，3 个）—— v0-issue-3

```python
# 1. LoadChapterCmd
{"cmd": "load_chapter", "path": "chapters/chapter01.md"}

# 2. UserInputCmd
{"cmd": "user_input", "value": "玩家输入的文本"}

# 3. ShutdownCmd
{"cmd": "shutdown"}
```

**验收**（v0-issue-3 acceptance，待实现）：
- `core/engine/protocol.py` 暴露 `Cmd` 基类 + 三个 dataclass 子类
- 每个子类含 `to_dict() -> dict` 与 `from_dict(d) -> Cmd`
- 字段 snake_case（`path` / `value`），无 datetime / 自定义对象
- 未知 cmd 类型 `from_dict` 抛 `ValueError`，错误信息含 cmd 名
- `runtime/protocol.py` 通过 re-export 共享（占位文件 + `__all__`）

## Engine → GUI（Evt，6 个）—— v0-issue-4

```python
# ADR §7.4 权威定义
{"event": "text", "content": "渲染的文本", "style": "narration"}     # narration | echo
{"event": "prompt_input", "var": "p_tall"}                          # 等用户输入
{"event": "decorator", "name": "style", "args": [...]}              # 修饰器广播
{"event": "route", "target": "chapter02"}                           # 章节路由
{"event": "chapter_end"}                                            # 章节结束
{"event": "log", "level": "info", "message": "..."}                 # info | warn | error
```

**验收**（v0-issue-4 acceptance，待实现）：
- `Evt` 基类 + 6 个 dataclass
- `DecoratorEvent.args` 类型 `list[str]`，允许空（休止符场景）
- `RouteEvent.target` 字段存在且非空（v0 强制 chapter 路由）
- `LogEvent.level` 限定为 `Literal["info", "warn", "error"]`

## Python 类型契约

```python
# core/engine/protocol.py
from dataclasses import dataclass, asdict
from typing import Literal

# ── Cmd ──
@dataclass
class Cmd: ...

@dataclass
class LoadChapterCmd(Cmd):
    path: str

@dataclass
class UserInputCmd(Cmd):
    value: str

@dataclass
class ShutdownCmd(Cmd):
    pass    # v0 无字段（注意与之前版本的 `reason` 字段差异）

# ── Evt ──
@dataclass
class Evt: ...

@dataclass
class TextEvt(Evt):
    content: str
    style: Literal["narration", "echo"]

@dataclass
class PromptInputEvt(Evt):
    var: str

@dataclass
class DecoratorEvent(Evt):
    name: str
    args: list[str]

@dataclass
class RouteEvt(Evt):
    target: str

@dataclass
class ChapterEndedEvent(Evt):
    pass

@dataclass
class LogEvt(Evt):
    level: Literal["info", "warn", "error"]
    message: str
```

## 字段命名 & JSON 兼容性

- `snake_case`，**全字段**可逆（无 datetime / 自定义对象 / bytes）
- dataclass 字段名 ↔ JSON key 一一对应（避免重命名空间）
- 新增字段只能加**可选**字段（带默认值），**不删**字段，**不改**字段名

## 端到端事件流（ADR 附录 A 入口块）

```
# 引擎启动后
→ LoadChapterCmd("chapters/chapter01.md")

# === id:start 块 ===
TextEvt("雨夜。", "narration")
TextEvt("雨声从破旧窗户的缝隙中渗入。", "narration")
TextEvt("你坐在窗边，听着雨声。", "narration")
DecoratorEvent("style", ["bgm:rain.mp3"])
PromptInputEvt("p_mood")
# GUI 发 UserInputCmd("平静")
TextEvt("平静", "echo")
# node end → NEXT=(None,"c1") 跳 c1

# === id:c1 块 ===
TextEvt("你听到门外传来两声敲门。", "narration")
PromptInputEvt("p_pick")
# GUI 发 UserInputCmd("1")
LogEvt("info", "条件打桩")
# node if 永远选第一分支 → NEXT=ref(t_a)=(None,"ca") 跳 ca

# === id:ca 块 ===
DecoratorEvent("style", ["bgm:storm.mp3"])
TextEvt("你打开门，雨中站着一个人。", "narration")
# node end → NEXT=null + id:ca 是普通 id（无 chapterYY）→ ChapterEndEvt

ChapterEndEvt
```

→ 相关：[[bus]] / [[../20-architecture/multi-process]] / `#43` `#44`（HITL）

## 原文快照（核对用）

本 wiki 页是分析层，下面是仓库原文快照以备核对：

- [[raw-docs/ADR-0001-v0-baseline-script-spec §7.3]]
- [[raw-docs/ADR-0001-v0-baseline-script-spec §7.4]]
- [[raw-docs/工程笔记/v0-issue-3-cmd.md]]
- [[raw-docs/工程笔记/v0-issue-4-evt.md]]