# core.engine.expr — v1 表达式子系统

按 [ADR-0003](../adr/0003-v1-expression-subsystem.md) 实现。

## 职责

DSL 表达式文本 → `bool` / `int` 求值。与 `interpreter`(解析) / `executor`(执行) 平行, 不依赖 UI 层。

## 模块结构

| 文件 | 职责 |
| --- | --- |
| `errors.py` | 错误类: `ExprError` / `UnsupportedNodeError` / `DSLSyntaxError` |
| `builtin_funcs.py` | `BUILTIN_FUNCS` —— simpleeval 函数白名单 |
| `translator.py` | `ExprTranslator` —— DSL → Python 表达式字符串 |
| `custom.py` | `CustomExecutor` —— simpleeval fallback + 业务钩子 |
| `dispatcher.py` | `ExprDispatcher` —— 三层调度 (translator → simpleeval → fallback) |

## 公开 API

```python
from core.engine.expr import (
    ExprDispatcher,        # 调度器入口
    ExprTranslator,        # DSL 翻译器
    CustomExecutor,        # fallback 钩子
    ExprError,             # 错误基类
    DSLSyntaxError,        # 翻译阶段错误
    UnsupportedNodeError,  # simpleeval 兜底信号
    BUILTIN_FUNCS,         # 函数白名单常量
)
```

## 调度链

```
DSL 表达式 ("p_tall 大于等于 18")
  ↓ ExprTranslator.to_python_expr()
Python 表达式 ("p_tall>=18")
  ↓ SimpleEval.eval()
返回值 (bool / int / ...)
  ↓ TypeError (UnsupportedNode)
CustomExecutor.eval_fallback()
  ↓ ExprError
最终兜底错误
```

## 用法

```python
from core.engine.expr import ExprDispatcher, CustomExecutor

# 基础用法
dispatcher = ExprDispatcher(game_state)
result = dispatcher.eval_bool("p_tall 大于等于 18")  # bool

# 含剧情自定义函数
custom = CustomExecutor(game_state)
custom.register_function("rand_scene", lambda: random.randint(1, 5))
dispatcher = ExprDispatcher(game_state, custom=custom)
result = dispatcher.eval_bool("rand_scene() == 3")
```

## v1 阶段覆盖度

- ✅ `==` / `!=` / `>` / `>=` / `<` / `<=`
- ✅ `and` / `or` / `not` (Chinese: `且` / `或` / `非`)
- ✅ 函数调用 (白名单内: `len` / `int` / `str` / ...)
- ✅ 变量名引用 (`p_xxx`)
- ⏳ 简略 `?:` ternary (v2 拓展)
- ⏳ 范围匹配 `1~10` (v2 拓展)
- ⏳ 自定义 AST 节点 (v2 拓展)
- ⏳ 异步表达式 (v3 拓展)

## 测试

```
tests/core/test_expr_translator.py
tests/core/test_expr_dispatcher.py
tests/core/test_expr_custom.py
```

## 不变量 (按 ADR-0003 §5)

- **核心引擎无 UI 依赖** —— 本子包不 import 任何 GUI / runtime / editor 模块
- **表达式求值安全** —— simpleeval 白名单 + CustomExecutor 函数白名单
- **DSL 语法错尽早报** —— ExprTranslator 失败抛 `DSLSyntaxError` (继承 `ParserError`)
- **v0 向后兼容** —— `("var", name)` v0 形态仍走"值匹配", 不进 dispatcher
- **子包解耦** —— `expr/` 可独立 import + 单测, 不依赖 interpreter/executor
