"""v0 进程间消息协议（GUI ↔ Engine）。

v0-issue-3 命令 schema + v0-issue-4 事件 schema 共用本文件（按 ADR §9 标注的复用）。

约定：
- to_dict() 只返回 dict，不做 json.dumps（序列化由 bus 负责）
- from_dict() 只做字段拷贝，不做 json.loads
- 字段缺失 / 类型错抛 ValueError

v2 扩展（EP-11 · 存档/读档）：
- `SaveCmd(slot)` —— 触发 SaveManager.save(slot, state)
- `LoadCmd(slot)` —— 触发 SaveManager.load(slot) 恢复 GameState
- `SaveAckEvt(slot, ok, [error])` —— 存档结果回执
- `LoadAckEvt(slot, ok, [error])` —— 读档结果回执
- 注册到 `_CMD_REGISTRY["save"]` / `_CMD_REGISTRY["load"]`，parse_cmd 自动分发
- 注册到 `_EVT_REGISTRY["save_ack"]` / `_EVT_REGISTRY["load_ack"]`，parse_evt 自动分发

v2 扩展（EP-06 · 修饰器事件 kind）：
- `DecoratorEvt(kind)` 新增 `kind: Literal["call", "stop"] = "call"` 字段
- 默认 "call"（向后兼容）；显式 "stop" 表示停止对应 name 的触发器
- from_dict 缺 kind 时默认 "call"（老 dict 仍能 parse）
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


_DECORATOR_KIND = Literal["call", "stop"]
_DECORATOR_KIND_ALLOWED = ("call", "stop")


def _check_dict(d: dict, name: str) -> None:
    """校验 d 是 dict + 含 cmd 字段 + cmd 是 str。"""
    if not isinstance(d, dict):
        raise ValueError(f"{name} 期望 dict，得到 {type(d).__name__}")


def _require_str(d: dict, field: str, owner: str) -> str:
    """校验 d[field] 存在且是 str，否则 ValueError。"""
    if field not in d:
        raise ValueError(f"{owner} 缺少字段 {field!r}")
    val = d[field]
    if not isinstance(val, str):
        raise ValueError(
            f"{owner}.{field} 应为 str，得到 {type(val).__name__}"
        )
    return val


def _require_str_list(d: dict, field: str, owner: str) -> list[str]:
    """校验 d[field] 存在且是 list[str]，否则 ValueError。"""
    if field not in d:
        raise ValueError(f"{owner} 缺少字段 {field!r}")
    val = d[field]
    if not isinstance(val, list):
        raise ValueError(
            f"{owner}.{field} 应为 list，得到 {type(val).__name__}"
        )
    for i, item in enumerate(val):
        if not isinstance(item, str):
            raise ValueError(
                f"{owner}.{field}[{i}] 应为 str，得到 {type(item).__name__}"
            )
    return val


# ─── 命令（GUI → Engine） ─────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class LoadChapterCmd:
    path: str

    def to_dict(self) -> dict:
        return {"cmd": "load_chapter", "path": self.path}

    @classmethod
    def from_dict(cls, d: dict) -> "LoadChapterCmd":
        _check_dict(d, "LoadChapterCmd")
        return cls(path=_require_str(d, "path", "LoadChapterCmd"))


@dataclass(frozen=True, slots=True)
class SaveCmd:
    """存档命令（GUI → Engine，v2 骨架扩展 · EP-11）。

    v2 用途：触发 SaveManager.save(slot, state) 把当前 GameState 持久化到
    `~/.neural-engine/saves/{slot}.json`（D4 决策）。
    v3+ 落地：V2-07 任务接管完整存档逻辑。
    """
    slot: str

    def to_dict(self) -> dict:
        return {"cmd": "save", "slot": self.slot}

    @classmethod
    def from_dict(cls, d: dict) -> "SaveCmd":
        _check_dict(d, "SaveCmd")
        return cls(slot=_require_str(d, "slot", "SaveCmd"))


@dataclass(frozen=True, slots=True)
class LoadCmd:
    """读档命令（GUI → Engine，v2 骨架扩展 · EP-11）。

    v2 用途：触发 SaveManager.load(slot) 恢复存档 → 替换 GameState。
    v3+ 落地：V2-07 任务接管完整读档逻辑。
    """
    slot: str

    def to_dict(self) -> dict:
        return {"cmd": "load", "slot": self.slot}

    @classmethod
    def from_dict(cls, d: dict) -> "LoadCmd":
        _check_dict(d, "LoadCmd")
        return cls(slot=_require_str(d, "slot", "LoadCmd"))


@dataclass(frozen=True, slots=True)
class UserInputCmd:
    value: str

    def to_dict(self) -> dict:
        return {"cmd": "user_input", "value": self.value}

    @classmethod
    def from_dict(cls, d: dict) -> "UserInputCmd":
        _check_dict(d, "UserInputCmd")
        return cls(value=_require_str(d, "value", "UserInputCmd"))


@dataclass(frozen=True, slots=True)
class ShutdownCmd:
    def to_dict(self) -> dict:
        return {"cmd": "shutdown"}

    @classmethod
    def from_dict(cls, d: dict) -> "ShutdownCmd":
        _check_dict(d, "ShutdownCmd")
        return cls()


# ─── 工厂函数 ────────────────────────────────────────────────────────────────


_CMD_REGISTRY = {
    "load_chapter": LoadChapterCmd,
    "save": SaveCmd,
    "load": LoadCmd,
    "user_input": UserInputCmd,
    "shutdown": ShutdownCmd,
}


def parse_cmd(d: dict):
    """按 d["cmd"] 字段分发到对应命令 dataclass。

    未知 cmd 值或缺 cmd 字段 → 抛 ValueError。
    """
    _check_dict(d, "cmd")
    cmd_name = d.get("cmd")
    if not isinstance(cmd_name, str):
        raise ValueError(f"cmd 字段应为 str，得到 {type(cmd_name).__name__}")
    if cmd_name not in _CMD_REGISTRY:
        raise ValueError(f"未知 cmd: {cmd_name!r}")
    return _CMD_REGISTRY[cmd_name].from_dict(d)


# ─── 事件（Engine → GUI） ─────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class TextEvt:
    content: str
    style: str = "narration"

    def to_dict(self) -> dict:
        return {"event": "text", "content": self.content, "style": self.style}

    @classmethod
    def from_dict(cls, d: dict) -> "TextEvt":
        _check_dict(d, "TextEvt")
        content = _require_str(d, "content", "TextEvt")
        # style 可选，默认 narration
        style = d.get("style", "narration")
        if not isinstance(style, str):
            raise ValueError(
                f"TextEvt.style 应为 str，得到 {type(style).__name__}"
            )
        return cls(content=content, style=style)


@dataclass(frozen=True, slots=True)
class PromptInputEvt:
    var: str

    def to_dict(self) -> dict:
        return {"event": "prompt_input", "var": self.var}

    @classmethod
    def from_dict(cls, d: dict) -> "PromptInputEvt":
        _check_dict(d, "PromptInputEvt")
        return cls(var=_require_str(d, "var", "PromptInputEvt"))


@dataclass(frozen=True, slots=True)
class DecoratorEvt:
    """修饰器事件（Engine → GUI，EP-06 扩展 kind 字段）。

    v0 字段：name + args（按修饰器定义触发，如 `style bgm:rain.mp3`）。
    v2 字段（EP-06）：kind ∈ {"call", "stop"}
        - "call"（默认）：触发 / 播放该修饰器（如 bgm 播放、bg 切换）
        - "stop"：停止 / 暂停该修饰器（如 bgm 停止）

    向后兼容（EP-06）：
    - to_dict 总是输出 kind（显式优于隐式）
    - from_dict 缺 kind 时默认 "call"（老 v0 dict 仍能 parse）
    - from_dict kind 非合法字面量抛 ValueError（防静默错配）

    v3+ 用途：
    - AudioManager 监听 name="bgm" → play(args[0]) / stop()
    - VideoPlayer 监听 name="video" → play(args[0])
    """
    name: str
    args: list[str]
    kind: _DECORATOR_KIND = "call"

    def to_dict(self) -> dict:
        return {
            "event": "decorator",
            "name": self.name,
            "args": list(self.args),  # 防御性拷贝
            "kind": self.kind,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DecoratorEvt":
        _check_dict(d, "DecoratorEvt")
        # kind 可选，缺时默认 "call"（EP-06 向后兼容）
        kind_raw = d.get("kind", "call")
        if not isinstance(kind_raw, str):
            raise ValueError(
                f"DecoratorEvt.kind 应为 str，得到 {type(kind_raw).__name__}"
            )
        if kind_raw not in _DECORATOR_KIND_ALLOWED:
            raise ValueError(
                f"DecoratorEvt.kind 应为 {list(_DECORATOR_KIND_ALLOWED)} 之一，"
                f"得到 {kind_raw!r}"
            )
        return cls(
            name=_require_str(d, "name", "DecoratorEvt"),
            args=_require_str_list(d, "args", "DecoratorEvt"),
            kind=kind_raw,  # type: ignore[arg-type]
        )


@dataclass(frozen=True, slots=True)
class RouteEvt:
    target: str

    def to_dict(self) -> dict:
        return {"event": "route", "target": self.target}

    @classmethod
    def from_dict(cls, d: dict) -> "RouteEvt":
        _check_dict(d, "RouteEvt")
        return cls(target=_require_str(d, "target", "RouteEvt"))


@dataclass(frozen=True, slots=True)
class ChapterEndEvt:
    def to_dict(self) -> dict:
        return {"event": "chapter_end"}

    @classmethod
    def from_dict(cls, d: dict) -> "ChapterEndEvt":
        _check_dict(d, "ChapterEndEvt")
        return cls()


@dataclass(frozen=True, slots=True)
class LogEvt:
    level: str
    message: str

    def to_dict(self) -> dict:
        return {"event": "log", "level": self.level, "message": self.message}

    @classmethod
    def from_dict(cls, d: dict) -> "LogEvt":
        _check_dict(d, "LogEvt")
        return cls(
            level=_require_str(d, "level", "LogEvt"),
            message=_require_str(d, "message", "LogEvt"),
        )


# ─── v2-p0 save-load (V2-07 · EP-11)：存档/读档回执事件 ─────────────────────
#
# GUI 进程订阅 save_ack / load_ack → 弹"存档成功"提示 / "存档槽 X 不存在"错误。
# 成功路径 error=None；失败路径 ok=False + error 含具体原因（slot 非法 / 文件缺失）。


@dataclass(frozen=True, slots=True)
class SaveAckEvt:
    """存档回执事件（Engine → GUI）。

    成功：`ok=True, error=None`
    失败：`ok=False, error="<原因>"`（如 slot 非法 / save_manager 缺失 / OSError）
    """
    slot: str
    ok: bool
    error: str | None = None

    def to_dict(self) -> dict:
        out = {"event": "save_ack", "slot": self.slot, "ok": self.ok}
        if self.error is not None:
            out["error"] = self.error
        return out

    @classmethod
    def from_dict(cls, d: dict) -> "SaveAckEvt":
        _check_dict(d, "SaveAckEvt")
        slot = _require_str(d, "slot", "SaveAckEvt")
        if "ok" not in d:
            raise ValueError("SaveAckEvt 缺少字段 'ok'")
        ok = d["ok"]
        if not isinstance(ok, bool):
            raise ValueError(
                f"SaveAckEvt.ok 应为 bool，得到 {type(ok).__name__}"
            )
        error = d.get("error")
        if error is not None and not isinstance(error, str):
            raise ValueError(
                f"SaveAckEvt.error 应为 str 或 None，得到 {type(error).__name__}"
            )
        return cls(slot=slot, ok=ok, error=error)


@dataclass(frozen=True, slots=True)
class LoadAckEvt:
    """读档回执事件（Engine → GUI）。

    成功：`ok=True, error=None`（state 已被替换）
    失败：`ok=False, error="<原因>"`（如 slot 非法 / 存档不存在 / JSON 损坏 / save_manager 缺失）
    """
    slot: str
    ok: bool
    error: str | None = None

    def to_dict(self) -> dict:
        out = {"event": "load_ack", "slot": self.slot, "ok": self.ok}
        if self.error is not None:
            out["error"] = self.error
        return out

    @classmethod
    def from_dict(cls, d: dict) -> "LoadAckEvt":
        _check_dict(d, "LoadAckEvt")
        slot = _require_str(d, "slot", "LoadAckEvt")
        if "ok" not in d:
            raise ValueError("LoadAckEvt 缺少字段 'ok'")
        ok = d["ok"]
        if not isinstance(ok, bool):
            raise ValueError(
                f"LoadAckEvt.ok 应为 bool，得到 {type(ok).__name__}"
            )
        error = d.get("error")
        if error is not None and not isinstance(error, str):
            raise ValueError(
                f"LoadAckEvt.error 应为 str 或 None，得到 {type(error).__name__}"
            )
        return cls(slot=slot, ok=ok, error=error)


# ─── 工厂函数 ────────────────────────────────────────────────────────────────


_EVT_REGISTRY = {
    "text": TextEvt,
    "prompt_input": PromptInputEvt,
    "decorator": DecoratorEvt,
    "route": RouteEvt,
    "chapter_end": ChapterEndEvt,
    "log": LogEvt,
    "save_ack": SaveAckEvt,
    "load_ack": LoadAckEvt,
}


def parse_evt(d: dict):
    """按 d["event"] 字段分发到对应事件 dataclass。

    未知 event 值或缺 event 字段 → 抛 ValueError。
    """
    _check_dict(d, "event")
    evt_name = d.get("event")
    if not isinstance(evt_name, str):
        raise ValueError(f"event 字段应为 str，得到 {type(evt_name).__name__}")
    if evt_name not in _EVT_REGISTRY:
        raise ValueError(f"未知 event: {evt_name!r}")
    return _EVT_REGISTRY[evt_name].from_dict(d)
