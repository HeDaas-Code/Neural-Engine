"""ResourceManager —— v4-04 资源管理器（#112）。

职责：
- `ResourceManager`：扫描/索引/校验项目资源文件（音频 + 图片）
- `validate_resource_path`：P0-S1 风格四闸门安全校验（symlink/越界/扩展名白名单/大小）
- `resolve_resource_path`：统一路径解析源（替代 AudioManager/ImageRenderer 各自重复的逻辑）
- 资源类型分类：AUDIO（.mp3/.wav/.ogg）/ IMAGE（.png/.jpg/.jpeg/.gif/.webp）

设计：
- 纯 Python（无 PyQt6 依赖），便于测试 + 与视图层解耦
- 仿 SaveManager 的 list/scan/validate 模式（save.py 的 list_slots/list_slots_with_meta）
- 安全校验复用 P0-S1 四闸门模式（main.py:validate_chapter_path），但扩展名改为白名单
- 路径解析三段式（绝对→资源根→cwd）与 AudioManager._resolve_path 一致，但收紧为"必须在资源根下"

资源根策略：
- 默认 resources_root = "resources"（独立目录，不与 chapters/ 混）
- 支持子目录：resources/audio/, resources/images/（不强制，扫描时全递归）
- 资源根不存在时自动创建（仿 SaveManager.__init__ 的 mkdir 模式）

不变量：
- validate_resource_path 是唯一校验源——禁止在其他模块复制本函数
- resolve_resource_path 是唯一解析源——AudioManager/ImageRenderer 应改为调本函数（后续 issue）
- list_resources 返回防御性拷贝，外部修改不影响内部索引
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# 资源类型常量
# ═══════════════════════════════════════════════════════════════════════


RESOURCE_AUDIO = "audio"
RESOURCE_IMAGE = "image"

# 扩展名白名单（按类型）
EXTENSION_WHITELIST: dict[str, set[str]] = {
    RESOURCE_AUDIO: {".mp3", ".wav", ".ogg"},
    RESOURCE_IMAGE: {".png", ".jpg", ".jpeg", ".gif", ".webp"},
}

# 扩展名 → 类型 反查表
_EXT_TO_TYPE: dict[str, str] = {}
for _rtype, _exts in EXTENSION_WHITELIST.items():
    for _ext in _exts:
        _EXT_TO_TYPE[_ext] = _rtype

# 文件大小上限（字节，按类型）
MAX_SIZE: dict[str, int] = {
    RESOURCE_AUDIO: 50_000_000,   # 50MB
    RESOURCE_IMAGE: 10_000_000,   # 10MB
}

# 默认资源根目录名
DEFAULT_RESOURCES_ROOT = "resources"


# ═══════════════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class ResourceEntry:
    """资源索引条目。

    Attributes:
        name: 资源文件名（含扩展名，如 "rain.mp3"）。
        relative_path: 相对资源根的路径（如 "audio/rain.mp3"）。
        resource_type: RESOURCE_AUDIO / RESOURCE_IMAGE。
        size: 文件大小（字节）。
    """
    name: str
    relative_path: str
    resource_type: str
    size: int


# ═══════════════════════════════════════════════════════════════════════
# 安全校验 + 路径解析
# ═══════════════════════════════════════════════════════════════════════


def get_resource_type(filename: str) -> Optional[str]:
    """根据扩展名判定资源类型。非白名单返回 None。"""
    ext = Path(filename).suffix.lower()
    return _EXT_TO_TYPE.get(ext)


def validate_resource_path(
    resource_path,
    resources_root,
    *,
    check_exists: bool = True,
) -> Path:
    """P0-S1 风格四闸门资源路径校验（单一校验源）。

    Args:
        resource_path: 资源文件路径（str / Path，相对或绝对）。
        resources_root: 资源根目录（str / Path）。
        check_exists: 是否检查文件存在 + 大小（False 则只做前 3 闸门）。

    Returns:
        校验通过后的绝对 Path（resolved）。

    Raises:
        ValueError: 任一闸门失败，含具体原因（symlink / under / ext / large|size）。
    """
    p = Path(resource_path)
    # 闸门 1：拒绝 symlink
    if p.is_symlink():
        raise ValueError(
            f"resource path {p!s} is a symlink, rejected by security gate"
        )
    # 闸门 2：resolve 后必须在资源根下（防 ../../etc/passwd 穿越）
    resolved = p.resolve()
    root_resolved = Path(resources_root).resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        raise ValueError(
            f"resource path {p!s} (resolved {resolved!s}) is not under "
            f"resources_root {root_resolved!s}"
        ) from None
    # 闸门 3：扩展名必须在白名单内
    ext = p.suffix.lower()
    rtype = _EXT_TO_TYPE.get(ext)
    if rtype is None:
        raise ValueError(
            f"resource path {p!s} has unsupported extension {ext!r}; "
            f"allowed: {sorted(_EXT_TO_TYPE.keys())}"
        )
    # 闸门 4：文件大小（仅 check_exists=True 时）
    if check_exists and p.exists():
        size = p.stat().st_size
        max_size = MAX_SIZE[rtype]
        if size > max_size:
            raise ValueError(
                f"resource file {p!s} too large: {size} bytes "
                f"(max {max_size} bytes for {rtype})"
            )
    return resolved


def resolve_resource_path(source: str, resources_root) -> Optional[Path]:
    """统一资源路径解析（三段式：资源根下 → 绝对 → cwd）。

    替代 AudioManager._resolve_path / ImageRenderer._resolve_path 的重复逻辑。
    不做安全校验（调用方自行调 validate_resource_path）；只负责"找到文件"。

    Args:
        source: 资源引用字符串（如 "rain.mp3" / "audio/rain.mp3" / 绝对路径）。
        resources_root: 资源根目录。

    Returns:
        解析到的绝对 Path（存在则返回），否则 None。
    """
    p = Path(source)
    # 1. 绝对路径直接用
    if p.is_absolute():
        return p if p.exists() else None
    # 2. 相对资源根
    candidate = Path(resources_root) / source
    resolved = candidate.resolve()
    if resolved.exists():
        return resolved
    # 3. 相对 cwd（兼容测试 tmp 文件）
    if p.exists():
        return p.resolve()
    return None


# ═══════════════════════════════════════════════════════════════════════
# ResourceManager
# ═══════════════════════════════════════════════════════════════════════


class ResourceManager:
    """资源管理器：扫描/索引/校验项目资源文件。

    用法：
        rm = ResourceManager()                          # 默认 resources/
        rm = ResourceManager(resources_root="assets")    # 自定义根
        rm.scan()                                        # 扫描建索引
        entries = rm.list_resources()                    # 列出所有
        audio = rm.list_resources(RESOURCE_AUDIO)        # 按类型过滤
        entry = rm.find("rain.mp3")                      # 按名查找
        path = rm.resolve("rain.mp3")                    # 解析为绝对路径
        rm.refresh()                                     # 重新扫描

    约定：
    - 资源根不存在时自动创建（空目录，scan 返回空列表）
    - 扫描递归子目录（resources/audio/xxx.mp3 也会被索引）
    - 索引是快照（scan 时建立）；文件系统变更需手动 refresh
    - 所有查询返回副本（防外部修改）
    """

    def __init__(self, resources_root=None):
        self._root = Path(resources_root) if resources_root else Path(DEFAULT_RESOURCES_ROOT)
        self._entries: list[ResourceEntry] = []
        self._index: dict[str, ResourceEntry] = {}  # name → entry（按名查找）
        # 自动创建根目录（仿 SaveManager）
        self._root.mkdir(parents=True, exist_ok=True)

    # ─── 属性 ──────────────────────────────────────────────────────

    @property
    def resources_root(self) -> Path:
        return self._root

    @property
    def count(self) -> int:
        return len(self._entries)

    # ─── 扫描 / 索引 ──────────────────────────────────────────────

    def scan(self) -> int:
        """扫描资源根目录，建立索引。返回索引条目数。

        - 递归扫描所有子目录
        - 仅索引白名单扩展名（.mp3/.wav/.ogg/.png/.jpg/...）
        - 跳过 symlink（安全）
        - 跳过过大文件（记 warning，不抛错）
        """
        self._entries = []
        self._index = {}
        if not self._root.exists():
            return 0
        for p in self._root.rglob("*"):
            if not p.is_file():
                continue
            if p.is_symlink():
                logger.warning("skip symlink resource: %s", p)
                continue
            rtype = get_resource_type(p.name)
            if rtype is None:
                continue  # 非白名单扩展名，跳过
            size = p.stat().st_size
            if size > MAX_SIZE[rtype]:
                logger.warning("skip oversized resource (%d > %d): %s",
                               size, MAX_SIZE[rtype], p)
                continue
            rel = p.relative_to(self._root).as_posix()
            entry = ResourceEntry(
                name=p.name,
                relative_path=rel,
                resource_type=rtype,
                size=size,
            )
            self._entries.append(entry)
            self._index[p.name] = entry
        return len(self._entries)

    def refresh(self) -> int:
        """重新扫描（scan 的别名，语义更清晰）。"""
        return self.scan()

    # ─── 查询 ──────────────────────────────────────────────────────

    def list_resources(self, resource_type: Optional[str] = None) -> list[ResourceEntry]:
        """列出资源条目（按 relative_path 排序的副本）。

        Args:
            resource_type: 可选类型过滤（RESOURCE_AUDIO / RESOURCE_IMAGE）。
        """
        entries = [e for e in self._entries if resource_type is None or e.resource_type == resource_type]
        return sorted(entries, key=lambda e: e.relative_path)

    def list_names(self, resource_type: Optional[str] = None) -> list[str]:
        """列出资源文件名（按名排序的副本）。"""
        return sorted(e.name for e in self.list_resources(resource_type))

    def find(self, name: str) -> Optional[ResourceEntry]:
        """按文件名查找资源条目。不存在返回 None。"""
        entry = self._index.get(name)
        return entry  # frozen dataclass，无需拷贝

    def resolve(self, source: str) -> Optional[Path]:
        """解析资源引用为绝对路径。不存在返回 None。"""
        return resolve_resource_path(source, self._root)

    def validate(self, source: str) -> Path:
        """校验资源引用（P0-S1 四闸门）。失败抛 ValueError。"""
        p = Path(source)
        full = self._root / p if not p.is_absolute() else p
        return validate_resource_path(full, self._root)

    def get_path(self, name: str) -> Optional[Path]:
        """取资源文件的绝对路径。不存在返回 None。"""
        entry = self.find(name)
        if entry is None:
            return None
        return self._root / entry.relative_path

    # ─── 统计 ──────────────────────────────────────────────────────

    def count_by_type(self) -> dict[str, int]:
        """按类型统计资源数量。"""
        counts: dict[str, int] = {RESOURCE_AUDIO: 0, RESOURCE_IMAGE: 0}
        for e in self._entries:
            counts[e.resource_type] = counts.get(e.resource_type, 0) + 1
        return counts

    def total_size(self) -> int:
        """所有资源的总大小（字节）。"""
        return sum(e.size for e in self._entries)


__all__ = [
    "ResourceManager", "ResourceEntry",
    "validate_resource_path", "resolve_resource_path", "get_resource_type",
    "RESOURCE_AUDIO", "RESOURCE_IMAGE",
    "EXTENSION_WHITELIST", "MAX_SIZE", "DEFAULT_RESOURCES_ROOT",
]
