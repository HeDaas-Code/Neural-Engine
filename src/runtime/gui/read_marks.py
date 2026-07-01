"""ReadMarks —— v3-07 已读标记追踪（#97）。

职责：
- 追踪已显示过的文本内容（按内容字符串去重）
- 支持持久化到 JSON 文件（跨会话记忆，可选）
- 提供查询 API：is_read / count / clear
- 纯 Python（无 PyQt6 依赖），便于测试

设计：
- 用 set 存储 text 字符串（O(1) 查询）
- 持久化格式：JSON array of strings（D2 决策风格）
- 不存 TextEvt 全字段（speaker/style 不影响"是否读过"语义）
- mark(None)/mark("") 静默（防御性）

集成点（MainWindow）：
- _handle_evt(TextEvt) → after render → self._read_marks.mark(evt.content)
- HistoryDialog 可选用 is_read 改样式（v3-07 暂不接入 UI）
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from core.engine.protocol import TextEvt

logger = logging.getLogger(__name__)


# 默认持久化路径（与 SaveManager 一致的 ~/.neural-engine 目录）
_DEFAULT_MARKS_FILE = Path.home() / ".neural-engine" / "read_marks.json"


class ReadMarks:
    """v3-07 已读标记追踪器。

    用法：
        marks = ReadMarks()  # 内存模式
        marks.mark("雨夜。")
        marks.is_read("雨夜。")  # True
        marks.is_read("晴天。")  # False

        # 持久化模式
        marks = ReadMarks(marks_file="/path/to/read_marks.json")
        marks.mark("foo")
        marks.save()  # 显式保存
    """

    def __init__(self, marks_file: Optional[Path | str] = None):
        """Args:
            marks_file: 持久化文件路径。None → 仅内存（不读写文件）。
                给定路径时构造即加载（若文件存在）。
        """
        self._marks: set[str] = set()
        self._file: Optional[Path] = Path(marks_file) if marks_file else None
        if self._file is not None:
            self._load()

    def mark(self, text: str) -> bool:
        """标记文本为已读。

        Args:
            text: 文本内容（None/空字符串静默忽略）。

        Returns:
            True —— 新增（之前未读）；False —— 已存在或被忽略。
        """
        if not text:
            return False
        if text in self._marks:
            return False
        self._marks.add(text)
        return True

    def mark_evt(self, evt: TextEvt) -> bool:
        """从 TextEvt 提取 content 标记（便捷方法）。"""
        if evt is None:
            return False
        return self.mark(getattr(evt, "content", ""))

    def is_read(self, text: str) -> bool:
        """查询文本是否已读。"""
        return text in self._marks

    def clear(self) -> None:
        """清空所有已读标记（内存；不删文件）。"""
        self._marks.clear()

    @property
    def count(self) -> int:
        """已标记的文本数。"""
        return len(self._marks)

    @property
    def is_empty(self) -> bool:
        return len(self._marks) == 0

    def get_all(self) -> list[str]:
        """取所有已读文本（sorted，便于断言稳定）。"""
        return sorted(self._marks)

    # ─── 持久化 ───────────────────────────────────────────────────────────

    def save(self) -> bool:
        """保存到 marks_file。无 file 或写失败 → False。

        Returns:
            True —— 成功；False —— 无文件 / 写失败。
        """
        if self._file is None:
            return False
        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            self._file.write_text(
                json.dumps(
                    sorted(self._marks), ensure_ascii=False, indent=2,
                ),
                encoding="utf-8",
            )
            return True
        except OSError as e:
            logger.warning("ReadMarks.save failed: %s", e)
            return False

    def _load(self) -> None:
        """从 file 加载（文件不存在 / 解析失败 → 静默忽略）。"""
        if self._file is None or not self._file.exists():
            return
        try:
            data = json.loads(self._file.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                return
            for item in data:
                if isinstance(item, str):
                    self._marks.add(item)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("ReadMarks._load failed: %s", e)


__all__ = ["ReadMarks"]
