## Parent

#22（PRD-0001 父 issue）

## What to build

落地 ADR §附录 A 的 `chapters/chapter01.md`（v0 全语法演示剧本），写端到端集成测试覆盖 §6 唯一跑通路径 + §8 MVP 表。

API：
- `chapters/chapter01.md` —— **精确**复制 ADR §附录 A（v0 官方 fixture）
- `tests/test_echo.md` —— 最小 fixture（`node in ->p_tall` + 输入 + `node echo p_tall` + `node end`）
- `tests/integration/test_chapter01_e2e.py` —— 端到端：用 `subprocess.Popen` spawn `python -m core.engine.main chapters/chapter01.md`，通过 `multiprocessing.Queue` 喂 `UserInputCmd`，断言收到的事件流
- `tests/integration/test_echo_path.py` —— 单元式端到端：用 `MemoryInputSink` + 真 `Executor` 跑 `tests/test_echo.md`，断言事件流

事件流断言样例（v0 唯一跑通路径）：
1. `text("雨夜。")`
2. `text("雨声从破旧窗户的缝隙中渗入。")`
3. `text("你坐在窗边，听着雨声。")`
4. `decorator("style", ["bgm:rain.mp3"])`
5. `prompt_input("p_mood")`
6. （喂 `UserInputCmd(value="平静")`）
7. `text("平静")`
8. `route(target="chapter02")` 或 `chapter_end()` —— 取决于 c1 块的第一分支

**§8 MVP 表逐条勾**：
- `id:xxx` / `id:start` / `id:endX` / `id:endX:chapterYY` 解析 → ✓（用 chapter01 fixture）
- `next:yyy` 单 next → ✓
- `xxx<-next:yyy` 多 next → ✓（c1 块）
- `node start` / `node end` → ✓
- 文本行推送 → ✓
- `node in` / `node echo` / `node next_id` → ✓
- `node if` 打桩（解析 + 占位执行） → ✓
- `@style` 修饰器 → ✓
- `id:endX:chapterYY` 触发 `route` 事件 → ✓
- 整行注释 → ✓

**不变量守护**（v0-issue-20 HITL 会做，本 issue 提前落 §11 自动化部分）：
- 不变量 #6：跨进程消息一律 JSON dict → 用 v0-issue-5 真 bus 验证
- 不变量 #7：单 next 简写与多 next 完整互斥 → v0-issue-9 已测
- 不变量 #10：分支项内省略 `node` 前缀 → v0-issue-11 已测

## Acceptance criteria

- [ ] `chapters/chapter01.md` 与 ADR §附录 A 字字相同（v0 官方 fixture）
- [ ] `tests/test_echo.md` 最小 fixture 可被 v0-issue-6..12 全管线解析
- [ ] `tests/integration/test_chapter01_e2e.py` 跑通：spawn + 喂输入 + 断言事件流
- [ ] `tests/integration/test_echo_path.py` 跑通：MemoryInputSink + 断言事件
- [ ] §8 MVP 表 18 条特性全部有测试覆盖
- [ ] `python -m pytest tests/` 全绿
- [ ] `python -m core.engine.main chapters/chapter01.md` 至少能跑（GUI 不可用时降级）

## Blocked by

- #22（父 PRD，**仅**为链接锚点）
- #23（v0-issue-1 仓库骨架）
- #24（v0-issue-2 AST 节点 dataclass）
- #25（v0-issue-3 命令 schema）
- #26（v0-issue-4 事件 schema）
- #27（v0-issue-5 EngineBus）
- #28（v0-issue-6 neon 围栏）
- #29（v0-issue-7 块级骨架）
- #30（v0-issue-8 元数据区）
- #31（v0-issue-9 next 归一）
- #32（v0-issue-10 块内语句）
- #33（v0-issue-11 node if 解析）
- #34（v0-issue-12 修饰器解析）
- #36（v0-issue-13 Executor 骨架）
- #37（v0-issue-14 核心节点执行）
- #38（v0-issue-15 修饰器执行）
- #39（v0-issue-16 if 打桩 + 路由）
- #40（v0-issue-17 core 进程入口）
- #41（v0-issue-18 GUI 占位）
