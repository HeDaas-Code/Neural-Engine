"""v3-04 · ImageRenderer + @bg/@char 装饰器测试（#94）。

验证 issue #94 验收点：
- ImageRenderer 类：set_background/clear_background/set_character/remove_character/clear
- 路径解析：相对 chapters_root / 绝对路径 / 不存在
- 降级 no-op：QLabel/QPixmap 未装 → 不抛错
- @bg 装饰器：call → set_background / stop → clear_background
- @char 装饰器：call → set_character / stop → remove_character
- 位置：left/center/right（默认 center，非法值回退 center）
- MainWindow 集成：构造时创建 + 注册到 bg/char 钩子 + close 清理
- executor 修复：DecoratorStop 发射 kind="stop"
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")


# ─── Fake Qt Widgets（ImageRenderer 用）──────────────────────────────────


class FakeQLabel:
    def __init__(self, parent=None):
        self._parent = parent
        self._pixmap = None
        self._scaled = False
        self._alignment = None
        self._cleared = False
        self._deleted = False

    def setPixmap(self, pm):
        self._pixmap = pm

    def setScaledContents(self, b):
        self._scaled = b

    def setAlignment(self, a):
        self._alignment = a

    def clear(self):
        self._cleared = True
        self._pixmap = None

    def setParent(self, p):
        self._parent = p

    def deleteLater(self):
        self._deleted = True

    def show(self):
        pass


class FakeQPixmap:
    def __init__(self, path=""):
        self._path = path

    @classmethod
    def fromLocalFile(cls, path):
        return cls(path)


class FakeLayout:
    def __init__(self):
        self._widgets: list = []

    def addWidget(self, w):
        self._widgets.append(w)


class FakeParent:
    pass


def make_qt_dict():
    """构造含 QLabel/QPixmap 的 qt dict（测试注入用）。"""
    return {"QLabel": FakeQLabel, "QPixmap": FakeQPixmap}


# ─── fixture ────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_bg_char_state():
    """每个测试前后清空 bg/char 装饰器状态。"""
    from core.decorators import clear
    from core.decorators import bg as bg_mod
    from core.decorators import char as char_mod
    clear()
    bg_mod.reset_last_bg()
    char_mod.reset_last_char()
    bg_mod.set_image_manager(None)
    char_mod.set_image_manager(None)
    yield
    clear()
    bg_mod.reset_last_bg()
    char_mod.reset_last_char()
    bg_mod.set_image_manager(None)
    char_mod.set_image_manager(None)


# ═══════════════════════════════════════════════════════════════════════
# 1. ImageRenderer —— 背景图
# ═══════════════════════════════════════════════════════════════════════


def test_image_renderer_constructs_with_defaults():
    """ImageRenderer 默认构造：无背景，无角色。"""
    from runtime.gui.image_renderer import ImageRenderer
    r = ImageRenderer(FakeParent(), FakeLayout(), qt=make_qt_dict())
    assert r.has_background is False
    assert r.character_count == 0
    assert r.get_background() is None


def test_set_background_returns_false_when_file_not_found():
    """文件不存在 → False。"""
    from runtime.gui.image_renderer import ImageRenderer
    r = ImageRenderer(FakeParent(), FakeLayout(), qt=make_qt_dict(),
                      chapters_root="/nonexistent")
    assert r.set_background("ghost.png") is False
    assert r.has_background is False


def test_set_background_relative_to_chapters_root(tmp_path):
    """相对路径 → 相对 chapters_root 解析（文件存在时成功）。"""
    from runtime.gui.image_renderer import ImageRenderer
    (tmp_path / "forest.png").write_text("fake img")
    r = ImageRenderer(FakeParent(), FakeLayout(), qt=make_qt_dict(),
                      chapters_root=str(tmp_path))

    assert r.set_background("forest.png") is True
    assert r.has_background is True
    assert r.get_background() == "forest.png"


def test_set_background_absolute_path(tmp_path):
    """绝对路径直接用。"""
    from runtime.gui.image_renderer import ImageRenderer
    img = tmp_path / "abs.png"
    img.write_text("x")
    r = ImageRenderer(FakeParent(), FakeLayout(), qt=make_qt_dict(),
                      chapters_root="/nonexistent")

    assert r.set_background(str(img)) is True
    assert r.get_background() == str(img)


def test_clear_background_resets_state(tmp_path):
    """clear_background → has_background=False, get_background=None。"""
    from runtime.gui.image_renderer import ImageRenderer
    (tmp_path / "x.png").write_text("x")
    r = ImageRenderer(FakeParent(), FakeLayout(), qt=make_qt_dict(),
                      chapters_root=str(tmp_path))
    r.set_background("x.png")
    assert r.has_background is True

    r.clear_background()
    assert r.has_background is False
    assert r.get_background() is None


def test_set_background_creates_bg_label(tmp_path):
    """set_background 成功时创建 bg_label 并 setPixmap。"""
    from runtime.gui.image_renderer import ImageRenderer
    (tmp_path / "x.png").write_text("x")
    layout = FakeLayout()
    r = ImageRenderer(FakeParent(), layout, qt=make_qt_dict(),
                      chapters_root=str(tmp_path))

    r.set_background("x.png")
    # bg_label 被加入 layout
    assert len(layout._widgets) >= 1


def test_set_background_reuses_bg_label_on_second_call(tmp_path):
    """第二次 set_background 复用 bg_label（不创建新的）。"""
    from runtime.gui.image_renderer import ImageRenderer
    (tmp_path / "a.png").write_text("x")
    (tmp_path / "b.png").write_text("x")
    layout = FakeLayout()
    r = ImageRenderer(FakeParent(), layout, qt=make_qt_dict(),
                      chapters_root=str(tmp_path))

    r.set_background("a.png")
    widgets_after_first = len(layout._widgets)
    r.set_background("b.png")
    widgets_after_second = len(layout._widgets)

    assert widgets_after_first == widgets_after_second  # 复用


# ═══════════════════════════════════════════════════════════════════════
# 2. ImageRenderer —— 角色立绘
# ═══════════════════════════════════════════════════════════════════════


def test_set_character_success(tmp_path):
    """set_character 成功 → character_count=1, get_characters 含该角色。"""
    from runtime.gui.image_renderer import ImageRenderer
    (tmp_path / "alice.png").write_text("x")
    r = ImageRenderer(FakeParent(), FakeLayout(), qt=make_qt_dict(),
                      chapters_root=str(tmp_path))

    assert r.set_character("alice", "alice.png", "left") is True
    assert r.character_count == 1
    chars = r.get_characters()
    assert "alice" in chars
    assert chars["alice"]["pos"] == "left"
    assert chars["alice"]["src"] == "alice.png"


def test_set_character_empty_name_returns_false(tmp_path):
    """name 为空 → False。"""
    from runtime.gui.image_renderer import ImageRenderer
    (tmp_path / "x.png").write_text("x")
    r = ImageRenderer(FakeParent(), FakeLayout(), qt=make_qt_dict(),
                      chapters_root=str(tmp_path))
    assert r.set_character("", "x.png", "center") is False


def test_set_character_file_not_found_returns_false(tmp_path):
    """source 文件不存在 → False。"""
    from runtime.gui.image_renderer import ImageRenderer
    r = ImageRenderer(FakeParent(), FakeLayout(), qt=make_qt_dict(),
                      chapters_root=str(tmp_path))
    assert r.set_character("alice", "ghost.png", "left") is False


def test_set_character_default_position_center(tmp_path):
    """position 默认 center。"""
    from runtime.gui.image_renderer import ImageRenderer
    (tmp_path / "x.png").write_text("x")
    r = ImageRenderer(FakeParent(), FakeLayout(), qt=make_qt_dict(),
                      chapters_root=str(tmp_path))

    r.set_character("alice", "x.png")
    assert r.get_characters()["alice"]["pos"] == "center"


def test_set_character_invalid_position_falls_back_center(tmp_path):
    """非法 position → 回退 center。"""
    from runtime.gui.image_renderer import ImageRenderer
    (tmp_path / "x.png").write_text("x")
    r = ImageRenderer(FakeParent(), FakeLayout(), qt=make_qt_dict(),
                      chapters_root=str(tmp_path))

    r.set_character("alice", "x.png", "upside_down")
    assert r.get_characters()["alice"]["pos"] == "center"


def test_set_character_same_name_replaces(tmp_path):
    """同 name 再次 set_character → 更换立绘（不新增）。"""
    from runtime.gui.image_renderer import ImageRenderer
    (tmp_path / "a.png").write_text("x")
    (tmp_path / "b.png").write_text("x")
    r = ImageRenderer(FakeParent(), FakeLayout(), qt=make_qt_dict(),
                      chapters_root=str(tmp_path))

    r.set_character("alice", "a.png", "left")
    r.set_character("alice", "b.png", "right")
    assert r.character_count == 1
    chars = r.get_characters()
    assert chars["alice"]["src"] == "b.png"
    assert chars["alice"]["pos"] == "right"


def test_remove_character(tmp_path):
    """remove_character → 角色被移除。"""
    from runtime.gui.image_renderer import ImageRenderer
    (tmp_path / "x.png").write_text("x")
    r = ImageRenderer(FakeParent(), FakeLayout(), qt=make_qt_dict(),
                      chapters_root=str(tmp_path))

    r.set_character("alice", "x.png", "left")
    assert r.character_count == 1

    r.remove_character("alice")
    assert r.character_count == 0
    assert "alice" not in r.get_characters()


def test_remove_character_unknown_name_silent():
    """移除不存在的角色 → 静默（不抛错）。"""
    from runtime.gui.image_renderer import ImageRenderer
    r = ImageRenderer(FakeParent(), FakeLayout(), qt=make_qt_dict())
    r.remove_character("ghost")  # 不抛


def test_multiple_characters(tmp_path):
    """多个角色同时存在。"""
    from runtime.gui.image_renderer import ImageRenderer
    (tmp_path / "a.png").write_text("x")
    (tmp_path / "b.png").write_text("x")
    r = ImageRenderer(FakeParent(), FakeLayout(), qt=make_qt_dict(),
                      chapters_root=str(tmp_path))

    r.set_character("alice", "a.png", "left")
    r.set_character("bob", "b.png", "right")
    assert r.character_count == 2
    assert "alice" in r.get_characters()
    assert "bob" in r.get_characters()


# ═══════════════════════════════════════════════════════════════════════
# 3. ImageRenderer —— clear() + 降级 no-op
# ═══════════════════════════════════════════════════════════════════════


def test_clear_removes_background_and_characters(tmp_path):
    """clear() → 清空背景 + 所有角色。"""
    from runtime.gui.image_renderer import ImageRenderer
    (tmp_path / "bg.png").write_text("x")
    (tmp_path / "c.png").write_text("x")
    r = ImageRenderer(FakeParent(), FakeLayout(), qt=make_qt_dict(),
                      chapters_root=str(tmp_path))

    r.set_background("bg.png")
    r.set_character("alice", "c.png", "left")
    r.clear()

    assert r.has_background is False
    assert r.character_count == 0


def test_set_background_downgrades_without_qpixmap(tmp_path):
    """qt dict 无 QPixmap → 降级 no-op，返回 True。"""
    from runtime.gui.image_renderer import ImageRenderer
    (tmp_path / "x.png").write_text("x")
    r = ImageRenderer(FakeParent(), FakeLayout(), qt={"QLabel": FakeQLabel},
                      chapters_root=str(tmp_path))
    # QPixmap 不在 qt dict → _get_qpixmap 返回 None → 降级
    assert r.set_background("x.png") is True
    assert r.get_background() == "x.png"


def test_set_character_downgrades_without_qpixmap(tmp_path):
    """qt dict 无 QPixmap → 降级 no-op，角色仍被记录。"""
    from runtime.gui.image_renderer import ImageRenderer
    (tmp_path / "x.png").write_text("x")
    r = ImageRenderer(FakeParent(), FakeLayout(), qt={"QLabel": FakeQLabel},
                      chapters_root=str(tmp_path))

    assert r.set_character("alice", "x.png", "left") is True
    assert r.character_count == 1


def test_set_background_downgrades_without_qlabel(tmp_path):
    """qt dict 无 QLabel → 降级 no-op，返回 True。"""
    from runtime.gui.image_renderer import ImageRenderer
    (tmp_path / "x.png").write_text("x")
    r = ImageRenderer(FakeParent(), FakeLayout(), qt={"QPixmap": FakeQPixmap},
                      chapters_root=str(tmp_path))
    assert r.set_background("x.png") is True


def test_image_renderer_no_qt_dict_lazy_import_fails(monkeypatch, tmp_path):
    """qt=None + PyQt6 import 失败 → 降级 no-op。"""
    from runtime.gui.image_renderer import ImageRenderer
    (tmp_path / "x.png").write_text("x")
    # 强制 PyQt6.QtWidgets / QtGui import 失败
    monkeypatch.setitem(sys.modules, "PyQt6.QtWidgets", None)
    monkeypatch.setitem(sys.modules, "PyQt6.QtGui", None)

    r = ImageRenderer(FakeParent(), FakeLayout(), qt=None,
                      chapters_root=str(tmp_path))
    assert r.set_background("x.png") is True  # 降级 no-op


# ═══════════════════════════════════════════════════════════════════════
# 4. @bg 装饰器
# ═══════════════════════════════════════════════════════════════════════


def test_bg_install_registers_hook():
    """bg.install() → 'bg' 钩子被注册。"""
    from core.decorators import get_hook
    from core.decorators import bg as bg_mod
    bg_mod.install()
    assert get_hook("bg") is not None


def test_bg_handle_call_records_set():
    """@bg src:forest.png (call) → ('set', 'forest.png') 被记录。"""
    from core.decorators import bg as bg_mod
    from core.engine.protocol import DecoratorEvt

    bg_mod.install()
    bg_mod.handle(DecoratorEvt(name="bg", args=["src:forest.png"]))
    assert bg_mod.get_last_bg() == [("set", "forest.png")]


def test_bg_handle_stop_records_clear():
    """@bg (stop) → ('clear', '') 被记录。"""
    from core.decorators import bg as bg_mod
    from core.engine.protocol import DecoratorEvt

    bg_mod.install()
    bg_mod.handle(DecoratorEvt(name="bg", args=[""], kind="stop"))
    assert bg_mod.get_last_bg() == [("clear", "")]


def test_bg_handle_no_src_key_silent():
    """@bg 无 src: 键 → 静默（不记录）。"""
    from core.decorators import bg as bg_mod
    from core.engine.protocol import DecoratorEvt

    bg_mod.install()
    bg_mod.handle(DecoratorEvt(name="bg", args=["foo:bar"]))
    assert bg_mod.get_last_bg() == []


def test_bg_set_image_manager_forwards_set():
    """注册 mgr → @bg call 转发到 mgr.set_background。"""
    from core.decorators import bg as bg_mod
    from core.engine.protocol import DecoratorEvt

    calls: list = []

    class FakeMgr:
        def set_background(self, src):
            calls.append(("set", src))

        def clear_background(self):
            calls.append(("clear",))

    bg_mod.set_image_manager(FakeMgr())
    bg_mod.install()
    bg_mod.handle(DecoratorEvt(name="bg", args=["src:forest.png"]))

    assert ("set", "forest.png") in calls
    assert bg_mod.get_last_bg() == [("set", "forest.png")]


def test_bg_set_image_manager_forwards_clear():
    """注册 mgr → @bg stop 转发到 mgr.clear_background。"""
    from core.decorators import bg as bg_mod
    from core.engine.protocol import DecoratorEvt

    calls: list = []

    class FakeMgr:
        def set_background(self, src):
            calls.append(("set", src))

        def clear_background(self):
            calls.append(("clear",))

    bg_mod.set_image_manager(FakeMgr())
    bg_mod.install()
    bg_mod.handle(DecoratorEvt(name="bg", args=[""], kind="stop"))

    assert ("clear",) in calls
    assert bg_mod.get_last_bg() == [("clear", "")]


def test_bg_handle_without_mgr_only_records():
    """未注册 mgr → 仅记录（v2 行为基线）。"""
    from core.decorators import bg as bg_mod
    from core.engine.protocol import DecoratorEvt

    bg_mod.install()
    bg_mod.handle(DecoratorEvt(name="bg", args=["src:x.png"]))
    assert bg_mod.get_last_bg() == [("set", "x.png")]


def test_bg_handle_mgr_exception_silent():
    """mgr.set_background 抛异常 → handle 不向上抛。"""
    from core.decorators import bg as bg_mod
    from core.engine.protocol import DecoratorEvt

    class BadMgr:
        def set_background(self, src):
            raise RuntimeError("boom")

        def clear_background(self):
            raise RuntimeError("boom clear")

    bg_mod.set_image_manager(BadMgr())
    bg_mod.install()
    # 不抛
    bg_mod.handle(DecoratorEvt(name="bg", args=["src:x.png"]))
    bg_mod.handle(DecoratorEvt(name="bg", args=[""], kind="stop"))


def test_bg_dispatch_routes_via_registry():
    """dispatch(DecoratorEvt(name='bg', ...)) → 触发 handle。"""
    from core.decorators import bg as bg_mod, dispatch
    from core.engine.protocol import DecoratorEvt

    bg_mod.install()
    dispatch(DecoratorEvt(name="bg", args=["src:forest.png"]))
    assert bg_mod.get_last_bg() == [("set", "forest.png")]


# ═══════════════════════════════════════════════════════════════════════
# 5. @char 装饰器
# ═══════════════════════════════════════════════════════════════════════


def test_char_install_registers_hook():
    """char.install() → 'char' 钩子被注册。"""
    from core.decorators import get_hook
    from core.decorators import char as char_mod
    char_mod.install()
    assert get_hook("char") is not None


def test_char_handle_call_records_show():
    """@char name:alice, src:alice.png, pos:left (call) → ('show', 'alice', 'alice.png', 'left')。"""
    from core.decorators import char as char_mod
    from core.engine.protocol import DecoratorEvt

    char_mod.install()
    char_mod.handle(DecoratorEvt(
        name="char", args=["name:alice", "src:alice.png", "pos:left"]
    ))
    assert char_mod.get_last_char() == [("show", "alice", "alice.png", "left")]


def test_char_handle_stop_records_remove():
    """@char alice (stop) → ('remove', 'alice', '', '')。"""
    from core.decorators import char as char_mod
    from core.engine.protocol import DecoratorEvt

    char_mod.install()
    char_mod.handle(DecoratorEvt(name="char", args=["alice"], kind="stop"))
    assert char_mod.get_last_char() == [("remove", "alice", "", "")]


def test_char_handle_no_name_key_silent():
    """@char 无 name: 键 → 静默（不记录）。"""
    from core.decorators import char as char_mod
    from core.engine.protocol import DecoratorEvt

    char_mod.install()
    char_mod.handle(DecoratorEvt(name="char", args=["src:x.png", "pos:left"]))
    assert char_mod.get_last_char() == []


def test_char_handle_default_pos_center():
    """@char 无 pos: 键 → 默认 center。"""
    from core.decorators import char as char_mod
    from core.engine.protocol import DecoratorEvt

    char_mod.install()
    char_mod.handle(DecoratorEvt(
        name="char", args=["name:alice", "src:alice.png"]
    ))
    assert char_mod.get_last_char() == [("show", "alice", "alice.png", "center")]


def test_char_handle_invalid_pos_falls_back_center():
    """@char pos:invalid → 回退 center。"""
    from core.decorators import char as char_mod
    from core.engine.protocol import DecoratorEvt

    char_mod.install()
    char_mod.handle(DecoratorEvt(
        name="char", args=["name:alice", "src:x.png", "pos:upside_down"]
    ))
    assert char_mod.get_last_char()[0][3] == "center"


def test_char_set_image_manager_forwards_show():
    """注册 mgr → @char call 转发到 mgr.set_character。"""
    from core.decorators import char as char_mod
    from core.engine.protocol import DecoratorEvt

    calls: list = []

    class FakeMgr:
        def set_character(self, name, src, pos="center"):
            calls.append(("show", name, src, pos))

        def remove_character(self, name):
            calls.append(("remove", name))

    char_mod.set_image_manager(FakeMgr())
    char_mod.install()
    char_mod.handle(DecoratorEvt(
        name="char", args=["name:alice", "src:a.png", "pos:left"]
    ))

    assert ("show", "alice", "a.png", "left") in calls


def test_char_set_image_manager_forwards_remove():
    """注册 mgr → @char stop 转发到 mgr.remove_character。"""
    from core.decorators import char as char_mod
    from core.engine.protocol import DecoratorEvt

    calls: list = []

    class FakeMgr:
        def set_character(self, name, src, pos="center"):
            calls.append(("show", name, src, pos))

        def remove_character(self, name):
            calls.append(("remove", name))

    char_mod.set_image_manager(FakeMgr())
    char_mod.install()
    char_mod.handle(DecoratorEvt(name="char", args=["alice"], kind="stop"))

    assert ("remove", "alice") in calls


def test_char_handle_without_mgr_only_records():
    """未注册 mgr → 仅记录。"""
    from core.decorators import char as char_mod
    from core.engine.protocol import DecoratorEvt

    char_mod.install()
    char_mod.handle(DecoratorEvt(
        name="char", args=["name:alice", "src:a.png", "pos:left"]
    ))
    assert char_mod.get_last_char() == [("show", "alice", "a.png", "left")]


def test_char_handle_mgr_exception_silent():
    """mgr.set_character 抛异常 → handle 不向上抛。"""
    from core.decorators import char as char_mod
    from core.engine.protocol import DecoratorEvt

    class BadMgr:
        def set_character(self, name, src, pos="center"):
            raise RuntimeError("boom")

        def remove_character(self, name):
            raise RuntimeError("boom remove")

    char_mod.set_image_manager(BadMgr())
    char_mod.install()
    # 不抛
    char_mod.handle(DecoratorEvt(
        name="char", args=["name:alice", "src:a.png"]
    ))
    char_mod.handle(DecoratorEvt(name="char", args=["alice"], kind="stop"))


def test_char_dispatch_routes_via_registry():
    """dispatch(DecoratorEvt(name='char', ...)) → 触发 handle。"""
    from core.decorators import char as char_mod, dispatch
    from core.engine.protocol import DecoratorEvt

    char_mod.install()
    dispatch(DecoratorEvt(
        name="char", args=["name:bob", "src:b.png", "pos:right"]
    ))
    assert char_mod.get_last_char() == [("show", "bob", "b.png", "right")]


# ═══════════════════════════════════════════════════════════════════════
# 6. executor 修复：DecoratorStop → kind="stop"
# ═══════════════════════════════════════════════════════════════════════


def test_executor_decorator_stop_emits_kind_stop():
    """DecoratorStop 节点 → executor 发射 DecoratorEvt(kind='stop')。"""
    from core.engine.ast_nodes import (
        DecoratorStop, Block, Story, IdMeta, IdEnd, Start, End,
        BlockLocation,
    )
    from core.engine.executor import Executor
    from core.engine.protocol import DecoratorEvt

    evts: list = []

    class FakeSink:
        def put_evt(self, evt):
            evts.append(evt)
        def put_cmd(self, cmd): pass

    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=1)),
        next_table=(),
        body=(Start(), DecoratorStop(name="bgm", key="rain.mp3"), End()),
        loc=BlockLocation(lineno=1, col=1),
    )
    story = Story(blocks=(block,))

    exe = Executor(story, FakeSink())
    exe.run()

    deco_evts = [e for e in evts if isinstance(e, DecoratorEvt)]
    assert len(deco_evts) == 1
    assert deco_evts[0].kind == "stop"
    assert deco_evts[0].args == ["rain.mp3"]


def test_executor_decorator_call_emits_kind_call():
    """DecoratorCall 节点 → executor 发射 DecoratorEvt(kind='call')。"""
    from core.engine.ast_nodes import (
        DecoratorCall, Block, Story, IdMeta, IdEnd, Start, End,
        BlockLocation,
    )
    from core.engine.executor import Executor
    from core.engine.protocol import DecoratorEvt

    evts: list = []

    class FakeSink:
        def put_evt(self, evt):
            evts.append(evt)
        def put_cmd(self, cmd): pass

    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=1)),
        next_table=(),
        body=(Start(), DecoratorCall(name="bg", args=("src:forest.png",)), End()),
        loc=BlockLocation(lineno=1, col=1),
    )
    story = Story(blocks=(block,))

    exe = Executor(story, FakeSink())
    exe.run()

    deco_evts = [e for e in evts if isinstance(e, DecoratorEvt)]
    assert len(deco_evts) == 1
    assert deco_evts[0].kind == "call"
    assert deco_evts[0].args == ["src:forest.png"]


# ═══════════════════════════════════════════════════════════════════════
# 7. MainWindow 集成（@bg/@char → ImageRenderer）
# ═══════════════════════════════════════════════════════════════════════


# 复用 test_pyqt6_main.py 的 fake qt 结构
class _FakeSignal:
    def __init__(self):
        self._slots: list = []

    def connect(self, slot):
        self._slots.append(slot)

    def emit(self, *args, **kwargs):
        for slot in self._slots:
            slot(*args, **kwargs)


class _FakeQMainWindow:
    def __init__(self, *a, **kw):
        self._window_title = ""
        self._central_widget = None
        self._shown = False
        self._closed = False

    def setWindowTitle(self, t): self._window_title = t
    def setCentralWidget(self, w): self._central_widget = w
    def show(self): self._shown = True
    def close(self): self._closed = True


class _FakeQTextEdit:
    def __init__(self, *a, **kw): self._text = ""
    def setReadOnly(self, ro): pass
    def append(self, t): self._text += t
    def clear(self): self._text = ""
    def toPlainText(self): return self._text


class _FakeQLineEdit:
    def __init__(self, *a, **kw):
        self._text = ""
        self._enabled = True
        self._visible = True
        self.returnPressed = _FakeSignal()
    def text(self): return self._text
    def setText(self, t): self._text = t
    def clear(self): self._text = ""
    def setEnabled(self, e): self._enabled = e
    def isEnabled(self): return self._enabled
    def setVisible(self, v): self._visible = v
    def isVisible(self): return self._visible
    def setFocus(self): pass


class _FakeQPushButton:
    def __init__(self, text="", *a, **kw):
        self._text = text
        self._visible = True
        self.clicked = _FakeSignal()
    def setVisible(self, v): self._visible = v
    def isVisible(self): return self._visible


class _FakeQWidget:
    def __init__(self, *a, **kw): pass


class _FakeQVBoxLayout:
    def __init__(self, *a, **kw):
        self._widgets: list = []
    def addWidget(self, w): self._widgets.append(w)


class _FakeQApplication:
    _instance = None
    def __init__(self, argv): _FakeQApplication._instance = self
    def exec(self): return 0
    @classmethod
    def instance(cls): return cls._instance


@pytest.fixture
def fake_pyqt6_img(monkeypatch):
    """fake PyQt6 with QLabel/QPixmap for ImageRenderer integration tests."""
    import types as _types
    from unittest.mock import MagicMock

    qtcore = _types.ModuleType("PyQt6.QtCore")
    qtcore.Qt = MagicMock()
    qtcore.QThread = MagicMock()
    qtcore.QObject = MagicMock()
    qtcore.pyqtSignal = MagicMock(return_value=_FakeSignal())

    qtgui = _types.ModuleType("PyQt6.QtGui")
    qtgui.QPixmap = FakeQPixmap

    qtwidgets = _types.ModuleType("PyQt6.QtWidgets")
    qtwidgets.QApplication = _FakeQApplication
    qtwidgets.QMainWindow = _FakeQMainWindow
    qtwidgets.QTextEdit = _FakeQTextEdit
    qtwidgets.QLineEdit = _FakeQLineEdit
    qtwidgets.QPushButton = _FakeQPushButton
    qtwidgets.QWidget = _FakeQWidget
    qtwidgets.QVBoxLayout = _FakeQVBoxLayout
    qtwidgets.QLabel = FakeQLabel

    pyqt6_pkg = _types.ModuleType("PyQt6")
    pyqt6_pkg.QtCore = qtcore
    pyqt6_pkg.QtWidgets = qtwidgets
    pyqt6_pkg.QtGui = qtgui
    monkeypatch.setitem(sys.modules, "PyQt6", pyqt6_pkg)
    monkeypatch.setitem(sys.modules, "PyQt6.QtCore", qtcore)
    monkeypatch.setitem(sys.modules, "PyQt6.QtGui", qtgui)
    monkeypatch.setitem(sys.modules, "PyQt6.QtWidgets", qtwidgets)
    return {
        "QApplication": _FakeQApplication, "QMainWindow": _FakeQMainWindow,
        "QTextEdit": _FakeQTextEdit, "QLineEdit": _FakeQLineEdit,
        "QPushButton": _FakeQPushButton, "QWidget": _FakeQWidget,
        "QVBoxLayout": _FakeQVBoxLayout, "QLabel": FakeQLabel,
        "QPixmap": FakeQPixmap, "Qt": qtcore.Qt, "QObject": qtcore.QObject,
        "QThread": qtcore.QThread, "pyqtSignal": qtcore.pyqtSignal,
    }


def test_main_window_creates_image_renderer_by_default(fake_pyqt6_img):
    """MainWindow 构造时默认创建 ImageRenderer。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from runtime.gui.image_renderer import ImageRenderer

    MainWindowCls = pyqt6_main._build_main_window_class()
    win = MainWindowCls(sink=PyQt6Sink(), input_sink=PyQt6InputSink())
    assert isinstance(win.image_renderer, ImageRenderer)


def test_main_window_registers_image_renderer_to_bg_char_hooks(fake_pyqt6_img):
    """MainWindow → bg.set_image_manager + char.set_image_manager 被调。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from core.decorators import bg as bg_mod
    from core.decorators import char as char_mod

    MainWindowCls = pyqt6_main._build_main_window_class()
    win = MainWindowCls(sink=PyQt6Sink(), input_sink=PyQt6InputSink())

    assert bg_mod.get_image_manager() is win.image_renderer
    assert char_mod.get_image_manager() is win.image_renderer


def test_main_window_accepts_injected_image_renderer(fake_pyqt6_img):
    """image_renderer 参数注入 → MainWindow 用注入的实例。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink

    class FakeRenderer:
        def set_background(self, src): pass
        def clear_background(self): pass
        def set_character(self, name, src, pos="center"): pass
        def remove_character(self, name): pass
        def clear(self): pass

    injected = FakeRenderer()
    MainWindowCls = pyqt6_main._build_main_window_class(image_renderer=injected)
    win = MainWindowCls(sink=PyQt6Sink(), input_sink=PyQt6InputSink())
    assert win.image_renderer is injected


def test_main_window_bg_evt_forwards_to_image_renderer(tmp_path, fake_pyqt6_img):
    """DecoratorEvt(@bg src:forest.png) → ImageRenderer.set_background 被调。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from core.engine.protocol import DecoratorEvt
    from core.decorators import bg as bg_mod

    # 创建临时图片文件
    (tmp_path / "forest.png").write_text("x")

    calls: list = []

    class FakeRenderer:
        def set_background(self, src):
            calls.append(("set", src))
        def clear_background(self):
            calls.append(("clear",))
        def set_character(self, name, src, pos="center"): pass
        def remove_character(self, name): pass
        def clear(self): pass

    bg_mod.install()
    MainWindowCls = pyqt6_main._build_main_window_class(
        image_renderer=FakeRenderer(), chapters_root=str(tmp_path),
    )
    win = MainWindowCls(sink=PyQt6Sink(), input_sink=PyQt6InputSink())

    win._sink.put_evt(DecoratorEvt(name="bg", args=["src:forest.png"]))

    assert ("set", "forest.png") in calls
    assert bg_mod.get_last_bg() == [("set", "forest.png")]


def test_main_window_bg_stop_evt_forwards_to_image_renderer(fake_pyqt6_img):
    """DecoratorEvt(@bg kind='stop') → ImageRenderer.clear_background 被调。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from core.engine.protocol import DecoratorEvt

    calls: list = []

    class FakeRenderer:
        def set_background(self, src): pass
        def clear_background(self):
            calls.append(("clear",))
        def set_character(self, name, src, pos="center"): pass
        def remove_character(self, name): pass
        def clear(self): pass

    from core.decorators import bg as bg_mod
    bg_mod.install()
    MainWindowCls = pyqt6_main._build_main_window_class(image_renderer=FakeRenderer())
    win = MainWindowCls(sink=PyQt6Sink(), input_sink=PyQt6InputSink())

    win._sink.put_evt(DecoratorEvt(name="bg", args=[""], kind="stop"))
    assert ("clear",) in calls


def test_main_window_char_evt_forwards_to_image_renderer(tmp_path, fake_pyqt6_img):
    """DecoratorEvt(@char name:alice, src:a.png, pos:left) → set_character。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from core.engine.protocol import DecoratorEvt

    (tmp_path / "a.png").write_text("x")

    calls: list = []

    class FakeRenderer:
        def set_background(self, src): pass
        def clear_background(self): pass
        def set_character(self, name, src, pos="center"):
            calls.append(("show", name, src, pos))
        def remove_character(self, name): pass
        def clear(self): pass

    from core.decorators import char as char_mod
    char_mod.install()
    MainWindowCls = pyqt6_main._build_main_window_class(
        image_renderer=FakeRenderer(), chapters_root=str(tmp_path),
    )
    win = MainWindowCls(sink=PyQt6Sink(), input_sink=PyQt6InputSink())

    win._sink.put_evt(DecoratorEvt(
        name="char", args=["name:alice", "src:a.png", "pos:left"]
    ))

    assert ("show", "alice", "a.png", "left") in calls


def test_main_window_char_stop_evt_forwards_to_image_renderer(fake_pyqt6_img):
    """DecoratorEvt(@char alice kind='stop') → remove_character('alice')。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from core.engine.protocol import DecoratorEvt

    calls: list = []

    class FakeRenderer:
        def set_background(self, src): pass
        def clear_background(self): pass
        def set_character(self, name, src, pos="center"): pass
        def remove_character(self, name):
            calls.append(("remove", name))
        def clear(self): pass

    from core.decorators import char as char_mod
    char_mod.install()
    MainWindowCls = pyqt6_main._build_main_window_class(image_renderer=FakeRenderer())
    win = MainWindowCls(sink=PyQt6Sink(), input_sink=PyQt6InputSink())

    win._sink.put_evt(DecoratorEvt(name="char", args=["alice"], kind="stop"))
    assert ("remove", "alice") in calls


def test_main_window_close_clears_image_renderer_and_unregisters(fake_pyqt6_img):
    """MainWindow.close() → image_renderer.clear() + bg/char 注销。"""
    from runtime.gui import pyqt6_main
    from runtime.gui.pyqt6_sink import PyQt6Sink
    from runtime.gui.pyqt6_input import PyQt6InputSink
    from core.decorators import bg as bg_mod
    from core.decorators import char as char_mod

    clear_calls: list = []

    class FakeRenderer:
        def set_background(self, src): pass
        def clear_background(self): pass
        def set_character(self, name, src, pos="center"): pass
        def remove_character(self, name): pass
        def clear(self):
            clear_calls.append(True)

    MainWindowCls = pyqt6_main._build_main_window_class(image_renderer=FakeRenderer())
    win = MainWindowCls(sink=PyQt6Sink(), input_sink=PyQt6InputSink())
    assert bg_mod.get_image_manager() is not None
    assert char_mod.get_image_manager() is not None

    win.close()

    assert len(clear_calls) >= 1
    assert bg_mod.get_image_manager() is None
    assert char_mod.get_image_manager() is None
