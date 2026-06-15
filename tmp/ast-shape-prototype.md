# Prototype v0-issue-2：AST 节点 shape 推演

## 回答的问题

按 v0-issue-2 body 落 AST dataclass 时，遇到 3 个**模糊点**——必须先定下来：

1. **`If.cond` 的精确 type 是什么？**  body 只写 "cond" 没 type
2. **`Branch.target` 是 `NextDecl | Echo | In` Union**——`Echo` 和 `In` **是否** `Node` 子类？
3. **`IdStart` / `Start` / `End` 用什么实现**——sentinel 单例？class without fields？enum？

## 实验方式

写一个 throwaway 脚本 `tmp/ast-shape-prototype.py`（**原型代码**，不 commit 到主模块），试着把 §附录 A chapter01 全部节点实例化一遍，看 type shape 是否自洽。

## 推演（不写代码，直接在文档里推理）

### 问题 1：`If.cond` 的 type

ADR §3.3 列了 3 种 `node if` 形态：
- 二元 `node if cond[a,b]`：`cond` 是变量名
- 多元 `node if var [1:a,2:b,3:c]`：`var` 是变量名
- 简略二元 `node [a?b:c]`：`a` 是"条件表达式（可执行语句，含 `node xxx`）"

v0 PRD 说"v0 阶段不真做条件判断"——那 `cond` **只**记录**变量名**即可（简略二元的 `a` 是表达式也降级存**字符串 token**）

**结论**：`If.cond: tuple[str, str] = ("var", "cond_name")`
- 第一个 string 是 kind：`"var"`（二元 / 多元）+ `"expr"`（简略）
- 第二个 string 是名字 / 表达式文本

### 问题 2：`Branch.target` Union

v0-issue-2 body 写 `Branch.target: NextDecl | Echo | In`——但 `Echo` 和 `In` **应该**是 `Node` 子类（块内执行区节点）。

**冲突**：如果 `Echo` 和 `In` 是 `Node`，那 `NextDecl` **不**是 `Node`（NextDecl 是元数据，**不是**块内执行节点）——那 `NextDecl | Echo | In` Union 的**最小公共基类**是 `object`，不能用 `Node` 替代。

**修法**：
- `Branch.target: BranchTarget` —— 定义 `BranchTarget = NextDecl | CallExpression`（**不**直接 `Echo` / `In`——这两是 Node，**不**该出现在分支项里"作为跳转目标"）
- `CallExpression` 是新 dataclass：`@dataclass(frozen=True, slots=True) class CallExpression: kind: Literal["echo", "in"], var: str`
- 分支项 `echo p_pick` → `CallExpression(kind="echo", var="p_pick")`
- 分支项 `in ->p_mood` → `CallExpression(kind="in", var="p_mood")`

→ 这样 `Branch` 内部只有 2 种：跳到 next_decl / 调一个 echo|in（打桩时用）

### 问题 3：Sentinel 实现

- Python 3.11+ 推荐 `dataclass(frozen=True, slots=True) class Start: pass`——空 dataclass 作 sentinel
- `IdStart` 同理
- `Start()` 每次构造都是新对象——**用模块级单例**：`START = Start()`、`ID_START = IdStart()`、`END = End()`

但 sentinel + frozen 有个坑：frozen 类的 `__eq__` 用 `==`——两个 `Start()` 实例**相等**。**OK**——单例语义靠**不重复构造**保证，**不**靠 `is` 比较。

→ `from ast_nodes import START` 是更清晰模式

## 决定（落 v0-issue-2 brief）

1. `If.cond: tuple[str, str]` —— `("var", name)` 或 `("expr", expr_text)`
2. `Branch.target: NextDecl | CallExpression` —— `CallExpression(kind="echo"|"in", var=...)`
3. `START = Start()` / `END = End()` / `ID_START = IdStart()` 模块级单例 + frozen dataclass

## 自洽性检查（手算）

chapter01 `c1` 块的 `node if p_pick [1:t_a,2:t_b,3:echo p_pick]` 实例化：

```python
If(
    cond=("var", "p_pick"),
    branches=[
        Branch(value=1, target=NextDecl(var_name="t_a", target_id="ca")),
        Branch(value=2, target=NextDecl(var_name="t_b", target_id="cb")),
        Branch(value=3, target=CallExpression(kind="echo", var="p_pick")),
    ],
)
```

✓ 自洽。

## 拒绝的方案

- ❌ `If.cond: str` —— 丢 kind 信息
- ❌ `Branch.target: Node` —— 混 next_decl（不是 Node）
- ❌ `enum.Enum` 做 sentinel —— 没必要，多余抽象
- ❌ `class Start: pass` 不 frozen —— issue 要求 frozen + slots
