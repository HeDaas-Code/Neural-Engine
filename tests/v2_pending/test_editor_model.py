"""v4-08 · EditorModel 编辑器主框架编排器测试（#116）。

验证 issue #116 验收点：
- EditorModel：聚合各子模型（ChapterManagerModel/ResourceManager/DslSync/
  DebuggerModel/ProjectExporter）的高层编排 API
- 当前章节生命周期：open / save / save_as / close / reload
- DSL 双向同步委托：update_from_source / update_from_graph
- 章节管理委托：list / create / delete / rename（含当前章节交互）
- 资源列表委托
- 预览/调试生命周期：run_preview / stop_preview / 预览运行时保护
- 导出委托：export_project / validate_project
- 脏标记跟踪
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
    DEFAULT_RESOURCES_ROOT, RESOURCE_AUDIO, RESOURCE_IMAGE,
)
from editor.preview_controller import (
    STATUS_IDLE, STATUS_RUNNING, STATUS_PAUSED, STATUS_STOPPED,
)
from editor.project_exporter import DEFAULT_EXPORT_NAME
from editor.node_graph_model import NodeGraphModel
from editor.dsl_sync import DslSync


# ═══════════════════════════════════════════════════════════════════════
# 辅助：构造测试项目
# ═══════════════════════════════════════════════════════════════════════


_SIMPLE_CHAPTER = """```neon
id:start
next: scene1
node start
开始。
node end
```

```neon
id:scene1
id:end
node start
结束。
node end
```
"""

_INPUT_CHAPTER = """```neon
id:start
next: c1
node start
开始。
node end
```

```neon
id:c1
next: c2
node start
node in → pick
node echo pick
node end
```

```neon
id:c2
id:end
node start
结束。
node end
```
"""


def _make_project(tmp_path: Path, *, with_resources: bool = True) -> Path:
    """构造测试项目：2 章节 + 2 资源。返回项目根。"""
    root = tmp_path / "proj"
    root.mkdir()
    chapters = root / DEFAULT_CHAPTERS_ROOT
    chapters.mkdir()
    (chapters / "chapter01.md").write_text(_SIMPLE_CHAPTER, encoding="utf-8")
    (chapters / "chapter02.md").write_text(_SIMPLE_CHAPTER, encoding="utf-8")
    (chapters / "input.md").write_text(_INPUT_CHAPTER, encoding="utf-8")
    if with_resources:
        resources = root / DEFAULT_RESOURCES_ROOT
        (resources / "audio").mkdir(parents=True)
        (resources / "images").mkdir(parents=True)
        (resources / "audio" / "rain.mp3").write_bytes(b"fake mp3" * 100)
        (resources / "images" / "forest.png").write_bytes(b"fake png" * 200)
    return root


def _wait_for_status(em: EditorModel, status: str, timeout: float = 2.0) -> bool:
    """轮询等待 preview_status == status。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if em.preview_status == status:
            return True
        time.sleep(0.005)
    return False


# ═══════════════════════════════════════════════════════════════════════
# 1. 构造与属性
# ═══════════════════════════════════════════════════════════════════════


def test_construct_with_project_root(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    assert em.project_root == root
    assert em.chapters_root == root / DEFAULT_CHAPTERS_ROOT
    assert em.resources_root == root / DEFAULT_RESOURCES_ROOT


def test_default_root_is_cwd():
    em = EditorModel()
    assert em.project_root == Path.cwd()


def test_sub_managers_exposed(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    assert isinstance(em.chapter_manager, ChapterManagerModel)
    assert em.chapter_manager.chapters_root == em.chapters_root
    # resource_manager / exporter 也应可用
    assert em.resource_manager is not None
    assert em.exporter is not None


def test_initial_state_no_current_chapter(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    assert em.has_current_chapter is False
    assert em.current_chapter_name is None
    assert em.current_source is None
    assert em.current_model is None
    assert em.is_dirty is False
    assert em.debugger is None
    assert em.preview_status == STATUS_IDLE
    assert em.is_preview_running is False


def test_auto_scan_on_init(tmp_path):
    """构造后立即扫描，list_chapters 可用。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    assert em.chapter_count == 3
    names = em.list_chapter_names()
    assert "chapter01" in names
    assert "chapter02" in names
    assert "input" in names


# ═══════════════════════════════════════════════════════════════════════
# 2. 章节列表 / 资源列表（委托）
# ═══════════════════════════════════════════════════════════════════════


def test_list_chapters_returns_entries(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    chapters = em.list_chapters()
    assert len(chapters) == 3
    # 按名排序
    names = [c.name for c in chapters]
    assert names == sorted(names)


def test_list_chapter_names(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    names = em.list_chapter_names()
    assert "chapter01" in names
    assert len(names) == 3


def test_list_resources_all(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    resources = em.list_resources()
    assert len(resources) == 2
    assert em.resource_count == 2


def test_list_resources_by_type(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    audio = em.list_resources(RESOURCE_AUDIO)
    assert len(audio) == 1
    assert audio[0].name == "rain.mp3"
    images = em.list_resources(RESOURCE_IMAGE)
    assert len(images) == 1
    assert images[0].name == "forest.png"


def test_list_resources_empty(tmp_path):
    """无 resources/ → 空列表。"""
    root = _make_project(tmp_path, with_resources=False)
    em = EditorModel(project_root=root)
    assert em.list_resources() == []
    assert em.resource_count == 0


# ═══════════════════════════════════════════════════════════════════════
# 3. open_chapter
# ═══════════════════════════════════════════════════════════════════════


def test_open_chapter_success(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    model = em.open_chapter("chapter01")
    assert isinstance(model, NodeGraphModel)
    assert em.has_current_chapter is True
    assert em.current_chapter_name == "chapter01"
    assert em.current_source is not None
    assert em.is_dirty is False
    # 2 块 chapter01 → 2 节点
    assert model.node_count == 2


def test_open_chapter_not_found(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    with pytest.raises(ValueError, match="not found"):
        em.open_chapter("nope")


def test_open_chapter_sets_current_source(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    em.open_chapter("chapter01")
    assert "id:start" in em.current_source
    assert "id:scene1" in em.current_source


def test_open_chapter_switches_current(tmp_path):
    """打开第二个章节 → 当前切换。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    em.open_chapter("chapter01")
    assert em.current_chapter_name == "chapter01"
    em.open_chapter("chapter02")
    assert em.current_chapter_name == "chapter02"


def test_open_chapter_clears_dirty(tmp_path):
    """打开新章节时脏标记清零。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    em.open_chapter("chapter01")
    em.update_from_source(_SIMPLE_CHAPTER.replace("开始。", "改。"))
    assert em.is_dirty is True
    em.open_chapter("chapter02")
    assert em.is_dirty is False


# ═══════════════════════════════════════════════════════════════════════
# 4. save_chapter / save_chapter_as / close / reload
# ═══════════════════════════════════════════════════════════════════════


def test_save_chapter_writes_source(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    em.open_chapter("chapter01")
    new_src = _SIMPLE_CHAPTER.replace("开始。", "新内容。")
    em.update_from_source(new_src)
    assert em.is_dirty is True
    path = em.save_chapter()
    assert path.exists()
    assert em.is_dirty is False
    # 磁盘内容已更新
    on_disk = (em.chapters_root / "chapter01.md").read_text(encoding="utf-8")
    assert "新内容。" in on_disk


def test_save_chapter_no_current_raises(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    with pytest.raises(ValueError, match="no chapter open"):
        em.save_chapter()


def test_save_chapter_as_creates_new(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    em.open_chapter("chapter01")
    em.update_from_source(_SIMPLE_CHAPTER.replace("开始。", "另存。"))
    path = em.save_chapter_as("chapter03")
    assert path.exists()
    # 切换到新章节
    assert em.current_chapter_name == "chapter03"
    assert em.is_dirty is False
    # 新章节内容已写入
    on_disk = (em.chapters_root / "chapter03.md").read_text(encoding="utf-8")
    assert "另存。" in on_disk
    # 原章节未变
    original = (em.chapters_root / "chapter01.md").read_text(encoding="utf-8")
    assert "另存。" not in original


def test_save_chapter_as_no_current_raises(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    with pytest.raises(ValueError, match="no chapter open"):
        em.save_chapter_as("new")


def test_close_chapter_clears_state(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    em.open_chapter("chapter01")
    em.close_chapter()
    assert em.has_current_chapter is False
    assert em.current_chapter_name is None
    assert em.current_source is None
    assert em.current_model is None
    assert em.is_dirty is False


def test_close_chapter_idempotent(tmp_path):
    """无当前章节时 close 不抛错。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    em.close_chapter()  # no-op


def test_reload_chapter_discards_changes(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    em.open_chapter("chapter01")
    original = em.current_source
    em.update_from_source(_SIMPLE_CHAPTER.replace("开始。", "临时改。"))
    assert em.current_source != original
    assert em.is_dirty is True
    em.reload_chapter()
    assert em.current_source == original
    assert em.is_dirty is False


def test_reload_no_current_raises(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    with pytest.raises(ValueError, match="no chapter open"):
        em.reload_chapter()


# ═══════════════════════════════════════════════════════════════════════
# 5. DSL 双向同步
# ═══════════════════════════════════════════════════════════════════════


def test_update_from_source_marks_dirty(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    em.open_chapter("chapter01")
    em.update_from_source(_SIMPLE_CHAPTER)
    assert em.is_dirty is True
    assert em.current_model is not None


def test_update_from_graph_marks_dirty(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    em.open_chapter("chapter01")
    model = em.current_model
    em.update_from_graph(model)
    assert em.is_dirty is True


def test_update_from_source_no_current_raises(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    with pytest.raises(ValueError, match="no chapter open"):
        em.update_from_source("x")


def test_update_from_graph_no_current_raises(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    with pytest.raises(ValueError, match="no chapter open"):
        em.update_from_graph(None)


def test_dsl_round_trip_preserves_structure(tmp_path):
    """open → update_from_source(原源码) → 结构不变。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    em.open_chapter("chapter01")
    original_source = em.current_source
    original_node_count = em.current_model.node_count
    em.update_from_source(original_source)
    assert em.current_model.node_count == original_node_count


# ═══════════════════════════════════════════════════════════════════════
# 6. 章节管理（委托 + 当前章节交互）
# ═══════════════════════════════════════════════════════════════════════


def test_create_chapter(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    path = em.create_chapter("newchap")
    assert path.exists()
    assert em.has_chapter("newchap")
    assert em.chapter_count == 4


def test_create_chapter_duplicate_raises(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    with pytest.raises(ValueError, match="already exists"):
        em.create_chapter("chapter01")


def test_delete_chapter(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    assert em.delete_chapter("chapter02") is True
    assert not em.has_chapter("chapter02")
    assert em.chapter_count == 2


def test_delete_chapter_nonexistent_returns_false(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    assert em.delete_chapter("nope") is False


def test_delete_current_chapter_closes_it(tmp_path):
    """删除当前章节 → 自动关闭当前。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    em.open_chapter("chapter01")
    assert em.has_current_chapter is True
    em.delete_chapter("chapter01")
    assert em.has_current_chapter is False
    assert em.current_chapter_name is None


def test_rename_chapter(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    em.rename_chapter("chapter01", "intro")
    assert em.has_chapter("intro")
    assert not em.has_chapter("chapter01")


def test_rename_current_chapter_updates_name(tmp_path):
    """重命名当前章节 → current_chapter_name 跟着变。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    em.open_chapter("chapter01")
    em.rename_chapter("chapter01", "intro")
    assert em.current_chapter_name == "intro"
    assert em.has_current_chapter is True


# ═══════════════════════════════════════════════════════════════════════
# 7. 预览 / 调试生命周期
# ═══════════════════════════════════════════════════════════════════════


def test_run_preview_completes(tmp_path):
    """run_preview 用当前章节 story 跑预览 → 自然完成。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    em.open_chapter("chapter01")
    assert em.run_preview() is True
    assert _wait_for_status(em, STATUS_STOPPED, timeout=2.0)
    # 完成后 debugger 仍在（直到 stop_preview）
    assert em.debugger is not None
    em.stop_preview()
    assert em.debugger is None
    assert em.preview_status == STATUS_IDLE


def test_run_preview_no_current_raises(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    with pytest.raises(ValueError, match="no chapter open"):
        em.run_preview()


def test_run_preview_breakpoint_pauses(tmp_path):
    """run_preview + 预设断点 → PAUSED（断点在 run 前注入，避免竞态）。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    em.open_chapter("chapter01")
    em.run_preview(breakpoints=["scene1"])
    assert _wait_for_status(em, STATUS_PAUSED, timeout=2.0)
    assert em.preview_status == STATUS_PAUSED
    em.stop_preview()


def test_stop_preview_idempotent(tmp_path):
    """无预览时 stop_preview 不抛错。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    em.stop_preview()  # no-op


def test_open_chapter_blocked_while_preview_running(tmp_path):
    """预览暂停中 open_chapter 抛 ValueError。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    em.open_chapter("chapter01")
    em.run_preview(breakpoints=["scene1"])  # 暂停在 scene1
    assert _wait_for_status(em, STATUS_PAUSED, timeout=2.0)
    with pytest.raises(ValueError, match="preview is running"):
        em.open_chapter("chapter02")
    em.stop_preview()


def test_close_chapter_blocked_while_preview_running(tmp_path):
    """预览暂停中 close_chapter 抛 ValueError。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    em.open_chapter("chapter01")
    em.run_preview(breakpoints=["scene1"])
    assert _wait_for_status(em, STATUS_PAUSED, timeout=2.0)
    with pytest.raises(ValueError, match="preview is running"):
        em.close_chapter()
    em.stop_preview()


def test_run_preview_twice_returns_false(tmp_path):
    """已有预览在跑 → 第二次 run_preview 返回 False。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    em.open_chapter("chapter01")
    em.run_preview(breakpoints=["scene1"])
    assert _wait_for_status(em, STATUS_PAUSED, timeout=2.0)
    assert em.run_preview() is False
    em.stop_preview()


def test_debugger_provides_data(tmp_path):
    """预览后 debugger 提供变量/事件数据。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    em.open_chapter("chapter01")
    em.run_preview()
    _wait_for_status(em, STATUS_STOPPED, timeout=2.0)
    dbg = em.debugger
    # 执行路径非空（至少 start + scene1）
    path = dbg.get_execution_path()
    assert len(path) >= 2
    em.stop_preview()


# ═══════════════════════════════════════════════════════════════════════
# 8. 导出（委托 ProjectExporter）
# ═══════════════════════════════════════════════════════════════════════


def test_export_project(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    out = tmp_path / "out.zip"
    result = em.export_project(out, name="my-game", engine_version="0.1.0")
    assert out.exists()
    assert result.manifest.name == "my-game"
    assert result.manifest.engine_version == "0.1.0"
    assert result.file_count == 5  # 3 章 + 2 资源


def test_export_project_without_resources(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    out = tmp_path / "out.zip"
    result = em.export_project(out, name="my-game", include_resources=False)
    assert out.exists()
    # manifest 仍含资源条目（清单不裁剪），但实际打包不含
    assert len(result.manifest.resources) == 2


def test_validate_project_ok(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    assert em.validate_project() == []


def test_validate_project_no_chapters(tmp_path):
    """空项目（chapters/ 被 ChapterManagerModel 自动创建为空目录）→ 校验失败。"""
    root = tmp_path / "empty"
    root.mkdir()
    em = EditorModel(project_root=root)
    issues = em.validate_project()
    # ChapterManagerModel 会自动创建 chapters/ 目录，所以这里是 "no chapters"
    assert any("no chapters" in i for i in issues)


def test_scan_project_manifest(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    m = em.scan_project_manifest(name="my-game")
    assert m.name == "my-game"
    assert len(m.chapters) == 3
    assert len(m.resources) == 2


# ═══════════════════════════════════════════════════════════════════════
# 9. refresh
# ═══════════════════════════════════════════════════════════════════════


def test_refresh_picks_up_new_chapters(tmp_path):
    """refresh 后能识别外部新增的章节。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    assert em.chapter_count == 3
    # 外部新增章节
    (em.chapters_root / "external.md").write_text(_SIMPLE_CHAPTER, encoding="utf-8")
    # refresh 前 count 不变（索引是快照）
    assert em.chapter_count == 3
    em.refresh()
    assert em.chapter_count == 4
    assert em.has_chapter("external")


def test_refresh_picks_up_new_resources(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    assert em.resource_count == 2
    # 外部新增资源
    (em.resources_root / "audio" / "new.wav").write_bytes(b"new audio")
    em.refresh()
    assert em.resource_count == 3


# ═══════════════════════════════════════════════════════════════════════
# 10. 完整工作流集成
# ═══════════════════════════════════════════════════════════════════════


def test_full_workflow_open_edit_save_preview_export(tmp_path):
    """完整工作流：open → edit → save → preview → export。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)

    # 1. 列出章节
    assert em.chapter_count == 3

    # 2. 打开章节
    em.open_chapter("chapter01")
    assert em.has_current_chapter
    original_source = em.current_source

    # 3. 编辑源码（替换文本）
    edited = original_source.replace("开始。", "新的开始。")
    em.update_from_source(edited)
    assert em.is_dirty is True

    # 4. 保存
    em.save_chapter()
    assert em.is_dirty is False
    on_disk = (em.chapters_root / "chapter01.md").read_text(encoding="utf-8")
    assert "新的开始。" in on_disk

    # 5. 跑预览
    em.run_preview()
    assert _wait_for_status(em, STATUS_STOPPED, timeout=2.0)
    assert em.debugger is not None
    em.stop_preview()

    # 6. 导出项目
    out = tmp_path / "final.zip"
    result = em.export_project(out, name="my-game", engine_version="1.0")
    assert out.exists()
    assert result.manifest.name == "my-game"


def test_full_workflow_create_open_edit_save(tmp_path):
    """create → open → edit → save 工作流。"""
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    # 新建章节
    em.create_chapter("draft")
    assert em.has_chapter("draft")
    # 打开
    em.open_chapter("draft")
    assert em.current_model is not None
    # 模板有 2 块（start + scene1）
    assert em.current_model.node_count == 2
    # 编辑后保存
    em.update_from_source(_SIMPLE_CHAPTER)
    em.save_chapter()
    assert em.is_dirty is False
    # 重新打开验证
    em.close_chapter()
    em.open_chapter("draft")
    assert "id:start" in em.current_source


def test_has_chapter(tmp_path):
    root = _make_project(tmp_path)
    em = EditorModel(project_root=root)
    assert em.has_chapter("chapter01") is True
    assert em.has_chapter("nope") is False


# ═══════════════════════════════════════════════════════════════════════
# 11. 模块导入
# ═══════════════════════════════════════════════════════════════════════


def test_module_exports():
    import editor.editor_model as m
    assert "EditorModel" in m.__all__


def test_editor_model_pure_python_no_qt():
    """EditorModel 模块不依赖 PyQt6（纯 Python）。"""
    import sys
    # 暂时屏蔽 PyQt6（如果存在），确认仍能 import
    saved = {}
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("PyQt6"):
            saved[mod_name] = sys.modules.pop(mod_name)
    try:
        # 重新 import editor_model
        import importlib
        import editor.editor_model
        importlib.reload(editor.editor_model)
        assert hasattr(editor.editor_model, "EditorModel")
    finally:
        sys.modules.update(saved)
