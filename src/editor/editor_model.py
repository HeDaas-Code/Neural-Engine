"""EditorModel —— v4-08 编辑器主框架编排器（#116）。

职责：
- 编排编辑器各子模型（ChapterManagerModel / ResourceManager / DslSync /
  DebuggerModel / ProjectExporter），提供高层编辑 API
- 跟踪当前章节状态（名称 / 脏标记 / 源码 / 图模型）
- 预览/调试生命周期管理（懒构造 DebuggerModel）
- 项目导出委托

设计：
- 纯 Python（无 PyQt6 依赖），便于测试 + 与视图层解耦
- 镜像 runtime 层 main.py + pyqt6_main.py 的分层纪律：
  本模块是"编排逻辑"本体；QMainWindow 视图壳（_build_editor_window_class）
  作为薄层叠加，后续 issue 落地
- 仿 DebuggerModel 包装 PreviewController、ProjectExporter 聚合
  ChapterManagerModel + ResourceManager 的"dataclass/闭包 + 委托"模式

不变量：
- 无当前章节时，所有编辑/预览 API 抛 ValueError
- 预览运行中，open_chapter / close_chapter 抛 ValueError（避免状态混乱）
- save_chapter 写入的是 DslSync.source（即上次 update_from_source /
  update_from_graph 后的源码）；用户编辑图后须先 update_from_graph
- 脏标记：open/save 时清零；update_from_source / update_from_graph 时置位
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from editor.chapter_manager_model import (
    ChapterManagerModel, ChapterEntry, DEFAULT_CHAPTERS_ROOT,
)
from editor.resource_manager import (
    ResourceManager, ResourceEntry, DEFAULT_RESOURCES_ROOT,
)
from editor.dsl_sync import DslSync, parse_source
from editor.debugger_model import DebuggerModel
from editor.preview_controller import STATUS_IDLE
from editor.project_exporter import (
    ProjectExporter, ExportResult, DEFAULT_EXPORT_NAME,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# EditorModel
# ═══════════════════════════════════════════════════════════════════════


class EditorModel:
    """编辑器主框架编排器：聚合各编辑器子模型，提供高层编辑 API。

    用法：
        em = EditorModel(project_root="my-game")
        em.list_chapters()                 # 列出项目章节
        em.open_chapter("chapter01")       # 加载 → DslSync → 设当前
        em.update_from_source(new_src)     # 源码→图（标记脏）
        em.save_chapter()                  # 写回磁盘
        em.run_preview()                   # 用当前章节 story 跑预览
        em.export_project("out.zip", name="my-game")
    """

    def __init__(self, project_root=None):
        self._root = Path(project_root) if project_root else Path.cwd()
        self._chapter_mgr = ChapterManagerModel(
            chapters_root=self._root / DEFAULT_CHAPTERS_ROOT
        )
        self._resource_mgr = ResourceManager(
            resources_root=self._root / DEFAULT_RESOURCES_ROOT
        )
        self._exporter = ProjectExporter(project_root=self._root)
        self._current_name: Optional[str] = None
        self._dsl: Optional[DslSync] = None
        self._dirty: bool = False
        self._debugger: Optional[DebuggerModel] = None
        # 初始扫描（让 list_chapters / list_resources 立即可用）
        self.refresh()

    # ─── 项目属性 ──────────────────────────────────────────────────

    @property
    def project_root(self) -> Path:
        return self._root

    @property
    def chapters_root(self) -> Path:
        return self._chapter_mgr.chapters_root

    @property
    def resources_root(self) -> Path:
        return self._resource_mgr.resources_root

    @property
    def chapter_manager(self) -> ChapterManagerModel:
        """暴露底层章节管理器（高级用法 / 测试用）。"""
        return self._chapter_mgr

    @property
    def resource_manager(self) -> ResourceManager:
        """暴露底层资源管理器（高级用法 / 测试用）。"""
        return self._resource_mgr

    @property
    def exporter(self) -> ProjectExporter:
        """暴露底层导出器（高级用法 / 测试用）。"""
        return self._exporter

    # ─── 章节列表（委托 ChapterManagerModel）──────────────────────

    def list_chapters(self) -> list:
        """列出项目章节条目（按名排序）。"""
        return self._chapter_mgr.list_chapters()

    def list_chapter_names(self) -> list:
        """列出章节名（按名排序）。"""
        return self._chapter_mgr.list_names()

    @property
    def chapter_count(self) -> int:
        return self._chapter_mgr.count

    # ─── 资源列表（委托 ResourceManager）──────────────────────────

    def list_resources(self, resource_type: Optional[str] = None) -> list:
        """列出资源条目（可选类型过滤）。"""
        return self._resource_mgr.list_resources(resource_type)

    def list_resource_names(self, resource_type: Optional[str] = None) -> list:
        return self._resource_mgr.list_names(resource_type)

    @property
    def resource_count(self) -> int:
        return self._resource_mgr.count

    # ─── 当前章节编辑 ──────────────────────────────────────────────

    @property
    def current_chapter_name(self) -> Optional[str]:
        return self._current_name

    @property
    def has_current_chapter(self) -> bool:
        return self._dsl is not None and self._current_name is not None

    @property
    def current_source(self) -> Optional[str]:
        """当前章节源码（DslSync.source）。无当前章节返回 None。"""
        return self._dsl.source if self._dsl is not None else None

    @property
    def current_model(self):
        """当前章节的 NodeGraphModel（DslSync.model）。无当前章节返回 None。"""
        return self._dsl.model if self._dsl is not None else None

    @property
    def is_dirty(self) -> bool:
        """是否有未保存变更。"""
        return self._dirty

    def _is_preview_active(self) -> bool:
        """预览是否处于活跃状态（running 或 paused）。"""
        return (
            self._debugger is not None
            and (self._debugger.is_running or self._debugger.is_paused)
        )

    def open_chapter(self, name: str):
        """打开章节：读源码 → DslSync → 设为当前。

        Args:
            name: 章节名（不含扩展名）。

        Returns:
            NodeGraphModel（DslSync 构造后从源码解析的图）。

        Raises:
            ValueError: 章节不存在 / 预览运行中。
        """
        if self._is_preview_active():
            raise ValueError(
                f"cannot open chapter while preview is running "
                f"(status={self._debugger.status!r}); call stop_preview() first"
            )
        if not self._chapter_mgr.has_chapter(name):
            raise ValueError(f"chapter {name!r} not found")
        source = self._chapter_mgr.read_chapter(name)
        self._dsl = DslSync(source=source)
        self._current_name = name
        self._dirty = False
        logger.info("opened chapter %r (%d blocks)",
                    name, len(self._dsl.model.get_nodes()))
        return self._dsl.model

    def save_chapter(self) -> Path:
        """保存当前章节：写 DslSync.source 回磁盘。

        Returns:
            章节文件绝对路径。

        Raises:
            ValueError: 无当前章节。
        """
        self._require_current_chapter("save_chapter")
        assert self._dsl is not None and self._current_name is not None
        path = self._chapter_mgr.write_chapter(self._current_name, self._dsl.source)
        self._dirty = False
        logger.info("saved chapter %r → %s", self._current_name, path)
        return path

    def save_chapter_as(self, new_name: str) -> Path:
        """另存为：用当前源码创建新章节并切换。

        Raises:
            ValueError: 无当前章节 / 新名字非法 / 新名字已存在。
        """
        self._require_current_chapter("save_chapter_as")
        assert self._dsl is not None
        path = self._chapter_mgr.create_chapter(new_name, content=self._dsl.source)
        self._current_name = new_name
        self._dirty = False
        logger.info("save-as chapter → %r (%s)", new_name, path)
        return path

    def close_chapter(self) -> None:
        """关闭当前章节（不保存）。预览运行中抛 ValueError。"""
        if self._is_preview_active():
            raise ValueError(
                f"cannot close chapter while preview is running "
                f"(status={self._debugger.status!r}); call stop_preview() first"
            )
        if self._current_name is not None:
            logger.info("closed chapter %r", self._current_name)
        self._dsl = None
        self._current_name = None
        self._dirty = False

    def reload_chapter(self) -> None:
        """重新从磁盘加载当前章节（丢弃未保存变更）。

        Raises:
            ValueError: 无当前章节。
        """
        self._require_current_chapter("reload_chapter")
        assert self._current_name is not None
        name = self._current_name
        source = self._chapter_mgr.read_chapter(name)
        self._dsl = DslSync(source=source)
        self._dirty = False

    # ─── DSL 双向同步 ─────────────────────────────────────────────

    def update_from_source(self, source: str) -> None:
        """源码 → 图（标记脏）。

        Raises:
            ValueError: 无当前章节。
        """
        self._require_current_chapter("update_from_source")
        assert self._dsl is not None
        self._dsl.update_from_source(source)
        self._dirty = True

    def update_from_graph(self, model) -> None:
        """图 → 源码（标记脏，保留已有块体）。

        Raises:
            ValueError: 无当前章节。
        """
        self._require_current_chapter("update_from_graph")
        assert self._dsl is not None
        self._dsl.update_from_graph(model)
        self._dirty = True

    # ─── 章节管理（委托 ChapterManagerModel）──────────────────────

    def create_chapter(self, name: str) -> Path:
        """新建章节（从模板）。返回新章节路径。"""
        return self._chapter_mgr.create_chapter(name)

    def delete_chapter(self, name: str) -> bool:
        """删除章节。若删的是当前章节，自动关闭当前。"""
        if self._current_name == name:
            self._dsl = None
            self._current_name = None
            self._dirty = False
        return self._chapter_mgr.delete_chapter(name)

    def rename_chapter(self, old_name: str, new_name: str) -> Path:
        """重命名章节。若重命名的是当前章节，更新当前名。"""
        path = self._chapter_mgr.rename_chapter(old_name, new_name)
        if self._current_name == old_name:
            self._current_name = new_name
        return path

    def has_chapter(self, name: str) -> bool:
        return self._chapter_mgr.has_chapter(name)

    # ─── 预览 / 调试 ──────────────────────────────────────────────

    @property
    def debugger(self) -> Optional[DebuggerModel]:
        """当前调试器（无活跃预览时为 None）。"""
        return self._debugger

    @property
    def preview_status(self) -> str:
        """预览状态（无 debugger 时 STATUS_IDLE）。"""
        if self._debugger is None:
            return STATUS_IDLE
        return self._debugger.status

    @property
    def is_preview_running(self) -> bool:
        """预览是否活跃（running 或 paused）。"""
        return self._is_preview_active()

    def run_preview(self, sink=None, *, breakpoints=None) -> bool:
        """用当前章节源码构造 story → 启动预览（DebuggerModel）。

        Args:
            sink: 输入 sink（None 时用 MemoryInputSink）。
            breakpoints: 可选的初始断点列表（在 run() 前注入，避免竞态）。

        Returns:
            True 若启动成功；False 若已有预览在跑。

        Raises:
            ValueError: 无当前章节。
        """
        self._require_current_chapter("run_preview")
        assert self._dsl is not None
        if self._is_preview_active():
            return False
        story = parse_source(self._dsl.source)
        if sink is None:
            from core.engine.executor import MemoryInputSink
            sink = MemoryInputSink()
        self._debugger = DebuggerModel(story=story, sink=sink)
        # 预设断点（在 run() 前注入，确保 worker 启动时即生效）
        if breakpoints:
            for bp in breakpoints:
                self._debugger.add_breakpoint(bp)
        return self._debugger.run()

    def stop_preview(self) -> None:
        """停止预览（若有）。同步等待 worker 退出。"""
        if self._debugger is None:
            return
        self._debugger.stop()
        self._debugger.join()
        self._debugger = None

    # ─── 导出（委托 ProjectExporter）──────────────────────────────

    def export_project(
        self,
        output_path,
        *,
        name: str = DEFAULT_EXPORT_NAME,
        include_resources: bool = True,
        engine_version: str = "",
    ) -> ExportResult:
        """导出项目为 zip 分发包。"""
        return self._exporter.export(
            output_path,
            name=name,
            include_resources=include_resources,
            engine_version=engine_version,
        )

    def validate_project(self) -> list:
        """校验项目（空列表 = 合法）。"""
        return self._exporter.validate_project()

    def scan_project_manifest(self, name: str = DEFAULT_EXPORT_NAME,
                              engine_version: str = ""):
        """扫描项目构建清单（不打包）。"""
        return self._exporter.scan_project(name=name, engine_version=engine_version)

    # ─── 刷新 ──────────────────────────────────────────────────────

    def refresh(self) -> None:
        """重新扫描章节 / 资源索引。"""
        self._chapter_mgr.refresh()
        self._resource_mgr.refresh()

    # ─── 内部 ──────────────────────────────────────────────────────

    def _require_current_chapter(self, op: str) -> None:
        if self._dsl is None or self._current_name is None:
            raise ValueError(
                f"{op}: no chapter open (call open_chapter first)"
            )


__all__ = [
    "EditorModel",
]
