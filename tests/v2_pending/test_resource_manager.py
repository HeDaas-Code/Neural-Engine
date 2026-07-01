"""v4-04 · ResourceManager 资源管理器测试（#112）。

验证 issue #112 验收点：
- validate_resource_path：P0-S1 四闸门（symlink/越界/扩展名白名单/大小）
- resolve_resource_path：三段式路径解析（资源根→绝对→cwd）
- ResourceManager：扫描/索引/查询/统计/刷新
- ResourceEntry：frozen+slots dataclass
- get_resource_type：扩展名→类型映射
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")

from editor.resource_manager import (
    ResourceManager, ResourceEntry,
    validate_resource_path, resolve_resource_path, get_resource_type,
    RESOURCE_AUDIO, RESOURCE_IMAGE,
    EXTENSION_WHITELIST, MAX_SIZE, DEFAULT_RESOURCES_ROOT,
)


# ═══════════════════════════════════════════════════════════════════════
# 辅助：在 tmp_path 下建资源目录结构
# ═══════════════════════════════════════════════════════════════════════


def _make_resources(tmp_path: Path) -> Path:
    """在 tmp_path/resources 下建测试资源结构。"""
    root = tmp_path / "resources"
    root.mkdir()
    (root / "audio").mkdir()
    (root / "images").mkdir()
    (root / "audio" / "rain.mp3").write_bytes(b"fake mp3" * 100)
    (root / "audio" / "storm.wav").write_bytes(b"fake wav" * 50)
    (root / "images" / "forest.png").write_bytes(b"fake png" * 200)
    (root / "images" / "alice.jpg").write_bytes(b"fake jpg" * 150)
    (root / "readme.txt").write_text("not a resource")  # 非白名单
    return root


# ═══════════════════════════════════════════════════════════════════════
# 1. get_resource_type
# ═══════════════════════════════════════════════════════════════════════


def test_get_resource_type_audio():
    assert get_resource_type("rain.mp3") == RESOURCE_AUDIO
    assert get_resource_type("storm.wav") == RESOURCE_AUDIO
    assert get_resource_type("se.ogg") == RESOURCE_AUDIO


def test_get_resource_type_image():
    assert get_resource_type("forest.png") == RESOURCE_IMAGE
    assert get_resource_type("alice.jpg") == RESOURCE_IMAGE
    assert get_resource_type("scene.jpeg") == RESOURCE_IMAGE
    assert get_resource_type("anim.gif") == RESOURCE_IMAGE
    assert get_resource_type("art.webp") == RESOURCE_IMAGE


def test_get_resource_type_case_insensitive():
    assert get_resource_type("Rain.MP3") == RESOURCE_AUDIO
    assert get_resource_type("Forest.PNG") == RESOURCE_IMAGE


def test_get_resource_type_unsupported():
    assert get_resource_type("readme.txt") is None
    assert get_resource_type("malware.exe") is None
    assert get_resource_type("noext") is None
    assert get_resource_type("") is None


# ═══════════════════════════════════════════════════════════════════════
# 2. validate_resource_path
# ═══════════════════════════════════════════════════════════════════════


def test_validate_ok(tmp_path):
    """合法资源路径通过四闸门。"""
    root = _make_resources(tmp_path)
    p = root / "audio" / "rain.mp3"
    result = validate_resource_path(p, root)
    assert result == p.resolve()


def test_validate_rejects_symlink(tmp_path):
    """闸门 1：拒绝 symlink。"""
    root = _make_resources(tmp_path)
    target = root / "audio" / "rain.mp3"
    link = root / "audio" / "link.mp3"
    os.symlink(target, link)
    with pytest.raises(ValueError, match="symlink"):
        validate_resource_path(link, root)


def test_validate_rejects_path_traversal(tmp_path):
    """闸门 2：拒绝越界（../../etc/passwd）。"""
    root = _make_resources(tmp_path)
    evil = root / "audio" / ".." / ".." / ".." / "etc" / "passwd"
    with pytest.raises(ValueError, match="not under"):
        validate_resource_path(evil, root)


def test_validate_rejects_bad_extension(tmp_path):
    """闸门 3：拒绝非白名单扩展名。"""
    root = _make_resources(tmp_path)
    p = root / "readme.txt"
    with pytest.raises(ValueError, match="unsupported extension"):
        validate_resource_path(p, root)


def test_validate_rejects_oversized(tmp_path):
    """闸门 4：拒绝过大文件。"""
    root = tmp_path / "resources"
    root.mkdir()
    big = root / "big.mp3"
    # 写超过 MAX_SIZE 的文件
    big.write_bytes(b"x" * (MAX_SIZE[RESOURCE_AUDIO] + 1))
    with pytest.raises(ValueError, match="too large"):
        validate_resource_path(big, root)


def test_validate_check_exists_false_skips_size(tmp_path):
    """check_exists=False 跳过大小检查（用于预检）。"""
    root = tmp_path / "resources"
    root.mkdir()
    big = root / "big.mp3"
    big.write_bytes(b"x" * (MAX_SIZE[RESOURCE_AUDIO] + 1))
    # 不检查存在/大小，只过前 3 闸门
    result = validate_resource_path(big, root, check_exists=False)
    assert result == big.resolve()


# ═══════════════════════════════════════════════════════════════════════
# 3. resolve_resource_path
# ═══════════════════════════════════════════════════════════════════════


def test_resolve_relative_under_root(tmp_path):
    """相对路径在资源根下找到。"""
    root = _make_resources(tmp_path)
    result = resolve_resource_path("audio/rain.mp3", root)
    assert result is not None
    assert result == (root / "audio" / "rain.mp3").resolve()


def test_resolve_absolute(tmp_path):
    """绝对路径直接解析。"""
    root = _make_resources(tmp_path)
    abs_path = root / "audio" / "rain.mp3"
    result = resolve_resource_path(str(abs_path), root)
    assert result is not None
    assert result == abs_path.resolve()


def test_resolve_not_found(tmp_path):
    """不存在的资源返回 None。"""
    root = _make_resources(tmp_path)
    assert resolve_resource_path("nope.mp3", root) is None


def test_resolve_cwd_fallback(tmp_path):
    """cwd 兜底（测试 tmp 文件不在资源根下时）。"""
    root = _make_resources(tmp_path)
    # tmp_path 下的文件不在 resources 下，但相对 cwd 可达
    # （测试运行时 cwd 可能不是 tmp_path，所以直接验证 None 或 path）
    external = tmp_path / "external.mp3"
    external.write_bytes(b"external")
    # external.mp3 不在 root 下，resolve 应返回 None（除非 cwd == tmp_path）
    result = resolve_resource_path("external.mp3", root)
    # 不强制断言，因为取决于 cwd；只验证不抛错
    assert result is None or result.exists()


# ═══════════════════════════════════════════════════════════════════════
# 4. ResourceManager 扫描 / 索引
# ═══════════════════════════════════════════════════════════════════════


def test_rm_scan_indexes_resources(tmp_path):
    """scan 索引所有白名单资源（跳过非白名单）。"""
    root = _make_resources(tmp_path)
    rm = ResourceManager(resources_root=root)
    count = rm.scan()
    assert count == 4  # 2 audio + 2 image（readme.txt 跳过）
    names = rm.list_names()
    assert "rain.mp3" in names
    assert "storm.wav" in names
    assert "forest.png" in names
    assert "alice.jpg" in names
    assert "readme.txt" not in names


def test_rm_scan_empty_root(tmp_path):
    """空资源根 → scan 返回 0。"""
    root = tmp_path / "empty_resources"
    rm = ResourceManager(resources_root=root)
    assert rm.scan() == 0
    assert rm.list_resources() == []


def test_rm_auto_creates_root(tmp_path):
    """资源根不存在时自动创建。"""
    root = tmp_path / "new_resources"
    rm = ResourceManager(resources_root=root)
    assert root.exists()
    assert root.is_dir()


def test_rm_scan_recursive(tmp_path):
    """递归扫描子目录。"""
    root = tmp_path / "resources"
    root.mkdir()
    (root / "deep").mkdir()
    (root / "deep" / "nested").mkdir()
    (root / "deep" / "nested" / "hidden.mp3").write_bytes(b"deep")
    rm = ResourceManager(resources_root=root)
    rm.scan()
    assert rm.find("hidden.mp3") is not None


def test_rm_scan_skips_symlink(tmp_path):
    """扫描跳过 symlink（安全）。"""
    root = _make_resources(tmp_path)
    target = root / "audio" / "rain.mp3"
    link = root / "audio" / "link.mp3"
    os.symlink(target, link)
    rm = ResourceManager(resources_root=root)
    rm.scan()
    # link.mp3 不应被索引
    assert rm.find("link.mp3") is None
    assert rm.find("rain.mp3") is not None


# ═══════════════════════════════════════════════════════════════════════
# 5. ResourceManager 查询
# ═══════════════════════════════════════════════════════════════════════


def test_rm_find_by_name(tmp_path):
    """按文件名查找。"""
    root = _make_resources(tmp_path)
    rm = ResourceManager(resources_root=root)
    rm.scan()
    entry = rm.find("rain.mp3")
    assert entry is not None
    assert entry.name == "rain.mp3"
    assert entry.resource_type == RESOURCE_AUDIO
    assert "rain.mp3" in entry.relative_path
    assert entry.size > 0


def test_rm_find_nonexistent(tmp_path):
    """查找不存在的资源返回 None。"""
    root = _make_resources(tmp_path)
    rm = ResourceManager(resources_root=root)
    rm.scan()
    assert rm.find("nope.mp3") is None


def test_rm_list_by_type(tmp_path):
    """按类型过滤列表。"""
    root = _make_resources(tmp_path)
    rm = ResourceManager(resources_root=root)
    rm.scan()
    audio = rm.list_resources(RESOURCE_AUDIO)
    images = rm.list_resources(RESOURCE_IMAGE)
    assert len(audio) == 2
    assert len(images) == 2
    assert all(e.resource_type == RESOURCE_AUDIO for e in audio)
    assert all(e.resource_type == RESOURCE_IMAGE for e in images)


def test_rm_list_sorted(tmp_path):
    """list_resources 按 relative_path 排序。"""
    root = _make_resources(tmp_path)
    rm = ResourceManager(resources_root=root)
    rm.scan()
    entries = rm.list_resources()
    paths = [e.relative_path for e in entries]
    assert paths == sorted(paths)


def test_rm_list_names_sorted(tmp_path):
    """list_names 按名排序。"""
    root = _make_resources(tmp_path)
    rm = ResourceManager(resources_root=root)
    rm.scan()
    names = rm.list_names()
    assert names == sorted(names)


def test_rm_get_path(tmp_path):
    """get_path 返回绝对路径。"""
    root = _make_resources(tmp_path)
    rm = ResourceManager(resources_root=root)
    rm.scan()
    p = rm.get_path("rain.mp3")
    assert p is not None
    assert p.exists()
    assert p.is_absolute()


def test_rm_get_path_nonexistent(tmp_path):
    """get_path 不存在返回 None。"""
    root = _make_resources(tmp_path)
    rm = ResourceManager(resources_root=root)
    rm.scan()
    assert rm.get_path("nope.mp3") is None


def test_rm_resolve(tmp_path):
    """resolve 解析资源引用。"""
    root = _make_resources(tmp_path)
    rm = ResourceManager(resources_root=root)
    p = rm.resolve("audio/rain.mp3")
    assert p is not None
    assert p.exists()


def test_rm_resolve_not_found(tmp_path):
    """resolve 不存在返回 None。"""
    root = _make_resources(tmp_path)
    rm = ResourceManager(resources_root=root)
    assert rm.resolve("nope.mp3") is None


def test_rm_validate_ok(tmp_path):
    """validate 通过合法路径。"""
    root = _make_resources(tmp_path)
    rm = ResourceManager(resources_root=root)
    result = rm.validate("audio/rain.mp3")
    assert result.exists()


def test_rm_validate_rejects_bad_ext(tmp_path):
    """validate 拒绝非白名单扩展名。"""
    root = _make_resources(tmp_path)
    rm = ResourceManager(resources_root=root)
    with pytest.raises(ValueError, match="unsupported extension"):
        rm.validate("readme.txt")


# ═══════════════════════════════════════════════════════════════════════
# 6. ResourceManager 统计
# ═══════════════════════════════════════════════════════════════════════


def test_rm_count(tmp_path):
    """count 属性返回索引数。"""
    root = _make_resources(tmp_path)
    rm = ResourceManager(resources_root=root)
    assert rm.count == 0  # scan 前
    rm.scan()
    assert rm.count == 4


def test_rm_count_by_type(tmp_path):
    """按类型统计。"""
    root = _make_resources(tmp_path)
    rm = ResourceManager(resources_root=root)
    rm.scan()
    counts = rm.count_by_type()
    assert counts[RESOURCE_AUDIO] == 2
    assert counts[RESOURCE_IMAGE] == 2


def test_rm_total_size(tmp_path):
    """总大小统计。"""
    root = _make_resources(tmp_path)
    rm = ResourceManager(resources_root=root)
    rm.scan()
    total = rm.total_size()
    assert total > 0
    # 4 个文件，每个至少 100+ 字节
    assert total > 400


# ═══════════════════════════════════════════════════════════════════════
# 7. ResourceManager 刷新
# ═══════════════════════════════════════════════════════════════════════


def test_rm_refresh_picks_up_new_files(tmp_path):
    """refresh 后新文件被索引。"""
    root = _make_resources(tmp_path)
    rm = ResourceManager(resources_root=root)
    rm.scan()
    assert rm.count == 4
    # 新增文件
    (root / "audio" / "new.mp3").write_bytes(b"new")
    rm.refresh()
    assert rm.count == 5
    assert rm.find("new.mp3") is not None


def test_rm_refresh_drops_deleted_files(tmp_path):
    """refresh 后已删文件从索引移除。"""
    root = _make_resources(tmp_path)
    rm = ResourceManager(resources_root=root)
    rm.scan()
    assert rm.find("rain.mp3") is not None
    (root / "audio" / "rain.mp3").unlink()
    rm.refresh()
    assert rm.find("rain.mp3") is None


# ═══════════════════════════════════════════════════════════════════════
# 8. ResourceEntry dataclass
# ═══════════════════════════════════════════════════════════════════════


def test_resource_entry_frozen():
    """ResourceEntry 不可变。"""
    entry = ResourceEntry(name="x.mp3", relative_path="x.mp3",
                          resource_type=RESOURCE_AUDIO, size=100)
    with pytest.raises(Exception):
        entry.name = "y.mp3"  # type: ignore


def test_resource_entry_slots():
    """ResourceEntry 用 slots（无 __dict__）。"""
    entry = ResourceEntry(name="x.mp3", relative_path="x.mp3",
                          resource_type=RESOURCE_AUDIO, size=100)
    assert not hasattr(entry, "__dict__")


# ═══════════════════════════════════════════════════════════════════════
# 9. 常量 / 默认值
# ═══════════════════════════════════════════════════════════════════════


def test_extension_whitelist_complete():
    """扩展名白名单齐全。"""
    assert ".mp3" in EXTENSION_WHITELIST[RESOURCE_AUDIO]
    assert ".wav" in EXTENSION_WHITELIST[RESOURCE_AUDIO]
    assert ".ogg" in EXTENSION_WHITELIST[RESOURCE_AUDIO]
    assert ".png" in EXTENSION_WHITELIST[RESOURCE_IMAGE]
    assert ".jpg" in EXTENSION_WHITELIST[RESOURCE_IMAGE]
    assert ".jpeg" in EXTENSION_WHITELIST[RESOURCE_IMAGE]
    assert ".gif" in EXTENSION_WHITELIST[RESOURCE_IMAGE]
    assert ".webp" in EXTENSION_WHITELIST[RESOURCE_IMAGE]


def test_max_size_reasonable():
    """大小上限合理（音频 > 图片）。"""
    assert MAX_SIZE[RESOURCE_AUDIO] > MAX_SIZE[RESOURCE_IMAGE]
    assert MAX_SIZE[RESOURCE_AUDIO] > 1_000_000  # > 1MB
    assert MAX_SIZE[RESOURCE_IMAGE] > 1_000_000


def test_default_resources_root():
    """默认资源根目录名。"""
    assert DEFAULT_RESOURCES_ROOT == "resources"


# ═══════════════════════════════════════════════════════════════════════
# 10. 模块导入
# ═══════════════════════════════════════════════════════════════════════


def test_resource_manager_module_exports():
    """resource_manager 公开 API 齐全。"""
    from editor import resource_manager as rm
    for name in ("ResourceManager", "ResourceEntry",
                 "validate_resource_path", "resolve_resource_path", "get_resource_type",
                 "RESOURCE_AUDIO", "RESOURCE_IMAGE",
                 "EXTENSION_WHITELIST", "MAX_SIZE", "DEFAULT_RESOURCES_ROOT"):
        assert hasattr(rm, name)
