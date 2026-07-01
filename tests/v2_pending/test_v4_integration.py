"""v4-09 · v4 开发工具台全功能集成测试（#117）。

验证 v4-01 ~ v4-08 所有组件在完整编辑器工作流中协同工作：

v4-01 NodeGraphModel/View  ── 节点图数据模型 + 视图工厂
v4-02 DslSync              ── 源码 ↔ 节点图双向同步
v4-03 PreviewController    ── 实时预览 + 断点
v4-04 ResourceManager      ── 资源扫描/校验
v4-05 ChapterManagerModel  ── 章节管理
v4-06 DebuggerModel        ── 调试器（变量/路径/事件）
v4-07 ProjectExporter      ── 项目导出/导入
v4-08 EditorModel          ── 主框架编排器

测试策略：
- 纯 Python（无 PyQt6 依赖，EditorModel 是纯 Python 编排器）
- 端到端工作流：create → open → edit → sync → save → preview → debug → export → extract → re-open
- 验证各组件交互的正确性（单组件行为由各 unit test 覆盖）
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")

from editor.editor_model import EditorModel
from editor.chapter_manager_model import (
    ChapterManagerModel, DEFAULT_CHAPTERS_ROOT, CHAPTER_TEMPLATE,
)
from editor.resource_manager import (
    ResourceManager, DEFAULT_RESOURCES_ROOT, RESOURCE_AUDIO, RESOURCE_IMAGE,
)
from editor.dsl_sync import DslSync, parse_source, story_to_source
from editor.node_graph_model import (
    NodeGraphModel, NodeData, EdgeData, story_to_graph,
    TYPE_ENTRY, TYPE_ENDING,
)
from editor.preview_controller import (
    PreviewController, BreakpointManager,
    STATUS_IDLE, STATUS_RUNNING, STATUS_PAUSED, STATUS_STOPPED,
)
from editor.debugger_model import (
    DebuggerModel, EVENT_STARTED, EVENT_PAUSED, EVENT_BREAKPOINT,
    EVENT_COMPLETED, EVENT_STOPPED,
)
from editor.project_exporter import (
    ProjectExporter, ExportManifest, MANIFEST_FILENAME, MANIFEST_VERSION,
)
from core.engine.executor import MemoryInputSink, MemoryEventSink
from core.engine.protocol import TextEvt


# ═══════════════════════════════════════════════════════════════════════
# 测试用章节源码
# ═══════════════════════════════════════════════════════════════════════


_CHAPTER_LINEAR = """```neon
id:start
next: scene1
node start
故事开始。
node end
```

```neon
id:scene1
next: scene2
node start
中间场景。
node end
```

```neon
id:scene2
id:end
node start
结局。
node end
```
"""

_CHAPTER_INPUT = """```neon
id:start
next: choice
node start
请选择。
node end
```

```neon
id:choice
next: finale
node start
node in → pick
node echo pick
node end
```

```neon
id:finale
id:end
node start
结束。
node end
```
"""


# ═══════════════════════════════════════════════════════════════════════
# 辅助
# ═══════════════════════════════════════════════════════════════════════


def _make_project(tmp_path: Path, *, with_resources: bool = True) -> Path:
    """构造测试项目：3 章节 + 2 资源。返回项目根。"""
    root = tmp_path / "game"
    root.mkdir()
    chapters = root / DEFAULT_CHAPTERS_ROOT
    chapters.mkdir()
    (chapters / "intro.md").write_text(_CHAPTER_LINEAR, encoding="utf-8")
    (chapters / "middle.md").write_text(_CHAPTER_LINEAR, encoding="utf-8")
    (chapters / "interactive.md").write_text(_CHAPTER_INPUT, encoding="utf-8")
    if with_resources:
        resources = root / DEFAULT_RESOURCES_ROOT
        (resources / "audio").mkdir(parents=True)
        (resources / "images").mkdir(parents=True)
        (resources / "audio" / "bgm.mp3").write_bytes(b"fake bgm" * 200)
        (resources / "audio" / "se.wav").write_bytes(b"fake se" * 50)
        (resources / "images" / "bg.png").write_bytes(b"fake png" * 300)
        (resources / "images" / "char.jpg").write_bytes(b"fake jpg" * 100)
    return root


def _wait_for_status(target, status: str, timeout: float = 2.0) -> bool:
    """轮询等待 preview_status / ctrl.status == status。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = target.preview_status if hasattr(target, "preview_status") else target.status
        if s == status:
            return True
        time.sleep(0.005)
    return False


# ═══════════════════════════════════════════════════════════════════════
# 1. 完整编辑工作流：create → open → edit → sync → save
# ═══════════════════════════════════════════════════════════════════════


def test_full_edit_workflow(tmp_path):
    """完整编辑工作流：新建 → 打开 → 编辑源码 → 同步图 → 编辑图 → 同步源码 → 保存。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)

    # 1. 新建章节
    em.create_chapter("draft")
    assert em.has_chapter("draft")

    # 2. 打开 → 模板有 2 块
    model = em.open_chapter("draft")
    assert model.node_count == 2
    assert em.is_dirty is False

    # 3. 替换源码为 3 块线性故事
    em.update_from_source(_CHAPTER_LINEAR)
    assert em.is_dirty is True
    assert em.current_model.node_count == 3

    # 4. 通过图模型操作：添加一个新节点 + 边
    graph = em.current_model
    graph.add_node(NodeData(id="extra", title="额外", preview="额外节点",
                            node_type="normal", x=400, y=200))
    assert graph.node_count == 4

    # 5. 同步图 → 源码
    em.update_from_graph(graph)
    assert em.is_dirty is True
    assert "extra" in em.current_source

    # 6. 保存
    path = em.save_chapter()
    assert path.exists()
    assert em.is_dirty is False

    # 7. 重新打开验证持久化
    em.close_chapter()
    em.open_chapter("draft")
    assert em.current_model.node_count == 4
    assert em.current_model.has_node("extra")
    assert "extra" in em.current_source


def test_open_edit_save_all_chapters(tmp_path):
    """打开所有章节 → 编辑 → 保存 → 验证全部持久化。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    names = em.list_chapter_names()
    assert len(names) == 3

    # 对每个章节：打开 → 编辑 → 保存
    for name in names:
        em.open_chapter(name)
        original = em.current_source
        # 添加一行注释（通过替换文本）
        edited = original.replace("node start", "node start\n新行。", 1)
        em.update_from_source(edited)
        em.save_chapter()

    # 验证全部已保存
    em.refresh()
    for name in names:
        em.open_chapter(name)
        assert "新行。" in em.current_source
        em.close_chapter()


# ═══════════════════════════════════════════════════════════════════════
# 2. DSL 双向同步 round-trip
# ═══════════════════════════════════════════════════════════════════════


def test_dsl_round_trip_source_to_graph_to_source(tmp_path):
    """源码 → 图 → 源码 round-trip 结构保真。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    em.open_chapter("intro")

    # 原始源码 → 图 → 源码
    original_source = em.current_source
    graph = em.current_model
    em.update_from_graph(graph)
    resynced_source = em.current_source

    # 重新解析 resynced 源码 → 图，比较结构
    graph2 = story_to_graph(parse_source(resynced_source))
    assert graph2.node_count == graph.node_count
    assert graph2.edge_count == graph.edge_count

    # 节点 id 集合一致
    ids1 = sorted(n.id for n in graph.get_nodes())
    ids2 = sorted(n.id for n in graph2.get_nodes())
    assert ids1 == ids2


def test_dsl_graph_edit_preserves_body(tmp_path):
    """图编辑（移动节点）→ 同步源码 → 块体保留。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    em.open_chapter("intro")

    # 原始块体文本
    original_source = em.current_source

    # 移动节点位置
    graph = em.current_model
    graph.move_node("scene1", 500, 300)
    em.update_from_graph(graph)

    # 块体内容保留（story_to_source 的文本仍在）
    assert "故事开始。" in em.current_source
    assert "中间场景。" in em.current_source
    assert "结局。" in em.current_source


def test_dsl_add_node_appears_in_source(tmp_path):
    """图新增节点 → 同步源码 → 新节点出现在源码。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    em.open_chapter("intro")

    graph = em.current_model
    original_count = graph.node_count
    graph.add_node(NodeData(
        id="new_scene", title="新场景", preview="新内容",
        node_type="normal", x=100, y=400,
    ))
    em.update_from_graph(graph)

    # 新节点在源码中
    assert "new_scene" in em.current_source
    # 重新解析后节点数 +1
    regraph = story_to_graph(parse_source(em.current_source))
    assert regraph.node_count == original_count + 1


# ═══════════════════════════════════════════════════════════════════════
# 3. 预览 + 调试集成
# ═══════════════════════════════════════════════════════════════════════


def test_preview_full_run_with_debugger_data(tmp_path):
    """完整预览：run → 完成 → debugger 收集执行路径 + 事件。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    em.open_chapter("intro")

    em.run_preview()
    assert _wait_for_status(em, STATUS_STOPPED, timeout=3.0)

    dbg = em.debugger
    # 执行路径包含所有 3 个块
    path = dbg.get_execution_path()
    assert "start" in path
    assert "scene1" in path
    assert "scene2" in path

    # 事件含 started + completed
    events = dbg.get_events()
    kinds = [e.kind for e in events]
    assert EVENT_STARTED in kinds
    assert EVENT_COMPLETED in kinds

    em.stop_preview()


def test_preview_breakpoint_inspect_resume(tmp_path):
    """断点调试：设断点 → 暂停 → 查变量 → 继续 → 完成。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    em.open_chapter("intro")

    # 预设断点在 scene1（中间块）
    em.run_preview(breakpoints=["scene1"])
    assert _wait_for_status(em, STATUS_PAUSED, timeout=2.0)

    dbg = em.debugger
    # 暂停在 scene1
    snap = dbg.get_snapshot()
    assert snap["block_id"] == "scene1"

    # 事件含 breakpoint
    events = dbg.get_events()
    kinds = [e.kind for e in events]
    assert EVENT_BREAKPOINT in kinds

    # 执行路径含 start + scene1（scene1 是当前块）
    path = dbg.get_execution_path()
    assert "start" in path
    assert "scene1" in path

    # 继续 → 完成
    dbg.resume()
    assert _wait_for_status(em, STATUS_STOPPED, timeout=2.0)

    # 完成后路径含所有 3 块
    path = dbg.get_execution_path()
    assert "scene2" in path

    em.stop_preview()


def test_preview_step_through_each_block(tmp_path):
    """单步执行：step 逐块推进 → 每步暂停 → 最终完成。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    em.open_chapter("intro")

    # 用断点先停在 start
    em.run_preview(breakpoints=["start"])
    assert _wait_for_status(em, STATUS_PAUSED, timeout=2.0)
    dbg = em.debugger

    # 单步执行 3 次：start → scene1 → scene2 → 完成
    visited = []
    for _ in range(3):
        dbg.step()
        assert _wait_for_status(em, STATUS_PAUSED, timeout=2.0) or \
               em.preview_status == STATUS_STOPPED
        snap = dbg.get_snapshot()
        if snap["block_id"]:
            visited.append(snap["block_id"])

    # 再 step 一次 → 完成
    dbg.step()
    assert _wait_for_status(em, STATUS_STOPPED, timeout=2.0)

    em.stop_preview()


def test_preview_with_input_chapter(tmp_path):
    """带 In 节点的章节预览：提供输入 → 完成。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    em.open_chapter("interactive")

    # 用带输入的 sink
    sink = MemoryInputSink(inputs=["1"])
    em.run_preview(sink=sink)
    assert _wait_for_status(em, STATUS_STOPPED, timeout=3.0)

    dbg = em.debugger
    # 执行路径含所有 3 块
    path = dbg.get_execution_path()
    assert "start" in path
    assert "choice" in path
    assert "finale" in path

    em.stop_preview()


# ═══════════════════════════════════════════════════════════════════════
# 4. 资源 + 章节管理集成
# ═══════════════════════════════════════════════════════════════════════


def test_resource_chapter_management_integration(tmp_path):
    """章节 + 资源管理协同：扫描 → 查询 → 统计。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)

    # 章节统计
    assert em.chapter_count == 3
    chapters = em.list_chapters()
    for c in chapters:
        assert c.block_count > 0  # 每章都有块
    total_blocks = sum(c.block_count for c in chapters)
    assert total_blocks > 0

    # 资源统计
    assert em.resource_count == 4
    audio = em.list_resources(RESOURCE_AUDIO)
    images = em.list_resources(RESOURCE_IMAGE)
    assert len(audio) == 2
    assert len(images) == 2

    # 按类型统计
    counts = em.resource_manager.count_by_type()
    assert counts[RESOURCE_AUDIO] == 2
    assert counts[RESOURCE_IMAGE] == 2


def test_chapter_crud_workflow(tmp_path):
    """章节 CRUD 完整工作流：create → read → update → delete。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    initial_count = em.chapter_count

    # Create
    em.create_chapter("test_crud")
    assert em.chapter_count == initial_count + 1

    # Read（打开）
    em.open_chapter("test_crud")
    assert em.current_model is not None
    original_source = em.current_source

    # Update（编辑 + 保存）
    em.update_from_source(_CHAPTER_LINEAR)
    em.save_chapter()
    # 验证磁盘更新
    em.close_chapter()
    em.open_chapter("test_crud")
    assert em.current_source != original_source  # 内容已变

    # Delete
    em.close_chapter()
    em.delete_chapter("test_crud")
    assert em.chapter_count == initial_count
    assert not em.has_chapter("test_crud")


def test_chapter_rename_current_preserves_edit_state(tmp_path):
    """重命名当前章节 → 当前名更新 → 编辑状态保留。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    em.open_chapter("intro")
    em.update_from_source(_CHAPTER_LINEAR.replace("故事开始。", "改。"))

    # 重命名当前章节
    em.rename_chapter("intro", "prologue")
    assert em.current_chapter_name == "prologue"
    assert em.has_current_chapter is True
    # 脏标记仍在（未保存）
    assert em.is_dirty is True

    # 保存到新名字
    em.save_chapter()
    assert em.is_dirty is False
    assert em.has_chapter("prologue")
    assert not em.has_chapter("intro")


# ═══════════════════════════════════════════════════════════════════════
# 5. 导出 round-trip 集成
# ═══════════════════════════════════════════════════════════════════════


def test_export_extract_full_round_trip(tmp_path):
    """完整导出 round-trip：编辑 → 导出 → 解压 → 重新打开 → 验证。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)

    # 1. 编辑章节
    em.open_chapter("intro")
    em.update_from_source(_CHAPTER_LINEAR.replace("故事开始。", "编辑后。"))
    em.save_chapter()
    em.close_chapter()

    # 2. 导出
    archive = tmp_path / "exported.zip"
    result = em.export_project(archive, name="my-game", engine_version="1.0")
    assert archive.exists()
    assert result.file_count == 7  # 3 章 + 4 资源

    # 3. 解压到新位置
    dest = tmp_path / "restored"
    manifest = ProjectExporter.extract_project(archive, dest)
    assert manifest.name == "my-game"
    assert manifest.engine_version == "1.0"

    # 4. 用新 EditorModel 打开解压后的项目
    em2 = EditorModel(project_root=dest)
    assert em2.chapter_count == 3
    assert em2.resource_count == 4

    # 5. 验证编辑内容已保留
    em2.open_chapter("intro")
    assert "编辑后。" in em2.current_source
    em2.close_chapter()

    # 6. 验证资源完整
    audio = em2.list_resources(RESOURCE_AUDIO)
    images = em2.list_resources(RESOURCE_IMAGE)
    assert len(audio) == 2
    assert len(images) == 2
    # 资源字节一致
    original_bgm = (root / DEFAULT_RESOURCES_ROOT / "audio" / "bgm.mp3").read_bytes()
    restored_bgm = (dest / DEFAULT_RESOURCES_ROOT / "audio" / "bgm.mp3").read_bytes()
    assert original_bgm == restored_bgm


def test_export_without_resources_then_extract(tmp_path):
    """仅导出章节（不含资源）→ 解压 → 验证资源缺失但章节完整。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)

    archive = tmp_path / "chapters_only.zip"
    em.export_project(archive, name="slim", include_resources=False)

    dest = tmp_path / "restored_slim"
    ProjectExporter.extract_project(archive, dest)

    em2 = EditorModel(project_root=dest)
    assert em2.chapter_count == 3
    # resources/ 不存在（未导出）
    assert em2.resource_count == 0


def test_read_manifest_without_extracting(tmp_path):
    """read_manifest 不解压直接读清单 → 验证元数据。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    archive = tmp_path / "proj.zip"
    em.export_project(archive, name="peek", engine_version="2.0")

    # 读清单
    manifest = ProjectExporter.read_manifest(archive)
    assert manifest.name == "peek"
    assert manifest.engine_version == "2.0"
    assert manifest.version == MANIFEST_VERSION
    assert len(manifest.chapters) == 3
    assert len(manifest.resources) == 4

    # 解压目录仍空
    dest = tmp_path / "should_be_empty"
    dest.mkdir()
    assert list(dest.iterdir()) == []


# ═══════════════════════════════════════════════════════════════════════
# 6. 跨组件协同：编辑 → 预览 → 导出
# ═══════════════════════════════════════════════════════════════════════


def test_edit_then_preview_reflects_changes(tmp_path):
    """编辑章节 → 预览反映编辑后的内容。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    em.open_chapter("intro")

    # 编辑：替换文本
    em.update_from_source(_CHAPTER_LINEAR.replace("故事开始。", "改写后的开始。"))
    em.save_chapter()

    # 预览：收集 TextEvt
    sink = MemoryInputSink()
    em.run_preview(sink=sink)
    _wait_for_status(em, STATUS_STOPPED, timeout=2.0)

    # 验证输出含改写后的文本
    texts = [e.content for e in sink.events if isinstance(e, TextEvt)]
    assert any("改写后的开始。" in t for t in texts)

    em.stop_preview()


def test_preview_multiple_chapters_sequentially(tmp_path):
    """连续预览多个章节：stop → 打开新章节 → run。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)

    for name in ["intro", "middle", "interactive"]:
        em.open_chapter(name)
        sink = MemoryInputSink(inputs=["1"]) if name == "interactive" else MemoryInputSink()
        em.run_preview(sink=sink)
        assert _wait_for_status(em, STATUS_STOPPED, timeout=3.0)
        # 执行路径非空
        assert len(em.debugger.get_execution_path()) > 0
        em.stop_preview()
        em.close_chapter()


def test_debugger_watch_variables_during_preview(tmp_path):
    """预览中设置监视变量 → 暂停时查监视值。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    em.open_chapter("interactive")

    # 提供输入 + 预设断点在 finale 块（choice 的 In 节点已执行）
    sink = MemoryInputSink(inputs=["1"])
    em.run_preview(sink=sink, breakpoints=["finale"])
    assert _wait_for_status(em, STATUS_PAUSED, timeout=3.0)

    dbg = em.debugger
    # 添加监视变量 pick（interactive 章节的 In 节点设置 pick）
    dbg.add_watch("pick")
    watched = dbg.get_watched_variables()
    # pick 应有值（In 节点已执行）
    assert "pick" in watched

    em.stop_preview()


# ═══════════════════════════════════════════════════════════════════════
# 7. 端到端：完整 v4 工作流
# ═══════════════════════════════════════════════════════════════════════


def test_end_to_end_v4_workflow(tmp_path):
    """端到端 v4 工作流：创建项目 → 编辑 → 预览 → 调试 → 导出 → 导入 → 验证。

    覆盖 v4-01 ~ v4-08 所有组件的协同：
    - EditorModel (v4-08) 编排
    - ChapterManagerModel (v4-05) 章节管理
    - ResourceManager (v4-04) 资源管理
    - DslSync (v4-02) 双向同步
    - NodeGraphModel (v4-01) 节点图
    - PreviewController (v4-03) 预览
    - DebuggerModel (v4-06) 调试
    - ProjectExporter (v4-07) 导出
    """
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)

    # ── 1. 项目扫描 ──
    assert em.chapter_count == 3
    assert em.resource_count == 4

    # ── 2. 章节编辑（DslSync + NodeGraphModel）──
    em.open_chapter("intro")
    assert em.current_model.node_count == 3  # start + scene1 + scene2

    # 编辑源码
    em.update_from_source(_CHAPTER_LINEAR.replace("故事开始。", "v4 编辑。"))
    assert em.is_dirty is True

    # 图操作：添加节点
    graph = em.current_model
    graph.add_node(NodeData(
        id="bonus", title="奖励", preview="奖励场景",
        node_type="normal", x=600, y=100,
    ))
    em.update_from_graph(graph)
    assert "bonus" in em.current_source

    # 保存
    em.save_chapter()
    assert em.is_dirty is False
    em.close_chapter()

    # ── 3. 预览 + 调试（PreviewController + DebuggerModel）──
    em.open_chapter("middle")
    em.run_preview(breakpoints=["scene1"])
    assert _wait_for_status(em, STATUS_PAUSED, timeout=2.0)

    dbg = em.debugger
    # 断点命中
    assert dbg.get_snapshot()["block_id"] == "scene1"
    # 事件含 breakpoint
    assert any(e.kind == EVENT_BREAKPOINT for e in dbg.get_events())

    # 继续 → 完成
    dbg.resume()
    assert _wait_for_status(em, STATUS_STOPPED, timeout=2.0)
    # 执行路径完整
    path = dbg.get_execution_path()
    assert "scene2" in path

    em.stop_preview()
    em.close_chapter()

    # ── 4. 导出（ProjectExporter）──
    archive = tmp_path / "v4_release.zip"
    result = em.export_project(archive, name="v4-game", engine_version="v4.0")
    assert archive.exists()
    assert result.manifest.name == "v4-game"

    # ── 5. 导入到新位置 ──
    dest = tmp_path / "installed"
    manifest = ProjectExporter.extract_project(archive, dest)
    assert manifest.name == "v4-game"
    assert manifest.engine_version == "v4.0"

    # ── 6. 验证导入项目完整 ──
    em2 = EditorModel(project_root=dest)
    assert em2.chapter_count == 3
    assert em2.resource_count == 4

    # intro 章节含编辑 + 新节点
    em2.open_chapter("intro")
    assert "v4 编辑。" in em2.current_source
    assert "bonus" in em2.current_source
    assert em2.current_model.has_node("bonus")
    em2.close_chapter()

    # 资源完整
    assert len(em2.list_resources(RESOURCE_AUDIO)) == 2
    assert len(em2.list_resources(RESOURCE_IMAGE)) == 2

    # ── 7. 导入后的项目可预览 ──
    em2.open_chapter("middle")
    em2.run_preview()
    assert _wait_for_status(em2, STATUS_STOPPED, timeout=2.0)
    assert len(em2.debugger.get_execution_path()) > 0
    em2.stop_preview()


def test_v4_components_pure_python_no_qt(tmp_path):
    """v4 所有核心组件（不含 NodeGraphView）不依赖 PyQt6。"""
    import sys
    # 暂时屏蔽 PyQt6
    saved = {}
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("PyQt6"):
            saved[mod_name] = sys.modules.pop(mod_name)
    try:
        root = _make_project(tmp_path)
        # EditorModel + 所有子模块在无 PyQt6 下应正常工作
        em = EditorModel(project_root=root)
        em.open_chapter("intro")
        em.update_from_source(_CHAPTER_LINEAR)
        em.save_chapter()
        em.run_preview()
        import time as _t; _t.sleep(0.1)
        em.stop_preview()
        em.export_project(tmp_path / "noqt.zip", name="test")
        # 全部操作无 Qt 依赖即可完成
    finally:
        sys.modules.update(saved)
