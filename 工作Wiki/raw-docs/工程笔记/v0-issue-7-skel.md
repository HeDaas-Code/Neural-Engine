## Parent

#22（PRD-0001 父 issue）

## What to build

`src/core/engine/interpreter.py` 的**第二阶段**：在 v0-issue-6 拆分出的 neon 块原文基础上，**块级骨架解析**：
- 识别 `node start` / `node end` 边界
- 块内**整行注释**（行首 `#`）静默跳过（v0 §6 限定）
- 块内**空行**静默跳过
- 元数据区 vs 块内执行区二分

API：
- `parse_block_skeleton(neon_content: str, lineno: int) -> tuple[BlockSkeleton, list[str]]`
- `BlockSkeleton` = `@dataclass class BlockSkeleton: meta_lines: list[str], body_lines: list[str], start_lineno: int`
  - `meta_lines`：`node start` 之前的所有非空、非整行注释行（**原文**，不做解析）
  - `body_lines`：`node start` 之后到 `node end` 之前的所有非空、非整行注释行（**原文**）
  - `start_lineno`：原始文件行号（用于错误报告）

错误：
- 缺 `node start` → `ParserError("missing 'node start' at line N")`
- 缺 `node end` → `ParserError("missing 'node end' at line N")`
- 多 `node start` → `ParserError("duplicate 'node start' at line N")`
- 多 `node end` → `ParserError("duplicate 'node end' at line N")`
- `node start` 不是块内执行区首条非空行（v0-issue-8 元数据区解析依赖这个）——本 issue **不**做严格首条检查（留给 v0-issue-8 元数据区统一处理），只二分

行为约定：
- `node start` / `node end` 必须**精确**匹配（小写、精确拼写），前缀空格允许，trailing 空格允许
- 整行注释（`^\s*#`）跳过
- 空行跳过
- 块内其他内容（`id:xxx` / `next:yyy` / `node in` / `@style` / 文本行）原样保留在 meta_lines 或 body_lines，**本 issue 不解析**

## Acceptance criteria

- [ ] `from core.engine.interpreter import parse_block_skeleton, BlockSkeleton` import 成功
- [ ] `tests/core/test_block_skeleton.py` 覆盖：
  - 1 个块正常（meta + start + body + end）
  - 缺 `node start` → ParserError
  - 缺 `node end` → ParserError
  - 多 `node start` → ParserError
  - 多 `node end` → ParserError
  - 整行注释跳过
  - 空行跳过
  - lineno 准确
- [ ] `python -m pytest tests/` 全绿

## Blocked by

- #23（v0-issue-1 仓库骨架）
- #24（v0-issue-2 AST 节点 dataclass，`ParserError` 来自那里）
- #28（v0-issue-6 neon 围栏拆分）
