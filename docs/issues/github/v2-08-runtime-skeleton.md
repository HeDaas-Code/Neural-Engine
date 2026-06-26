## Parent

PDR：[`docs/pdr/phase3-v2p0.md`](../../pdr/phase3-v2p0.md) §5.1.1 + §5.3.1（runtime 子模块清单）
Issue 列表：[`docs/issues/phase3-v2p0.md`](../../issues/phase3-v2p0.md) V2-08
关联 EP：EP-07（`src/runtime/` 占位）

## What to build

补齐 `src/runtime/` 三个子模块的占位（`gui/` 已有；`save.py` V2-07 已建；新建 `audio.py` / `video.py` / `renderer.py` 占位 + `__init__.py` 导出）；与 `src/runtime/CONTEXT.md` 术语表对齐。

### 步骤

1. **`src/runtime/` 目录结构**（完工目标）：
   ```
   src/runtime/
   ├── __init__.py          (空文件已留 → 本 issue 改为导出子模块)
   ├── CONTEXT.md           (术语表已留)
   ├── gui/                 (V2-01 已建)
   │   ├── __init__.py
   │   ├── main.py
   │   ├── _cli_main.py
   │   └── pyqt6_main.py    (V2-01 新建)
   ├── save.py              (V2-07 新建)
   ├── audio.py             (本 issue 新建 · 占位)
   ├── video.py             (本 issue 新建 · 占位)
   └── renderer.py          (本 issue 新建 · 占位)
   ```

2. **`src/runtime/audio.py` 占位**（v3+ 落地）：
   ```python
   """音频管理器（BGM/SE/Voice）—— v3+ 落地。v2 仅占位。"""
   from __future__ import annotations

   class AudioManager:
       """订阅 DecoratorEvt(kind="call") 触发 BGM/SE 播放。

       v3+ 落地路径：
       - 监听 DecoratorEvt(name="bgm", kind="call") → play(bgm_path)
       - 监听 DecoratorEvt(name="bgm", kind="stop") → stop()
       """
       def play(self, bgm: str) -> None:
           raise NotImplementedError("v3+ 落地（EP-07）")
       def stop(self) -> None:
           raise NotImplementedError("v3+ 落地（EP-07）")
   ```

3. **`src/runtime/video.py` 占位**（v3+ 落地）：
   ```python
   """视频播放器 —— v3+ 落地。v2 仅占位。"""
   from __future__ import annotations

   class VideoPlayer:
       """视频播放器 —— v3+ 落地。"""
       def play(self, video: str) -> None:
           raise NotImplementedError("v3+ 落地（EP-07）")
   ```

4. **`src/runtime/renderer.py` 占位**（v3+ 落地）：
   ```python
   """文字/立绘/背景渲染器 —— v3+ 落地。v2 仅占位。"""
   from __future__ import annotations

   class TextRenderer:
       """文字渲染器 —— v3+ 落地。

       v2 钩子签名（V2-02 已落）：fn("text", "rgb:red") → apply_style
       """
       def set_style(self, key: str, val: str) -> None:
           raise NotImplementedError("v3+ 落地（EP-07）")
   ```

5. **`src/runtime/__init__.py` 改为导出子模块**（从空文件改）：
   ```python
   """Neural Engine runtime layer.

   v2 落地模块：save (V2-07) · gui (V2-01) · audio/video/renderer (V2-08 占位)
   v3+ 落地：audio/video/renderer 实际实现
   """
   from runtime.save import SaveManager
   from runtime.audio import AudioManager
   from runtime.video import VideoPlayer
   from runtime.renderer import TextRenderer

   __all__ = ["SaveManager", "AudioManager", "VideoPlayer", "TextRenderer"]
   ```

6. **`src/runtime/CONTEXT.md` 验证**：与 `src/runtime/__init__.py` 子模块清单对齐（5 个子模块：gui / save / audio / video / renderer）
   - 关键类型表：`SaveManager` v2 落地；`TextRenderer` / `AudioManager` / `VideoPlayer` v3+ 落地

7. **测试**：
   - `tests/runtime/test_runtime_skeleton.py::test_runtime_modules_importable` —— `from runtime.audio import AudioManager` 等可 import
   - `tests/runtime/test_runtime_skeleton.py::test_runtime_init_exports` —— `from runtime import SaveManager, AudioManager, VideoPlayer, TextRenderer` 全可 import
   - `tests/runtime/test_runtime_skeleton.py::test_v3_methods_raise_not_implemented` —— `AudioManager.play()` / `VideoPlayer.play()` / `TextRenderer.set_style()` 抛 `NotImplementedError`

8. **现有测试不破**：
   - `tests/runtime/test_gui_protocol.py` 不破
   - `tests/runtime/test_save_manager.py` 不破

## Acceptance criteria

- [ ] `src/runtime/audio.py` 新建（含 `AudioManager.play` / `stop` 占位）
- [ ] `src/runtime/video.py` 新建（含 `VideoPlayer.play` 占位）
- [ ] `src/runtime/renderer.py` 新建（含 `TextRenderer.set_style` 占位）
- [ ] `src/runtime/__init__.py` 改为导出 4 个类（`SaveManager` / `AudioManager` / `VideoPlayer` / `TextRenderer`）
- [ ] `tests/runtime/test_runtime_skeleton.py` 新建，至少 3 个测试
- [ ] `src/runtime/CONTEXT.md` 验证（与子模块清单对齐）
- [ ] 现有 `tests/runtime/test_gui_protocol.py` / `test_save_manager.py` 不破
- [ ] 现有 211+ tests 维持 + 3+ 新测试

## Blocked by

- V2-07（SaveManager，#78）—— `src/runtime/save.py` 必须先有，本 issue 才能验证 `SaveManager` 导出

## 关联依赖

- 阻塞 V2-09（文档同步+回归，依赖本 issue 的子模块清单）
