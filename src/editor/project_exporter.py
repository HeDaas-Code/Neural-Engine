"""ProjectExporter —— v4-07 项目导出（#115）。

职责：
- 扫描项目（chapters/ + resources/），构建导出清单（project.json）
- 打包为 zip 分发包（chapters + resources + manifest）
- P0-S1 安全校验：拒绝 symlink / 路径穿越 / 超大文件 / 超多文件
- extract_project：从 zip 导入项目（清单校验 + 路径穿越防护，round-trip）

设计：
- 纯 Python（无 PyQt6 依赖），便于测试 + 与视图层解耦
- 仿 SaveManager / ResourceManager / ChapterManagerModel 的 scan/list/validate 模式
- 聚合 ChapterManagerModel（#113）+ ResourceManager（#112）的 scan 能力，不重复扫描逻辑
- 清单格式遵循 D2 决策（json.dumps ensure_ascii=False indent=2）+ version 字段（仿 GameState）
- zip 结构：project.json（清单）+ chapters/ + resources/（顶层目录）

项目模型：
- 项目 = 含 chapters/ 的目录（resources/ 可选）
- project_root 默认 cwd；chapters_root = project_root/chapters，resources_root = project_root/resources

不变量：
- export 前必须 scan + validate（任一文件失败抛 ValueError，不产出半成品 zip）
- 清单 manifest 是导出的唯一元数据源（含 version/name/chapters/resources/统计）
- extract 拒绝清单 version > 当前支持版本（前向保护，仿 GameState.from_dict）
- extract 拒绝 arcname 含绝对路径 / .. 穿越（zip-slip 防护）
"""
from __future__ import annotations

import json
import logging
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from editor.chapter_manager_model import (
    ChapterManagerModel, ChapterEntry, DEFAULT_CHAPTERS_ROOT,
)
from editor.resource_manager import (
    ResourceManager, ResourceEntry, DEFAULT_RESOURCES_ROOT,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════════════


MANIFEST_FILENAME = "project.json"
MANIFEST_VERSION = 1

# 默认导出名（→ {name}.zip）
DEFAULT_EXPORT_NAME = "project"

# 项目大小 / 文件数上限（防滥用）
MAX_PROJECT_SIZE = 200_000_000   # 200MB
MAX_FILE_COUNT = 5_000


# ═══════════════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class ExportManifest:
    """项目导出清单（序列化为 zip 内 project.json）。

    Attributes:
        version: 清单版本（当前 1；>1 拒绝读取，仿 GameState 前向保护）。
        name: 项目名（导出时指定，默认 "project"）。
        created_at: 导出时间（ISO 8601 字符串）。
        chapters: 章节条目列表（dict: name/filename/relative_path/size/block_count）。
        resources: 资源条目列表（dict: name/relative_path/resource_type/size）。
        total_size: 所有文件总大小（字节）。
        file_count: 文件总数（章节 + 资源）。
        engine_version: 引擎版本标识（可选，默认空串）。
    """
    version: int
    name: str
    created_at: str
    chapters: list
    resources: list
    total_size: int
    file_count: int
    engine_version: str = ""

    def to_dict(self) -> dict:
        """序列化为 dict（D2 决策：ensure_ascii=False 兼容）。"""
        return {
            "version": self.version,
            "name": self.name,
            "created_at": self.created_at,
            "engine_version": self.engine_version,
            "chapters": list(self.chapters),
            "resources": list(self.resources),
            "total_size": self.total_size,
            "file_count": self.file_count,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ExportManifest":
        """从 dict 反序列化（向后兼容 + 前向保护）。

        Raises:
            ValueError: 非 dict / version 不支持（>1）。
        """
        if not isinstance(d, dict):
            raise ValueError(
                f"ExportManifest.from_dict 期望 dict，得到 {type(d).__name__}"
            )
        version = d.get("version", 1)
        if version > MANIFEST_VERSION:
            raise ValueError(
                f"manifest version {version} 不支持（当前仅支持 version<={MANIFEST_VERSION}）"
            )
        return cls(
            version=version,
            name=d.get("name", DEFAULT_EXPORT_NAME),
            created_at=d.get("created_at", ""),
            chapters=list(d.get("chapters", [])),
            resources=list(d.get("resources", [])),
            total_size=int(d.get("total_size", 0)),
            file_count=int(d.get("file_count", 0)),
            engine_version=d.get("engine_version", ""),
        )


@dataclass(frozen=True, slots=True)
class ExportResult:
    """导出结果。

    Attributes:
        archive_path: 生成的 zip 文件绝对路径。
        manifest: 导出清单（同写入 zip 的 project.json）。
        file_count: 打包文件数。
        total_size: 打包文件总大小（字节，不含 zip 元数据）。
    """
    archive_path: Path
    manifest: ExportManifest
    file_count: int
    total_size: int


# ═══════════════════════════════════════════════════════════════════════
# ProjectExporter
# ═══════════════════════════════════════════════════════════════════════


class ProjectExporter:
    """项目导出器：扫描 + 校验 + 打包 chapters/resources 为 zip 分发包。

    用法：
        exp = ProjectExporter(project_root="my-game")
        manifest = exp.scan_project(name="my-game")      # 扫描构建清单
        issues = exp.validate_project()                   # 校验（空=合法）
        result = exp.export("out/my-game.zip", name="my-game")  # 打包
        # 导入：
        ProjectExporter.extract_project("out/my-game.zip", "restored/")

    约定：
    - chapters_root = project_root / "chapters"（必须存在且有 .md 文件才导出章节）
    - resources_root = project_root / "resources"（可选，不存在则跳过资源）
    - 不自动创建项目目录（导出只读已有文件；extract 时创建目标目录）
    """

    def __init__(self, project_root=None):
        self._root = Path(project_root) if project_root else Path.cwd()
        self._chapters_root = self._root / DEFAULT_CHAPTERS_ROOT
        self._resources_root = self._root / DEFAULT_RESOURCES_ROOT

    # ─── 属性 ──────────────────────────────────────────────────────

    @property
    def project_root(self) -> Path:
        return self._root

    @property
    def chapters_root(self) -> Path:
        return self._chapters_root

    @property
    def resources_root(self) -> Path:
        return self._resources_root

    # ─── 扫描 / 清单 ──────────────────────────────────────────────

    def scan_project(self, name: str = DEFAULT_EXPORT_NAME,
                     engine_version: str = "") -> ExportManifest:
        """扫描项目目录，构建导出清单（不打包）。

        Args:
            name: 项目名（写入清单）。
            engine_version: 引擎版本标识（可选）。

        Returns:
            ExportManifest（含章节/资源条目 + 统计）。
        """
        chapters = self._scan_chapters()
        resources = self._scan_resources()
        total_size = (
            sum(c["size"] for c in chapters)
            + sum(r["size"] for r in resources)
        )
        file_count = len(chapters) + len(resources)
        return ExportManifest(
            version=MANIFEST_VERSION,
            name=name,
            created_at=datetime.now().isoformat(timespec="seconds"),
            chapters=chapters,
            resources=resources,
            total_size=total_size,
            file_count=file_count,
            engine_version=engine_version,
        )

    def _scan_chapters(self) -> list:
        """扫描章节，返回条目 dict 列表（按 name 排序）。"""
        if not self._chapters_root.exists():
            return []
        cm = ChapterManagerModel(chapters_root=self._chapters_root)
        cm.scan()
        return [
            {
                "name": e.name,
                "filename": e.filename,
                "relative_path": e.relative_path,
                "size": e.size,
                "block_count": e.block_count,
            }
            for e in cm.list_chapters()
        ]

    def _scan_resources(self) -> list:
        """扫描资源，返回条目 dict 列表（按 relative_path 排序）。"""
        if not self._resources_root.exists():
            return []
        rm = ResourceManager(resources_root=self._resources_root)
        rm.scan()
        return [
            {
                "name": e.name,
                "relative_path": e.relative_path,
                "resource_type": e.resource_type,
                "size": e.size,
            }
            for e in rm.list_resources()
        ]

    # ─── 校验 ──────────────────────────────────────────────────────

    def validate_project(self) -> list:
        """校验项目，返回问题列表（空 = 合法）。

        检查项：
        - chapters_root 存在且有至少 1 个章节
        - 总大小 / 文件数不超上限

        说明：
        - symlink 检查由底层 ChapterManagerModel.scan / ResourceManager.scan
          完成（silently skip，不进入索引）—— 因此本方法不需要再检 symlink。
        - 路径穿越检查由底层 validate_chapter_path / validate_resource_path 保证。
        """
        issues: list[str] = []
        if not self._chapters_root.exists():
            issues.append(f"chapters_root not found: {self._chapters_root}")
        else:
            chapters = self._scan_chapters()
            if not chapters:
                issues.append("no chapters to export (chapters/ is empty)")
        # 总量校验
        manifest = self.scan_project()
        if manifest.total_size > MAX_PROJECT_SIZE:
            issues.append(
                f"project too large: {manifest.total_size} > {MAX_PROJECT_SIZE}"
            )
        if manifest.file_count > MAX_FILE_COUNT:
            issues.append(
                f"too many files: {manifest.file_count} > {MAX_FILE_COUNT}"
            )
        return issues

    # ─── 文件列表 / 估算 ───────────────────────────────────────────

    def list_files(self) -> list:
        """列出将被导出的所有文件路径（绝对路径，排序）。"""
        files: list[Path] = []
        for c in self._scan_chapters():
            files.append((self._chapters_root / c["relative_path"]).resolve())
        for r in self._scan_resources():
            files.append((self._resources_root / r["relative_path"]).resolve())
        return sorted(files)

    def estimate_size(self) -> int:
        """估算导出总大小（字节，= manifest.total_size）。"""
        return self.scan_project().total_size

    # ─── 导出 ──────────────────────────────────────────────────────

    def export(
        self,
        output_path,
        *,
        name: str = DEFAULT_EXPORT_NAME,
        include_resources: bool = True,
        engine_version: str = "",
    ) -> ExportResult:
        """导出项目为 zip 分发包。

        Args:
            output_path: 输出 zip 路径（str / Path）。
            name: 项目名（写入清单）。
            include_resources: 是否打包资源（False 则只打包章节 + 清单）。
            engine_version: 引擎版本标识（可选）。

        Returns:
            ExportResult（含 zip 路径 + 清单 + 统计）。

        Raises:
            ValueError: 项目校验失败 / 无章节 / 超大小上限。
        """
        issues = self.validate_project()
        if issues:
            raise ValueError(
                "project validation failed:\n  - " + "\n  - ".join(issues)
            )

        manifest = self.scan_project(name=name, engine_version=engine_version)
        if not manifest.chapters:
            raise ValueError("no chapters to export")

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            # 1. 写清单
            zf.writestr(
                MANIFEST_FILENAME,
                json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2),
            )
            # 2. 写章节
            for c in manifest.chapters:
                src = self._chapters_root / c["relative_path"]
                arc = f"{DEFAULT_CHAPTERS_ROOT}/{c['relative_path']}"
                zf.write(src, arcname=arc)
            # 3. 写资源（可选）
            if include_resources:
                for r in manifest.resources:
                    src = self._resources_root / r["relative_path"]
                    arc = f"{DEFAULT_RESOURCES_ROOT}/{r['relative_path']}"
                    zf.write(src, arcname=arc)

        return ExportResult(
            archive_path=out.resolve(),
            manifest=manifest,
            file_count=manifest.file_count,
            total_size=manifest.total_size,
        )

    # ─── 导入（extract）────────────────────────────────────────────

    @staticmethod
    def extract_project(
        archive_path,
        dest_dir,
        *,
        overwrite: bool = False,
    ) -> ExportManifest:
        """从 zip 导入项目（清单校验 + zip-slip 防护）。

        Args:
            archive_path: zip 文件路径。
            dest_dir: 目标目录（不存在则创建）。
            overwrite: 是否覆盖已存在文件（False 时遇到已存在文件抛错）。

        Returns:
            解析出的 ExportManifest。

        Raises:
            ValueError: zip 损坏 / 清单缺失或版本不支持 / arcname 穿越 / 已存在且不覆盖。
            FileNotFoundError: zip 不存在。
        """
        archive = Path(archive_path)
        if not archive.exists():
            raise FileNotFoundError(f"archive not found: {archive}")
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        dest_resolved = dest.resolve()

        with zipfile.ZipFile(archive, "r") as zf:
            names = zf.namelist()
            # 1. 找清单
            if MANIFEST_FILENAME not in names:
                raise ValueError(
                    f"manifest {MANIFEST_FILENAME!r} not found in archive"
                )
            manifest = ExportManifest.from_dict(
                json.loads(zf.read(MANIFEST_FILENAME).decode("utf-8"))
            )
            # 2. 校验所有 arcname（zip-slip 防护）+ 解压
            for info in zf.infolist():
                if info.is_dir():
                    continue
                arcname = info.filename
                if arcname == MANIFEST_FILENAME:
                    # 清单写到 dest 根
                    target = dest / MANIFEST_FILENAME
                else:
                    target = dest / arcname
                # zip-slip 防护：resolve 后必须在 dest 下
                target_resolved = target.resolve()
                try:
                    target_resolved.relative_to(dest_resolved)
                except ValueError:
                    raise ValueError(
                        f"archive entry {arcname!r} escapes dest dir "
                        f"(resolved {target_resolved!s} not under {dest_resolved!s})"
                    ) from None
                # 覆盖检查
                if target_resolved.exists() and not overwrite:
                    raise ValueError(
                        f"file already exists (use overwrite=True): {target_resolved}"
                    )
                target_resolved.parent.mkdir(parents=True, exist_ok=True)
                target_resolved.write_bytes(zf.read(arcname))

        return manifest

    # ─── 读清单（不解压）───────────────────────────────────────────

    @staticmethod
    def read_manifest(archive_path) -> ExportManifest:
        """从 zip 读取清单（不解压文件，仅读 project.json）。"""
        archive = Path(archive_path)
        if not archive.exists():
            raise FileNotFoundError(f"archive not found: {archive}")
        with zipfile.ZipFile(archive, "r") as zf:
            if MANIFEST_FILENAME not in zf.namelist():
                raise ValueError(
                    f"manifest {MANIFEST_FILENAME!r} not found in archive"
                )
            return ExportManifest.from_dict(
                json.loads(zf.read(MANIFEST_FILENAME).decode("utf-8"))
            )


__all__ = [
    "ProjectExporter", "ExportManifest", "ExportResult",
    "MANIFEST_FILENAME", "MANIFEST_VERSION",
    "DEFAULT_EXPORT_NAME", "MAX_PROJECT_SIZE", "MAX_FILE_COUNT",
]
