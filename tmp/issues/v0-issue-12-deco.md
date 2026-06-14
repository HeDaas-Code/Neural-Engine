## Parent

#22（PRD-0001 父 issue）

## What to build

`src/core/engine/interpreter.py` 的**第七阶段**：解析 `@xxx` 修饰器行。

API：
- `parse_decorator(line: str, lineno: int) -> DecoratorCall | DecoratorStop`
- 复用 v0-issue-2 的 `DecoratorCall` / `DecoratorStop` dataclass

行为约定（ADR §4.2 + §4.3）：
- 修饰器名 = `@` 后第一个 token（snake_case 标识符）
- 后续 token 是 `args: list[str]`，按**逗号 + 可选空格**分割
- 每个 token 形态：
  - `key:val`（有冒号）→ 完整 token，保留为 `"key:val"`
  - `key`（无冒号，**裸 key**）→ 休止符语义 → 返回 `DecoratorStop(name="xxx", key="key")`
- 例：
  - `@style bgm:rain.mp3` → `DecoratorCall(name="style", args=["bgm:rain.mp3"])`
  - `@style bgm:rain.mp3, vol:0.5` → `DecoratorCall(name="style", args=["bgm:rain.mp3", "vol:0.5"])`
  - `@style bgm` → `DecoratorStop(name="style", key="bgm")`（休止符）

错误：
- 缺修饰器名（`@` 后空）→ `ParserError("empty decorator name at line N")`
- 修饰器名不合法（非 snake_case 标识符）→ `ParserError("invalid decorator name '...' at line N")`
- 同一行内混用 call + stop（如 `@style bgm:rain.mp3, vol:0.5, bgm`）——**v0 暂不**做严格校验，**全部 args 保留**为 call，**不**自动转 stop；**推荐 executor 阶段**按 last-wins 规则处理（v0-issue-15）

**v0-issue-10 hook**：v0-issue-10 看到 `@` 前缀行转交本 issue 的 `parse_decorator`

## Acceptance criteria

- [ ] `from core.engine.interpreter import parse_decorator` import 成功
- [ ] `tests/core/test_decorator_parse.py` 覆盖：
  - `@style bgm:rain.mp3` → DecoratorCall
  - `@style bgm:rain.mp3, vol:0.5` → DecoratorCall 多 args
  - `@style bgm` → DecoratorStop
  - `@` 缺名 → ParserError
  - `@X-Y` 不合法修饰器名 → ParserError
- [ ] `python -m pytest tests/` 全绿

## Blocked by

- #24（v0-issue-2 AST 节点 dataclass，`DecoratorCall`/`DecoratorStop` 来自那里）
- #29（v0-issue-7 块级骨架）
- #32（v0-issue-10 块内语句，`@` 路由点）
