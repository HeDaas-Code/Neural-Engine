# 阶段一 Issue 列表：独立审计 + v1 偏差修复

> **关联 PDR**：`docs/pdr/phase1-audit-and-fixes.md`
> **基线**：v0 基础版 + v1 表达式重构已闭环（211/211 tests passed）
> **作者**：pdr-analyst
> **日期**：2026-06-24
> **状态**：待 PM 拍板分派

---

## 0. 概览

共 **9 个原子 issue**（在 5-10 范围内），按 3 类组织：

| 类别 | 编号 | 标题 | 估时 | 依赖 |
|---|---|---|---|---|
| A. 基线 | P1-001 | 建立项目基线（装依赖/跑测试/扫描/覆盖率） | L | — |
| B. 审计 | P1-002 | 三视角独立审计·架构与代码质量 | M | P1-001 |
| B. 审计 | P1-003 | 三视角独立审计·安全与沙箱 | M | P1-001 |
| B. 审计 | P1-004 | 三视角独立审计·可测试性与工程化 | M | P1-001 |
| B. 审计 | P1-005 | 合并三视角审计报告 | S | P1-002/003/004 |
| C. 修复 | P1-006 | 修偏差 D5：锁定 simpleeval 版本 | S | P1-001 |
| C. 修复 | P1-007 | 修偏差 D1：If.cond 显式登记 bool_expr 决策 | S | P1-001 |
| C. 修复 | P1-008 | 修偏差 D4：收窄 dispatcher 异常捕获 | S-M | P1-001 |
| C. 修复 | P1-009 | 修偏差 D2：实现 G5 修饰器结构化参数（MVP） | L | P1-001, P1-002（参考） |
| 收尾 | P1-010 | 阶段一回归与文档同步 | S | 全部 |

**依赖图**：

```
P1-001 ─┬─→ P1-002 ─┐
        ├─→ P1-003 ─┼─→ P1-005
        ├─→ P1-004 ─┘
        ├─→ P1-006 ─┐
        ├─→ P1-007 ─┤
        ├─→ P1-008 ─┼─→ P1-010
        └─→ P1-009 ─┘
```

**可并行 issue**：
- P1-002 / P1-003 / P1-004 三审计互相并行（不同视角）
- P1-006 / P1-007 / P1-008 三小修复互相并行（不同文件）
- 审计组（P1-002/003/004）与小修复组（P1-006/007/008）可并行

---

## A. 项目基线（Category a）

### P1-001 · 建立项目基线

| 项 | 内容 |
|---|---|
| **ID** | P1-001 |
| **类型** | chore（基础设施） |
| **估时** | L（约 0.5-1 天） |
| **依赖** | 无（阶段一第一个 issue） |
| **风险** | LOW |
| **目标** | 在本机建立可复现的 v0+v1 基线，作为后续审计和修复的对照基线 |
| **上下文** | 阶段一所有后续工作都依赖一个可信基线：测试全绿、覆盖率有数字、lint 有结论、依赖有版本。当前环境已 `git clone`，但未确认依赖装好、测试 211/211 通过、ruff 跑通、pytest-cov 报告已生成。 |

**验收标准**（全部必须通过）：

1. **依赖安装**：
   - 命令：`python3 -m pip install -e .[dev]` 退出码 0
   - 命令：`python3 -c "import simpleeval; print(simpleeval.__version__)"` 输出当前安装的 simpleeval 版本（记入 commit message）

2. **测试通过**：
   - 命令：`python3 -m pytest tests/ -q` 输出 `211 passed, 0 failed`
   - 命令：`python3 -m pytest tests/ -q` 退出码 0

3. **覆盖率报告**：
   - 命令：`python3 -m pytest tests/ --cov=src --cov-report=term-missing --cov-report=html:tmp/coverage_html`
   - 生成 `tmp/coverage_html/index.html` + stdout 输出每模块覆盖率
   - **记录**到 `docs/audit/phase1-baseline.md`（新建），包含：总覆盖率、各模块覆盖率、当前 simpleeval 版本

4. **Ruff 扫描**（如未配置需先 `pip install ruff` + 在 pyproject.toml 初始化）：
   - 命令：`ruff check src/ tests/`
   - 目标：0 error（warning 记录即可，不阻塞）
   - 如发现 error，先登记到 issue 列表再修（本 issue 不修）

5. **依赖版本清单**：
   - 输出 `pip freeze > tmp/requirements-baseline.txt`
   - 关键依赖标记：simpleeval / pytest / pytest-cov 的具体版本

**不在范围内**：

- 不修复 ruff error
- 不修测试
- 不锁 simpleeval 版本（D5 由 P1-006 负责）

**产物**：
- `docs/audit/phase1-baseline.md`（新建，含上面 5 项的数据）
- `tmp/requirements-baseline.txt`
- `tmp/coverage_html/index.html`

**commit message 模板**：
```
chore(phase1): 建立阶段一基线（依赖/测试/覆盖率/ruff）

- pip install -e .[dev] 成功，simpleeval=X.Y.Z
- pytest 211/211 passed
- 覆盖率：XX%（详见 docs/audit/phase1-baseline.md）
- ruff：N warnings, 0 errors
```

---

## B. 三视角独立审计（Category b）

> 三个审计 issue 在 P1-001 完成后**可并行**执行。
> 三个视角**视角分离**——同一审计人/不同审计人均可，但报告**不混**。
> 三个 issue 完成后由 P1-005 合并。

### P1-002 · 三视角独立审计·架构与代码质量

| 项 | 内容 |
|---|---|
| **ID** | P1-002 |
| **类型** | chore（审计） |
| **估时** | M（约 1-2 天） |
| **依赖** | P1-001（基线 ready） |
| **风险** | LOW |
| **目标** | 从架构与代码质量视角，审计 v0+v1 完工代码，对照 ADR-0001/0003/0004 发现偏离/隐患 |
| **上下文** | 哈尼斯 v1 审计（2026-06-22）已部分覆盖架构视角，但与安全/工程化混在一份报告。本 issue 独立做一次"只关注架构/质量"的审计。 |

**审计范围**：

| 子项 | 关注点 | 对照文档 |
|---|---|---|
| 模块分层 | `src/core/engine/` 内部依赖方向、单向性 | CONTEXT-MAP.md、ADR-0003 §2 决策 2 |
| 循环依赖 | `ast_nodes` / `interpreter` / `executor` / `expr` / `bus` / `protocol` / `main` 之间 | CodeGraph（如可用）或 `pydeps` |
| ADR 一致性 | ADR-0001/0003/0004 的每条决策是否在代码中落实 | 4 份 ADR |
| 命名空间分离 | ID 命名空间 vs 变量命名空间实现 | ADR-0001 §1、§11 #1 |
| 块级作用域 | 修饰器状态清空时机（ADR-0002 D1-confirmed） | ADR-0001 §4.1、§11 #2 |
| NEXT 三阶段 | 声明→竞争→end 锁定 | ADR-0001 §5、§11 #3 |
| 复杂度热点 | 函数圈复杂度 > 15 的 | 哈尼斯审计 §4 |
| 命名规范 | 变量/函数英文、文档/注释中文 | CLAUDE.md |
| 可读性 | docstring 完整性、类型注解完整性 | ruff `ANN` 规则（如启用） |
| 偏差 | 已登记 6 条偏差（D1-D6）的代码侧状态 | ADR-0004 附录 |

**输出文档**：`docs/audit/phase1-audit-architecture.md`（新建）

每条发现必须含：
- 等级：CRITICAL / HIGH / MEDIUM / LOW / INFO
- 位置：文件:行号
- 证据：代码片段或 grep 输出
- 修复建议：高层级（不写具体代码实现，那是 P1-006~009 的活）

**验收标准**：

1. `docs/audit/phase1-audit-architecture.md` 文件存在
2. 至少 5 条发现（可以是 INFO 级别）
3. 每条发现含上述 4 个字段
4. 文件末尾有"视角 1 总结"小节：1-3 句话评价代码架构/质量状态

**不在范围内**：
- 不修复发现的任何问题（修复归 P1-006~009）
- 不重复哈尼斯 v1 审计的发现，除非有新视角
- 不涉及安全沙箱细节（那是 P1-003）

---

### P1-003 · 三视角独立审计·安全与沙箱

| 项 | 内容 |
|---|---|
| **ID** | P1-003 |
| **类型** | chore（审计） |
| **估时** | M（约 1-2 天） |
| **依赖** | P1-001（基线 ready） |
| **风险** | LOW（但发现高危项时升为 MEDIUM） |
| **目标** | 从安全/沙箱视角，审计 v0+v1 完工代码，重点是表达式求值与进程间通信 |
| **上下文** | 哈尼斯 v1 审计 S1/S2/S3 三条安全发现已部分处理。本次独立审视整个 v0+v1 代码库的安全边界。 |

**审计范围**：

| 子项 | 关注点 | 对照文档 |
|---|---|---|
| simpleeval 沙箱 | `BUILTIN_FUNCS` 白名单、AST 节点限制、函数参数限制 | ADR-0003 §2 决策 1 |
| dispatcher 异常捕获 | TypeError 过宽问题（哈尼斯 Q3） | dispatcher.py |
| DSL 长度限制 | 表达式 DoS 防护（哈尼斯 S2） | dispatcher.py |
| 关键字替换 | translator 砍后是否还残留（v1 已砍，确认无残留） | expr/ 子包 |
| 修饰器执行边界 | 修饰器参数是否可注入恶意 payload | interpreter.py `parse_decorator` |
| 进程间序列化 | EngineBus 的 JSON 序列化、跨进程数据流 | bus.py、protocol.py |
| 错误信息泄露 | 异常 traceback 是否包含敏感信息（路径、变量值） | executor.py |
| 变量注入 | `node in` 输入是否做类型/范围检查 | executor.py `_execute_in` |
| 跨章节路由 | `id:endX:chapterYY` 的 chapterYY 是否校验 | executor.py |
| 异常吞并 | 是否有 `except Exception: pass` 类吞错 | 全代码库 grep |
| 死代码 | 哈尼斯 D2/D3 提到但未确认是否仍存在 | errors.py、custom.py |

**输出文档**：`docs/audit/phase1-audit-security.md`（新建）

每条发现必须含：
- 等级：CRITICAL / HIGH / MEDIUM / LOW / INFO
- 位置：文件:行号
- 证据：代码片段或 grep 输出
- 攻击场景：如何被利用（仅描述，不利用）
- 修复建议：高层级

**验收标准**：

1. `docs/audit/phase1-audit-security.md` 文件存在
2. 至少 5 条发现
3. 至少 1 条达到 MEDIUM 或以上等级
4. 每条发现含上述 5 个字段
5. 文件末尾有"视角 2 总结"小节

**不在范围内**：
- 不修复发现的任何问题（修复归 P1-006~009）
- 不做真实攻击（仅描述攻击场景）
- 不涉及测试覆盖（那是 P1-004）

---

### P1-004 · 三视角独立审计·可测试性与工程化

| 项 | 内容 |
|---|---|
| **ID** | P1-004 |
| **类型** | chore（审计） |
| **估时** | M（约 1-2 天） |
| **依赖** | P1-001（基线 ready） |
| **风险** | LOW |
| **目标** | 从可测试性/工程化视角，审计 v0+v1 完工代码的测试质量、CI 友好性、文档同步 |
| **上下文** | 哈尼斯 v1 审计 Q1（硬编码路径）已修。本次独立审视测试设计、mock 难度、fixture 复用、CI 配置。 |

**审计范围**：

| 子项 | 关注点 | 对照文档 |
|---|---|---|
| 测试覆盖 | 单元/集成/e2e 比例、关键路径覆盖 | pytest-cov 报告 |
| 测试隔离 | 是否每个测试独立（不依赖全局状态） | tests/ |
| Mock 难度 | EngineBus / GUI / multiprocessing 是否易 mock | tests/runtime/、tests/integration/ |
| Fixture 设计 | chapter01.md / chapter01_v1.md 是否覆盖语法全集 | ADR-0001 附录 A、ROADMAP §1.1 |
| CI 友好性 | 是否能在干净环境一键跑通 | pyproject.toml、requirements-dev.txt |
| 文档同步 | README / CHANGELOG / 文档是否与代码一致 | README.md、ADR、ROADMAP |
| 提交规范 | commit message / 分支命名是否规范 | git log、CLAUDE.md |
| Issue 跟踪 | 已关闭 issue 是否真的反映了实际功能 | gh issue list |
| 死代码 | 未使用的 import、函数、变量 | 全代码库 |
| 错误处理一致性 | raise 类型、异常 message 风格 | 全代码库 |
| 偏差登记 | ADR-0004 附录的 6 条偏差是否在代码中可见 | executor.py、interpreter.py |

**输出文档**：`docs/audit/phase1-audit-engineering.md`（新建）

每条发现必须含：
- 等级：CRITICAL / HIGH / MEDIUM / LOW / INFO
- 位置：文件:行号
- 证据：测试输出、文件引用
- 修复建议：高层级

**验收标准**：

1. `docs/audit/phase1-audit-engineering.md` 文件存在
2. 至少 5 条发现
3. 覆盖率低的模块（< 80%）单独列出
4. 每条发现含上述 4 个字段
5. 文件末尾有"视角 3 总结"小节

**不在范围内**：
- 不补测试（仅审计）
- 不涉及安全沙箱细节（那是 P1-003）
- 不涉及架构决策（那是 P1-002）

---

### P1-005 · 合并三视角审计报告

| 项 | 内容 |
|---|---|
| **ID** | P1-005 |
| **类型** | chore（文档） |
| **估时** | S（约 0.5 天） |
| **依赖** | P1-002 + P1-003 + P1-004 全部完成 |
| **风险** | LOW |
| **目标** | 将三个视角的发现合并为一份审计报告，作为阶段一的最终审计交付物 |

**输入**：
- `docs/audit/phase1-audit-architecture.md`（来自 P1-002）
- `docs/audit/phase1-audit-security.md`（来自 P1-003）
- `docs/audit/phase1-audit-engineering.md`（来自 P1-004）

**输出**：`docs/audit/v2-independent-audit-pm.md`（新建）

**报告结构**（与哈尼斯 v1 审计保持风格一致）：

```markdown
# Neural Engine 独立审计报告 v2

> **执行人**：XXX（角色/署名）
> **执行日期**：2026-06-XX
> **审计范围**：v0+v1 完工代码（main 分支）
> **关联文档**：
> - 视角 1（架构/质量）：docs/audit/phase1-audit-architecture.md
> - 视角 2（安全/沙箱）：docs/audit/phase1-audit-security.md
> - 视角 3（可测试性/工程化）：docs/audit/phase1-audit-engineering.md
> - v1 哈尼斯审计（前置）：docs/audit/v1-independent-audit-hanice.md

## 1. 执行摘要
（状态表 + 1-2 段总结）

## 2. 视角 1·架构与代码质量
（聚合 phase1-audit-architecture.md 关键发现，去除冗余）

## 3. 视角 2·安全与沙箱
（聚合 phase1-audit-security.md 关键发现）

## 4. 视角 3·可测试性与工程化
（聚合 phase1-audit-engineering.md 关键发现）

## 5. 跨视角综合发现
（多个视角都提到的、特别重要的发现）

## 6. 与 v1 哈尼斯审计的对照
（新发现 vs 已修 vs 仍存）

## 7. 复杂度热点（如有）

## 8. 总体评价
（1-3 段，对 v0+v1 代码做整体评级）

## 9. 新发现 issue 候选
（按优先级列表，每条对应 P1-002/003/004 视角里的发现）

## 附录 A：三视角原始发现清单
（按等级降序列出所有发现）
```

**验收标准**：

1. `docs/audit/v2-independent-audit-pm.md` 文件存在
2. 包含上述 9 个章节 + 附录
3. 引用三份原始视角报告（`phase1-audit-*.md`）
4. 至少 1 条跨视角发现（如适用）
5. 与 v1 哈尼斯审计有显式对照节

---

## C. 修 v1 偏差（Category c）

> 4 条修复 issue 在 P1-001 完成后**可并行**。
> P1-006/007/008 涉及不同文件，可同时进行。
> P1-009 涉及 interpreter/executor，独立窗口。

### P1-006 · 修偏差 D5：锁定 simpleeval 版本

| 项 | 内容 |
|---|---|
| **ID** | P1-006 |
| **类型** | fix（依赖管理） |
| **估时** | S（约 0.5-1 小时） |
| **依赖** | P1-001（确认当前 simpleeval 版本） |
| **风险** | LOW |
| **目标** | 消除 v1 偏差 D5，把 `pyproject.toml` 中 `simpleeval>=1.0` 改为具体版本 |
| **上下文** | 当前 pyproject.toml:13 `"simpleeval>=1.0"`，哈尼斯审计 S3 建议锁定。哈尼斯报告写时是 0.x 版本，现状是 1.x（待 P1-001 确认）。 |

**验收标准**：

1. `pyproject.toml` 第 13 行从 `"simpleeval>=1.0"` 改为具体版本（建议 `~=1.0.X` 或精确版本）
2. 命令 `python3 -m pip install -e .[dev]` 仍成功
3. 命令 `python3 -m pytest tests/ -q` 仍 211 passed
4. 偏差附录 `docs/adr/0004-appendix-deviations.md` §1.2 D5 行更新为"✅ 已修复（阶段一 P1-006，YYYY-MM-DD）"
5. `docs/ROADMAP.md` §2.1 偏差表 D5 行更新为"✅ 已修复"

**commit message 模板**：
```
fix(deps): 锁定 simpleeval 版本（修 v1 偏差 D5）

- pyproject.toml: simpleeval>=1.0 → simpleeval==1.0.X
- 211 tests passed
- 偏差附录 §1.2 D5 标记已修复
```

**不在范围内**：
- 不升级 simpleeval（如需升级走单独 PR）
- 不修改其他依赖

---

### P1-007 · 修偏差 D1：If.cond 显式登记 bool_expr 决策

| 项 | 内容 |
|---|---|
| **ID** | P1-007 |
| **类型** | fix（语义登记） |
| **估时** | S（约 1-2 小时） |
| **依赖** | P1-001 |
| **风险** | LOW |
| **目标** | 消除 v1 偏差 D1，按"路径 A"（推荐）：接受"用 `("expr", ...)` + branches 数量判断"代替 `("bool_expr", ...)` 第三种 kind，但**显式登记**到 ADR + executor 加 defense-in-depth 断言 |
| **上下文** | D1 偏差的本质是类型设计上少了一种 kind。当前实现用 `("expr", ...)` 配 `len(branches) == 2` 判断二元 if，工作正常但缺规范。 |

**验收标准**：

1. **ADR 同步**：
   - `docs/adr/0004-v1-refactor-design.md` §3.3 决策 4 或 §4 阶段 3 增补一行："`("expr", ...)` 配 `len(branches) == 2` 判定二元 if（不再加 `bool_expr` kind）"
   - `docs/adr/0001-v0-baseline-script-spec.md` §11 不变量（如果涉及 If 条件）增补同样说明

2. **代码同步**：
   - `src/core/engine/executor.py::_execute_if` 在 `cond == "expr"` 分支加 `assert len(if_node.branches) in (1, 2), f"二元 if 期望 1-2 个 branches，实际 {len(if_node.branches)}"`
   - 加 1 个单测：覆盖 `len(branches) == 1` 和 `len(branches) == 2` 两种形态
   - 加 1 个负向单测：`len(branches) == 3` 时 assert 失败（或抛 ValueError）

3. **偏差附录**：
   - `docs/adr/0004-appendix-deviations.md` §1.2 D1 行更新为"✅ 已修复（阶段一 P1-007，YYYY-MM-DD，路径 A：接受 + 显式登记）"

4. **ROADMAP**：
   - `docs/ROADMAP.md` §2.1 偏差表 D1 行更新为"✅ 已修复"

5. **回归**：211 tests + 新增 2 个 tests 全过

**commit message 模板**：
```
fix(expr): 显式登记 If.cond 二元判定（修 v1 偏差 D1）

- executor._execute_if 加 assert len(branches) in (1, 2)
- ADR-0001/0004 同步说明：二元 if 用 ("expr", ...) + branches 数量判定
- 新增 2 个单测覆盖正常 + 异常形态
- 213 tests passed（211 + 2）
- 偏差附录 §1.2 D1 标记已修复
```

**不在范围内**：
- 不实现 `bool_expr` 第三种 kind（走路径 B 是 OQ-1 的拍板项，本 issue 默认 A）
- 不动 v0 fixture

---

### P1-008 · 修偏差 D4：收窄 dispatcher 异常捕获

| 项 | 内容 |
|---|---|
| **ID** | P1-008 |
| **类型** | fix（错误处理） |
| **估时** | S-M（约 2-4 小时） |
| **依赖** | P1-001（确认 simpleeval 1.x 实际异常类型） |
| **风险** | MEDIUM（simpleeval API 实际可能不允许收窄） |
| **目标** | 消除 v1 偏差 D4，把 dispatcher.eval 中过宽的 `TypeError` 捕获**按 simpleeval 1.x 实际异常类型收窄** |
| **上下文** | 哈尼斯 Q3 + D4 都指出：dispatcher.eval 当前 `except (TypeError, InvalidExpression) as e`，TypeError 过宽。但 simpleeval 1.x 的实际异常类型可能不支持细分。 |

**实施步骤**：

1. **调查**：
   - 读 simpleeval 1.x 源码（`pip show simpleeval` 找路径）
   - 列出所有抛出的异常类
   - 验证哪些可以细分（`FunctionNotDefined` / `NameNotDefined` / `OperatorNotDefined` / `TypeError` 等）

2. **修改**：
   - 优先收窄到具体异常类（如有）
   - 如确实只能保留 TypeError，则改为 `except TypeError as e: if "Unsupported node type" not in str(e): raise` 之类字符串过滤
   - 如 simpleeval 1.x 仍无干净方案，**fallback**：保持 TypeError 捕获，但**显式登记**到 ADR-0004 偏差附录"simpleeval API 限制无法进一步收窄"——视为接受现状

3. **测试**：
   - 现有 211 tests 仍通过
   - 加 2-3 个新单测：覆盖真实 TypeError（如 `"1" + 1`）vs simpleeval 内部 TypeError 的区分路径
   - 验证 fallback 仍正确触发

**验收标准**（任一达成）：

- **路径 A（推荐）**：异常收窄到具体类，2-3 个新单测全过
- **路径 B（fallback）**：异常未收窄，但显式登记到偏差附录，commit message 写明 simpleeval 1.x 实际异常类型 + 收窄尝试失败原因

不论路径，**必须**：
- 偏差附录 `docs/adr/0004-appendix-deviations.md` §1.2 D4 行更新（"✅ 已修复（路径 A）"或"⚠️ simpleeval API 限制，已尝试登记，路径 B 接受"）
- 211+ tests 全过
- ROADMAP §2.1 偏差表 D4 行更新

**commit message 模板（路径 A）**：
```
fix(expr): 收窄 dispatcher 异常捕获（修 v1 偏差 D4）

- dispatcher.eval: except TypeError → except (FunctionNotDefined, NameNotDefined, OperatorNotDefined, InvalidExpression)
- 保留 fallback 到 TypeError 但通过 str(e) 过滤
- 新增 3 个单测覆盖真实 TypeError vs 沙箱 TypeError
- 214 tests passed
- 偏差附录 §1.2 D4 标记已修复
```

**不在范围内**：
- 不升级 simpleeval
- 不改错误类层次（errors.py）

---

### P1-009 · 修偏差 D2：实现 G5 修饰器结构化参数（MVP）

| 项 | 内容 |
|---|---|
| **ID** | P1-009 |
| **类型** | feat（DSL 扩展） |
| **估时** | L（约 1-2 天） |
| **依赖** | P1-001, P1-002（参考架构审计发现） |
| **风险** | MEDIUM（涉及解析器 + AST + executor，可能引入新偏差） |
| **目标** | 消除 v1 偏差 D2，让 `@style key:[a,b,c]` 形式可解析（MVP：仅顶层列表，不嵌套） |
| **上下文** | G5 是 ADR-0004 §4 阶段 4 的一部分，完整语法是 `@style text:[rgb:red,Px:12],bgm:start:1.mp3`。v1 阶段未实现。本次走 MVP：仅顶层参数值为列表。 |

**MVP 范围**：

- ✅ 支持：`@style text:[rgb:red,Px:12]` —— `text` 值为 `["rgb:red", "Px:12"]`
- ✅ 支持：`@style keys:[a,b,c],bgm:rain.mp3` —— 多个 key 混合
- ❌ 不支持：`@style text:[[a,b],c]` —— 嵌套
- ❌ 不支持：`@style text:[{a:1}]` —— 字典
- ❌ 不支持：`@style text:[a, [b, c]]` —— 嵌套列表

**实施步骤**：

1. **AST 扩展**：
   - `src/core/engine/ast_nodes.py::DecoratorCall`
   - 当前 `args: tuple[str, ...]` 扩展为 `args: tuple[str | list[str], ...]`
   - 或新增 `args_v2: tuple[...]` 字段（更保守，不破坏现有）
   - **建议**：保守做法——新增 `args_v2`，旧 `args` 保留兼容

2. **解析器**：
   - `src/core/engine/interpreter.py::parse_decorator`
   - 检测参数值是否以 `[` 开头、`]` 结尾
   - 若是：去掉首尾 `[` `]`，按 `,` 拆分
   - 否则：旧逻辑（字符串值）

3. **Executor 适配**：
   - `src/core/engine/executor.py::_emit_decorator`
   - 列表值展开为多个 sub-event 或保持 list 传给 GUI
   - **建议**：保持 list 传给 GUI，GUI 端再展开（与 v0 风格"广播即可"一致）

4. **协议**：
   - `src/core/engine/protocol.py::DecoratorEvt`
   - 确认 JSON 序列化支持 list（应当已支持）

5. **测试**：
   - 现有 211 tests 仍通过
   - 新增 4-6 个单测：
     - 解析：`@style key:[a,b,c]` → `args_v2 == ["a", ["b", "c"]]`（或等价的 list 结构）
     - 解析：`@style key1:v1, key2:[a,b]` 混合
     - 解析：`@style key:[a]` 单元素列表
     - 解析：`@style key:a,b,c` 旧格式（无变化）
     - 解析：负向 — `@style key:[[a,b]]` 嵌套 → 抛 ParseError
     - 执行：`DecoratorEvt` 广播包含 list 参数

6. **Fixture**：
   - `chapters/chapter01_v1.md` 加一个新块演示 `@style text:[rgb:red,Px:12]`
   - 或新建 `chapters/chapter01_v1_g5.md`

7. **ADR 同步**：
   - `docs/adr/0004-v1-refactor-design.md` §4 阶段 4 标注"✅ MVP 已实现"
   - `docs/adr/0004-appendix-deviations.md` §1.2 D2 行更新为"✅ 已修复（MVP，阶段一 P1-009）"

**验收标准**：

1. `@style text:[rgb:red,Px:12]` 解析成功，AST 中 `args_v2` 包含 `["rgb:red", "Px:12"]`
2. `python3 -m pytest tests/ -q` 输出 `215+ passed, 0 failed`
3. `python3 -m core.engine.main chapters/chapter01_v1.md`（如 fixture 扩展）跑通
4. 偏差附录 D2 行更新为已修复
5. ROADMAP §2.1 偏差表 D2 行更新

**commit message 模板**：
```
feat(decorator): G5 修饰器结构化参数 MVP（修 v1 偏差 D2）

- ast_nodes.DecoratorCall 新增 args_v2: tuple[str | list[str], ...]
- interpreter.parse_decorator 支持 [a,b,c] 列表参数
- executor._emit_decorator 透传 list 到 GUI（不展开）
- 新增 5 个单测 + chapter01_v1_g5 fixture
- 216+ tests passed
- 偏差附录 §1.2 D2 标记已修复
```

**不在范围内**：
- 不做嵌套（OQ-2 拍板项，默认 MVP）
- 不做 GUI 端展开
- 不改 BUILTIN_FUNCS
- 不动 v0 fixture

---

## D. 收尾

### P1-010 · 阶段一回归与文档同步

| 项 | 内容 |
|---|---|
| **ID** | P1-010 |
| **类型** | chore（验收） |
| **估时** | S（约 2-4 小时） |
| **依赖** | P1-005（审计合并完成）+ P1-006/007/008/009（4 偏差修复完成） |
| **风险** | LOW |
| **目标** | 阶段一最终回归：所有测试通过 + ruff 0 error + 文档全部同步 + 验收清单走完 |
| **上下文** | 4 偏差修复 + 3 审计 + 1 合并报告完成后，需要一次完整回归确保互相不冲突。 |

**验收标准**：

1. **测试**：
   - `python3 -m pytest tests/ -q` 输出 `215+ passed, 0 failed`（基线 211 + 修复期间新增）
   - 覆盖率不低于基线（`docs/audit/phase1-baseline.md` 记录的数字）

2. **Lint**：
   - `ruff check src/ tests/` 输出 `0 errors`
   - warning 不阻塞但记录到 `docs/audit/phase1-baseline.md` 末尾

3. **文档同步清单**（全部必须更新）：

   | 文档 | 更新内容 | 触发 issue |
   |---|---|---|
   | `docs/adr/0004-appendix-deviations.md` | D1/D2/D4/D5 行更新为已修复 | P1-006/007/008/009 |
   | `docs/ROADMAP.md` §2.1 | 偏差表 D1/D2/D4/D5 行更新为已修复 | P1-006/007/008/009 |
   | `docs/ROADMAP.md` §2.2 | 远期表 F4 / G5（如实现）状态更新 | P1-009 |
   | `docs/ROADMAP.md` §3 | 新发现的 issue 候选（来自 P1-005 合并报告） | P1-005 |
   | `README.md` | 状态表 v0 偏差行 / v1 偏差行更新 | 全部修复 |
   | `docs/audit/v2-independent-audit-pm.md` | 确认存在且最新 | P1-005 |

4. **Git 状态**：
   - 5 个 commit（4 修复 + 1 基线）独立可读
   - 分支命名符合 `fix/xxx` / `chore/xxx` 规范（CLAUDE.md）
   - commit message 中文 + 符合规范

5. **最终报告**：
   - 在 `docs/audit/phase1-summary.md`（新建）写一份阶段一总结：
     - 阶段一目标 vs 实际达成
     - 4 偏差修复状态
     - 审计关键发现（CRITICAL/HIGH 级）
     - 阶段二（v2 P0）建议

**不在范围内**：
- 不做新功能
- 不推到原仓 GitHub（owner 指示）
- 不发 GitHub release

**commit message 模板**：
```
chore(phase1): 阶段一回归 + 文档同步

- 215+ tests passed, ruff 0 errors
- 文档同步：偏差附录 / ROADMAP / README
- 新建 docs/audit/phase1-summary.md 阶段总结
- 阶段一验收：✅
```

---

## 附录 A：估时汇总

| 类别 | 编号 | 估时 | 实际（待填） |
|---|---|---|---|
| A. 基线 | P1-001 | L (0.5-1 天) | |
| B. 审计 | P1-002 | M (1-2 天) | |
| B. 审计 | P1-003 | M (1-2 天) | |
| B. 审计 | P1-004 | M (1-2 天) | |
| B. 审计 | P1-005 | S (0.5 天) | |
| C. 修复 | P1-006 | S (0.5-1 小时) | |
| C. 修复 | P1-007 | S (1-2 小时) | |
| C. 修复 | P1-008 | S-M (2-4 小时) | |
| C. 修复 | P1-009 | L (1-2 天) | |
| 收尾 | P1-010 | S (2-4 小时) | |
| **合计** | | **5-7 个工作日** | |

## 附录 B：与 PDR 的对应关系

| PDR 章节 | 对应 issue |
|---|---|
| §2 目标 P0 #1 三视角独立审计 | P1-002/003/004 + P1-005 |
| §2 目标 P0 #2 修 4 条 v1 偏差 | P1-006/007/008/009 |
| §2 目标 P1 #1 全量回归 | P1-010 |
| §2 目标 P1 #2 基线指标量化 | P1-001 |
| §2 目标 P2 审计发现并入 ROADMAP | P1-010 |
| §3.1 A 项目基线建立 | P1-001 |
| §3.1 B 三视角独立审计 | P1-002/003/004 + P1-005 |
| §3.1 C 修复 v1 偏差（4 条） | P1-006/007/008/009 |
| §4.1 硬性验收 1-5 | P1-001（1） + P1-005（2） + P1-006/007/008/009（3） + P1-010（4） + P1-010（5） |
| §6 决策 1 审计与修复并行 | P1-002/003/004 并行 P1-006/007/008 |
| §6 决策 2 D1 路径 A | P1-007 |
| §6 决策 3 D2 MVP | P1-009 |
| §6 决策 4 审计文档格式 | P1-002/003/004 + P1-005 |
| §6 决策 5 覆盖率基线 | P1-001 |
| §8.2 可并行 issue | P1-002/003/004 + P1-006/007/008 |
| §8.3 关键里程碑 M1-M5 | P1-001（M1） + P1-002/003/004（M2） + P1-005（M3） + P1-006/007/008/009（M4） + P1-010（M5） |
| §9 Open Questions OQ-1 | P1-007（默认路径 A） |
| §9 Open Questions OQ-2 | P1-009（默认 MVP） |
| §9 Open Questions OQ-3 | P1-008（默认接受 fallback） |
| §9 Open Questions OQ-4 | P1-002/003/004（默认只覆盖生产代码） |
| §9 Open Questions OQ-5 | P1-001（默认不要求 mypy） |
| §9 Open Questions OQ-6 | P1-010（默认需要签字） |
| §9 Open Questions OQ-8 | P1-005（默认进入 v2 P0 候选） |

---

*阶段一拍板后，PM 按本表分派 issue。P1-001 必须先完成，P1-010 必须最后完成。*
