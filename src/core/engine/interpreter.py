"""v0 解析器入口：把 .md 拆成 NeonBlock 序列 + 块级骨架解析。

v0-issue-6 第一阶段：extract_neon_blocks（只拆围栏，不解析内容）
v0-issue-7 第二阶段：parse_block_skeleton（识别 node start/end 边界）

约定（ADR §2.1 / §6）：
- 只匹配精确 ```` ```neon ````（不支持 ```` ```Neon ```` / ```` ```NEON ```` 变体）
- 不嵌套；未关闭抛 ParserError
- 围栏外忽略
- 整行注释（行首 ``#``）跳过
- 空行跳过
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core.engine.ast_nodes import (
    ParserError, BlockLocation, NextDecl, IdMeta, IdEnd,
    Start, End, Text, In, Echo, NextId,
    If, Branch, CallExpression,
    DecoratorCall, DecoratorStop,
)


@dataclass(frozen=True, slots=True)
class NeonBlock:
    """一个 neon 围栏块（含开闭围栏 + 块内原文）。"""
    lineno: int
    content: str
    raw: str

    @property
    def loc(self) -> BlockLocation:
        return BlockLocation(lineno=self.lineno, col=1)


_NEON_FENCE = "neon"
_NODE_START = "node start"
_NODE_END = "node end"


@dataclass
class BlockSkeleton:
    """块级骨架：node start 之前的元数据区 + 之后的执行区。"""
    meta_lines: list[str] = field(default_factory=list)
    body_lines: list[str] = field(default_factory=list)
    start_lineno: int = 0


def extract_neon_blocks(markdown_text: str) -> list[NeonBlock]:
    """扫 markdown_text 找 ```neon ... ``` 围栏块。

    行为：
    - 顺序扫描，每行做 .strip() 比较
    - 开围栏必须是行首的 ```neon（行内只含 ```neon，可 trailing 空格）
    - 闭围栏必须是行首的 ```（行内只含 ```，可 trailing 空格）
    - 未关闭抛 ParserError("unclosed neon fence at line N")
    - 围栏外全部忽略
    """
    # keepends=True 保留行尾换行，方便还原 raw / content
    lines = markdown_text.splitlines(keepends=True)
    blocks: list[NeonBlock] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()
        if stripped == f"```{_NEON_FENCE}":
            fence_lineno = i + 1  # 1-indexed
            content_start = i + 1
            # 找闭围栏
            j = content_start
            closed = False
            while j < n:
                if lines[j].strip() == "```":
                    closed = True
                    break
                j += 1
            if not closed:
                raise ParserError(
                    f"unclosed neon fence at line {fence_lineno}",
                    loc=BlockLocation(lineno=fence_lineno, col=1),
                )
            # content：开闭围栏之间的行（含行尾 \n）
            content = "".join(lines[content_start:j])
            # raw：开闭围栏之间 + 闭围栏行
            raw = "".join(lines[i:j + 1])
            blocks.append(NeonBlock(
                lineno=fence_lineno,
                content=content,
                raw=raw,
            ))
            i = j + 1
        else:
            i += 1

    return blocks


# ─── 第二阶段：块级骨架 ──────────────────────────────────────────────────────


def _is_full_line_comment(line: str) -> bool:
    """整行注释：strip 后以 # 开头（保留行内注释不在本 issue 范围）。"""
    return line.strip().startswith("#")


def _is_blank(line: str) -> bool:
    """空行：strip 后为空。"""
    return line.strip() == ""


def parse_block_skeleton(
    neon_content: str,
    lineno: int,
) -> tuple[BlockSkeleton, list[str]]:
    """从 neon 块原文识别 node start/end 边界，分 meta_lines + body_lines。

    Args:
        neon_content: extract_neon_blocks 输出的 content（不含围栏）
        lineno: 围栏开行的 1-indexed 行号（用于错误报告）

    Returns:
        (BlockSkeleton, 剩余行)：
        - meta_lines: node start 之前非空非注释行
        - body_lines: node start 之后到 node end 之前
        - 第二返回值: node end 之后剩余行（多块管线留接口）

    Raises:
        ParserError: 缺/多 node start, 缺/多 node end
    """
    lines = neon_content.splitlines(keepends=True)

    # 找 node start 第一次出现行
    start_idx: Optional[int] = None
    end_idx: Optional[int] = None
    start_count = 0
    end_count = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == _NODE_START:
            start_count += 1
            if start_idx is None:
                start_idx = i
        elif stripped == _NODE_END:
            end_count += 1
            if end_idx is None:
                end_idx = i

    if start_count == 0:
        raise ParserError(
            f"missing 'node start' at line {lineno}",
            loc=BlockLocation(lineno=lineno, col=1),
        )
    if start_count > 1:
        raise ParserError(
            f"duplicate 'node start' at line {lineno + start_idx + 1}",
            loc=BlockLocation(lineno=lineno + start_idx + 1, col=1),
        )
    if end_count == 0:
        raise ParserError(
            f"missing 'node end' at line {lineno}",
            loc=BlockLocation(lineno=lineno, col=1),
        )
    if end_count > 1:
        raise ParserError(
            f"duplicate 'node end' at line {lineno + end_idx + 1}",
            loc=BlockLocation(lineno=lineno + end_idx + 1, col=1),
        )

    # 收集 meta_lines（start 之前，跳过空行和注释）
    meta_lines = []
    for line in lines[:start_idx]:
        if _is_blank(line) or _is_full_line_comment(line):
            continue
        meta_lines.append(line)

    # v0-issue-17 fix: 保留 'node start' 和 'node end' 在 body_lines
    # （让 parse_block_body 能检查首条 / 末条 sentinel）
    body_lines = []
    for line in lines[start_idx:end_idx + 1]:
        if _is_blank(line) or _is_full_line_comment(line):
            continue
        body_lines.append(line)

    # 剩余行
    rest = lines[end_idx + 1:]

    return (
        BlockSkeleton(
            meta_lines=meta_lines,
            body_lines=body_lines,
            start_lineno=lineno,
        ),
        rest,
    )


# ─── 第三阶段：元数据区解析 ──────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class BlockMeta:
    """块级元数据区解析结果：所有 id: 语句 + 起始行号。"""
    ids: list[IdMeta | IdEnd]
    start_lineno: int


def _parse_id_line(line: str, lineno: int):
    """解析 'id:xxx' 单行，返回 IdMeta 或 IdEnd。"""
    # 去掉行尾换行 / 前后空白
    s = line.strip()
    if not s.startswith("id:"):
        raise ParserError(
            f"unexpected meta line {s!r} at line {lineno}",
            loc=BlockLocation(lineno=lineno, col=1),
        )
    payload = s[3:].strip()  # id: 之后

    if payload == "start":
        return IdMeta(id="start", lineno=lineno)

    if payload == "end":
        return IdEnd(x=None, route_chapter=None, lineno=lineno)

    if payload.startswith("end"):
        # end / endX / endX:chapterYY
        rest = payload[3:]  # end 之后
        if rest == "":
            return IdEnd(x=None, route_chapter=None, lineno=lineno)
        # rest 形如 "X" 或 "X:chapterYY"
        if ":" in rest:
            x_part, chapter_part = rest.split(":", 1)
        else:
            x_part, chapter_part = rest, None

        if not x_part.isdigit():
            # 浮点/字母/负数 → isdigit 都不通过；负数 '-' 不在 isdigit
            raise ParserError(
                f"end 后必须是自然数，得到 {x_part!r} at line {lineno}",
                loc=BlockLocation(lineno=lineno, col=1),
            )
        x = int(x_part)
        return IdEnd(x=x, route_chapter=chapter_part, lineno=lineno)

    # 普通 id:xxx
    return IdMeta(id=payload, lineno=lineno)


def parse_block_meta(meta_lines: list[str], start_lineno: int) -> BlockMeta:
    """解析块级元数据区。

    每行 lineno = start_lineno + 1 (跳过围栏) + 行 index。
    重复 id:xxx 抛 ParserError。
    """
    seen_ids: set[str] = set()
    specs: list = []
    fence_lineno = start_lineno
    for i, line in enumerate(meta_lines):
        # v0-issue-17 fix: 跳过 'next:' 行（v0-issue-9 parse_next_decls 处理）
        if line.strip().startswith("next:") or "<-next:" in line:
            continue
        # 围栏开行是 start_lineno；第一行 meta 在 start_lineno+1
        lineno = fence_lineno + 1 + i
        spec = _parse_id_line(line, lineno)
        # 重复检测：IdMeta 用 id 字段；IdEnd 不参与
        if isinstance(spec, IdMeta):
            if spec.id in seen_ids:
                raise ParserError(
                    f"duplicate id {spec.id!r} at line {lineno}",
                    loc=BlockLocation(lineno=lineno, col=1),
                )
            seen_ids.add(spec.id)
        specs.append(spec)
    return BlockMeta(ids=specs, start_lineno=fence_lineno)


# ─── 第四阶段：next 声明解析 ──────────────────────────────────────────────────


def _parse_next_line(line: str, lineno: int) -> NextDecl:
    """解析 'next:xxx' 或 'yyy <-next:xxx' 单行。"""
    s = line.strip()
    if "<-next:" in s:
        # yyy <-next: xxx
        var_part, target_part = s.split("<-next:", 1)
        var_name = var_part.strip()
        target_id = target_part.strip()
        if not var_name:
            raise ParserError(
                f"empty variable name in next decl at line {lineno}",
                loc=BlockLocation(lineno=lineno, col=1),
            )
        return NextDecl(var_name=var_name, target_id=target_id, lineno=lineno)
    elif s.startswith("next:"):
        # next: xxx
        target_id = s[len("next:"):].strip()
        if not target_id:
            raise ParserError(
                f"empty target in next decl at line {lineno}",
                loc=BlockLocation(lineno=lineno, col=1),
            )
        return NextDecl(var_name=None, target_id=target_id, lineno=lineno)
    else:
        raise ParserError(
            f"unexpected meta line {s!r} at line {lineno}",
            loc=BlockLocation(lineno=lineno, col=1),
        )


def parse_next_decls(
    meta_lines: list[str],
    start_lineno: int,
) -> list[NextDecl]:
    """解析元数据区 next 声明 + 互斥校验。

    - 单 next（0 或 1 条）：bare / named 都允许
    - 多 next（2+ 条）：必须全 named；bare 混合 → ParserError
    - 重复 var_name → ParserError
    - 重复 target_id：合法

    命名规则严格校验留给 executor。
    """
    decls: list[NextDecl] = []
    fence_lineno = start_lineno
    for i, line in enumerate(meta_lines):
        # v0-issue-17 fix: 跳过 'id:' 行（v0-issue-8 parse_block_meta 处理）
        if line.strip().startswith("id:") or "<-next:" in line and "id:" in line:
            continue
        # 简化：只处理以 next: 开头或包含 <-next: 的行
        if not (line.strip().startswith("next:") or "<-next:" in line):
            continue
        lineno = fence_lineno + 1 + i
        decls.append(_parse_next_line(line, lineno))

    # 互斥校验
    if len(decls) >= 2:
        bare_count = sum(1 for d in decls if d.var_name is None)
        if bare_count > 0:
            raise ParserError(
                f"bare 'next:' not allowed with {len(decls)}>1 next decls "
                f"at line {fence_lineno}",
                loc=BlockLocation(lineno=fence_lineno, col=1),
            )
    # 重复 var_name
    seen: set[str] = set()
    for d in decls:
        if d.var_name is None:
            continue
        if d.var_name in seen:
            raise ParserError(
                f"duplicate next var {d.var_name!r} at line {d.lineno}",
                loc=BlockLocation(lineno=d.lineno, col=1),
            )
        seen.add(d.var_name)

    return decls


# ─── 第五阶段：块内执行区解析 ──────────────────────────────────────────────────


def _parse_body_line(line: str, lineno: int):
    """解析块内执行区一行。返回 AST 节点 或 抛 ParserError。

    - 'node in ->var' / 'node in->var' → In(var)
    - 'node echo var' → Echo(var)
    - 'node next_id' → NextId(target_id)
    - '@xxx' → 保留为 Text（v0-issue-12 二次处理）
    - 普通文本 → Text(content=line)
    - 其他 → ParserError
    """
    s = line.strip()
    if s.startswith("node "):
        rest = s[len("node "):].strip()
        if rest == "start":
            return None  # sentinel: 调用方不生成节点
        if rest == "end":
            return None  # sentinel
        # node in / node echo / node xxx
        if rest.startswith("in"):
            # "in ->var" / "in->var"
            after = rest[len("in"):].strip()
            # 去 -> 前缀
            if after.startswith("->"):
                after = after[len("->"):].strip()
            if not after:
                raise ParserError(
                    f"empty var after 'node in' at line {lineno}",
                    loc=BlockLocation(lineno=lineno, col=1),
                )
            return In(var=after)
        if rest.startswith("echo"):
            var = rest[len("echo"):].strip()
            if not var:
                raise ParserError(
                    f"empty var after 'node echo' at line {lineno}",
                    loc=BlockLocation(lineno=lineno, col=1),
                )
            return Echo(var=var)
        # node xxx (xxx = next_id 形)
        # 本 issue 把任何 node xxx 视为 NextId，校验留给 v0-issue-16
        if rest:
            return NextId(target_id=rest)
        raise ParserError(
            f"empty node command at line {lineno}",
            loc=BlockLocation(lineno=lineno, col=1),
        )
    if s.startswith("@"):
        # 修饰器行：v0-issue-12 解析
        return parse_decorator(line, lineno)
    if s == "":
        # 空行（v0-issue-7 应该已跳过，但防御性）
        return None
    # 普通文本行
    return Text(content=line)


def parse_block_body(
    body_lines: list[str],
    start_lineno: int,
    *,
    block_meta: BlockMeta,
    next_table: list | None = None,
) -> list:
    """解析块内执行区，返回 list[Node]。

    首条非空行必须是 'node start'，末条非空行必须是 'node end'。
    返回 list 包含 Start() 在首位、End() 在末位。

    next_table: 用于 v0-issue-11 node if 解析；None 时 node if 抛 ParserError
    """
    fence_lineno = start_lineno
    if not body_lines:
        raise ParserError(
            f"empty body at line {fence_lineno + 1}",
            loc=BlockLocation(lineno=fence_lineno + 1, col=1),
        )
    if body_lines[0].strip() != "node start":
        raise ParserError(
            f"missing 'node start' at line {fence_lineno + 1}",
            loc=BlockLocation(lineno=fence_lineno + 1, col=1),
        )
    if body_lines[-1].strip() != "node end":
        raise ParserError(
            f"missing 'node end' at line {fence_lineno + 1}",
            loc=BlockLocation(lineno=fence_lineno + 1, col=1),
        )

    nodes: list = []
    for i, line in enumerate(body_lines):
        lineno = fence_lineno + 1 + i
        if line.strip() == "node start":
            continue
        if line.strip() == "node end":
            continue
        # v0-issue-11 路由: node if / node [...] 转交
        s = line.strip()
        if s.startswith("node if") or (s.startswith("node [") and "?" in s):
            if next_table is None:
                raise ParserError(
                    f"'node if' requires next_table at line {lineno}",
                    loc=BlockLocation(lineno=lineno, col=1),
                )
            nodes.append(parse_if_stmt(line, lineno, next_table=next_table))
            continue
        node = _parse_body_line(line, lineno)
        if node is None:
            continue
        nodes.append(node)

    return [Start(), *nodes, End()]


# ─── 第六阶段：node if 解析 ──────────────────────────────────────────────────


import re

_BINARY_IF_RE = re.compile(r"^node if\s+(\w+)\s*\[(\w+),(\w+)\]\s*$")
_MULTI_IF_RE = re.compile(r"^node if\s+(\w+)\s*\[([^\]]+)\]\s*$")
_SHORTCUT_IF_RE = re.compile(r"^node\s*\[([^?]+)\?(\w+):(\w+)\]\s*$")
# v1-issue-5: 新增 bool_expr (if? + 表达式) 和 range (if var ~ lo~hi) 形态
_BOOL_EXPR_IF_RE = re.compile(r"^node if\?\s+(.+?)\s*\[([^\]]+)\]\s*$")
_RANGE_IF_RE = re.compile(r"^node if\s+(\w+)\s+~\s*(-?\d+)~(\d+)\s*\[([^\]]+)\]\s*$")


def _build_next_lookup(next_table: list[NextDecl]) -> dict[str, NextDecl]:
    """var_name -> NextDecl 查表。"""
    return {d.var_name: d for d in next_table if d.var_name is not None}


def _parse_branch_item(
    item: str,
    lineno: int,
    next_lookup: dict[str, NextDecl],
):
    """解析多元分支项 'xxx' / 'echo xxx' / 'in ->xxx' / 'node xxx'。"""
    s = item.strip()
    # 去 node 前缀
    if s.startswith("node "):
        s = s[len("node "):].strip()
    if s.startswith("node\t"):
        s = s[len("node\t"):].strip()

    # echo / in 关键字
    if s.startswith("echo "):
        var = s[len("echo "):].strip()
        return CallExpression(kind="echo", var=var)
    if s.startswith("in"):
        after = s[len("in"):].strip()
        if after.startswith("->"):
            after = after[len("->"):].strip()
        return CallExpression(kind="in", var=after)

    # 裸变量名 → 查 next_table
    if s in next_lookup:
        return next_lookup[s]
    raise ParserError(
        f"unknown branch {s!r} at line {lineno}",
        loc=BlockLocation(lineno=lineno, col=1),
    )


def parse_if_stmt(
    line: str,
    lineno: int,
    *,
    next_table: list[NextDecl],
) -> If:
    """解析 'node if' / 'node [...]' 各种形态。

    三种形态：
    - 二元：node if cond[a,b]
    - 多元：node if var [1:a,2:b,3:echo p_pick]
    - 简略二元：node [a?b:c]
    """
    s = line.strip()
    next_lookup = _build_next_lookup(next_table)

    def _lookup(name: str):
        if name not in next_lookup:
            raise ParserError(
                f"unknown next var {name!r} at line {lineno}",
                loc=BlockLocation(lineno=lineno, col=1),
            )
        return next_lookup[name]

    # 简略二元：node [...]
    m = _SHORTCUT_IF_RE.match(s)
    if m and not s.startswith("node if"):
        a_expr, b, c = m.group(1).strip(), m.group(2), m.group(3)
        return If(
            cond=("expr", a_expr),
            branches=(
                Branch(value=0, target=_lookup(b)),
                Branch(value=1, target=_lookup(c)),
            ),
        )

    # v1-issue-5: bool_expr 形态 `node if? 表达式 [1:a,2:b]`
    # 必须在 binary/multi 之前匹配, 否则 `if?` 会被二元/multi 吞
    m = _BOOL_EXPR_IF_RE.match(s)
    if m:
        expr, body = m.group(1).strip(), m.group(2)
        branches_list = _parse_multi_branches(body, lineno, next_lookup)
        return If(cond=("bool_expr", expr), branches=tuple(branches_list))

    # v1-issue-5: range 形态 `node if var ~ lo~hi [...]`
    # 必须在 binary 之前匹配 (binary 期望 `[a,b]` 紧跟 var, 不期望 `~lo~hi`)
    m = _RANGE_IF_RE.match(s)
    if m:
        var_name, lo_str, hi_str, body = m.group(1), m.group(2), m.group(3), m.group(4)
        branches_list = _parse_multi_branches(body, lineno, next_lookup)
        return If(
            cond=("range", (int(lo_str), int(hi_str))),
            branches=tuple(branches_list),
        )

    # 二元
    m = _BINARY_IF_RE.match(s)
    if m:
        cond_name, a, b = m.group(1), m.group(2), m.group(3)
        return If(
            cond=("var", cond_name),
            branches=(
                Branch(value=0, target=_lookup(a)),
                Branch(value=1, target=_lookup(b)),
            ),
        )

    # 多元
    m = _MULTI_IF_RE.match(s)
    if m:
        var_name, body = m.group(1), m.group(2)
        branches_list = _parse_multi_branches(body, lineno, next_lookup)
        return If(cond=("var", var_name), branches=tuple(branches_list))

    raise ParserError(
        f"malformed 'node if' at line {lineno}: {s!r}",
        loc=BlockLocation(lineno=lineno, col=1),
    )


def _parse_multi_branches(body: str, lineno: int, next_lookup: dict) -> list:
    """把 '1:a,2:b,3:echo p_pick' 拆成 [Branch(...)]——bool_expr / range / multi 复用。

    拆分逻辑：每项 "N:item" 必须是 N: 前缀（v0 既有规则）。
    """
    items = [it.strip() for it in body.split(",") if it.strip()]
    branches_list: list = []
    for it in items:
        if ":" not in it:
            raise ParserError(
                f"multi-if branch item missing 'N:' prefix: {it!r} at line {lineno}",
                loc=BlockLocation(lineno=lineno, col=1),
            )
        val_str, item = it.split(":", 1)
        try:
            val = int(val_str.strip())
        except ValueError:
            raise ParserError(
                f"branch value must be integer, got {val_str!r} at line {lineno}",
                loc=BlockLocation(lineno=lineno, col=1),
            )
        target = _parse_branch_item(item, lineno, next_lookup)
        branches_list.append(Branch(value=val, target=target))
    return branches_list


# ─── 第七阶段：修饰器解析 ─────────────────────────────────────────────────────


_DECOR_NAME_RE = re.compile(r"^([a-z_]\w*)$")


def parse_decorator(line: str, lineno: int):
    """解析 @xxx 修饰器行，返回 DecoratorCall 或 DecoratorStop。

    判定规则：
    - 所有 args 都是裸 key（无 ':'）→ DecoratorStop(name=xxx, key=first_key)
    - 任一 arg 含 ':' → DecoratorCall(name=xxx, args=(...))
    - 无 args → DecoratorStop(name=xxx, key="")

    错误：
    - 缺名（@ 后空）→ ParserError
    - 非法名（非 snake_case）→ ParserError
    """
    s = line.strip()
    if not s.startswith("@"):
        raise ParserError(
            f"line does not start with '@' at line {lineno}",
            loc=BlockLocation(lineno=lineno, col=1),
        )
    rest = s[1:].strip()
    if not rest:
        raise ParserError(
            f"empty decorator name at line {lineno}",
            loc=BlockLocation(lineno=lineno, col=1),
        )

    # 拆 name + rest tokens（按空白切分，args 按逗号）
    parts = rest.split(None, 1)
    name = parts[0]
    args_str = parts[1] if len(parts) > 1 else ""

    if not _DECOR_NAME_RE.match(name):
        raise ParserError(
            f"invalid decorator name {name!r} at line {lineno}",
            loc=BlockLocation(lineno=lineno, col=1),
        )

    # 拆 args（按逗号 + 可选空格）
    if args_str.strip() == "":
        return DecoratorStop(name=name, key="")

    args = tuple(a.strip() for a in args_str.split(",") if a.strip())

    # 判定 call vs stop
    all_bare = all(":" not in a for a in args)
    if all_bare:
        # stop：用第一个 key
        return DecoratorStop(name=name, key=args[0])
    return DecoratorCall(name=name, args=args)
