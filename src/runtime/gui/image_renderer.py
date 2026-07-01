"""ImageRenderer —— v3-04 真实现（背景图 + 角色立绘）。

职责：
- set_background(src) / clear_background() —— 背景图渲染
- set_character(name, src, pos) / remove_character(name) —— 角色立绘渲染
- 三位置：left / center / right（QLabel alignment）
- 图片路径解析：相对 chapters/ 目录（与 AudioManager 一致）
- QPixmap 选型（PyQt6 优先，lazy import）

设计（仿 TextRenderer / OptionsPanel 模式）：
- 不直接 import PyQt6（lazy import），便于测试注入 fake backend
- 接受 qt dict 注入（含 QLabel / QPixmap），测试隔离
- 无 PyQt6 / 图片不存在时降级为 no-op（不抛错，记日志）
- 所有 widget 调用 try/except 兜底（兼容 fake QLabel）

v3-04 简化：
- 淡入淡出暂不实现（v3+ 可接 QGraphicsOpacityEffect + QPropertyAnimation）
- 立绘位置用 QLabel.setAlignment 实现（v3-09 可改 QStackedLayout 叠层）
- 背景/角色 QLabel 加入 layout 顶部（v3-09 可改背景层叠）
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ImageRenderer:
    """v3-04 图片渲染器（背景 + 角色立绘）。

    用法：
        renderer = ImageRenderer(central, layout, qt=qt, chapters_root="chapters")
        renderer.set_background("forest.png")  # 设置背景
        renderer.set_character("alice", "alice.png", "left")  # 左侧立绘
        renderer.remove_character("alice")  # 移除 alice
        renderer.clear()  # 清空所有
    """

    def __init__(
        self,
        parent_widget,
        layout,
        qt: Optional[dict] = None,
        chapters_root: str = "chapters",
    ):
        """Args:
            parent_widget: 父 QWidget（QLabel 的 parent）
            layout: QVBoxLayout（背景/角色 label 插入顶部）
            qt: PyQt6 modules dict（测试注入 fake）。None 时 lazy import。
                需含 QLabel / QPixmap 键。
            chapters_root: 图片文件解析根目录
        """
        self._parent = parent_widget
        self._layout = layout
        self._qt = qt
        self._chapters_root = Path(chapters_root)

        # 背景 QLabel（lazy 创建）
        self._bg_label = None
        self._bg_source: Optional[str] = None

        # 角色立绘：name → {"label": QLabel, "src": str, "pos": str}
        self._characters: dict[str, dict] = {}

    # ─── 背景图 ───────────────────────────────────────────────────────────

    def set_background(self, source: str) -> bool:
        """设置背景图。

        Args:
            source: 图片路径（相对 chapters_root 或绝对路径）

        Returns:
            True —— 成功加载（或降级 no-op）
            False —— 文件不存在
        """
        path = self._resolve_path(source)
        if path is None:
            logger.warning("ImageRenderer.set_background: 图片不存在: %s", source)
            return False

        QPixmap = self._get_qpixmap()
        if QPixmap is None:
            # 降级 no-op（PyQt6 未装）
            self._bg_source = source
            logger.info("ImageRenderer.set_background: 降级 no-op: %s", source)
            return True

        try:
            pixmap = QPixmap(str(path))
            label = self._get_or_create_bg_label()
            if label is not None:
                label.setPixmap(pixmap)
                label.setScaledContents(True)
            self._bg_source = source
            return True
        except Exception as e:
            logger.warning("ImageRenderer.set_background 失败: %s", e)
            return False

    def clear_background(self) -> None:
        """清除背景图。"""
        if self._bg_label is not None:
            try:
                self._bg_label.clear()
            except Exception:
                pass
        self._bg_source = None

    def get_background(self) -> Optional[str]:
        """取当前背景图源（测试断言用）。"""
        return self._bg_source

    @property
    def has_background(self) -> bool:
        return self._bg_source is not None

    # ─── 角色立绘 ─────────────────────────────────────────────────────────

    _VALID_POS = ("left", "center", "right")

    def set_character(
        self, name: str, source: str, position: str = "center"
    ) -> bool:
        """显示角色立绘。

        Args:
            name: 角色名（唯一标识，同 name 再次调用 = 更换立绘）
            source: 图片路径（相对 chapters_root 或绝对路径）
            position: "left" / "center" / "right"（非法值回退 center）

        Returns:
            True —— 成功加载（或降级 no-op）
            False —— 文件不存在
        """
        if not name:
            return False

        # 位置归一化（与 @char 装饰器一致）
        if position not in self._VALID_POS:
            position = "center"

        # source 为空时只记录不加载（可能仅切换位置）
        path = self._resolve_path(source) if source else None
        if source and path is None:
            logger.warning("ImageRenderer.set_character: 图片不存在: %s", source)
            return False

        QPixmap = self._get_qpixmap()
        if QPixmap is None:
            # 降级 no-op
            self._characters[name] = {"label": None, "src": source, "pos": position}
            return True

        try:
            label = self._characters.get(name, {}).get("label")
            if label is None:
                QLabel = self._get_qlabel()
                if QLabel is None:
                    self._characters[name] = {"label": None, "src": source, "pos": position}
                    return True
                label = QLabel(self._parent)
                self._layout.addWidget(label)
                label.show()

            if path is not None:
                pixmap = QPixmap(str(path))
                label.setPixmap(pixmap)

            self._apply_position(label, position)
            self._characters[name] = {"label": label, "src": source, "pos": position}
            return True
        except Exception as e:
            logger.warning("ImageRenderer.set_character 失败: %s", e)
            self._characters[name] = {"label": None, "src": source, "pos": position}
            return True

    def remove_character(self, name: str) -> None:
        """移除角色立绘。"""
        entry = self._characters.pop(name, None)
        if entry is None:
            return
        label = entry.get("label")
        if label is not None:
            try:
                label.setParent(None)
            except Exception:
                pass
            try:
                label.deleteLater()
            except Exception:
                pass

    def get_characters(self) -> dict:
        """取当前角色列表（name → {src, pos}，测试断言用）。"""
        return {
            name: {"src": e.get("src", ""), "pos": e.get("pos", "")}
            for name, e in self._characters.items()
        }

    @property
    def character_count(self) -> int:
        return len(self._characters)

    # ─── 通用 ─────────────────────────────────────────────────────────────

    def clear(self) -> None:
        """清空所有图片（背景 + 角色）。"""
        self.clear_background()
        # 复制 keys 避免 dict 变动
        for name in list(self._characters.keys()):
            self.remove_character(name)

    # ─── 内部方法 ─────────────────────────────────────────────────────────

    def _resolve_path(self, source: str) -> Optional[Path]:
        """解析图片路径（与 AudioManager._resolve_path 一致）。"""
        p = Path(source)
        if p.is_absolute():
            return p if p.exists() else None
        resolved = self._chapters_root / source
        if resolved.exists():
            return resolved
        if p.exists():
            return p
        return None

    def _get_qlabel(self):
        """lazy 取 QLabel。"""
        if self._qt is not None:
            return self._qt.get("QLabel")
        try:
            from PyQt6.QtWidgets import QLabel
            return QLabel
        except ImportError:
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

    def _get_or_create_bg_label(self):
        """获取或创建背景 QLabel（lazy）。"""
        if self._bg_label is not None:
            return self._bg_label
        QLabel = self._get_qlabel()
        if QLabel is None:
            return None
        try:
            label = QLabel(self._parent)
            self._layout.addWidget(label)
            label.show()
            self._bg_label = label
            return label
        except Exception as e:
            logger.warning("ImageRenderer: 创建 bg_label 失败: %s", e)
            return None

    def _apply_position(self, label, position: str) -> None:
        """应用角色位置（QLabel alignment）。"""
        try:
            # Qt.AlignmentFlag: AlignLeft=0x0001, AlignCenter=0x0004, AlignRight=0x0002
            # 用 setAlignment 接受 int（兼容 fake）
            if position == "left":
                label.setAlignment(0x0001)
            elif position == "right":
                label.setAlignment(0x0002)
            else:
                label.setAlignment(0x0004)
        except Exception:
            pass


__all__ = ["ImageRenderer"]
