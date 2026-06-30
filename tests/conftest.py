"""pytest 全局配置。

v2-p0 核心扩展已合并（SaveCmd/LoadCmd/validate_chapter_path/GameState.to_dict 等），
v2_pending 测试已激活并并入主测试套件。
PyQt6 相关测试在测试文件内部用 `pytest.importorskip("PyQt6")` 处理缺失依赖
（行业默认：optional 依赖缺失时 skip 而非 fail）。
"""
