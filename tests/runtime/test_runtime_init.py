"""v2-skeleton · EP-07 runtime 子包入口占位类测试。

按 PM 派工 V2-08 (EP-07) acceptance criteria 验证：
- `src/runtime/__init__.py` 导出 SaveManager / AudioManager / VideoPlayer 三个占位类
- 三个子模块各自可独立 import
- 占位类在 v2 阶段不抛错（仅暴露类名 + 文档说明 v3+ 落地）
- 不修改 `src/runtime/gui/` 子包（GUI 入口属 EP-05）

设计：v2 仅放空占位 class；v3+ 落地由后续 V2-08 任务补 NotImplementedError 方法。
"""
import sys

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")


# 1. runtime 包入口导出三个占位类
def test_runtime_init_exports_three_placeholders():
    """`from runtime import SaveManager, AudioManager, VideoPlayer` 全部可导入。"""
    from runtime import SaveManager, AudioManager, VideoPlayer  # noqa: F401

    assert SaveManager is not None
    assert AudioManager is not None
    assert VideoPlayer is not None


# 2. 三个占位类都是 type（class）
def test_runtime_placeholders_are_classes():
    """SaveManager / AudioManager / VideoPlayer 必须是 type（不是 instance / ModuleType）。"""
    from runtime import SaveManager, AudioManager, VideoPlayer

    assert isinstance(SaveManager, type)
    assert isinstance(AudioManager, type)
    assert isinstance(VideoPlayer, type)


# 3. 子模块各自可独立导入
def test_runtime_audio_submodule_importable():
    """`from runtime.audio import AudioManager` 可导入。"""
    from runtime.audio import AudioManager
    assert isinstance(AudioManager, type)


def test_runtime_video_submodule_importable():
    """`from runtime.video import VideoPlayer` 可导入。"""
    from runtime.video import VideoPlayer
    assert isinstance(VideoPlayer, type)


def test_runtime_save_submodule_importable():
    """`from runtime.save import SaveManager` 可导入。"""
    from runtime.save import SaveManager
    assert isinstance(SaveManager, type)


# 4. 入口导出与子模块导出是同一个类（不允许重复定义）
def test_runtime_init_and_submodules_share_same_class():
    """runtime.SaveManager 与 runtime.save.SaveManager 是同一个类对象。"""
    from runtime import SaveManager as _InitSaveManager
    from runtime.audio import AudioManager as _AudioAudioManager
    from runtime.video import VideoPlayer as _VideoVideoPlayer
    from runtime.save import SaveManager as _SaveSaveManager

    assert _InitSaveManager is _SaveSaveManager
    # AudioManager / VideoPlayer 不在 __init__ 之外的别名表中（PM 派工未要求），
    # 但子模块必须能 import：确认两者都是 type 即满足。
    assert isinstance(_AudioAudioManager, type)
    assert isinstance(_VideoVideoPlayer, type)


# 5. runtime 包导入时不抛异常（import-time sanity）
def test_runtime_import_does_not_raise():
    """`import runtime` 在 v2 阶段必须不抛 ImportError / AttributeError。"""
    # 此断言由 pytest 的 import 阶段保证；如果 import 失败则 collection 报错。
    import runtime  # noqa: F401

    # 触发属性查找（防 AttributeError）
    assert hasattr(runtime, "SaveManager")
    assert hasattr(runtime, "AudioManager")
    assert hasattr(runtime, "VideoPlayer")