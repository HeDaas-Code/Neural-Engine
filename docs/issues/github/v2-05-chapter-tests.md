## Parent

PDR：[`docs/pdr/phase3-v2p0.md`](../../pdr/phase3-v2p0.md) §5.2.4（章节加载器验收标准）
Issue 列表：[`docs/issues/phase3-v2p0.md`](../../issues/phase3-v2p0.md) V2-05
关联 EP：EP-10（`RouteEvt` 处理）

## What to build

`tests/integration/test_chapter_routing.py` 端到端 fixture 跨章节跳转；最小 `chapter01.md` 触发 `id:end1:chapter02` → 自动加载 `chapter02.md` → 变量 `pick` 跨章节保留。

### 步骤

1. **新建 `tests/integration/test_chapter_routing.py`**：
   - `test_chapter01_to_chapter02_via_route` —— 最小 chapter01.md + chapter02.md fixture，跨章节跳转
   - `test_state_vars_persist_across_chapters` —— chapter01 设置 var `pick=1`，chapter02 读取 var
   - `test_chapter_end_terminates_run` —— 收到 `ChapterEndEvt` 退出
   - `test_invalid_route_raises` —— `RouteEvt("nonexistent")` → `FileNotFoundError`
   - `test_chapter_manager_state_isolation` —— 跨章节不影响 GameState.next_table 块级重置

2. **Fixture 最小化**（`tests/integration/fixtures/`）：
   - `chapter01_minimal.md` —— 5-10 行：`id:start` + 1 个 `node echo hello` + `id:end1:chapter02`
   - `chapter02_minimal.md` —— 5-10 行：`id:start` + `node in → P-text` + `node end` + `id:end1`

3. **CI 路径**：`pytest tests/integration/test_chapter_routing.py` 全绿
   - 用 `tmp_path` fixture 注入临时 `chapters_dir`
   - 用 `MemoryEventSink` / `MemoryInputSink` 组合 mock bus

4. **现有 fixture 不破**：
   - `tests/integration/test_chapter_end.py`（v0 已有）继续工作
   - `tests/integration/` 下其他测试继续工作

5. **覆盖度**：跨章节跳转路径 100% 行覆盖（`ChapterManager.on_route` + `load_chapter_safe` + `Executor` 跨章节状态共享）

## Acceptance criteria

- [ ] `tests/integration/test_chapter_routing.py` 新建，至少 5 个测试
- [ ] `tests/integration/fixtures/chapter01_minimal.md` 新建（≤10 行）
- [ ] `tests/integration/fixtures/chapter02_minimal.md` 新建（≤10 行）
- [ ] `pytest tests/integration/test_chapter_routing.py` 全绿
- [ ] 跨章节变量保留验证（`pick=1` 在 chapter02 可读）
- [ ] 现有 `tests/integration/test_chapter_end.py` 不破
- [ ] 现有 211+ tests 维持 + 5+ 新测试
- [ ] CI 跑测时无依赖 PyQt6（仅用 `MemoryEventSink`）

## Blocked by

- V2-04（ChapterManager + RouteEvt 消费，#75）

## 关联依赖

- 不阻塞其他 issue
