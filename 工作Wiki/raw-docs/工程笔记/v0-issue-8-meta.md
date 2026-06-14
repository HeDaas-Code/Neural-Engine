## Parent

#22（PRD-0001 父 issue）

## What to build

`src/core/engine/interpreter.py` 的**第三阶段**：解析块级元数据区，输出 `BlockMeta` 对象。

API：
- `parse_block_meta(meta_lines: list[str], start_lineno: int) -> BlockMeta`
- `BlockMeta` = `@dataclass(frozen=True) class BlockMeta: ids: list[IdSpec], start_lineno: int`
- `IdSpec` = `@dataclass(frozen=True) class IdSpec: kind: Literal["normal", "start", "end"], id: str | None, x: int | None, route_chapter: str | None, lineno: int`
  - `kind="start"`：`id:start`，`id="start"`，`x=None`，`route_chapter=None`
  - `kind="end"`：`id:end` / `id:endX` / `id:endX:chapterYY`，`id=None`，`x=int`、`route_chapter=可选`
  - `kind="normal"`：`id:xxx` 普通 ID

行为约定（ADR §2.2 + §2.3）：
- 元数据区允许的语句**只有** `id:xxx`（`node start` 之前）——其他前缀（`next:` / `xxx<-next:`）由 v0-issue-9 处理
- `id:start` 整文件必须**唯一**——本 issue 不做跨块校验（留给 v0-issue-10 块级语句解析统一处理），只解析 + 返回
- `id:endX` 中 X 必须是自然数（0 也算）——`X="01"` 视为合法（不严格去前导零）
- `id:endX:chapterYY` 第三段 `chapterYY` 是路由目标章节文件名（不含 `.md`）
- 重复 `id:xxx`（同块内）抛 `ParserError("duplicate id 'xxx' at line N")`
- 未识别的前缀在元数据区抛 `ParserError("unexpected meta line '...' at line N")`（**不**留给 v0-issue-14——本 issue 范围）

## Acceptance criteria

- [ ] `from core.engine.interpreter import parse_block_meta, BlockMeta, IdSpec` import 成功
- [ ] `tests/core/test_block_meta.py` 覆盖：
  - 1 个 `id:start` 块
  - 1 个 `id:xxx` 普通 ID 块
  - 1 个 `id:end` / `id:end1` / `id:end2:chapter02` 块
  - 多 ID 块（按出现顺序）
  - 重复 ID → ParserError
  - 未识别前缀 → ParserError
  - `endX` 中 X 非自然数 → ParserError
- [ ] `python -m pytest tests/` 全绿

## Blocked by

- #23（v0-issue-1 仓库骨架）
- #24（v0-issue-2 AST 节点 dataclass）
- #28（v0-issue-6 neon 围栏拆分）
- #29（v0-issue-7 块级骨架）
