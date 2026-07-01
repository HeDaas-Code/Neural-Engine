"""HistoryDialog —— v3-06 历史回看对话框（BackLog 显示）。

职责：
- 滚动列表展示 BackLog 中的所有历史条目
- 每条：[speaker] text（speaker 为空时只显示 text）
- 关闭按钮
- PyQt6 lazy import + qt dict 注入（测试隔离）

设计（仿 SaveSlotDialog 模式）：
- 模块顶层不 import PyQt6（D3 决策）
- `_build_history_dialog_class(qt=None)` 动态构造 QDialog 子类
- 无 PyQt6 时工厂函数抛 RuntimeError

UI 结构：
```
┌─────────────────────────────────────────┐
│  历史回看                                 │
├─────────────────────────────────────────┤
│  ┌─────────────────────────────────────┐ │
│  │ [alice] 你好。                       │ │
│  │ 雨夜。                               │ │
│  │ [bob] 有人在吗？                     │ │
│  │ ...                                  │ │
│  └─────────────────────────────────────┘ │
├─────────────────────────────────────────┤
│                              [关闭]      │
└─────────────────────────────────────────┘
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def _import_pyqt6() -> dict:
    """Lazy import PyQt6 modules needed for HistoryDialog。"""
    from PyQt6.QtCore import Qt, pyqtSignal
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QWidget, QScrollArea,
    )
    return {
        "QDialog": QDialog, "QVBoxLayout": QVBoxLayout,
        "QHBoxLayout": QHBoxLayout, "QLabel": QLabel,
        "QPushButton": QPushButton, "QWidget": QWidget,
        "QScrollArea": QScrollArea, "Qt": Qt, "pyqtSignal": pyqtSignal,
    }


def _build_history_dialog_class(qt: Optional[dict] = None):
    """动态构造 HistoryDialog Qt 子类（继承 qt["QDialog"]）。

    Args:
        qt: PyQt6 modules dict（测试可注入 fake）。None 时 lazy import。
            需含 QDialog/QVBoxLayout/QHBoxLayout/QLabel/QPushButton/QWidget/QScrollArea。

    Returns:
        HistoryDialog class（type）

    Raises:
        RuntimeError: qt=None 且 PyQt6 import 失败。
    """
    if qt is None:
        try:
            qt = _import_pyqt6()
        except ImportError as e:
            raise RuntimeError(f"PyQt6 不可用: {e}") from e

    QDialog = qt["QDialog"]
    QVBoxLayout = qt["QVBoxLayout"]
    QHBoxLayout = qt["QHBoxLayout"]
    QLabel = qt["QLabel"]
    QPushButton = qt["QPushButton"]
    QWidget = qt["QWidget"]
    QScrollArea = qt.get("QScrollArea")

    class HistoryDialog(QDialog):
        """v3-06 历史回看对话框。

        用法：
            DialogCls = _build_history_dialog_class(qt=qt)
            dialog = DialogCls(parent=main_window)
            dialog.set_entries(backlog.get_entries())
            dialog.exec()
        """

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle("历史回看")
            self._entries: list[dict] = []
            self._entry_labels: list = []

            # 布局
            layout = QVBoxLayout(self)

            # 滚动区域容器
            if QScrollArea is not None:
                self._scroll = QScrollArea()
                self._scroll.setWidgetResizable(True)
                self._content_widget = QWidget()
                self._content_layout = QVBoxLayout(self._content_widget)
                self._scroll.setWidget(self._content_widget)
                layout.addWidget(self._scroll)
            else:
                # 降级：无 QScrollArea 时直接铺
                self._scroll = None
                self._content_widget = QWidget()
                self._content_layout = QVBoxLayout(self._content_widget)
                layout.addWidget(self._content_widget)

            # 底部关闭按钮
            btn_layout = QHBoxLayout()
            self._close_btn = QPushButton("关闭")
            btn_layout.addStretch(1) if hasattr(btn_layout, "addStretch") else None
            btn_layout.addWidget(self._close_btn)
            layout.addLayout(btn_layout)

            # 信号槽
            try:
                self._close_btn.clicked.connect(self._on_close)
            except Exception as e:
                logger.warning("HistoryDialog 信号绑定失败: %s", e)

        # ─── 公开 API ──────────────────────────────────────────────────

        def set_entries(self, entries: list[dict]) -> None:
            """设置历史条目并重建列表。

            Args:
                entries: list[dict]，每项含 text/speaker/style/ts
                    （ts 可选，用于显示时间戳）
            """
            # 深拷贝每个 dict（避免外部修改影响内部）
            self._entries = [dict(e) for e in entries] if entries else []
            self._rebuild_list()

        def refresh_from(self, backlog) -> None:
            """从 BackLog 实例刷新条目。

            Args:
                backlog: BackLog 实例（调 get_entries()）
            """
            if backlog is None:
                self.set_entries([])
                return
            try:
                self.set_entries(backlog.get_entries())
            except Exception as e:
                logger.warning("HistoryDialog.refresh_from 失败: %s", e)
                self.set_entries([])

        def get_entries(self) -> list[dict]:
            """取当前显示的条目（返回副本，测试断言用）。"""
            return [dict(e) for e in self._entries]

        @property
        def entry_count(self) -> int:
            return len(self._entries)

        # ─── 内部方法 ──────────────────────────────────────────────────

        def _rebuild_list(self) -> None:
            """清空 + 重建条目 label 列表。"""
            self._clear_entries()
            for entry in self._entries:
                label = self._build_entry_label(entry)
                self._content_layout.addWidget(label)
                self._entry_labels.append(label)

        def _build_entry_label(self, entry: dict) -> QLabel:
            """构造单条历史的 QLabel。

            显示格式：
            - 有 speaker："[speaker] text"
            - 无 speaker："text"
            - 有 ts（可选）：追加 "  (HH:MM:SS)" 后缀
            """
            text = entry.get("text", "")
            speaker = entry.get("speaker", None)
            ts = entry.get("ts", None)

            display = ""
            if speaker:
                display = f"[{speaker}] {text}"
            else:
                display = text

            # 时间戳后缀（HH:MM:SS）
            if ts is not None:
                try:
                    ts_str = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
                    display = f"{display}  ({ts_str})"
                except (TypeError, ValueError, OSError):
                    pass

            label = QLabel(display)
            # 测试可访问原始字段
            label._entry_text = text
            label._entry_speaker = speaker
            label._entry_style = entry.get("style", None)
            label._entry_ts = ts
            return label

        def _clear_entries(self) -> None:
            """清空条目 label 列表。"""
            try:
                while self._content_layout.count():
                    item = self._content_layout.takeAt(0)
                    if item is not None and item.widget() is not None:
                        w = item.widget()
                        try:
                            w.setParent(None)
                        except Exception:
                            pass
                        try:
                            w.deleteLater()
                        except Exception:
                            pass
            except Exception as e:
                logger.debug("HistoryDialog _clear_entries 失败: %s", e)
            self._entry_labels.clear()

        def _on_close(self) -> None:
            """关闭按钮 → accept。"""
            try:
                self.accept()
            except Exception:
                pass

    return HistoryDialog


__all__ = ["_build_history_dialog_class", "_import_pyqt6"]
