# v2-p0 测试（已激活）

这些测试来自 `feature/v2-p0-gui-first` 分支合并，验证 v2-p0 的 protocol/main/executor 扩展
（SaveCmd/LoadCmd/validate_chapter_path/GameState.to_dict 等）。

## 状态：已激活

v2-p0 核心扩展已合并到 main 分支，测试已激活并纳入主测试套件。

## 测试覆盖

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

## 关联 issue

- #72: GameState 序列化（to_dict/from_dict + version 字段）
- #81: SaveCmd/LoadCmd/SaveAckEvt/LoadAckEvt 协议扩展
- #88: validate_chapter_path + v2_pending 测试激活
