"""ChapterManagerModel —— v4-05 章节管理器模型（#113）。

职责：
- 扫描 chapters/ 目录，索引所有 .md 章节文件
- 列出章节元数据（名/大小/mtime/块数/节点数）
- 创建新章节（从模板）、删除章节、重命名章节
- 章节名安全校验（防路径穿越 / 非法字符）
- 与 DslSync 集成：解析章节获取块数/节点数统计

设计：
- 纯 Python（无 PyQt6 依赖），便于测试 + 与视图层解耦
- 仿 ResourceManager 的 scan/list/validate 模式
- 仿 SaveManager 的文件操作闭环（创建/删除/重命名）
- 章节名校验复用 P0-S1 思路（防 symlink/越界），扩展名固定 .md

视图层集成点（后续 issue 落地 QWidget）：
- ChapterListView 从 ChapterManagerModel.list_chapters() 读列表渲染
- 双击章节 → 用 DslSync 加载到 NodeGraphView 编辑
- 右键菜单 → 新建/删除/重命名
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════════════


DEFAULT_CHAPTERS_ROOT = "chapters"
CHAPTER_EXTENSION = ".md"

# 章节名安全正则：必须以字母数字开头，后续可含下划线/连字符
# 不允许：../ / \ : * ? " < > | 等路径分隔符和特殊字符
_CHAPTER_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-]*$")

# 新章节模板（最小可用 neon 块）
CHAPTER_TEMPLATE = """```neon
id:start
next: scene1
node start
新章节开始。
node end
```

```neon
id:scene1
id:end
node start
场景内容。
node end
```
"""

# 最大章节文件大小（字节，1MB，与 main.MAX_CHAPTER_SIZE 一致）
MAX_CHAPTER_SIZE = 1_000_000


# ═══════════════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class ChapterEntry:
    """章节索引条目。

    Attributes:
        name: 章节名（不含扩展名，如 "chapter01"）。
        filename: 文件名（含扩展名，如 "chapter01.md"）。
        relative_path: 相对章节根的路径（如 "chapter01.md"）。
        size: 文件大小（字节）。
        mtime: 最后修改时间（datetime）。
        block_count: 块数（neon 围栏块数，scan 时解析；解析失败为 0）。
    """
    name: str
    filename: str
    relative_path: str
    size: int
    mtime: datetime
    block_count: int


# ═══════════════════════════════════════════════════════════════════════
# 章节名校验
# ═══════════════════════════════════════════════════════════════════════


def validate_chapter_name(name: str) -> str:
    """章节名安全校验（单一校验源）。

    规则：
    - 仅允许字母数字 + 下划线 + 连字符
    - 必须以字母或数字开头（不能以 _ 或 - 开头）
    - 长度 1-64 字符
    - 不允许路径分隔符 / 特殊字符（防穿越）

    Args:
        name: 章节名（不含扩展名）。

    Returns:
        校验通过的章节名（原样返回）。

    Raises:
        ValueError: 名字非法，含具体原因。
    """
    if not name:
        raise ValueError("chapter name is empty")
    if len(name) > 64:
        raise ValueError(f"chapter name too long: {len(name)} > 64")
    if not _CHAPTER_NAME_RE.match(name):
        raise ValueError(
            f"invalid chapter name {name!r}: only alphanumeric, underscore, hyphen allowed; "
            f"must start with alphanumeric"
        )
    return name


def validate_chapter_file(path, chapters_root) -> Path:
    """章节文件路径安全校验（P0-S1 风格）。

    闸门：
    1. 拒绝 symlink
    2. resolve 后必须在 chapters_root 下
    3. 扩展名必须 .md
    4. 文件大小不超过 MAX_CHAPTER_SIZE（文件存在时检查）

    Returns:
        校验通过后的绝对 Path（resolved）。
    """
    p = Path(path)
    if p.is_symlink():
        raise ValueError(f"chapter path {p!s} is a symlink, rejected")
    resolved = p.resolve()
    root_resolved = Path(chapters_root).resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        raise ValueError(
            f"chapter path {p!s} is not under chapters_root {root_resolved!s}"
        ) from None
    if p.suffix != CHAPTER_EXTENSION:
        raise ValueError(f"chapter path {p!s} must have {CHAPTER_EXTENSION} extension")
    if p.exists():
        size = p.stat().st_size
        if size > MAX_CHAPTER_SIZE:
            raise ValueError(
                f"chapter file {p!s} too large: {size} bytes (max {MAX_CHAPTER_SIZE})"
            )
    return resolved


# ═══════════════════════════════════════════════════════════════════════
# ChapterManagerModel
# ═══════════════════════════════════════════════════════════════════════


class ChapterManagerModel:
    """章节管理器模型：扫描/索引/创建/删除/重命名章节。

    用法：
        cm = ChapterManagerModel()                        # 默认 chapters/
        cm = ChapterManagerModel(chapters_root="story")   # 自定义根
        cm.scan()                                          # 扫描建索引
        entries = cm.list_chapters()                       # 列出所有
        cm.create_chapter("chapter02")                     # 从模板创建
        cm.delete_chapter("chapter01")                     # 删除
        cm.rename_chapter("chapter01", "intro")            # 重命名
        entry = cm.find("chapter01")                       # 按名查找
        content = cm.read_chapter("chapter01")             # 读内容
        cm.write_chapter("chapter01", new_content)         # 写内容

    约定：
    - 章节根不存在时自动创建
    - 扫描仅索引 .md 文件（递归子目录）
    - 所有写操作（create/delete/rename/write）自动刷新索引
    - 所有查询返回副本（防外部修改）
    """

    def __init__(self, chapters_root=None):
        self._root = Path(chapters_root) if chapters_root else Path(DEFAULT_CHAPTERS_ROOT)
        self._entries: list[ChapterEntry] = []
        self._index: dict[str, ChapterEntry] = {}  # name → entry
        self._root.mkdir(parents=True, exist_ok=True)

    # ─── 属性 ──────────────────────────────────────────────────────

    @property
    def chapters_root(self) -> Path:
        return self._root

    @property
    def count(self) -> int:
        return len(self._entries)

    # ─── 扫描 / 索引 ──────────────────────────────────────────────

    def scan(self) -> int:
        """扫描章节根，建立索引。返回索引条目数。

        - 递归扫描所有子目录
        - 仅索引 .md 文件
        - 跳过 symlink（安全）
        - 跳过过大文件（记 warning）
        - 解析每个章节获取 block_count（解析失败记 warning，block_count=0）
        """
        self._entries = []
        self._index = {}
        if not self._root.exists():
            return 0
        for p in sorted(self._root.rglob(f"*{CHAPTER_EXTENSION}")):
            if not p.is_file():
                continue
            if p.is_symlink():
                logger.warning("skip symlink chapter: %s", p)
                continue
            size = p.stat().st_size
            if size > MAX_CHAPTER_SIZE:
                logger.warning("skip oversized chapter (%d > %d): %s",
                               size, MAX_CHAPTER_SIZE, p)
                continue
            name = p.stem
            rel = p.relative_to(self._root).as_posix()
            mtime = datetime.fromtimestamp(p.stat().st_mtime)
            block_count = self._count_blocks(p)
            entry = ChapterEntry(
                name=name,
                filename=p.name,
                relative_path=rel,
                size=size,
                mtime=mtime,
                block_count=block_count,
            )
            self._entries.append(entry)
            self._index[name] = entry
        return len(self._entries)

    def refresh(self) -> int:
        """重新扫描（scan 的别名）。"""
        return self.scan()

    def _count_blocks(self, path: Path) -> int:
        """解析章节文件，返回 neon 块数。解析失败返回 0。"""
        try:
            from editor.dsl_sync import parse_source
            text = path.read_text(encoding="utf-8")
            story = parse_source(text)
            return len(story.blocks)
        except Exception as e:
            logger.warning("failed to parse chapter %s: %s", path, e)
            return 0

    # ─── 查询 ──────────────────────────────────────────────────────

    def list_chapters(self) -> list[ChapterEntry]:
        """列出章节条目（按 name 排序的副本）。"""
        return sorted(self._entries, key=lambda e: e.name)

    def list_names(self) -> list[str]:
        """列出章节名（按名排序的副本）。"""
        return sorted(e.name for e in self._entries)

    def find(self, name: str) -> Optional[ChapterEntry]:
        """按名查找章节条目。不存在返回 None。"""
        return self._index.get(name)

    def has_chapter(self, name: str) -> bool:
        """查询章节是否存在。"""
        return name in self._index

    def get_path(self, name: str) -> Optional[Path]:
        """取章节文件的绝对路径。不存在返回 None。"""
        entry = self.find(name)
        if entry is None:
            return None
        return self._root / entry.relative_path

    # ─── 文件操作 ──────────────────────────────────────────────────

    def create_chapter(self, name: str, content: Optional[str] = None) -> Path:
        """从模板创建新章节。

        Args:
            name: 章节名（不含扩展名）。
            content: 可选自定义内容；None 则用 CHAPTER_TEMPLATE。

        Returns:
            新章节文件的绝对路径。

        Raises:
            ValueError: 名字非法 / 章节已存在。
        """
        validate_chapter_name(name)
        if self.has_chapter(name):
            raise ValueError(f"chapter {name!r} already exists")
        path = self._root / f"{name}{CHAPTER_EXTENSION}"
        text = content if content is not None else CHAPTER_TEMPLATE
        path.write_text(text, encoding="utf-8")
        self.refresh()
        return path

    def delete_chapter(self, name: str) -> bool:
        """删除章节。不存在返回 False。"""
        path = self.get_path(name)
        if path is None or not path.exists():
            return False
        path.unlink()
        self.refresh()
        return True

    def rename_chapter(self, old_name: str, new_name: str) -> Path:
        """重命名章节。

        Raises:
            ValueError: 原章节不存在 / 新名字非法 / 新名字已存在。
        """
        if not self.has_chapter(old_name):
            raise ValueError(f"chapter {old_name!r} not found")
        validate_chapter_name(new_name)
        if old_name == new_name:
            return self.get_path(old_name)  # no-op
        if self.has_chapter(new_name):
            raise ValueError(f"chapter {new_name!r} already exists")
        old_path = self.get_path(old_name)
        new_path = self._root / f"{new_name}{CHAPTER_EXTENSION}"
        old_path.rename(new_path)
        self.refresh()
        return new_path

    def read_chapter(self, name: str) -> str:
        """读章节内容。不存在抛 ValueError。"""
        path = self.get_path(name)
        if path is None or not path.exists():
            raise ValueError(f"chapter {name!r} not found")
        return path.read_text(encoding="utf-8")

    def write_chapter(self, name: str, content: str) -> Path:
        """写章节内容（覆盖）。不存在抛 ValueError。"""
        if not self.has_chapter(name):
            raise ValueError(f"chapter {name!r} not found")
        path = self.get_path(name)
        path.write_text(content, encoding="utf-8")
        self.refresh()
        return path

    def duplicate_chapter(self, src_name: str, dst_name: str) -> Path:
        """复制章节。

        Raises:
            ValueError: 源不存在 / 目标名字非法 / 目标已存在。
        """
        content = self.read_chapter(src_name)  # 抛 ValueError if not found
        return self.create_chapter(dst_name, content=content)

    # ─── 统计 ──────────────────────────────────────────────────────

    def total_size(self) -> int:
        """所有章节的总大小（字节）。"""
        return sum(e.size for e in self._entries)

    def total_blocks(self) -> int:
        """所有章节的总块数。"""
        return sum(e.block_count for e in self._entries)


__all__ = [
    "ChapterManagerModel", "ChapterEntry",
    "validate_chapter_name", "validate_chapter_file",
    "DEFAULT_CHAPTERS_ROOT", "CHAPTER_EXTENSION", "CHAPTER_TEMPLATE",
    "MAX_CHAPTER_SIZE",
]
