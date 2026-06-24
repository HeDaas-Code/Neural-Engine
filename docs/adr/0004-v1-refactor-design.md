# ADR-0004: v1 重构设计——对齐 neon 规范最新形态

- **状态**：提案（待 owner 拍板）
- **日期**：2026-06-22
- **决策者**：项目所有者 @HeDaas-Code
- **范围**：neon DSL 语法对齐 + translator 砍除 + executor 接入 + 新功能扩展
- **提案人**：哈尼斯（独立第三方审计）
- **依据**：owner 提供的最新 neon 规范图（2026-06-22）

---

## 1. 背景与动机

owner 提供了最新的 neon 规范图，与当前实现（ADR-0001 v0 + ADR-0003 v1 骨架）存在多处差异。本次重构以最新规范图为准，对齐语法、砍除 translator 中文翻译层、接入 executor 真求值、并扩展新功能。

**核心原则**：
- 结构化剧本思维不变（元数据区 + 剧本段 + 双命名空间）
- 表达式用原生 Python 语法，simpleeval 直接求值
- 中文覆盖在工作语言层面，不在 DSL 语法层面

---

## 2. 目标形态（owner 规范图）

### 2.1 neon 块结构

```
```neon                    # 节点块开始
元数据区
  id:start                # 节点 id 标记
  n2 ← next : cn2         # 接续 id 标记（← 声明符）
-----                     # 分隔线（可选）
node start                # 剧本段开始
数据区
  平层 ← 文字行，逐行输出
  -- 阳光照向大地 @style text:[rgb:red,Px:12],bgm:start:1.mp3
  # 修饰器可单独成行或附于文本后
  你在想什么？@style text:[rgb:clear]
  node in → P-text        # in 方法，用户输入赋值
  node echo P-text + 是吗?我知道了.   # echo 拼接
  node if @LLM-jud(P-text,是否积极情感)[0:n1,1:n2]  # if + 装饰器
node end                  # 脚本结束
```                        # 节点块结束
```

### 2.2 NEXT 标记机制（三阶段）

| 阶段 | 行为 |
|---|---|
| **声明** | 元数据区 `(变量 ←) next : 节点id`，将节点 id 与变量关联 |
| **竞争** | next 变量有自有方法，调用时将 NEXT 隐变量指向自身；`node end` 之前 NEXT 不封闭 |
| **应用** | `node end` 时 NEXT 锁定，按最后一个指向跳转 |

- 单 next 声明 → NEXT 直接指向唯一节点
- 多 next 声明 → NEXT=null，等待 next 变量竞争

---

## 3. 差异清单（现有 → 目标）

### 3.1 语法层

| # | 现有 | 目标 | 影响 | 优先级 |
|---|---|---|---|---|
| G1 | `t_a<-next:ca` | `n2 ← next : cn2` | 解析器：箭头符号 + 空格容忍 | 高 |
| G2 | `node in ->var` | `node in → P-text` | 解析器：箭头符号 | 高 |
| G4 | `node echo var` | `node echo P-text + 是吗?我知道了.` | executor：echo 拼接 | 中 |
| G5 | `@style key:val` | `@style text:[rgb:red,Px:12],bgm:start:1.mp3` | 解析器+executor：结构化参数 | 中 |
| G6 | `node if var [1:a,2:b]` | `node if @LLM-jud(P-text,条件)[0:n1,1:n2]` | executor+expr：装饰器调用 | 低（远期） |

### 3.2 表达式层

| # | 现有 | 目标 | 影响 | 优先级 |
|---|---|---|---|---|
| E1 | translator 中文关键字替换 | 砍掉，原生 Python 语法 | 删 translator.py | 高 |
| E2 | `p_tall 等于 1 且 p_age 大于 18` | `tall == 1 and age >= 18` | 测试 + fixture 改 | 高 |
| E3 | `If.cond = ("var"/"expr", name)` | 简化：`("expr", "tall == 1")` 走 simpleeval | ast_nodes + executor | 高 |
| E4 | dispatcher 三层调度（translator→simpleeval→fallback） | 两层（simpleeval→fallback） | dispatcher.py | 高 |

### 3.3 bug/契约层

| # | 问题 | 修复 | 优先级 |
|---|---|---|---|
| B1 | #64: `to_python_expr()` 在 try 块外 | 砍 translator 后自动消失 | 高 |
| B2 | Q3: TypeError 捕获过宽 | 收窄到 simpleeval 的 FunctionNotDefined/NameNotDefined | 高 |
| B3 | Q1: 4 个 e2e 测试硬编码路径 | 改 `__file__` 相对路径 | 高 |
| B4 | #62: UnsupportedNodeError 死代码 | 清除 | 低 |
| B5 | #63: register_node 占位 | 砍掉，v2 要时再加 | 低 |
| B6 | S3: simpleeval 版本未锁定 | pyproject.toml 锁版本 | 低 |

### 3.4 功能层

| # | 现有 | 目标 | 影响 | 优先级 |
|---|---|---|---|---|
| F1 | executor._execute_if 打桩 | 接入 ExprDispatcher 真求值 | executor.py | 高 |
| F2 | If.cond 不支持 range kind | 扩 union 类型注解 | ast_nodes.py | 中 |
| F3 | chapter01.md 只有 v0 形态 | 加 v1 表达式形态 + 端到端断言 | fixture + test | 高 |
| F4 | 无 LLM 装饰器 | `@LLM-jud(...)` 装饰器框架 | 新模块 | 低（远期） |

---

## 4. 重构方案

### 阶段 1：砍 translator + 表达式回退（E1-E4, B1）

**删除**：
- `src/core/engine/expr/translator.py` 整个文件
- `ExprTranslator` 类 + `_KEYWORD_REPLACEMENTS` 表 + `?:` 三元翻译
- `dispatcher.py` 中 `translator` 参数和 `to_python_expr()` 调用

**修改 dispatcher.py**：
```python
class ExprDispatcher:
    def __init__(self, state, custom=None):
        self.state = state
        self.custom = custom or CustomExecutor(state)
        self._evaluator = SimpleEval(
            names=state.vars if hasattr(state, "vars") else {},
            functions={**BUILTIN_FUNCS, **self.custom.functions},
        )

    def eval(self, expr: str) -> object:
        # 直接 simpleeval 求值，不翻译
        self._evaluator.names = self.state.vars if hasattr(self.state, "vars") else {}
        try:
            return self._evaluator.eval(expr)
        except (NameNotDefined, FunctionNotDefined, OperatorNotDefined) as e:
            # simpleeval 不认识的名字/函数/操作符 → fallback
            try:
                return self.custom.eval_fallback(expr, self._evaluator.names)
            except ExprError:
                raise ExprError(f"expression evaluation failed: {expr!r} ({e})") from e
        except InvalidExpression as e:
            raise ExprError(f"expression evaluation failed: {expr!r} ({e})") from e
```

**修改 `expr/__init__.py`**：移除 ExprTranslator / DSLSyntaxError 导出

**修改 errors.py**：DSLSyntaxError 保留但标记废弃（translator 砍掉后无使用方）

**修改测试**：中文关键字用例改为 Python 表达式

### 阶段 2：语法对齐（G1-G2）

**G1: next 声明符号 `<-` → `←`**
- `interpreter.py::parse_next_decls` 修改解析逻辑
- 同时容忍 `<-` 和 `←`（向后兼容 v0 fixture 过渡期）
- 空格容忍：`n2 ← next : cn2` 和 `n2←next:cn2` 都接受
- 元数据区语法：`(变量 ←) next : 节点id`，容忍冒号两侧空格

**G2: in 箭头 `->` → `→`**
- `interpreter.py::parse_block_body` 修改 `node in` 解析
- 同时容忍 `->` 和 `→`


### 阶段 3：executor 接入（F1-F3, E3, B2）

**F1: executor._execute_if 接入 dispatcher**
```python
def _execute_if(self, if_node: If) -> None:
    kind, expr = if_node.cond
    if kind == "var":
        # v0 值匹配模式：var [1:a, 2:b, 3:c]
        val = self.state.vars.get(expr, "")
        chosen = self._match_branch_by_value(if_node.branches, val)
    elif kind == "expr":
        # v1 表达式模式：expr 求值 → bool → 选 branch
        result = self.dispatcher.eval_bool(expr)
        chosen = if_node.branches[0] if result else if_node.branches[-1]
    # ... 处理 chosen target
```

**E3: If.cond 简化**
- `("var", "pick")` → 值匹配（v0 兼容）
- `("expr", "pick == 1")` → simpleeval 求值
- 新增 `("bool_expr", "pick == 1 and age >= 18")` 用于二元分支

**F2: ast_nodes.py If.cond 类型注解**
```python
@dataclass(frozen=True, slots=True)
class If:
    cond: tuple[str, str]  # (kind, expr)：kind="var"|"expr"|"bool_expr"
    branches: tuple[Branch, ...]
```

**F3: chapter01.md 加 v1 形态**
```neon
id:c1
pick <- next : ca
pick <- next : cb
node start
你听到门外传来两声敲门。
node in → pick
node if pick == 1 [1:pick, 2:pick]
node end
```

### 阶段 4：echo 拼接 + 修饰器增强（G4-G5）

**G4: echo 拼接**
- `node echo P-text + 是吗?我知道了.`
- 解析器：识别 `+` 拼接符，拆成变量 + 文本字面量
- executor：依次取值拼接，输出 TextEvt

**G5: 修饰器结构化参数**
- `@style text:[rgb:red,Px:12],bgm:start:1.mp3`
- 解析器：参数从简单 `key:val` 扩展为 `key:[p1,p2,...],key2:val2`
- DecoratorCall.args 从 `tuple[str,...]` 扩展为支持嵌套结构

### 阶段 5：清理与验证（B3-B6, F4 远期）

- B3: 硬编码路径修复
- B4: UnsupportedNodeError 死代码清除
- B5: register_node 占位砍掉
- B6: simpleeval 版本锁定
- F4: `@LLM-jud` 装饰器框架（远期，本次不实现）

---

## 5. 不做的事

- 不改双命名空间分离原则（标记段 + 剧本段）
- 不改 NEXT 三阶段机制的核心语义
- 不改进程间协议（EngineBus + JSON）
- 不改三层调度架构（simpleeval → fallback）
- 不实现 LLM 装饰器（F4 远期）
- 不加 PyQt6 GUI

---

## 6. 向后兼容策略

| 场景 | 策略 |
|---|---|
| v0 fixture `t_a<-next:ca` | 解析器容忍 `<-` 和 `←` |
| v0 fixture `node in ->var` | 解析器容忍 `->` 和 `→` |
| v0 fixture `node end`（无句号）| 不变，`node end` 就是标准 |
| v0 `If.cond = ("var", name)` | executor 保留值匹配路径 |
| v0 chapter01.md | 保留，新增 v1 fixture 而非覆盖 |

---

## 7. 验收标准

1. `python3 -m pytest tests/ -q` 全绿
2. 砍掉 translator 后，`tall == 1 and age >= 18` 可正确求值
3. `node in → pick` 和 `node in -> pick` 都能解析
4. `n2 ← next : cn2` 和 `n2 <- next : cn2` 都能解析
5. `node echo pick + 是吗?我知道了.` 正确拼接输出
6. `node if pick == 1 [1:ca, 2:cb]` 真求值，不走打桩
7. v0 chapter01.md 仍可正常运行
8. 新 v1 fixture 端到端测试通过

---

## 8. 执行顺序

```
阶段 1（砍 translator）    → 阶段 2（语法对齐）   → 阶段 3（executor 接入）
     ↓                            ↓                         ↓
  删文件 + 改 dispatcher       改解析器                  改 executor + ast_nodes
     ↓                            ↓                         ↓
  改测试                        加容忍                    新 fixture + 端到端
                                                            ↓
                                                     阶段 4（echo + 修饰器）
                                                            ↓
                                                     阶段 5（清理 + 验证）
```

---

*哈尼斯 · 2026-06-22 · 待 owner 拍板*
