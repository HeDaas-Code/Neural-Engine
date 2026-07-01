"""SettingsManager —— v3-08 全局配置持久化（#98）。

职责：
- 管理 settings.json 配置文件（默认 ~/.neural-engine/settings.json）
- 提供类型校验的 get/set API
- 默认值表（DEFAULT_SETTINGS）
- 应用到运行时组件（TextRenderer/AudioManager/AutoMode）

设计：
- 纯 Python（无 PyQt6 依赖）
- JSON 序列化（D2 决策风格：ensure_ascii=False + indent=2）
- 未知 key 静默忽略（向后兼容老配置）
- 类型校验：set 时校验，非法值返回 False
- load 失败（文件损坏/缺字段）→ 用默认值补齐

配置 schema（v3-08）：
    text_speed:    int   打字机每字延迟（ms），0=瞬时，默认 40
    auto_delay:    int   Auto 模式推进延迟（ms），默认 1500
    bgm_volume:    float BGM 音量（0.0-1.0），默认 0.7
    se_volume:     float SE 音量（0.0-1.0），默认 1.0
    voice_volume:  float Voice 音量（0.0-1.0），默认 1.0
    fullscreen:    bool  全屏模式，默认 False
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# 默认配置路径（与 SaveManager / ReadMarks 一致的 ~/.neural-engine 目录）
_DEFAULT_SETTINGS_FILE = Path.home() / ".neural-engine" / "settings.json"


# 默认配置（v3-08 schema）
DEFAULT_SETTINGS: dict[str, Any] = {
    "text_speed": 40,        # ms/char，0=瞬时
    "auto_delay": 1500,      # ms
    "bgm_volume": 0.7,       # 0.0-1.0
    "se_volume": 1.0,        # 0.0-1.0
    "voice_volume": 1.0,     # 0.0-1.0
    "fullscreen": False,     # bool
}


# 类型校验表（key → (type, validator)）
# validator 接受值返回 bool（True=合法）
def _is_int_nonneg(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def _is_volume(v) -> bool:
    if isinstance(v, bool):
        return False
    if not isinstance(v, (int, float)):
        return False
    return 0.0 <= float(v) <= 1.0


def _is_bool(v) -> bool:
    return isinstance(v, bool)


_VALIDATORS: dict[str, callable] = {
    "text_speed": _is_int_nonneg,
    "auto_delay": _is_int_nonneg,
    "bgm_volume": _is_volume,
    "se_volume": _is_volume,
    "voice_volume": _is_volume,
    "fullscreen": _is_bool,
}


class SettingsManager:
    """v3-08 全局配置管理器。

    用法：
        mgr = SettingsManager()  # 默认 ~/.neural-engine/settings.json
        mgr.set("text_speed", 20)
        mgr.save()
        # 重新加载
        mgr2 = SettingsManager()
        assert mgr2.get("text_speed") == 20

        # 应用到运行时组件
        text_renderer.char_delay_ms = mgr.get("text_speed")
        audio_mgr.set_bgm_volume(mgr.get("bgm_volume"))
    """

    def __init__(self, settings_file: Optional[Path | str] = None):
        """Args:
            settings_file: 配置文件路径。None → 默认 ~/.neural-engine/settings.json。
                给定路径时构造即加载（若文件存在）。
        """
        self._file: Path = Path(settings_file) if settings_file else _DEFAULT_SETTINGS_FILE
        self._settings: dict[str, Any] = dict(DEFAULT_SETTINGS)
        self._load()

    # ─── 查询 API ───

    def get(self, key: str, default: Any = None) -> Any:
        """取配置值。未知 key → default。"""
        if key in self._settings:
            return self._settings[key]
        return default

    def get_all(self) -> dict[str, Any]:
        """取全部配置（返回副本，外部修改不影响内部）。"""
        return dict(self._settings)

    # ─── 修改 API ───

    def set(self, key: str, value: Any) -> bool:
        """设置配置值。未知 key 或类型非法 → 返回 False。

        Returns:
            True —— 成功；False —— key 未知 / 类型非法。
        """
        if key not in _VALIDATORS:
            return False
        validator = _VALIDATORS[key]
        if not validator(value):
            return False
        # int 类型严格：bool 不算 int（已由 _is_int_nonneg 拦截）
        self._settings[key] = value
        return True

    def set_many(self, updates: dict[str, Any]) -> int:
        """批量设置。返回成功设置的项数（非法项跳过）。"""
        n = 0
        for k, v in updates.items():
            if self.set(k, v):
                n += 1
        return n

    def reset(self, key: Optional[str] = None) -> None:
        """重置配置。

        Args:
            key: 指定 key 重置为默认值。None → 全部重置为默认值。
        """
        if key is None:
            self._settings = dict(DEFAULT_SETTINGS)
        elif key in DEFAULT_SETTINGS:
            self._settings[key] = DEFAULT_SETTINGS[key]

    def reset_to_defaults(self) -> None:
        """重置全部为默认值（reset(None) 的别名）。"""
        self.reset(None)

    # ─── 持久化 ───

    def save(self) -> bool:
        """保存到 settings_file。写失败 → False。

        Returns:
            True —— 成功；False —— 写失败。
        """
        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            self._file.write_text(
                json.dumps(self._settings, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return True
        except OSError as e:
            logger.warning("SettingsManager.save failed: %s", e)
            return False

    def reload(self) -> None:
        """重新从文件加载（覆盖内存中未保存的修改）。"""
        self._settings = dict(DEFAULT_SETTINGS)
        self._load()

    def _load(self) -> None:
        """从 file 加载（文件不存在 / 解析失败 → 静默忽略，保留默认值）。"""
        if not self._file.exists():
            return
        try:
            data = json.loads(self._file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("SettingsManager._load failed: %s", e)
            return
        if not isinstance(data, dict):
            return
        # 只接受合法 key + 类型（非法项静默忽略）
        for k, v in data.items():
            if k in _VALIDATORS and _VALIDATORS[k](v):
                self._settings[k] = v

    # ─── 应用到运行时组件 ───

    def apply_to_text_renderer(self, renderer) -> None:
        """应用到 TextRenderer（text_speed → char_delay_ms）。"""
        try:
            renderer._char_delay_ms = int(self.get("text_speed", 40))
        except Exception as e:
            logger.debug("apply_to_text_renderer failed: %s", e)

    def apply_to_auto_mode(self, auto_mode) -> None:
        """应用到 AutoModeController（auto_delay → auto_delay_ms）。"""
        try:
            auto_mode.set_auto_delay(int(self.get("auto_delay", 1500)))
        except Exception as e:
            logger.debug("apply_to_auto_mode failed: %s", e)

    def apply_to_audio_manager(self, audio_manager) -> None:
        """应用到 AudioManager（三轨音量）。

        AudioManager 用 0-100 int 音量；本配置用 0.0-1.0 float，转换公式：int(v*100)。
        """
        try:
            bgm_vol = int(float(self.get("bgm_volume", 0.7)) * 100)
            audio_manager.set_volume(bgm_vol, track="bgm")
        except Exception:
            pass
        try:
            se_vol = int(float(self.get("se_volume", 1.0)) * 100)
            audio_manager.set_volume(se_vol, track="se")
        except Exception:
            pass
        try:
            voice_vol = int(float(self.get("voice_volume", 1.0)) * 100)
            audio_manager.set_volume(voice_vol, track="voice")
        except Exception:
            pass

    @property
    def settings_file(self) -> Path:
        return self._file


__all__ = ["SettingsManager", "DEFAULT_SETTINGS"]
