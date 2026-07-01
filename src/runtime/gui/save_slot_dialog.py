"""SaveSlotDialog —— v3-05 存档槽位网格对话框（缩略图）。

职责：
- 网格布局展示所有存档槽位（QGridLayout，3 列）
- 每格：缩略图 QLabel + slot 名 + 时间戳
- 点击格 → 选中（高亮）→ 底部按钮 Save/Load/Delete
- PyQt6 lazy import + qt dict 注入（测试隔离）

设计（仿 pyqt6_main 模式）：
- 模块顶层不 import PyQt6（D3 决策）
- `_build_save_slot_dialog_class(qt=None)` 动态构造 QDialog 子类
- 接受 qt dict 注入（含 QDialog/QGridLayout/QLabel/QPushButton/QWidget/QVBoxLayout/QHBoxLayout/QPixmap）
- 无 PyQt6 时降级：工厂函数抛 RuntimeError（与 pyqt6_main._run_with_sinks 一致）

UI 结构：
```
┌─────────────────────────────────────────┐
│  存档管理                                 │
├─────────────────────────────────────────┤
│  ┌──────┐ ┌──────┐ ┌──────┐              │
│  │ 图01 │ │ 图02 │ │ 图03 │              │
│  │ 01   │ │ 02   │ │ 03   │              │
│  │ 时间 │ │ 时间 │ │ 时间 │              │
│  └──────┘ └──────┘ └──────┘              │
│  ...                                     │
├─────────────────────────────────────────┤
│  [保存到该槽位] [读取] [删除] [取消]      │
└─────────────────────────────────────────┘
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _import_pyqt6() -> dict:
    """Lazy import PyQt6 modules needed for SaveSlotDialog。"""
    from PyQt6.QtCore import Qt, pyqtSignal
    from PyQt6.QtGui import QPixmap
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QGridLayout, QLabel, QPushButton,
        QWidget, QHBoxLayout, QScrollArea,
    )
    return {
        "QDialog": QDialog, "QVBoxLayout": QVBoxLayout,
        "QGridLayout": QGridLayout, "QLabel": QLabel,
        "QPushButton": QPushButton, "QWidget": QWidget,
        "QHBoxLayout": QHBoxLayout, "QScrollArea": QScrollArea,
        "QPixmap": QPixmap, "Qt": Qt, "pyqtSignal": pyqtSignal,
    }


# 默认槽位数（固定网格 01-09）
_DEFAULT_SLOT_COUNT = 9
# 网格列数
_GRID_COLUMNS = 3
# 缩略图尺寸
_THUMB_WIDTH = 160
_THUMB_HEIGHT = 90


def _build_save_slot_dialog_class(qt: Optional[dict] = None):
    """动态构造 SaveSlotDialog Qt 子类（继承 qt["QDialog"]）。

    Args:
        qt: PyQt6 modules dict（测试可注入 fake）。None 时 lazy import。
            需含 QDialog/QVBoxLayout/QGridLayout/QLabel/QPushButton/QWidget/QHBoxLayout/QPixmap。

    Returns:
        SaveSlotDialog class（type）

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
    QGridLayout = qt["QGridLayout"]
    QLabel = qt["QLabel"]
    QPushButton = qt["QPushButton"]
    QWidget = qt["QWidget"]
    QHBoxLayout = qt["QHBoxLayout"]
    QPixmap = qt.get("QPixmap")

    class SaveSlotDialog(QDialog):
        """v3-05 存档槽位网格对话框。

        用法：
            DialogCls = _build_save_slot_dialog_class(qt=qt)
            dialog = DialogCls(save_manager=mgr, parent=main_window)
            if dialog.exec():  # 用户确认
                slot = dialog.get_selected_slot()
                if dialog.action == "save":
                    ...  # 保存到 slot
                elif dialog.action == "load":
                    ...  # 从 slot 读取
        """

        # 类级常量（测试可访问）
        DEFAULT_SLOT_COUNT = _DEFAULT_SLOT_COUNT
        GRID_COLUMNS = _GRID_COLUMNS
        THUMB_WIDTH = _THUMB_WIDTH
        THUMB_HEIGHT = _THUMB_HEIGHT

        def __init__(
            self,
            save_manager=None,
            parent=None,
            slot_count: int = _DEFAULT_SLOT_COUNT,
        ):
            """Args:
                save_manager: SaveManager 实例（用于读 list_slots_with_meta / get_screenshot）。
                    None 时网格仍可显示空槽位（不读截图）。
                parent: 父 QWidget
                slot_count: 显示的槽位数（默认 9，即 01-09）
            """
            super().__init__(parent)
            self.setWindowTitle("存档管理")
            self._save_manager = save_manager
            self._slot_count = slot_count
            self._selected_slot: Optional[str] = None
            self._action: Optional[str] = None  # "save" / "load" / "delete" / None
            self._cells: dict[str, QWidget] = {}  # slot → cell widget

            # 布局
            layout = QVBoxLayout(self)

            # 网格容器（QScrollArea 包裹，槽位多时可滚动）
            self._grid_container = QWidget()
            self._grid_layout = QGridLayout(self._grid_container)
            layout.addWidget(self._grid_container)

            # 底部按钮
            btn_layout = QHBoxLayout()
            self._save_btn = QPushButton("保存到该槽位")
            self._load_btn = QPushButton("读取该槽位")
            self._delete_btn = QPushButton("删除")
            self._cancel_btn = QPushButton("取消")
            btn_layout.addWidget(self._save_btn)
            btn_layout.addWidget(self._load_btn)
            btn_layout.addWidget(self._delete_btn)
            btn_layout.addWidget(self._cancel_btn)
            layout.addLayout(btn_layout)

            # 信号槽绑定
            try:
                self._save_btn.clicked.connect(self._on_save)
                self._load_btn.clicked.connect(self._on_load)
                self._delete_btn.clicked.connect(self._on_delete)
                self._cancel_btn.clicked.connect(self._on_cancel)
            except Exception as e:
                logger.warning("SaveSlotDialog 信号绑定失败: %s", e)

            # 初始：未选中时禁用 Save/Load/Delete
            self._update_button_states()

            # 填充网格
            self.refresh()

        # ─── 公开 API ──────────────────────────────────────────────────

        def refresh(self) -> None:
            """重新读取槽位并重建网格。"""
            self._clear_grid()
            slots_meta = self._load_slots_meta()
            for i, slot_info in enumerate(slots_meta):
                row = i // _GRID_COLUMNS
                col = i % _GRID_COLUMNS
                cell = self._build_cell(slot_info)
                self._grid_layout.addWidget(cell, row, col)
                self._cells[slot_info["slot"]] = cell

        def get_selected_slot(self) -> Optional[str]:
            """取当前选中的 slot 名（None=未选中）。"""
            return self._selected_slot

        @property
        def action(self) -> Optional[str]:
            """取用户选择的动作（"save"/"load"/"delete"/None）。"""
            return self._action

        # ─── 内部方法 ──────────────────────────────────────────────────

        def _load_slots_meta(self) -> list[dict]:
            """构造 slot 元数据列表（含空槽位）。

            若 save_manager 提供，合并已有存档 + 空槽位（01-{slot_count:02d}）。
            """
            # 默认空槽位 01, 02, ..., 0N
            default_slots = [f"{i:02d}" for i in range(1, self._slot_count + 1)]
            # 已有存档元数据（若 save_manager 提供）
            existing_meta: dict[str, dict] = {}
            if self._save_manager is not None:
                try:
                    for m in self._save_manager.list_slots_with_meta():
                        existing_meta[m["slot"]] = m
                except Exception as e:
                    logger.warning("SaveSlotDialog 读 list_slots_with_meta 失败: %s", e)

            # 合并：default_slots + 额外已有存档（不在默认范围内的）
            all_slots = sorted(set(default_slots) | set(existing_meta.keys()))
            result = []
            for slot in all_slots:
                if slot in existing_meta:
                    result.append(existing_meta[slot])
                else:
                    result.append({
                        "slot": slot,
                        "has_screenshot": False,
                        "mtime": "",
                        "size": 0,
                    })
            return result

        def _build_cell(self, slot_info: dict) -> QWidget:
            """构造单个槽位格（缩略图 + slot 名 + 时间戳）。"""
            cell = QWidget()
            cell_layout = QVBoxLayout(cell)

            # 缩略图
            thumb_label = QLabel()
            screenshot_bytes = self._load_screenshot(slot_info["slot"])
            if screenshot_bytes is not None and QPixmap is not None:
                try:
                    pm = QPixmap()
                    pm.loadFromData(screenshot_bytes)
                    # 缩放到固定尺寸（保持比例）
                    if hasattr(pm, "scaled"):
                        pm = pm.scaled(
                            _THUMB_WIDTH, _THUMB_HEIGHT,
                            # Qt.AspectRatioMode.KeepAspectRatio = 1
                            # Qt.TransformationMode.SmoothTransformation = 1
                            1, 1,
                        )
                    thumb_label.setPixmap(pm)
                except Exception as e:
                    logger.debug("SaveSlotDialog 缩略图加载失败: %s", e)
                    thumb_label.setText("(空)")
            else:
                thumb_label.setText("(空)")

            # slot 名
            name_label = QLabel(slot_info["slot"])
            # 时间戳（截短显示）
            mtime = slot_info.get("mtime", "")
            if mtime and len(mtime) > 16:
                mtime = mtime[:16].replace("T", " ")
            time_label = QLabel(mtime if mtime else "—")

            cell_layout.addWidget(thumb_label)
            cell_layout.addWidget(name_label)
            cell_layout.addWidget(time_label)

            # 点击选中
            try:
                cell.mousePressEvent = lambda e, s=slot_info["slot"]: self._on_select(s)
            except Exception:
                pass

            # 记录子 widget 引用（测试可访问）
            cell._thumb_label = thumb_label
            cell._name_label = name_label
            cell._time_label = time_label
            cell._slot = slot_info["slot"]
            return cell

        def _load_screenshot(self, slot: str) -> Optional[bytes]:
            """从 save_manager 读截图 bytes（None=无截图或无 mgr）。"""
            if self._save_manager is None:
                return None
            try:
                return self._save_manager.get_screenshot(slot)
            except Exception as e:
                logger.debug("SaveSlotDialog get_screenshot 失败: %s", e)
                return None

        def _clear_grid(self) -> None:
            """清空网格中的所有 cell。"""
            try:
                while self._grid_layout.count():
                    item = self._grid_layout.takeAt(0)
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
                logger.debug("SaveSlotDialog _clear_grid 失败: %s", e)
            self._cells.clear()

        def _on_select(self, slot: str) -> None:
            """点击格 → 选中 slot。"""
            self._selected_slot = slot
            self._update_button_states()

        def _update_button_states(self) -> None:
            """根据选中状态更新底部按钮启用/禁用。"""
            selected = self._selected_slot is not None
            try:
                self._save_btn.setEnabled(selected)
                self._load_btn.setEnabled(selected)
                self._delete_btn.setEnabled(selected)
            except Exception:
                pass

        # ─── 按钮事件 ──────────────────────────────────────────────────

        def _on_save(self) -> None:
            self._action = "save"
            try:
                self.accept()
            except Exception:
                pass

        def _on_load(self) -> None:
            self._action = "load"
            try:
                self.accept()
            except Exception:
                pass

        def _on_delete(self) -> None:
            self._action = "delete"
            try:
                self.accept()
            except Exception:
                pass

        def _on_cancel(self) -> None:
            self._action = None
            self._selected_slot = None
            try:
                self.reject()
            except Exception:
                pass

    return SaveSlotDialog


__all__ = ["_build_save_slot_dialog_class", "_import_pyqt6"]
