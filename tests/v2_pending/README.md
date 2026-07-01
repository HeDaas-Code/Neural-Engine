# v2-p0 测试（已激活）

这些测试来自 `feature/v2-p0-gui-first` 分支合并，验证 v2-p0 的 protocol/main/executor 扩展
（SaveCmd/LoadCmd/validate_chapter_path/GameState.to_dict 等）。

## 状态：已激活

v2-p0 核心扩展已合并到 main 分支，测试已激活并纳入主测试套件。

## 测试覆盖

### v2-p0 基线（#72 / #81 / #88）

| 测试文件 | 覆盖范围 |
|---------|---------|
| test_chapter_loading.py | 跨章节加载集成（chapter01_route → chapter_route） |
| test_chapter_manager.py | ChapterManager 单元 + 集成测试 |
| test_decorator_hooks.py | @style / @bgm 装饰器钩子注册表 |
| test_decorator_parse.py | 修饰器解析（含 `[...]` 结构化参数） |
| test_executor_save.py | GameState 序列化 + current_block_id 跟踪 |
| test_gui_fallback.py | PyQt6 探测 + CLI 降级（D3 决策） |
| test_load_chapter.py | load_chapter_safe + P0-S1 路径校验 |
| test_pyqt6_e2e.py | PyQt6 端到端（用 fake Qt 模块，不依赖真实 PyQt6） |
| test_pyqt6_main.py | PyQt6 主窗口（用 fake Qt 模块） |
| test_pyqt6_sink.py | PyQt6Sink / PyQt6InputSink（用 fake Qt 模块） |
| test_save.py | SaveManager 存档/读档/列表/删除 |
| test_save_cmd.py | SaveCmd/LoadCmd → SaveAckEvt/LoadAckEvt 集成 |
| test_save_load_e2e.py | 存档/读档端到端 |

### v3 AVG 最小闭环（#91-#99）

| 测试文件 | 覆盖范围 | 关联 issue |
|---------|---------|-----------|
| test_text_renderer.py | 打字机 + 名字标签 + @style 应用 | #91 |
| test_options_panel.py | PromptInputEvt → 选项按钮列表 | #92 |
| test_audio_manager.py | BGM/SE/Voice 三轨 + 音量 + 降级 no-op | #93 |
| test_image_renderer.py | 背景图 + 角色立绘 + @bg/@char 钩子 | #94 |
| test_save_screenshot.py | 存档截图捕获 + SaveSlotDialog 网格 | #95 |
| test_backlog_history.py | BackLog 文本累积 + HistoryDialog | #96 |
| test_read_marks_auto_mode.py | ReadMarks 已读标记 + AutoModeController | #97 |
| test_settings.py | SettingsManager + SettingsDialog | #98 |
| test_v3_integration.py | v3-01~v3-08 全组件协同集成测试 | #99 |

### v4 开发工具台（#109-#117）

| 测试文件 | 覆盖范围 | 关联 issue |
|---------|---------|-----------|
| test_node_graph_model.py | Block→NodeData/EdgeData 转换 + 5 类分类 + 增删移动级联 + auto_layout + 序列化 | #109 |
| test_node_graph_view.py | NodeGraphView 工厂 + 6 用户操作 + 快照式撤销重做 + 双击/右键事件 + 真 PyQt6 smoke | #109 |
| test_dsl_sync.py | parse_source/story_to_source 全节点 unparser + roundtrip + graph_to_source + DslSync 双向同步（增删节点保留 body + If.branch 悬空过滤） | #110 |
| test_preview_controller.py | BreakpointManager 线程安全 + PreviewController worker 线程 + 断点/单步/暂停/停止 + 状态快照 + on_paused/on_finished 回调 + Executor before_block 钩子 | #111 |
| test_resource_manager.py | ResourceManager 扫描/索引/查询/统计/刷新 + P0-S1 四闸门校验（symlink/越界/扩展名白名单/大小）+ 统一路径解析 + ResourceEntry frozen dataclass | #112 |
| test_chapter_manager_model.py | ChapterManagerModel 扫描/索引/查询/创建/删除/重命名/复制/读写 + 名字安全校验 + DslSync 集成解析块数 + P0-S1 四闸门 + ChapterEntry frozen dataclass | #113 |
| test_debugger_model.py | DebuggerModel 变量查看（实时 + 历史快照）+ 执行路径/调用栈 + 断点列表委托 + 调试事件日志 + 监视变量 + 表达式求值 + PreviewController 集成（on_block_visit/on_paused/on_finished）+ max_history 裁剪 | #114 |
| test_project_exporter.py | ProjectExporter 扫描/校验/导出/导入 + ExportManifest 序列化（version 前向保护）+ zip 结构（chapters/+resources/+project.json）+ extract zip-slip 防护 + read_manifest 不解压 + 大小/文件数上限 + round-trip 内容保真 | #115 |
| test_editor_model.py | EditorModel 编排器：聚合 ChapterManagerModel/ResourceManager/DslSync/DebuggerModel/ProjectExporter + 当前章节生命周期（open/save/save_as/close/reload）+ DSL 双向同步委托 + 章节管理委托（含当前章节交互）+ 预览/调试生命周期（breakpoints 预设 + 运行时保护）+ 导出委托 + 脏标记跟踪 + refresh + 完整工作流集成 | #116 |
| test_v4_integration.py | v4-01~v4-08 全组件协同集成：完整编辑工作流（create→open→edit→sync→save）+ DSL round-trip + 预览/断点/单步/变量监视 + 章节 CRUD + 资源管理 + 导出 round-trip + 端到端工作流（编辑→预览→调试→导出→导入→验证）+ 纯 Python 无 Qt 验证 | #117 |

## 关联 issue

- #72: GameState 序列化（to_dict/from_dict + version 字段）
- #81: SaveCmd/LoadCmd/SaveAckEvt/LoadAckEvt 协议扩展
- #88: validate_chapter_path + v2_pending 测试激活
- #91-#99: v3 AVG 最小闭环（对话框 / 选项 / 音频 / 立绘 / 存档 / 历史 / 快进 / 设置 / 集成）
- #109-#117: v4 开发工具台（节点图编辑器 / DSL 双向同步 / 实时预览 / 资源 / 章节 / 调试 / 导出 / 主框架 / 集成）

## 测试统计

- v2-p0 + v3 合计：486 测试
- v4-01 节点图（模型 + 视图）：102 测试（55 + 47）
- v4-02 DSL 双向同步：29 测试
- v4-03 实时预览 + 断点调试：33 测试
- v4-04 资源管理器：41 测试
- v4-05 章节管理器模型：53 测试
- v4-06 调试器模型：62 测试
- v4-07 项目导出：55 测试
- v4-08 编辑器主框架：55 测试
- v4-09 v4 集成测试：20 测试
- v2_pending 合计：936 测试（全部通过）
- 全项目（含 core / runtime / v2_pending）：1236 测试
