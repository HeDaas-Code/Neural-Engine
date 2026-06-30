## Parent

PDR：[`docs/pdr/phase3-v2p0.md`](../../pdr/phase3-v2p0.md) §5.2（章节加载器）
Issue 列表：[`docs/issues/phase3-v2p0.md`](../../issues/phase3-v2p0.md) V2-04
关联 EP：EP-10（`RouteEvt` 处理）+ EP-11（`LoadChapterCmd` 消费）
关联决策：D1（顺序：章节在 GUI 之后做）

## What to build

新建 `src/runtime/chapter_manager.py` 订阅 `RouteEvt` → 加载新章节 → 新建 Executor.run()；抽取 `src/runtime/load_chapter.py` 复用 `_load_story` 4 项路径校验；`main.py` 启动时改用 `ChapterManager.run()`。

### 步骤

1. **新建 `src/runtime/load_chapter.py`**（从 `main.py:28-51` 抽取）：
   ```python
   """加载章节 → Story。复用 main._load_story 4 项校验：symlink/CHAPTERS_ROOT/.md/1MB。"""
   from pathlib import Path
   from core.engine.ast_nodes import Block as AstBlock, Story
   from core.engine.interpreter import (
       extract_neon_blocks, parse_block_skeleton,
       parse_block_meta, parse_next_decls, parse_block_body,
   )

   def load_chapter_safe(chapter_path: Path) -> Story:
       text = chapter_path.read_text(encoding="utf-8")
       blocks_text = extract_neon_blocks(text)
       blocks = []
       for nb in blocks_text:
           skel, _ = parse_block_skeleton(nb.content, lineno=nb.lineno)
           meta = parse_block_meta(skel.meta_lines, start_lineno=nb.lineno)
           next_decls = parse_next_decls(skel.meta_lines, start_lineno=nb.lineno)
           body = parse_block_body(
               skel.body_lines,
               start_lineno=nb.lineno,
               block_meta=meta,
               next_table=next_decls,
           )
           blocks.append(AstBlock(
               meta=tuple(meta.ids),
               next_table=tuple(next_decls),
               body=tuple(body),
               loc=nb.loc,
           ))
       return Story(blocks=tuple(blocks))
   ```

2. **新建 `src/runtime/chapter_manager.py`**：
   ```python
   """章节加载器 —— 订阅 RouteEvt 跨章节跳转。"""
   from pathlib import Path
   from core.engine.bus import EngineBus
   from core.engine.executor import Executor
   from core.engine.protocol import RouteEvt, ChapterEndEvt
   from runtime.load_chapter import load_chapter_safe

   class ChapterManager:
       def __init__(self, chapters_dir: Path, bus: EngineBus, *, shared_state=None):
           self.chapters_dir = chapters_dir
           self.bus = bus
           self._shared_state = shared_state  # 跨章节状态共享

       def on_route(self, evt: RouteEvt) -> None:
           chapter_path = self.chapters_dir / f"{evt.target}.md"
           story = load_chapter_safe(chapter_path)
           kwargs = {"sink": self.bus}
           if self._shared_state is not None:
               kwargs["state"] = self._shared_state
           executor = Executor(story, **kwargs)
           executor.run()  # 同步阻塞（v2 简化）

       def run(self) -> None:
           while True:
               evt = self.bus.get_evt()
               if isinstance(evt, RouteEvt):
                   self.on_route(evt)
               elif isinstance(evt, ChapterEndEvt):
                   break
   ```

3. **`src/core/engine/executor.py:77-86` `Executor.__init__` 接受 `state` 参数**：
   ```python
   def __init__(self, story: Story, sink: EventSink, *, entry_id: str = "start", state: GameState | None = None):
       self.story = story
       self.sink = sink
       self.state = state if state is not None else GameState()  # 跨章节共享
       self._entry_id = entry_id
       self.next: tuple = None
       self._deco_state: dict = {}
       self._dispatcher = ExprDispatcher(self.state)
       self._validate_target_ids()
   ```

4. **`src/core/engine/main.py:67-137` 启动改造**：
   - 替换 `Executor(story, bus).run()` → `ChapterManager(CHAPTERS_ROOT, bus).run()`
   - 保留 `_load_story` 调用 + 错误处理路径（v0 阶段仍可用）
   - **重构而非重写**：保留现有错误处理（`FileNotFoundError` / `ParserError` / `ValueError` → `LogEvt(error)` + exit 1）

5. **测试**：
   - `tests/runtime/test_chapter_manager.py::test_on_route_loads_new_chapter` —— `RouteEvt("chapter02")` → `load_chapter_safe("chapter02.md")` 调用
   - `tests/runtime/test_chapter_manager.py::test_chapter_end_breaks_loop` —— `ChapterEndEvt` → `run()` 退出
   - `tests/runtime/test_chapter_manager.py::test_state_shared_across_chapters` —— chapter01 vars 在 chapter02 可读
   - `tests/runtime/test_chapter_manager.py::test_invalid_route_raises` —— `RouteEvt("nonexistent")` → `FileNotFoundError`
   - 现有 `tests/core/test_main_entry.py` 不破

6. **OQ-1 默认值**：相对路径（`CHAPTERS_ROOT` 拼接）—— `ChapterManager.on_route` 用 `self.chapters_dir / f"{evt.target}.md"`. PM 拍板后可能改绝对路径。

7. **OQ-3 默认值**：跨章节变量保留（`shared_state` 参数）—— PM 拍板后可能改为每章节重置。

## Acceptance criteria

- [ ] `src/runtime/load_chapter.py` 新建（从 `main.py:28-51` 抽取）
- [ ] `src/runtime/chapter_manager.py` 新建（`ChapterManager` 类 + `on_route` + `run`）
- [ ] `src/core/engine/executor.py:77-86` `Executor.__init__` 接受 `state` 参数
- [ ] `src/core/engine/main.py:67-137` 启动改造（用 `ChapterManager` 替代直接 `Executor.run`）
- [ ] `tests/runtime/test_chapter_manager.py` 新建，至少 4 个测试
- [ ] 现有 `tests/core/test_main_entry.py` 不破
- [ ] 现有 211+ tests 维持 + 4+ 新测试
- [ ] 跨章节变量保留（`state=shared_state`）
- [ ] 4 项路径校验复用（不重写 `_load_story`）
- [ ] v0/v1 解析器/执行器核心不动（仅扩 `Executor.__init__` 接受 state 参数）

## Blocked by

无（Window 1 · 3 人并行启动）

## 关联依赖

- 阻塞 V2-05（章节加载器端到端集成测试，依赖本 issue）
