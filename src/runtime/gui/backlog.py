"""BackLog —— v3-06 历史文本累积（BackLog）。

职责：
- 累积所有 TextEvt 的文本（供 HistoryDialog 回看）
- 维护 entry 列表：{text, speaker, style, timestamp}
- 容量上限（默认 200 条，超出自动丢弃最旧条目）
- 纯 Python（无 PyQt6 依赖），便于测试

设计：
- 不直接依赖 PyQt6（与 TextRenderer 分离，BackLog 只管数据）
- MainWindow._handle_evt(TextEvt) → self._backlog.add(evt)
- HistoryDialog 通过 `backlog.get_entries()` 取数据展示

v3-06 简化：
- 不去重（同文本多次出现都保留，AVG 场景重复对话常见）
- 不存装饰器状态（@style/@bg 仅是瞬时效果，历史只看文本）
- timestamp 用 time.time()（ISO 字符串化在 HistoryDialog 处理）
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from core.engine.protocol import TextEvt

logger = logging.getLogger(__name__)


# 默认容量上限（超出自动丢最旧）
_DEFAULT_MAX_ENTRIES = 200


class BackLog:
    """v3-06 历史文本累积器。

    用法：
        backlog = BackLog(max_entries=200)
        backlog.add(TextEvt(content="雨夜。", style="narration"))
        backlog.add(TextEvt(content="你好。", speaker="alice", style="dialog"))
        entries = backlog.get_entries()
        # [{"text": "雨夜。", "speaker": None, "style": "narration", "ts": ...}, ...]
    """

    def __init__(self, max_entries: int = _DEFAULT_MAX_ENTRIES):
        """Args:
            max_entries: 容量上限。超出时丢弃最旧条目（FIFO）。<=0 视为无限。
        """
        self._entries: list[dict] = []
        self._max_entries = max_entries if max_entries > 0 else 0  # 0=无限

    def add(self, evt: TextEvt) -> None:
        """追加一个 TextEvt 到历史。

        Args:
            evt: TextEvt（取 content / speaker / style）
        """
        if evt is None:
            return
        entry = {
            "text": getattr(evt, "content", ""),
            "speaker": getattr(evt, "speaker", None),
            "style": getattr(evt, "style", None),
            "ts": time.time(),
        }
        self._entries.append(entry)
        self._trim_if_needed()

    def add_text(
        self,
        text: str,
        speaker: Optional[str] = None,
        style: Optional[str] = None,
    ) -> None:
        """直接追加文本（不经 TextEvt，测试 / 调试用）。"""
        self._entries.append({
            "text": text,
            "speaker": speaker,
            "style": style,
            "ts": time.time(),
        })
        self._trim_if_needed()

    def get_entries(self) -> list[dict]:
        """取所有历史条目（返回副本，外部修改不影响内部）。

        每项含：text / speaker / style / ts（Unix timestamp float）。
        """
        return [dict(e) for e in self._entries]

    def clear(self) -> None:
        """清空所有历史。"""
        self._entries.clear()

    @property
    def max_entries(self) -> int:
        return self._max_entries

    @property
    def count(self) -> int:
        """当前条目数。"""
        return len(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def is_empty(self) -> bool:
        return len(self._entries) == 0

    def latest(self, n: int = 10) -> list[dict]:
        """取最近 n 条（不足则全返）。"""
        if n <= 0:
            return []
        return [dict(e) for e in self._entries[-n:]]

    # ─── 内部方法 ─────────────────────────────────────────────────────────

    def _trim_if_needed(self) -> None:
        """超过 max_entries 时丢弃最旧条目。"""
        if self._max_entries <= 0:
            return
        while len(self._entries) > self._max_entries:
            self._entries.pop(0)


__all__ = ["BackLog"]
