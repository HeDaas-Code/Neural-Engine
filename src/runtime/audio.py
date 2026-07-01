"""AudioManager —— v3-03 真实现（BGM/SE/Voice 三轨播放）。

职责：
- play(bgm) / stop() / set_volume(vol) / fade(time)
- 三轨分离：BGM（循环）/ SE（单次）/ Voice（语音）
- @bgm call → play / @bgm stop → stop（对接装饰器钩子）
- 音频文件路径解析：相对 chapters/ 目录
- QMediaPlayer 选型（PyQt6 优先，减少依赖）

设计：
- 不直接 import PyQt6（lazy import），便于测试注入 fake backend
- 接受可选 player_factory（测试注入 fake），默认 lazy 创建 QMediaPlayer
- 无音频设备/PyQt6 未装时降级为 no-op（不抛错，记日志）
- 音量控制接口（为 v3-08 设置菜单留接口）
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Callable

logger = logging.getLogger(__name__)


# 默认音量（0-100）
DEFAULT_VOLUME = 80


class AudioManager:
    """v3-03 音频管理器（BGM/SE/Voice 三轨）。

    用法：
        mgr = AudioManager(chapters_root="chapters")
        mgr.play("rain.mp3", track="bgm")  # 播放 BGM（循环）
        mgr.play("se/door.mp3", track="se")  # 播放 SE（单次）
        mgr.stop(track="bgm")  # 停止 BGM
        mgr.set_volume(50, track="bgm")  # 设置 BGM 音量
        mgr.fade(2.0, track="bgm")  # 2 秒淡出 BGM

    线程安全：QMediaPlayer 必须在 GUI 线程操作。
    """

    def __init__(
        self,
        chapters_root: str = "chapters",
        player_factory: Optional[Callable] = None,
    ):
        """Args:
            chapters_root: 章节根目录（音频文件相对此目录解析）
            player_factory: 可选 callable，返回 player 实例（测试注入 fake）。
                None 时 lazy import QMediaPlayer。factory 签名：() -> player
                player 需有 setSource/setLoops/play/stop/setVolume 方法。
        """
        self._chapters_root = Path(chapters_root)
        self._player_factory = player_factory
        # 三轨独立 player（lazy 创建）
        self._players: dict[str, object] = {}  # track → player
        self._volumes: dict[str, int] = {  # 各轨音量
            "bgm": DEFAULT_VOLUME,
            "se": DEFAULT_VOLUME,
            "voice": DEFAULT_VOLUME,
        }
        self._current_source: dict[str, Optional[str]] = {  # 各轨当前源
            "bgm": None,
            "se": None,
            "voice": None,
        }

    def play(
        self,
        source: str,
        track: str = "bgm",
        loop: bool = False,
    ) -> bool:
        """播放音频。

        Args:
            source: 音频文件路径（相对 chapters_root 或绝对路径）
            track: "bgm" / "se" / "voice"（BGM 默认 loop=True）
            loop: 是否循环播放（BGM 默认 True，SE/Voice 默认 False）

        Returns:
            True —— 成功开始播放（或降级 no-op 但不报错）
            False —— 文件不存在或 player 创建失败

        BGM 轨默认 loop=True（背景音乐循环）；SE/Voice 默认 loop=False。
        """
        if track not in self._players and track not in ("bgm", "se", "voice"):
            return False

        # BGM 默认循环
        if track == "bgm" and not loop:
            loop = True

        # 解析路径
        path = self._resolve_path(source)
        if path is None:
            logger.warning("AudioManager.play: 音频文件不存在: %s", source)
            return False

        player = self._get_or_create_player(track)
        if player is None:
            # 无 player（PyQt6 未装/无音频设备）→ 降级 no-op，记状态供测试
            self._current_source[track] = source
            logger.info("AudioManager.play: 降级 no-op（无 player）: %s", source)
            return True

        try:
            # 设置源 + 循环 + 音量 + 播放
            self._set_source(player, path)
            self._set_loops(player, loop)
            self._set_volume(player, self._volumes[track])
            player.play()
            self._current_source[track] = source
            return True
        except Exception as e:
            logger.warning("AudioManager.play 失败: %s", e)
            return False

    def stop(self, track: Optional[str] = None) -> None:
        """停止播放。

        Args:
            track: 指定轨停止；None=停止所有轨
        """
        tracks = [track] if track else list(self._players.keys())
        for t in tracks:
            player = self._players.get(t)
            if player is not None:
                try:
                    player.stop()
                except Exception:
                    pass
            self._current_source[t] = None

    def set_volume(self, volume: int, track: Optional[str] = None) -> None:
        """设置音量。

        Args:
            volume: 0-100
            track: 指定轨；None=所有轨
        """
        volume = max(0, min(100, volume))
        tracks = [track] if track else ["bgm", "se", "voice"]
        for t in tracks:
            self._volumes[t] = volume
            player = self._players.get(t)
            if player is not None:
                self._set_volume(player, volume)

    def fade(self, duration: float, track: Optional[str] = None) -> None:
        """淡出音频（v3-03 简化：直接 stop，真正 fade 需要 QPropertyAnimation）。

        Args:
            duration: 淡出秒数（v3-03 简化忽略，直接 stop；v3+ 可接 QTimer 渐变）
            track: 指定轨；None=所有轨

        注：真正淡出效果需要 QTimer 渐变音量，v3-03 简化为立即 stop。
        v3-08 设置菜单或 v4 可补 QPropertyAnimation 渐变。
        """
        # v3-03 简化：直接 stop（duration 参数保留接口，v3+ 实现渐变）
        logger.info("AudioManager.fade: %ss 淡出（v3-03 简化为立即 stop）", duration)
        self.stop(track)

    def get_current_source(self, track: str = "bgm") -> Optional[str]:
        """取当前播放源（测试断言用）。"""
        return self._current_source.get(track)

    def get_volume(self, track: str = "bgm") -> int:
        """取当前音量。"""
        return self._volumes.get(track, DEFAULT_VOLUME)

    # ─── 内部方法 ───────────────────────────────────────────────────────────

    def _resolve_path(self, source: str) -> Optional[Path]:
        """解析音频文件路径。

        - 绝对路径 → 直接用
        - 相对路径 → 相对 chapters_root
        返回 Path（存在）或 None（不存在）。
        """
        p = Path(source)
        if p.is_absolute():
            return p if p.exists() else None
        # 相对 chapters_root
        resolved = self._chapters_root / source
        if resolved.exists():
            return resolved
        # 也尝试相对 cwd（测试用 tmp 文件）
        if p.exists():
            return p
        return None

    def _get_or_create_player(self, track: str):
        """获取或创建指定轨的 player（lazy）。"""
        if track in self._players:
            return self._players[track]
        if self._player_factory is not None:
            player = self._player_factory()
            self._players[track] = player
            return player
        # lazy import QMediaPlayer
        try:
            from PyQt6.QtMultimedia import QMediaPlayer
            from PyQt6.QtCore import QUrl
            player = QMediaPlayer()
            self._players[track] = player
            # 保存 QUrl 供 _set_source 用
            self._players[f"{track}_QUrl"] = QUrl
            return player
        except ImportError:
            logger.info("PyQt6.QtMultimedia 未装，AudioManager 降级 no-op")
            return None

    def _set_source(self, player, path: Path) -> None:
        """设置 player 源（兼容 fake backend）。"""
        # 真 QMediaPlayer 用 setSource(QUrl)
        track = None
        for t, p in self._players.items():
            if p is player:
                track = t
                break
        QUrl = self._players.get(f"{track}_QUrl") if track else None
        if QUrl is not None:
            from PyQt6.QtCore import QUrl as QUrlCls
            player.setSource(QUrlCls.fromLocalFile(str(path)))
        else:
            # fake backend：尝试 setSource(path) 或 setSource(str)
            try:
                player.setSource(path)
            except Exception:
                try:
                    player.setSource(str(path))
                except Exception:
                    pass

    def _set_loops(self, player, loop: bool) -> None:
        """设置循环（兼容 fake）。"""
        try:
            if loop:
                # QMediaPlayer.setLoops(0)=无限循环
                if hasattr(player, "setLoops"):
                    player.setLoops(0)
            else:
                if hasattr(player, "setLoops"):
                    player.setLoops(1)
        except Exception:
            pass

    def _set_volume(self, player, volume: int) -> None:
        """设置音量（兼容 fake）。QMediaPlayer 音量 0-1 float。"""
        try:
            if hasattr(player, "setVolume"):
                # QMediaPlayer 6.x: setVolume(0-100 int)
                player.setVolume(volume)
        except Exception:
            pass


__all__ = ["AudioManager", "DEFAULT_VOLUME"]
