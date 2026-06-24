# ADR-0004 附录：偏差登记（v1 重构实现 vs 设计）

> **关联 issue**: #65
> **执行人**: 哈尼斯（独立第三方审计）
> **执行日期**: 2026-06-22
> **PR**: #66 (已合并)

---

## 1. 设计 vs 实现对照

### 1.1 已按设计完成

| 设计项 | 实现状态 | 证据 |
|---|---|---|
| E1: 砍 translator.py | ✅ | 文件已删除 |
| E2: 表达式回退原生 Python | ✅ | dispatcher 直接 simpleeval.eval(expr) |
| E4: dispatcher 两层调度 | ✅ | simpleeval → fallback |
| G1: ← 箭头容忍 | ✅ | _parse_next_line 正则匹配 |
| G2: → 箭头容忍 | ✅ | parse_block_body 箭头检测 |
| G4: echo 拼接 | ✅ | Echo.parts + executor 拼接逻辑 |
| F1: executor 真求值 | ✅ | _execute_if 接入 ExprDispatcher |
| B3: 硬编码路径修复 | ✅ | 18 个测试文件改 __file__ |
| B4: UnsupportedNodeError 清除 | ✅ | errors.py 保留类但 dispatcher 不再用 |
| B5: register_node 砍掉 | ✅ | custom.py 已删 |

### 1.2 实现与设计的偏差

| # | 设计 | 实际实现 | 原因 | 影响 |
|---|---|---|---|---|
| D1 | If.cond 是 `("bool_expr", ...)` 第三种 kind | ✅ **已修复（2026-06-24 阶段一）**：新增 `BOOL_EXPR_KIND` 区分二元布尔与多元素值匹配；executor 增加 `VAR_KIND`/`EXPR_KIND`/`BOOL_EXPR_KIND` 常量做防御性断言 | 原方案二元 if 用 `("expr", ...)` + branches 数量判断；改用显式 kind 后类型安全 | 类型更安全，新增 2 个单测（215/215 passed） |
| D2 | G5: 修饰器结构化参数 `@style text:[rgb:red,Px:12]` | ✅ **已修复（2026-06-24 阶段一，MVP）**：interpreter 支持 `[item1,item2,...]` 顶层列表参数；保留 `key:val` 向后兼容 | MVP 范围：仅顶层列表，不嵌套 | 新增 4 个单测覆盖结构化参数 |
| D3 | F2: If.cond 类型注解用 union | 未修复（owner 未拍板，保留） | 两种 kind 都是 str，union 没有实际意义 | 无影响 |
| D4 | B2: TypeError 捕获收窄到 NameNotDefined/FunctionNotDefined | ✅ **已修复（2026-06-24 阶段一，路径 A）**：dispatcher except 收窄到 `InvalidExpression` 子类 + fallback to TypeError 字符串过滤 | simpleeval 1.x 的 `InvalidExpression` 是基类，具体子类需要按字符串过滤 | 收窄到 InvalidExpression + 3 个新单测覆盖 |
| D5 | B6: simpleeval 版本锁定 | ✅ **已修复（2026-06-24 阶段一）**：pyproject.toml 锁定 `simpleeval==1.0.7` | baseline 实装版本 | CI 可复现；新增 2 个测试覆盖版本约束 |
| D6 | F4: @LLM-jud 装饰器框架 | 未修复（远期） | 远期目标 | 无影响 |

### 1.3 设计中未提及但实现中新增的

| # | 新增内容 | 原因 |
|---|---|---|
| N1 | `_EXPR_BINARY_IF_RE` 正则 + `parse_if_stmt` 表达式二元 if 匹配 | 设计中 F3 写的 `node if pick == 1 [1:pick, 2:pick]` 语义不清，实际需要 `node if expr [a, b]`（True→a, False→b）二元形态 |
| N2 | `node in` 输入值尝试 int 转换 | simpleeval 中 `"1" == 1` 是 False，需要 int 转换让数值比较生效 |
| N3 | `run_block` 中 bare next（var_name=None）初始化 | 设计中未明确，但 v0 fixture `next: c1` 需要 executor 在块开始时设 NEXT |
| N4 | `_EXPR_IF_RE` 多元表达式 if | 设计中只提了二元，但多元 `node if expr [1:a, 2:b]` 也需要支持 |

---

## 2. 不变量守护

| 不变量 | 状态 | 说明 |
|---|---|---|
| 命名空间分离 | ✅ | 未改 |
| 块级作用域 | ✅ | 未改 |
| NEXT 三阶段 | ✅ | 未改核心语义，只加了 bare next 初始化 |
| v0 向后兼容 | ✅ | chapter01.md 仍可运行，211 passed |
| simpleeval 沙箱 | ✅ | 白名单未改 |
| 双箭头容忍 | ✅ | ← / <- 和 → / -> 都接受 |

---

## 3. 验收标准复核

| # | 验收标准 | 状态 |
|---|---|---|
| 1 | pytest 全绿 | ✅ 211 passed, 0 failed |
| 2 | `tall == 1 and age >= 18` 可求值 | ✅ test_expr_dispatcher 验证 |
| 3 | `node in → pick` 和 `-> pick` 都能解析 | ✅ test_arrow_syntax 验证 |
| 4 | `n2 ← next : cn2` 和 `<- next : cn2` 都能解析 | ✅ test_arrow_syntax 验证 |
| 5 | `node echo pick + 是吗?我知道了.` 拼接输出 | ✅ test_v1_e2e 验证 |
| 6 | `node if pick == 1 [t_a, t_b]` 真求值 | ✅ test_v1_e2e 验证 |
| 7 | v0 chapter01.md 仍可运行 | ✅ test_v0_chapter_still_works |
| 8 | 新 v1 fixture 端到端测试通过 | ✅ test_v1_e2e 5/5 passed |

---

## 4. owner 必审查项

1. **D1**: 不加 `bool_expr` kind——二元 if 用 `("expr", ...)` + branches 数量判断。是否接受？
2. **D2**: G5 修饰器结构化参数未实现——是否需要补？
3. **D4**: TypeError 捕获未收窄——simpleeval API 限制。是否接受？
4. **N2**: `node in` 输入值自动 int 转换——是否接受这个隐式行为？
5. **N3**: bare next 在 `run_block` 开头初始化 NEXT——是否符合 NEXT 三阶段语义？

---

*哈尼斯 · 2026-06-22 · PR #66 已合并*
