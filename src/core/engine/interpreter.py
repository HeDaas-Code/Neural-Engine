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

from core.engine.ast_nodes import ParserError, BlockLocation


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
