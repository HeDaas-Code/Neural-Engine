# Phase1 Baseline Deviation List — Neural-Engine

> **任务编号**：phase1-baseline-deviations
> **执行者**：tdd-coder
> **日期**：2026-06-24
> **配套报告**：`docs/audit/phase1-baseline.md`
> **性质**：基线运行中发现的偏差登记，**不修复**，移交 code-auditor 评估

---

## 偏差登记格式

每条偏差包括：
- **编号**：唯一 ID
- **类别**：ENV / TEST / LINT / COV / DEP / DOC
- **严重度**：🔴 高（阻塞 CI/发布） / 🟡 中（影响一致性） / 🟢 低（噪声/可推迟）
- **现象**：可观察到的偏差
- **影响范围**：哪些路径受影响
- **根因**：技术原因
- **修复候选**：可选方案
- **建议归属**：交给哪个角色 / 哪个 issue

---

## D-ENV-1 — Python 版本与 `pyproject.toml` 声明不一致

| 项 | 值 |
|---|---|
| 类别 | ENV |
| 严重度 | 🟡 中 |
| 现象 | 环境仅有 Python 3.10.11；`pyproject.toml` 声明 `requires-python = ">=3.11"` |
| 影响范围 | 所有开发机/CI 环境若装 Python 3.10 则 `pip install -e .` 直接失败 |
| 根因 | pyproject.toml 中硬编码 `>=3.11`，但未强制 CI 镜像升级 |
| 当前绕过 | `pip install --ignore-requires-python -e .` |
| 修复候选 | A. 放宽到 `>=3.10`（兼容性最佳）；B. 强制 CI/开发机用 3.11+；C. 文档化"需手动 `--ignore-requires-python`" |
| 风险 | 用 3.10 跑测试可能掩盖 3.11+ 才有的语法特性（如 `tomllib`、`Self`、`ExceptionGroup`）；simpleeval 当前未用到这些，但未来 v2 可能引入 |
| 建议归属 | **PM 决策**（环境策略）+ **code-auditor 评估**（pyproject.toml 是否需要修改） |
| 状态 | 待决策 |

---

## D-TEST-1 — 3 个 invariant 守护测试在 Windows 上失败（grep 子进程）

| 项 | 值 |
|---|---|
| 类别 | TEST |
| 严重度 | 🔴 高（CI 在 Windows 平台会失败） |
| 现象 | `tests/test_invariants.py` 中 3 个测试调用 `subprocess.run(["grep", ...])`，Windows 默认无 `grep.exe`，导致 `FileNotFoundError: [WinError 2]` |
| 失败用例 ID | `test_invariant_3_next_not_string_literal`、`test_invariant_6_bus_json_only`、`test_no_todo_or_fixme_in_src` |
| 影响范围 | Windows 平台无法跑全套测试（208/211） |
| 根因 | invariant 测试是 POSIX-only 设计（开发者本机可能是 macOS/Linux），未做跨平台兼容 |
| 修复候选 | A. 用 `pathlib + re` 在 Python 内实现 grep 等价扫描（**跨平台，推荐**）；B. `pytest.mark.skipif(sys.platform == "win32")` 跳过；C. 文档要求开发者装 Git for Windows / WSL |
| 建议归属 | **tdd-coder phase1-fixes issue**：先用 TDD 写"Windows 平台 invariant 守护测试"（先 Red），再改实现 |
| 状态 | 待 issue 派工 |

---

## D-LINT-1 — Ruff 默认规则 31 个错误（绝大多数为未使用 import）

| 项 | 值 |
|---|---|
| 类别 | LINT |
| 严重度 | 🟡 中（CI 若开 ruff check 会失败） |
| 现象 | `ruff check src/ tests/` 报 31 个错误 |
| 分布 | F401 28 处 + E402 1 处 + E741 1 处 + F541 1 处 |
| 影响范围 | src 涉及 2 文件（executor.py / interpreter.py），tests 涉及 17 文件 |
| 根因 | 历次迭代遗留的未使用 import（多数为 TypeScript 风格的 import-as-document）；少量代码风格细节 |
| 修复候选 | A. `ruff check --fix`（自动修 29/31）；B. 手动 review 后 `--fix`（更稳妥） |
| 不可自动修的 2 个 | `src/core/engine/interpreter.py:504` 的 `import re` 放在文件中间（E402，需移到顶部）；`tests/core/test_block_skeleton.py:69` 的歧义变量名 `l`（E741，需重命名） |
| 建议归属 | **tdd-coder phase1-fixes issue**：自动修 29 处 + 手动改 2 处 |
| 状态 | 待 issue 派工 |

---

## D-LINT-2 — 34 处 E501 行长超限（默认 ruff 不查）

| 项 | 值 |
|---|---|
| 类别 | LINT |
| 严重度 | 🟢 低（默认 ruff 不查） |
| 现象 | `--select=E` 时报 34 处行超 88 字符 |
| 分布 | 中文长注释（docstring）+ dataclass 长调用（`NextDecl(...)` / `Branch(value=...)`） |
| 根因 | 项目混用中英文注释 + dataclass 字段名较长 |
| 修复候选 | A. pyproject.toml 设 `line-length = 100`（适应中文 docstring）；B. 拆长行 |
| 建议归属 | **code-auditor 决策**（要不要启用 E501 / 设多少长度阈值） |
| 状态 | 待决策 |

---

## D-LINT-3 — 2 处 W292 文件末尾缺换行

| 项 | 值 |
|---|---|
| 类别 | LINT |
| 严重度 | 🟢 低 |
| 现象 | `tests/test_invariants.py` 和 `tests/test_mvp_table.py` 末尾无换行符 |
| 修复方式 | `ruff check --fix` 自动修 |
| 建议归属 | 随 D-LINT-1 一并修 |
| 状态 | 待 issue 派工 |

---

## D-COV-1 — `src/core/engine/main.py` 覆盖率仅 65%

| 项 | 值 |
|---|---|
| 类别 | COV |
| 严重度 | 🟢 低（不阻塞，但应在 v2 提升） |
| 现象 | main.py 中 30 行未覆盖，主要在 GUI 集成的 `main()` 入口 |
| 缺行 | 63-64, 80-86, 97-98, 104-105, 112-127, 135-136, 141-144 |
| 根因 | v2 阶段才集成 PyQt6，当前无 GUI 集成测试 |
| 修复候选 | v2 阶段补 GUI 集成测试 |
| 建议归属 | **v2 阶段 GUI 集成任务** |
| 状态 | 已知推迟 |

---

## D-COV-2 — `src/core/engine/interpreter.py` 覆盖率 89%（19 行缺）

| 项 | 值 |
|---|---|
| 类别 | COV |
| 严重度 | 🟢 低 |
| 现象 | interpreter.py 中 19 行未覆盖，涉及 multi-if 异常路径、二元/多元 if 失败路径 |
| 缺行 | 240, 309, 318, 324, 352, 397, 399, 410, 431, 440, 461, 487, 495, 532, 547, 623-627, 634-635, 647-667, 695 |
| 根因 | 多为"理论上会抛错但 happy path 触发不到"的防御性代码 |
| 修复候选 | 写负面测试覆盖异常路径（如 `test_if_parse_malformed_xxx` 已部分覆盖） |
| 建议归属 | 评估是否需要补覆盖（可能不必要） |
| 状态 | 待评估 |

---

## D-COV-3 — `src/core/engine/executor.py` 覆盖率 91%（10 行缺）

| 项 | 值 |
|---|---|
| 类别 | COV |
| 严重度 | 🟢 低 |
| 现象 | executor.py 中 10 行未覆盖 |
| 缺行 | 43, 116, 135, 202, 235, 267-272, 278-283, 293-294, 300, 317-318 |
| 根因 | 主要为运行时错误分支（如未知 next target、bus 关闭后写入） |
| 修复候选 | 写负面测试覆盖 |
| 建议归属 | 评估是否需要补覆盖 |
| 状态 | 待评估 |

---

## D-DEP-1 — pyproject.toml `requires-python>=3.11` 与运行时 3.10 不一致

| 项 | 值 |
|---|---|
| 类别 | DEP |
| 严重度 | 🟡 中 |
| 现象 | 同 D-ENV-1，从依赖声明视角再列一次 |
| 建议归属 | 同 D-ENV-1，由 PM 决策 |
| 状态 | 待决策 |

---

## D-DEP-2 — 无 GUI 依赖（按任务约束推迟）

| 项 | 值 |
|---|---|
| 类别 | DEP |
| 严重度 | 🟢 低（符合任务约束） |
| 现象 | PyQt6 未安装；`requirements-gui.txt` 未执行 |
| 任务依据 | "不装 PyQt6（GUI 推迟到 v2 阶段）" |
| 状态 | 符合预期，无须处置 |

---

## D-DOC-1 — `tmp/coverage_html/` 在仓库内（建议 gitignore）

| 项 | 值 |
|---|---|
| 类别 | DOC |
| 严重度 | 🟢 低 |
| 现象 | 覆盖率 HTML 报告生成在 `tmp/coverage_html/`，未检查 `.gitignore` 是否覆盖 |
| 修复候选 | 检查并补充 `.gitignore` 规则 |
| 建议归属 | **tdd-coder phase1-fixes**（顺手） |
| 状态 | 待检查 |

---

## 偏差汇总表

| 编号 | 类别 | 严重度 | 简述 | 归属 |
|---|---|---|---|---|
| D-ENV-1 | ENV | 🟡 | Python 3.10 vs pyproject 3.11 | PM 决策 |
| D-TEST-1 | TEST | 🔴 | 3 个 invariant 守护测试在 Windows 上失败 | tdd-coder phase1-fixes |
| D-LINT-1 | LINT | 🟡 | ruff 31 errors（28 F401 + 3 其他） | tdd-coder phase1-fixes |
| D-LINT-2 | LINT | 🟢 | 34 E501 超长行 | code-auditor 决策 |
| D-LINT-3 | LINT | 🟢 | 2 W292 文件末尾缺换行 | 随 D-LINT-1 |
| D-COV-1 | COV | 🟢 | main.py 覆盖率 65% | v2 GUI 阶段 |
| D-COV-2 | COV | 🟢 | interpreter.py 89% | 评估是否补覆盖 |
| D-COV-3 | COV | 🟢 | executor.py 91% | 评估是否补覆盖 |
| D-DEP-1 | DEP | 🟡 | pyproject 3.11 vs 运行时 3.10 | PM 决策 |
| D-DEP-2 | DEP | 🟢 | GUI 推迟到 v2 | 符合预期 |
| D-DOC-1 | DOC | 🟢 | tmp/coverage_html 未确认 gitignore | tdd-coder phase1-fixes |

**统计**：11 条偏差
- 🔴 高：1 条（D-TEST-1）
- 🟡 中：3 条（D-ENV-1 / D-LINT-1 / D-DEP-1）
- 🟢 低：7 条

---

## 不在本偏差清单的事项（避免噪音）

- ✅ pytest 9.1.1 / ruff 0.15.19 / simpleeval 1.0.7 等具体版本选择 — 属于依赖版本基线，不是偏差
- ✅ 测试用例的中文 docstring 长度 — 属 D-LINT-2 范围
- ✅ Windows PowerShell 输出含 `?` 乱码 — 终端编码问题，非代码问题

---

## 移交流程

1. **tdd-coder** → 把本清单 + baseline 报告 + `tmp/` 下原始输出打包
2. → **code-auditor**：评估偏差严重度排序，决定进入 phase1-fixes issue 集
3. → **PM**：对 D-ENV-1 / D-DEP-1 做环境决策
4. → **pdr-analyst**（可选）：把 D-TEST-1 写入下一个 PDR 的"已知问题"章节

---

**清单版本**：v1.0  
**最后更新**：2026-06-24 23:08（Asia/Shanghai）
