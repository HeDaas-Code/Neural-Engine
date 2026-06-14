# 20 · AST 节点设计（v0-issue-2）

> **TL;DR**：`core/engine/ast_nodes.py` 提供 **18 个 dataclass(frozen=True, slots=True)** + 1 个错误类——**纯数据结构层**，不解析、不执行。详情见 [[raw-docs/工程笔记/v0-issue-2-ast.md]]。

## 设计原则

1. **纯叶子模块**——不引用 `interpreter / executor / bus`，只被它们 import
2. **`dataclass(frozen=True, slots=True)`**——不可变 + 省内存
3. **字段命名 snake_case**（不变量 #6 延伸）
4. **错误定位**——所有解析错误带 `loc: BlockLocation(lineno, col)`

## 18 个 dataclass 速查

### 顶层容器

```python
@dataclass(frozen=True, slots=True)
class Story:
    blocks: list[Block]                # 所有 neon 块按文件顺序

@dataclass(frozen=True, slots=True)
class Block:
    meta: list[Node]                   # 元数据区节点（id / next）
    next_table: list[NextDecl]         # next 变量声明（变量名 → ID）
    body: list[Node]                   # 块内执行区节点
```

### 错误定位

```python
@dataclass(frozen=True, slots=True)
class BlockLocation:
    lineno: int
    col: int

class ParserError(SyntaxError):
    def __init__(self, msg: str, loc: BlockLocation):
        super().__init__(f"{msg} (line {loc.lineno}, col {loc.col})")
        self.loc = loc
```

### 元数据区节点

```python
@dataclass(frozen=True, slots=True)
class IdMeta:
    id: str                            # id:xxx

@dataclass(frozen=True, slots=True)
class IdStart:                         # 单例式 sentinel
    ...

@dataclass(frozen=True, slots=True)
class IdEnd:
    x: int                             # 结局编号（0 = 缺省）
    route_chapter: str | None          # 路由目标（None = 普通结局）
```

### next 声明

```python
@dataclass(frozen=True, slots=True)
class NextDecl:
    var_name: str | None               # None = 单 next 简写（直达 ID）
    target_id: str                     # 节点 ID（ID 命名空间）
```

### 块内执行区节点

```python
@dataclass(frozen=True, slots=True)
class Start: ...                       # sentinel
@dataclass(frozen=True, slots=True)
class End: ...                         # sentinel

@dataclass(frozen=True, slots=True)
class Text:
    content: str                       # 普通文本行

@dataclass(frozen=True, slots=True)
class In:
    var: str                           # node in ->var

@dataclass(frozen=True, slots=True)
class Echo:
    var: str                           # node echo var

@dataclass(frozen=True, slots=True)
class NextId:
    target_id: str                     # 显式跳转：NEXT = target_id
```

### 条件节点（v0 打桩）

```python
@dataclass(frozen=True, slots=True)
class If:
    cond: str                          # 条件（v0 不求值，只解析）
    branches: list[Branch]             # 分支列表

@dataclass(frozen=True, slots=True)
class Branch:
    value: int                         # 比较值（1 / 2 / 3 ...）
    target: NextDecl | Echo | In       # 分支项：next 变量 / echo / in（§11 #10）
```

### 修饰器节点

```python
@dataclass(frozen=True, slots=True)
class DecoratorCall:
    name: str                          # @style
    args: list[str]                    # token 列表（["bgm:rain.mp3"]）

@dataclass(frozen=True, slots=True)
class DecoratorStop:
    name: str                          # @style
    key: str                           # 休止符裸 key（"bgm"）
```

## 为什么这样拆

| 拆分点 | 设计动机 |
| --- | --- |
| **`Story` vs `Block`** | 一个文件 = 一个 Story（v0 单章节），Story 持多个 Block |
| **`Block` 三段（meta/next_table/body）** | 元数据区 / next 声明 / 块内执行区物理分隔，解析器分别处理 |
| **`Branch.target` 是 `NextDecl \| Echo \| In`** | 分支项可以是 next 变量名 / echo 节点 / in 节点（§11 #10 允许省略 node 前缀）|
| **`IdEnd(x, route_chapter)` 合一** | 结局标记 + 路由目标绑定（§11 #5）|
| **`ParserError` 子类化 `SyntaxError`** | 调用方 `try/except SyntaxError` 仍可捕获；额外带 `loc` 信息 |
| **`Start/End` 单例式 sentinel** | 块边界在 body 里**只允许出现一次**，用 `is` 比较即可 |

## 与 ADR 的对应

| ADR 章节 | 对应 AST |
| --- | --- |
| §1 命名空间 | `IdMeta.id`（ID 命名空间）vs `In.var` / `Echo.var` / `NextDecl.var_name`（变量命名空间）|
| §2.3 章节路由 | `IdEnd.route_chapter` |
| §3.2 next 声明 | `NextDecl(var_name, target_id)` |
| §3.3 块内执行区 | `Text / In / Echo / NextId / If / Branch` |
| §4 修饰器 | `DecoratorCall / DecoratorStop` |
| §6 注释 | 解析器跳过 `#` 行，**不进 AST** |
| §11 #1 命名空间分离 | 解析器在 body 里遇到 `IdMeta` 必须报 `ParserError` |
| §11 #10 分支项省略 node | `Branch.target: NextDecl \| Echo \| In`（union 涵盖三种）|

## 验收（v0-issue-2 acceptance）

- ✅ `python -c "from core.engine.ast_nodes import ..."` 全部 import 成功
- ✅ 所有 dataclass 都是 `frozen + slots`
- ✅ `tests/core/test_ast_shapes.py` 至少 5 个断言（构造、字段、相等性、frozen、loc）
- ✅ `python -m pytest tests/` 全绿

## 引用源

- v0-issue-2 工程笔记 —— [[raw-docs/工程笔记/v0-issue-2-ast.md]]
- CONTEXT-core 术语表 —— [[raw-docs/CONTEXT-core.md]]
- 术语表（DataType 代号）—— [[../10-design/terminology]]

## 原文快照（核对用）

本 wiki 页是分析层，下面是仓库原文快照以备核对：

- [[raw-docs/工程笔记/v0-issue-2-ast.md]]
- [[raw-docs/CONTEXT-core.md]]
- [[raw-docs/ADR-0001-v0-baseline-script-spec §3]]（块结构）