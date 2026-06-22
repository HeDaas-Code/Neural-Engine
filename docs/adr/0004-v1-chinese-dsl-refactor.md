# ADR-0004: v1 中文 DSL 表达式重构设计

- **状态**：提案（待 owner 拍板）
- **日期**：2026-06-22
- **决策者**：项目所有者 @HeDaas-Code
- **范围**：v1 表达式子系统中文化扩展 + bug 修复 + 结构清理
- **提案人**：哈尼斯（独立第三方审计）

---

## 1. 背景

### 1.1 设计意图澄清

owner 明确：**"中文原生"指工作语言层面（issue/PR/commit/文档/agent 回复），DSL 表达式的中文关键字替换是保留设计，不是误解的产物。**

本次重构在保留中文 DSL 翻译层的前提下，**扩大中文覆盖范围**，同时修复审计发现的 bug 和契约问题。

### 1.2 现状（v1 骨架）

**translator 已有中文关键字**（10 条）：

| 中文 | Python | 类型 | 边界检查 |
|---|---|---|---|
| 且 | and | 中缀 | ✅ lookbehind/lookahead |
| 或 | or | 中缀 | ✅ |
| 非 | not | 前缀 | ✅ |
| 包含 | in | 中缀 | ✅ |
| 大于等于 | >= | 比较 | ❌ 直接子串 |
| 小于等于 | <= | 比较 | ❌ |
| 不等于 | != | 比较 | ❌ |
| 等于 | == | 比较 | ❌ |
| 大于 | > | 比较 | ❌ |
| 小于 | < | 比较 | ❌ |

**内置函数**（BUILTIN_FUNCS）：纯英文 `int/str/float/bool/len/min/max/abs/round`

**已知 bug**：
- S1: `?:` 三元翻译漏翻 b/c 分支
- #64: dispatcher.eval 的 `to_python_expr()` 在 try 块外
- Q3: TypeError 捕获过宽
- A3: 比较运算符无边界检查

### 1.3 不动的部分

**结构化剧本思维不变**：
- neon 块结构：`node start` / `node end` / `id:xxx` / `next:yyy` / `@style`
- 节点生命周期：元数据区 → 块内执行区
- 命名空间分离：ID 命名空间 vs 变量命名空间
- NEXT 引用语义：next 变量表项引用，不是字符串
- 进程间协议：EngineBus + JSON 序列化
- 三层调度架构：translator → simpleeval → CustomExecutor fallback

---

## 2. 重构设计

### 2.1 表达式中文化扩展

#### 2.1.1 新增逻辑关键字

| 中文 | Python | 类型 | 示例 |
|---|---|---|---|
| `为真` | `== True` | 后缀判断 | `p_flag 为真` → `p_flag == True` |
| `为假` | `== False` | 后缀判断 | `p_flag 为假` → `p_flag == False` |
| `为空` | `== ""` | 后缀判断 | `p_name 为空` → `p_name == ""` |
| `非空` | `!= ""` | 后缀判断 | `p_name 非空` → `p_name != ""` |

#### 2.1.2 新增范围关键字

| 中文 | Python | 示例 |
|---|---|---|
| `介于 X 与 Y 之间` | `X <= val <= Y` | `p_age 介于 18 与 30 之间` → `18 <= p_age <= 30` |

> 实现方式：正则 `(?P<val>[\w_]+)\s*介于\s*(?P<low>[^\s]+)\s*与\s*(?P<high>[^\s]+)\s*之间` → `({low} <= {val} <= {high})`

#### 2.1.3 三元表达式中文化

当前：`a ? b : c`（简略形式）

新增中文形式：

| 中文 | 示例 |
|---|---|
| `如果 A 就 B 否则 C` | `如果 p_tall 大于 180 就 "高" 否则 "矮"` |

> 翻译为 Python 三元：`(B) if (A) else (C)`

#### 2.1.4 内置函数中文别名

BUILTIN_FUNCS 白名单增加中文别名映射：

| 中文 | Python 函数 |
|---|---|
| `长度` | `len` |
| `最小` | `min` |
| `最大` | `max` |
| `绝对值` | `abs` |
| `四舍五入` | `round` |
| `取整` | `int` |
| `转文本` | `str` |
| `转小数` | `float` |
| `转布尔` | `bool` |

> 实现方式：在 dispatcher 构造时，`functions` 字典同时注册英文名和中文名，指向同一个 Callable。simpleeval 按函数名查找，中文名同等可用。

### 2.2 translator 修复与增强

#### 2.2.1 S1 修复：`?:` 三元 b/c 翻译

```python
# 修复前（b/c 直接插入，跳过翻译）
return f"({b}) if ({py_a}) else ({c})"

# 修复后（b/c 也走翻译）
py_b = self._apply_keyword_replacements(b)
py_c = self._apply_keyword_replacements(c)
return f"({py_b}) if ({py_a}) else ({py_c})"
```

#### 2.2.2 A3 修复：比较运算符加边界检查

```python
# 修复前（直接子串替换，变量名含中文会误替换）
(re.compile(r"大于等于"), ">="),

# 修复后（加 lookbehind/lookahead，要求两侧是操作数边界）
(re.compile(r"(?<=\w|\s|\))大于等于(?=\s|\d|\w|\()"), ">="),
```

> 边界定义：左侧是 `\w` / 空白 / `)`，右侧是空白 / 数字 / `\w` / `(`。避免 `p_大于等于` 这类变量名被误替换。

#### 2.2.3 三元中文形式支持

```python
# 新增正则：如果 A 就 B 否则 C
_IF_THEN_ELSE_RE = re.compile(
    r"^如果\s+(?P<a>.+?)\s+就\s+(?P<b>.+?)\s+否则\s+(?P<c>.+)$"
)
```

翻译顺序：先匹配中文三元 → 再匹配 `?:` → 最后走关键字替换。

### 2.3 dispatcher 契约修正

#### 2.3.1 #64 修复：to_python_expr 放入 try

```python
def eval(self, expr: str) -> object:
    try:
        py_expr = self.translator.to_python_expr(expr)
        self._evaluator.names = self.state.vars if hasattr(self.state, "vars") else {}
        try:
            return self._evaluator.eval(py_expr)
        except (TypeError, InvalidExpression) as e:
            # fallback...
            ...
    except DSLSyntaxError:
        raise  # 翻译错误直接传播
    except Exception as e:
        raise ExprError(...) from e
```

#### 2.3.2 Q3 修复：收窄 TypeError 捕获

只捕 simpleeval 的 `UnsupportedNodeError` 信号（TypeError 且消息含 "not supported"），不吞合法类型错误。

```python
except TypeError as e:
    if "not supported" in str(e):
        # 走 fallback
        ...
    raise  # 合法的类型错误直接报
```

#### 2.3.3 Q5 修复：Raises 契约补全

```python
def eval(self, expr: str) -> object:
    """...
    
    Raises:
        DSLSyntaxError: DSL 翻译失败（继承 ParserError）
        ExprError: simpleeval 求值失败 + fallback 失败
    """
```

### 2.4 工程层清理

| 项 | 动作 | 理由 |
|---|---|---|
| #62 UnsupportedNodeError 死代码 | 砍掉 | 没有代码路径抛这个异常 |
| #63 register_node 占位 | 砍掉 | v2 要用时再加，不养死代码 |
| Q1 硬编码路径 | 改 `__file__` 相对路径 | 4 个 e2e 测试跨机器失败 |
| S3 simpleeval 版本 | 锁定 `>=1.0,<2.0` | 避免大版本 breaking change |

### 2.5 executor 接入（#59）

```python
def _execute_if(self, if_node: If) -> None:
    """v1: 接入 ExprDispatcher 真求值。"""
    cond = if_node.cond
    
    if cond[0] == "var":
        # v0 兼容：值匹配模式（p_pick [1:a, 2:b]）
        var_val = self.state.vars.get(cond[1], "")
        for branch in if_node.branches:
            if str(branch.value) == str(var_val):
                self._execute_branch(branch)
                return
        # 无匹配分支——日志 + 选最后一个
        self.sink.put_evt(LogEvt(level="warning", 
            message=f"no branch matched: {cond[1]}={var_val!r}"))
        self._execute_branch(if_node.branches[-1])
    
    elif cond[0] == "expr":
        # v1 新增：表达式求值模式
        result = self.dispatcher.eval_bool(cond[1])
        chosen = if_node.branches[0] if result else if_node.branches[-1]
        self._execute_branch(chosen)
    
    elif cond[0] == "range":
        # v1 新增：范围匹配模式
        var_val = self.state.vars.get(cond[1], 0)
        for branch in if_node.branches:
            if hasattr(branch, 'range_spec') and branch.range_spec.contains(var_val):
                self._execute_branch(branch)
                return
        self._execute_branch(if_node.branches[-1])
    
    else:
        raise RuntimeError(f"unknown cond kind: {cond[0]}")
```

### 2.6 If.cond 类型扩展（#60）

```python
# ast_nodes.py
@dataclass(frozen=True, slots=True)
class If:
    cond: tuple[str, str]  # kind 扩展: "var" | "expr" | "range" | "bool_expr"
    branches: tuple[Branch, ...]
```

### 2.7 chapter01.md 端到端（#61）

新增 v1 形态测试块：

```neon
id:c1
t_a<-next:ca
t_b<-next:cb
node start
你听到门外传来两声敲门。
node in ->p_pick
# v1 表达式形态：中文条件求值
node if p_pick 等于 1 [t_a:t_a, t_b:t_b]
node end
```

端到端断言：输入 `1` → 走 `t_a` → 跳到 `ca`；输入 `2` → 走 `t_b` → 跳到 `cb`。

---

## 3. 重构清单（按执行顺序）

### 阶段 1：translator 层修复（无破坏性）
1. S1: `?:` 三元 b/c 翻译修复
2. A3: 比较运算符加边界检查
3. 新增中文关键字（为真/为假/为空/非空/介于）
4. 新增中文三元（如果...就...否则...）
5. 新增内置函数中文别名

### 阶段 2：dispatcher 契约修正
6. #64: to_python_expr 放入 try 块
7. Q3: TypeError 捕获收窄
8. Q5: Raises 契约补全

### 阶段 3：executor 接入
9. #60: If.cond 类型注解扩 union
10. #59: executor._execute_if 接入 ExprDispatcher
11. 死代码清理（#62 UnsupportedNodeError / #63 register_node）

### 阶段 4：验证闭环
12. #61: chapter01.md 加 v1 形态 + 端到端断言
13. Q1: 硬编码路径修复
14. S3: simpleeval 版本锁定
15. 全量 pytest 绿

---

## 4. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 中文关键字正则冲突（`为空` vs `非空`） | 顺序敏感：`非空` 在 `为空` 之前替换 |
| `介于...与...之间` 的 `与` 和逻辑 `或` 冲突 | `介于` 模式优先匹配，在关键字替换之前 |
| 比较运算符边界检查改变现有行为 | 加测试用例覆盖 `p_大于等于` 这类边界 |
| executor 接入后 v0 兼容性 | `cond[0]=="var"` 走原路径，不走 dispatcher |

---

## 5. 不做的事

- 不改 neon 块结构（node/id/next/@style）
- 不改变名空间分离原则
- 不改进程间协议
- 不改三层调度架构
- 不加 PyQt6 GUI（推到 v2）
- 不做可视化编辑器（推到 v3）

---

## 6. 验收标准

1. `python3 -m pytest tests/ -q` 全绿（含新增 v1 测试）
2. chapter01.md v1 形态端到端断言通过
3. `p_大于等于` 这类变量名不被误替换
4. `如果 p_tall 大于 180 就 "高" 否则 "矮"` 可正确求值
5. `长度(p_name)` 等价于 `len(p_name)`
6. `p_age 介于 18 与 30 之间` 可正确求值
7. v0 形态 `node if p_pick [1:t_a, 2:t_b]` 仍正常工作

---

*哈尼斯 · 2026-06-22 · 待 owner 拍板*
