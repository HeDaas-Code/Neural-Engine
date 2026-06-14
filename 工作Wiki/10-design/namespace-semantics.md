# 10 · 命名空间语义（核心澄清）

> **TL;DR**：ADR-0001 §1 划了**两个**命名空间——**ID 命名空间**（跨块）与**变量命名空间**（块内）。`next_var_table` 是**桥**：把块内的变量名映射到跨块的节点 ID。`NEXT` 是一个 `(var_name, node_id)` 元组，**永远不属于任一命名空间**——它是引用，跨两个命名空间。

## 两个命名空间（ADR §1 原文）

| 命名空间 | 内容 | 位置 | 跨块？ | 例子 |
| --- | --- | --- | --- | --- |
| **ID 命名空间** | `id:xxx` | 元数据区（`node start` 之前） | ✓ 跨块 | `id:c1`、`id:start`、`id:end1:chapter02` |
| **变量命名空间** | next 变量名 / 用户输入 / 临时值 | 块内执行区 | ✗ 块级 | `t_a`、`p_mood`、`p_pick` |

**铁律**（§11 不变量 #1）：
- `id:xxx` 只能出现在 `node start` **之前**
- 解析器在 `node start` **之后**遇到 `id:xxx` → SyntaxError

## 两个命名空间为什么必须分

`c1` 和 `c11` 在变量命名空间内**没有本质区别**（[ADR §1 末句](raw-docs/ADR-0001-v0-baseline-script-spec)）：

```neon
id:c1                              # ID 命名空间
node start
# c1 在这里就是普通变量名（虽然长得像 c1 的 id）
node in ->c1                       # 把用户输入存到变量 c1
node echo c1                       # 输出变量 c1
node end
```

如果不分，块内 `c1` 这个变量名会和"下一个叫 c1 的节点 ID"撞名——作者不敢用这种自然的命名。

## 桥：next_var_table

跨命名空间的跳转需要**字典映射**（[ADR §5.1](raw-docs/ADR-0001-v0-baseline-script-spec) + §11 不变量 #9）：

> **`<-` 冒号右边是 ID 命名空间，左边是变量命名空间**

```neon
id:c1
t_a <- next : ca       # 左边 t_a = 变量名（变量命名空间）
                       # 右边 ca  = 节点 ID（ID 命名空间）
t_b <- next : cb
```

`next_var_table` 就是这个字典（**块级作用域**，强约束 #4）：

```
next_var_table = {
    "t_a": "ca",      # 变量命名空间 → ID 命名空间
    "t_b": "cb",
}
```

## NEXT 引用：跨两个命名空间的"中转"

NEXT **不是字符串**，不是节点 ID，也不是变量名（§11 不变量 #3）。它的内部类型：

```
NEXT: tuple[str | None, str | None]
      └────────┬────────┘   └────┬────┘
       变量命名空间        ID 命名空间
```

| 场景 | NEXT 值 | 含义 |
| --- | --- | --- |
| 单 next 简写 `next:c1` | `(None, "c1")` | 变量名槽为空，ID 直接给 c1 |
| 多 next 完整 `t_a<-next:ca` | `null`（待显式） | 等执行 `node t_a` 才赋值 |
| 执行 `node t_a` | `("t_a", "ca")` | 通过 next_var_table 解析得到 |
| 执行 `node if p_pick [1:t_a, ...]` | `("t_a", "ca")` | 走第一个分支 |
| 分支项 `3:echo p_pick`（打桩） | `("echo", None)` | echo 是变量名引用，ID 槽为空（v0 不真跳 echo） |

## 跳转时跨命名空间的实际流程

```
executor.run() 在某个块执行 node end
        │
        ▼
读 NEXT = ("t_a", "ca")
        │   │       │
   变量名槽  │   ID 槽
        │   │       │
        │   └───────┼──→ 跳到 id:ca 的块（ID 命名空间，跨块）
        │           │
        └─→ next_var_table["t_a"] == "ca"  ← 桥
```

**关键**：NEXT 既包含变量名槽（让你能审计"我这次跳的是哪个变量名"），又包含 ID 槽（让你能直接定位）。**两者永不混淆**。

## §5.3 node end 行为的命名空间视角

```python
def node_end_behavior(node, next_ref, next_var_table):
    if next_ref is None:
        # 没有显式 NEXT——多 next 块没执行过 node t_a 的场景
        if node.route_target:                       # ID 命名空间，含 chapterYY
            bus.put_evt(RouteEvt(target=node.route_target))   # ID 命名空间事件
        else:
            bus.put_evt(ChapterEndEvt())
    else:
        # NEXT 引用解析：变量命名空间 → ID 命名空间
        var_name, node_id = next_ref
        # next_var_table[var_name] 应等于 node_id（不变量 #9）
        # 跳到 node_id 对应的块（ID 命名空间，跨块）
        jump_to_block(node_id)
```

## 三层命名空间视角对照表

| 视角 | 在哪出现 | 例子 |
| --- | --- | --- |
| **作者视角** | `.md` 剧本 | `id:c1`、`next:c1`、`node t_a`、`node in ->p_mood` |
| **解析器视角** | `Node` dataclass 字段 | `id`、`next_ref`、`next_var_table` |
| **执行器视角** | 运行时 NEXT 状态 | `("t_a", "ca")` 元组，跨两命名空间引用 |

## 自检问题

- ❓ `t_a<-next:ca` 里的 `t_a` 是 ID 还是变量？ → **变量**（变量命名空间）
- ❓ NEXT 是字符串吗？ → **不是**（§11 不变量 #3）
- ❓ 单 next 简写时变量名槽是空的吗？ → **是**，`(None, "c1")`
- ❓ `next_var_table` 跨块继承吗？ → **不**（强约束 #4，块级作用域）
- ❓ `id:end1:chapter02` 的三段都在 ID 命名空间吗？ → **是**（全 ID 命名空间）

## 与其他页的关系

- [[terminology]] — "不要用 Node 子类" 等纯术语
- [[design-philosophy]] — 原则 1（命名空间分离）的设计动机
- [[../20-architecture/state-machine]] — NEXT 状态机（运行时表现）
- [[../30-protocol/messages]] — 协议层的命名空间映射（不涉及，纯 wire 协议）

## 引用源

- ADR-0001 §1（术语与命名空间）—— [raw-docs/ADR-0001-v0-baseline-script-spec](raw-docs/ADR-0001-v0-baseline-script-spec)
- ADR-0001 §3.2（块结构）—— next 变量声明的语法
- ADR-0001 §5（命名空间与跳转机制）—— NEXT 语义
- ADR-0001 §11 不变量 #1, #3, #9 —— 命名空间 + NEXT + 跨命名空间定位
- `src/core/CONTEXT.md` 命名空间小节 —— [raw-docs/CONTEXT-core.md](raw-docs/CONTEXT-core.md)