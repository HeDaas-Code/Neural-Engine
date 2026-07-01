"""SettingsDialog —— v3-08 设置对话框（#98）。

职责：
- 表单式编辑 SettingsManager 的配置项
- 文本速度 / Auto 延迟 / 三轨音量 / 全屏
- 确定按钮 → 收集表单值 + accept；取消按钮 → reject
- PyQt6 lazy import + qt dict 注入（测试隔离）

设计（仿 HistoryDialog / SaveSlotDialog 模式）：
- 模块顶层不 import PyQt6（D3 决策）
- `_build_settings_dialog_class(qt=None)` 动态构造 QDialog 子类
- 无 PyQt6 时工厂函数抛 RuntimeError

UI 结构：
```
┌─────────────────────────────────────────┐
│  设置                                     │
├─────────────────────────────────────────┤
│  文本速度 (ms):  [  40  ]                 │
│  Auto 延迟 (ms): [ 1500  ]                │
│  BGM 音量:       [====○====] 0.7          │
│  SE 音量:        [========○] 1.0          │
│  Voice 音量:     [========○] 1.0          │
│  全屏:           [✓]                       │
├─────────────────────────────────────────┤
│                       [确定] [取消]       │
└─────────────────────────────────────────┘
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _import_pyqt6() -> dict:
    """Lazy import PyQt6 modules needed for SettingsDialog。"""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
        QWidget, QSpinBox, QDoubleSpinBox, QCheckBox,
    )
    return {
        "QDialog": QDialog, "QVBoxLayout": QVBoxLayout,
        "QHBoxLayout": QHBoxLayout, "QFormLayout": QFormLayout,
        "QLabel": QLabel, "QPushButton": QPushButton, "QWidget": QWidget,
        "QSpinBox": QSpinBox, "QDoubleSpinBox": QDoubleSpinBox,
        "QCheckBox": QCheckBox, "Qt": Qt,
    }


# 配置项 schema（key → (label, widget_kind, range_or_step)）
# widget_kind: "int" / "float" / "bool"
_SETTINGS_FIELDS = [
    ("text_speed",   "文本速度 (ms):",  "int",   (0, 500, 1)),
    ("auto_delay",   "Auto 延迟 (ms):", "int",   (0, 10000, 100)),
    ("bgm_volume",   "BGM 音量:",       "float", (0.0, 1.0, 0.05)),
    ("se_volume",    "SE 音量:",        "float", (0.0, 1.0, 0.05)),
    ("voice_volume", "Voice 音量:",     "float", (0.0, 1.0, 0.05)),
    ("fullscreen",   "全屏:",           "bool",  None),
]


def _build_settings_dialog_class(qt: Optional[dict] = None):
    """动态构造 SettingsDialog Qt 子类（继承 qt["QDialog"]）。

    Args:
        qt: PyQt6 modules dict（测试可注入 fake）。None 时 lazy import。
            需含 QDialog/QVBoxLayout/QHBoxLayout/QFormLayout/QLabel/QPushButton/
            QWidget/QSpinBox/QDoubleSpinBox/QCheckBox。

    Returns:
        SettingsDialog class（type）

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
    QFormLayout = qt["QFormLayout"]
    QLabel = qt["QLabel"]
    QPushButton = qt["QPushButton"]
    QWidget = qt["QWidget"]
    QSpinBox = qt.get("QSpinBox")
    QDoubleSpinBox = qt.get("QDoubleSpinBox")
    QCheckBox = qt.get("QCheckBox")

    class SettingsDialog(QDialog):
        """v3-08 设置对话框。

        用法：
            DialogCls = _build_settings_dialog_class(qt=qt)
            dialog = DialogCls(settings_manager=mgr, parent=main_window)
            if dialog.exec():  # 用户点确定
                new_settings = dialog.get_settings()
                mgr.set_many(new_settings)
                mgr.save()
        """

        def __init__(self, settings_manager=None, parent=None):
            super().__init__(parent)
            self.setWindowTitle("设置")
            self._settings_manager = settings_manager
            self._widgets: dict = {}  # key → widget
            self._accepted = False

            # 主布局
            layout = QVBoxLayout(self)

            # 表单
            form = QFormLayout() if QFormLayout is not None else None
            if form is not None:
                layout.addLayout(form)
            else:
                # 降级：无 QFormLayout 时用 QVBoxLayout（罕见）
                form = layout

            # 初始值（从 settings_manager 取，None 时用默认）
            from runtime.settings import DEFAULT_SETTINGS
            initial = dict(DEFAULT_SETTINGS)
            if settings_manager is not None:
                try:
                    initial = settings_manager.get_all()
                except Exception:
                    pass

            # 构造各字段
            for key, label_text, kind, range_info in _SETTINGS_FIELDS:
                value = initial.get(key)
                widget = self._build_field(key, kind, range_info, value)
                if widget is not None:
                    self._widgets[key] = widget
                    label = QLabel(label_text)
                    if hasattr(form, "addRow"):
                        form.addRow(label, widget)
                    else:
                        # 降级 fallback
                        try:
                            form.addWidget(label)
                            form.addWidget(widget)
                        except Exception:
                            pass

            # 底部按钮
            btn_layout = QHBoxLayout()
            self._ok_btn = QPushButton("确定")
            self._cancel_btn = QPushButton("取消")
            if hasattr(btn_layout, "addStretch"):
                btn_layout.addStretch(1)
            btn_layout.addWidget(self._ok_btn)
            btn_layout.addWidget(self._cancel_btn)
            layout.addLayout(btn_layout)

            # 信号槽
            try:
                self._ok_btn.clicked.connect(self._on_ok)
            except Exception as e:
                logger.warning("SettingsDialog ok 信号绑定失败: %s", e)
            try:
                self._cancel_btn.clicked.connect(self._on_cancel)
            except Exception as e:
                logger.warning("SettingsDialog cancel 信号绑定失败: %s", e)

        # ─── 公开 API ──────────────────────────────────────────────────

        def get_settings(self) -> dict:
            """收集表单当前值。返回 dict（key → value）。"""
            result = {}
            for key, _, kind, _ in _SETTINGS_FIELDS:
                widget = self._widgets.get(key)
                if widget is None:
                    continue
                try:
                    if kind == "int":
                        result[key] = int(widget.value())
                    elif kind == "float":
                        result[key] = float(widget.value())
                    elif kind == "bool":
                        # QCheckBox.isChecked()
                        if hasattr(widget, "isChecked"):
                            result[key] = bool(widget.isChecked())
                        elif hasattr(widget, "checkState"):
                            result[key] = bool(widget.checkState())
                        else:
                            result[key] = bool(widget.value())
                except Exception as e:
                    logger.debug("get_settings %s failed: %s", key, e)
            return result

        def set_settings(self, settings: dict) -> None:
            """设置表单初始值（构造后调用）。"""
            for key, _, kind, _ in _SETTINGS_FIELDS:
                if key not in settings:
                    continue
                widget = self._widgets.get(key)
                if widget is None:
                    continue
                value = settings[key]
                try:
                    if kind == "int":
                        widget.setValue(int(value))
                    elif kind == "float":
                        widget.setValue(float(value))
                    elif kind == "bool":
                        if hasattr(widget, "setChecked"):
                            widget.setChecked(bool(value))
                        elif hasattr(widget, "setCheckState"):
                            widget.setCheckState(bool(value))
                        elif hasattr(widget, "setValue"):
                            widget.setValue(bool(value))
                except Exception as e:
                    logger.debug("set_settings %s failed: %s", key, e)

        @property
        def was_accepted(self) -> bool:
            """用户是否点确定（exec 返回 True 后查）。"""
            return self._accepted

        @property
        def field_count(self) -> int:
            """表单字段数（测试断言用）。"""
            return len(self._widgets)

        # ─── 内部方法 ──────────────────────────────────────────────────

        def _build_field(self, key, kind, range_info, value):
            """构造单个字段 widget。"""
            try:
                if kind == "int":
                    if QSpinBox is None:
                        return None
                    w = QSpinBox()
                    lo, hi, step = range_info if range_info else (0, 9999, 1)
                    w.setMinimum(lo)
                    w.setMaximum(hi)
                    w.setSingleStep(step)
                    if value is not None:
                        w.setValue(int(value))
                    return w
                elif kind == "float":
                    if QDoubleSpinBox is None:
                        return None
                    w = QDoubleSpinBox()
                    lo, hi, step = range_info if range_info else (0.0, 1.0, 0.05)
                    w.setMinimum(lo)
                    w.setMaximum(hi)
                    w.setSingleStep(step)
                    w.setDecimals(2)
                    if value is not None:
                        w.setValue(float(value))
                    return w
                elif kind == "bool":
                    if QCheckBox is None:
                        return None
                    w = QCheckBox()
                    if value is not None:
                        w.setChecked(bool(value))
                    return w
            except Exception as e:
                logger.debug("_build_field %s failed: %s", key, e)
                return None
            return None

        def _on_ok(self) -> None:
            """确定 → 标记 accepted + accept。"""
            self._accepted = True
            try:
                self.accept()
            except Exception:
                pass

        def _on_cancel(self) -> None:
            """取消 → reject。"""
            self._accepted = False
            try:
                self.reject()
            except Exception:
                pass

    return SettingsDialog


__all__ = ["_build_settings_dialog_class", "_import_pyqt6"]
