# Neural-Engine 独立审计报告

> **执行人**: 哈尼斯 (独立第三方审计)
> **执行日期**: 2026-06-22
> **审计范围**: main 分支 (HEAD = f43e64c) + 开放 issue/PR
> **CodeGraph 索引**: 49 文件 / 574 nodes / 1383 edges

---

## 1. 执行摘要

| 维度 | 状态 | 备注 |
|---|---|---|
| v0 基础引擎 | ✅ 闭环 | parser → AST → executor → bus → GUI 全链路通 |
| v1 表达式子系统 | ⚠️ 骨架已建，未接入 | expr/ 子包完整但 executor._execute_if 仍是 v0 打桩 |
| 测试 | 214 passed / 4 failed / 1 skipped | 4 失败全是硬编码路径 |
| 循环依赖 | ✅ 0 | CodeGraph 确认 |
| 安全沙箱 | ⚠️ simpleeval 白名单有效，但翻译层有缝隙 | 见 S1-S3 |

---

## 2. 已有开放 Issue 验证（#59-#65）

上一轮审计（Hermes）提交的 7 条 issue，逐条独立验证：

| Issue | 标题 | 验证结果 | 证据 |
|---|---|---|---|
| #59 (B1) | executor._execute_if 接入 ExprDispatcher | ✅ 确认 | `_execute_if` (executor.py:227) docstring 明写 "v0-issue-16: node if 打桩——永远选第一分支" |
| #60 (B2) | If.cond 类型注解扩 union | ✅ 确认 | ast_nodes.py:111 `cond: tuple[str, str]` 不含 `range` kind |
| #61 (D1) | chapter01.md 加 v1 形态 | ✅ 确认 | chapter01.md 只有 v0 语法 `node if p_pick [1:t_a,2:t_b,3:echo p_pick]` |
| #62 (D2) | UnsupportedNodeError 死代码 | ✅ 确认 | errors.py 定义了 `UnsupportedNodeError`，但 dispatcher.eval 直接捕 `TypeError`，从未构造 `UnsupportedNodeError` 实例 |
| #63 (D3) | register_node 公开 API | ✅ 确认 | custom.py:65 `register_node` 存在但 `raise NotImplementedError` |
| #64 (D4) | DSLSyntaxError 类型信息被吞 | ✅ 确认（但机制不同） | 见下方详细分析 |
| #65 | ADR-0004 偏差登记 | ✅ 确认 | docs/adr/ 下无 0004 文件 |

### #64 详细分析（DSLSyntaxError 泄露路径）

dispatcher.eval 的实际结构：

```
py_expr = self.translator.to_python_expr(expr)  # ← 在 try 块外
try:
    return self._evaluator.eval(py_expr)
except (TypeError, InvalidExpression) as e: → fallback
except (SyntaxError, NameError) as e: → ExprError
except Exception as e: → ExprError
```

`to_python_expr()` 在 try 块**外**调用。如果翻译失败抛 `DSLSyntaxError`（继承 `ParserError` → `SyntaxError`），它会直接传播到调用方，**不被 eval 的 except 捕获**。

**真正的问题是 API 契约**：`eval` / `eval_bool` / `eval_int` 的 docstring 都只声明 `Raises: ExprError`，但实际可以抛出 `DSLSyntaxError`。调用方（executor）如果只 catch `ExprError`，会漏掉 `DSLSyntaxError`。

---

## 3. 新发现（独立审计）

### 安全类

#### S1 (MEDIUM): `?:` 三元翻译漏翻 b/c 分支

**位置**: translator.py:104-109

```python
if m:
    a, b, c = m.group("a").strip(), m.group("b").strip(), m.group("c").strip()
    py_a = self._apply_keyword_replacements(a)
    return f"({b}) if ({py_a}) else ({c})"  # ← b, c 未翻译
```

`a`（条件）经过 `_apply_keyword_replacements` 翻译，但 `b` 和 `c`（两个分支）**直接插入 Python 表达式**，跳过了 Chinese 关键字替换。

**影响**: DSL 写 `p_tall 等于 1 ? 是 : 否`，`b="是"` `c="否"` 会直接作为 Python 标识符传给 simpleeval，导致 `NameNotDefined` 错误。

**修复**: `b` 和 `c` 也应经过 `_apply_keyword_replacements`。

#### S2 (LOW): DSL 表达式无长度限制

**位置**: dispatcher.py:76 `eval(self, expr: str)`

没有对 `expr` 长度做限制。极长的 DSL 表达式会导致 simpleeval 的 AST 解析性能下降。虽然 DSL 作者通常是可信的剧情写作者，但如果未来支持用户自定义表达式（如 mod 系统），这会成为 DoS 向量。

#### S3 (INFO): simpleeval 版本未锁定

**位置**: pyproject.toml:13

```toml
"simpleeval>=1.0"
```

`>=1.0` 允许任何 1.x 版本。simpleeval 的沙箱策略在不同版本间可能变化。建议锁定到具体版本或更窄范围（如 `~=1.0`）。

### 代码质量类

#### Q1 (BUG): 测试硬编码绝对路径

**位置**: tests/integration/test_echo_path.py, tests/test_mvp_table.py 等

4 个失败测试引用 `/home/hedaas/桌面/Neural Engine/tests/test_echo.md` —— owner 本机路径。在其他环境（包括本审计环境）直接 `FileNotFoundError`。

**修复**: 用 `Path(__file__).parent` 或 pytest fixture 构造相对路径。

#### Q2 (BUG): `_execute_if` 不防空 branches

**位置**: executor.py:228

```python
chosen = if_node.branches[0]  # ← 无长度检查
```

如果 `if_node.branches` 为空元组，抛 `IndexError` 而非有意义的错误。虽然 parser 应该保证至少一个分支，但 defense-in-depth 原则下应加 guard。

#### Q3 (DESIGN): `dispatcher.eval` 捕获 `TypeError` 过宽

**位置**: dispatcher.py:92

```python
except (TypeError, InvalidExpression) as e:
```

注释说 "TypeError: simpleeval 遇不支持的 AST 节点"，但 `TypeError` 也可能是合法的类型错误（如 `int + str`）。这导致真实的类型错误会错误地走 fallback 路径，可能掩盖 bug。

simpleeval 对不支持的 AST 节点实际抛的是 `TypeError("Unsupported node type: ...")`，可以通过消息内容区分，但当前代码没做区分。

#### Q4 (DESIGN): `eval_fallback` 收到的是 Python 表达式而非 DSL

**位置**: dispatcher.py:96

```python
return self.custom.eval_fallback(py_expr, self.state.vars)
```

`eval_fallback` 的参数 `py_expr` 是翻译后的 Python 表达式。但 `register_evaluator` 的文档说 "注册自定义表达式"，没有明确说明 regex 匹配的是 Python 表达式而非 DSL 原文。开发者写 evaluator pattern 时可能误以为在匹配 DSL。

#### Q5 (DOC): `dispatcher.eval` 的 Raises 契约不完整

**位置**: dispatcher.py:80-87

docstring 声明 `Raises: ExprError`，但 `to_python_expr()` 在 try 块外调用，可能抛 `DSLSyntaxError`（继承 `ParserError` → `SyntaxError`），不是 `ExprError` 的子类。API 契约应补充。

### 架构类

#### A1 (GOOD): 无循环依赖

CodeGraph `find_circular_deps` 返回 0。模块层次清晰：`ast_nodes` ← `interpreter` / `executor` / `expr` ← `main`。

#### A2 (GOOD): 进程隔离设计

EngineBus 封装 `multiprocessing.Queue` / `queue.Queue` 双模式，protocol.py 做 dict ↔ dataclass 序列化。v0 用 CLI 占位验证协议层，v1 再接 PyQt6 —— 渐进式落地合理。

#### A3 (RISK): 比较运算符替换无边界检查

**位置**: translator.py:46-51

```python
(re.compile(r"大于等于"), ">="),
(re.compile(r"等于"), "=="),
(re.compile(r"大于"), ">"),
```

`且`/`或`/`非`/`包含` 用了 `(?<![\w])` 和 `(?=[\s)])` 边界检查，但比较运算符**直接子串替换**。注释说 "中文字符之间不会有英文标识符，直接替换安全"。

这在纯中文 DSL 中成立，但如果变量名允许包含中文字符（Python 标识符支持中文），`p_大于_阈值` 会被错误替换为 `p_>_阈值`。

**建议**: 统一加边界检查，或显式在 ADR 中约束变量名只能用 ASCII。

#### A4 (RISK): `register_keyword` 用 `str.replace` 无转义

**位置**: translator.py:116

```python
result = result.replace(dsl_kw, py_expr)
```

如果 `dsl_kw` 是其他 DSL 关键字的子串（如 `等于` 是 `大于等于` 的子串），替换顺序会影响结果。当前 `register_keyword` 在 `_KEYWORD_REPLACEMENTS` 之后执行，所以内置 `大于等于` 已经被替换成 `>=`，不会干扰。但如果用户注册的 `dsl_kw` 之间有子串关系，结果不可预测。

---

## 4. 复杂度热点

| 函数 | 复杂度 | 位置 | 说明 |
|---|---|---|---|
| `_validate_target_ids` | 18 | executor.py:84 | 最高复杂度，验证 next target ID 合法性 |
| `parse_block_skeleton` | 16 | interpreter.py:122 | 块骨架解析 |
| `run_block` | 15 | executor.py:161 | 块执行主循环 |
| `parse_next_decls` | 14 | interpreter.py:321 | next 声明解析 |
| `parse_if_stmt` | 12 | interpreter.py:532 | if 语句解析 |
| `_parse_body_line` | 12 | interpreter.py:373 | 块体行解析 |
| `parse_block_body` | 12 | interpreter.py:429 | 块体解析 |

v0 阶段复杂度可接受。`_validate_target_ids` 和 `run_block` 是未来重构候选——当 v1 接入 ExprDispatcher 后 `run_block` 逻辑会更复杂。

---

## 5. v0→v1 过渡评估

### 已就绪
- expr/ 子包完整：translator → dispatcher → custom 三层调度链清晰
- simpleeval 白名单函数 10 个（int/str/float/bool/len/min/max/abs/round）合理
- 错误类层次：ExprError / UnsupportedNodeError / DSLSyntaxError 设计到位

### 阻塞项（按优先级）
1. **#59 (B1)**: executor._execute_if 接入 ExprDispatcher —— v1 的核心交付物
2. **#64 (D4)**: DSLSyntaxError 契约修正 —— 影响 executor 错误处理
3. **S1**: `?:` 三元翻译漏翻 b/c —— 影响表达式正确性
4. **#60 (B2)**: If.cond 类型注解 —— 影响 range kind 扩展
5. **#61 (D1)**: chapter01.md 加 v1 形态 —— 端到端验证依赖

### 建议新增 issue

| 优先级 | 标题 | 对应发现 |
|---|---|---|
| Medium | S1: `?:` 三元翻译漏翻 b/c 分支 | translator.py:104-109 |
| Medium | Q1: 测试硬编码绝对路径导致 4 个 e2e 测试失败 | tests/integration/ |
| Low | Q3: dispatcher.eval 捕获 TypeError 过宽 | dispatcher.py:92 |
| Low | Q5: dispatcher.eval Raises 契约不完整 | dispatcher.py:80-87 |
| Low | A3: 比较运算符替换无边界检查 | translator.py:46-51 |
| Info | S3: simpleeval 版本未锁定 | pyproject.toml:13 |

---

## 6. 总体评价

Neural-Engine 的 v0 baseline **工程质量良好**：模块层次清晰、不变量有测试守护、ADR 记录完整。v1 表达式子系统的架构设计（translator → simpleeval → custom fallback 三层）是合理的沙箱方案。

主要风险集中在 v0→v1 过渡的**集成层**：expr/ 子包独立可用，但 executor 还没接入，且接入过程中暴露的 API 契约问题（#64、Q5）需要先解决。安全面整体可控，simpleeval 的 AST 级沙箱是主要防线，翻译层的缝隙（S1）是当前最值得修的实际 bug。

---

*哈尼斯 · 独立第三方审计 · 2026-06-22*
