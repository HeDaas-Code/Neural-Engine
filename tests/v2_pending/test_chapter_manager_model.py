"""v4-05 · ChapterManagerModel 章节管理器模型测试（#113）。

验证 issue #113 验收点：
- validate_chapter_name：名字安全校验（防穿越/非法字符/长度）
- validate_chapter_file：P0-S1 风格四闸门（symlink/越界/.md/大小）
- ChapterManagerModel：扫描/索引/查询/创建/删除/重命名/复制/读写
- ChapterEntry：frozen+slots dataclass
- DslSync 集成：scan 时解析块数
"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")

from editor.chapter_manager_model import (
    ChapterManagerModel, ChapterEntry,
    validate_chapter_name, validate_chapter_file,
    DEFAULT_CHAPTERS_ROOT, CHAPTER_EXTENSION, CHAPTER_TEMPLATE,
    MAX_CHAPTER_SIZE,
)


# ═══════════════════════════════════════════════════════════════════════
# 辅助：在 tmp_path 下建章节目录
# ═══════════════════════════════════════════════════════════════════════


def _make_chapters(tmp_path: Path) -> Path:
    """在 tmp_path/chapters 下建测试章节结构。"""
    root = tmp_path / "chapters"
    root.mkdir()
    (root / "chapter01.md").write_text(
        "```neon\nid:start\nnext: c1\nnode start\nA\nnode end\n```\n\n"
        "```neon\nid:c1\nid:end\nnode start\nB\nnode end\n```\n",
        encoding="utf-8",
    )
    (root / "chapter02.md").write_text(
        "```neon\nid:start\nnode start\nC\nnode end\n```\n",
        encoding="utf-8",
    )
    (root / "readme.txt").write_text("not a chapter")  # 非 .md
    return root


# ═══════════════════════════════════════════════════════════════════════
# 1. validate_chapter_name
# ═══════════════════════════════════════════════════════════════════════


def test_validate_name_ok():
    assert validate_chapter_name("chapter01") == "chapter01"
    assert validate_chapter_name("intro") == "intro"
    assert validate_chapter_name("ch_01") == "ch_01"
    assert validate_chapter_name("ch-01") == "ch-01"
    assert validate_chapter_name("a") == "a"


def test_validate_name_empty():
    with pytest.raises(ValueError, match="empty"):
        validate_chapter_name("")


def test_validate_name_too_long():
    with pytest.raises(ValueError, match="too long"):
        validate_chapter_name("a" * 65)


def test_validate_name_path_traversal():
    with pytest.raises(ValueError, match="invalid"):
        validate_chapter_name("../etc/passwd")
    with pytest.raises(ValueError, match="invalid"):
        validate_chapter_name("a/b")


def test_validate_name_special_chars():
    with pytest.raises(ValueError, match="invalid"):
        validate_chapter_name("chapter:01")
    with pytest.raises(ValueError, match="invalid"):
        validate_chapter_name("chapter*01")
    with pytest.raises(ValueError, match="invalid"):
        validate_chapter_name("中文")  # 非字母数字


def test_validate_name_start_with_special():
    with pytest.raises(ValueError, match="invalid"):
        validate_chapter_name("_chapter")
    with pytest.raises(ValueError, match="invalid"):
        validate_chapter_name("-chapter")


# ═══════════════════════════════════════════════════════════════════════
# 2. validate_chapter_file
# ═══════════════════════════════════════════════════════════════════════


def test_validate_file_ok(tmp_path):
    root = _make_chapters(tmp_path)
    p = root / "chapter01.md"
    result = validate_chapter_file(p, root)
    assert result == p.resolve()


def test_validate_file_rejects_symlink(tmp_path):
    root = _make_chapters(tmp_path)
    target = root / "chapter01.md"
    link = root / "link.md"
    os.symlink(target, link)
    with pytest.raises(ValueError, match="symlink"):
        validate_chapter_file(link, root)


def test_validate_file_rejects_traversal(tmp_path):
    root = _make_chapters(tmp_path)
    evil = root / ".." / ".." / "etc" / "passwd"
    with pytest.raises(ValueError, match="not under"):
        validate_chapter_file(evil, root)


def test_validate_file_rejects_bad_ext(tmp_path):
    root = _make_chapters(tmp_path)
    p = root / "readme.txt"
    with pytest.raises(ValueError, match="extension"):
        validate_chapter_file(p, root)


def test_validate_file_rejects_oversized(tmp_path):
    root = tmp_path / "chapters"
    root.mkdir()
    big = root / "big.md"
    big.write_bytes(b"x" * (MAX_CHAPTER_SIZE + 1))
    with pytest.raises(ValueError, match="too large"):
        validate_chapter_file(big, root)


# ═══════════════════════════════════════════════════════════════════════
# 3. ChapterManagerModel 扫描 / 索引
# ═══════════════════════════════════════════════════════════════════════


def test_cm_scan_indexes_chapters(tmp_path):
    """scan 索引所有 .md 章节（跳过非 .md）。"""
    root = _make_chapters(tmp_path)
    cm = ChapterManagerModel(chapters_root=root)
    count = cm.scan()
    assert count == 2  # chapter01 + chapter02（readme.txt 跳过）
    names = cm.list_names()
    assert "chapter01" in names
    assert "chapter02" in names


def test_cm_scan_empty_root(tmp_path):
    """空章节根 → scan 返回 0。"""
    root = tmp_path / "empty_chapters"
    cm = ChapterManagerModel(chapters_root=root)
    assert cm.scan() == 0
    assert cm.list_chapters() == []


def test_cm_auto_creates_root(tmp_path):
    """章节根不存在时自动创建。"""
    root = tmp_path / "new_chapters"
    cm = ChapterManagerModel(chapters_root=root)
    assert root.exists()
    assert root.is_dir()


def test_cm_scan_parses_block_count(tmp_path):
    """scan 解析每个章节的 block_count。"""
    root = _make_chapters(tmp_path)
    cm = ChapterManagerModel(chapters_root=root)
    cm.scan()
    e1 = cm.find("chapter01")
    e2 = cm.find("chapter02")
    assert e1 is not None and e2 is not None
    assert e1.block_count == 2  # 2 个 neon 块
    assert e2.block_count == 1  # 1 个 neon 块


def test_cm_scan_skips_symlink(tmp_path):
    """扫描跳过 symlink。"""
    root = _make_chapters(tmp_path)
    target = root / "chapter01.md"
    link = root / "link.md"
    os.symlink(target, link)
    cm = ChapterManagerModel(chapters_root=root)
    cm.scan()
    assert cm.find("link") is None
    assert cm.find("chapter01") is not None


def test_cm_scan_recursive(tmp_path):
    """递归扫描子目录。"""
    root = tmp_path / "chapters"
    root.mkdir()
    (root / "act1").mkdir()
    (root / "act1" / "scene1.md").write_text(
        "```neon\nid:start\nnode start\nA\nnode end\n```\n", encoding="utf-8"
    )
    cm = ChapterManagerModel(chapters_root=root)
    cm.scan()
    assert cm.find("scene1") is not None


# ═══════════════════════════════════════════════════════════════════════
# 4. ChapterManagerModel 查询
# ═══════════════════════════════════════════════════════════════════════


def test_cm_find(tmp_path):
    root = _make_chapters(tmp_path)
    cm = ChapterManagerModel(chapters_root=root)
    cm.scan()
    entry = cm.find("chapter01")
    assert entry is not None
    assert entry.name == "chapter01"
    assert entry.filename == "chapter01.md"
    assert entry.size > 0
    assert isinstance(entry.mtime, datetime)


def test_cm_find_nonexistent(tmp_path):
    root = _make_chapters(tmp_path)
    cm = ChapterManagerModel(chapters_root=root)
    cm.scan()
    assert cm.find("nope") is None


def test_cm_has_chapter(tmp_path):
    root = _make_chapters(tmp_path)
    cm = ChapterManagerModel(chapters_root=root)
    cm.scan()
    assert cm.has_chapter("chapter01") is True
    assert cm.has_chapter("nope") is False


def test_cm_get_path(tmp_path):
    root = _make_chapters(tmp_path)
    cm = ChapterManagerModel(chapters_root=root)
    cm.scan()
    p = cm.get_path("chapter01")
    assert p is not None
    assert p.exists()
    assert p.is_absolute()
    assert p.suffix == CHAPTER_EXTENSION


def test_cm_list_sorted(tmp_path):
    """list_chapters 按 name 排序。"""
    root = _make_chapters(tmp_path)
    cm = ChapterManagerModel(chapters_root=root)
    cm.scan()
    entries = cm.list_chapters()
    names = [e.name for e in entries]
    assert names == sorted(names)


# ═══════════════════════════════════════════════════════════════════════
# 5. ChapterManagerModel 创建 / 删除 / 重命名
# ═══════════════════════════════════════════════════════════════════════


def test_cm_create_from_template(tmp_path):
    """create_chapter 从模板创建。"""
    root = tmp_path / "chapters"
    cm = ChapterManagerModel(chapters_root=root)
    path = cm.create_chapter("new_chapter")
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "id:start" in content
    assert "node start" in content
    assert cm.has_chapter("new_chapter")


def test_cm_create_with_custom_content(tmp_path):
    """create_chapter 用自定义内容。"""
    root = tmp_path / "chapters"
    cm = ChapterManagerModel(chapters_root=root)
    cm.create_chapter("custom", content="custom content")
    assert cm.read_chapter("custom") == "custom content"


def test_cm_create_invalid_name(tmp_path):
    """create_chapter 名字非法 → ValueError。"""
    root = tmp_path / "chapters"
    cm = ChapterManagerModel(chapters_root=root)
    with pytest.raises(ValueError, match="invalid"):
        cm.create_chapter("../evil")


def test_cm_create_duplicate(tmp_path):
    """create_chapter 已存在 → ValueError。"""
    root = _make_chapters(tmp_path)
    cm = ChapterManagerModel(chapters_root=root)
    cm.scan()
    with pytest.raises(ValueError, match="already exists"):
        cm.create_chapter("chapter01")


def test_cm_delete(tmp_path):
    """delete_chapter 删除文件 + 刷新索引。"""
    root = _make_chapters(tmp_path)
    cm = ChapterManagerModel(chapters_root=root)
    cm.scan()
    assert cm.delete_chapter("chapter01") is True
    assert not cm.has_chapter("chapter01")
    assert not (root / "chapter01.md").exists()


def test_cm_delete_nonexistent(tmp_path):
    """delete_chapter 不存在 → False。"""
    root = _make_chapters(tmp_path)
    cm = ChapterManagerModel(chapters_root=root)
    cm.scan()
    assert cm.delete_chapter("nope") is False


def test_cm_rename(tmp_path):
    """rename_chapter 重命名 + 刷新索引。"""
    root = _make_chapters(tmp_path)
    cm = ChapterManagerModel(chapters_root=root)
    cm.scan()
    new_path = cm.rename_chapter("chapter01", "intro")
    assert new_path.exists()
    assert cm.has_chapter("intro")
    assert not cm.has_chapter("chapter01")
    assert not (root / "chapter01.md").exists()


def test_cm_rename_same_name_noop(tmp_path):
    """rename 同名 → no-op，不抛错。"""
    root = _make_chapters(tmp_path)
    cm = ChapterManagerModel(chapters_root=root)
    cm.scan()
    path = cm.rename_chapter("chapter01", "chapter01")
    assert cm.has_chapter("chapter01")


def test_cm_rename_nonexistent_src(tmp_path):
    """rename 源不存在 → ValueError。"""
    root = _make_chapters(tmp_path)
    cm = ChapterManagerModel(chapters_root=root)
    cm.scan()
    with pytest.raises(ValueError, match="not found"):
        cm.rename_chapter("nope", "new")


def test_cm_rename_target_exists(tmp_path):
    """rename 目标已存在 → ValueError。"""
    root = _make_chapters(tmp_path)
    cm = ChapterManagerModel(chapters_root=root)
    cm.scan()
    with pytest.raises(ValueError, match="already exists"):
        cm.rename_chapter("chapter01", "chapter02")


def test_cm_rename_invalid_target(tmp_path):
    """rename 目标名字非法 → ValueError。"""
    root = _make_chapters(tmp_path)
    cm = ChapterManagerModel(chapters_root=root)
    cm.scan()
    with pytest.raises(ValueError, match="invalid"):
        cm.rename_chapter("chapter01", "../evil")


# ═══════════════════════════════════════════════════════════════════════
# 6. ChapterManagerModel 读写 / 复制
# ═══════════════════════════════════════════════════════════════════════


def test_cm_read_chapter(tmp_path):
    root = _make_chapters(tmp_path)
    cm = ChapterManagerModel(chapters_root=root)
    cm.scan()
    content = cm.read_chapter("chapter01")
    assert "id:start" in content
    assert "node end" in content


def test_cm_read_nonexistent(tmp_path):
    root = _make_chapters(tmp_path)
    cm = ChapterManagerModel(chapters_root=root)
    cm.scan()
    with pytest.raises(ValueError, match="not found"):
        cm.read_chapter("nope")


def test_cm_write_chapter(tmp_path):
    """write_chapter 覆盖内容 + 刷新索引（block_count 更新）。"""
    root = _make_chapters(tmp_path)
    cm = ChapterManagerModel(chapters_root=root)
    cm.scan()
    old_count = cm.find("chapter01").block_count
    new_content = (
        "```neon\nid:start\nnode start\nnew\nnode end\n```\n"
    )
    cm.write_chapter("chapter01", new_content)
    entry = cm.find("chapter01")
    assert entry.block_count == 1  # 从 2 块变 1 块
    assert cm.read_chapter("chapter01") == new_content


def test_cm_write_nonexistent(tmp_path):
    root = _make_chapters(tmp_path)
    cm = ChapterManagerModel(chapters_root=root)
    cm.scan()
    with pytest.raises(ValueError, match="not found"):
        cm.write_chapter("nope", "content")


def test_cm_duplicate(tmp_path):
    """duplicate_chapter 复制章节。"""
    root = _make_chapters(tmp_path)
    cm = ChapterManagerModel(chapters_root=root)
    cm.scan()
    cm.duplicate_chapter("chapter01", "copy01")
    assert cm.has_chapter("copy01")
    assert cm.read_chapter("copy01") == cm.read_chapter("chapter01")


def test_cm_duplicate_nonexistent_src(tmp_path):
    root = _make_chapters(tmp_path)
    cm = ChapterManagerModel(chapters_root=root)
    cm.scan()
    with pytest.raises(ValueError, match="not found"):
        cm.duplicate_chapter("nope", "copy")


def test_cm_duplicate_target_exists(tmp_path):
    root = _make_chapters(tmp_path)
    cm = ChapterManagerModel(chapters_root=root)
    cm.scan()
    with pytest.raises(ValueError, match="already exists"):
        cm.duplicate_chapter("chapter01", "chapter02")


# ═══════════════════════════════════════════════════════════════════════
# 7. ChapterManagerModel 刷新 / 统计
# ═══════════════════════════════════════════════════════════════════════


def test_cm_refresh_picks_up_new(tmp_path):
    """refresh 后新文件被索引。"""
    root = _make_chapters(tmp_path)
    cm = ChapterManagerModel(chapters_root=root)
    cm.scan()
    assert cm.count == 2
    (root / "chapter03.md").write_text(
        "```neon\nid:start\nnode start\nD\nnode end\n```\n", encoding="utf-8"
    )
    cm.refresh()
    assert cm.count == 3
    assert cm.has_chapter("chapter03")


def test_cm_refresh_drops_deleted(tmp_path):
    """refresh 后已删文件从索引移除。"""
    root = _make_chapters(tmp_path)
    cm = ChapterManagerModel(chapters_root=root)
    cm.scan()
    (root / "chapter01.md").unlink()
    cm.refresh()
    assert not cm.has_chapter("chapter01")


def test_cm_count(tmp_path):
    root = _make_chapters(tmp_path)
    cm = ChapterManagerModel(chapters_root=root)
    assert cm.count == 0
    cm.scan()
    assert cm.count == 2


def test_cm_total_size(tmp_path):
    root = _make_chapters(tmp_path)
    cm = ChapterManagerModel(chapters_root=root)
    cm.scan()
    assert cm.total_size() > 0


def test_cm_total_blocks(tmp_path):
    root = _make_chapters(tmp_path)
    cm = ChapterManagerModel(chapters_root=root)
    cm.scan()
    # chapter01 (2 blocks) + chapter02 (1 block) = 3
    assert cm.total_blocks() == 3


# ═══════════════════════════════════════════════════════════════════════
# 8. ChapterEntry dataclass
# ═══════════════════════════════════════════════════════════════════════


def test_entry_frozen():
    entry = ChapterEntry(
        name="x", filename="x.md", relative_path="x.md",
        size=100, mtime=datetime.now(), block_count=1,
    )
    with pytest.raises(Exception):
        entry.name = "y"  # type: ignore


def test_entry_slots():
    entry = ChapterEntry(
        name="x", filename="x.md", relative_path="x.md",
        size=100, mtime=datetime.now(), block_count=1,
    )
    assert not hasattr(entry, "__dict__")


# ═══════════════════════════════════════════════════════════════════════
# 9. 常量 / 模板
# ═══════════════════════════════════════════════════════════════════════


def test_default_chapters_root():
    assert DEFAULT_CHAPTERS_ROOT == "chapters"


def test_chapter_extension():
    assert CHAPTER_EXTENSION == ".md"


def test_template_has_neon_block():
    """模板含合法 neon 块。"""
    assert "```neon" in CHAPTER_TEMPLATE
    assert "id:start" in CHAPTER_TEMPLATE
    assert "node start" in CHAPTER_TEMPLATE
    assert "node end" in CHAPTER_TEMPLATE


def test_template_parseable():
    """模板能被 parse_source 解析（合法 neon）。"""
    from editor.dsl_sync import parse_source
    story = parse_source(CHAPTER_TEMPLATE)
    assert len(story.blocks) >= 1


def test_max_chapter_size():
    assert MAX_CHAPTER_SIZE == 1_000_000


# ═══════════════════════════════════════════════════════════════════════
# 10. 模块导入
# ═══════════════════════════════════════════════════════════════════════


def test_chapter_manager_model_module_exports():
    """chapter_manager_model 公开 API 齐全。"""
    from editor import chapter_manager_model as cm
    for name in ("ChapterManagerModel", "ChapterEntry",
                 "validate_chapter_name", "validate_chapter_file",
                 "DEFAULT_CHAPTERS_ROOT", "CHAPTER_EXTENSION",
                 "CHAPTER_TEMPLATE", "MAX_CHAPTER_SIZE"):
        assert hasattr(cm, name)
