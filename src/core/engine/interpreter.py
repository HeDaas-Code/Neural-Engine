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

from core.engine.ast_nodes import ParserError, BlockLocation, NextDecl


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

    # 收集 body_lines（start 之后到 end 之前）
    body_lines = []
    for line in lines[start_idx + 1:end_idx]:
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
class IdSpec:
    """元数据区一条 id 语句的解析结果。"""
    kind: str  # "normal" | "start" | "end"
    id: str | None
    x: int | None
    route_chapter: str | None
    lineno: int


@dataclass(frozen=True, slots=True)
class BlockMeta:
    """块级元数据区解析结果：所有 id: 语句 + 起始行号。"""
    ids: list[IdSpec]
    start_lineno: int


def _parse_id_line(line: str, lineno: int) -> IdSpec:
    """解析 'id:xxx' 单行。"""
    # 去掉行尾换行 / 前后空白
    s = line.strip()
    if not s.startswith("id:"):
        raise ParserError(
            f"unexpected meta line {s!r} at line {lineno}",
            loc=BlockLocation(lineno=lineno, col=1),
        )
    payload = s[3:].strip()  # id: 之后

    if payload == "start":
        return IdSpec(
            kind="start", id="start", x=None, route_chapter=None, lineno=lineno,
        )

    if payload == "end":
        return IdSpec(
            kind="end", id=None, x=None, route_chapter=None, lineno=lineno,
        )

    if payload.startswith("end"):
        # end / endX / endX:chapterYY
        rest = payload[3:]  # end 之后
        if rest == "":
            return IdSpec(
                kind="end", id=None, x=None, route_chapter=None, lineno=lineno,
            )
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
        return IdSpec(
            kind="end", id=None, x=x, route_chapter=chapter_part, lineno=lineno,
        )

    # 普通 id:xxx
    return IdSpec(
        kind="normal", id=payload, x=None, route_chapter=None, lineno=lineno,
    )


def parse_block_meta(meta_lines: list[str], start_lineno: int) -> BlockMeta:
    """解析块级元数据区。

    每行 lineno = start_lineno + 1 (跳过围栏) + 行 index。
    重复 id:xxx 抛 ParserError。
    """
    seen_ids: set[str] = set()
    specs: list[IdSpec] = []
    fence_lineno = start_lineno
    for i, line in enumerate(meta_lines):
        # 围栏开行是 start_lineno；第一行 meta 在 start_lineno+1
        lineno = fence_lineno + 1 + i
        spec = _parse_id_line(line, lineno)
        # 重复检测：normal kind 用 id；start/end 不参与（id 字段语义不同）
        if spec.kind == "normal":
            assert spec.id is not None
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
