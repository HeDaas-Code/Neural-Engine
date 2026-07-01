"""v3-03 · AudioManager 真实现测试（#93）。

验证 issue #93 验收点：
- AudioManager 类：play/stop/set_volume/fade 接口
- 三轨分离：BGM（循环默认）/ SE（单次）/ Voice
- player_factory 注入（fake backend，测试隔离）
- 路径解析：相对 chapters_root / 绝对路径 / 不存在
- 降级 no-op：PyQt6.QtMultimedia 未装 → lazy import 失败 → 不抛错
- BGM 默认 loop=True（背景音乐循环）

测试策略：
- 注入 fake player_factory → 返回记录型 fake player，断言调用序列
- 用 tmp_path 构造真音频文件，验证路径解析
- monkeypatch sys.modules 强制 QMediaPlayer import 失败 → 验证降级
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")

from runtime.audio import AudioManager, DEFAULT_VOLUME


# ─── Fake Player（记录型，验证调用序列）──────────────────────────────────


class FakePlayer:
    """Fake QMediaPlayer —— 记录所有调用。"""

    def __init__(self):
        self.source = None
        self.loops = None
        self.volume = None
        self.is_playing = False
        self.calls: list[tuple] = []  # 记录所有调用顺序

    def setSource(self, source):
        self.source = source
        self.calls.append(("setSource", source))

    def setLoops(self, n):
        self.loops = n
        self.calls.append(("setLoops", n))

    def setVolume(self, v):
        self.volume = v
        self.calls.append(("setVolume", v))

    def play(self):
        self.is_playing = True
        self.calls.append(("play",))

    def stop(self):
        self.is_playing = False
        self.calls.append(("stop",))


class FailingPlayer:
    """play() 抛异常的 fake player —— 验证异常处理。"""

    def setSource(self, source):
        raise RuntimeError("boom setSource")

    def setLoops(self, n):
        pass

    def setVolume(self, v):
        pass

    def play(self):
        raise RuntimeError("boom play")

    def stop(self):
        pass


# ─── 1. 构造与默认状态 ────────────────────────────────────────────────────


def test_audio_manager_constructs_with_defaults():
    """AudioManager 默认构造：chapters_root='chapters'，三轨音量 DEFAULT_VOLUME。"""
    mgr = AudioManager()
    assert mgr is not None
    assert mgr.get_volume("bgm") == DEFAULT_VOLUME
    assert mgr.get_volume("se") == DEFAULT_VOLUME
    assert mgr.get_volume("voice") == DEFAULT_VOLUME
    assert mgr.get_current_source("bgm") is None
    assert mgr.get_current_source("se") is None
    assert mgr.get_current_source("voice") is None


def test_audio_manager_accepts_custom_chapters_root(tmp_path):
    """chapters_root 可自定义（影响路径解析）。"""
    mgr = AudioManager(chapters_root=str(tmp_path))
    assert str(mgr._chapters_root) == str(tmp_path)


def test_audio_manager_get_volume_unknown_track_returns_default():
    """未知轨的 get_volume 返回 DEFAULT_VOLUME（不抛 KeyError）。"""
    mgr = AudioManager()
    assert mgr.get_volume("unknown") == DEFAULT_VOLUME


def test_audio_manager_get_current_source_unknown_track_returns_none():
    """未知轨的 get_current_source 返回 None（不抛 KeyError）。"""
    mgr = AudioManager()
    assert mgr.get_current_source("unknown") is None


# ─── 2. play() 路径解析 ──────────────────────────────────────────────────


def test_play_returns_false_when_file_not_found():
    """文件不存在 → 返回 False（不抛错，记 warning）。"""
    mgr = AudioManager(chapters_root="/nonexistent_root")
    assert mgr.play("ghost.mp3") is False
    assert mgr.get_current_source("bgm") is None


def test_play_resolves_relative_to_chapters_root(tmp_path):
    """相对路径 → 相对 chapters_root 解析（文件存在时成功）。"""
    (tmp_path / "rain.mp3").write_text("fake audio")
    players = []
    mgr = AudioManager(
        chapters_root=str(tmp_path),
        player_factory=lambda: (players.append(FakePlayer()), players[-1])[1],
    )

    assert mgr.play("rain.mp3") is True
    assert mgr.get_current_source("bgm") == "rain.mp3"
    assert len(players) == 1
    assert players[0].is_playing is True
    # setSource 被调用（路径对象或字符串）
    assert any(c[0] == "setSource" for c in players[0].calls)


def test_play_accepts_absolute_path(tmp_path):
    """绝对路径直接用（不相对 chapters_root）。"""
    audio_file = tmp_path / "abs.mp3"
    audio_file.write_text("fake")
    players = []
    mgr = AudioManager(
        chapters_root="/nonexistent",
        player_factory=lambda: (players.append(FakePlayer()), players[-1])[1],
    )

    assert mgr.play(str(audio_file)) is True
    assert mgr.get_current_source("bgm") == str(audio_file)


def test_play_absolute_path_not_exist_returns_false(tmp_path):
    """绝对路径文件不存在 → False。"""
    mgr = AudioManager(player_factory=lambda: FakePlayer())
    fake_abs = str(tmp_path / "no_such.mp3")
    assert mgr.play(fake_abs) is False


# ─── 3. play() 三轨 + BGM 默认循环 ───────────────────────────────────────


def test_play_bgm_defaults_to_loop(tmp_path):
    """BGM 轨默认 loop=True（setLoops(0)=无限循环）。"""
    (tmp_path / "bgm.mp3").write_text("x")
    players = []
    mgr = AudioManager(
        chapters_root=str(tmp_path),
        player_factory=lambda: (players.append(FakePlayer()), players[-1])[1],
    )

    mgr.play("bgm.mp3", track="bgm")
    assert players[0].loops == 0  # 0 = 无限循环


def test_play_bgm_explicit_loop_false_still_loops(tmp_path):
    """BGM 轨即使传 loop=False 也强制 loop=True（BGM 总是循环）。"""
    (tmp_path / "bgm.mp3").write_text("x")
    players = []
    mgr = AudioManager(
        chapters_root=str(tmp_path),
        player_factory=lambda: (players.append(FakePlayer()), players[-1])[1],
    )

    mgr.play("bgm.mp3", track="bgm", loop=False)
    assert players[0].loops == 0  # BGM 强制循环


def test_play_se_defaults_to_no_loop(tmp_path):
    """SE 轨默认 loop=False（setLoops(1)=单次）。"""
    (tmp_path / "se.mp3").write_text("x")
    players = []
    mgr = AudioManager(
        chapters_root=str(tmp_path),
        player_factory=lambda: (players.append(FakePlayer()), players[-1])[1],
    )

    mgr.play("se.mp3", track="se")
    assert players[0].loops == 1  # 1 = 单次


def test_play_voice_defaults_to_no_loop(tmp_path):
    """Voice 轨默认 loop=False。"""
    (tmp_path / "voice.mp3").write_text("x")
    players = []
    mgr = AudioManager(
        chapters_root=str(tmp_path),
        player_factory=lambda: (players.append(FakePlayer()), players[-1])[1],
    )

    mgr.play("voice.mp3", track="voice")
    assert players[0].loops == 1


def test_play_unknown_track_returns_false(tmp_path):
    """未知 track（非 bgm/se/voice）→ 返回 False。"""
    (tmp_path / "x.mp3").write_text("x")
    mgr = AudioManager(chapters_root=str(tmp_path), player_factory=lambda: FakePlayer())
    assert mgr.play("x.mp3", track="invalid") is False


def test_play_sets_volume_from_current_track_volume(tmp_path):
    """play 时应用当前轨音量到 player.setVolume。"""
    (tmp_path / "x.mp3").write_text("x")
    players = []
    mgr = AudioManager(
        chapters_root=str(tmp_path),
        player_factory=lambda: (players.append(FakePlayer()), players[-1])[1],
    )
    mgr.set_volume(42, track="bgm")

    mgr.play("x.mp3", track="bgm")
    assert players[0].volume == 42


# ─── 4. play() 异常处理 ──────────────────────────────────────────────────


def test_play_player_exception_returns_false(tmp_path):
    """player.play() 抛异常 → 返回 False（不向上抛）。"""
    (tmp_path / "x.mp3").write_text("x")
    mgr = AudioManager(
        chapters_root=str(tmp_path),
        player_factory=lambda: FailingPlayer(),
    )
    assert mgr.play("x.mp3") is False


def test_play_reuses_player_on_second_call(tmp_path):
    """同一轨第二次 play → 复用 player（不创建新实例）。"""
    (tmp_path / "a.mp3").write_text("x")
    (tmp_path / "b.mp3").write_text("x")
    players = []
    mgr = AudioManager(
        chapters_root=str(tmp_path),
        player_factory=lambda: (players.append(FakePlayer()), players[-1])[1],
    )

    mgr.play("a.mp3", track="bgm")
    mgr.play("b.mp3", track="bgm")
    assert len(players) == 1  # 复用
    assert mgr.get_current_source("bgm") == "b.mp3"


def test_play_different_tracks_create_different_players(tmp_path):
    """不同轨 → 各自创建独立 player。"""
    (tmp_path / "a.mp3").write_text("x")
    (tmp_path / "b.mp3").write_text("x")
    players = []
    mgr = AudioManager(
        chapters_root=str(tmp_path),
        player_factory=lambda: (players.append(FakePlayer()), players[-1])[1],
    )

    mgr.play("a.mp3", track="bgm")
    mgr.play("b.mp3", track="se")
    assert len(players) == 2  # bgm + se 各一


# ─── 5. stop() ───────────────────────────────────────────────────────────


def test_stop_specific_track_calls_player_stop(tmp_path):
    """stop(track='bgm') → bgm player.stop() 被调。"""
    (tmp_path / "x.mp3").write_text("x")
    players = []
    mgr = AudioManager(
        chapters_root=str(tmp_path),
        player_factory=lambda: (players.append(FakePlayer()), players[-1])[1],
    )
    mgr.play("x.mp3", track="bgm")
    assert players[0].is_playing is True

    mgr.stop(track="bgm")
    assert players[0].is_playing is False
    assert mgr.get_current_source("bgm") is None


def test_stop_all_tracks_when_track_none(tmp_path):
    """stop(track=None) → 停止所有已创建 player。"""
    (tmp_path / "a.mp3").write_text("x")
    (tmp_path / "b.mp3").write_text("x")
    players = []
    mgr = AudioManager(
        chapters_root=str(tmp_path),
        player_factory=lambda: (players.append(FakePlayer()), players[-1])[1],
    )
    mgr.play("a.mp3", track="bgm")
    mgr.play("b.mp3", track="se")
    assert all(p.is_playing for p in players)

    mgr.stop()  # 停止所有
    assert all(not p.is_playing for p in players)
    assert mgr.get_current_source("bgm") is None
    assert mgr.get_current_source("se") is None


def test_stop_without_players_is_noop():
    """stop() 在无 player 时不抛错（no-op）。"""
    mgr = AudioManager()
    mgr.stop()  # 不抛
    mgr.stop(track="bgm")  # 不抛


def test_stop_unknown_track_silent():
    """stop(track='unknown') 不抛错。"""
    mgr = AudioManager()
    mgr.stop(track="unknown")  # 不抛


# ─── 6. set_volume() ─────────────────────────────────────────────────────


def test_set_volume_all_tracks_when_track_none():
    """set_volume(v, track=None) → 设置所有三轨音量。"""
    mgr = AudioManager()
    mgr.set_volume(33)
    assert mgr.get_volume("bgm") == 33
    assert mgr.get_volume("se") == 33
    assert mgr.get_volume("voice") == 33


def test_set_volume_specific_track():
    """set_volume(v, track='se') → 只改 se 音量。"""
    mgr = AudioManager()
    mgr.set_volume(50, track="se")
    assert mgr.get_volume("se") == 50
    # bgm/voice 不变
    assert mgr.get_volume("bgm") == DEFAULT_VOLUME
    assert mgr.get_volume("voice") == DEFAULT_VOLUME


def test_set_volume_clamps_to_0_100():
    """音量超出 0-100 → 钳制到边界。"""
    mgr = AudioManager()
    mgr.set_volume(150)
    assert mgr.get_volume("bgm") == 100
    mgr.set_volume(-20)
    assert mgr.get_volume("bgm") == 0


def test_set_volume_applies_to_active_player(tmp_path):
    """set_volume 对已 play 的 player 立即生效（调 player.setVolume）。"""
    (tmp_path / "x.mp3").write_text("x")
    players = []
    mgr = AudioManager(
        chapters_root=str(tmp_path),
        player_factory=lambda: (players.append(FakePlayer()), players[-1])[1],
    )
    mgr.play("x.mp3", track="bgm")
    assert players[0].volume == DEFAULT_VOLUME

    mgr.set_volume(60, track="bgm")
    assert players[0].volume == 60


# ─── 7. fade()（v3-03 简化为立即 stop）──────────────────────────────────


def test_fade_stops_audio(tmp_path):
    """fade(duration) → v3-03 简化为立即 stop。"""
    (tmp_path / "x.mp3").write_text("x")
    players = []
    mgr = AudioManager(
        chapters_root=str(tmp_path),
        player_factory=lambda: (players.append(FakePlayer()), players[-1])[1],
    )
    mgr.play("x.mp3", track="bgm")
    assert players[0].is_playing is True

    mgr.fade(2.0, track="bgm")
    # v3-03 简化：直接 stop
    assert players[0].is_playing is False
    assert mgr.get_current_source("bgm") is None


def test_fade_all_tracks_when_track_none(tmp_path):
    """fade(track=None) → 停止所有轨。"""
    (tmp_path / "a.mp3").write_text("x")
    (tmp_path / "b.mp3").write_text("x")
    players = []
    mgr = AudioManager(
        chapters_root=str(tmp_path),
        player_factory=lambda: (players.append(FakePlayer()), players[-1])[1],
    )
    mgr.play("a.mp3", track="bgm")
    mgr.play("b.mp3", track="se")

    mgr.fade(1.5)
    assert all(not p.is_playing for p in players)


# ─── 8. 降级 no-op（PyQt6.QtMultimedia 未装）────────────────────────────


def test_play_downgrades_to_noop_when_qmediaplayer_unavailable(monkeypatch, tmp_path):
    """无 player_factory + PyQt6.QtMultimedia import 失败 → 降级 no-op，返回 True。"""
    (tmp_path / "x.mp3").write_text("x")
    # 强制 PyQt6.QtMultimedia import 失败
    monkeypatch.setitem(sys.modules, "PyQt6.QtMultimedia", None)

    mgr = AudioManager(chapters_root=str(tmp_path))
    # 降级 no-op：返回 True，current_source 被记录
    assert mgr.play("x.mp3") is True
    assert mgr.get_current_source("bgm") == "x.mp3"


def test_stop_silent_when_no_player_created():
    """降级模式下 stop() 不抛错。"""
    mgr = AudioManager()
    mgr.stop()
    mgr.stop(track="bgm")


def test_set_volume_silent_when_no_player():
    """降级模式下 set_volume() 只更新内部状态，不抛错。"""
    mgr = AudioManager()
    mgr.set_volume(50, track="bgm")
    assert mgr.get_volume("bgm") == 50


# ─── 9. @bgm 装饰器对接 AudioManager（v3-03 集成）──────────────────────


@pytest.fixture(autouse=True)
def _reset_bgm_state():
    """每个测试前后清空 bgm 装饰器状态。"""
    from core.decorators import clear
    from core.decorators import bgm as bgm_mod
    clear()
    bgm_mod.reset_last_bgm()
    bgm_mod.set_audio_manager(None)  # 清除已注册的 mgr
    yield
    clear()
    bgm_mod.reset_last_bgm()
    bgm_mod.set_audio_manager(None)


def test_bgm_set_audio_manager_registers_mgr():
    """bgm.set_audio_manager(mgr) → 后续 @bgm 调用转发到 mgr.play。"""
    from core.decorators import bgm as bgm_mod
    from core.engine.protocol import DecoratorEvt

    calls: list = []

    class FakeMgr:
        def play(self, source, track="bgm", loop=False):
            calls.append(("play", source, track, loop))
            return True

        def stop(self, track=None):
            calls.append(("stop", track))

    mgr = FakeMgr()
    bgm_mod.set_audio_manager(mgr)
    bgm_mod.install()

    bgm_mod.handle(DecoratorEvt(name="bgm", args=["rain.mp3"]))

    assert ("play", "rain.mp3", "bgm", True) in calls


def test_bgm_handle_still_records_last_bgm_for_backward_compat():
    """注册 mgr 后，_LAST_BGM 仍被记录（向后兼容已有测试）。"""
    from core.decorators import bgm as bgm_mod
    from core.engine.protocol import DecoratorEvt

    class FakeMgr:
        def play(self, source, track="bgm", loop=False):
            return True

        def stop(self, track=None):
            pass

    bgm_mod.set_audio_manager(FakeMgr())
    bgm_mod.install()

    bgm_mod.handle(DecoratorEvt(name="bgm", args=["rain.mp3"]))
    assert bgm_mod.get_last_bgm() == [("play", "rain.mp3")]


def test_bgm_handle_stop_kind_calls_mgr_stop():
    """@bgm kind='stop' → mgr.stop() 被调。"""
    from core.decorators import bgm as bgm_mod
    from core.engine.protocol import DecoratorEvt

    calls: list = []

    class FakeMgr:
        def play(self, source, track="bgm", loop=False):
            return True

        def stop(self, track=None):
            calls.append(("stop", track))

    bgm_mod.set_audio_manager(FakeMgr())
    bgm_mod.install()

    bgm_mod.handle(DecoratorEvt(name="bgm", args=["rain.mp3"], kind="stop"))
    assert ("stop", "bgm") in calls
    assert bgm_mod.get_last_bgm() == [("stop", "rain.mp3")]


def test_bgm_handle_multi_args_calls_mgr_play_multiple_times():
    """@bgm arg1 arg2 → mgr.play 被调两次。"""
    from core.decorators import bgm as bgm_mod
    from core.engine.protocol import DecoratorEvt

    calls: list = []

    class FakeMgr:
        def play(self, source, track="bgm", loop=False):
            calls.append(("play", source))
            return True

        def stop(self, track=None):
            calls.append(("stop", track))

    bgm_mod.set_audio_manager(FakeMgr())
    bgm_mod.install()

    bgm_mod.handle(DecoratorEvt(name="bgm", args=["rain.mp3", "storm.mp3"]))
    assert ("play", "rain.mp3") in calls
    assert ("play", "storm.mp3") in calls


def test_bgm_handle_without_mgr_only_records():
    """未注册 mgr → 仅记录 _LAST_BGM（v2 行为基线，向后兼容）。"""
    from core.decorators import bgm as bgm_mod
    from core.engine.protocol import DecoratorEvt

    bgm_mod.install()
    bgm_mod.handle(DecoratorEvt(name="bgm", args=["rain.mp3"]))

    assert bgm_mod.get_last_bgm() == [("play", "rain.mp3")]


def test_bgm_handle_mgr_play_exception_silent():
    """mgr.play 抛异常 → handle 不向上抛（hook 不能崩 dispatcher）。"""
    from core.decorators import bgm as bgm_mod
    from core.engine.protocol import DecoratorEvt

    class BadMgr:
        def play(self, source, track="bgm", loop=False):
            raise RuntimeError("boom")

        def stop(self, track=None):
            raise RuntimeError("boom stop")

    bgm_mod.set_audio_manager(BadMgr())
    bgm_mod.install()

    # 不抛
    bgm_mod.handle(DecoratorEvt(name="bgm", args=["rain.mp3"]))
    bgm_mod.handle(DecoratorEvt(name="bgm", args=["rain.mp3"], kind="stop"))


def test_bgm_dispatch_routes_to_mgr_via_registry():
    """dispatch(DecoratorEvt(name='bgm', ...)) → 通过 registry 触发 handle → 调 mgr。"""
    from core.decorators import bgm as bgm_mod, dispatch
    from core.engine.protocol import DecoratorEvt

    calls: list = []

    class FakeMgr:
        def play(self, source, track="bgm", loop=False):
            calls.append(("play", source))
            return True

        def stop(self, track=None):
            calls.append(("stop", track))

    bgm_mod.set_audio_manager(FakeMgr())
    bgm_mod.install()

    dispatch(DecoratorEvt(name="bgm", args=["storm.mp3"]))
    assert ("play", "storm.mp3") in calls
