## Parent

#22（PRD-0001 父 issue）

## What to build

`src/core/engine/executor.py` 第三步：实现 `@xxx` 修饰器执行 + 块级作用域（不变量 #2）。

API（在 v0-issue-13 / v0-issue-14 基础上追加）：
- `Executor._deco_state: dict[str, str]` 修饰器状态表（key=`修饰器名.key`）
- `Executor._emit_decorator(deco: DecoratorCall | DecoratorStop) -> None`

行为约定（ADR §4.1 + §4.2 + 不变量 #2）：
- `DecoratorCall(name="style", args=["bgm:rain.mp3"])` →
  1. 解析 args 为 `dict[str, str]`（按 `:` split；**无冒号**的裸 key **不**进 dict，单独保留为 last-seen 标记）
  2. 更新 `self._deco_state[name]` 中对应 key
  3. 广播 `DecoratorEvt(name=name, args=[原始 token 列表])`（**注意**：args 是**原始 token 列表**，不是 dict）
- `DecoratorStop(name="style", key="bgm")` →
  1. `self._deco_state["style"].pop("bgm", None)`（仅清单个 key）
  2. 广播 `DecoratorEvt(name="style", args=[key])`（休止符也广播**仅** key）
- 块级作用域：每进入新块 `self._deco_state.clear()`——不变量 #2（v0 在 `run_block` 开头清，不是在 `End` 时清；**v0 行为选择**：**进入时清**——比"结束时清"更稳妥，避免一个块末尾的修饰器被下一块继承。**实施 agent 拍板**）

设计要点：
- **不**真做多媒体播放——只广播事件（ADR §8 表中"打桩"项）
- 装饰器 last-wins 语义：同 key 后到覆盖前到；同 key 多个 `key:val` 在 args 列表中按顺序处理，**最后**一个生效
- `DecoratorCall` 与 `DecoratorStop` 都广播 `DecoratorEvt`——GUI 据 `args` 形态判别（`["bgm"]` 无冒号 = 休止；`["bgm:rain.mp3"]` 有冒号 = 调用）

## Acceptance criteria

- [ ] `from core.engine.executor import Executor` 现有 import 仍可
- [ ] `tests/core/test_executor_decorator.py` 覆盖：
  - `@style bgm:rain.mp3` → `DecoratorEvt(name="style", args=["bgm:rain.mp3"])` 发出 + `_deco_state["style.bgm"]="rain.mp3"`
  - `@style bgm:rain.mp3, vol:0.5` → 两个 key 都进 state + `DecoratorEvt` 广播 args 完整
  - `@style bgm` → 休止符，state 清 bgm + `DecoratorEvt(name="style", args=["bgm"])`
  - 块级作用域：块 A 设 `@style bgm:rain.mp3`，块 B 没设 → 块 B 起始 `_deco_state` 为空
  - last-wins：同 key 后到覆盖前到
- [ ] `python -m pytest tests/` 全绿

## Blocked by

- #24（v0-issue-2 AST 节点 dataclass）
- #26（v0-issue-4 事件 schema，`DecoratorEvt` 来自那里）
- #34（v0-issue-12 修饰器解析，`DecoratorCall`/`DecoratorStop` 来自那里）
- #36（v0-issue-13 Executor 骨架）
- #37（v0-issue-14 核心节点执行，`run_block` 入口来自那里）
