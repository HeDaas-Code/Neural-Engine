## Parent

#1（PRD-0001 父 issue）

## What to build

建立 v0 项目骨架，让后续所有 vertical slice 有落地处。

- 仓库根 `pyproject.toml`（PEP 621）：声明 `name="neural-engine"`、`requires-python=">=3.11"`、dev dep `pytest>=8`、`pytest-cov`（**不**声明 PyQt6——v0 可选）
- `requirements.txt`（或 `requirements-dev.txt`）：固定 pytest 版本
- `requirements-gui.txt`（**可选**）：固定 PyQt6
- `pytest.ini` 或 `pyproject.toml [tool.pytest.ini_options]`：`testpaths = ["tests"]`、`pythonpath = ["src"]`
- `README.md`：v0 状态（**已实现哪些 / 未实现哪些**）+ `python -m pytest tests/` 跑测命令
- 包结构（**只建 `__init__.py`，不写实现**）：
  - `src/core/__init__.py`、`src/core/engine/__init__.py`、`src/core/decorators/__init__.py`
  - `src/runtime/__init__.py`、`src/runtime/gui/__init__.py`
  - `tests/__init__.py`（可空）、`tests/parser/__init__.py`、`tests/executor/__init__.py`
- `tests/parser/inputs/`、`tests/executor/inputs/` 建空目录占位

## Acceptance criteria

- [ ] `python -m pytest tests/` 在空仓库上跑 0 个测试、退出码 0
- [ ] `python -c "import sys; sys.path.insert(0, 'src'); from core.engine import ..."` 可 import 各子包
- [ ] `requirements.txt` / `requirements-gui.txt` 拆分清楚
- [ ] `README.md` 标 v0 状态为 "骨架已就位"

## Blocked by

#1
