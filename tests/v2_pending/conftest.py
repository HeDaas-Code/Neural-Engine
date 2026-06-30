"""v2-p0 待激活测试 — 跳过收集.

这些测试依赖 v2-p0 的 protocol/main/executor 扩展(SaveCmd/LoadCmd/
validate_chapter_path/GameState.to_dict 等), 待核心扩展合并后移除此文件激活.
"""
import pytest
pytest.skip("v2-p0 待激活: 依赖 protocol/main 扩展未合并", allow_module_level=True)
