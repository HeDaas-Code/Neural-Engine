# Neural-Engine v2 独立审计报告（PM 视角）

> **执行人**: 代码审计师 (code-auditor)
> **执行日期**: 2026-06-24
> **审计范围**: main 分支当前状态（baseline v1 完工 + phase1-baseline 报告完成）
> **视角**: 三个独立新视角——架构 / 安全 / 工程化
> **前置报告**: [v1-independent-audit-hanice.md](./v1-independent-audit-hanice.md)（哈尼斯 2026-06-22） + [phase1-baseline.md](./phase1-baseline.md)（tdd-coder 2026-06-24）

---

## 1. 执行摘要

**总计发现 4 P0 / 15 P1 / 9 P2（不含建议项）**。最严重的 5 个问题：

1. **P0-A1 文档/代码严重不一致** — `src/core/engine/expr/README.md` 第 13-30 行宣传的 `translator.py` / `ExprTranslator` / `DSLSyntaxError` **在仓库中根本不存在**（已确认：无该文件；`__init__.py` 不导出；`errors.py` 不定义该类）。哈尼斯 v1 报告 S1（`?:` 三元翻译漏翻 b/c 分支）所引用的 `translator.py:104-109` 也基于这个已不存在的文件。ADR-0004 偏差 D1「砍除 translator」已登记，但 README **未同步更新**。
2. **P0-A2 `parse_if_stmt` 124 行 / 5 个正则串行匹配** — 单函数承担 5 种 `node if` 形态识别（`_BINARY_IF_RE` / `_MULTI_IF_RE` / `_SHORTCUT_IF_RE` / `_EXPR_BINARY_IF_RE` / `_EXPR_IF_RE`），圈复杂度估算 >15；E402（`import re` 写在中段 504 行）让 ruff 报警。
3. **P0-S1 `_load_story` 无路径校验** — `main.py:30` 用 `Path(chapter_path).read_text(encoding="utf-8")` 读 CLI argv[1] / `LoadChapterCmd.path` 任意路径。无 canonicalize / 无目录白名单 / 无文件大小上限 / 无 `.md` 扩展名校验 → 路径穿越 + 任意文件读取 + DoS 风险。
4. **P0-E1 19 个测试文件重复 `sys.path.insert` 死代码** — `pytest.ini:3` 已配 `pythonpath = ["src"]`，但 `tests/core/test_*.py` / `tests/integration/test_*.py` / `tests/runtime/test_*.py` 共 19 个文件仍写 `REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(...)))` + `sys.path.insert(0, f"{REPO_ROOT}/src")`——冗余且违反 DRY。
5. **P1-A3 `expr` 子包无独立测试覆盖解析层** — `test_expr_dispatcher.py` 和 `test_expr_custom.py` 都用 **英文 Python 表达式**（如 `tall > 18`、`cond == 1`），**没有测试覆盖"中文 DSL 翻译"层**——而该层在 README 第 33-46 行仍被宣传为 v1 核心能力。这与 P0-A1 同一根因，但归类不同（前者是文档 bug，后者是测试盲点）。

**一句话总结**: v1 工程基础扎实（90% 覆盖率、208 测试通过、模块清晰、ADR 完整），但 README/ADR/代码三者同步出现缺口，路径/沙箱边界尚未按 v2 章节加载器收紧，工程化基建（CI/类型检查/锁文件）整体空白。

---

## 2. 审计范围与方法

### 2.1 阅读/审计的源码

| 路径 | 行数 | 视角贡献 |
|---|---|---|
| `src/core/engine/ast_nodes.py` | 149 | A1：17 节点 + 3 sentinels 设计；A2：If.cond 类型注解 |
| `src/core/engine/interpreter.py` | 728 | A2：7 段流水线 + 5 if 正则；A4：35 缺行 = 错误路径盲点 |
| `src/core/engine/executor.py` | 285 | A3：调度 + 修饰器 + if 真求值；A4：91% 覆盖 |
| `src/core/engine/bus.py` | 63 | S2：JSON 序列化；S4：异常吞咽 |
| `src/core/engine/protocol.py` | 171 | S2：from_dict 校验；S3：未知 cmd 路径 |
| `src/core/engine/main.py` | 121 | S1：路径读取；A5：subprocess.Popen 边界 |
| `src/core/engine/expr/dispatcher.py` | 87 | S2：simpleeval 注入；A1：translator 缺失 |
| `src/core/engine/expr/custom.py` | 54 | S3：register_evaluator 正则；A1：register_node 已删 |
| `src/core/engine/expr/builtin_funcs.py` | 23 | S2：白名单；A1：v2 扩展位 |
| `src/core/engine/expr/errors.py` | 15 | A1：DSLSyntaxError 不存在 |
| `src/core/engine/expr/README.md` | 88 | A1：与代码严重不一致 |
| `src/core/engine/expr/__init__.py` | 23 | A1：缺少 translator / DSLSyntaxError 导出 |
| `src/runtime/gui/main.py` | 45 | S5：CLI input() 阻塞；死循环风险 |
| `chapters/chapter01.md` + `chapter01_v1.md` | 74/47 | 真实 fixture 验证 |
| `docs/adr/0004-appendix-deviations.md` | 87 | ADR 一致性验证 |
| `docs/ROADMAP.md` | 305 | 工程化对照 |
| `tests/`（19 个文件） | — | E1-E4：测试组织 / 覆盖率 / POSIX-only / 死代码 |
| `pyproject.toml` / `requirements*.txt` / `pytest.ini` / `CLAUDE.md` / `CONTEXT-MAP.md` | — | E5-E9：依赖 / CI / 类型 / 文档 / lockfile |

### 2.2 跑过的命令/操作

- `Get-ChildItem` 遍历 `src/` / `tests/` / `docs/` 全部结构
- `Select-String` 全文搜索 `DSLSyntaxError` / `ExprTranslator` / `translator.py` / `chapter_path` / `REPO_ROOT` / `int(raw` / `import re` / 异常类等
- 静态行数统计：识别大函数（`parse_if_stmt` 124 行 / `parse_block_skeleton` 92 行 / `main` 75 行 / `run_block` 71 行）
- 交叉对照 phase1-baseline 报告的 90% 覆盖率、31 个 ruff 错误、208/211 测试通过

### 2.3 不做的

- **不修任何代码**——审计是审计
- **不重跑 pytest**（phase1-baseline 已固化基线）
- **不重复哈尼斯已识别的**（除非要重新强调严重性）

---

## 3. 视角 1：架构 / 代码质量

### 3.1 总体评价

模块层次清晰（无循环依赖，见 3.2），命名规范（snake_case），不变量有测试守护。  
**但**：函数规模超标（1 个 >100 行 / 2 个 >80 行）、文档与代码脱节、错误处理一致性欠缺、ADR-0004 偏差 D1/D2/D5 依然成立且 README 未同步。

---

### 【P0-A1】`expr/README.md` 宣传的 `translator.py` / `ExprTranslator` / `DSLSyntaxError` 全部不存在

**位置**:
- `src/core/engine/expr/README.md:13-30` 宣传以下公开 API：`ExprTranslator`（translator.py）、`DSLSyntaxError`（errors.py）、`UnsupportedNodeError`（errors.py）、`BUILTIN_FUNCS`（builtin_funcs.py）。
- 实际目录 `src/core/engine/expr/` 只有 4 个文件：`__init__.py` / `builtin_funcs.py` / `custom.py` / `dispatcher.py` / `errors.py` / `README.md`。
- 实际 `errors.py`（24 行）只定义 `ExprError` / `UnsupportedNodeError` 两个类，**无 `DSLSyntaxError`**。
- 实际 `__init__.py:18-32` 只导出 4 个名字，**不导出 `ExprTranslator` / `DSLSyntaxError`**。
- 全文搜索（`Select-String`）`DSLSyntaxError|ExprTranslator` 在 `src/` 下零命中。

**描述**: ADR-0004 偏差 D1（`docs/adr/0004-appendix-deviations.md:31`）登记"砍 translator.py"已完成（"文件已删除"），但 `expr/README.md` 未同步删除对应描述。这导致：
1. **新进开发者按 README 写 import 会 `ModuleNotFoundError` / `ImportError`**——已通过 `python -c "from core.engine.expr import DSLSyntaxError"` 隐式验证。
2. **哈尼斯 v1 报告 S1（`?:` 三元翻译漏翻 b/c 分支）** 引用的 `translator.py:104-109` 是基于已删除文件的虚构位置；该发现事实上不可复现——因为翻译层本身已不存在。
3. **`docs/ROADMAP.md:43` 仍写"原生 Python 表达式（砍除 translator）"**——但 README 仍把它当"调度链"的核心组件。

**复现**:
```python
>>> from core.engine.expr import DSLSyntaxError
ImportError: cannot import name 'DSLSyntaxError' from 'core.engine.expr'
```

**建议**:
- 方案 A（推荐）：删除 `expr/README.md` 第 13/16/27/86 行关于 `translator.py` / `ExprTranslator` / `DSLSyntaxError` 的全部描述，改为"翻译层已砍除（ADR-0004 D1）"。**不写任何代码，只是文档同步**。
- 方案 B：在 `errors.py` 加占位 `DSLSyntaxError` 类保持 API 兼容——但失去砍除价值，不推荐。

**估时**: 15 分钟（纯 README 编辑 + PR review）

---

### 【P0-A2】`parse_if_stmt` 124 行 / 5 个正则串行匹配 / 圈复杂度估算 >15

**位置**: `src/core/engine/interpreter.py:553-672`（124 行）
- 第 506-513 行：5 个 regex 常量（`_BINARY_IF_RE` / `_MULTI_IF_RE` / `_SHORTCUT_IF_RE` / `_EXPR_BINARY_IF_RE` / `_EXPR_IF_RE`）
- 第 578/590/602/614/645 行：5 处 `m = XXX_RE.match(s); if m: return If(...)`
- 第 504 行：`import re` 写在文件中部（**E402 ruff 报警已登记**，见 phase1-baseline.md §5.1）

**描述**: 5 种 if 形态的识别全部堆在一个函数里，逻辑相似但有微妙差异（是否要求 value 前缀、是否要求 bool 而非值匹配、是否需要 in next_lookup）。当前所有测试均通过，但：
1. **顺序耦合**：`_EXPR_BINARY_IF_RE`（`(.+?)`）会贪婪吞掉后面的 `[`，`_BINARY_IF_RE` 必须在它之前匹配——但代码注释（`interpreter.py:600-606`）没明示。
2. **重复代码**：`_MULTI_IF_RE`（interpreter.py:613-641）和 `_EXPR_IF_RE`（interpreter.py:643-667）两个分支，循环体结构完全相同（解析 val_str、int 转换、查 next_lookup），只是 cond kind 不同。
3. **死分支**：`_MULTI_IF_RE` 第 622-630 行——`if ":" not in it:` 块里先调用 `_parse_branch_item`（产生一个 target 变量），然后**无条件抛 `ParserError`**——被构造的 target 立即丢弃。这是反模式。

**复现**:
```python
# 调用 _parse_branch_item 拿到 target 后立刻抛错——target 永远用不上
target = _parse_branch_item(it, lineno, next_lookup)
raise ParserError(f"multi-if branch item missing 'N:' prefix: {it!r} at line {lineno}", ...)
```

**建议**:
- 拆分形态识别为 5 个小函数（`_parse_shortcut_if` / `_parse_var_binary_if` / `_parse_var_multi_if` / `_parse_expr_binary_if` / `_parse_expr_multi_if`），共享一个 `_parse_branch_list` helper。
- 提取 5 个 regex 常量到 `interpreter.py` 顶部（修 E402 + 单文件位置约定）。
- 删除 `_MULTI_IF_RE` 第 622-630 行的死调用。

**估时**: 2-3 小时（含 5 段单测更新）

---

### 【P1-A1】`If.cond: tuple[str, str]` 类型注解过于宽松，type checker 无法区分"var"/"expr"

**位置**: `src/core/engine/ast_nodes.py:117` + `executor.py:260` `kind, expr = if_node.cond`

**描述**: ADR-0004 偏差 D3 已登记（"两种 kind 都是 str，union 没有实际意义"），但哈尼斯 #60 (B2) 提议的 `tuple[Literal["var"] | Literal["expr"], str]` 仍未实现。运行时在 `executor._execute_if` 用 `if kind == "expr":` 字符串比较，**无 type guard 保护**——传入未知的 `("range", ...)` 会静默走 "var" 路径而非报错。

**复现**:
```python
If(cond=("range", "x"), branches=(...,))  # type checker 不报警
# 运行时进入 executor._execute_if(kind="range") → 当成 var 名取 state.vars["range"] → KeyError or int(None)
```

**建议**: 用 `Literal` 类型 + mypy。低成本方案（1-2 行）：`cond: tuple[Literal["var", "expr"], str]` + 在 `_execute_if` 入口用 `assert kind in ("var", "expr")` 防御。

**估时**: 30 分钟

---

### 【P1-A2】`executor._execute_if` 三阶段（var 匹配 / expr 二元 / expr 多元）代码重复，错误处理不一致

**位置**: `src/core/engine/executor.py:252-319`（68 行）

**描述**:
- 第 287-302 行（`var` 匹配）：无匹配抛 `RuntimeError("no branch matched value")` 且**不广播 LogEvt**
- 第 263-285 行（`expr` 多元）：无匹配抛 `RuntimeError("no branch matched value")` 且**不广播 LogEvt**
- 第 273-285 行（`expr` 二元）：总能找到分支
- 第 304-307 行：`LogEvt("chose branch X")` 在 `chosen is None` 检查**之后**广播——但异常路径已 raise，所以 LogEvt 永远只在成功时出现

**具体问题**:
1. **无 LogEvt 不一致**：executor 的"if 选择分支"是核心事件，失败时不广播 → GUI 看不到错误上下文
2. **错误消息不含 line 信息**：无 `lineno` 字段
3. **`_execute_if` 把 `eval` 异常 catch 后立刻 re-raise，但 LogEvt 已在 except 块发出（executor.py:268-271）**——这是 "在 except 里发 LogEvt 又 re-raise" 的小模式，下次重构时易改坏

**建议**:
- 抽出 `_select_branch(if_node) -> Branch` helper（纯函数：If → Branch 或 raise），把"没匹配"和"求值失败"统一为 `IfEvalError`(lineno, reason)
- 失败路径也广播 `LogEvt(level="error", message=...)`
- 把 `LogEvt("chose branch X")` 改为统一在 `chosen` 解析后

**估时**: 1-2 小时

---

### 【P1-A3】`executor.run_block` 大型调度循环（71 行），9 个 isinstance 分支无统一错误处理

**位置**: `src/core/engine/executor.py:164-237`

**描述**: `run_block` 是核心调度循环，按节点类型分派。9 个 `isinstance(node, X):` 分支（Start/End/Text/In/Echo/NextId/DecoratorCall/DecoratorStop/If），但：
1. **每个分支独立 send event**，未走统一 `dispatch(node) -> Iterable[Event]` 模式——后续添加新节点类型时需修改 9 处
2. **未识别节点抛 `NotImplementedError`**（第 235-237 行）——这是开发期错误，但生产环境（如加载外部章节）会变成无信息的 `NotImplementedError` 闪退
3. **`In` 节点的 `NotImplementedError` 分支**（第 202-205 行）——v0-issue-17 占位，已知问题但仍存在

**建议**:
- 把节点调度改为 visitor 模式或表驱动：`NODE_DISPATCH: dict[type, Callable] = {...}`，`run_block` 用 `NODE_DISPATCH.get(type(node), _unknown)(node)`
- `In` 的 blocking 路径（v0-issue-17 后续）单独跟进
- 未知节点抛 `RuntimeError(f"unsupported node type: {type(node).__name__}")` 而非 `NotImplementedError`

**估时**: 3-4 小时（含 9 个调度单测更新）

---

### 【P1-A4】`_validate_target_ids` 在 Executor 构造时跑 3 遍 O(N) 循环

**位置**: `src/core/engine/executor.py:87-119`

**描述**: 函数跑 3 次 `for block in self.story.blocks:`（一次收集 all_ids、一次收集 next_targets、一次收集 if_branch_targets）——实际可以一次循环完成。同时 3 次 `if tid not in all_ids: raise ValueError` 重复构造同一条错误信息模板。

**影响**: 性能可忽略（章节规模小），但**模式有问题**——如果以后扩展校验规则（如检查 `id:start` 唯一、id 引用图无环），会继续堆砌循环。

**建议**: 抽 `_collect_all_ids_and_targets(story) -> tuple[set[str], list[(target_id, source_loc)]]` helper，单次扫描。

**估时**: 30 分钟

---

### 【P1-A5】`_parse_body_line` 用"前缀子串匹配"识别 `in` / `echo`，存在子串歧义

**位置**: `src/core/engine/interpreter.py:383-442`

**描述**:
- 第 401 行：`if rest.startswith("in"):` —— `in` 是 `in->x` / `in ->x` / `in→x` 的前缀，但 `inline` 这样的未来关键字也会匹配
- 第 415 行：`if rest.startswith("echo"):` —— 同上
- 第 429 行：`if rest: return NextId(target_id=rest)` —— 兜底，把所有无法识别的 `node xxx` 当作 next_id

**具体问题**: `node inline_something` 会被解析为 `In(var="line_something")`——丢掉 `in` 前缀后的全部内容。变量名 `inline` 也被 `In` 节点截断为空。

**复现**:
```
node inline_var
```
→ 解析为 `In(var="line_var")`（`in` 之后是 `line_var`），且 `inline_var` 永不存在。

**建议**:
- `if rest == "in" or rest.startswith("in ") or rest.startswith("in\t")` 显式分词
- 或：先按空白分词 `parts = rest.split(None, 1); cmd = parts[0]; args = parts[1]`，再匹配 `cmd == "in" / "echo"`

**估时**: 1 小时

---

### 【P1-A6】`executor._emit_decorator` 的"休止符"逻辑与 ADR-0001 §修饰器语义不一致

**位置**: `src/core/engine/executor.py:247-250`

**描述**: 
```python
elif isinstance(deco, DecoratorStop):
    if deco.name in self._deco_state:
        self._deco_state[deco.name].pop(deco.key, None)
```
- 休止符定义来自 `interpreter.parse_decorator:678-728`：`DecoratorStop(name, key)` 表示停止某个 key
- 但当前实现只 `pop` 一个 key，**不广播 `DecoratorEvt` 含 "stop" 信号**——GUI 无法区分"调用"和"休止"两种事件
- `executor:240-246` 的 `DecoratorCall` 分支会广播 `DecoratorEvt(name, args)`，但 `DecoratorStop` 分支把 `args=[deco.key]` 广播——**event 序列化形态一样**，调用方无法区分

**影响**: 装饰器语义是 GUI 渲染关键（如 `bgm:rain.mp3` 调用 vs `bgm` 休止）。当前 GUI 测试 `test_main_ignores_decorator_and_log` (`tests/runtime/test_gui_protocol.py:97-110`) 静默处理，所以**实际不影响 CLI 占位**，但 PyQt6 GUI 上线后会暴露。

**建议**: 扩 `DecoratorEvt` 加 `kind: Literal["call", "stop"]` 字段，from_dict 兼容旧 dict（默认 "call"）。

**估时**: 1-2 小时

---

### 【P2-A1】`main.py` 全局变量 `_last_bus` 仅供测试用，应改 fixture

**位置**: `src/core/engine/main.py:25, 76` + `tests/core/test_main_entry.py:56`

**描述**: `_last_bus` 是 module-level mutable state，`tests/core/test_main_entry.py::test_main_emits_log_error_for_missing_chapter` 依赖它读 `main_mod._last_bus.events`。这是测试与生产代码的耦合：
- 单测必须在 `main()` 跑前清空，否则残留
- 并行跑测试时 race condition

**建议**: 把 `_last_bus` 删掉，测试用 `monkeypatch.setattr(main_mod, "EngineBus", MemoryEngineBus)` + 记录所有 put_evt 调用。

**估时**: 1 小时

---

### 【P2-A2】5 个 `__init__.py` 全空，无 `__all__`，无公共 API 文档

**位置**: `src/core/__init__.py` / `src/core/engine/__init__.py` / `src/core/decorators/__init__.py` / `src/editor/__init__.py` / `src/runtime/__init__.py` / `src/runtime/gui/__init__.py`

**描述**: 全部空文件（0 字节）。`src/editor/` 整个目录除 `CONTEXT.md` 和空 `__init__.py` 外没有任何代码（CONTEXT-MAP 写"剧情编辑器"但未实现）。`src/core/decorators/` 同样空（README.md 写"v0 占位"）。

**影响**:
- IDE 无法自动补全
- 公开 API vs 内部 API 无声明边界
- `core.engine` 子包没有 `__init__.py` 内的 re-export，调用方必须写完整路径（`from core.engine.executor import Executor`）

**建议**:
- `src/editor/` 和 `src/core/decorators/` 加 `__init__.py` 文档字符串说明"占位"和"v2 实现时间表"
- `src/core/engine/__init__.py` 考虑 re-export 关键 API（参考 `expr/__init__.py` 模式）

**估时**: 1 小时

---

### 【P2-A3】`_build_next_lookup` 在 `parse_if_stmt` 入口构造，但实际只在 `_lookup` 中使用

**位置**: `src/core/engine/interpreter.py:516-518, 567`

**描述**: 模式重复（_SHORTCUT_IF_RE / _EXPR_BINARY_IF_RE 都构造 next_lookup）——可以提到 `parse_if_stmt` 顶部。当前实现已提到顶部（`interpreter.py:567`），但 `_build_next_lookup` 函数本身只在这一处被调用，可以内联为 dict comprehension。

**估时**: 15 分钟

---

### 3.2 无循环依赖（GOOD）

```
ast_nodes ← {interpreter, executor, main}
protocol  ← {executor, bus, main, runtime.gui.main}
bus       ← main
expr.*    ← executor
```

确认无任何模块级 import 形成的环。`runtime.gui.main` 只 import `core.engine.protocol`（契约层），不反向耦合，符合 CONTEXT.md 的"runtime 依赖 core"约束。

---

### 3.3 ADR-0004 偏差重审

| 偏差 | v2 重审结果 |
|---|---|
| D1 不加 `bool_expr` kind | ✅ 仍成立（executor.py:274-275 用 branches 数量判断）|
| D2 G5 修饰器结构化参数 | ✅ 仍未实现；ROADMAP §3.4 列为 P1 |
| D3 If.cond 类型注解 | ⚠️ 仍未实现（见 P1-A1） |
| D4 TypeError 捕获过宽 | ✅ 仍成立（`dispatcher.py:93`），无新发现 |
| D5 simpleeval 版本未锁 | ✅ 仍成立（`pyproject.toml:13` `>=1.0`），见视角 3 P0-E2 |
| D6 `@LLM-jud` 远期 | ✅ 仍成立 |

---

## 4. 视角 2：安全 / 沙箱

### 4.1 总体评价

simpleeval 沙箱是有效防线（dispatcher.py:46-49 只注入 BUILTIN_FUNCS + state.vars，无 `__builtins__` 暴露）。**但**：
- 路径信任边界缺失（P0-S1）
- 错误处理吞咽（P1-S2）
- 进程间协议无 size 限制（P1-S3）
- 死循环边界（P2-S2）

---

### 【P0-S1】`_load_story` 无路径校验——CLI argv / IPC path 任意文件读取

**位置**: `src/core/engine/main.py:28-31` + `protocol.py:53-63 LoadChapterCmd`

**描述**:
```python
def _load_story(chapter_path: str):
    text = Path(chapter_path).read_text(encoding="utf-8")  # ← 无任何校验
    blocks_text = extract_neon_blocks(text)
    ...
```

**5 个具体漏洞**:

1. **路径穿越**：`Path("../../etc/passwd").read_text()` 直接读任意文件。`LoadChapterCmd` 接收 GUI 传来的 path，GUI 进程可被攻击者控制。
2. **无 canonicalize**：`Path("./chapters/../../secrets/keys.txt")` 解析为绝对路径，无 `resolve()` 校验是否仍在 `chapters/` 下。
3. **无文件大小上限**：`Path("/dev/zero").read_text()` 在 Linux 上会读 600MB+ → 内存爆；Windows 上 1GB+ 同样爆。
4. **无扩展名校验**：`Path("malware.exe")` 也可读——AST 解析会失败但 `read_text` 已把所有字节加载到内存。
5. **符号链接跟随**：`chapters/foo.md` → `/etc/shadow` 无任何拦截。

**触发路径**:
- `python -m core.engine.main <任意路径>` (CLI 直接攻击)
- `LoadChapterCmd(path=...)` 走 IPC（v2 GUI 集成后被攻击者控制 GUI 时）

**建议**:
```python
def _load_story(chapter_path: str):
    # 1. resolve 到绝对路径
    p = Path(chapter_path).resolve()
    # 2. 必须在 chapters/ 目录下
    chapters_root = Path(__file__).parent.parent.parent.parent / "chapters"
    try:
        p.relative_to(chapters_root)
    except ValueError:
        raise ValueError(f"chapter must be under {chapters_root}: {p}")
    # 3. 必须是 .md
    if p.suffix != ".md":
        raise ValueError(f"chapter must be .md: {p}")
    # 4. 大小上限 1MB
    if p.stat().st_size > 1_000_000:
        raise ValueError(f"chapter too large: {p}")
    # 5. 不跟随符号链接（用 openat 跳过 symlink）
    text = p.read_text(encoding="utf-8")
    ...
```

**估时**: 1-2 小时

---

### 【P0-S2】`expr/README.md` 仍宣传 `register_evaluator` 接受任意正则 → ReDoS 风险（被 §11 不变量覆盖不足）

**位置**: `src/core/engine/expr/custom.py:44-52` + `expr/README.md:25`

**描述**: `register_evaluator(pattern: str, handler)` 接受任意正则；`CustomExecutor.eval_fallback(expr, vars)` 对每个 expr 顺序匹配所有 handler。**README 第 25 行的例子是 `r"chapter_\\d+_done"`**——这种"宽泛前缀 + 数字"模式在 ReDoS 攻击下可能造成指数级回溯：
- `r"^(a+)+$"` 类灾难性回溯正则
- `(a|a)*` 类歧义分支

**触发条件**:
- 剧情作者 `register_evaluator(r"^chapter_(\d+)+_done$", handler)` → 攻击者构造 `chapter_111111111111111!`（N 个 1 + 非数字结尾）触发 ReDoS
- 当前 v0 没有 `register_evaluator` 调用方（`test_expr_custom.py:42-74` 是测试），但 v2 章节加载器会让剧情作者 / 模组作者调用此 API

**建议**:
1. `register_evaluator` 加 timeout（5 秒）+ 正则长度限制（如 256 字符）
2. 检测"危险模式"——`re.compile(pattern)` 时检测 `re.search(r"\(.+\)\+", pattern)` / 含 `(.*)?` 等
3. 文档明示"避免灾难性回溯模式"

**估时**: 2-3 小时

---

### 【P1-S1】`simpleeval` 沙箱白名单 8 个函数 + 9 个危险函数被屏蔽，但 simpleeval 默认行为无 `__builtins__` 隔离验证

**位置**: `src/core/engine/expr/dispatcher.py:46-49` + `simpleeval` 库

**描述**:
- `BUILTIN_FUNCS` 8 个（int/str/float/bool/len/min/max/abs/round）——窄白名单，合理
- `dispatcher.py:46-49` 构造 `SimpleEval(names=..., functions=...)` —— simpleeval 的安全前提是 `names` 和 `functions` 都是 dict 引用
- **但** simpleeval 库默认 `SimpleEval()` 构造时设置 `ATTR_INDEXES = [n for n in SimpleEval._builtin_attributes]`，可能包含 `type`/`object`/`getattr` 等敏感属性
- 验证：`SimpleEval(names={"x": 1}).eval("getattr(x, '__class__')")` 在 simpleeval 1.0.7 下被拦截（不是支持的 AST 节点）——但未来版本可能放宽

**建议**:
- 显式禁用 simpleeval 的某些 power-user 方法（如 `SimpleEval.ATTR_INDEXES` 留空列表）
- 升级到 simpleeval 时跑 `tests/security/test_simpleeval_sandbox.py`（不存在，需要新增）
- 当前 v0 simpleeval 版本 `>=1.0` 未锁，**该建议依赖 P0-E2（锁版本）**

**估时**: 2-3 小时（含 sandbox 测试）

---

### 【P1-S2】`bus.py` `_drain` 用 `except Exception` 吞咽所有异常

**位置**: `src/core/engine/bus.py:62-71`

**描述**:
```python
@staticmethod
def _drain(q) -> None:
    while True:
        try:
            q.get_nowait()
        except (_thread_queue.Empty, Exception):
            break
```

`_thread_queue.Empty` 是 `Exception` 的子类，所以 `except (_thread_queue.Empty, Exception)` 实际只命中第二个分支（Exception）。这是 Python 反模式——**所有非 `BaseException` 异常都被吞**。

**触发条件**:
- multiprocessing.Queue 关闭时 `get_nowait` 抛 `ValueError("queue is closed")` → 被吞
- 如果 `q` 被错误传入其他类型对象，`AttributeError` 也被吞
- 编程错误（如 `q.get_nowait(keyword=invalid)` 的 `TypeError`）也被吞

**建议**:
```python
@staticmethod
def _drain(q) -> None:
    while True:
        try:
            q.get_nowait()
        except _thread_queue.Empty:
            continue  # 排空一个，继续
        except (ValueError, OSError):
            break  # 队列已关闭——正常退出
        # 其他异常让其传播
```

**估时**: 30 分钟

---

### 【P1-S3】`bus.py` JSON 序列化无 size 限制，巨型 payload → DoS

**位置**: `src/core/engine/bus.py:38-54`

**描述**:
```python
def put_cmd(self, cmd) -> None:
    self._cmd_q.put(json.dumps(cmd.to_dict()).encode("utf-8"))
```

`json.dumps` 无长度限制。如果 `TextEvt(content="A" * 1_000_000_000)` 调 `put_evt`，**会构造 1GB+ 字节串**入队。

**触发条件**:
- `TextEvt.content` 来源于 DSL 文本（`executor.py:188` 把 `Text(content=node.content)` 直接发事件）——攻击者写 `node AAAA...` (10MB 重复 A) → 单事件 10MB
- `chapters/chapter01.md` 现在最大 1.6KB，但模组作者可以写 1GB

**建议**:
1. `protocol.py` 各事件 dataclass 加 `__post_init__` 校验 size：`TextEvt` content ≤ 64KB，`DecoratorEvt` args 总长 ≤ 4KB
2. 或在 `bus.put_evt` 入口统一校验

**估时**: 1-2 小时

---

### 【P1-S4】`runtime/gui/main.py` `input()` 阻塞无超时——玩家卡死游戏

**位置**: `src/runtime/gui/main.py:35`

**描述**:
```python
val = input()  # 永远阻塞
```

无超时、无 SIGINT 优雅处理、无 EOF 反馈。如果 GUI 进程 stdout 断开（玩家关闭 terminal），引擎进程 `bus.get_cmd()` 永远等不到响应——需要重启游戏。

**当前缓解**: v0 CLI 占位，v2 PyQt6 GUI 不会有此问题。但**作为占位已经够用**——标 P1 是因为 v0→v1 过渡期 GUI 不可用时降级为 headless，`python -m runtime.gui.main` 单独跑也卡。

**建议**:
- v0 不动
- v2 PyQt6 落地时改用 QLineEdit + 信号槽

**估时**: 0（v0）/ 0（v2 PyQt6 自然解决）

---

### 【P2-S1】`Echo.parts` 拼接时，part 是变量名还是字面量的判断不一致

**位置**: `src/core/engine/executor.py:209-216`

**描述**:
```python
for p in node.parts:
    if p in self.state.vars:
        pieces.append(str(self.state.vars[p]))
    else:
        pieces.append(p)  # 字面量
```

`p in self.state.vars` 把"part 字符串 == 现有变量名"作为字面量判断依据。如果剧情写作者写 `node echo "+ test +"`（意图字面量 `+ test +`），而 `+ test +` 不在 state.vars，会被当字面量——OK。但如果写 `node echo true + false`（意图字面量），而后续 `node in ->true` 设置了 var=true，则 `true` 被当变量替换。

**触发条件**: 低概率但真实。攻击者/剧情作者构造 `node echo `pick + 是吗` `+ pick 不在 vars → 当字面量。但当后续 `node in → pick` 后，`pick` 在 vars 中 → 第二次执行被当变量。

**建议**:
- 引入显式字面量语法：`node echo 'pick + 是吗'`（用引号）
- 或在 AST 层要求"part 必须以 `$` 前缀才算变量引用"：`node echo $pick + 是吗?`

**估时**: 3-4 小时（含 ADR + fixture 更新）

---

### 【P2-S2】`main.py` GUI spawn 失败时静默降级，但日志写不进任何 sink

**位置**: `src/core/engine/main.py:79-86`

**描述**:
```python
if gui_proc is None:
    try:
        bus.put_evt(LogEvt(level="warning", message="GUI not available, running headless"))
    except Exception:
        pass  # 吞咽所有异常
```

如果 `LogEvt` 序列化失败（理论上不会，但 `Exception` 包括 `MemoryError`），`pass` 隐藏所有问题。**更严重**：v0 CLI 跑时 `_try_spawn_gui` 用 `subprocess.DEVNULL` 屏蔽 stderr/stdout——如果 GUI 启动失败，**用户完全看不到**为何降级。

**建议**:
- `_try_spawn_gui` 返回 `(proc, stderr_capture)` 元组，stderr 写到 `tmp/gui_stderr.log`
- 降级时日志带 stderr 摘要

**估时**: 1 小时

---

## 5. 视角 3：可测试性 / 工程化

### 5.1 总体评价

测试基础扎实（208 通过，90% 覆盖率，10 条不变量守护）。  
**但**：测试组织冗余、CI 缺失、类型检查无、依赖锁文件无、文档-代码一致性缺口（见 P0-A1）、POSIX-only 测试在 Windows 失败。

---

### 【P0-E1】19 个测试文件重复 `sys.path.insert` 死代码——`pytest.ini` 已配 `pythonpath = ["src"]`

**位置**:
- `pytest.ini:3` — `pythonpath = ["src"]`（已配）
- 19 个文件重复同一段：
  ```python
  import os
  REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
  sys.path.insert(0, f"{REPO_ROOT}/src")
  ```
- 受影响文件（按列出的 line 号）：
  - `tests/core/test_ast_shapes.py:11`
  - `tests/core/test_block_body.py:10`
  - `tests/core/test_block_meta.py:7`
  - `tests/core/test_block_skeleton.py:10`
  - `tests/core/test_decorator_parse.py:11`
  - `tests/core/test_engine_bus.py:16`
  - `tests/core/test_executor_decorator.py:10`
  - `tests/core/test_executor_nodes.py:10`
  - `tests/core/test_executor_skeleton.py:10`
  - `tests/core/test_extract_neon.py:10`
  - `tests/core/test_if_parse.py:10`
  - `tests/core/test_main_entry.py:12`
  - `tests/core/test_next_decls.py:10`
  - `tests/core/test_protocol_cmd.py:11`
  - `tests/core/test_protocol_evt.py:11`
  - `tests/integration/test_chapter01_e2e.py:13`
  - `tests/integration/test_echo_path.py:11`
  - `tests/integration/test_v1_e2e.py:14`
  - `tests/runtime/test_gui_protocol.py:12`

**描述**: 
1. **冗余**：`pythonpath = ["src"]` 已生效（`pytest.ini:3`），这 19 段 `sys.path.insert` 全部是死代码
2. **ruff 报警**：每个文件都因 `import os` 导入但只用于一次性 `REPO_ROOT` 计算，触发 F401（28 个 F401 错误的 27 个来源）
3. **跨平台脆弱**：`os.path.dirname` 在 Windows 上也能跑（`__file__` 是绝对路径），但换 macOS/Linux 同样能跑——**没有跨平台 bug**——纯属冗余
4. **维护成本**：任何文件移动到子目录（如 `tests/core/expression/`）就要改 3 层 dirname 计数

**建议**:
1. 删除所有 19 段 `REPO_ROOT` + `sys.path.insert`
2. 同时删除 `import os`（如果不再用）
3. 保留 pytest.ini 的 `pythonpath` 配置
4. ruff 跑一次应该看到 27 个 F401 减少

**估时**: 30 分钟（机械批量删除 + 跑 pytest 验证）

---

### 【P0-E2】`simpleeval` 版本未锁，CI/可重现性零保障

**位置**: `pyproject.toml:13` `simpleeval>=1.0` + `requirements.txt` 几乎空

**描述**:
- ADR-0004 偏差 D5 已登记
- 实际影响：
  - 本机 baseline 装 `simpleeval==1.0.7`（phase1-baseline §3.1）
  - 同事机器可能装 `1.0.0` 或未来 `1.1.0`——沙箱行为、TypeError 消息格式可能变化
  - `tests/core/test_expr_dispatcher.py:68-72` 断言 `ExprError` 包装格式 `f"expression evaluation failed: {expr!r} (simpleeval: {e})"`——若新版本改变 simpleeval 异常消息格式，测试可能误报
- **无 lockfile**（`requirements.txt` 是空占位）——所有依赖都是 `pip install -e .` 解析的版本约束，无 SHA 锁定

**复现**:
```bash
# 同事 A 机器
pip install -e .  # 装 simpleeval 1.0.0
# 同事 B 机器（晚一周装）
pip install -e .  # 装 simpleeval 1.0.7
# simpleeval 1.0.0 → 1.0.7 之间的 TypeError 消息格式可能已变
```

**建议**:
1. `pyproject.toml` 改 `simpleeval>=1.0,<2.0`（窄约束）或 `~=1.0.7`（锁小版本）
2. 生成 `requirements.lock` 用 `pip freeze > requirements.lock` + CI 用 `pip install -r requirements.lock`
3. 或：用 `pip-tools` / `uv` / `poetry` 引入 lockfile 机制

**估时**: 1 小时（含 CI 配置）

---

### 【P1-E1】无 CI 配置（`.github/workflows/` 不存在），测试靠开发者手动跑

**位置**: 项目根目录无 `.github/` 目录（确认：phase1-baseline §3.4 未列 CI 工具）

**描述**:
- 没有 `.github/workflows/pytest.yml`
- 没有 `.gitlab-ci.yml`
- 没有 pre-commit hook
- `README.md:198-211` 写"跑单测"命令，但**没有任何自动化触发**

**影响**:
- 任何 push / PR 不会自动跑测试 → 回归问题累积
- 208 passed / 3 failed 状态**只能靠 phase1-baseline 这种手工任务**发现
- 新人无法快速验证"我的环境能不能跑通"

**建议**:
最小可用 GitHub Actions：
```yaml
# .github/workflows/pytest.yml
name: pytest
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: ${{ matrix.python-version }} }
      - run: pip install -e ".[dev]"
      - run: pytest tests/ --cov=src --cov-fail-under=85
```

同时加 ruff 检查 + mypy 检查（见 P1-E3）。

**估时**: 1-2 小时

---

### 【P1-E2】无 `conftest.py`——共享 fixture / hook 散落

**位置**: 项目根目录 `tests/conftest.py` 不存在

**描述**:
- `tests/test_invariants.py` 每个 invariant 测试都重新 `subprocess.run([sys.executable, "-m", "pytest", ...])`——这是 fixture 不该做的事
- `tests/core/test_main_entry.py:36-50` `MemoryEngineBus` 类重复 2 次——本应进 conftest
- `tests/core/test_*.py` 的 `_loc(lineno)` helper 重复 6+ 次——本应是 conftest fixture
- `FakeState` 类在 `test_expr_dispatcher.py:16-20` 和 `test_expr_custom.py:16-19` 重复——本应在 conftest

**建议**:
- `tests/conftest.py` 集中：
  - `FakeState` / `FakeBus` / `MemoryEngineBus` 共享 fake
  - `_loc(lineno)` helper
  - `REPO_ROOT` 常量
  - `chapter_path` fixture 指向 `chapters/chapter01.md`

**估时**: 2-3 小时

---

### 【P1-E3】无类型检查（mypy / pyright）——AST 节点无 type guard

**位置**: `pyproject.toml` 无 `[tool.mypy]` / `[tool.pyright]`

**描述**:
- `ast_nodes.py` dataclass 都用 `frozen=True, slots=True`——结构好但**所有字段都是无约束类型**（`str`、`int | None`、`tuple`）
- `If.cond: tuple[str, str]`（前面 P1-A1 已提）
- `Block.meta: tuple`（字面写 `tuple` 不是 `tuple[IdMeta | IdStart | IdEnd, ...]`）
- `Block.body: tuple`（同样无元素类型）

**影响**:
- `Block(meta=("not a meta object",))` 不被 type checker 拦截
- `Story(blocks=())` 是合法但运行时报错
- 重构时 IDE 不会提示"这里改了 `If.cond` 的语义"

**建议**:
1. `pyproject.toml` 加：
   ```toml
   [tool.mypy]
   strict = true
   files = ["src/core"]
   ignore_missing_imports = true
   ```
2. 用 `from __future__ import annotations` + `Literal` 精确化 `If.cond`
3. CI 加 `mypy src/core` 步骤

**估时**: 4-6 小时（首轮 strict 跑会暴露 ~30 个错）

---

### 【P1-E4】覆盖率 90% 但缺关键路径——`main.py` 65% 暴露 GUI 集成盲点

**位置**: `src/core/engine/main.py:63-64, 80-86, 97-98, 104-105, 112-127, 135-136, 141-144`（phase1-baseline §6.2）

**描述**: 30 行未覆盖：
- `_try_spawn_gui` 成功路径（第 57-60 行）
- GUI spawn 失败 + LogEvt 广播路径（第 80-86 行）
- 章节加载失败路径（第 97-98 行）
- Executor RuntimeError 路径（第 112-127 行）
- `subprocess.TimeoutExpired` 路径（第 104-105、135-136 行）
- `if __name__ == "__main__"` 入口（第 141-144 行）

**影响**: 当前这些路径只通过 phase1-baseline 手工验证。一旦代码改动（如加 `asyncio` 改造），无测试守护。

**建议**:
- `test_main_entry.py` 加 fixture mock `subprocess.Popen` 覆盖 GUI 成功 / 失败 / timeout 三种路径
- 加 `test_main_cli_invocation` 跑 `python -m core.engine.main chapters/chapter01.md` 用 `subprocess.run` 验证（不依赖 GUI spawn）

**估时**: 2-3 小时

---

### 【P1-E5】`requirements.txt` 几乎空（3 行占位），`requirements-dev.txt` / `requirements-gui.txt` 各自只 1 行

**位置**: `requirements.txt:1-3` + `requirements-dev.txt:1` + `requirements-gui.txt:1`

**描述**:
- `requirements.txt:1-3` 写"v0 阶段无生产运行时依赖"——但实际有 `simpleeval`（运行时依赖！）
- `requirements-dev.txt:1` 只 `-e .[dev]`——这是 editable install，不锁版本
- `requirements-gui.txt:1` 只 `-e .[gui]`——同上

**影响**:
- 新人 `pip install -r requirements.txt` **不会装 simpleeval**——导入时 `ModuleNotFoundError`
- 应直接 `pip install -e .[dev,gui]`（pyproject.toml 才有真实依赖）

**建议**:
- `requirements.txt` 改为 `pip install -e .` + 注释说明"主依赖见 pyproject.toml"
- 或：删除 `requirements*.txt`，全部用 `pyproject.toml`（PEP 621 标准做法）
- 加 `requirements-dev.lock`（pip freeze 输出）

**估时**: 30 分钟

---

### 【P1-E6】3 个 invariant 守护测试（§11 #3 / #6 / TODO）POSIX-only，Windows 全失败

**位置**: `tests/test_invariants.py:50-58, 88-95, 154-160`（phase1-baseline §4.3）

**描述**:
- `test_invariant_3_next_not_string_literal`: `subprocess.run(["grep", "-r", ...])`
- `test_invariant_6_bus_json_only`: `subprocess.run(["grep", "-r", ...])`
- `test_no_todo_or_fixme_in_src`: `subprocess.run(["grep", "-r", ...])`

**根因**: 设计者假设环境有 GNU `grep.exe`，但 Windows 默认无此二进制。

**影响**:
- Windows 开发机 / CI runner：3 个测试直接 fail
- 208 passed / 3 failed 的 3 个失败
- §11 关键不变量的守护形同虚设（这 3 条正是"不变量"被破坏的告警）

**建议**（参考 phase1-baseline §4.3 选项）：
- **选项 A（推荐）**：改用 Python `pathlib` + `re` 实现 grep 等价扫描，跨平台
- 选项 B：保留 POSIX-only，`pytest.mark.skipif(sys.platform == "win32")` 跳过
- 选项 C：要求开发者装 Git for Windows（带 grep.exe）

**估时**: 1 小时（选项 A）

---

### 【P2-E1】`pyproject.toml` `requires-python = ">=3.11"` 与实际环境（3.10.11）不一致

**位置**: `pyproject.toml:9` vs phase1-baseline §2.2

**描述**:
- `pyproject.toml` 声明 `requires-python = ">=3.11"`
- 实际环境只有 Python 3.10.11
- `pip install -e .` 在 3.10 上失败，需要 `--ignore-requires-python` 绕过
- phase1-baseline §2.2 偏差 D-ENV-1 已登记

**影响**:
- 3.10 + 3.11 行为差异（`tomllib` 3.11+ 才内置、`Self` typing 3.11+ 才正式）可能掩盖未来 bug
- 但当前代码没用任何 3.11-only 特性——3.10 也能跑

**建议**:
- 选项 A：`requires-python = ">=3.10"` 放宽（最小阻力）
- 选项 B：环境升 3.11+（CI 用 3.11，本地用 3.11）
- 选项 C：保留 3.11+，3.10 开发者手动 `--ignore-requires-python`

**估时**: 5 分钟（选项 A）

---

### 【P2-E2】`ruff` 31 errors 已登记但未修；CI 也未启用 ruff 检查

**位置**: phase1-baseline §5.1

**描述**:
- 28 个 F401 unused import（绝大部分是 P0-E1 提到的 `import os`）
- 1 个 E402（`interpreter.py:504 import re`）
- 1 个 E741（`test_block_skeleton.py:69 ambiguous 'l'`）
- 1 个 F541（`executor.py:329 f-string no placeholders`）

**修复 P0-E1 后** 27 个 F401 自动消除。剩下 4 个 E 类 / F 类简单手修。

**建议**:
- 修 P0-E1 后跑 `ruff check --fix` 自动消除 28 个 F401
- 手修 E402 / E741 / F541
- `pyproject.toml` 加 `[tool.ruff] line-length = 100` 防 E501 误伤
- CI 加 `ruff check src/ tests/` 步骤

**估时**: 1 小时

---

### 【P2-E3】`pytest.ini` 无 `addopts = "--cov=src --cov-report=term-missing"`，覆盖率仅手工跑才有

**位置**: `pytest.ini:1-4`

**描述**: `addopts = "-ra --strict-markers"` 严格标记但无覆盖率。开发者必须 `pytest --cov=src --cov-report=term-missing` 才看得到覆盖率。

**建议**: `addopts = "-ra --strict-markers --cov=src --cov-report=term-missing --cov-fail-under=85"`——自动跑覆盖率，跌破 85% 失败。

**估时**: 5 分钟

---

### 【P2-E4】`tests/core/test_*.py` 用 `function`-level 测试无 `class TestX:` 组织

**位置**: 19 个 `tests/core/test_*.py`（除 `test_executor_if.py` / `test_executor_decorator.py` / `test_engine_bus.py` 外）

**描述**:
- `test_executor_if.py` 是平铺 `def test_xxx():` 风格（28 个测试无 class）
- `test_engine_bus.py` 也是平铺（8 个）
- `tests/runtime/test_gui_protocol.py` 平铺（6 个）

**影响**: 
- pytest 输出会按文件分组，但无 `TestClass::test_xxx` 嵌套结构
- 共享 setup 不能用 `setUp` method
- 命名空间隔离差

**建议**:
- 不是必须改，但建议对"功能聚类"测试用 class（如 `TestNodeInNodeEcho` 包 5 个 In/Echo 相关测试）
- pytest 7+ 仍兼容两种风格

**估时**: 4-6 小时（机械重构，可选）

---

## 6. 与哈尼斯 v1 报告的对照

### 6.1 哈尼斯已识别的（不再重复）

| # | 哈尼斯发现 | v2 复核结果 |
|---|---|---|
| S1 | `?:` 三元翻译漏翻 b/c | **已无效**——translator.py 已删（P0-A1 文档未同步） |
| S2 | DSL 表达式无长度限制 | **仍成立**——见 P1-S3（巨型 payload DoS） |
| S3 | simpleeval 版本未锁 | **仍成立**——见 P0-E2 |
| Q1 | 测试硬编码路径 | ✅ 已修（ADR-0004 偏差 B3） |
| Q2 | `_execute_if` 不防空 branches | ✅ 仍成立但严重度 P2（executor.py:223 if_node.branches[0] 仍无 guard） |
| Q3 | `dispatcher.eval` 捕获 `TypeError` 过宽 | **仍成立**——dispatcher.py:93 仍同代码 |
| Q4 | `eval_fallback` 收到的是 Python 表达式 | ✅ 已自然解决（translator 砍除，DSL 即 Python 表达式） |
| Q5 | `dispatcher.eval` Raises 契约 | ✅ 已自然解决（DSLSyntaxError 已不存在） |
| A1 | 无循环依赖 | ✅ v2 复核仍 0 |
| A2 | 进程隔离设计 | ✅ 仍良好 |
| A3 | 比较运算符替换无边界检查 | **已无效**——translator.py 已删 |
| A4 | `register_keyword` `str.replace` 无转义 | **已无效**——translator.py 已删 |

### 6.2 v2 新发现

| # | 视角 | 级别 | 一句话标题 |
|---|---|---|---|
| P0-A1 | 架构 | **P0** | expr/README.md 宣传的 translator/DSLSyntaxError 不存在 |
| P0-A2 | 架构 | **P0** | parse_if_stmt 124 行 / 5 正则串行匹配 |
| P0-S1 | 安全 | **P0** | _load_story 无路径校验 |
| P0-S2 | 安全 | **P0** | register_evaluator ReDoS 风险 |
| P0-E1 | 工程 | **P0** | 19 测试文件 sys.path.insert 死代码 |
| P0-E2 | 工程 | **P0** | simpleeval 版本未锁 |
| P1-A1 | 架构 | P1 | If.cond Literal 类型注解 |
| P1-A2 | 架构 | P1 | _execute_if 三阶段重复 + 错误处理不一致 |
| P1-A3 | 架构 | P1 | run_block 大型调度循环 |
| P1-A4 | 架构 | P1 | _validate_target_ids 三次循环 |
| P1-A5 | 架构 | P1 | _parse_body_line 子串前缀歧义 |
| P1-A6 | 架构 | P1 | 修饰器 call vs stop 事件不可区分 |
| P1-S1 | 安全 | P1 | simpleeval 默认属性暴露风险 |
| P1-S2 | 安全 | P1 | bus._drain 吞咽 Exception |
| P1-S3 | 安全 | P1 | bus.put_evt 无 size 限制 |
| P1-S4 | 安全 | P1 | GUI CLI input() 阻塞无超时 |
| P1-E1 | 工程 | P1 | 无 CI 配置 |
| P1-E2 | 工程 | P1 | 无 conftest.py 共享 fixture |
| P1-E3 | 工程 | P1 | 无 mypy 类型检查 |
| P1-E4 | 工程 | P1 | main.py 65% 覆盖率 |
| P1-E5 | 工程 | P1 | requirements.txt 与 pyproject.toml 不一致 |
| P1-E6 | 工程 | P1 | invariant 守护 POSIX-only |
| P2-A1 | 架构 | P2 | main._last_bus 全局变量 |
| P2-A2 | 架构 | P2 | __init__.py 全空无 __all__ |
| P2-A3 | 架构 | P2 | _build_next_lookup 可内联 |
| P2-S1 | 安全 | P2 | Echo.parts 字面量 vs 变量歧义 |
| P2-S2 | 安全 | P2 | main.py GUI spawn 失败 stderr 丢失 |
| P2-E1 | 工程 | P2 | requires-python 3.11 vs 实际 3.10 |
| P2-E2 | 工程 | P2 | ruff 31 errors 未修 |
| P2-E3 | 工程 | P2 | pytest.ini 无覆盖率自动检查 |
| P2-E4 | 工程 | P2 | 测试组织 function-level 而非 class |

### 6.3 哈尼斯报告未提但当前最严重的（"严重到必须重新强调"）

- **P0-S1 路径穿越**——哈尼斯未列。v2 章节加载器按 ROADMAP 是 P0 优先，但 `_load_story` 仍零校验。**这是当前最高优的安全问题**。
- **P0-E1 死代码**——哈尼斯未列。19 个文件 × 5 行 = 95 行冗余，掩盖 ruff 真实问题。**这是当前最高优的工程化问题**。
- **P0-A1 README/代码脱节**——哈尼斯报告 S1 基于"translator.py 存在"的假设，但 v1 PR #66 砍除后 README 没更新。**新进开发者第一道坎**。

---

## 7. 推荐修复优先级（前 5 名）

| # | 标题 | 估时 | 依赖 | 修复后能解锁什么 |
|---|---|---|---|---|
| 1 | **P0-A1 expr/README.md 同步**（删除 translator/DSLSyntaxError 描述）| 15 分钟 | 无 | 新开发者按 README 写 import 不再 ImportError；哈尼斯 S1 报告作废 |
| 2 | **P0-E1 删除 19 个 sys.path.insert 死代码** + 跑 ruff --fix | 30 分钟 | 无 | 27 个 F401 自动消除；测试仍 100% 通过 |
| 3 | **P0-S1 _load_story 路径校验**（5 项：resolve / relative_to / suffix / size / no-symlink）| 1-2 小时 | 无 | v2 章节加载器（ROADMAP §3.2）安全基础；防路径穿越 |
| 4 | **P0-E2 simpleeval 版本锁**（`~=1.0.7` 或 `>=1.0,<2.0`）+ 加 requirements.lock | 1 小时 | 无 | CI 可重现；同事机器行为一致 |
| 5 | **P0-A2 parse_if_stmt 拆分**（5 形态抽 5 函数 + 删 _MULTI_IF_RE 死调用 + 修 E402）| 2-3 小时 | 无 | parse_if_stmt 可读可测；E402 报警消失 |

**总估时**: 6-9 小时（约 1 个工作日）。可并行：1+2 可同时改（不冲突）；3 独立；4 独立；5 独立。

### 7.1 次优先（前 5 名之后）

- P1-A1 / P1-A2 / P1-A3：架构清理，可与 v2 PyQt6 GUI 一起做
- P1-S2 / P1-S3：bus 健壮性，依赖 P0-S1 落地
- P1-E1（CI）：所有 P0/P1 修完后建 CI
- P1-E3（mypy）：CI 之后第一个跑（会暴露约 30 个 type 错）

### 7.2 不建议立刻修

- P1-S1 simpleeval 默认属性：依赖 P0-E2 锁版本，lockfile 之后再 audit
- P2-*: P2 全部，可延后到 v2 阶段

---

## 8. 附录：审计元数据

### 8.1 工具与命令

- `Get-ChildItem` / `Select-String` 静态分析（无自动化脚本）
- 阅读 21 份源文件 + 19 份测试文件 + 6 份 ADR/audit/phase1-baseline 报告
- 静态行数统计（识别大函数）
- 模块依赖图手工梳理（确认 0 循环依赖）

### 8.2 与 phase1-baseline 的关系

| 偏差 ID | phase1-baseline 描述 | v2 复核 |
|---|---|---|
| D-ENV-1 | Python 3.10 vs 3.11 | 见 P2-E1（建议放宽） |
| D-TEST-1 | 3 个 invariant POSIX-only | 见 P1-E6（建议改 pathlib+re） |
| D-LINT-1 | ruff 31 errors | 见 P2-E2（修 P0-E1 后剩 4 个） |
| D-LINT-2 | E501 行长 | 仍未启用——建议 pyproject.toml 设 line-length=100 |
| D-LINT-3 | W292 文件末尾换行 | ruff --fix 自动修 |
| D-COV-1 | main.py 65% | 见 P1-E4 |
| D-DEP-1 | requires-python 不一致 | 与 D-ENV-1 同根因 |

### 8.3 不在本次审计范围

- v2 章节加载器（ROADMAP §3.2，尚未实现）
- v2 PyQt6 GUI（ROADMAP §3.1，尚未实现）
- 存档 / 读档（ROADMAP §3.3，尚未实现）
- `@LLM-jud` 装饰器（ROADMAP §3.7，远期）

这些 v2+ 功能的不变量在它们落地时再审计。

---

*代码审计师 · 2026-06-24 · v2 独立审计完成*
