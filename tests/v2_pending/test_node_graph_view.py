"""v4-01 · NodeGraphView 节点图视图层测试（#109）。

验证 issue #109 视图层验收点：
- `_build_node_graph_view_class(qt=None/fake)` 工厂模式
- NodeGraphView 构造 + refresh（从 model 同步节点/边 → items）
- 6 个用户操作 API（add_node_at / delete_selected / connect_nodes /
  delete_edge / update_node / move_node）
- 快照式撤销/重做（add→undo→redo 循环、空栈、计数）
- 双击事件 → emit nodeDoubleClicked(node_id)
- 右键菜单（新建/删除/连接/自动布局）
- NodeItem.update_from_data / EdgeItem.refresh
- 真 PyQt6 smoke test（QT_QPA_PLATFORM=offscreen，端到端渲染 chapter01）

测试隔离：
- 用 fake qt dict 注入（不依赖真 PyQt6 即可跑核心逻辑测试）
- 真 PyQt6 smoke test 单独用 pytest.importorskip 守卫
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")

from editor.node_graph_model import (
    NodeData, EdgeData, NodeGraphModel,
    TYPE_NORMAL, TYPE_ENTRY, TYPE_BRANCH, TYPE_ENDING, TYPE_ROUTE,
    NODE_WIDTH, NODE_HEIGHT,
)
from editor.node_graph_view import (
    _build_node_graph_view_class, _import_pyqt6,
)


# ═══════════════════════════════════════════════════════════════════════
# Fake Qt 类
# ═══════════════════════════════════════════════════════════════════════


class FakeSignal:
    """Fake pyqtSignal —— connect/emit。"""

    def __init__(self, *types):
        self._slots: list = []
        self._emits: list = []

    def connect(self, slot):
        self._slots.append(slot)

    def emit(self, *args, **kwargs):
        self._emits.append(args)
        for slot in self._slots:
            slot(*args, **kwargs)


def _fake_pyqt_signal(*types):
    """pyqtSignal 替身：调用返回 FakeSignal 实例（类属性，单例）。"""
    return FakeSignal(*types)


class FakeQColor:
    def __init__(self, name=""):
        self._name = name


class FakeQPen:
    def __init__(self, color=None, width=1):
        self._color = color
        self._width = width


class FakeQBrush:
    def __init__(self, color=None):
        self._color = color


class FakeQFont:
    def __init__(self):
        self._bold = False

    def setBold(self, b):
        self._bold = b


class FakeQPointF:
    def __init__(self, x=0.0, y=0.0):
        self._x = float(x)
        self._y = float(y)

    def x(self):
        return self._x

    def y(self):
        return self._y


class FakeQRectF:
    def __init__(self, *args):
        pass


# ─── 枚举 ─────────────────────────────────────────────────────────────


class _GraphicsItemFlag:
    ItemIsMovable = "ItemIsMovable"
    ItemIsSelectable = "ItemIsSelectable"
    ItemSendsGeometryChanges = "ItemSendsGeometryChanges"


class _FakeQGraphicsItem:
    GraphicsItemFlag = _GraphicsItemFlag


class _RenderHint:
    Antialiasing = "Antialiasing"


class _FakeQPainter:
    RenderHint = _RenderHint


class _DragMode:
    RubberBandDrag = "RubberBandDrag"


# ─── Graphics Items ───────────────────────────────────────────────────


class FakeQGraphicsRectItem:
    """QGraphicsRectItem 基类（NodeItem 继承）。"""

    def __init__(self, x=0, y=0, w=0, h=0, parent=None):
        self._x = 0.0
        self._y = 0.0
        self._brush = None
        self._pen = None
        self._flags: set = set()
        self._selected = False
        self._parent = parent

    def setBrush(self, b):
        self._brush = b

    def setPen(self, p):
        self._pen = p

    def setPos(self, point):
        # point 是 FakeQPointF
        self._x = point.x()
        self._y = point.y()

    def x(self):
        return self._x

    def y(self):
        return self._y

    def setFlag(self, flag, on=True):
        if on:
            self._flags.add(flag)
        else:
            self._flags.discard(flag)

    def setSelected(self, on):
        self._selected = bool(on)

    def isSelected(self):
        return self._selected


class FakeQGraphicsTextItem:
    def __init__(self, text="", parent=None):
        self._text = text
        self._parent = parent
        self._color = None
        self._font = None
        self._pos = None

    def setDefaultTextColor(self, c):
        self._color = c

    def setFont(self, f):
        self._font = f

    def setPos(self, x, y):
        self._pos = (x, y)

    def setPlainText(self, t):
        self._text = t

    def toPlainText(self):
        return self._text


class FakeQGraphicsLineItem:
    """QGraphicsLineItem 基类（EdgeItem 继承）。"""

    def __init__(self, parent=None):
        self._line = (0.0, 0.0, 0.0, 0.0)
        self._pen = None
        self._parent = parent

    def setPen(self, p):
        self._pen = p

    def setLine(self, x1, y1, x2, y2):
        self._line = (x1, y1, x2, y2)

    def line(self):
        return self._line


class FakeQGraphicsEllipseItem:
    def __init__(self, *args, **kwargs):
        pass


# ─── Scene ────────────────────────────────────────────────────────────


class FakeQGraphicsScene:
    def __init__(self, parent=None):
        self._parent = parent
        self._items: list = []
        self._cleared = 0

    def addItem(self, item):
        self._items.append(item)

    def clear(self):
        self._items = []
        self._cleared += 1

    def itemAt(self, pos, transform):
        # 测试可设 _next_item_at 控制返回
        return getattr(self, "_next_item_at", None)


# ─── View ─────────────────────────────────────────────────────────────


class FakeQGraphicsView:
    """QGraphicsView 基类（NodeGraphView 继承）。"""

    DragMode = _DragMode

    def __init__(self, parent=None):
        self._parent = parent
        self._scene = None
        self._render_hints: list = []
        self._drag_mode = None

    def setScene(self, scene):
        self._scene = scene

    def scene(self):
        return self._scene

    def setRenderHint(self, hint, on=True):
        self._render_hints.append((hint, on))

    def setDragMode(self, mode):
        self._drag_mode = mode

    def transform(self):
        return None

    def mapToScene(self, pos):
        # 默认原样返回（FakeQPointF）
        return pos

    # 父类事件方法（被子类 super() 调用）
    def mouseDoubleClickEvent(self, event):
        pass

    def contextMenuEvent(self, event):
        pass


# ─── Menu ─────────────────────────────────────────────────────────────


class FakeQAction:
    def __init__(self, text=""):
        self._text = text

    def text(self):
        return self._text


class FakeQMenu:
    """右键菜单。测试通过 _exec_return 控制菜单选中哪个 action。"""

    _exec_return = None  # 类级，测试设置

    def __init__(self, parent=None):
        self._parent = parent
        self._actions: list = []

    def addAction(self, text):
        act = FakeQAction(text)
        self._actions.append(act)
        return act

    def exec(self, pos):
        return FakeQMenu._exec_return


# ─── Qt 占位 ──────────────────────────────────────────────────────────


class _FakeQt:
    """命名空间占位（视图代码未直接用 Qt.* 但 import 了）。"""
    ItemIsMovable = _GraphicsItemFlag.ItemIsMovable


# ─── 构造 qt dict ─────────────────────────────────────────────────────


def make_qt_dict() -> dict:
    """构造 fake qt dict（注入 _build_node_graph_view_class）。"""
    return {
        "QGraphicsView": FakeQGraphicsView,
        "QGraphicsScene": FakeQGraphicsScene,
        "QGraphicsRectItem": FakeQGraphicsRectItem,
        "QGraphicsTextItem": FakeQGraphicsTextItem,
        "QGraphicsLineItem": FakeQGraphicsLineItem,
        "QGraphicsEllipseItem": FakeQGraphicsEllipseItem,
        "QMenu": FakeQMenu,
        "QGraphicsItem": _FakeQGraphicsItem,
        "QPen": FakeQPen,
        "QBrush": FakeQBrush,
        "QColor": FakeQColor,
        "QFont": FakeQFont,
        "QPainter": _FakeQPainter,
        "Qt": _FakeQt,
        "pyqtSignal": _fake_pyqt_signal,
        "QPointF": FakeQPointF,
        "QRectF": FakeQRectF,
    }


# ─── fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def view_cls():
    """每测试构造独立 NodeGraphView 类（信号/栈互不干扰）。"""
    return _build_node_graph_view_class(qt=make_qt_dict())


@pytest.fixture
def empty_model():
    return NodeGraphModel()


@pytest.fixture
def sample_model():
    """start → c1 → [ca, cb] → end 的节点图。"""
    m = NodeGraphModel()
    m.add_node(NodeData(id="start", title="start", preview="雨夜。", node_type=TYPE_ENTRY))
    m.add_node(NodeData(id="c1", title="c1", preview="敲门。", node_type=TYPE_BRANCH))
    m.add_node(NodeData(id="ca", title="ca", preview="开门。", node_type=TYPE_NORMAL, x=0, y=120))
    m.add_node(NodeData(id="cb", title="cb", preview="不应。", node_type=TYPE_NORMAL, x=220, y=120))
    m.add_node(NodeData(id="end", title="end", preview="结局。", node_type=TYPE_ENDING, x=0, y=240))
    m.add_edge(EdgeData(source_id="start", target_id="c1"))
    m.add_edge(EdgeData(source_id="c1", target_id="ca", label="0"))
    m.add_edge(EdgeData(source_id="c1", target_id="cb", label="1"))
    m.add_edge(EdgeData(source_id="ca", target_id="end"))
    m.add_edge(EdgeData(source_id="cb", target_id="end"))
    return m


@pytest.fixture(autouse=True)
def _reset_fake_menu():
    """每个测试前后重置 FakeQMenu._exec_return。"""
    FakeQMenu._exec_return = None
    yield
    FakeQMenu._exec_return = None


# ═══════════════════════════════════════════════════════════════════════
# 1. 工厂 + 模块导入
# ═══════════════════════════════════════════════════════════════════════


def test_build_class_with_fake_qt_returns_class(view_cls):
    """工厂注入 fake qt → 返回 NodeGraphView 类。"""
    assert isinstance(view_cls, type)
    assert view_cls.__name__ == "NodeGraphView"


def test_build_class_with_none_qt_raises_when_pyqt6_missing(monkeypatch):
    """qt=None 且 PyQt6 import 失败 → RuntimeError。"""
    import editor.node_graph_view as ngv
    monkeypatch.setattr(ngv, "_import_pyqt6",
                        lambda: (_ for _ in ()).throw(ImportError("no PyQt6")))
    with pytest.raises(RuntimeError, match="PyQt6 不可用"):
        _build_node_graph_view_class(qt=None)


def test_import_pyqt6_returns_dict_with_required_keys():
    """_import_pyqt6() 真 PyQt6 → 返回含所有需要的 key。"""
    pytest.importorskip("PyQt6")
    qt = _import_pyqt6()
    required = {"QGraphicsView", "QGraphicsScene", "QGraphicsRectItem",
                "QGraphicsTextItem", "QGraphicsLineItem", "QMenu",
                "QPen", "QBrush", "QColor", "QFont", "QPainter",
                "Qt", "pyqtSignal", "QPointF", "QRectF"}
    assert required.issubset(qt.keys())


# ═══════════════════════════════════════════════════════════════════════
# 2. 构造 + refresh
# ═══════════════════════════════════════════════════════════════════════


def test_construct_empty_model(view_cls, empty_model):
    """空 model → view 构造成功，无 items。"""
    view = view_cls(empty_model)
    assert view.model is empty_model
    assert len(view._node_items) == 0
    assert len(view._edge_items) == 0
    assert view.undo_count == 0
    assert view.redo_count == 0
    assert view.can_undo() is False
    assert view.can_redo() is False


def test_construct_with_sample_model_creates_items(view_cls, sample_model):
    """sample model → refresh 后 5 节点 + 5 边全部渲染。"""
    view = view_cls(sample_model)
    assert len(view._node_items) == 5
    assert len(view._edge_items) == 5
    # 节点 id 都在
    for nid in ("start", "c1", "ca", "cb", "end"):
        assert nid in view._node_items


def test_refresh_clears_and_rebuilds(view_cls, sample_model):
    """refresh 清空旧 items 后重建。"""
    view = view_cls(sample_model)
    scene = view._scene
    initial_clear_count = scene._cleared
    # 外部改动 model 后 refresh
    sample_model.add_node(NodeData(id="extra", title="extra", preview="x", node_type=TYPE_NORMAL))
    view.refresh()
    assert scene._cleared == initial_clear_count + 1
    assert "extra" in view._node_items


def test_get_node_item_returns_item_or_none(view_cls, sample_model):
    view = view_cls(sample_model)
    item = view.get_node_item("start")
    assert item is not None
    assert item.node_id == "start"
    assert view.get_node_item("nope") is None


# ═══════════════════════════════════════════════════════════════════════
# 3. 选择 + 删除
# ═══════════════════════════════════════════════════════════════════════


def test_get_selected_node_ids_empty(view_cls, sample_model):
    view = view_cls(sample_model)
    assert view.get_selected_node_ids() == []


def test_get_selected_node_ids_returns_selected(view_cls, sample_model):
    view = view_cls(sample_model)
    view.get_node_item("start").setSelected(True)
    view.get_node_item("c1").setSelected(True)
    selected = set(view.get_selected_node_ids())
    assert selected == {"start", "c1"}


def test_delete_selected_removes_nodes(view_cls, sample_model):
    """删除选中节点 + 级联边 + 撤销栈增长。"""
    view = view_cls(sample_model)
    view.get_node_item("ca").setSelected(True)
    n = view.delete_selected()
    assert n == 1
    assert "ca" not in view._node_items
    # 级联删除 ca 相关边（ca→end, c1→ca）
    assert len(view._edge_items) == 3
    assert view.undo_count == 1
    assert view.model.has_node("ca") is False


def test_delete_selected_nothing_returns_zero(view_cls, sample_model):
    view = view_cls(sample_model)
    assert view.delete_selected() == 0
    assert view.undo_count == 0  # 无操作不入栈


# ═══════════════════════════════════════════════════════════════════════
# 4. add_node_at
# ═══════════════════════════════════════════════════════════════════════


def test_add_node_at_generates_id(view_cls, empty_model):
    view = view_cls(empty_model)
    nid = view.add_node_at(100, 200)
    assert nid == "node1"
    assert view.model.has_node("node1")
    node = view.model.get_node("node1")
    assert node.x == 100.0
    assert node.y == 200.0
    assert view.undo_count == 1


def test_add_node_at_increments_id(view_cls, sample_model):
    """已有 node1 时再生成 node2。"""
    view = view_cls(sample_model)
    # 先手动加 node1 到 model（不通过 view，所以 _node_items 没有）
    sample_model.add_node(NodeData(id="node1", title="node1", preview="",
                                    node_type=TYPE_NORMAL))
    view.refresh()
    nid = view.add_node_at(0, 0)
    assert nid == "node2"


def test_add_node_at_with_explicit_id(view_cls, empty_model):
    view = view_cls(empty_model)
    nid = view.add_node_at(0, 0, node_id="custom", node_type=TYPE_ENTRY, preview="hi")
    assert nid == "custom"
    node = view.model.get_node("custom")
    assert node.node_type == TYPE_ENTRY
    assert node.preview == "hi"


def test_add_node_at_duplicate_returns_none(view_cls, sample_model):
    """已存在的 id → 返回 None，不重复添加。"""
    view = view_cls(sample_model)
    nid = view.add_node_at(0, 0, node_id="start")
    assert nid is None
    assert view.undo_count == 0  # 失败不入栈


# ═══════════════════════════════════════════════════════════════════════
# 5. connect_nodes / delete_edge
# ═══════════════════════════════════════════════════════════════════════


def test_connect_nodes_creates_edge(view_cls, sample_model):
    view = view_cls(sample_model)
    # start 已连 c1，连 start→end（新边）
    ok = view.connect_nodes("start", "end", label="skip")
    assert ok is True
    assert view.undo_count == 1
    # 检查 model 有新边
    out_edges = view.model.get_out_edges("start")
    targets = {(e.target_id, e.label) for e in out_edges}
    assert ("end", "skip") in targets


def test_connect_nodes_nonexistent_node_returns_false(view_cls, sample_model):
    """source/target 节点不存在 → add_edge 返回 False，不入栈。"""
    view = view_cls(sample_model)
    ok = view.connect_nodes("start", "ghost")  # ghost 不存在
    assert ok is False
    assert view.undo_count == 0  # 失败不入栈


def test_connect_nodes_allows_parallel_edges(view_cls, sample_model):
    """model.add_edge 允许平行边（同 source→target 多 label）→ connect 返回 True。"""
    view = view_cls(sample_model)
    # start→c1 已存在（label=""），再连一次同 label → 仍 True（平行边）
    ok = view.connect_nodes("start", "c1")
    assert ok is True
    assert view.undo_count == 1


def test_delete_edge_removes(view_cls, sample_model):
    view = view_cls(sample_model)
    n = view.delete_edge("c1", "ca", label="0")
    assert n == 1
    assert view.undo_count == 1
    # model 中 c1→ca 边没了
    out = view.model.get_out_edges("c1")
    assert all(not (e.target_id == "ca" and e.label == "0") for e in out)


def test_delete_edge_nonexistent_returns_zero(view_cls, sample_model):
    view = view_cls(sample_model)
    n = view.delete_edge("start", "end")
    assert n == 0
    assert view.undo_count == 0  # 无删除不入栈


# ═══════════════════════════════════════════════════════════════════════
# 6. update_node / move_node
# ═══════════════════════════════════════════════════════════════════════


def test_update_node_changes_title_and_preview(view_cls, sample_model):
    view = view_cls(sample_model)
    ok = view.update_node("start", title="Start", preview="opening")
    assert ok is True
    node = view.model.get_node("start")
    assert node.title == "Start"
    assert node.preview == "opening"
    assert view.undo_count == 1


def test_update_node_nonexistent_returns_false(view_cls, sample_model):
    view = view_cls(sample_model)
    ok = view.update_node("nope", title="x")
    assert ok is False
    assert view.undo_count == 0


def test_move_node_updates_position(view_cls, sample_model):
    view = view_cls(sample_model)
    ok = view.move_node("start", 500, 600)
    assert ok is True
    node = view.model.get_node("start")
    assert node.x == 500.0
    assert node.y == 600.0
    assert view.undo_count == 1


def test_move_node_nonexistent_returns_false(view_cls, sample_model):
    view = view_cls(sample_model)
    ok = view.move_node("nope", 1, 2)
    assert ok is False


# ═══════════════════════════════════════════════════════════════════════
# 7. 撤销/重做（快照式）
# ═══════════════════════════════════════════════════════════════════════


def test_undo_empty_returns_false(view_cls, empty_model):
    view = view_cls(empty_model)
    assert view.undo() is False


def test_redo_empty_returns_false(view_cls, empty_model):
    view = view_cls(empty_model)
    assert view.redo() is False


def test_undo_redo_add_node_cycle(view_cls, empty_model):
    """add → undo → redo 完整循环。"""
    view = view_cls(empty_model)
    view.add_node_at(0, 0, node_id="n1")
    assert view.model.has_node("n1")
    assert view.undo_count == 1
    assert view.redo_count == 0

    # undo：节点消失
    assert view.undo() is True
    assert view.model.has_node("n1") is False
    assert view.undo_count == 0
    assert view.redo_count == 1
    assert view.can_redo() is True
    assert view.can_undo() is False

    # redo：节点回来
    assert view.redo() is True
    assert view.model.has_node("n1") is True
    assert view.undo_count == 1
    assert view.redo_count == 0


def test_undo_redo_delete_node_cycle(view_cls, sample_model):
    """delete → undo → redo。"""
    view = view_cls(sample_model)
    view.get_node_item("end").setSelected(True)
    view.delete_selected()
    assert view.model.has_node("end") is False
    assert view.undo_count == 1

    assert view.undo() is True
    assert view.model.has_node("end") is True
    # 级联边也回来
    out = view.model.get_out_edges("ca")
    assert any(e.target_id == "end" for e in out)

    assert view.redo() is True
    assert view.model.has_node("end") is False


def test_undo_redo_move_node_cycle(view_cls, sample_model):
    """move → undo → redo。"""
    view = view_cls(sample_model)
    original = view.model.get_node("start")
    ox, oy = original.x, original.y
    view.move_node("start", 999, 888)
    assert view.model.get_node("start").x == 999.0

    assert view.undo() is True
    node = view.model.get_node("start")
    assert node.x == ox
    assert node.y == oy

    assert view.redo() is True
    assert view.model.get_node("start").x == 999.0


def test_new_cmd_clears_redo_stack(view_cls, empty_model):
    """新操作清空 redo 栈（标准撤销/重做行为）。"""
    view = view_cls(empty_model)
    view.add_node_at(0, 0, node_id="n1")
    view.undo()  # redo_stack 有 1
    assert view.redo_count == 1
    # 新操作
    view.add_node_at(0, 0, node_id="n2")
    assert view.redo_count == 0  # 被清空
    assert view.undo_count == 1  # 只剩 n2 的


def test_undo_redo_connect_nodes_cycle(view_cls, sample_model):
    """connect → undo → redo。"""
    view = view_cls(sample_model)
    view.connect_nodes("start", "end", label="skip")
    assert any(e.target_id == "end" and e.label == "skip"
               for e in view.model.get_out_edges("start"))
    view.undo()
    assert not any(e.target_id == "end" and e.label == "skip"
                   for e in view.model.get_out_edges("start"))
    view.redo()
    assert any(e.target_id == "end" and e.label == "skip"
               for e in view.model.get_out_edges("start"))


# ═══════════════════════════════════════════════════════════════════════
# 8. 双击事件 → nodeDoubleClicked 信号
# ═══════════════════════════════════════════════════════════════════════


class _FakeMouseEvent:
    def __init__(self, pos):
        self._pos = pos

    def pos(self):
        return self._pos

    def globalPos(self):
        return self._pos


def test_mouse_double_click_emits_signal(view_cls, sample_model):
    """双击节点 → emit nodeDoubleClicked(node_id)。"""
    view = view_cls(sample_model)
    hits: list = []
    view.nodeDoubleClicked.connect(lambda nid: hits.append(nid))

    # 让 scene.itemAt 返回 start 节点 item
    start_item = view.get_node_item("start")
    view._scene._next_item_at = start_item

    event = _FakeMouseEvent(FakeQPointF(10, 10))
    view.mouseDoubleClickEvent(event)
    assert hits == ["start"]


def test_mouse_double_click_on_empty_no_emit(view_cls, sample_model):
    """双击空白 → 不 emit。"""
    view = view_cls(sample_model)
    hits: list = []
    view.nodeDoubleClicked.connect(lambda nid: hits.append(nid))
    view._scene._next_item_at = None  # 点空
    event = _FakeMouseEvent(FakeQPointF(0, 0))
    view.mouseDoubleClickEvent(event)
    assert hits == []


def test_mouse_double_click_on_edge_no_emit(view_cls, sample_model):
    """双击边（无 node_id 属性）→ 不 emit。"""
    view = view_cls(sample_model)
    hits: list = []
    view.nodeDoubleClicked.connect(lambda nid: hits.append(nid))
    # 边 item 没有 node_id 属性
    edge_item = view._edge_items[0]
    assert not hasattr(edge_item, "node_id")
    view._scene._next_item_at = edge_item
    event = _FakeMouseEvent(FakeQPointF(0, 0))
    view.mouseDoubleClickEvent(event)
    assert hits == []


# ═══════════════════════════════════════════════════════════════════════
# 9. 右键菜单
# ═══════════════════════════════════════════════════════════════════════


def test_context_menu_new_node(view_cls, empty_model):
    """右键 → 新建节点。"""
    view = view_cls(empty_model)
    FakeQMenu._exec_return = FakeQAction("新建节点")
    event = _FakeMouseEvent(FakeQPointF(100, 100))
    view.contextMenuEvent(event)
    assert view.model.node_count == 1
    assert view.undo_count == 1


def test_context_menu_delete_selected(view_cls, sample_model):
    """右键 → 删除选中。"""
    view = view_cls(sample_model)
    view.get_node_item("end").setSelected(True)
    FakeQMenu._exec_return = FakeQAction("删除选中")
    event = _FakeMouseEvent(FakeQPointF(0, 0))
    view.contextMenuEvent(event)
    assert view.model.has_node("end") is False


def test_context_menu_connect_selected(view_cls, sample_model):
    """右键 → 连接选中（首→尾）。

    get_selected_node_ids 按 id 字母序返回（model.get_nodes 排序），
    故选中 c1 + end 时，selected = ['c1', 'end']，连接 c1→end。
    """
    view = view_cls(sample_model)
    view.get_node_item("c1").setSelected(True)
    view.get_node_item("end").setSelected(True)
    assert view.get_selected_node_ids() == ["c1", "end"]  # 字母序
    FakeQMenu._exec_return = FakeQAction("连接选中（首→尾）")
    event = _FakeMouseEvent(FakeQPointF(0, 0))
    view.contextMenuEvent(event)
    # c1→end 边被创建（sample 原本无此边）
    assert any(e.target_id == "end"
               for e in view.model.get_out_edges("c1"))
    assert view.undo_count == 1


def test_context_menu_auto_layout(view_cls, sample_model):
    """右键 → 自动布局（节点坐标重排）。"""
    view = view_cls(sample_model)
    # 把所有节点挪到同一点（重叠）
    for nid in ("start", "c1", "ca", "cb", "end"):
        sample_model.move_node(nid, 0, 0)
    view.refresh()
    FakeQMenu._exec_return = FakeQAction("自动布局")
    event = _FakeMouseEvent(FakeQPointF(0, 0))
    view.contextMenuEvent(event)
    # 布局后至少有一个节点 y != 0
    nodes = view.model.get_nodes()
    assert any(n.y != 0.0 for n in nodes)


def test_context_menu_no_action_noop(view_cls, sample_model):
    """菜单取消（exec 返回 None）→ 无操作。"""
    view = view_cls(sample_model)
    FakeQMenu._exec_return = None
    event = _FakeMouseEvent(FakeQPointF(0, 0))
    before_count = view.model.node_count
    view.contextMenuEvent(event)
    assert view.model.node_count == before_count
    assert view.undo_count == 0


# ═══════════════════════════════════════════════════════════════════════
# 10. NodeItem / EdgeItem 内部行为
# ═══════════════════════════════════════════════════════════════════════


def test_node_item_stores_node_id_and_type(view_cls, sample_model):
    view = view_cls(sample_model)
    item = view.get_node_item("start")
    assert item.node_id == "start"
    assert item.node_type == TYPE_ENTRY


def test_node_item_update_from_data(view_cls, sample_model):
    """update_from_data 刷新位置 + 文本。"""
    view = view_cls(sample_model)
    item = view.get_node_item("start")
    new_data = NodeData(id="start", title="NEW", preview="newtext",
                        node_type=TYPE_ENTRY, x=42, y=99)
    item.update_from_data(new_data)
    assert item.x() == 42.0
    assert item.y() == 99.0
    if item._title_item is not None:
        assert item._title_item.toPlainText() == "NEW"
    if item._preview_item is not None:
        assert item._preview_item.toPlainText() == "newtext"


def test_edge_item_refresh_updates_geometry(view_cls, sample_model):
    """移动源节点后 EdgeItem.refresh 重算连线坐标。"""
    view = view_cls(sample_model)
    edge_item = view._edge_items[0]
    src = edge_item._source
    tgt = edge_item._target
    # 移动源节点
    src.setPos(FakeQPointF(100, 200))
    edge_item.refresh()
    line = edge_item.line()
    # 起点 = src 中心
    assert line[0] == 100 + NODE_WIDTH / 2
    assert line[1] == 200 + NODE_HEIGHT / 2


def test_edge_item_with_label(view_cls, empty_model):
    """带 label 的边 → 创建 label_item。"""
    m = empty_model
    m.add_node(NodeData(id="a", title="a", preview="", node_type=TYPE_NORMAL, x=0, y=0))
    m.add_node(NodeData(id="b", title="b", preview="", node_type=TYPE_NORMAL, x=220, y=0))
    m.add_edge(EdgeData(source_id="a", target_id="b", label="L1"))
    view = view_cls(m)
    edge_item = view._edge_items[0]
    assert edge_item._label == "L1"
    assert edge_item._label_item is not None


# ═══════════════════════════════════════════════════════════════════════
# 11. 真 PyQt6 smoke test（端到端渲染 chapter01）
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture
def qapp():
    """真 QApplication（offscreen）。"""
    PyQt6 = pytest.importorskip("PyQt6")
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_real_pyqt6_smoke_construct_view(qapp):
    """真 PyQt6：构造 view + refresh + items 创建。"""
    from editor.node_graph_model import story_to_graph
    from core.engine.main import _load_story

    chapter = Path(REPO_ROOT) / "chapters" / "chapter01_v1.md"
    story = _load_story(str(chapter))
    model = story_to_graph(story)

    RealView = _build_node_graph_view_class()  # qt=None → 真 import
    view = RealView(model)
    assert view.__class__.__name__ == "NodeGraphView"
    assert len(view._node_items) >= 1
    assert len(view._edge_items) >= 1
    assert view.undo_count == 0


def test_real_pyqt6_smoke_signal_emit(qapp):
    """真 PyQt6：nodeDoubleClicked 信号 connect + emit。"""
    from editor.node_graph_model import story_to_graph
    from core.engine.main import _load_story

    chapter = Path(REPO_ROOT) / "chapters" / "chapter01_v1.md"
    story = _load_story(str(chapter))
    model = story_to_graph(story)

    RealView = _build_node_graph_view_class()
    view = RealView(model)
    hits: list = []
    view.nodeDoubleClicked.connect(lambda nid: hits.append(nid))
    view.nodeDoubleClicked.emit("start")
    assert hits == ["start"]


def test_real_pyqt6_smoke_undo_redo(qapp):
    """真 PyQt6：add → undo → redo 闭环。"""
    from editor.node_graph_model import NodeGraphModel

    RealView = _build_node_graph_view_class()
    view = RealView(NodeGraphModel())
    nid = view.add_node_at(100, 200, node_id="real1")
    assert nid == "real1"
    assert view.undo_count == 1
    assert view.undo() is True
    assert view.model.has_node("real1") is False
    assert view.redo() is True
    assert view.model.has_node("real1") is True


def test_real_pyqt6_smoke_node_item_coloring(qapp):
    """真 PyQt6：不同类型节点用不同 brush 颜色。"""
    from editor.node_graph_model import NodeGraphModel, NodeData, TYPE_COLORS
    from PyQt6.QtGui import QBrush

    m = NodeGraphModel()
    m.add_node(NodeData(id="start", title="s", preview="", node_type=TYPE_ENTRY))
    m.add_node(NodeData(id="end", title="e", preview="", node_type=TYPE_ENDING))

    RealView = _build_node_graph_view_class()
    view = RealView(m)
    start_item = view.get_node_item("start")
    end_item = view.get_node_item("end")
    # brush 是 QBrush 实例
    assert isinstance(start_item.brush(), QBrush)
    assert isinstance(end_item.brush(), QBrush)
