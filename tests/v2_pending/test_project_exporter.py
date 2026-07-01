"""v4-07 · ProjectExporter 项目导出测试（#115）。

验证 issue #115 验收点：
- ExportManifest：to_dict/from_dict 序列化 + version 前向保护
- ProjectExporter：scan_project / validate_project / list_files / estimate_size
- export：打包 chapters/ + resources/ + project.json 清单为 zip
- extract_project：从 zip 导入（zip-slip 防护 + 覆盖检查 + round-trip）
- read_manifest：不解压只读清单
- P0-S1 安全校验：拒绝 symlink / 路径穿越 / 超大文件 / 超多文件
"""
from __future__ import annotations

import json
import os
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")

from editor.project_exporter import (
    ProjectExporter, ExportManifest, ExportResult,
    MANIFEST_FILENAME, MANIFEST_VERSION,
    DEFAULT_EXPORT_NAME, MAX_PROJECT_SIZE, MAX_FILE_COUNT,
)
from editor.chapter_manager_model import DEFAULT_CHAPTERS_ROOT, CHAPTER_TEMPLATE
from editor.resource_manager import DEFAULT_RESOURCES_ROOT


# ═══════════════════════════════════════════════════════════════════════
# 辅助：构造测试项目目录结构
# ═══════════════════════════════════════════════════════════════════════


def _make_chapter(root: Path, name: str, content: str | None = None) -> Path:
    """在 root/chapters 下建章节文件。返回路径。"""
    chapters = root / DEFAULT_CHAPTERS_ROOT
    chapters.mkdir(parents=True, exist_ok=True)
    p = chapters / f"{name}.md"
    p.write_text(content if content is not None else CHAPTER_TEMPLATE, encoding="utf-8")
    return p


def _make_resource(root: Path, relpath: str, content: bytes = b"fake") -> Path:
    """在 root/resources 下建资源文件。relpath 含子目录。返回路径。"""
    resources = root / DEFAULT_RESOURCES_ROOT
    p = resources / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return p


def _make_project(tmp_path: Path, *, with_resources: bool = True) -> Path:
    """构造完整测试项目：2 章节 + 2 资源。返回项目根。"""
    root = tmp_path / "proj"
    root.mkdir()
    _make_chapter(root, "chapter01", CHAPTER_TEMPLATE)
    _make_chapter(root, "chapter02", CHAPTER_TEMPLATE)
    if with_resources:
        _make_resource(root, "audio/rain.mp3", b"fake mp3" * 100)
        _make_resource(root, "images/forest.png", b"fake png" * 200)
    return root


# ═══════════════════════════════════════════════════════════════════════
# 1. 常量与模块导入
# ═══════════════════════════════════════════════════════════════════════


def test_constants():
    assert MANIFEST_FILENAME == "project.json"
    assert MANIFEST_VERSION == 1
    assert DEFAULT_EXPORT_NAME == "project"
    assert MAX_PROJECT_SIZE == 200_000_000
    assert MAX_FILE_COUNT == 5_000


def test_module_exports():
    import editor.project_exporter as m
    assert "ProjectExporter" in m.__all__
    assert "ExportManifest" in m.__all__
    assert "ExportResult" in m.__all__


# ═══════════════════════════════════════════════════════════════════════
# 2. ExportManifest 序列化
# ═══════════════════════════════════════════════════════════════════════


def test_manifest_to_dict_round_trip():
    m = ExportManifest(
        version=1,
        name="my-game",
        created_at="2026-01-01T00:00:00",
        chapters=[{"name": "c1", "filename": "c1.md", "relative_path": "c1.md",
                   "size": 10, "block_count": 2}],
        resources=[{"name": "rain.mp3", "relative_path": "audio/rain.mp3",
                    "resource_type": "audio", "size": 100}],
        total_size=110,
        file_count=2,
        engine_version="0.1.0",
    )
    d = m.to_dict()
    assert d["version"] == 1
    assert d["name"] == "my-game"
    assert d["total_size"] == 110
    assert d["file_count"] == 2
    assert d["engine_version"] == "0.1.0"
    assert len(d["chapters"]) == 1
    assert len(d["resources"]) == 1
    # round-trip
    m2 = ExportManifest.from_dict(d)
    assert m2 == m


def test_manifest_from_dict_default_engine_version():
    """缺 engine_version 字段 → 默认空串。"""
    d = {
        "version": 1, "name": "x", "created_at": "ts",
        "chapters": [], "resources": [],
        "total_size": 0, "file_count": 0,
    }
    m = ExportManifest.from_dict(d)
    assert m.engine_version == ""


def test_manifest_from_dict_rejects_non_dict():
    with pytest.raises(ValueError, match="期望 dict"):
        ExportManifest.from_dict("not a dict")  # type: ignore[arg-type]


def test_manifest_from_dict_rejects_future_version():
    """version > MANIFEST_VERSION → 拒绝（前向保护）。"""
    d = {"version": MANIFEST_VERSION + 1, "name": "x"}
    with pytest.raises(ValueError, match="不支持"):
        ExportManifest.from_dict(d)


def test_manifest_from_dict_accepts_current_version():
    """version == MANIFEST_VERSION → 通过。"""
    m = ExportManifest.from_dict({"version": MANIFEST_VERSION})
    assert m.version == MANIFEST_VERSION


def test_manifest_frozen():
    """frozen dataclass 不可变。"""
    m = ExportManifest(
        version=1, name="x", created_at="t",
        chapters=[], resources=[], total_size=0, file_count=0,
    )
    with pytest.raises(Exception):
        m.name = "y"  # type: ignore[misc]


def test_manifest_json_serializable():
    """to_dict() 可 JSON 序列化（D2 决策：ensure_ascii=False）。"""
    m = ExportManifest(
        version=1, name="中文游戏", created_at="ts",
        chapters=[{"name": "章一", "size": 5}],
        resources=[], total_size=5, file_count=1,
    )
    s = json.dumps(m.to_dict(), ensure_ascii=False, indent=2)
    assert "中文游戏" in s
    assert "章一" in s
    # 反序列化回来
    m2 = ExportManifest.from_dict(json.loads(s))
    assert m2.name == "中文游戏"


# ═══════════════════════════════════════════════════════════════════════
# 3. ExportResult dataclass
# ═══════════════════════════════════════════════════════════════════════


def test_export_result_frozen():
    r = ExportResult(
        archive_path=Path("/tmp/x.zip"),
        manifest=ExportManifest(
            version=1, name="x", created_at="t",
            chapters=[], resources=[], total_size=0, file_count=0,
        ),
        file_count=0,
        total_size=0,
    )
    with pytest.raises(Exception):
        r.file_count = 99  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════════════════
# 4. ProjectExporter 构造与属性
# ═══════════════════════════════════════════════════════════════════════


def test_exporter_default_root_is_cwd():
    exp = ProjectExporter()
    assert exp.project_root == Path.cwd()
    assert exp.chapters_root == Path.cwd() / DEFAULT_CHAPTERS_ROOT
    assert exp.resources_root == Path.cwd() / DEFAULT_RESOURCES_ROOT


def test_exporter_custom_root(tmp_path):
    root = tmp_path / "myproj"
    root.mkdir()
    exp = ProjectExporter(project_root=root)
    assert exp.project_root == root
    assert exp.chapters_root == root / DEFAULT_CHAPTERS_ROOT
    assert exp.resources_root == root / DEFAULT_RESOURCES_ROOT


# ═══════════════════════════════════════════════════════════════════════
# 5. scan_project
# ═══════════════════════════════════════════════════════════════════════


def test_scan_project_with_chapters_and_resources(tmp_path):
    root = _make_project(tmp_path)
    exp = ProjectExporter(project_root=root)
    m = exp.scan_project(name="my-game", engine_version="0.1.0")
    assert m.version == MANIFEST_VERSION
    assert m.name == "my-game"
    assert m.engine_version == "0.1.0"
    assert len(m.chapters) == 2
    assert len(m.resources) == 2
    assert m.file_count == 4
    assert m.total_size > 0
    assert m.created_at  # 非空


def test_scan_project_without_resources(tmp_path):
    """resources/ 不存在 → resources 列表为空，但不报错。"""
    root = _make_project(tmp_path, with_resources=False)
    exp = ProjectExporter(project_root=root)
    m = exp.scan_project()
    assert len(m.chapters) == 2
    assert m.resources == []
    assert m.file_count == 2


def test_scan_project_default_name():
    exp = ProjectExporter(project_root=Path("/nonexistent"))
    m = exp.scan_project()
    assert m.name == DEFAULT_EXPORT_NAME


def test_scan_project_empty_chapters_dir(tmp_path):
    """chapters/ 存在但空 → chapters 列表为空。"""
    root = tmp_path / "proj"
    (root / DEFAULT_CHAPTERS_ROOT).mkdir(parents=True)
    exp = ProjectExporter(project_root=root)
    m = exp.scan_project()
    assert m.chapters == []
    assert m.resources == []
    assert m.total_size == 0
    assert m.file_count == 0


def test_scan_project_no_chapters_dir(tmp_path):
    """chapters/ 不存在 → chapters 列表为空。"""
    root = tmp_path / "proj"
    root.mkdir()
    exp = ProjectExporter(project_root=root)
    m = exp.scan_project()
    assert m.chapters == []


def test_scan_chapter_entry_fields(tmp_path):
    root = _make_project(tmp_path)
    exp = ProjectExporter(project_root=root)
    m = exp.scan_project()
    c = m.chapters[0]
    assert set(c.keys()) == {"name", "filename", "relative_path", "size", "block_count"}


def test_scan_resource_entry_fields(tmp_path):
    root = _make_project(tmp_path)
    exp = ProjectExporter(project_root=root)
    m = exp.scan_project()
    r = m.resources[0]
    assert set(r.keys()) == {"name", "relative_path", "resource_type", "size"}


# ═══════════════════════════════════════════════════════════════════════
# 6. validate_project
# ═══════════════════════════════════════════════════════════════════════


def test_validate_ok(tmp_path):
    root = _make_project(tmp_path)
    exp = ProjectExporter(project_root=root)
    assert exp.validate_project() == []


def test_validate_no_chapters_root(tmp_path):
    """chapters_root 不存在 → 1 个问题。"""
    root = tmp_path / "proj"
    root.mkdir()
    exp = ProjectExporter(project_root=root)
    issues = exp.validate_project()
    assert any("chapters_root not found" in i for i in issues)


def test_validate_empty_chapters_dir(tmp_path):
    """chapters/ 存在但空 → 1 个问题。"""
    root = tmp_path / "proj"
    (root / DEFAULT_CHAPTERS_ROOT).mkdir(parents=True)
    exp = ProjectExporter(project_root=root)
    issues = exp.validate_project()
    assert any("no chapters to export" in i for i in issues)


def test_validate_symlink_chapter_silently_skipped(tmp_path):
    """symlink 章节由 ChapterManagerModel.scan 静默跳过 → 不在导出列表，validate 仍通过。

    底层 ChapterManagerModel.scan 会跳过 symlink（记 warning），所以 symlink 章节
    既不进入 manifest 也不出现在 list_files；ProjectExporter 不需要重复检查。
    """
    root = _make_project(tmp_path)
    chapters = root / DEFAULT_CHAPTERS_ROOT
    os.symlink(chapters / "chapter01.md", chapters / "link.md")
    exp = ProjectExporter(project_root=root)
    # symlink 不在导出列表
    files = exp.list_files()
    filenames = [f.name for f in files]
    assert "link.md" not in filenames
    assert "chapter01.md" in filenames
    # validate 仍通过（symlink 已被底层过滤）
    assert exp.validate_project() == []


def test_validate_symlink_resource_silently_skipped(tmp_path):
    """symlink 资源由 ResourceManager.scan 静默跳过 → 不在导出列表。"""
    root = _make_project(tmp_path)
    resources = root / DEFAULT_RESOURCES_ROOT
    os.symlink(resources / "audio" / "rain.mp3",
               resources / "audio" / "link.mp3")
    exp = ProjectExporter(project_root=root)
    files = exp.list_files()
    filenames = [f.name for f in files]
    assert "link.mp3" not in filenames
    assert "rain.mp3" in filenames
    assert exp.validate_project() == []


# ═══════════════════════════════════════════════════════════════════════
# 7. list_files / estimate_size
# ═══════════════════════════════════════════════════════════════════════


def test_list_files_includes_all(tmp_path):
    root = _make_project(tmp_path)
    exp = ProjectExporter(project_root=root)
    files = exp.list_files()
    assert len(files) == 4  # 2 章 + 2 资源
    # 都是绝对路径
    assert all(f.is_absolute() for f in files)
    # 排序
    assert files == sorted(files)


def test_list_files_no_resources(tmp_path):
    root = _make_project(tmp_path, with_resources=False)
    exp = ProjectExporter(project_root=root)
    files = exp.list_files()
    assert len(files) == 2


def test_list_files_empty_project(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    exp = ProjectExporter(project_root=root)
    assert exp.list_files() == []


def test_estimate_size_matches_manifest(tmp_path):
    root = _make_project(tmp_path)
    exp = ProjectExporter(project_root=root)
    m = exp.scan_project()
    assert exp.estimate_size() == m.total_size
    assert exp.estimate_size() > 0


# ═══════════════════════════════════════════════════════════════════════
# 8. export
# ═══════════════════════════════════════════════════════════════════════


def test_export_creates_zip(tmp_path):
    root = _make_project(tmp_path)
    exp = ProjectExporter(project_root=root)
    out = tmp_path / "out" / "my-game.zip"
    result = exp.export(out, name="my-game", engine_version="0.1.0")
    assert out.exists()
    assert result.archive_path == out.resolve()
    assert result.file_count == 4
    assert result.total_size > 0


def test_export_zip_structure(tmp_path):
    """zip 内含 project.json + chapters/ + resources/。"""
    root = _make_project(tmp_path)
    exp = ProjectExporter(project_root=root)
    out = tmp_path / "proj.zip"
    exp.export(out, name="my-game")
    with zipfile.ZipFile(out, "r") as zf:
        names = zf.namelist()
    assert MANIFEST_FILENAME in names
    assert any(n.startswith(f"{DEFAULT_CHAPTERS_ROOT}/") for n in names)
    assert any(n.startswith(f"{DEFAULT_RESOURCES_ROOT}/") for n in names)


def test_export_manifest_in_zip(tmp_path):
    """zip 内 project.json 是合法 manifest。"""
    root = _make_project(tmp_path)
    exp = ProjectExporter(project_root=root)
    out = tmp_path / "proj.zip"
    exp.export(out, name="my-game", engine_version="0.1.0")
    with zipfile.ZipFile(out, "r") as zf:
        data = json.loads(zf.read(MANIFEST_FILENAME).decode("utf-8"))
    m = ExportManifest.from_dict(data)
    assert m.name == "my-game"
    assert m.engine_version == "0.1.0"
    assert len(m.chapters) == 2
    assert len(m.resources) == 2


def test_export_without_resources(tmp_path):
    """include_resources=False → 只打包章节 + 清单。"""
    root = _make_project(tmp_path)
    exp = ProjectExporter(project_root=root)
    out = tmp_path / "proj.zip"
    result = exp.export(out, name="my-game", include_resources=False)
    with zipfile.ZipFile(out, "r") as zf:
        names = zf.namelist()
    assert MANIFEST_FILENAME in names
    assert any(n.startswith(f"{DEFAULT_CHAPTERS_ROOT}/") for n in names)
    # 不应含 resources/
    assert not any(n.startswith(f"{DEFAULT_RESOURCES_ROOT}/") for n in names)
    # 但 manifest 里 resources 字段仍有内容（清单不裁剪，只裁剪打包）
    assert len(result.manifest.resources) == 2


def test_export_creates_parent_dir(tmp_path):
    """output_path 父目录不存在 → 自动创建。"""
    root = _make_project(tmp_path)
    exp = ProjectExporter(project_root=root)
    out = tmp_path / "deep" / "nested" / "out" / "proj.zip"
    exp.export(out, name="my-game")
    assert out.exists()


def test_export_rejects_invalid_project(tmp_path):
    """校验失败 → 抛 ValueError，不产出 zip。"""
    root = tmp_path / "proj"
    root.mkdir()  # 无 chapters/
    exp = ProjectExporter(project_root=root)
    out = tmp_path / "proj.zip"
    with pytest.raises(ValueError, match="validation failed"):
        exp.export(out)
    assert not out.exists()


def test_export_rejects_empty_chapters(tmp_path):
    """chapters/ 存在但空 → 抛 ValueError。"""
    root = tmp_path / "proj"
    (root / DEFAULT_CHAPTERS_ROOT).mkdir(parents=True)
    exp = ProjectExporter(project_root=root)
    with pytest.raises(ValueError):
        exp.export(tmp_path / "out.zip")


def test_export_result_dataclass(tmp_path):
    """ExportResult 含正确字段。"""
    root = _make_project(tmp_path)
    exp = ProjectExporter(project_root=root)
    result = exp.export(tmp_path / "proj.zip", name="my-game")
    assert isinstance(result, ExportResult)
    assert isinstance(result.archive_path, Path)
    assert isinstance(result.manifest, ExportManifest)


# ═══════════════════════════════════════════════════════════════════════
# 9. extract_project（round-trip + 安全）
# ═══════════════════════════════════════════════════════════════════════


def test_extract_round_trip(tmp_path):
    """export → extract round-trip：恢复章节 + 资源 + 清单。"""
    root = _make_project(tmp_path)
    exp = ProjectExporter(project_root=root)
    archive = tmp_path / "proj.zip"
    result = exp.export(archive, name="my-game", engine_version="0.1.0")

    dest = tmp_path / "restored"
    manifest = ProjectExporter.extract_project(archive, dest)

    assert manifest.name == "my-game"
    assert manifest.engine_version == "0.1.0"
    assert len(manifest.chapters) == 2
    assert len(manifest.resources) == 2
    # 文件实际解压
    assert (dest / MANIFEST_FILENAME).exists()
    assert (dest / DEFAULT_CHAPTERS_ROOT / "chapter01.md").exists()
    assert (dest / DEFAULT_CHAPTERS_ROOT / "chapter02.md").exists()
    assert (dest / DEFAULT_RESOURCES_ROOT / "audio" / "rain.mp3").exists()
    assert (dest / DEFAULT_RESOURCES_ROOT / "images" / "forest.png").exists()


def test_extract_creates_dest_dir(tmp_path):
    """dest_dir 不存在 → 自动创建。"""
    root = _make_project(tmp_path)
    exp = ProjectExporter(project_root=root)
    archive = tmp_path / "proj.zip"
    exp.export(archive)
    dest = tmp_path / "fresh" / "new"
    ProjectExporter.extract_project(archive, dest)
    assert dest.exists()


def test_extract_rejects_missing_archive(tmp_path):
    with pytest.raises(FileNotFoundError):
        ProjectExporter.extract_project(tmp_path / "nope.zip", tmp_path / "out")


def test_extract_rejects_missing_manifest(tmp_path):
    """zip 无 project.json → 抛 ValueError。"""
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("chapters/c1.md", "content")
    with pytest.raises(ValueError, match="manifest"):
        ProjectExporter.extract_project(archive, tmp_path / "out")


def test_extract_rejects_existing_file_without_overwrite(tmp_path):
    """dest 已存在同名文件且 overwrite=False → 抛错。"""
    root = _make_project(tmp_path)
    exp = ProjectExporter(project_root=root)
    archive = tmp_path / "proj.zip"
    exp.export(archive)
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / MANIFEST_FILENAME).write_text("placeholder")
    with pytest.raises(ValueError, match="already exists"):
        ProjectExporter.extract_project(archive, dest, overwrite=False)


def test_extract_overwrite_replaces_existing(tmp_path):
    """overwrite=True → 覆盖已存在文件。"""
    root = _make_project(tmp_path)
    exp = ProjectExporter(project_root=root)
    archive = tmp_path / "proj.zip"
    exp.export(archive)
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / MANIFEST_FILENAME).write_text("placeholder")
    # 不抛错
    ProjectExporter.extract_project(archive, dest, overwrite=True)
    # 内容已被覆盖（不是 "placeholder"）
    content = (dest / MANIFEST_FILENAME).read_text(encoding="utf-8")
    assert "placeholder" not in content
    assert "version" in content


def test_extract_rejects_zip_slip(tmp_path):
    """arcname 含 .. 穿越 → 拒绝（zip-slip 防护）。"""
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr(MANIFEST_FILENAME, json.dumps({
            "version": 1, "name": "x", "created_at": "t",
            "chapters": [], "resources": [],
            "total_size": 0, "file_count": 0,
        }))
        # 故意构造穿越条目
        zf.writestr("../escape.txt", "evil")
    dest = tmp_path / "out"
    with pytest.raises(ValueError, match="escape"):
        ProjectExporter.extract_project(archive, dest)


def test_extract_returns_manifest_from_archive(tmp_path):
    """extract 返回的 manifest 与 archive 内清单一致。"""
    root = _make_project(tmp_path)
    exp = ProjectExporter(project_root=root)
    archive = tmp_path / "proj.zip"
    expected = exp.export(archive, name="my-game")
    dest = tmp_path / "out"
    actual = ProjectExporter.extract_project(archive, dest)
    assert actual.name == expected.manifest.name
    assert actual.file_count == expected.manifest.file_count
    assert actual.total_size == expected.manifest.total_size


# ═══════════════════════════════════════════════════════════════════════
# 10. read_manifest（不解压）
# ═══════════════════════════════════════════════════════════════════════


def test_read_manifest_no_extract(tmp_path):
    """read_manifest 读清单不解压文件。"""
    root = _make_project(tmp_path)
    exp = ProjectExporter(project_root=root)
    archive = tmp_path / "proj.zip"
    exp.export(archive, name="my-game", engine_version="0.1.0")
    dest = tmp_path / "out"
    dest.mkdir()
    m = ProjectExporter.read_manifest(archive)
    assert m.name == "my-game"
    assert m.engine_version == "0.1.0"
    assert len(m.chapters) == 2
    # dest 仍空（未解压）
    assert list(dest.iterdir()) == []


def test_read_manifest_rejects_missing_archive(tmp_path):
    with pytest.raises(FileNotFoundError):
        ProjectExporter.read_manifest(tmp_path / "nope.zip")


def test_read_manifest_rejects_missing_manifest(tmp_path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("chapters/c1.md", "x")
    with pytest.raises(ValueError, match="manifest"):
        ProjectExporter.read_manifest(archive)


def test_read_manifest_rejects_future_version(tmp_path):
    """清单 version 高于当前 → 拒绝（前向保护）。"""
    archive = tmp_path / "future.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr(MANIFEST_FILENAME, json.dumps({
            "version": MANIFEST_VERSION + 1,
            "name": "future",
        }))
    with pytest.raises(ValueError, match="不支持"):
        ProjectExporter.read_manifest(archive)


# ═══════════════════════════════════════════════════════════════════════
# 11. 大小 / 文件数上限
# ═══════════════════════════════════════════════════════════════════════


def test_validate_rejects_too_many_files(tmp_path, monkeypatch):
    """文件数 > MAX_FILE_COUNT → 校验失败。"""
    root = _make_project(tmp_path)
    exp = ProjectExporter(project_root=root)
    # 把上限改小（临时）
    import editor.project_exporter as mod
    monkeypatch.setattr(mod, "MAX_FILE_COUNT", 2)
    issues = exp.validate_project()
    assert any("too many files" in i for i in issues)


def test_validate_rejects_too_large_project(tmp_path, monkeypatch):
    """总大小 > MAX_PROJECT_SIZE → 校验失败。"""
    root = _make_project(tmp_path)
    exp = ProjectExporter(project_root=root)
    import editor.project_exporter as mod
    monkeypatch.setattr(mod, "MAX_PROJECT_SIZE", 10)  # 比实际小
    issues = exp.validate_project()
    assert any("too large" in i for i in issues)


def test_export_rejects_too_many_files(tmp_path, monkeypatch):
    """export 在校验阶段拒绝超文件数。"""
    root = _make_project(tmp_path)
    exp = ProjectExporter(project_root=root)
    import editor.project_exporter as mod
    monkeypatch.setattr(mod, "MAX_FILE_COUNT", 2)
    with pytest.raises(ValueError, match="too many files"):
        exp.export(tmp_path / "out.zip")


# ═══════════════════════════════════════════════════════════════════════
# 12. 集成：与 ChapterManagerModel / ResourceManager 协同
# ═══════════════════════════════════════════════════════════════════════


def test_export_after_chapter_creation(tmp_path):
    """通过 ChapterManagerModel 创建章节后再导出 → 包含新章节。"""
    root = tmp_path / "proj"
    root.mkdir()
    from editor.chapter_manager_model import ChapterManagerModel
    cm = ChapterManagerModel(chapters_root=root / DEFAULT_CHAPTERS_ROOT)
    cm.create_chapter("intro")
    cm.create_chapter("scene1")
    exp = ProjectExporter(project_root=root)
    m = exp.scan_project()
    names = sorted(c["name"] for c in m.chapters)
    assert names == ["intro", "scene1"]


def test_round_trip_preserves_chapter_content(tmp_path):
    """export → extract 章节内容一致。"""
    root = tmp_path / "proj"
    root.mkdir()
    custom_content = """```neon
id:start
next: scene1
node start
自定义内容。
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
    _make_chapter(root, "intro", custom_content)
    exp = ProjectExporter(project_root=root)
    archive = tmp_path / "proj.zip"
    exp.export(archive, name="my-game")
    dest = tmp_path / "out"
    ProjectExporter.extract_project(archive, dest)
    restored = (dest / DEFAULT_CHAPTERS_ROOT / "intro.md").read_text(encoding="utf-8")
    assert restored == custom_content


def test_round_trip_preserves_resource_bytes(tmp_path):
    """export → extract 资源字节一致。"""
    root = _make_project(tmp_path)
    exp = ProjectExporter(project_root=root)
    archive = tmp_path / "proj.zip"
    exp.export(archive, name="my-game")
    dest = tmp_path / "out"
    ProjectExporter.extract_project(archive, dest)
    original = (root / DEFAULT_RESOURCES_ROOT / "audio" / "rain.mp3").read_bytes()
    restored = (dest / DEFAULT_RESOURCES_ROOT / "audio" / "rain.mp3").read_bytes()
    assert original == restored


def test_full_workflow_scan_export_read_extract(tmp_path):
    """完整工作流：scan → export → read_manifest → extract → 二次 scan。"""
    root = _make_project(tmp_path)
    exp = ProjectExporter(project_root=root)
    # 1. scan
    m1 = exp.scan_project(name="my-game", engine_version="0.1.0")
    assert m1.file_count == 4
    # 2. export
    archive = tmp_path / "proj.zip"
    exp.export(archive, name="my-game", engine_version="0.1.0")
    # 3. read_manifest（不解压）
    m2 = ProjectExporter.read_manifest(archive)
    assert m2.name == "my-game"
    # 4. extract 到新位置
    dest = tmp_path / "restored"
    m3 = ProjectExporter.extract_project(archive, dest)
    assert m3.file_count == 4
    # 5. 二次 scan 验证恢复后的项目
    exp2 = ProjectExporter(project_root=dest)
    m4 = exp2.scan_project()
    assert m4.file_count == 4
    assert len(m4.chapters) == 2
    assert len(m4.resources) == 2
