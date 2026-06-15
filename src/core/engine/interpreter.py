"""v0 解析器入口：把 .md 拆成 NeonBlock 序列（v0-issue-6 第一阶段）。

v0-issue-6 只做围栏提取（不解析 neon 内容），后续 v0-issue-7..12 在此基础上
把 NeonBlock 编译成 Block / Story AST。

约定（ADR §2.1）：
- 只匹配精确 ```neon（不支持 ```Neon / ```NEON 变体——strip 后比较）
- 不嵌套；未关闭抛 ParserError
- 围栏外忽略
"""
from __future__ import annotations

from dataclasses import dataclass

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
