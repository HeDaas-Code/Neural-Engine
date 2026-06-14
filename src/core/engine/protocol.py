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


_CMD_REGISTRY = {
    "load_chapter": LoadChapterCmd,
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
