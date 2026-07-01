"""ScreenshotManager —— v3-05 截图捕获（QWidget → PNG bytes）。

职责：
- `capture(widget) -> bytes | None` —— QWidget.grab() → QPixmap → PNG bytes
- `capture_to_path(widget, path) -> bool` —— 捕获并直接写文件
- PyQt6 lazy import + qt dict 注入（测试隔离）
- 无 PyQt6 / 捕获失败 → 降级返回 None（不抛错）

设计（仿 ImageRenderer / TextRenderer 模式）：
- 不直接 import PyQt6（lazy import），便于测试注入 fake backend
- 接受 qt dict 注入（含 QPixmap / QBuffer / QImage），测试隔离
- 所有 Qt 调用 try/except 兜底（兼容 fake QPixmap）

v3-05 简化：
- 截图尺寸 = widget 原始 size（不缩放，SaveSlotDialog 显示时再缩）
- 格式固定 PNG（无损 + 通用）
- 不支持区域截图（v3+ 可加 rect 参数）
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ScreenshotManager:
    """v3-05 截图管理器（QWidget → PNG bytes）。

    用法：
        mgr = ScreenshotManager(qt=qt)
        png_bytes = mgr.capture(main_window)  # 捕获主窗口
        mgr.capture_to_path(main_window, "slot01.png")  # 直接写文件
        # 也可保存到 SaveManager：
        save_mgr.save("01", state, screenshot=mgr.capture(widget))
    """

    def __init__(self, qt: Optional[dict] = None):
        """Args:
            qt: PyQt6 modules dict（测试注入 fake）。None 时 lazy import。
                需含 QPixmap 键（QBuffer / QByteArray 内部 lazy 取）。
        """
        self._qt = qt

    def capture(self, widget) -> Optional[bytes]:
        """捕获 widget 为 PNG bytes。

        Args:
            widget: 任意 QWidget（需有 grab() 方法返回 QPixmap）

        Returns:
            PNG bytes —— 成功；None —— 失败（PyQt6 未装 / grab 失败 / 编码失败）。
        """
        if widget is None:
            return None

        QPixmap = self._get_qpixmap()
        if QPixmap is None:
            logger.info("ScreenshotManager.capture: 降级 None（PyQt6 未装）")
            return None

        try:
            # QWidget.grab() 返回 QPixmap
            pixmap = widget.grab()
            if pixmap is None:
                return None
            return self._pixmap_to_png(pixmap)
        except Exception as e:
            logger.warning("ScreenshotManager.capture 失败: %s", e)
            return None

    def capture_to_path(self, widget, path: str | Path) -> bool:
        """捕获 widget 并直接写 PNG 文件。

        Args:
            widget: 任意 QWidget
            path: 输出 PNG 文件路径

        Returns:
            True —— 成功；False —— 失败。
        """
        data = self.capture(widget)
        if data is None:
            return False
        try:
            Path(path).write_bytes(data)
            return True
        except OSError as e:
            logger.warning("ScreenshotManager.capture_to_path 写文件失败: %s", e)
            return False

    # ─── 内部方法 ─────────────────────────────────────────────────────────

    def _pixmap_to_png(self, pixmap) -> Optional[bytes]:
        """QPixmap → PNG bytes（用 QBuffer + QImage.save）。

        fake QPixmap 可能没实现 save，try/except 兜底。
        """
        # 优先用 QPixmap.save(QBuffer, "PNG") —— 真 PyQt6 路径
        try:
            QBuffer = self._get_qbuffer()
            QByteArray = self._get_qbytearray()
            if QBuffer is not None and QByteArray is not None:
                # 真 PyQt6: QByteArray + QBuffer
                byte_array = QByteArray()
                buffer = QBuffer(byte_array)
                buffer.open(QBuffer.OpenModeFlag.WriteOnly)
                pixmap.save(buffer, "PNG")
                buffer.close()
                return bytes(byte_array)
        except Exception as e:
            logger.debug("QBuffer 路径失败，尝试 QImage: %s", e)

        # 备用：QImage.save 到 BytesIO（fake 友好）
        try:
            QImage = self._get_qimage()
            if QImage is not None:
                # 转 QImage 再 save
                image = pixmap.toImage() if hasattr(pixmap, "toImage") else pixmap
                # fake QImage 可能直接返回 bytes（测试简化）
                if isinstance(image, (bytes, bytearray)):
                    return bytes(image)
        except Exception as e:
            logger.debug("QImage 路径失败: %s", e)

        return None

    def _get_qpixmap(self):
        """lazy 取 QPixmap。"""
        if self._qt is not None:
            return self._qt.get("QPixmap")
        try:
            from PyQt6.QtGui import QPixmap
            return QPixmap
        except ImportError:
            return None

    def _get_qimage(self):
        """lazy 取 QImage。"""
        if self._qt is not None:
            return self._qt.get("QImage")
        try:
            from PyQt6.QtGui import QImage
            return QImage
        except ImportError:
            return None

    def _get_qbuffer(self):
        """lazy 取 QBuffer（QtCore）。"""
        if self._qt is not None:
            return self._qt.get("QBuffer")
        try:
            from PyQt6.QtCore import QBuffer
            return QBuffer
        except ImportError:
            return None

    def _get_qbytearray(self):
        """lazy 取 QByteArray（QtCore）。"""
        if self._qt is not None:
            return self._qt.get("QByteArray")
        try:
            from PyQt6.QtCore import QByteArray
            return QByteArray
        except ImportError:
            return None


__all__ = ["ScreenshotManager"]
