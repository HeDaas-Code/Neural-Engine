"""v3-08 · SettingsManager + SettingsDialog 测试（#98）。

验证 issue #98 验收点：
- SettingsManager：get/set/get_all/set_many
- SettingsManager：reset / reset_to_defaults
- SettingsManager：save / load / reload / roundtrip
- SettingsManager：类型校验（int/float/bool 范围）
- SettingsManager：未知 key 静默忽略
- SettingsManager：损坏 JSON / 非法值静默忽略
- SettingsManager：apply_to_text_renderer / auto_mode / audio_manager
- SettingsDialog：构造 + 字段数 + get_settings / set_settings
- SettingsDialog：确定/取消按钮 + was_accepted
- SettingsDialog：从 settings_manager 初始化表单值
- MainWindow 集成：构造时创建 + 应用配置 + show_settings / apply_settings
"""
from __future__ import annotations

import json
import os
import sys
import types
from unittest.mock import MagicMock

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")


# ═══════════════════════════════════════════════════════════════════════
# 1. SettingsManager 基础测试
# ═══════════════════════════════════════════════════════════════════════


def test_settings_constructs_with_defaults(tmp_path):
    """SettingsManager 默认构造 → DEFAULT_SETTINGS 副本。"""
    from runtime.settings import SettingsManager, DEFAULT_SETTINGS
    f = tmp_path / "settings.json"  # 用 tmp_path 避免污染 home
    m = SettingsManager(settings_file=f)
    assert m.get_all() == DEFAULT_SETTINGS


def test_settings_get_returns_value():
    """get(key) 返回配置值。"""
    from runtime.settings import SettingsManager
    m = SettingsManager(settings_file="/tmp/nonexistent_test_settings.json")
    assert m.get("text_speed") == 40
    assert m.get("auto_delay") == 1500
    assert m.get("bgm_volume") == 0.7
    assert m.get("fullscreen") is False


def test_settings_get_unknown_key_returns_default():
    """get(未知 key) → default 参数。"""
    from runtime.settings import SettingsManager
    m = SettingsManager(settings_file="/tmp/nonexistent_test_settings.json")
    assert m.get("nonexistent", "fallback") == "fallback"
    assert m.get("nonexistent") is None


def test_settings_set_valid_value():
    """set 合法值 → True，get 反映更新。"""
    from runtime.settings import SettingsManager
    m = SettingsManager(settings_file="/tmp/nonexistent_test_settings.json")
    assert m.set("text_speed", 20) is True
    assert m.get("text_speed") == 20
    assert m.set("bgm_volume", 0.5) is True
    assert m.get("bgm_volume") == 0.5
    assert m.set("fullscreen", True) is True
    assert m.get("fullscreen") is True


def test_settings_set_unknown_key_returns_false():
    """set 未知 key → False。"""
    from runtime.settings import SettingsManager
    m = SettingsManager(settings_file="/tmp/nonexistent_test_settings.json")
    assert m.set("unknown_key", 123) is False


def test_settings_set_invalid_type_returns_false():
    """set 类型非法 → False。"""
    from runtime.settings import SettingsManager
    m = SettingsManager(settings_file="/tmp/nonexistent_test_settings.json")
    # text_speed 应是 int，传 str/float/bool
    assert m.set("text_speed", "fast") is False
    assert m.set("text_speed", 40.5) is False
    assert m.set("text_speed", True) is False  # bool 不算 int
    # bgm_volume 应是 float 0-1，超范围
    assert m.set("bgm_volume", 1.5) is False
    assert m.set("bgm_volume", -0.1) is False
    assert m.set("bgm_volume", "loud") is False
    assert m.set("bgm_volume", True) is False  # bool 不算 float
    # fullscreen 应是 bool，传 int
    assert m.set("fullscreen", 1) is False
    assert m.set("fullscreen", "yes") is False


def test_settings_set_negative_int_returns_false():
    """text_speed / auto_delay 不允许负数。"""
    from runtime.settings import SettingsManager
    m = SettingsManager(settings_file="/tmp/nonexistent_test_settings.json")
    assert m.set("text_speed", -1) is False
    assert m.set("auto_delay", -100) is False


def test_settings_set_many():
    """set_many 批量设置，返回成功项数。"""
    from runtime.settings import SettingsManager
    m = SettingsManager(settings_file="/tmp/nonexistent_test_settings.json")
    n = m.set_many({
        "text_speed": 30,
        "auto_delay": 2000,
        "bgm_volume": 0.3,
        "unknown": 99,  # 跳过
    })
    assert n == 3
    assert m.get("text_speed") == 30
    assert m.get("auto_delay") == 2000
    assert m.get("bgm_volume") == 0.3


def test_settings_get_all_returns_copy():
    """get_all 返回副本，外部修改不影响内部。"""
    from runtime.settings import SettingsManager
    m = SettingsManager(settings_file="/tmp/nonexistent_test_settings.json")
    d = m.get_all()
    d["text_speed"] = 9999
    assert m.get("text_speed") == 40  # 内部未变


# ═══════════════════════════════════════════════════════════════════════
# 2. SettingsManager reset 测试
# ═══════════════════════════════════════════════════════════════════════


def test_settings_reset_single_key():
    """reset(key) → 单 key 重置为默认。"""
    from runtime.settings import SettingsManager, DEFAULT_SETTINGS
    m = SettingsManager(settings_file="/tmp/nonexistent_test_settings.json")
    m.set("text_speed", 99)
    m.reset("text_speed")
    assert m.get("text_speed") == DEFAULT_SETTINGS["text_speed"]


def test_settings_reset_unknown_key_silent():
    """reset 未知 key → 静默（不影响其他配置）。"""
    from runtime.settings import SettingsManager
    m = SettingsManager(settings_file="/tmp/nonexistent_test_settings.json")
    m.set("text_speed", 99)
    m.reset("unknown")
    assert m.get("text_speed") == 99  # 未被重置


def test_settings_reset_all():
    """reset(None) → 全部重置为默认。"""
    from runtime.settings import SettingsManager, DEFAULT_SETTINGS
    m = SettingsManager(settings_file="/tmp/nonexistent_test_settings.json")
    m.set("text_speed", 1)
    m.set("auto_delay", 2)
    m.set("bgm_volume", 0.1)
    m.reset(None)
    assert m.get_all() == DEFAULT_SETTINGS


def test_settings_reset_to_defaults_alias():
    """reset_to_defaults 等价于 reset(None)。"""
    from runtime.settings import SettingsManager, DEFAULT_SETTINGS
    m = SettingsManager(settings_file="/tmp/nonexistent_test_settings.json")
    m.set("text_speed", 999)
    m.reset_to_defaults()
    assert m.get_all() == DEFAULT_SETTINGS


# ═══════════════════════════════════════════════════════════════════════
# 3. SettingsManager 持久化测试
# ═══════════════════════════════════════════════════════════════════════


def test_settings_save_to_file(tmp_path):
    """save → JSON 文件写入。"""
    from runtime.settings import SettingsManager
    f = tmp_path / "settings.json"
    m = SettingsManager(settings_file=f)
    m.set("text_speed", 25)
    m.set("bgm_volume", 0.4)
    assert m.save() is True
    assert f.exists()
    data = json.loads(f.read_text(encoding="utf-8"))
    assert data["text_speed"] == 25
    assert data["bgm_volume"] == 0.4


def test_settings_load_from_file(tmp_path):
    """构造时加载已存在的文件。"""
    from runtime.settings import SettingsManager
    f = tmp_path / "settings.json"
    f.write_text(json.dumps({
        "text_speed": 60,
        "auto_delay": 2500,
        "bgm_volume": 0.8,
    }, ensure_ascii=False), encoding="utf-8")
    m = SettingsManager(settings_file=f)
    assert m.get("text_speed") == 60
    assert m.get("auto_delay") == 2500
    assert m.get("bgm_volume") == 0.8


def test_settings_load_missing_file_uses_defaults(tmp_path):
    """加载不存在的文件 → 用默认值。"""
    from runtime.settings import SettingsManager, DEFAULT_SETTINGS
    f = tmp_path / "nonexistent.json"
    m = SettingsManager(settings_file=f)
    assert m.get_all() == DEFAULT_SETTINGS


def test_settings_load_corrupt_json_uses_defaults(tmp_path):
    """加载损坏 JSON → 用默认值。"""
    from runtime.settings import SettingsManager, DEFAULT_SETTINGS
    f = tmp_path / "bad.json"
    f.write_text("not valid {{{", encoding="utf-8")
    m = SettingsManager(settings_file=f)
    assert m.get_all() == DEFAULT_SETTINGS


def test_settings_load_non_dict_uses_defaults(tmp_path):
    """加载非 dict JSON → 用默认值。"""
    from runtime.settings import SettingsManager, DEFAULT_SETTINGS
    f = tmp_path / "list.json"
    f.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    m = SettingsManager(settings_file=f)
    assert m.get_all() == DEFAULT_SETTINGS


def test_settings_load_invalid_values_filtered(tmp_path):
    """加载文件含非法值 → 该项用默认值，合法项保留。"""
    from runtime.settings import SettingsManager
    f = tmp_path / "mixed.json"
    f.write_text(json.dumps({
        "text_speed": 50,           # 合法
        "bgm_volume": 1.5,          # 非法（超范围）
        "unknown_key": "garbage",   # 未知 key
        "fullscreen": "yes",        # 类型非法
    }), encoding="utf-8")
    m = SettingsManager(settings_file=f)
    assert m.get("text_speed") == 50  # 合法保留
    assert m.get("bgm_volume") == 0.7  # 非法 → 默认值
    assert m.get("fullscreen") is False  # 类型非法 → 默认值


def test_settings_save_creates_parent_dir(tmp_path):
    """save 自动创建父目录。"""
    from runtime.settings import SettingsManager
    f = tmp_path / "subdir" / "nested" / "settings.json"
    m = SettingsManager(settings_file=f)
    m.set("text_speed", 10)
    assert m.save() is True
    assert f.exists()


def test_settings_roundtrip(tmp_path):
    """save → 新实例 load → 数据一致。"""
    from runtime.settings import SettingsManager
    f = tmp_path / "rt.json"
    m1 = SettingsManager(settings_file=f)
    m1.set("text_speed", 33)
    m1.set("auto_delay", 1800)
    m1.set("bgm_volume", 0.55)
    m1.set("fullscreen", True)
    m1.save()
    m2 = SettingsManager(settings_file=f)
    assert m2.get("text_speed") == 33
    assert m2.get("auto_delay") == 1800
    assert m2.get("bgm_volume") == 0.55
    assert m2.get("fullscreen") is True


def test_settings_reload_overrides_unsaved_changes(tmp_path):
    """reload → 从文件重新加载，覆盖未保存的内存修改。"""
    from runtime.settings import SettingsManager
    f = tmp_path / "settings.json"
    m = SettingsManager(settings_file=f)
    m.set("text_speed", 50)
    m.save()
    # 内存中改了但不保存
    m.set("text_speed", 999)
    assert m.get("text_speed") == 999
    m.reload()
    assert m.get("text_speed") == 50  # 回到文件中的值


def test_settings_file_property(tmp_path):
    """settings_file 属性返回 Path。"""
    from runtime.settings import SettingsManager
    f = tmp_path / "x.json"
    m = SettingsManager(settings_file=f)
    assert m.settings_file == f


# ═══════════════════════════════════════════════════════════════════════
# 4. SettingsManager apply_to_* 测试
# ═══════════════════════════════════════════════════════════════════════


def test_apply_to_text_renderer():
    """apply_to_text_renderer → renderer._char_delay_ms 更新。"""
    from runtime.settings import SettingsManager

    class FakeRenderer:
        def __init__(self):
            self._char_delay_ms = 40

    m = SettingsManager(settings_file="/tmp/nonexistent_test_settings.json")
    m.set("text_speed", 25)
    r = FakeRenderer()
    m.apply_to_text_renderer(r)
    assert r._char_delay_ms == 25


def test_apply_to_auto_mode():
    """apply_to_auto_mode → auto_mode.set_auto_delay 调用。"""
    from runtime.settings import SettingsManager

    class FakeAutoMode:
        def __init__(self):
            self.delay = 1500

        def set_auto_delay(self, ms):
            self.delay = ms

    m = SettingsManager(settings_file="/tmp/nonexistent_test_settings.json")
    m.set("auto_delay", 2000)
    am = FakeAutoMode()
    m.apply_to_auto_mode(am)
    assert am.delay == 2000


def test_apply_to_audio_manager():
    """apply_to_audio_manager → set_volume(track=...) 三次调用（音量 0-100 int）。"""
    from runtime.settings import SettingsManager

    class FakeAudioManager:
        def __init__(self):
            self.calls = []

        def set_volume(self, vol, track=None):
            self.calls.append((track, vol))

    m = SettingsManager(settings_file="/tmp/nonexistent_test_settings.json")
    m.set("bgm_volume", 0.5)
    m.set("se_volume", 0.8)
    m.set("voice_volume", 1.0)
    am = FakeAudioManager()
    m.apply_to_audio_manager(am)
    # 三次调用
    assert ("bgm", 50) in am.calls
    assert ("se", 80) in am.calls
    assert ("voice", 100) in am.calls


def test_apply_to_audio_manager_swallows_exceptions():
    """apply_to_audio_manager 静默吞掉异常（fake 缺方法）。"""
    from runtime.settings import SettingsManager

    class BrokenAudioManager:
        pass  # 无 set_volume 方法

    m = SettingsManager(settings_file="/tmp/nonexistent_test_settings.json")
    am = BrokenAudioManager()
    # 不应抛
    m.apply_to_audio_manager(am)


# ═══════════════════════════════════════════════════════════════════════
# 5. SettingsDialog 测试
# ═══════════════════════════════════════════════════════════════════════


# ─── Fake Qt Widgets for SettingsDialog ───────────────────────────────


class FakeSignal:
    def __init__(self):
        self._slots: list = []

    def connect(self, slot):
        self._slots.append(slot)


class FakeQDialogS:
    def __init__(self, *a, **kw):
        self._title = ""
        self._accepted = False
        self._rejected = False

    def setWindowTitle(self, t):
        self._title = t

    def accept(self):
        self._accepted = True

    def reject(self):
        self._rejected = True


class FakeQVBoxLayoutS:
    def __init__(self, *a, **kw):
        self._layouts: list = []
        self._widgets: list = []

    def addLayout(self, l):
        self._layouts.append(l)

    def addWidget(self, w):
        self._widgets.append(w)


class FakeQHBoxLayoutS:
    def __init__(self, *a, **kw):
        self._widgets: list = []
        self._stretch_count = 0

    def addWidget(self, w):
        self._widgets.append(w)

    def addStretch(self, n=0):
        self._stretch_count += 1


class FakeQFormLayoutS:
    def __init__(self, *a, **kw):
        self._rows: list = []

    def addRow(self, label, widget):
        self._rows.append((label, widget))


class FakeQLabelS:
    def __init__(self, t=""):
        self._text = t


class FakeQPushButtonS:
    def __init__(self, t=""):
        self._text = t
        self.clicked = FakeSignal()


class FakeQWidgetS:
    def __init__(self, *a, **kw):
        pass


class FakeQSpinBoxS:
    """Fake QSpinBox —— 记录 value / range / step。"""
    def __init__(self):
        self._value = 0
        self._min = 0
        self._max = 99
        self._step = 1

    def setMinimum(self, v): self._min = v
    def setMaximum(self, v): self._max = v
    def setSingleStep(self, s): self._step = s
    def setValue(self, v): self._value = v
    def value(self): return self._value


class FakeQDoubleSpinBoxS:
    """Fake QDoubleSpinBox。"""
    def __init__(self):
        self._value = 0.0
        self._min = 0.0
        self._max = 1.0
        self._step = 0.05
        self._decimals = 2

    def setMinimum(self, v): self._min = v
    def setMaximum(self, v): self._max = v
    def setSingleStep(self, s): self._step = s
    def setDecimals(self, d): self._decimals = d
    def setValue(self, v): self._value = v
    def value(self): return self._value


class FakeQCheckBoxS:
    """Fake QCheckBox。"""
    def __init__(self):
        self._checked = False

    def setChecked(self, b): self._checked = bool(b)
    def isChecked(self): return self._checked


@pytest.fixture
def fake_pyqt6_settings():
    """构造含 SettingsDialog 所需 Qt 类的 dict。"""
    return {
        "QDialog": FakeQDialogS,
        "QVBoxLayout": FakeQVBoxLayoutS,
        "QHBoxLayout": FakeQHBoxLayoutS,
        "QFormLayout": FakeQFormLayoutS,
        "QLabel": FakeQLabelS,
        "QPushButton": FakeQPushButtonS,
        "QWidget": FakeQWidgetS,
        "QSpinBox": FakeQSpinBoxS,
        "QDoubleSpinBox": FakeQDoubleSpinBoxS,
        "QCheckBox": FakeQCheckBoxS,
    }


def test_settings_dialog_constructs(fake_pyqt6_settings):
    """SettingsDialog 构造 → 6 个字段 + 确定/取消按钮。"""
    from runtime.gui.settings_dialog import _build_settings_dialog_class
    DialogCls = _build_settings_dialog_class(qt=fake_pyqt6_settings)
    dialog = DialogCls()
    assert dialog.field_count == 6
    assert dialog._ok_btn is not None
    assert dialog._cancel_btn is not None
    assert dialog._title == "设置"


def test_settings_dialog_initial_values_from_manager(fake_pyqt6_settings, tmp_path):
    """从 SettingsManager 初始化表单值。"""
    from runtime.gui.settings_dialog import _build_settings_dialog_class
    from runtime.settings import SettingsManager
    f = tmp_path / "s.json"
    f.write_text(json.dumps({
        "text_speed": 60,
        "auto_delay": 3000,
        "bgm_volume": 0.3,
        "fullscreen": True,
    }), encoding="utf-8")
    mgr = SettingsManager(settings_file=f)
    DialogCls = _build_settings_dialog_class(qt=fake_pyqt6_settings)
    dialog = DialogCls(settings_manager=mgr)
    settings = dialog.get_settings()
    assert settings["text_speed"] == 60
    assert settings["auto_delay"] == 3000
    assert settings["bgm_volume"] == 0.3
    assert settings["fullscreen"] is True


def test_settings_dialog_get_settings_default_values(fake_pyqt6_settings):
    """无 settings_manager → 用 DEFAULT_SETTINGS 初始化。"""
    from runtime.gui.settings_dialog import _build_settings_dialog_class
    from runtime.settings import DEFAULT_SETTINGS
    DialogCls = _build_settings_dialog_class(qt=fake_pyqt6_settings)
    dialog = DialogCls()
    s = dialog.get_settings()
    assert s["text_speed"] == DEFAULT_SETTINGS["text_speed"]
    assert s["auto_delay"] == DEFAULT_SETTINGS["auto_delay"]
    assert s["bgm_volume"] == DEFAULT_SETTINGS["bgm_volume"]
    assert s["fullscreen"] == DEFAULT_SETTINGS["fullscreen"]


def test_settings_dialog_set_settings(fake_pyqt6_settings):
    """set_settings → 表单 widget 值更新。"""
    from runtime.gui.settings_dialog import _build_settings_dialog_class
    DialogCls = _build_settings_dialog_class(qt=fake_pyqt6_settings)
    dialog = DialogCls()
    dialog.set_settings({
        "text_speed": 80,
        "auto_delay": 5000,
        "bgm_volume": 0.9,
        "se_volume": 0.2,
        "voice_volume": 0.5,
        "fullscreen": True,
    })
    s = dialog.get_settings()
    assert s["text_speed"] == 80
    assert s["auto_delay"] == 5000
    assert s["bgm_volume"] == 0.9
    assert s["se_volume"] == 0.2
    assert s["voice_volume"] == 0.5
    assert s["fullscreen"] is True


def test_settings_dialog_ok_button_sets_accepted(fake_pyqt6_settings):
    """点确定 → was_accepted=True + accept() 调用。"""
    from runtime.gui.settings_dialog import _build_settings_dialog_class
    DialogCls = _build_settings_dialog_class(qt=fake_pyqt6_settings)
    dialog = DialogCls()
    # 模拟点确定（直接调 slot）
    dialog._ok_btn.clicked._slots[0]()
    assert dialog.was_accepted is True
    assert dialog._accepted is True


def test_settings_dialog_cancel_button_rejects(fake_pyqt6_settings):
    """点取消 → was_accepted=False + reject() 调用。"""
    from runtime.gui.settings_dialog import _build_settings_dialog_class
    DialogCls = _build_settings_dialog_class(qt=fake_pyqt6_settings)
    dialog = DialogCls()
    # 模拟点取消
    dialog._cancel_btn.clicked._slots[0]()
    assert dialog.was_accepted is False
    assert dialog._rejected is True


def test_settings_dialog_field_widgets_initialized(fake_pyqt6_settings):
    """6 个字段的 widget 都被创建（QSpinBox/QDoubleSpinBox/QCheckBox）。"""
    from runtime.gui.settings_dialog import _build_settings_dialog_class
    DialogCls = _build_settings_dialog_class(qt=fake_pyqt6_settings)
    dialog = DialogCls()
    # text_speed / auto_delay 是 QSpinBox
    assert isinstance(dialog._widgets["text_speed"], FakeQSpinBoxS)
    assert isinstance(dialog._widgets["auto_delay"], FakeQSpinBoxS)
    # 三个音量是 QDoubleSpinBox
    assert isinstance(dialog._widgets["bgm_volume"], FakeQDoubleSpinBoxS)
    assert isinstance(dialog._widgets["se_volume"], FakeQDoubleSpinBoxS)
    assert isinstance(dialog._widgets["voice_volume"], FakeQDoubleSpinBoxS)
    # fullscreen 是 QCheckBox
    assert isinstance(dialog._widgets["fullscreen"], FakeQCheckBoxS)


def test_settings_dialog_spinbox_range_set(fake_pyqt6_settings):
    """QSpinBox 的 min/max/step 被设置。"""
    from runtime.gui.settings_dialog import _build_settings_dialog_class
    DialogCls = _build_settings_dialog_class(qt=fake_pyqt6_settings)
    dialog = DialogCls()
    ts = dialog._widgets["text_speed"]
    assert ts._min == 0
    assert ts._max == 500
    assert ts._step == 1


def test_settings_dialog_no_pyqt6_raises():
    """qt=None 且 PyQt6 不可用 → RuntimeError。"""
    # 强制 PyQt6 import 失败
    for k in list(sys.modules):
        if k.startswith("PyQt6"):
            sys.modules.pop(k, None)
    sys.modules["PyQt6"] = None  # type: ignore
    sys.modules["PyQt6.QtCore"] = None  # type: ignore
    sys.modules["PyQt6.QtWidgets"] = None  # type: ignore
    try:
        from runtime.gui.settings_dialog import _build_settings_dialog_class
        with pytest.raises(RuntimeError, match="PyQt6"):
            _build_settings_dialog_class()
    finally:
        # 恢复
        sys.modules.pop("PyQt6", None)
        sys.modules.pop("PyQt6.QtCore", None)
        sys.modules.pop("PyQt6.QtWidgets", None)


# ═══════════════════════════════════════════════════════════════════════
# 6. MainWindow 集成测试
# ═══════════════════════════════════════════════════════════════════════


# ─── Fake Qt Widgets（与 test_read_marks_auto_mode.py 一致）─────────


class FakeSignalMW:
    def __init__(self):
        self._slots: list = []

    def connect(self, slot):
        self._slots.append(slot)


class FakeQMainWindowMW2:
    def __init__(self, *a, **kw):
        self._window_title = ""
        self._shown = False
        self._closed = False

    def setWindowTitle(self, t): self._window_title = t
    def setCentralWidget(self, w): pass
    def show(self): self._shown = True
    def close(self): self._closed = True


class FakeQTextEditMW2:
    def __init__(self, *a, **kw):
        self._text = ""
        self._read_only = False
        self._style_sheet = ""

    def setReadOnly(self, ro): self._read_only = ro
    def append(self, t): self._text += t
    def insertPlainText(self, t): self._text += t
    def setStyleSheet(self, css): self._style_sheet = css
    def toPlainText(self): return self._text
    def clear(self): self._text = ""


class FakeQLineEditMW2:
    def __init__(self, *a, **kw):
        self._text = ""
        self._enabled = True
        self._visible = True
        self.returnPressed = FakeSignalMW()

    def text(self): return self._text
    def setText(self, t): self._text = t
    def clear(self): self._text = ""
    def setEnabled(self, e): self._enabled = e
    def setVisible(self, v): self._visible = v
    def setFocus(self): pass


class FakeQPushButtonMW2:
    def __init__(self, t="", *a, **kw):
        self._text = t
        self._visible = True
        self.clicked = FakeSignalMW()

    def setVisible(self, v): self._visible = v
    def setEnabled(self, e): pass
    def setParent(self, p): pass
    def deleteLater(self): pass


class FakeQWidgetMW2:
    def __init__(self, *a, **kw): pass


class FakeQVBoxLayoutMW2:
    def __init__(self, *a, **kw):
        self._widgets: list = []

    def addWidget(self, w): self._widgets.append(w)


class FakeQLabelMW2:
    def __init__(self, *a, **kw):
        self._pixmap = None

    def setPixmap(self, pm): self._pixmap = pm
    def setScaledContents(self, b): pass
    def setAlignment(self, a): pass
    def clear(self): self._pixmap = None
    def setParent(self, p): pass
    def deleteLater(self): pass
    def show(self): pass


class FakeQPixmapMW2:
    def __init__(self, path=""):
        self._path = path


@pytest.fixture
def fake_pyqt6_mw2():
    return {
        "QMainWindow": FakeQMainWindowMW2,
        "QTextEdit": FakeQTextEditMW2,
        "QLineEdit": FakeQLineEditMW2,
        "QPushButton": FakeQPushButtonMW2,
        "QWidget": FakeQWidgetMW2,
        "QVBoxLayout": FakeQVBoxLayoutMW2,
        "QLabel": FakeQLabelMW2,
        "QPixmap": FakeQPixmapMW2,
    }


def _make_main_window2(qt, **kwargs):
    """构造 MainWindow 实例（注入 fake qt + 已 reset 装饰器状态）。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from core.decorators import clear
    from core.decorators import bgm as bgm_mod
    from core.decorators import bg as bg_mod
    from core.decorators import char as char_mod
    clear()
    bgm_mod.set_audio_manager(None)
    bg_mod.set_image_manager(None)
    char_mod.set_image_manager(None)
    MainWindowCls = pyqt6_main._build_main_window_class(qt=qt, **kwargs)
    sink = PyQt6Sink()
    input_sink = PyQt6InputSink()
    return MainWindowCls(sink=sink, input_sink=input_sink)


@pytest.fixture(autouse=True)
def _reset_decorator_state_v308():
    from core.decorators import clear
    from core.decorators import bgm as bgm_mod
    from core.decorators import bg as bg_mod
    from core.decorators import char as char_mod
    clear()
    bgm_mod.set_audio_manager(None)
    bg_mod.set_image_manager(None)
    char_mod.set_image_manager(None)
    yield
    clear()
    bgm_mod.set_audio_manager(None)
    bg_mod.set_image_manager(None)
    char_mod.set_image_manager(None)


def test_main_window_has_settings(fake_pyqt6_mw2, tmp_path):
    """MainWindow 构造时创建 SettingsManager 实例。"""
    f = tmp_path / "settings.json"
    win = _make_main_window2(fake_pyqt6_mw2, char_delay_ms=0, settings_manager=__import__("runtime.settings", fromlist=["SettingsManager"]).SettingsManager(settings_file=f))
    assert win.settings is not None


def test_main_window_settings_applied_to_text_renderer(fake_pyqt6_mw2, tmp_path):
    """构造时 settings.text_speed 应用到 text_renderer._char_delay_ms。"""
    from runtime.settings import SettingsManager
    f = tmp_path / "settings.json"
    f.write_text(json.dumps({"text_speed": 15}), encoding="utf-8")
    mgr = SettingsManager(settings_file=f)
    win = _make_main_window2(fake_pyqt6_mw2, char_delay_ms=40, settings_manager=mgr)
    # settings.text_speed=15 应覆盖 char_delay_ms=40
    assert win._text_renderer._char_delay_ms == 15


def test_main_window_settings_applied_to_auto_mode(fake_pyqt6_mw2, tmp_path):
    """构造时 settings.auto_delay 应用到 auto_mode.auto_delay_ms。"""
    from runtime.settings import SettingsManager
    f = tmp_path / "settings.json"
    f.write_text(json.dumps({"auto_delay": 2500}), encoding="utf-8")
    mgr = SettingsManager(settings_file=f)
    win = _make_main_window2(fake_pyqt6_mw2, char_delay_ms=0, settings_manager=mgr)
    assert win.auto_mode.auto_delay_ms == 2500


def test_main_window_show_settings_returns_dialog(fake_pyqt6_mw2, tmp_path):
    """show_settings → 返回 SettingsDialog 实例。"""
    from runtime.settings import SettingsManager
    from runtime.gui.settings_dialog import _build_settings_dialog_class
    f = tmp_path / "settings.json"
    win = _make_main_window2(
        fake_pyqt6_mw2, char_delay_ms=0,
        settings_manager=SettingsManager(settings_file=f),
    )
    # 构造 fake qt 含 SettingsDialog 所需类
    settings_qt = {
        "QDialog": FakeQDialogS, "QVBoxLayout": FakeQVBoxLayoutS,
        "QHBoxLayout": FakeQHBoxLayoutS, "QFormLayout": FakeQFormLayoutS,
        "QLabel": FakeQLabelS, "QPushButton": FakeQPushButtonS,
        "QWidget": FakeQWidgetS, "QSpinBox": FakeQSpinBoxS,
        "QDoubleSpinBox": FakeQDoubleSpinBoxS, "QCheckBox": FakeQCheckBoxS,
    }
    dialog = win.show_settings(qt_override=settings_qt)
    assert dialog is not None
    assert dialog.field_count == 6


def test_main_window_apply_settings(fake_pyqt6_mw2, tmp_path):
    """apply_settings → 重新推送配置到运行时组件。"""
    from runtime.settings import SettingsManager
    f = tmp_path / "settings.json"
    win = _make_main_window2(
        fake_pyqt6_mw2, char_delay_ms=0,
        settings_manager=SettingsManager(settings_file=f),
    )
    # 改 settings 后 apply
    win.settings.set("text_speed", 99)
    win.apply_settings()
    assert win._text_renderer._char_delay_ms == 99


def test_main_window_injected_settings_used(fake_pyqt6_mw2, tmp_path):
    """注入自定义 SettingsManager → MainWindow 用它。"""
    from runtime.settings import SettingsManager
    f = tmp_path / "custom.json"
    custom = SettingsManager(settings_file=f)
    custom.set("text_speed", 7)
    win = _make_main_window2(
        fake_pyqt6_mw2, char_delay_ms=0, settings_manager=custom,
    )
    assert win.settings is custom
    assert win._text_renderer._char_delay_ms == 7


# ═══════════════════════════════════════════════════════════════════════
# 7. 模块导入测试
# ═══════════════════════════════════════════════════════════════════════


def test_settings_module_imports():
    """settings 模块可独立 import（无 PyQt6 依赖）。"""
    for k in list(sys.modules):
        if k.startswith("PyQt6"):
            sys.modules.pop(k, None)
    from runtime.settings import SettingsManager, DEFAULT_SETTINGS
    assert SettingsManager is not None
    assert isinstance(DEFAULT_SETTINGS, dict)


def test_settings_dialog_module_imports():
    """settings_dialog 模块可独立 import（顶层不 import PyQt6）。"""
    for k in list(sys.modules):
        if k.startswith("PyQt6"):
            sys.modules.pop(k, None)
    sys.modules.pop("runtime.gui.settings_dialog", None)
    from runtime.gui.settings_dialog import _build_settings_dialog_class
    assert _build_settings_dialog_class is not None


def test_default_settings_has_all_keys():
    """DEFAULT_SETTINGS 含全部 6 个 key。"""
    from runtime.settings import DEFAULT_SETTINGS
    expected = {"text_speed", "auto_delay", "bgm_volume",
                "se_volume", "voice_volume", "fullscreen"}
    assert set(DEFAULT_SETTINGS.keys()) == expected
