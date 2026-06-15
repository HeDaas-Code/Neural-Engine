# 20 · 状态机

> **TL;DR**：两种状态严格解耦——`GameState`（变量）跨节点保留，`decorator_state`（修饰器）块级清空。`node end` 是状态转移的唯一驱动器。

## 两状态视图

```
┌────────────────────────────────────────────────────────────┐
│  GameState (dict[str, str])                                 │
│  ─ 跨节点保留                                              │
│  ─ 初始为空字典                                            │
│  ─ node in ->var 写入                                       │
│  ─ node echo var 读取                                       │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│  decorator_state (dict[str, list[str]])                     │
│  ─ 块级作用域                                              │
│  ─ **node start 时清空**（v0-issue-15 决策，2026-06-15）   │
│  ─ @xxx key:val 覆盖                                       │
│  ─ @xxx key 休止符清空该 key                                │
│  ─ §11 不变量 #2                                           │
└────────────────────────────────────────────────────────────┘
```

**注意**：v0-issue-15 决策是 **node start 时清空**（不是 ADR §4.1 写的 "node end 时清空"）——这是 owner 在 v0-issue-15 工程笔记里做出的实现决策，**已被写进 raw-docs**。**wiki 与 raw-docs 一致**。

## NEXT 状态机

NEXT **不是** GameState 的一部分——它是 executor 内部维护的"下一步去哪"的引用，**永远跨两个命名空间**。详见 [[../10-design/namespace-semantics]]。

```
                 ┌───────────────────────────────────────────┐
                 │  当前 Block.next_table（NextDecl 列表）     │
                 │  dict[var_name, target_id]                │
                 └──────────────┬────────────────────────────┘
                                │ executor 解释
                                ▼
                 ┌───────────────────────────────────────────┐
                 │  NEXT = (var, id)                           │
                 │  (None, "c1")    单 next 简写              │
                 │  null            多 next 完整（待显式）     │
                 │  ("t_a", "ca")   node t_a / node if 第1分支 │
                 │  ("echo", None)  分支项 echo 占位（打桩）   │
                 └──────────────┬────────────────────────────┘
                                │ node end 触发
                                ▼
                 ┌───────────────────────────────────────────┐
                 │  1) NEXT 非空 → 跳 ID（变量名槽仅审计用） │
                 │  2) NEXT 空 + id:endX:chapterYY →          │
                 │     RouteEvt(target=chapterYY)              │
                 │  3) 否则 → ChapterEndEvt                   │
                 └───────────────────────────────────────────┘
```

> **跳转时只用 ID 槽**：NEXT 的变量名槽在 `next_table` 校验时用（一致性检查）；真正跳的是 ID 槽。详见 [[../10-design/namespace-semantics#next-引用跨两个命名空间的中转]]。

## 状态转移序列（以 ADR 附录 A 入口块为例）

```neon
id:start
next:c1                     # Block.next_table = [NextDecl(None, "c1")]
node start
雨夜。                       # → TextEvt("雨夜。", "narration")
@style bgm:rain.mp3         # → DecoratorEvt(name="style", args=["bgm:rain.mp3"])
                            #   decorator_state["style"] = ["bgm:rain.mp3"]
node in ->p_mood            # → PromptInputEvt(var="p_mood")
                            #   阻塞等 UserInputCmd
                            #   收到后 GameState["p_mood"] = "平静"
node echo p_mood            # → TextEvt(GameState["p_mood"], "echo") = TextEvt("平静", "echo")
node end                    # NEXT = (None, "c1") 非空 → 跳到 id:c1
                            # decorator_state 不在此清空（v0-issue-15 改到 node start 清）
```

## `node if` 决策细节（v0 打桩 / v1 真求值）

### v0（v0-issue-16，**当前生效**）：

```neon
node if p_pick [1:t_a, 2:t_b, 3:echo p_pick]
```

**解析时**（v0-issue-11）：构造 `If(cond="p_pick", branches=[Branch(1, NextDecl("t_a")), Branch(2, NextDecl("t_b")), Branch(3, Echo("p_pick"))])`

**执行时**（v0-issue-16，**打桩路径**）：
1. **永远选第一个分支**（按 `value` 排序最小）
2. 广播 `LogEvt(level="info", message="条件打桩")`
3. 把分支项解析为 `NEXT`：
   - `1:t_a` → NEXT = `("t_a", "ca")`（变量名槽=t_a，ID 槽=ca，通过 next_table 解析）
   - `3:echo p_pick` → NEXT = `("echo", None)`（v0 打桩语义）

**代码位置**：`src/core/engine/executor.py:227 _execute_if`（commit `abb67ab`，自 v0 完工后**0 行变化**——v1-issue-6 OPEN）。

### v1（v1-issue-6，**OPEN 待实现**）：

```
If.cond = ("bool_expr", "p_tall >= 18 且 p_age == 1")
         ↓ _execute_if 按 kind 分流
dispatcher = ExprDispatcher(game_state, custom=CustomExecutor(state))
result = dispatcher.eval_bool("p_tall >= 18 and p_age == 1")
         ↓ 按 branch.value 选第一个 match
chosen = first(branch for branch in if_node.branches if result.matches(branch.value))
         ↓ 解析 target（同 v0）
self.next = (target.var_name, target.target_id) if isinstance(target, NextDecl) else ...
```

**v1 真分支的 3 个 kind 分流**：

| kind | v1 处理 |
| --- | --- |
| `"var"` | **保持 v0 兼容**——`state.vars[cond[1]] == branch.value`，**不进 dispatcher** |
| `"bool_expr"` | `dispatcher.eval_bool(payload)` → 选第一个 `result == branch.value` 的分支 |
| `"expr"` | `dispatcher.eval_bool(payload)`（简略三元 `[a?b:c]` 走 `_SHORTCUT_TERNARY_RE` 翻译）|
| `"range"` | `lo <= state.vars[???] <= hi`（v2+，v1 不实现）|

**预估改动量**：~30 行 executor.py + 1 个 dispatcher 注入点（构造时或 `run_block` 入口）+ ~50 行测试改名（`*_stub_*` → `*_eval_*`）。

> **详细 v1 路线图**见 [[../40-issues/dashboard#v1-表达式子系统-prd-0002--adr-0003]]。**CodeGraph 唯一卡点确认**：`ExprDispatcher` 公开 API 已有，但**仅被测试调用**——`executor.py` 没 import `core.engine.expr.*`，所以 dispatcher 真值根本走不到 v0 的 `node if` 分支。

## 块级作用域 vs 跨块继承

```neon
# 块 1
node start                          # decorator_state 在此清空
@style bgm:rain.mp3                 # decorator_state["style"] = ["bgm:rain.mp3"]
node end

# 块 2
node start                          # ← 清空（v0-issue-15 决策）
@style bgm:storm.mp3                # 又赋一次
node end
```

## §5.3 node end 行为的命名空间视角

```python
def node_end_behavior(node, next_ref, next_table):
    if next_ref is None:
        if node.route_chapter is not None:    # ID 命名空间，含 chapterYY
            bus.put_evt(RouteEvt(target=node.route_chapter))
        else:
            bus.put_evt(ChapterEndEvt())
    else:
        var_name, node_id = next_ref
        jump_to_block(node_id)                # 跨块跳转
```

## 与其他页的关系

- [[../10-design/design-philosophy]] — 原则 1（命名空间分离）
- [[../10-design/namespace-semantics]] — NEXT 元组两槽语义
- [[overview]] — v0 实施路径（v0-issue-13/14/15/16）

## 引用源

- ADR-0001 §4.1（块级作用域）—— [[raw-docs/ADR-0001-v0-baseline-script-spec]]
- ADR-0001 §5（NEXT 语义）—— [[raw-docs/ADR-0001-v0-baseline-script-spec]]
- ADR-0001 §11 #2 #5（不变量）—— [[raw-docs/ADR-0001-v0-baseline-script-spec]]
- v0-issue-15（@style 块级作用域，**node start 清空**）—— [[raw-docs/工程笔记/v0-issue-15-deco-exec.md]]
- v0-issue-16（node if 打桩执行）—— [[raw-docs/工程笔记/v0-issue-16-if-end.md]]
- CONTEXT-core 强约束 —— [[raw-docs/CONTEXT-core.md]]