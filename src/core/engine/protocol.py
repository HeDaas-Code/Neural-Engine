"""v0 进程间消息协议（GUI ↔ Engine）。

v0-issue-3 命令 schema + v0-issue-4 事件 schema 共用本文件（按 ADR §9 标注的复用）。

约定：
- to_dict() 只返回 dict，不做 json.dumps（序列化由 bus 负责）
- from_dict() 只做字段拷贝，不做 json.loads
- 字段缺失 / 类型错抛 ValueError
"""
from __future__ import annotations

from dataclasses import dataclass


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


@dataclass(frozen=True, slots=True)
class SaveCmd:
    slot: str

    def to_dict(self) -> dict:
        return {"cmd": "save", "slot": self.slot}

    @classmethod
    def from_dict(cls, d: dict) -> "SaveCmd":
        _check_dict(d, "SaveCmd")
        return cls(slot=_require_str(d, "slot", "SaveCmd"))


@dataclass(frozen=True, slots=True)
class LoadCmd:
    slot: str

    def to_dict(self) -> dict:
        return {"cmd": "load", "slot": self.slot}

    @classmethod
    def from_dict(cls, d: dict) -> "LoadCmd":
        _check_dict(d, "LoadCmd")
        return cls(slot=_require_str(d, "slot", "LoadCmd"))


_CMD_REGISTRY = {
    "load_chapter": LoadChapterCmd,
    "user_input": UserInputCmd,
    "shutdown": ShutdownCmd,
    "save": SaveCmd,
    "load": LoadCmd,
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
    speaker: str = ""  # v3-01: 名字标签（空字符串=旁白）

    def to_dict(self) -> dict:
        d: dict = {"event": "text", "content": self.content, "style": self.style}
        if self.speaker:
            d["speaker"] = self.speaker
        return d

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
        # speaker 可选，v3-01 新增（老协议无此字段→空串=旁白）
        speaker = d.get("speaker", "")
        if not isinstance(speaker, str):
            raise ValueError(
                f"TextEvt.speaker 应为 str，得到 {type(speaker).__name__}"
            )
        return cls(content=content, style=style, speaker=speaker)


@dataclass(frozen=True, slots=True)
class PromptInputEvt:
    var: str
    options: tuple[str, ...] = ()  # v3-02: 选项列表（空=自由输入 QLineEdit）

    def to_dict(self) -> dict:
        d: dict = {"event": "prompt_input", "var": self.var}
        if self.options:
            d["options"] = list(self.options)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "PromptInputEvt":
        _check_dict(d, "PromptInputEvt")
        var = _require_str(d, "var", "PromptInputEvt")
        # v3-02: options 可选（老协议无此字段→空 tuple）
        opts_raw = d.get("options", [])
        if not isinstance(opts_raw, list):
            raise ValueError(
                f"PromptInputEvt.options 应为 list，得到 {type(opts_raw).__name__}"
            )
        opts = tuple(_require_str({"v": o}, "v", "PromptInputEvt.options") for o in opts_raw)
        return cls(var=var, options=opts)


@dataclass(frozen=True, slots=True)
class DecoratorEvt:
    name: str
    args: list[str]
    kind: str = "call"  # "call" 或 "stop"（v2-p0 装饰器钩子用）

    def to_dict(self) -> dict:
        d = {
            "event": "decorator",
            "name": self.name,
            "args": list(self.args),  # 防御性拷贝
        }
        if self.kind != "call":
            d["kind"] = self.kind
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "DecoratorEvt":
        _check_dict(d, "DecoratorEvt")
        kind = d.get("kind", "call")
        if not isinstance(kind, str):
            raise ValueError(
                f"DecoratorEvt.kind 应为 str，得到 {type(kind).__name__}"
            )
        return cls(
            name=_require_str(d, "name", "DecoratorEvt"),
            args=_require_str_list(d, "args", "DecoratorEvt"),
            kind=kind,
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


# ─── 工厂函数 ────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class SaveAckEvt:
    slot: str
    ok: bool
    error: str = ""

    def to_dict(self) -> dict:
        d = {"event": "save_ack", "slot": self.slot, "ok": self.ok}
        if self.error:
            d["error"] = self.error
        return d

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
        error = d.get("error", "")
        if not isinstance(error, str):
            raise ValueError(
                f"SaveAckEvt.error 应为 str，得到 {type(error).__name__}"
            )
        return cls(slot=slot, ok=ok, error=error)


@dataclass(frozen=True, slots=True)
class LoadAckEvt:
    slot: str
    ok: bool
    error: str = ""

    def to_dict(self) -> dict:
        d = {"event": "load_ack", "slot": self.slot, "ok": self.ok}
        if self.error:
            d["error"] = self.error
        return d

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
        error = d.get("error", "")
        if not isinstance(error, str):
            raise ValueError(
                f"LoadAckEvt.error 应为 str，得到 {type(error).__name__}"
            )
        return cls(slot=slot, ok=ok, error=error)


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
