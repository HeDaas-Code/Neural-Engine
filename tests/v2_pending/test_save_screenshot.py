"""v3-05 · 存档截图 + SaveSlotDialog 网格缩略图测试（#95）。

验证 issue #95 验收点：
- SaveManager.save(slot, state, screenshot=bytes) → 写 {slot}.png
- SaveManager.get_screenshot(slot) → bytes | None
- SaveManager.list_slots_with_meta() → 含 has_screenshot/mtime/size
- SaveManager.delete(slot) → 一并删 .png
- ScreenshotManager.capture(widget) → bytes | None（lazy PyQt6 + 降级 no-op）
- SaveSlotDialog 网格布局 + 缩略图 + 选中 + 动作
"""
from __future__ import annotations

import os
import sys
import types
from unittest.mock import MagicMock

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")


# ═══════════════════════════════════════════════════════════════════════
# 1. SaveManager 截图扩展
# ═══════════════════════════════════════════════════════════════════════


def test_save_with_screenshot_writes_png(tmp_path):
    """save(slot, state, screenshot=bytes) → 写 {slot}.json + {slot}.png。"""
    from runtime.save import SaveManager
    from core.engine.executor import GameState

    mgr = SaveManager(save_dir=tmp_path)
    state = GameState(vars={"x": 1}, path=[], current_block_id="start")
    png = b"\x89PNG\r\n\x1a\nfake png bytes"

    mgr.save("01", state, screenshot=png)

    assert (tmp_path / "01.json").exists()
    assert (tmp_path / "01.png").read_bytes() == png


def test_save_without_screenshot_no_png_file(tmp_path):
    """save(slot, state) 不传 screenshot → 不写 .png（向后兼容 v2）。"""
    from runtime.save import SaveManager
    from core.engine.executor import GameState

    mgr = SaveManager(save_dir=tmp_path)
    state = GameState()

    mgr.save("01", state)

    assert (tmp_path / "01.json").exists()
    assert not (tmp_path / "01.png").exists()


def test_get_screenshot_returns_bytes(tmp_path):
    """get_screenshot(slot) → 截图 PNG bytes。"""
    from runtime.save import SaveManager
    from core.engine.executor import GameState

    mgr = SaveManager(save_dir=tmp_path)
    state = GameState()
    png = b"fake png data"
    mgr.save("01", state, screenshot=png)

    assert mgr.get_screenshot("01") == png


def test_get_screenshot_returns_none_when_absent(tmp_path):
    """无截图 → None（不抛错）。"""
    from runtime.save import SaveManager
    from core.engine.executor import GameState

    mgr = SaveManager(save_dir=tmp_path)
    state = GameState()
    mgr.save("01", state)  # 无 screenshot

    assert mgr.get_screenshot("01") is None


def test_get_screenshot_returns_none_for_unknown_slot(tmp_path):
    """不存在的 slot → None。"""
    from runtime.save import SaveManager
    mgr = SaveManager(save_dir=tmp_path)
    assert mgr.get_screenshot("ghost") is None


def test_get_screenshot_returns_none_for_invalid_slot(tmp_path):
    """非法 slot 名 → None（不抛 ValueError）。"""
    from runtime.save import SaveManager
    mgr = SaveManager(save_dir=tmp_path)
    assert mgr.get_screenshot("../escape") is None


def test_list_slots_with_meta_includes_screenshot_flag(tmp_path):
    """list_slots_with_meta() → 含 has_screenshot 字段。"""
    from runtime.save import SaveManager
    from core.engine.executor import GameState

    mgr = SaveManager(save_dir=tmp_path)
    state = GameState()
    mgr.save("01", state, screenshot=b"png1")
    mgr.save("02", state)  # 无截图

    metas = mgr.list_slots_with_meta()
    assert len(metas) == 2
    by_slot = {m["slot"]: m for m in metas}

    assert by_slot["01"]["has_screenshot"] is True
    assert by_slot["02"]["has_screenshot"] is False
    # mtime + size 字段存在
    assert by_slot["01"]["mtime"] != ""
    assert by_slot["01"]["size"] > 0


def test_list_slots_with_meta_empty_dir(tmp_path):
    """空目录 → []。"""
    from runtime.save import SaveManager
    mgr = SaveManager(save_dir=tmp_path)
    assert mgr.list_slots_with_meta() == []


def test_delete_also_removes_screenshot(tmp_path):
    """delete(slot) → 一并删 .png 文件。"""
    from runtime.save import SaveManager
    from core.engine.executor import GameState

    mgr = SaveManager(save_dir=tmp_path)
    state = GameState()
    mgr.save("01", state, screenshot=b"png")

    assert (tmp_path / "01.png").exists()
    result = mgr.delete("01")
    assert result is True
    assert not (tmp_path / "01.json").exists()
    assert not (tmp_path / "01.png").exists()


def test_delete_returns_false_when_json_absent(tmp_path):
    """JSON 不存在 → False（即使有孤儿 .png）。"""
    from runtime.save import SaveManager

    mgr = SaveManager(save_dir=tmp_path)
    # 直接写孤儿 .png（不经 save）
    (tmp_path / "01.png").write_bytes(b"orphan")
    result = mgr.delete("01")
    assert result is False


def test_save_screenshot_overwrites_existing(tmp_path):
    """重复 save 同 slot → 截图覆盖写。"""
    from runtime.save import SaveManager
    from core.engine.executor import GameState

    mgr = SaveManager(save_dir=tmp_path)
    state = GameState()
    mgr.save("01", state, screenshot=b"old png")
    mgr.save("01", state, screenshot=b"new png")

    assert mgr.get_screenshot("01") == b"new png"


# ═══════════════════════════════════════════════════════════════════════
# 2. ScreenshotManager
# ═══════════════════════════════════════════════════════════════════════


class FakeQPixmapForShot:
    """Fake QPixmap for ScreenshotManager —— save 写入 bytes buffer。"""
    def __init__(self):
        self._saved_bytes = b""

    def save(self, buffer, fmt):
        buffer.write(b"fake png from qpixmap")
        return True


class FakeQByteArray:
    """Fake QByteArray。"""
    def __init__(self, data=b""):
        self._data = data

    def __bytes__(self):
        return self._data

    def write(self, b):
        self._data += b


class FakeQBuffer:
    """Fake QBuffer —— OpenModeFlag 内嵌。"""
    class OpenModeFlag:
        WriteOnly = 1

    def __init__(self, byte_array):
        self._byte_array = byte_array
        self._open = False

    def open(self, mode):
        self._open = True
        return True

    def close(self):
        self._open = False

    def write(self, data):
        self._byte_array.write(data)


class FakeWidget:
    """Fake QWidget —— grab() 返回 FakeQPixmap。"""
    def grab(self):
        return FakeQPixmapForShot()


def test_screenshot_manager_capture_returns_bytes():
    """capture(widget) → PNG bytes（fake qt 路径）。"""
    from runtime.gui.screenshot import ScreenshotManager

    qt = {
        "QPixmap": FakeQPixmapForShot,
        "QBuffer": FakeQBuffer,
        "QByteArray": FakeQByteArray,
    }
    mgr = ScreenshotManager(qt=qt)
    data = mgr.capture(FakeWidget())
    assert data is not None
    assert b"fake png" in data


def test_screenshot_manager_capture_none_widget():
    """capture(None) → None。"""
    from runtime.gui.screenshot import ScreenshotManager
    mgr = ScreenshotManager(qt={"QPixmap": FakeQPixmapForShot})
    assert mgr.capture(None) is None


def test_screenshot_manager_capture_downgrades_without_qpixmap():
    """qt dict 无 QPixmap → 降级 None。"""
    from runtime.gui.screenshot import ScreenshotManager
    mgr = ScreenshotManager(qt={})
    assert mgr.capture(FakeWidget()) is None


def test_screenshot_manager_capture_to_path_writes_file(tmp_path):
    """capture_to_path → 写 PNG 文件。"""
    from runtime.gui.screenshot import ScreenshotManager

    qt = {
        "QPixmap": FakeQPixmapForShot,
        "QBuffer": FakeQBuffer,
        "QByteArray": FakeQByteArray,
    }
    mgr = ScreenshotManager(qt=qt)
    out = tmp_path / "shot.png"
    result = mgr.capture_to_path(FakeWidget(), out)
    assert result is True
    assert out.read_bytes() == b"fake png from qpixmap"


def test_screenshot_manager_capture_to_path_returns_false_on_failure(tmp_path):
    """capture 失败 → capture_to_path 返 False。"""
    from runtime.gui.screenshot import ScreenshotManager
    # qt 无 QPixmap → capture 返 None → capture_to_path 返 False
    mgr = ScreenshotManager(qt={})
    result = mgr.capture_to_path(FakeWidget(), tmp_path / "shot.png")
    assert result is False


def test_screenshot_manager_no_qt_lazy_import_fails(monkeypatch):
    """qt=None + PyQt6 import 失败 → 降级 None。"""
    from runtime.gui.screenshot import ScreenshotManager
    monkeypatch.setitem(sys.modules, "PyQt6.QtGui", None)
    monkeypatch.setitem(sys.modules, "PyQt6.QtCore", None)

    mgr = ScreenshotManager(qt=None)
    assert mgr.capture(FakeWidget()) is None


# ═══════════════════════════════════════════════════════════════════════
# 3. SaveSlotDialog（fake PyQt6 fixture）
# ═══════════════════════════════════════════════════════════════════════


class _FakeSignal:
    def __init__(self):
        self._slots: list = []

    def connect(self, slot):
        self._slots.append(slot)

    def emit(self, *a, **kw):
        for s in self._slots:
            s(*a, **kw)


class _FakeQDialog:
    def __init__(self, *a, **kw):
        self._title = ""
        self._accepted = False
        self._rejected = False

    def setWindowTitle(self, t): self._title = t
    def accept(self): self._accepted = True
    def reject(self): self._rejected = True


class _FakeQLabel:
    def __init__(self, text=""):
        self._text = text
        self._pixmap = None

    def setText(self, t): self._text = t
    def setPixmap(self, pm): self._pixmap = pm
    def text(self): return self._text


class _FakeQPushButton:
    def __init__(self, text=""):
        self._text = text
        self._enabled = True
        self.clicked = _FakeSignal()

    def setEnabled(self, e): self._enabled = e
    def isEnabled(self): return self._enabled


class _FakeQWidget:
    def __init__(self, *a, **kw):
        self._parent = None
        self._slot = None
        self.mousePressEvent = None

    def setParent(self, p): self._parent = p
    def deleteLater(self): pass


class _FakeQVBoxLayout:
    def __init__(self, *a, **kw):
        self._widgets: list = []
        self._layouts: list = []

    def addWidget(self, w): self._widgets.append(w)
    def addLayout(self, l): self._layouts.append(l)


class _FakeQHBoxLayout:
    def __init__(self, *a, **kw):
        self._widgets: list = []

    def addWidget(self, w): self._widgets.append(w)


class _FakeQGridLayout:
    def __init__(self, *a, **kw):
        self._cells: dict = {}  # (row, col) → widget

    def addWidget(self, w, row, col):
        self._cells[(row, col)] = w

    def count(self):
        return len(self._cells)

    def takeAt(self, i):
        items = list(self._cells.items())
        if i >= len(items):
            return None
        key = items[i][0]
        widget = self._cells.pop(key)

        class _Item:
            def widget(self_inner):
                return widget
        return _Item()


class _FakeQPixmapForDialog:
    """Fake QPixmap for SaveSlotDialog —— loadFromData + scaled。"""
    def __init__(self):
        self._data = None

    def loadFromData(self, data):
        self._data = data
        return True

    def scaled(self, w, h, *a, **kw):
        return self  # 返回 self 简化


@pytest.fixture
def fake_pyqt6_dialog(monkeypatch):
    """注入 fake PyQt6 modules for SaveSlotDialog。"""
    qtcore = types.ModuleType("PyQt6.QtCore")
    qtcore.Qt = MagicMock()
    qtcore.pyqtSignal = MagicMock(return_value=_FakeSignal())

    qtgui = types.ModuleType("PyQt6.QtGui")
    qtgui.QPixmap = _FakeQPixmapForDialog

    qtwidgets = types.ModuleType("PyQt6.QtWidgets")
    qtwidgets.QDialog = _FakeQDialog
    qtwidgets.QVBoxLayout = _FakeQVBoxLayout
    qtwidgets.QHBoxLayout = _FakeQHBoxLayout
    qtwidgets.QGridLayout = _FakeQGridLayout
    qtwidgets.QLabel = _FakeQLabel
    qtwidgets.QPushButton = _FakeQPushButton
    qtwidgets.QWidget = _FakeQWidget
    qtwidgets.QScrollArea = MagicMock()

    pyqt6_pkg = types.ModuleType("PyQt6")
    pyqt6_pkg.QtCore = qtcore
    pyqt6_pkg.QtWidgets = qtwidgets
    pyqt6_pkg.QtGui = qtgui
    monkeypatch.setitem(sys.modules, "PyQt6", pyqt6_pkg)
    monkeypatch.setitem(sys.modules, "PyQt6.QtCore", qtcore)
    monkeypatch.setitem(sys.modules, "PyQt6.QtGui", qtgui)
    monkeypatch.setitem(sys.modules, "PyQt6.QtWidgets", qtwidgets)
    return {
        "QDialog": _FakeQDialog, "QVBoxLayout": _FakeQVBoxLayout,
        "QHBoxLayout": _FakeQHBoxLayout, "QGridLayout": _FakeQGridLayout,
        "QLabel": _FakeQLabel, "QPushButton": _FakeQPushButton,
        "QWidget": _FakeQWidget, "QPixmap": _FakeQPixmapForDialog,
        "Qt": qtcore.Qt, "pyqtSignal": qtcore.pyqtSignal,
    }


def test_save_slot_dialog_constructs(fake_pyqt6_dialog):
    """SaveSlotDialog 构造 → 含网格 + 4 按钮。"""
    from runtime.gui.save_slot_dialog import _build_save_slot_dialog_class
    DialogCls = _build_save_slot_dialog_class(qt=fake_pyqt6_dialog)
    dialog = DialogCls()
    assert dialog is not None
    assert dialog._title == "存档管理"
    assert hasattr(dialog, "_grid_layout")
    assert hasattr(dialog, "_save_btn")
    assert hasattr(dialog, "_load_btn")
    assert hasattr(dialog, "_delete_btn")
    assert hasattr(dialog, "_cancel_btn")


def test_save_slot_dialog_default_9_slots(fake_pyqt6_dialog):
    """默认显示 9 个槽位（01-09）。"""
    from runtime.gui.save_slot_dialog import _build_save_slot_dialog_class
    DialogCls = _build_save_slot_dialog_class(qt=fake_pyqt6_dialog)
    dialog = DialogCls()
    # 9 个 cell，3 列 → 3 行
    assert len(dialog._cells) == 9
    assert "01" in dialog._cells
    assert "09" in dialog._cells


def test_save_slot_dialog_no_save_manager_shows_empty_slots(fake_pyqt6_dialog):
    """无 save_manager → 9 个空槽位（无缩略图）。"""
    from runtime.gui.save_slot_dialog import _build_save_slot_dialog_class
    DialogCls = _build_save_slot_dialog_class(qt=fake_pyqt6_dialog)
    dialog = DialogCls(save_manager=None)
    assert len(dialog._cells) == 9
    # 所有 cell 的 thumb_label 文本应为 "(空)"
    for cell in dialog._cells.values():
        assert cell._thumb_label._text == "(空)"


def test_save_slot_dialog_loads_existing_slots_with_meta(
    fake_pyqt6_dialog, tmp_path
):
    """save_manager 含存档 → 网格合并已有 + 默认槽位。"""
    from runtime.gui.save_slot_dialog import _build_save_slot_dialog_class
    from runtime.save import SaveManager
    from core.engine.executor import GameState

    mgr = SaveManager(save_dir=tmp_path)
    state = GameState()
    mgr.save("01", state, screenshot=b"png01")
    mgr.save("02", state)  # 无截图

    DialogCls = _build_save_slot_dialog_class(qt=fake_pyqt6_dialog)
    dialog = DialogCls(save_manager=mgr)
    # 01 + 02 + 默认 01-09 合并 → 9 个
    assert "01" in dialog._cells
    assert "02" in dialog._cells
    assert "09" in dialog._cells


def test_save_slot_dialog_thumbnail_loaded_from_screenshot(
    fake_pyqt6_dialog, tmp_path
):
    """slot 有截图 → cell 的 thumb_label setPixmap 被调（_pixmap 非空）。"""
    from runtime.gui.save_slot_dialog import _build_save_slot_dialog_class
    from runtime.save import SaveManager
    from core.engine.executor import GameState

    mgr = SaveManager(save_dir=tmp_path)
    state = GameState()
    mgr.save("01", state, screenshot=b"real png bytes")

    DialogCls = _build_save_slot_dialog_class(qt=fake_pyqt6_dialog)
    dialog = DialogCls(save_manager=mgr)
    cell_01 = dialog._cells["01"]
    # setPixmap 被调 → _pixmap 非 None
    assert cell_01._thumb_label._pixmap is not None


def test_save_slot_dialog_no_screenshot_shows_empty_text(
    fake_pyqt6_dialog, tmp_path
):
    """slot 无截图 → thumb_label 文本 "(空)"。"""
    from runtime.gui.save_slot_dialog import _build_save_slot_dialog_class
    from runtime.save import SaveManager
    from core.engine.executor import GameState

    mgr = SaveManager(save_dir=tmp_path)
    state = GameState()
    mgr.save("01", state)  # 无截图

    DialogCls = _build_save_slot_dialog_class(qt=fake_pyqt6_dialog)
    dialog = DialogCls(save_manager=mgr)
    cell_01 = dialog._cells["01"]
    assert cell_01._thumb_label._text == "(空)"


def test_save_slot_dialog_select_slot(fake_pyqt6_dialog):
    """点击 cell → _on_select → selected_slot 更新 + 按钮启用。"""
    from runtime.gui.save_slot_dialog import _build_save_slot_dialog_class
    DialogCls = _build_save_slot_dialog_class(qt=fake_pyqt6_dialog)
    dialog = DialogCls()

    # 初始未选中 → 按钮禁用
    assert dialog.get_selected_slot() is None
    assert dialog._save_btn._enabled is False

    # 选中 slot 03
    dialog._on_select("03")
    assert dialog.get_selected_slot() == "03"
    assert dialog._save_btn._enabled is True
    assert dialog._load_btn._enabled is True
    assert dialog._delete_btn._enabled is True


def test_save_slot_dialog_save_action(fake_pyqt6_dialog):
    """点保存按钮 → action='save' + accept。"""
    from runtime.gui.save_slot_dialog import _build_save_slot_dialog_class
    DialogCls = _build_save_slot_dialog_class(qt=fake_pyqt6_dialog)
    dialog = DialogCls()
    dialog._on_select("01")
    dialog._on_save()
    assert dialog.action == "save"
    assert dialog._accepted is True


def test_save_slot_dialog_load_action(fake_pyqt6_dialog):
    """点读取按钮 → action='load' + accept。"""
    from runtime.gui.save_slot_dialog import _build_save_slot_dialog_class
    DialogCls = _build_save_slot_dialog_class(qt=fake_pyqt6_dialog)
    dialog = DialogCls()
    dialog._on_select("02")
    dialog._on_load()
    assert dialog.action == "load"


def test_save_slot_dialog_delete_action(fake_pyqt6_dialog):
    """点删除按钮 → action='delete' + accept。"""
    from runtime.gui.save_slot_dialog import _build_save_slot_dialog_class
    DialogCls = _build_save_slot_dialog_class(qt=fake_pyqt6_dialog)
    dialog = DialogCls()
    dialog._on_select("01")
    dialog._on_delete()
    assert dialog.action == "delete"


def test_save_slot_dialog_cancel_action(fake_pyqt6_dialog):
    """点取消按钮 → action=None + selected_slot=None + reject。"""
    from runtime.gui.save_slot_dialog import _build_save_slot_dialog_class
    DialogCls = _build_save_slot_dialog_class(qt=fake_pyqt6_dialog)
    dialog = DialogCls()
    dialog._on_select("01")
    dialog._on_cancel()
    assert dialog.action is None
    assert dialog.get_selected_slot() is None
    assert dialog._rejected is True


def test_save_slot_dialog_refresh_rebuilds_grid(
    fake_pyqt6_dialog, tmp_path
):
    """refresh() → 清空 + 重建网格（反映最新存档）。"""
    from runtime.gui.save_slot_dialog import _build_save_slot_dialog_class
    from runtime.save import SaveManager
    from core.engine.executor import GameState

    mgr = SaveManager(save_dir=tmp_path)
    DialogCls = _build_save_slot_dialog_class(qt=fake_pyqt6_dialog)
    dialog = DialogCls(save_manager=mgr)

    # 初始 9 个空槽位
    assert len(dialog._cells) == 9
    assert "01" in dialog._cells

    # 加一个新存档（不在默认 01-09 范围）
    mgr.save("slot_x", GameState())
    dialog.refresh()

    assert "slot_x" in dialog._cells


def test_save_slot_dialog_grid_3_columns(fake_pyqt6_dialog):
    """网格 3 列布局：9 个槽位 → (0,0)..(2,2)。"""
    from runtime.gui.save_slot_dialog import _build_save_slot_dialog_class
    DialogCls = _build_save_slot_dialog_class(qt=fake_pyqt6_dialog)
    dialog = DialogCls()
    # 9 个 cell，3 列 → 行 0/1/2，列 0/1/2
    assert (0, 0) in dialog._grid_layout._cells
    assert (2, 2) in dialog._grid_layout._cells
    # (2, 2) 是第 9 个槽位（"09"）
    assert dialog._grid_layout._cells[(2, 2)]._slot == "09"


def test_save_slot_dialog_custom_slot_count(fake_pyqt6_dialog):
    """slot_count=6 → 显示 6 个槽位。"""
    from runtime.gui.save_slot_dialog import _build_save_slot_dialog_class
    DialogCls = _build_save_slot_dialog_class(qt=fake_pyqt6_dialog)
    dialog = DialogCls(slot_count=6)
    assert len(dialog._cells) == 6
    assert "01" in dialog._cells
    assert "06" in dialog._cells
    assert "07" not in dialog._cells


def test_save_slot_dialog_build_raises_runtime_error_when_no_pyqt6(monkeypatch):
    """qt=None + PyQt6 import 失败 → RuntimeError。"""
    from runtime.gui import save_slot_dialog
    monkeypatch.setitem(sys.modules, "PyQt6.QtCore", None)
    monkeypatch.setitem(sys.modules, "PyQt6.QtWidgets", None)
    monkeypatch.setitem(sys.modules, "PyQt6.QtGui", None)

    with pytest.raises(RuntimeError, match="PyQt6"):
        save_slot_dialog._build_save_slot_dialog_class(qt=None)


def test_save_slot_dialog_module_imports_without_pyqt6():
    """save_slot_dialog 模块顶层不 import PyQt6——即使未装也能 import。"""
    for k in ("PyQt6", "PyQt6.QtCore", "PyQt6.QtWidgets", "PyQt6.QtGui"):
        sys.modules.pop(k, None)
    sys.modules.pop("runtime.gui.save_slot_dialog", None)
    try:
        import runtime.gui.save_slot_dialog as mod
        assert mod is not None
        assert hasattr(mod, "_build_save_slot_dialog_class")
    finally:
        pass


# ═══════════════════════════════════════════════════════════════════════
# 4. 端到端集成：SaveManager + ScreenshotManager + SaveSlotDialog
# ═══════════════════════════════════════════════════════════════════════


def test_e2e_save_with_screenshot_then_load_in_dialog(
    fake_pyqt6_dialog, tmp_path
):
    """端到端：
    1. ScreenshotManager.capture(widget) → bytes
    2. SaveManager.save(slot, state, screenshot=bytes)
    3. SaveSlotDialog 构造时读 list_slots_with_meta + get_screenshot
    4. cell 缩略图显示
    """
    from runtime.gui.screenshot import ScreenshotManager
    from runtime.gui.save_slot_dialog import _build_save_slot_dialog_class
    from runtime.save import SaveManager
    from core.engine.executor import GameState

    # 1. 截图
    shot_qt = {
        "QPixmap": FakeQPixmapForShot,
        "QBuffer": FakeQBuffer,
        "QByteArray": FakeQByteArray,
    }
    shot_mgr = ScreenshotManager(qt=shot_qt)
    png_bytes = shot_mgr.capture(FakeWidget())
    assert png_bytes is not None

    # 2. 存档（含截图）
    save_mgr = SaveManager(save_dir=tmp_path)
    state = GameState(vars={"pick": 1}, current_block_id="c1")
    save_mgr.save("03", state, screenshot=png_bytes)

    # 3. 构造 dialog
    DialogCls = _build_save_slot_dialog_class(qt=fake_pyqt6_dialog)
    dialog = DialogCls(save_manager=save_mgr)

    # 4. slot 03 cell 有缩略图
    cell_03 = dialog._cells["03"]
    assert cell_03._thumb_label._pixmap is not None

    # 5. 选中并加载
    dialog._on_select("03")
    assert dialog.get_selected_slot() == "03"
    dialog._on_load()
    assert dialog.action == "load"
