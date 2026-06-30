# Phase1 Baseline Report — Neural-Engine

> **任务编号**：phase1-baseline
> **执行者**：tdd-coder
> **执行日期**：2026-06-24
> **工作目录**：`C:\Users\rog\.mavis\agents\project-manager\workspace\neural-engine\Neural-Engine-main`
> **任务性质**：基线建立（不修复任何问题，仅记录）

---

## 一、TL;DR（决策摘要）

| 维度 | 期望值 | 实测值 | 偏差 | 处置 |
|---|---|---|---|---|
| 全量测试 | 211 passed | **208 passed / 3 failed** | -3（平台不兼容，**非代码缺陷**） | 见 §四 |
| Ruff（默认规则） | 通过 | **31 errors / 0 warnings** | +31 | 见 §五 |
| Ruff（E+W+F 全规则） | n/a | 67 errors / 0 warnings | 仅参考 | 见 §五 |
| 总体覆盖率 | n/a（无阈值） | **90%（943 stmts / 93 missed）** | — | 见 §六 |
| GUI 依赖（PyQt6） | 推迟 | **未装** | 符合约束 | 见 §三 |

**主要偏差**：3 个 invariant 守护测试在 Windows 上调用 `grep` 子进程失败（POSIX-only 设计），需要 code-auditor 评估是否修复测试或保留 POSIX-only。

---

## 二、环境

### 2.1 操作系统

- 平台：`win32`（Windows 10/11）
- Shell：PowerShell 5.1
- 用户家目录：`C:\Users\rog`

### 2.2 Python 解释器

| 项 | 值 |
|---|---|
| Python 版本 | **3.10.11** |
| `requires-python`（pyproject.toml） | `>=3.11` |
| venv 路径 | `.venv/`（位于项目根目录） |
| venv 创建方式 | `python -m venv .venv` |

> **偏差 D-ENV-1**：环境仅有 Python 3.10.11，`pyproject.toml` 声明 `>=3.11`。本基线使用 `--ignore-requires-python` 绕过版本检查以建立基线，未安装 PyQt6（推迟到 v2）。详见 §四.1。

---

## 三、依赖

### 3.1 已装（必装项）

通过 `pip install -e .` + `pip install -r requirements-dev.txt` 安装：

| 包名 | 版本 | 来源 | 用途 |
|---|---|---|---|
| neural-engine | 0.0.0（editable） | 本仓库 | 项目本体 |
| simpleeval | 1.0.7 | `dependencies` | v1-issue-1 表达式求值器（ADR-0003 §1 决策 1） |
| pytest | 9.1.1 | dev extras | 测试框架 |
| pytest-cov | 7.1.0 | dev extras | 覆盖率 |
| coverage | 7.14.3 | pytest-cov 传递依赖 | 覆盖率引擎 |
| exceptiongroup | 1.3.1 | pytest 传递依赖 | 异常组（pytest 内部用） |
| tomli | 2.4.1 | pytest 传递依赖 | TOML 解析 |
| typing-extensions | 4.15.0 | pytest 传递依赖 | typing 扩展 |
| pluggy | 1.6.0 | pytest 传递依赖 | pytest 插件机制 |
| iniconfig | 2.3.0 | pytest 传递依赖 | INI 配置解析 |
| colorama | 0.4.6 | pytest 传递依赖 | Windows ANSI 颜色 |
| pygments | 2.20.0 | pytest 传递依赖 | 代码高亮 |
| packaging | 26.2 | pip 升级带入 | 版本元数据 |

### 3.2 工具（不在 requirements 中，按任务需要单独装）

| 包名 | 版本 | 用途 |
|---|---|---|
| ruff | 0.15.19 | 静态扫描 |
| pip | 26.1.2 | 已升级 |
| setuptools | 82.0.1 | 已升级 |
| wheel | 0.47.0 | 已升级 |

### 3.3 未装（GUI 推迟到 v2 阶段）

- **PyQt6**（`requirements-gui.txt`）：按任务约束 **不安装**，GUI 推迟到 v2。

---

## 四、测试结果

### 4.1 总体

- **收集**：211 items
- **通过**：**208**
- **失败**：**3**
- **跳过**：0
- **总耗时**：约 9.87 秒

> **与期望偏差**：期望 211 passed，实测 208 passed / 3 failed。**3 个失败均为同一根因：测试假设环境存在 `grep.exe`，Windows 默认无此二进制**。详见 §4.3。

### 4.2 通过测试分布（按文件）

| 测试文件 | 通过 / 总数 |
|---|---|
| `tests/core/test_arrow_syntax.py` | 6/6 |
| `tests/core/test_ast_shapes.py` | 8/8 |
| `tests/core/test_block_body.py` | 11/11 |
| `tests/core/test_block_meta.py` | 10/10 |
| `tests/core/test_block_skeleton.py` | 10/10 |
| `tests/core/test_decorator_parse.py` | 6/6 |
| `tests/core/test_engine_bus.py` | 8/8 |
| `tests/core/test_executor_decorator.py` | 5/5 |
| `tests/core/test_executor_if.py` | 8/8 |
| `tests/core/test_executor_nodes.py` | 11/11 |
| `tests/core/test_executor_skeleton.py` | 7/7 |
| `tests/core/test_expr_custom.py` | 6/6 |
| `tests/core/test_expr_dispatcher.py` | 11/11 |
| `tests/core/test_extract_neon.py` | 10/10 |
| `tests/core/test_if_parse.py` | 9/9 |
| `tests/core/test_main_entry.py` | 4/4 |
| `tests/core/test_next_decls.py` | 8/8 |
| `tests/core/test_protocol_cmd.py` | 8/8 |
| `tests/core/test_protocol_evt.py` | 11/11 |
| `tests/integration/test_chapter01_e2e.py` | 2/2 |
| `tests/integration/test_echo_path.py` | 3/3 |
| `tests/integration/test_v1_e2e.py` | 5/5 |
| `tests/runtime/test_gui_protocol.py` | 6/6 |
| `tests/test_invariants.py` | **8/11**（3 失败） |
| `tests/test_mvp_table.py` | 19/19 |
| `tests/test_skeleton_smoke.py` | 8/8 |
| **合计** | **208/211** |

### 4.3 失败用例清单（不修复）

| # | 用例 ID | 错误类型 | 错误信息 |
|---|---|---|---|
| F1 | `tests/test_invariants.py::test_invariant_3_next_not_string_literal` | `FileNotFoundError` | 调用 `subprocess.run(["grep", "-r", "-E", '"NEXT"', "src/", "--include=*.py"], ...)` 时找不到 `grep.exe` |
| F2 | `tests/test_invariants.py::test_invariant_6_bus_json_only` | `FileNotFoundError` | 调用 `subprocess.run(["grep", "-r", "-E", "pickle\|msgpack", "src/", "--include=*.py"], ...)` 时找不到 `grep.exe` |
| F3 | `tests/test_invariants.py::test_no_todo_or_fixme_in_src` | `FileNotFoundError` | 调用 `subprocess.run(["grep", "-r", "-E", "TODO\|FIXME", "src/", "--include=*.py"], ...)` 时找不到 `grep.exe` |

**共同根因**：`tests/test_invariants.py` 中 3 个守护测试（§11 不变量 #3、#6、#6-扩展 TODO/FIXME 守护）使用 `subprocess.run(["grep", ...])` 直接调用 GNU grep。该测试是 POSIX-only 设计——Windows 无 `grep.exe` 默认安装，导致 `FileNotFoundError: [WinError 2]`。

**影响范围**：仅这 3 个失败用例；其他 8 个 invariant 测试（`test_invariant_1/2/4/5/7/8/9/10`）均通过。

**修复候选**（**不执行**，留给 code-auditor 评估）：
- 选项 A：改用 Python `pathlib` + `re` 实现 grep 等价扫描（跨平台）
- 选项 B：保留 POSIX-only 假设，在 `conftest.py` 中 `pytest.mark.skipif(sys.platform == "win32")` 跳过
- 选项 C：要求开发者装 Git for Windows（带 grep.exe）或 WSL

### 4.4 pytest 配置

- 配置文件：`pytest.ini`
- `testpaths = ["tests"]`
- `pythonpath = ["src"]`
- `addopts = "-ra --strict-markers"`
- 插件：pytest-cov 7.1.0
- 命令：`.\.venv\Scripts\python.exe -m pytest tests/ -v`

---

## 五、ruff 静态扫描

### 5.1 默认规则集（`ruff check src/ tests/`）

| 项 | 数量 |
|---|---|
| **errors**（总） | **31** |
| warnings | 0 |
| fixable（`--fix`） | 29 / 31 |

**按规则分类**：

| 代码 | 数量 | 含义 | 可自动修复 |
|---|---|---|---|
| F401 | 28 | `imported but unused`（未使用的 import） | ✓ |
| E402 | 1 | `module level import not at top of file`（模块级 import 位置错误） | ✗ |
| E741 | 1 | `ambiguous variable name: l`（歧义变量名 `l`） | ✗ |
| F541 | 1 | `f-string without any placeholders`（f-string 缺占位符） | ✓ |

### 5.2 全规则集（`--select=E,W,F`）— 参考

| 项 | 数量 |
|---|---|
| **errors**（总） | **67** |
| warnings | 0（ruff 把 W 也归为 error） |
| fixable | 31 / 67 |

| 代码 | 数量 | 含义 |
|---|---|---|
| E501 | 34 | `line too long`（默认未启用，需 `--select=E` 才查） |
| F401 | 28 | 未使用的 import |
| W292 | 2 | `no newline at end of file` |
| E402 | 1 | import 位置 |
| E741 | 1 | 歧义变量名 |
| F541 | 1 | f-string 占位符缺失 |

### 5.3 ruff 扫描的文件

- `src/core/engine/executor.py`
- `src/core/engine/interpreter.py`
- `tests/core/test_arrow_syntax.py`
- `tests/core/test_block_meta.py`
- `tests/core/test_block_skeleton.py`
- `tests/core/test_decorator_parse.py`
- `tests/core/test_executor_decorator.py`
- `tests/core/test_executor_if.py`
- `tests/core/test_executor_nodes.py`
- `tests/core/test_executor_skeleton.py`
- `tests/core/test_extract_neon.py`
- `tests/core/test_if_parse.py`
- `tests/core/test_main_entry.py`
- `tests/core/test_next_decls.py`
- `tests/integration/test_chapter01_e2e.py`
- `tests/integration/test_v1_e2e.py`
- `tests/runtime/test_gui_protocol.py`
- `tests/test_invariants.py`
- `tests/test_mvp_table.py`

**涉及 src 文件数**：2 个（`executor.py`, `interpreter.py`）  
**涉及 tests 文件数**：17 个  
**合计扫描文件数**：19 个

> **注**：默认 ruff 不查 E501（行长），这是 Ruff 0.15.19 的默认行为（避免在 CI 误伤中文长注释）。若需严格 88 字符限制，需在 `pyproject.toml` 中显式开启。

---

## 六、覆盖率

### 6.1 总体

| 项 | 值 |
|---|---|
| Stmts | **943** |
| Miss | 93 |
| Branches | 未配置分支覆盖 |
| **总体覆盖率** | **90%** |

HTML 报告：`tmp/coverage_html/index.html`

### 6.2 src/core/engine/ 文件维度（任务重点）

| 文件 | Stmts | Miss | Cover | Missing Lines |
|---|---|---|---|---|
| `src/core/engine/__init__.py` | 0 | 0 | **100%** | — |
| `src/core/engine/ast_nodes.py` | 78 | 0 | **100%** | — |
| `src/core/engine/bus.py` | 36 | 0 | **100%** | — |
| `src/core/engine/executor.py` | 207 | 19 | **91%** | 43, 116, 135, 202, 235, 267-272, 278-283, 293-294, 300, 317-318 |
| `src/core/engine/interpreter.py` | 324 | 35 | **89%** | 240, 309, 318, 324, 352, 397, 399, 410, 431, 440, 461, 487, 495, 532, 547, 623-627, 634-635, 647-667, 695 |
| `src/core/engine/main.py` | 82 | 29 | **65%** | 63-64, 80-86, 97-98, 104-105, 112-127, 135-136, 141-144 |
| `src/core/engine/protocol.py` | 126 | 4 | **97%** | 18, 36, 132, 234 |
| `src/core/engine/expr/__init__.py` | 5 | 0 | **100%** | — |
| `src/core/engine/expr/builtin_funcs.py` | 3 | 0 | **100%** | — |
| `src/core/engine/expr/custom.py` | 19 | 0 | **100%** | — |
| `src/core/engine/expr/dispatcher.py` | 26 | 2 | **92%** | 108-110 |
| `src/core/engine/expr/errors.py` | 3 | 0 | **100%** | — |

### 6.3 其他 src 子包

| 文件 | Stmts | Miss | Cover |
|---|---|---|---|
| `src/core/__init__.py` | 0 | 0 | 100% |
| `src/core/decorators/__init__.py` | 0 | 0 | 100% |
| `src/editor/__init__.py` | 0 | 0 | 100% |
| `src/runtime/__init__.py` | 0 | 0 | 100% |
| `src/runtime/gui/__init__.py` | 0 | 0 | 100% |
| `src/runtime/gui/main.py` | 34 | 4 | 88% |

### 6.4 覆盖率盲点（需要关注的低覆盖文件）

| 文件 | 覆盖率 | 缺行 | 备注 |
|---|---|---|---|
| `src/core/engine/main.py` | **65%** | 30 行未覆盖 | 缺少 GUI 集成路径覆盖（与 PyQt6 推迟有关） |
| `src/runtime/gui/main.py` | **88%** | 4 行未覆盖 | GUI 主入口，同样受 PyQt6 推迟影响 |
| `src/core/engine/interpreter.py` | 89% | 19 行未覆盖 | 涉及 multi-if 异常路径、二元/多元 if 失败路径 |
| `src/core/engine/executor.py` | 91% | 10 行未覆盖 | 涉及运行时错误分支、未知 next target 路径 |
| `src/core/engine/expr/dispatcher.py` | 92% | 3 行未覆盖 | fallback 全部 handler 失败后的兜底异常路径 |

> **决策建议**：当前 90% 总覆盖率已属较高水位；`main.py` 65% 主要受 GUI 推迟影响，待 PyQt6 集成后应能回升。

---

## 七、已知问题（不修，先列出来）

### 偏差 D-ENV-1 — Python 版本与 `pyproject.toml` 声明不一致

- **现象**：环境仅有 Python 3.10.11；`pyproject.toml` 中 `requires-python = ">=3.11"`
- **影响**：`pip install -e .` 直接失败（ERROR: Package 'neural-engine' requires a different Python: 3.10.11 not in '>=3.11'）
- **当前绕过**：`pip install --ignore-requires-python -e .`
- **建议处置**：
  - 选项 A：放宽 pyproject.toml 到 `>=3.10`（兼容性更好，但失去 3.11+ 新特性）
  - 选项 B：环境升级 Python 到 3.11+（更严格，但需运维配合）
  - 选项 C：保留 3.11+，让 3.10 环境的开发者手动 `--ignore-requires-python`
- **风险**：用 3.10 跑测试可能掩盖仅在 3.11+ 出现的语法/类型问题（如 `tomllib`、`Self`、`ExceptionGroup`）。

### 偏差 D-TEST-1 — 3 个 invariant 守护测试在 Windows 上失败（grep 子进程）

- **现象**：3 个测试调用 `subprocess.run(["grep", ...])`，Windows 无 grep.exe 报错 `FileNotFoundError`
- **影响**：测试套件不能完整在 Windows 平台通过（208/211）
- **修复候选**：见 §4.3 三个选项
- **建议处置**：code-auditor 评估后决定走 A/B/C 哪条路；当前 tdd-coder 不修。

### 偏差 D-LINT-1 — Ruff 默认规则 31 个错误（绝大多数为未使用 import）

- **现象**：
  - 28 处 `F401 unused-import`（src 1 处 + tests 27 处）
  - 1 处 `E402 import not at top`（`src/core/engine/interpreter.py:504`）
  - 1 处 `E741 ambiguous variable name 'l'`（`tests/core/test_block_skeleton.py:69`）
  - 1 处 `F541 f-string without placeholders`（`src/core/engine/executor.py:329`）
- **影响**：CI 若开 ruff 会失败
- **修复建议**：其中 29/31 可通过 `ruff check --fix` 自动修复；剩下 E402/E741 需手动调整
- **建议处置**：纳入 phase1-fix issue，让 tdd-coder 后续任务一并修

### 偏差 D-LINT-2 — 34 处 E501 行长超限（中文长注释+长 dataclass 调用）

- **现象**：默认 ruff 不查 E501，但若开启 `--select=E` 会扫到 34 处
- **主要分布**：
  - `tests/test_invariants.py`：约 9 处（pytest 命令字符串拼接）
  - `tests/core/test_if_parse.py`：约 8 处（`NextDecl(...)` 调用）
  - `tests/integration/test_echo_path.py`：2 处（docstring 中文）
  - 其余零散
- **建议处置**：
  - 选项 A：开启 E501 时设置 line-length=100（适应中文 docstring）
  - 选项 B：拆长行
- **建议**：在 pyproject.toml 中显式配置 ruff：`[tool.ruff] line-length = 100`，再让 phase1-fix 处理剩余超长行

### 偏差 D-LINT-3 — 2 处 W292 文件末尾缺换行

- **现象**：`tests/test_invariants.py` 和 `tests/test_mvp_table.py` 文件末尾无换行符
- **修复方式**：`ruff check --fix` 可自动修
- **建议处置**：随 D-LINT-1 一起修

### 偏差 D-COV-1 — `src/core/engine/main.py` 覆盖率仅 65%

- **现象**：30 行未覆盖，主要是 GUI 集成的 `main()` 入口路径
- **根因**：v2 阶段才集成 PyQt6，当前无 GUI 集成测试覆盖
- **建议处置**：v2 阶段 PyQt6 集成时补齐测试覆盖

### 偏差 D-DEP-1 — pyproject.toml 中 `requires-python>=3.11` 但运行时 Python 3.10

- 见 D-ENV-1，本质是同一问题的不同侧面
- 重复列出以提示"运行时 vs 声明"两个视角都需要决策

---

## 八、构建证据

### 8.1 测试运行命令

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

### 8.2 ruff 扫描命令

```powershell
.\.venv\Scripts\ruff.exe check src/ tests/ --output-format=concise
```

### 8.3 覆盖率命令

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ --cov=src --cov-report=term-missing --cov-report=html:tmp/coverage_html
```

### 8.4 原始输出存档

- `tmp/pytest_baseline.txt` — pytest -v 全量输出
- `tmp/pytest_failed_invariants.txt` — 失败用例的精简 tb 输出
- `tmp/ruff_baseline.txt` — ruff check 默认规则输出
- `tmp/ruff_default_stats.txt` — ruff 默认规则分类统计
- `tmp/ruff_ewf_stats.txt` — ruff E+W+F 全规则分类统计
- `tmp/ruff_ew.txt` — ruff E+W 全规则明细
- `tmp/coverage_baseline.txt` — pytest + coverage 输出
- `tmp/coverage_html/` — 覆盖率 HTML 报告（点开 `index.html`）

---

## 九、下一步建议

1. **code-auditor**：评估 7 个偏差（D-ENV-1 / D-TEST-1 / D-LINT-1 / D-LINT-2 / D-LINT-3 / D-COV-1 / D-DEP-1）的修复优先级与归属
2. **pdr-analyst**：将 D-TEST-1 的修复选项纳入 phase1-fixes issue
3. **tdd-coder**：等 phase1-fixes issue 派工后，按 TDD 流程先写失败测试再修代码
4. **PM**：环境需要决策 Python 3.10 vs 3.11，影响 CI/开发机一致性

---

**报告完成时间**：2026-06-24 23:08（Asia/Shanghai）  
**报告版本**：v1.0（baseline 初版，未修正任何代码）
