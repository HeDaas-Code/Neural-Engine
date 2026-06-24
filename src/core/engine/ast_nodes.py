"""v0 AST 节点 dataclass + 错误类。

v0-issue-2 落地：纯数据结构层，不解析、不执行、不引用 executor/interpreter/bus/protocol。

字段命名 snake_case（不变量 #6 延伸）。
所有 dataclass 用 frozen=True + slots=True（不可变 + 内存紧凑）。
"""
from __future__ import annotations

from dataclasses import dataclass


# ─── 元数据区 ────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class IdMeta:
    id: str
    lineno: int


@dataclass(frozen=True, slots=True)
class IdStart:
    lineno: int = 0  # 默认 0，单例 ID_START 用


@dataclass(frozen=True, slots=True)
class IdEnd:
    x: int | None
    route_chapter: str | None
    lineno: int = 0


# ─── 块结构 ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class BlockLocation:
    lineno: int
    col: int


@dataclass(frozen=True, slots=True)
class NextDecl:
    var_name: str | None  # None = 单 next 简写
    target_id: str
    lineno: int = 0


@dataclass(frozen=True, slots=True)
class Block:
    meta: tuple  # tuple[IdMeta | IdStart | IdEnd, ...]
    next_table: tuple[NextDecl, ...]
    body: tuple  # tuple[Node-like, ...] 含 Start/End
    loc: BlockLocation


@dataclass(frozen=True, slots=True)
class Story:
    blocks: tuple[Block, ...]


# ─── 块内执行区 ──────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Start:
    lineno: int = 0


@dataclass(frozen=True, slots=True)
class End:
    lineno: int = 0


@dataclass(frozen=True, slots=True)
class Text:
    content: str


@dataclass(frozen=True, slots=True)
class In:
    var: str


@dataclass(frozen=True, slots=True)
class Echo:
    """echo 节点：输出变量或拼接文本。

    v0: var="p_mood" → 输出变量值
    v1 (ADR-0004): parts=("p_text", "是吗?我知道了.") → 拼接输出
    """
    var: str = ""
    parts: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class NextId:
    target_id: str


@dataclass(frozen=True, slots=True)
class CallExpression:
    """分支项里省略 node 前缀的简写：`echo p` / `in ->p`。"""
    kind: str  # "echo" | "in"
    var: str


@dataclass(frozen=True, slots=True)
class Branch:
    value: int
    target: NextDecl | CallExpression


@dataclass(frozen=True, slots=True)
class If:
    """v0/v1 node if 节点。

    cond: (kind, expr_str) 二元组
        - VAR_KIND       ("var", "<name>"): 变量值匹配, 适用于 `node if cond [a, b]` 和 `node if cond [1:a, 2:b]`
        - EXPR_KIND      ("expr", "<expr>"): 表达式值匹配, 适用于 `node if <expr> [1:a, 2:b]`
        - BOOL_EXPR_KIND ("bool_expr", "<expr>"): 表达式布尔求值, 适用于
                                `node if <expr> [a, b]` (二元) 和 `node [a?b:c]` (简略二元)
    branches: (Branch, ...) 二元组
    """
    cond: tuple[str, str]
    branches: tuple[Branch, ...]


# If.cond kind 常量 (D1 修法: 显式定义, 避免硬编码)
VAR_KIND = "var"
EXPR_KIND = "expr"
BOOL_EXPR_KIND = "bool_expr"


@dataclass(frozen=True, slots=True)
class DecoratorCall:
    name: str
    args: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DecoratorStop:
    name: str
    key: str


# ─── Sentinel 单例 ───────────────────────────────────────────────────────────


START = Start()
END = End()
ID_START = IdStart()


# ─── 错误类 ──────────────────────────────────────────────────────────────────


class ParserError(SyntaxError):
    """解析期语法错误，带可选位置。"""

    def __init__(self, message: str, loc: BlockLocation | None = None):
        super().__init__(message)
        self.loc = loc
