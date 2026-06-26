"""v2-p0 · 装饰器运行时钩子（@style / @bgm）测试。

按 PDR §5.1.2（PDR phase3-v2p0.md） + V2-02 issue 验收：
- `core/decorators/__init__.py` 提供 `register` / `unregister` / `clear` / `dispatch`
- `core/decorators/style.py` 默认 `@style` 钩子：解析 key:val → 设置样式（颜色/字体/大小）
- `core/decorators/bgm.py` 默认 `@bgm` 钩子：解析 path → 记录 play/stop

约束：
- 测试不应依赖 PyQt6 / runtime 子包（钩子是 core 层，runtime 是消费者）
- 测试不应依赖 fixtures（钩子是纯函数 + 模块状态）
- v2 阶段钩子**不实际播放/渲染**，仅记录调用（v3+ 接管）
"""
from __future__ import annotations

import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")


# ─── 模块级 fixture：每个测试前后清空全局状态 ────────────────────────────


@pytest.fixture(autouse=True)
def _reset_hook_registry():
    """每个测试前后清空 registry + style/bgm 内部状态——避免顺序耦合。"""
    from core.decorators import clear
    from core.decorators import style as style_mod
    from core.decorators import bgm as bgm_mod

    clear()
    style_mod.reset_last_style()
    bgm_mod.reset_last_bgm()
    yield
    clear()
    style_mod.reset_last_style()
    bgm_mod.reset_last_bgm()


# ─── 1. registry（core/decorators/__init__.py）───


def test_register_and_dispatch_calls_handler():
    """register(name, fn) → dispatch(evt) 调用 fn(evt)。"""
    from core.decorators import register, dispatch
    from core.engine.protocol import DecoratorEvt

    received: list = []

    def my_hook(evt):
        received.append(evt)

    register("custom", my_hook)
    evt = DecoratorEvt(name="custom", args=["x"])
    handled = dispatch(evt)
    assert handled is True
    assert received == [evt]


def test_dispatch_unknown_name_returns_false_and_silent():
    """未注册的 name → dispatch 返回 False，不抛错。"""
    from core.decorators import dispatch
    from core.engine.protocol import DecoratorEvt

    evt = DecoratorEvt(name="nope", args=["x"])
    # 不抛错
    handled = dispatch(evt)
    assert handled is False


def test_register_overrides_previous_handler():
    """重复 register 同一个 name → 后注册覆盖前注册（last-write-wins）。"""
    from core.decorators import register, dispatch
    from core.engine.protocol import DecoratorEvt

    first_calls: list = []
    second_calls: list = []

    register("dup", lambda evt: first_calls.append(evt))
    register("dup", lambda evt: second_calls.append(evt))  # 覆盖

    evt = DecoratorEvt(name="dup", args=["x"])
    dispatch(evt)
    assert first_calls == []
    assert second_calls == [evt]


def test_unregister_removes_hook():
    """unregister(name) → dispatch 静默返回 False。"""
    from core.decorators import register, unregister, dispatch, get_hook
    from core.engine.protocol import DecoratorEvt

    def hook(evt):
        pass

    register("removable", hook)
    assert get_hook("removable") is hook

    removed = unregister("removable")
    assert removed is True
    assert get_hook("removable") is None

    # 移除后 dispatch 静默
    evt = DecoratorEvt(name="removable", args=["x"])
    assert dispatch(evt) is False


def test_unregister_unknown_returns_false():
    """unregister 不存在的 name → 返回 False，不抛错。"""
    from core.decorators import unregister

    assert unregister("never_registered") is False


def test_clear_resets_all_hooks():
    """clear() → 所有钩子清空。"""
    from core.decorators import register, clear, dispatch, get_hook
    from core.engine.protocol import DecoratorEvt

    register("a", lambda evt: None)
    register("b", lambda evt: None)
    clear()
    assert get_hook("a") is None
    assert get_hook("b") is None

    assert dispatch(DecoratorEvt(name="a", args=[])) is False
    assert dispatch(DecoratorEvt(name="b", args=[])) is False


# ─── 2. @style 钩子（core/decorators/style.py）───


def test_style_install_registers_default_style_hook():
    """style.install() → 'style' 钩子被注册。"""
    from core.decorators import get_hook
    from core.decorators import style as style_mod

    style_mod.install()
    assert get_hook("style") is not None


def test_style_hook_parses_key_val_into_color_font_size():
    """@style color:red font:arial size:14 → 颜色/字体/大小 被分别设置。"""
    from core.decorators import style as style_mod
    from core.engine.protocol import DecoratorEvt

    style_mod.install()
    evt = DecoratorEvt(name="style", args=["color:red", "font:arial", "size:14"])
    style_mod.handle(evt)  # 直接调 handle，便于断言

    s = style_mod.get_last_style()
    assert s["color"] == "red"
    assert s["font"] == "arial"
    assert s["size"] == "14"


def test_style_hook_ignores_stop_kind():
    """kind='stop' → 不写 _LAST_STYLE（v2 阶段不处理 stop 语义）。"""
    from core.decorators import style as style_mod
    from core.engine.protocol import DecoratorEvt

    style_mod.install()
    evt = DecoratorEvt(name="style", args=["color:red"], kind="stop")
    style_mod.handle(evt)

    assert style_mod.get_last_style() == {}


def test_style_hook_ignores_args_without_colon():
    """无冒号的 arg 被忽略（不抛错）。"""
    from core.decorators import style as style_mod
    from core.engine.protocol import DecoratorEvt

    style_mod.install()
    evt = DecoratorEvt(name="style", args=["plain", "color:red"])
    style_mod.handle(evt)

    s = style_mod.get_last_style()
    assert s == {"color": "red"}
    assert "plain" not in s


def test_style_hook_dispatch_routes_via_registry():
    """dispatch(DecoratorEvt(name='style', ...)) → 调 style 钩子（注册表 + dispatcher 集成）。"""
    from core.decorators import style as style_mod
    from core.engine.protocol import DecoratorEvt

    style_mod.install()
    evt = DecoratorEvt(name="style", args=["size:16"])
    # 集成路径：通过 dispatcher
    from core.decorators import dispatch
    handled = dispatch(evt)
    assert handled is True
    assert style_mod.get_last_style()["size"] == "16"


# ─── 3. @bgm 钩子（core/decorators/bgm.py）───


def test_bgm_install_registers_default_bgm_hook():
    """bgm.install() → 'bgm' 钩子被注册。"""
    from core.decorators import get_hook
    from core.decorators import bgm as bgm_mod

    bgm_mod.install()
    assert get_hook("bgm") is not None


def test_bgm_hook_play_kind_records_path():
    """@bgm rain.mp3 (kind='call') → ('play', 'rain.mp3') 被记录。"""
    from core.decorators import bgm as bgm_mod
    from core.engine.protocol import DecoratorEvt

    bgm_mod.install()
    evt = DecoratorEvt(name="bgm", args=["rain.mp3"])
    bgm_mod.handle(evt)

    assert bgm_mod.get_last_bgm() == [("play", "rain.mp3")]


def test_bgm_hook_stop_kind_records_stop():
    """@bgm kind='stop' → ('stop', key) 被记录（v2 仅记录，v3+ 真实停止）。"""
    from core.decorators import bgm as bgm_mod
    from core.engine.protocol import DecoratorEvt

    bgm_mod.install()
    evt = DecoratorEvt(name="bgm", args=["rain.mp3"], kind="stop")
    bgm_mod.handle(evt)

    assert bgm_mod.get_last_bgm() == [("stop", "rain.mp3")]


def test_bgm_hook_dispatch_routes_via_registry():
    """dispatch(DecoratorEvt(name='bgm', ...)) → 调 bgm 钩子。"""
    from core.decorators import bgm as bgm_mod
    from core.engine.protocol import DecoratorEvt
    from core.decorators import dispatch

    bgm_mod.install()
    evt = DecoratorEvt(name="bgm", args=["storm.mp3"])
    handled = dispatch(evt)
    assert handled is True
    assert bgm_mod.get_last_bgm() == [("play", "storm.mp3")]


def test_bgm_hook_multi_args_each_recorded():
    """@bgm arg1 arg2 → 每个 arg 都生成一条记录。"""
    from core.decorators import bgm as bgm_mod
    from core.engine.protocol import DecoratorEvt

    bgm_mod.install()
    evt = DecoratorEvt(name="bgm", args=["rain.mp3", "storm.mp3"])
    bgm_mod.handle(evt)

    assert bgm_mod.get_last_bgm() == [
        ("play", "rain.mp3"),
        ("play", "storm.mp3"),
    ]


# ─── 4. 子包级集成 ───


def test_style_and_bgm_install_together_does_not_clash():
    """style.install() + bgm.install() → 两个钩子都注册，dispatch 按 name 路由。"""
    from core.decorators import style as style_mod
    from core.decorators import bgm as bgm_mod
    from core.engine.protocol import DecoratorEvt
    from core.decorators import dispatch

    style_mod.install()
    bgm_mod.install()

    dispatch(DecoratorEvt(name="style", args=["color:blue"]))
    dispatch(DecoratorEvt(name="bgm", args=["x.mp3"]))

    assert style_mod.get_last_style() == {"color": "blue"}
    assert bgm_mod.get_last_bgm() == [("play", "x.mp3")]
