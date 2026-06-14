## Parent

#22（PRD-0001 父 issue）

## What to build

`src/core/engine/interpreter.py` 的**第一阶段**：从 .md 文件**只**提取 ```neon … ``` 围栏块，忽略其余 Markdown 内容，输出 `list[str]`（每个元素是一个 neon 块的**原文**，含围栏）。

API：
- `extract_neon_blocks(markdown_text: str) -> list[NeonBlock]`
- `NeonBlock` = `@dataclass(frozen=True) class NeonBlock: lineno: int, content: str, raw: str`
  - `lineno`：块首行（围栏 ```neon 那行）在原文件中的 1-indexed 行号
  - `content`：围栏内的内容（**不含** 围栏 ``` 行）
  - `raw`：完整原文（含开闭围栏）——给调试用

行为约定（ADR §2.1）：
- 只匹配**精确** ```neon 围栏（不支持 ```Neon / ```NEON / ```neon 变体——`strip` 后比较）
- **不**嵌套——发现未关闭围栏抛 `ParserError("unclosed neon fence at line N")`
- 围栏闭 ``` 必须是行首独立 ``` （可带 trailing 空格）
- 围栏外（```neon 之前的部分、闭围栏之后的部分、```markdown 围栏）一律忽略
- 围栏内**不**做内容解析——纯字符串保留

## Acceptance criteria

- [ ] `from core.engine.interpreter import extract_neon_blocks, NeonBlock` import 成功
- [ ] `tests/core/test_extract_neon.py` 覆盖：
  - 1 个 neon 块（基本）
  - 0 个 neon 块（纯 Markdown）→ `[]`
  - 多个 neon 块（顺序保留）
  - 围栏外 ```markdown 块、标题、序言——全部忽略
  - lineno 准确（多行围栏，lineno 是开围栏那行）
  - 未关闭围栏 → `ParserError`
  - 围栏变体 ```Neon / ```NEON 忽略
- [ ] `python -m pytest tests/` 全绿

## Blocked by

- #23（v0-issue-1 仓库骨架）
- #24（v0-issue-2 AST 节点 dataclass，`ParserError` 来自那里）
