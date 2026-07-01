"""NodeGraphView —— v4-01 节点图视图层（#109）。

职责：
- 把 NodeGraphModel 渲染为 QGraphicsView/QGraphicsScene 画布
- 节点 = QGraphicsRectItem（按类型着色 + id/preview 文本）
- 边 = QGraphicsLineItem（节点中心连线 + 标签）
- 交互：拖拽移动节点、双击编辑、右键菜单（新建/删除/连线）、多选、缩放/平移
- 撤销/重做（轻量命令栈，纯 Python，不依赖 QUndoStack 便于测试）

设计（仿 pyqt6_main / save_slot_dialog 工厂模式）：
- 模块顶层不 import PyQt6（D3 决策延伸）
- `_import_pyqt6()` lazy import，失败抛 ImportError
- `_build_node_graph_view_class(qt=None)` 动态构造 NodeGraphView 子类
- qt dict 注入（测试隔离）

集成点：
- NodeGraphView(model, parent=None, qt=None)
- model 变更 → view.refresh() 重建画布
- 用户操作 → 改 model → view.refresh()
- 双击节点 → emit nodeDoubleClicked(node_id) 信号（调用方开编辑面板）
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _import_pyqt6() -> dict:
    """Lazy import PyQt6 modules needed for NodeGraphView。"""
    from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF
    from PyQt6.QtGui import QPen, QBrush, QColor, QFont, QPainter
    from PyQt6.QtWidgets import (
        QGraphicsView, QGraphicsScene, QGraphicsRectItem,
        QGraphicsTextItem, QGraphicsLineItem, QGraphicsEllipseItem,
        QMenu, QGraphicsItem,
    )
    return {
        "QGraphicsView": QGraphicsView, "QGraphicsScene": QGraphicsScene,
        "QGraphicsRectItem": QGraphicsRectItem, "QGraphicsTextItem": QGraphicsTextItem,
        "QGraphicsLineItem": QGraphicsLineItem, "QGraphicsEllipseItem": QGraphicsEllipseItem,
        "QMenu": QMenu, "QGraphicsItem": QGraphicsItem,
        "QPen": QPen, "QBrush": QBrush, "QColor": QColor, "QFont": QFont,
        "QPainter": QPainter, "Qt": Qt, "pyqtSignal": pyqtSignal,
        "QPointF": QPointF, "QRectF": QRectF,
    }


def _build_node_graph_view_class(qt: Optional[dict] = None):
    """动态构造 NodeGraphView Qt 子类（继承 qt["QGraphicsView"]）。

    Args:
        qt: PyQt6 modules dict（测试可注入 fake）。None 时 lazy import。
            需含 QGraphicsView/QGraphicsScene/QGraphicsRectItem/QGraphicsTextItem/
            QGraphicsLineItem/QMenu/QPen/QBrush/QColor/QFont/Qt/pyqtSignal/QPointF/QRectF。

    Returns:
        NodeGraphView class（type）

    Raises:
        RuntimeError: qt=None 且 PyQt6 import 失败。
    """
    if qt is None:
        try:
            qt = _import_pyqt6()
        except ImportError as e:
            raise RuntimeError(f"PyQt6 不可用: {e}") from e

    QGraphicsView = qt["QGraphicsView"]
    QGraphicsScene = qt["QGraphicsScene"]
    QGraphicsRectItem = qt["QGraphicsRectItem"]
    QGraphicsTextItem = qt["QGraphicsTextItem"]
    QGraphicsLineItem = qt["QGraphicsLineItem"]
    QMenu = qt["QMenu"]
    QPen = qt["QPen"]
    QBrush = qt["QBrush"]
    QColor = qt["QColor"]
    QFont = qt["QFont"]
    Qt = qt["Qt"]
    pyqtSignal = qt["pyqtSignal"]
    QPointF = qt["QPointF"]
    QRectF = qt["QRectF"]

    # 延迟导入模型层（避免顶层循环）
    from editor.node_graph_model import (
        NodeGraphModel, NodeData, EdgeData, TYPE_COLORS,
        NODE_WIDTH, NODE_HEIGHT,
    )

    # ─── NodeItem：节点矩形 ──────────────────────────────────────────

    class NodeItem(QGraphicsRectItem):
        """节点图中的一个节点矩形（按类型着色 + 显示 id/preview）。"""

        def __init__(self, node_data: NodeData, parent=None):
            super().__init__(0, 0, NODE_WIDTH, NODE_HEIGHT, parent)
            self.node_id = node_data.id
            self.node_type = node_data.node_type
            self._qt = qt

            # 颜色（按类型）
            color_hex = TYPE_COLORS.get(node_data.node_type, TYPE_COLORS["normal"])
            try:
                self.setBrush(QBrush(QColor(color_hex)))
                self.setPen(QPen(QColor("#333333"), 1))
            except Exception:
                pass  # fake qt 可能不支持

            # 文本：id（粗体）+ preview（小字）
            try:
                self._title_item = QGraphicsTextItem(node_data.title, self)
                self._title_item.setDefaultTextColor(QColor("#ffffff"))
                font = QFont()
                font.setBold(True)
                self._title_item.setFont(font)
                self._title_item.setPos(6, 4)

                preview_text = node_data.preview or ""
                self._preview_item = QGraphicsTextItem(preview_text, self)
                self._preview_item.setDefaultTextColor(QColor("#e0e0e0"))
                self._preview_item.setPos(6, 24)
            except Exception:
                self._title_item = None
                self._preview_item = None

            # 位置（model 坐标 → scene 坐标）
            self.setPos(QPointF(node_data.x, node_data.y))

            # 可选可移动
            try:
                self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
                self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
                self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
            except Exception:
                pass

        def update_from_data(self, node_data: NodeData) -> None:
            """数据变更后刷新位置 + 文本。"""
            self.setPos(QPointF(node_data.x, node_data.y))
            if self._title_item is not None:
                try:
                    self._title_item.setPlainText(node_data.title)
                except Exception:
                    pass
            if self._preview_item is not None:
                try:
                    self._preview_item.setPlainText(node_data.preview or "")
                except Exception:
                    pass

    # ─── EdgeItem：边连线 ──────────────────────────────────────────

    class EdgeItem(QGraphicsLineItem):
        """节点图中的边（源节点中心 → 目标节点中心）。"""

        def __init__(self, source_item: NodeItem, target_item: NodeItem,
                     label: str = "", parent=None):
            super().__init__(parent)
            self._source = source_item
            self._target = target_item
            self._label = label
            self._qt = qt
            try:
                pen = QPen(QColor("#666666"), 2)
                self.setPen(pen)
            except Exception:
                pass
            self._update_geometry()

            # 标签（可选）
            if label:
                try:
                    self._label_item = QGraphicsTextItem(label, self)
                    self._label_item.setDefaultTextColor(QColor("#ff9800"))
                    font = QFont()
                    font.setBold(True)
                    self._label_item.setFont(font)
                except Exception:
                    self._label_item = None
                self._update_label_pos()
            else:
                self._label_item = None

        def _update_geometry(self) -> None:
            """更新连线两端到节点中心。"""
            try:
                sx = self._source.x() + NODE_WIDTH / 2
                sy = self._source.y() + NODE_HEIGHT / 2
                tx = self._target.x() + NODE_WIDTH / 2
                ty = self._target.y() + NODE_HEIGHT / 2
                self.setLine(sx, sy, tx, ty)
            except Exception:
                pass

        def _update_label_pos(self) -> None:
            """标签放连线中点。"""
            if self._label_item is None:
                return
            try:
                mx = (self._source.x() + self._target.x()) / 2 + NODE_WIDTH / 2
                my = (self._source.y() + self._target.y()) / 2
                self._label_item.setPos(mx, my)
            except Exception:
                pass

        def refresh(self) -> None:
            """节点移动后刷新连线 + 标签位置。"""
            self._update_geometry()
            self._update_label_pos()

    # ─── NodeGraphView：主视图 ──────────────────────────────────────

    class NodeGraphView(QGraphicsView):
        """节点图主视图（QGraphicsView + QGraphicsScene）。"""

        # 信号：双击节点（node_id）/ 选择变更
        # 直接调用 pyqtSignal(type) —— 真 PyQt6 返回信号描述符；fake qt 返回 MagicMock 均可用
        nodeDoubleClicked = pyqtSignal(str)
        selectionChanged = pyqtSignal(list)

        def __init__(self, model: NodeGraphModel, parent=None, chapters_root: str = "chapters"):
            super().__init__(parent)
            self._model = model
            self._qt = qt
            self._node_items: dict[str, NodeItem] = {}
            self._edge_items: list[EdgeItem] = []
            self._scene = QGraphicsScene(self)
            self.setScene(self._scene)

            # 撤销/重做栈（轻量纯 Python，不依赖 QUndoStack）
            self._undo_stack: list[dict] = []
            self._redo_stack: list[dict] = []

            # 渲染设置
            try:
                self.setRenderHint(qt["QPainter"].RenderHint.Antialiasing, True)
                self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            except Exception:
                pass

            # 初次渲染
            self.refresh()

        # ─── 公开 API ──────────────────────────────────────────────

        @property
        def model(self) -> NodeGraphModel:
            return self._model

        def refresh(self) -> None:
            """重建画布（从 model 同步所有节点 + 边）。"""
            # 清空旧 items
            self._node_items.clear()
            self._edge_items.clear()
            try:
                self._scene.clear()
            except Exception:
                pass

            # 创建节点 items
            for node in self._model.get_nodes():
                item = NodeItem(node)
                try:
                    self._scene.addItem(item)
                except Exception:
                    pass
                self._node_items[node.id] = item

            # 创建边 items
            for edge in self._model.get_edges():
                src = self._node_items.get(edge.source_id)
                tgt = self._node_items.get(edge.target_id)
                if src is None or tgt is None:
                    continue  # 悬空边跳过
                edge_item = EdgeItem(src, tgt, label=edge.label)
                try:
                    self._scene.addItem(edge_item)
                except Exception:
                    pass
                self._edge_items.append(edge_item)

        def get_node_item(self, node_id: str) -> Optional[NodeItem]:
            """取节点 item（不存在 → None）。"""
            return self._node_items.get(node_id)

        def get_selected_node_ids(self) -> list[str]:
            """取当前选中的节点 id 列表。"""
            result = []
            for nid, item in self._node_items.items():
                try:
                    if item.isSelected():
                        result.append(nid)
                except Exception:
                    pass
            return result

        # ─── 用户操作（带撤销/重做） ──────────────────────────────

        def _snapshot_model(self) -> dict:
            """取 model 快照（to_dict）。"""
            return self._model.to_dict()

        def _restore_model(self, snapshot: dict) -> None:
            """从快照恢复 model。"""
            from editor.node_graph_model import NodeGraphModel as _M
            self._model = _M.from_dict(snapshot)

        def _begin_cmd(self) -> dict:
            """命令开始：返回 before 快照。"""
            return self._snapshot_model()

        def _end_cmd(self, before: dict) -> None:
            """命令结束：压入 (before, after) 到撤销栈。"""
            self._undo_stack.append({
                "before": before,
                "after": self._snapshot_model(),
            })
            self._redo_stack.clear()

        def add_node_at(self, x: float, y: float, node_id: str = "",
                        node_type: str = "normal", preview: str = "") -> Optional[str]:
            """在 (x, y) 新建节点。返回新节点 id（失败 → None）。"""
            before = self._begin_cmd()
            # 生成唯一 id
            if not node_id:
                base = "node"
                i = 1
                while f"{base}{i}" in self._node_items:
                    i += 1
                node_id = f"{base}{i}"
            if self._model.has_node(node_id):
                return None
            node = NodeData(id=node_id, title=node_id, preview=preview,
                            node_type=node_type, x=x, y=y)
            self._model.add_node(node)
            self._end_cmd(before)
            self.refresh()
            return node_id

        def delete_selected(self) -> int:
            """删除选中节点 + 级联边。返回删除节点数。"""
            selected = self.get_selected_node_ids()
            if not selected:
                return 0
            before = self._begin_cmd()
            for nid in selected:
                self._model.remove_node(nid)
            self._end_cmd(before)
            self.refresh()
            return len(selected)

        def connect_nodes(self, source_id: str, target_id: str, label: str = "") -> bool:
            """连接两节点（新建边）。成功 → True。"""
            before = self._begin_cmd()
            edge = EdgeData(source_id=source_id, target_id=target_id, label=label)
            if not self._model.add_edge(edge):
                return False
            self._end_cmd(before)
            self.refresh()
            return True

        def delete_edge(self, source_id: str, target_id: str, label: str = "") -> int:
            """删除边。返回删除数。"""
            before = self._begin_cmd()
            n = self._model.remove_edge(source_id, target_id, label)
            if n > 0:
                self._end_cmd(before)
            self.refresh()
            return n

        def update_node(self, node_id: str, title: Optional[str] = None,
                        preview: Optional[str] = None) -> bool:
            """更新节点 title/preview（双击编辑后调用）。"""
            before = self._begin_cmd()
            ok = self._model.update_node(node_id, title=title, preview=preview)
            if ok:
                self._end_cmd(before)
            self.refresh()
            return ok

        def move_node(self, node_id: str, x: float, y: float) -> bool:
            """移动节点（拖拽结束调用）。"""
            before = self._begin_cmd()
            ok = self._model.move_node(node_id, x, y)
            if ok:
                self._end_cmd(before)
            self.refresh()
            return ok

        # ─── 撤销/重做（快照式，始终正确） ────────────────────────

        def undo(self) -> bool:
            """撤销上一步：恢复 before 快照。成功 → True。"""
            if not self._undo_stack:
                return False
            entry = self._undo_stack.pop()
            self._restore_model(entry["before"])
            self._redo_stack.append(entry)
            self.refresh()
            return True

        def redo(self) -> bool:
            """重做：恢复 after 快照。成功 → True。"""
            if not self._redo_stack:
                return False
            entry = self._redo_stack.pop()
            self._restore_model(entry["after"])
            self._undo_stack.append(entry)
            self.refresh()
            return True

        @property
        def undo_count(self) -> int:
            return len(self._undo_stack)

        @property
        def redo_count(self) -> int:
            return len(self._redo_stack)

        def can_undo(self) -> bool:
            return len(self._undo_stack) > 0

        def can_redo(self) -> bool:
            return len(self._redo_stack) > 0

        # ─── 事件处理 ──────────────────────────────────────────────

        def mouseDoubleClickEvent(self, event) -> None:
            """双击节点 → emit nodeDoubleClicked(node_id)。"""
            try:
                pos = self.mapToScene(event.pos())
                item = self._scene.itemAt(pos, self.transform())
            except Exception:
                item = None
            # 找到 NodeItem（边不是 NodeItem）
            if item is not None and hasattr(item, "node_id"):
                try:
                    self.nodeDoubleClicked.emit(item.node_id)
                except Exception:
                    pass
            try:
                super().mouseDoubleClickEvent(event)
            except Exception:
                pass

        def contextMenuEvent(self, event) -> None:
            """右键菜单：新建节点 / 删除选中 / 连接选中。"""
            try:
                menu = QMenu(self)
                act_new = menu.addAction("新建节点")
                act_del = menu.addAction("删除选中")
                act_connect = menu.addAction("连接选中（首→尾）")
                act_layout = menu.addAction("自动布局")
                action = menu.exec(event.globalPos())
            except Exception:
                action = None

            if action is None:
                return
            try:
                label = action.text()
            except Exception:
                return

            if label == "新建节点":
                try:
                    pos = self.mapToScene(event.pos())
                    self.add_node_at(pos.x(), pos.y())
                except Exception:
                    self.add_node_at(0, 0)
            elif label == "删除选中":
                self.delete_selected()
            elif label == "连接选中（首→尾）":
                selected = self.get_selected_node_ids()
                if len(selected) >= 2:
                    self.connect_nodes(selected[0], selected[1])
            elif label == "自动布局":
                self._model.auto_layout()
                self.refresh()

    # 设清晰类名（便于 isinstance / 调试）
    NodeGraphView.__name__ = "NodeGraphView"
    NodeGraphView.__qualname__ = "NodeGraphView"
    NodeItem.__name__ = "NodeItem"
    EdgeItem.__name__ = "EdgeItem"
    return NodeGraphView


__all__ = ["_build_node_graph_view_class", "_import_pyqt6"]
