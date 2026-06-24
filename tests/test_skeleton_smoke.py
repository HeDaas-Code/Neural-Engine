"""smoke test: 仓库骨架能让 pytest 跑通。

v0-issue-1 acceptance criteria:
- python3 -m pytest tests/ 在空仓库上跑 0 个测试、退出码 0
- src 下的子包都可 import
- pyproject.toml / requirements*.txt / README.md 齐备
"""
import importlib
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))


def test_core_engine_importable():
    """src/core/engine/ 子包存在且可 import。"""
    mod = importlib.import_module("core.engine")
    assert mod is not None


def test_core_decorators_importable():
    """src/core/decorators/ 子包存在且可 import。"""
    mod = importlib.import_module("core.decorators")
    assert mod is not None


def test_runtime_gui_importable():
    """src/runtime/gui/ 子包存在且可 import。"""
    mod = importlib.import_module("runtime.gui")
    assert mod is not None


def test_editor_importable():
    """src/editor/ 子包存在且可 import。"""
    mod = importlib.import_module("editor")
    assert mod is not None


def test_pyproject_toml_has_required_fields():
    """pyproject.toml 包含关键字段：name、requires-python、optional gui 依赖。"""
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "neural-engine"' in text
    assert 'requires-python = ">=3.11"' in text
    assert "PyQt6" in text  # gui optional dep
    assert "pytest" in text  # dev optional dep


def test_requirements_files_split():
    """requirements*.txt 拆分清楚：dev / gui 两个独立文件。"""
    assert (REPO_ROOT / "requirements.txt").exists()
    assert (REPO_ROOT / "requirements-dev.txt").exists()
    assert (REPO_ROOT / "requirements-gui.txt").exists()
    gui_text = (REPO_ROOT / "requirements-gui.txt").read_text(encoding="utf-8")
    assert "PyQt6" in gui_text or "gui" in gui_text


def test_pytest_ini_configures_testpaths():
    """pytest.ini 配置 testpaths=tests、pythonpath=src。"""
    text = (REPO_ROOT / "pytest.ini").read_text(encoding="utf-8")
    assert "testpaths" in text
    assert "tests" in text
    assert "pythonpath" in text
    assert "src" in text


def test_readme_states_v0_skeleton_status():
    """README.md 标 v0 状态。"""
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    # 至少有一个中文状态描述
    assert re.search(r"v0[- ]?issue-1|骨架|已就位|未实现", text), (
        "README.md 缺少 v0 状态描述"
    )
