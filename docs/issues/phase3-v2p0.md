# 阶段三 Issue 列表：v2 P0 三大功能（PyQt6 GUI / 章节加载器 / 存档）

> **关联 PDR**：[`docs/pdr/phase3-v2p0.md`](../pdr/phase3-v2p0.md)
> **审计依据**：[`docs/audit/phase3-method-audit.md`](../audit/phase3-method-audit.md)（11 EP · 接入契约）
> **基线**：`feature/v2-p0-gui-first` 分支基于 master，5 个 P0 修复已合并（211+ tests passed / 92% 覆盖率）
> **作者**：pdr-analyst
> **日期**：2026-06-26
> **状态**：**待 PM 分派**（5 条决策 D1-D5 已由用户拍板确认）
> **GitHub 镜像**：[`docs/issues/github/v2-NN-xxx.md`](./github/)（9 个模板 · #72-#80）

---

## 0. 概览

**9 个原子 issue**（在 7-10 范围内），按"v2 三大功能 + 骨架回归"组织：

| 类别 | 编号 | 标题 | 估时 | 依赖 | Window | 关联 EP |
|---|---|---|---|---|---|---|
| **PyQt6 GUI** | V2-01（#72） | PyQt6 入口切换 + QMainWindow 窗口框架 | M（2-3 天） | 无 | W1 | EP-03 + EP-05 + D3 |
| **PyQt6 GUI** | V2-02（#73） | 装饰器运行时钩子（@style 钩子 + DecoratorEvt.kind 扩展） | M（1-2 天） | V2-01 | W2 | EP-06 + EP-08 |
| **PyQt6 GUI** | V2-03（#74） | PyQt6 GUI 集成测试（mock bus + 信号槽覆盖） | S（0.5-1 天） | V2-01 + V2-02 | W3 | EP-03 |
| **章节加载器** | V2-04（#75） | ChapterManager + RouteEvt 消费 + load_chapter_safe 抽取 | M（2-3 天） | 无 | W1 | EP-10 + EP-11 |
| **章节加载器** | V2-05（#76） | 章节加载器端到端集成测试 | S（0.5-1 天） | V2-04 | W2 | EP-10 |
| **存档** | V2-06（#77） | GameState 序列化（to_dict/from_dict + current_block_id 字段） | S（1 天） | 无 | W1 | EP-09 + D2 |
| **存档** | V2-07（#78） | SaveManager + SaveCmd/LoadCmd（runtime/save.py + protocol.py 扩展） | M（2-3 天） | V2-06 | W2 | EP-07 + EP-11 + D2 + D4 |
| **骨架回归** | V2-08（#79） | EP-07 runtime 骨架（src/runtime/ 子模块清单 + CONTEXT 更新） | S（0.5-1 天） | V2-07 | W3 | EP-07 |
| **骨架回归** | V2-09（#80） | 文档同步 + 跨模块回归（ROADMAP/AGENTS/CONTEXT + 230+ tests） | S（0.5-1 天） | V2-01~V2-08 | W4 | — |

**总估时**：**11-15 天**（串行）/ **5-7 天**（按 3 人小团队 3+3+2+1 并行窗口）

**D1 决策顺序**：V2-01 → V2-04 → V2-06 三个 W1 无依赖 issue 全部并行启动

---

## 1. 依赖关系图

```
Window 1 (3 并行)        Window 2 (3 并行)        Window 3 (2 并行)    Window 4
─────────────────────     ─────────────────────     ───────────────────   ───────
V2-01 PyQt6 入口  ────→  V2-02 装饰器渲染   ────→  V2-03 PyQt6 测试
                          │                          │                ↘
V2-04 ChapterMgr ────→  V2-05 章节测试    ────→                       ↘
                          │                                            ↘
V2-06 GameState ─────→  V2-07 SaveManager ────→  V2-08 EP-07 骨架  ──→ V2-09
                                                                            文档+回归
```

**关键路径**（critical path）：
- V2-01 → V2-02 → V2-03：PyQt6 链路（最长 5-6 天）
- V2-06 → V2-07 → V2-08：存档链路（最长 4-5 天）
- V2-04 → V2-05：章节链路（最长 3-4 天）

**最优并行**（3 人小团队）：
- 工程师 A：V2-01 → V2-02 → V2-03（PyQt6 全程）
- 工程师 B：V2-04 → V2-05（章节加载器全程）
- 工程师 C：V2-06 → V2-07 → V2-08 → V2-09（存档 + 骨架 + 回归）

**总耗时**：5-7 天

---

## 2. PyQt6 GUI（issue 1-3）

### V2-01 · PyQt6 入口切换 + QMainWindow 窗口框架

| 项 | 内容 |
|---|---|
| **ID** | V2-01（GitHub #72） |
| **类型** | feature（GUI 入口 + 工厂分发） |
| **估时** | M（2-3 天） |
| **依赖** | 无 |
| **Window** | W1（3 人并行启动） |
| **风险** | MEDIUM（PyQt6 线程模型 + D5 不引入 asyncio） |
| **关联决策** | D3（PyQt6 fallback）、D5（不引入 asyncio） |
| **关联 EP** | EP-03（`EventSink` Protocol）+ EP-05（`_try_spawn_gui`） |
| **GitHub 模板** | [`docs/issues/github/v2-01-pyqt6-entry.md`](./github/v2-01-pyqt6-entry.md) |

**目标**：在 `src/runtime/gui/main.py` 顶部加 `importlib.util.find_spec("PyQt6")` 工厂分发；新建 `src/runtime/gui/pyqt6_main.py` 实现 QMainWindow + QTextEdit + QLineEdit + QThread 消费 bus。

**验收标准**（全部必须通过）：

1. **`runtime/gui/main.py:1-15` 切换**：
   ```python
   import importlib.util
   if importlib.util.find_spec("PyQt6") is not None:
       from runtime.gui.pyqt6_main import main as _pyqt_main
       return _pyqt_main(bus)
   return _cli_main(bus)  # v0 CLI 占位保留
   ```
2. **`src/runtime/gui/pyqt6_main.py` 新建**：
   - `QApplication` + `QMainWindow`（标题 "Neural Engine"）
   - `DisplayPanel(QTextEdit)` 文本显示（`append_text(content, style)` 方法）
   - `InputPanel(QLineEdit)` 用户输入（`returnPressed` 信号 → `bus.put_cmd(UserInputCmd(...))`）
   - `QThread` 启动 bus 消费循环：`while True: bus.get_evt()` → 通过 `QMetaObject.invokeMethod` 跨线程更新 UI
3. **`PyQt6Sink(QObject) implements EventSink`**：
   - `put_evt(evt) → signal emit`（线程安全）
   - `get_cmd() → 阻塞消费`（PyQt6 信号槽 + `bus._cmd_q.get()`）
4. **D3 降级测试**：`tests/runtime/test_gui_pyqt6.py::test_pyqt6_not_installed_falls_back_to_cli` mock `find_spec` 返回 None，验证走 CLI 占位路径
5. **PyQt6 装上时**：`from runtime.gui.window import MainWindow` 可 import；窗口类**不**在 CI 测
6. **CI 路径**：CI 跑 pytest 时 PyQt6 不在 PATH——降级路径走通
7. **211+ tests 维持 + 5+ 新测试**：`pytest tests/` 全绿，新增测试不破坏现有 92% 覆盖率

**复杂度判断依据**：
- PyQt6 三组件（QApplication / QMainWindow / QThread）框架搭建
- 跨线程信号槽（`Qt.QueuedConnection`）+ QObject 线程安全 API
- D5 不引入 asyncio → QThread 替代方案
- D3 降级路径 mock 测试

---

### V2-02 · 装饰器运行时钩子（@style 钩子 + DecoratorEvt.kind 扩展）

| 项 | 内容 |
|---|---|
| **ID** | V2-02（GitHub #73） |
| **类型** | feature（修饰器运行时钩子 + IPC 协议扩展） |
| **估时** | M（1-2 天） |
| **依赖** | V2-01 |
| **Window** | W2（依赖 V2-01） |
| **风险** | MEDIUM（EP-08 占位未实现 + G5 推迟） |
| **关联决策** | D5（不引入 asyncio） |
| **关联 EP** | EP-06（`DecoratorEvt.kind`）+ EP-08（`src/core/decorators/` 占位） |
| **GitHub 模板** | [`docs/issues/github/v2-02-decorator-hooks.md`](./github/v2-02-decorator-hooks.md) |

**目标**：扩展 `DecoratorEvt` 加 `kind: Literal["call", "stop"]` 字段（默认 `"call"`，向后兼容）；新建 `src/core/decorators/style.py` 注册 `@style` 钩子；executor 广播时按 `isinstance(DecoratorCall/Stop)` 区分 kind。

**验收标准**（全部必须通过）：

1. **`src/core/engine/protocol.py:151-169` `DecoratorEvt` 扩展**：
   ```python
   @dataclass(frozen=True, slots=True)
   class DecoratorEvt:
       name: str
       args: list[str]
       kind: str = "call"  # v2 新增；"call" | "stop"；默认 "call" 向后兼容
   ```
2. **`from_dict` 兼容旧 dict**：`d.get("kind", "call")` —— 旧 GUI 收到无 kind 字段的 dict 时走默认 call
3. **`src/core/engine/executor.py:240-251` `_emit_decorator` 区分**：
   ```python
   if isinstance(deco, DecoratorCall):
       self.sink.put_evt(DecoratorEvt(name=deco.name, args=list(deco.args), kind="call"))
   elif isinstance(deco, DecoratorStop):
       self.sink.put_evt(DecoratorEvt(name=deco.name, args=[deco.key], kind="stop"))
   ```
4. **`src/core/decorators/style.py` 新建**（EP-08 落地）：
   ```python
   _STYLE_HOOKS: dict[str, Callable] = {}

   def register_hook(name: str, fn: Callable) -> None:
       _STYLE_HOOKS[name] = fn

   def dispatch(evt: DecoratorEvt) -> None:
       fn = _STYLE_HOOKS.get(evt.name)
       if fn is None:
           return  # 未注册的钩子静默忽略（与 v0 一致）
       for arg in evt.args:
           if ":" in arg:
               k, v = arg.split(":", 1)
               fn(k, v)  # @style text:rgb:red → fn("text", "rgb:red")

   # 默认注册 @style 钩子（落地 PyQt6Sink.apply_style）
   register_hook("style", lambda k, v: PyQt6Sink.apply_style(k, v))
   ```
5. **测试**：
   - `tests/core/test_protocol_evt.py::test_decorator_evt_kind_default` 验证默认 `"call"`
   - `tests/core/test_decorator_hooks.py::test_register_and_dispatch` 验证钩子注册 + 派发
   - `tests/core/test_decorator_hooks.py::test_unregistered_hook_silent` 验证未注册钩子静默
   - 现有 `tests/runtime/test_gui_protocol.py::test_main_ignores_decorator_and_log` 不破
6. **G5 推迟**：结构化参数 `[item1,item2,...]`（ADR-0004 §4）v3+ 落地；v2 走"字符串 key/val 解析"路径

**复杂度判断依据**：
- 协议向后兼容（默认 `"call"`）需要测试覆盖旧 dict
- `_emit_decorator` 是 v0 已有代码，扩展而非重写
- EP-08 占位目录 `src/core/decorators/__init__.py` 已留 + ADR-0003 §2 决策 2

---

### V2-03 · PyQt6 GUI 集成测试（mock bus + 信号槽覆盖）

| 项 | 内容 |
|---|---|
| **ID** | V2-03（GitHub #74） |
| **类型** | test（mock bus + PyQt6Sink 覆盖） |
| **估时** | S（0.5-1 天） |
| **依赖** | V2-01 + V2-02 |
| **Window** | W3（最后串行） |
| **风险** | LOW（mock 测试，不实际启动 QApplication） |
| **关联 EP** | EP-03（`EventSink` Protocol） |
| **GitHub 模板** | [`docs/issues/github/v2-03-pyqt6-tests.md`](./github/v2-03-pyqt6-tests.md) |

**目标**：用 `MemoryEventSink` / `queue.Queue` mock 测试 `PyQt6Sink` 包装 EngineBus 收发正常；CI 跑测时 PyQt6 不在 PATH 走降级路径；实际 QMainWindow 不在 CI 测（人工手动验证）。

**验收标准**（全部必须通过）：

1. **`tests/runtime/test_gui_pyqt6.py` 新建**：
   - `test_pyqt6_sink_put_evt_emits_signal` —— `PyQt6Sink.put_evt(TextEvt("hello"))` → `text_received` signal 收到
   - `test_pyqt6_sink_get_cmd_blocks_on_queue` —— `PyQt6Sink.get_cmd()` 阻塞消费 `UserInputCmd`
   - `test_pyqt6_sink_close_drains_queue` —— `PyQt6Sink.close()` 排空残留（与 `EngineBus.close()` 对齐）
2. **D3 降级测试**：
   - `test_pyqt6_not_installed_falls_back_to_cli` —— mock `importlib.util.find_spec("PyQt6")` 返回 None，验证走 CLI 占位
3. **CI 路径**：
   - `pytest tests/runtime/test_gui_pyqt6.py` 全绿
   - **不**实际启动 QApplication（mock QApplication / QMainWindow）
   - 现有 `tests/runtime/test_gui_protocol.py` 不破
4. **人工手动验证清单**（写入 `docs/v2-gui-manual-verify.md`，**不**在 CI）：
   - [ ] 装 PyQt6 后 `python -m runtime.gui.main` 启动 QMainWindow 窗口
   - [ ] TextEvt 渲染到 DisplayPanel
   - [ ] QLineEdit 回车推 UserInputCmd
   - [ ] 装饰器 `@style text:rgb:red` 在窗口中可见
5. **测试覆盖**：`PyQt6Sink` 类 100% 行覆盖（不实际渲染）

**复杂度判断依据**：
- mock 测试比实际 GUI 测试简单
- 主要工作量在 PyQt6 API 的 mock 策略（`unittest.mock.patch`）

---

## 3. 章节加载器（issue 4-5）

### V2-04 · ChapterManager + RouteEvt 消费 + load_chapter_safe 抽取

| 项 | 内容 |
|---|---|
| **ID** | V2-04（GitHub #75） |
| **类型** | feature（章节路由 + 跨章节跳转） |
| **估时** | M（2-3 天） |
| **依赖** | 无（与 V2-01 共享 bus 设计，但不强依赖） |
| **Window** | W1（3 人并行启动） |
| **风险** | MEDIUM（跨章节状态保留 + main 启动改造） |
| **关联决策** | D1（顺序：章节在 GUI 之后做） |
| **关联 EP** | EP-10（`RouteEvt` 处理）+ EP-11（`LoadChapterCmd` 消费） |
| **GitHub 模板** | [`docs/issues/github/v2-04-chapter-manager.md`](./github/v2-04-chapter-manager.md) |

**目标**：新建 `src/runtime/chapter_manager.py` 订阅 `RouteEvt` → 加载新章节 → 新建 Executor.run()；抽取 `src/runtime/load_chapter.py` 复用 `_load_story` 4 项路径校验；`main.py` 启动时改用 `ChapterManager.run()`。

**验收标准**（全部必须通过）：

1. **`src/runtime/load_chapter.py` 新建**（从 `main.py:28-51` 抽取）：
   ```python
   def load_chapter_safe(chapter_path: Path) -> Story:
       """复用 main._load_story 4 项校验：symlink/CHAPTERS_ROOT/.md/1MB"""
       # 完整实现提取 main.py:28-51 + 阶段二 P0-S1 路径校验
   ```
2. **`src/runtime/chapter_manager.py` 新建**：
   ```python
   class ChapterManager:
       def __init__(self, chapters_dir: Path, bus: EngineBus):
           self.chapters_dir = chapters_dir
           self.bus = bus

       def on_route(self, evt: RouteEvt) -> None:
           chapter_path = self.chapters_dir / f"{evt.target}.md"
           story = load_chapter_safe(chapter_path)
           executor = Executor(story, sink=self.bus)
           executor.run()  # 同步阻塞（v2 简化）

       def run(self) -> None:
           while True:
               evt = self.bus.get_evt()
               if isinstance(evt, RouteEvt):
                   self.on_route(evt)
               elif isinstance(evt, ChapterEndEvt):
                   break
   ```
3. **`src/core/engine/main.py:67-137` 启动改造**：
   - 替换 `Executor(story, bus).run()` → `ChapterManager(CHAPTERS_ROOT, bus).run()`
   - 保留 `_load_story` 调用 + 错误处理路径
4. **跨章节状态保留**：新建 Executor 时**复用同一 `state` 对象**（`Executor(story, sink, state=self.state)`）—— 需 `Executor.__init__` 接受 `state` 参数
5. **测试**：
   - `tests/runtime/test_chapter_manager.py::test_on_route_loads_new_chapter` —— `RouteEvt("chapter02")` → `load_chapter_safe("chapter02.md")` 调用
   - `tests/runtime/test_chapter_manager.py::test_chapter_end_breaks_loop` —— `ChapterEndEvt` → `run()` 退出
   - `tests/runtime/test_chapter_manager.py::test_state_shared_across_chapters` —— chapter01 vars 在 chapter02 可读
6. **OQ-1 默认值**：相对路径（`CHAPTERS_ROOT` 拼接）—— PM 拍板后可能改
7. **现有测试不破**：`tests/core/test_main_entry.py` 跑现有 `main()` 流程不破

**复杂度判断依据**：
- `ChapterManager` 类设计 + `RouteEvt` 消费循环
- 跨章节 `state` 共享（需要 `Executor` 接受 state 参数）
- `_load_story` 抽取（重构而非重写）

---

### V2-05 · 章节加载器端到端集成测试

| 项 | 内容 |
|---|---|
| **ID** | V2-05（GitHub #76） |
| **类型** | test（端到端跨章节） |
| **估时** | S（0.5-1 天） |
| **依赖** | V2-04 |
| **Window** | W2（依赖 V2-04） |
| **风险** | MEDIUM（fixture 复杂） |
| **关联 EP** | EP-10（`RouteEvt` 处理） |
| **GitHub 模板** | [`docs/issues/github/v2-05-chapter-tests.md`](./github/v2-05-chapter-tests.md) |

**目标**：`tests/integration/test_chapter_routing.py` 端到端 fixture 跨章节跳转；最小 `chapter01.md` 触发 `id:end1:chapter02` → 自动加载 `chapter02.md` → 变量 `pick` 跨章节保留。

**验收标准**（全部必须通过）：

1. **`tests/integration/test_chapter_routing.py` 新建**：
   - `test_chapter01_to_chapter02_via_route` —— 最小 chapter01.md + chapter02.md fixture，跨章节跳转
   - `test_state_vars_persist_across_chapters` —— chapter01 设置 var `pick=1`，chapter02 读取 var
   - `test_chapter_end_terminates_run` —— 收到 `ChapterEndEvt` 退出
   - `test_invalid_route_raises` —— `RouteEvt("nonexistent")` → `FileNotFoundError`
2. **Fixture 最小化**：
   - `tests/integration/fixtures/chapter01_minimal.md` —— `id:start` + `node end` + `id:end1:chapter02`
   - `tests/integration/fixtures/chapter02_minimal.md` —— `id:start` + `node in → P-text` + `node end` + `id:end1`
3. **CI 路径**：`pytest tests/integration/test_chapter_routing.py` 全绿
4. **现有 fixture 不破**：`tests/integration/test_chapter_end.py`（v0 已有）继续工作
5. **覆盖度**：跨章节跳转路径 100% 行覆盖

**复杂度判断依据**：
- 最小 fixture 设计（10-20 行 .md）
- `MemoryEventSink` + `MemoryInputSink` 组合 mock

---

## 4. 存档（issue 6-7）

### V2-06 · GameState 序列化（to_dict/from_dict + current_block_id 字段）

| 项 | 内容 |
|---|---|
| **ID** | V2-06（GitHub #77） |
| **类型** | feature（存档核心 - 数据序列化） |
| **估时** | S（1 天） |
| **依赖** | 无 |
| **Window** | W1（3 人并行启动） |
| **风险** | MEDIUM（`vars: dict[str, Any]` 类型宽泛 + 跨块 `current_block_id` 更新） |
| **关联决策** | D2（JSON 复用 protocol.py） |
| **关联 EP** | EP-09（`GameState` 序列化） |
| **GitHub 模板** | [`docs/issues/github/v2-06-gamestate-serialize.md`](./github/v2-06-gamestate-serialize.md) |

**目标**：在 `src/core/engine/executor.py:63-68` 扩展 `GameState` 加 `current_block_id` 字段 + `to_dict/from_dict` 方法；`Executor.run` 入口 / `_next_block` 后置更新 `current_block_id`。

**验收标准**（全部必须通过）：

1. **`src/core/engine/executor.py:63-68` `GameState` 扩展**：
   ```python
   @dataclass
   class GameState:
       vars: dict = field(default_factory=dict)
       path: list = field(default_factory=list)
       next_table: dict = field(default_factory=dict)
       current_block_id: str | None = None  # v2 新增

       def to_dict(self) -> dict:
           return {
               "version": 1,  # 存档版本字段
               "vars": dict(self.vars),
               "path": list(self.path),
               "current_block_id": self.current_block_id,
           }

       @classmethod
       def from_dict(cls, d: dict) -> "GameState":
           return cls(
               vars=dict(d.get("vars", {})),
               path=list(d.get("path", [])),
               current_block_id=d.get("current_block_id"),
           )
   ```
2. **`Executor.run` / `_next_block` 更新 `current_block_id`**：
   - `run()` 入口：`self.state.current_block_id = entry_block.id`
   - `_next_block` 后置：`self.state.current_block_id = next_block.id`
3. **D2 决策落地**：序列化/反序列化用 `json.dumps + utf-8`（与 `protocol.py` 一致），存档格式与 IPC 消息同一序列化模式
4. **存档版本字段**：`to_dict` 写 `"version": 1`，`from_dict` 检查版本（v2 仅读 v1；v3+ 升级时写迁移函数）
5. **OQ-5 默认值**：仅允许 `vars` 含 `str / int / list / dict`（其他类型需先 `to_dict()` 再存档）—— PM 拍板后可能改
6. **测试**：
   - `tests/core/test_executor_skeleton.py::test_gamestate_to_dict_round_trip` —— 序列化后反序列化恢复
   - `tests/core/test_executor_skeleton.py::test_gamestate_version_field` —— `to_dict()` 含 `"version": 1`
   - `tests/core/test_executor_skeleton.py::test_current_block_id_updated` —— `_next_block` 后 `state.current_block_id` 正确
7. **现有测试不破**：`tests/core/test_executor_*.py` 全套不破
8. **OQ-3 默认值**：跨章节变量保留（`GameState.vars` 跨块已隐式全局）—— PM 拍板后可能改

**复杂度判断依据**：
- `GameState` 字段扩展（小改动）
- `current_block_id` 更新逻辑（需要在 run / `_next_block` 加 2 行）
- round-trip 序列化测试（标准模式）

---

### V2-07 · SaveManager + SaveCmd/LoadCmd

| 项 | 内容 |
|---|---|
| **ID** | V2-07（GitHub #78） |
| **类型** | feature（存档 IPC + 文件管理） |
| **估时** | M（2-3 天） |
| **依赖** | V2-06 |
| **Window** | W2（依赖 V2-06） |
| **风险** | MEDIUM（main 加 cmd 循环 + 存档位置 D4 决策） |
| **关联决策** | D2（JSON 复用）+ D4（`~/.neural-engine/saves/{slot}.json`） |
| **关联 EP** | EP-07（`src/runtime/` 占位）+ EP-11（IPC 协议扩展） |
| **GitHub 模板** | [`docs/issues/github/v2-07-save-manager.md`](./github/v2-07-save-manager.md) |

**目标**：在 `src/core/engine/protocol.py` 新增 `SaveCmd/LoadCmd` 数据类 + 注册到 `_CMD_REGISTRY`；新建 `src/runtime/save.py`（SaveManager，JSON 文件 + 槽位管理）；`main.py` 加 cmd 循环（v0 简化下 main 不读 cmd_q——v2 改造）。

**验收标准**（全部必须通过）：

1. **`src/core/engine/protocol.py:93-97` 新增**（EP-11）：
   ```python
   @dataclass(frozen=True, slots=True)
   class SaveCmd:
       slot: str
       def to_dict(self) -> dict: return {"cmd": "save", "slot": self.slot}
       @classmethod
       def from_dict(cls, d: dict) -> "SaveCmd":
           _check_dict(d, "SaveCmd")
           return cls(slot=_require_str(d, "slot", "SaveCmd"))

   @dataclass(frozen=True, slots=True)
   class LoadCmd:
       slot: str
       def to_dict(self) -> dict: return {"cmd": "load", "slot": self.slot}
       @classmethod
       def from_dict(cls, d: dict) -> "LoadCmd":
           _check_dict(d, "LoadCmd")
           return cls(slot=_require_str(d, "slot", "LoadCmd"))

   _CMD_REGISTRY["save"] = SaveCmd
   _CMD_REGISTRY["load"] = LoadCmd
   ```
2. **`src/runtime/save.py` 新建**（EP-07 + D4 决策）：
   ```python
   class SaveManager:
       def __init__(self, save_dir: Path = Path.home() / ".neural-engine" / "saves"):
           self.save_dir = save_dir
           self.save_dir.mkdir(parents=True, exist_ok=True)

       def save(self, slot: str, state: GameState) -> None:
           # D2 决策：复用 protocol.py json.dumps + utf-8
           path = self.save_dir / f"{slot}.json"
           path.write_text(
               json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
               encoding="utf-8",
           )

       def load(self, slot: str) -> GameState:
           path = self.save_dir / f"{slot}.json"
           data = json.loads(path.read_text(encoding="utf-8"))
           return GameState.from_dict(data)

       def list_slots(self) -> list[str]:
           return sorted([p.stem for p in self.save_dir.glob("*.json")])
   ```
3. **`src/core/engine/main.py:67-137` cmd 循环**：
   - 新建 `QThread` 读 `cmd_q`（与 V2-01 PyQt6 集成；CLI 占位走 polling）
   - 收到 `SaveCmd` → `SaveManager.save(cmd.slot, executor.state)`
   - 收到 `LoadCmd` → `executor.state = SaveManager.load(cmd.slot)`
   - 收到 `ShutdownCmd` → 优雅退出
4. **路径校验**：`save()` / `load()` 加 slot 名字校验（仅允许 `[\w-]+`，防止路径穿越）
5. **OQ-2 默认值**：slot 短名 + 序号（`"01"` / `"02"`）—— PM 拍板后可能改
6. **测试**：
   - `tests/runtime/test_save_manager.py::test_save_creates_json_file` —— `save("01", state)` 写入 `~/.neural-engine/saves/01.json`
   - `tests/runtime/test_save_manager.py::test_load_reads_json_file` —— `load("01")` 恢复 `GameState`
   - `tests/runtime/test_save_manager.py::test_round_trip_preserves_state` —— `state → save → load → state` 一致
   - `tests/runtime/test_save_manager.py::test_list_slots` —— `list_slots()` 返回所有槽
   - `tests/core/test_protocol_cmd.py::test_save_cmd_from_dict` —— `SaveCmd.from_dict({"cmd": "save", "slot": "01"})` 正确
   - `tests/integration/test_save_load_e2e.py` —— 游戏中途存档 → 重启 → 读档 → 恢复状态
7. **测试用临时目录**：`tmp_path` fixture 注入 `save_dir`（避免污染 `~/.neural-engine/saves/`）
8. **现有测试不破**：`tests/core/test_protocol_cmd.py` 跑现有 3 cmd 不破

**复杂度判断依据**：
- 协议扩展（小改动，复用 `_CMD_REGISTRY` 工厂模式）
- `SaveManager` 类设计（JSON + 路径校验 + 槽位管理）
- main 加 cmd 循环（v0 简化下 main 不读 cmd_q——v2 改造）
- 端到端 fixture

---

## 5. 骨架与回归（issue 8-9）

### V2-08 · EP-07 runtime 骨架（src/runtime/ 子模块清单 + CONTEXT 更新）

| 项 | 内容 |
|---|---|
| **ID** | V2-08（GitHub #79） |
| **类型** | chore（runtime 骨架 + 文档同步） |
| **估时** | S（0.5-1 天） |
| **依赖** | V2-07（`src/runtime/save.py` 已建） |
| **Window** | W3（依赖 V2-07） |
| **风险** | LOW（占位已留 + 文档更新） |
| **关联 EP** | EP-07（`src/runtime/` 占位） |
| **GitHub 模板** | [`docs/issues/github/v2-08-runtime-skeleton.md`](./github/v2-08-runtime-skeleton.md) |

**目标**：补齐 `src/runtime/` 三个子模块的占位（`gui/` 已有；`save.py` V2-07 已建；新建 `audio.py` / `video.py` / `renderer.py` 占位 + CONTEXT.md 更新）；与 `src/runtime/CONTEXT.md` 术语表对齐。

**验收标准**（全部必须通过）：

1. **`src/runtime/` 目录结构**：
   ```
   src/runtime/
   ├── __init__.py          (空文件已留)
   ├── CONTEXT.md           (术语表已留)
   ├── gui/                 (V2-01 已建)
   │   ├── __init__.py
   │   └── main.py
   │   └── pyqt6_main.py    (V2-01 新建)
   ├── save.py              (V2-07 新建)
   ├── audio.py             (v2 本 issue 新建 · 占位)
   ├── video.py             (v2 本 issue 新建 · 占位)
   └── renderer.py          (v2 本 issue 新建 · 占位)
   ```
2. **`src/runtime/audio.py` 占位**（v3+ 落地）：
   ```python
   """音频管理器（BGM/SE/Voice）—— v3+ 落地。v2 仅占位。"""
   from __future__ import annotations

   class AudioManager:
       """订阅 DecoratorEvt 触发 BGM/SE 播放。"""
       def play(self, bgm: str) -> None:
           raise NotImplementedError("v3+ 落地")
       def stop(self) -> None:
           raise NotImplementedError("v3+ 落地")
   ```
3. **`src/runtime/video.py` 占位**（v3+ 落地）：
   ```python
   """视频播放器 —— v3+ 落地。v2 仅占位。"""
   class VideoPlayer:
       def play(self, video: str) -> None:
           raise NotImplementedError("v3+ 落地")
   ```
4. **`src/runtime/renderer.py` 占位**（v3+ 落地）：
   ```python
   """文字/立绘/背景渲染器 —— v3+ 落地。v2 仅占位。"""
   class TextRenderer:
       def set_style(self, key: str, val: str) -> None:
           raise NotImplementedError("v3+ 落地")
   ```
5. **`src/runtime/CONTEXT.md` 验证**：与 `src/runtime/__init__.py` 子模块清单对齐（5 个子模块：gui / save / audio / video / renderer）
6. **测试**：
   - `tests/runtime/test_runtime_skeleton.py::test_runtime_modules_importable` —— `from runtime.audio import AudioManager` 等可 import
   - `tests/runtime/test_runtime_skeleton.py::test_v3_methods_raise_not_implemented` —— `AudioManager.play()` 抛 `NotImplementedError`
7. **现有测试不破**：`tests/runtime/test_gui_protocol.py` / `test_save_manager.py` 不破

**复杂度判断依据**：
- 三个占位类（各 5-10 行）
- CONTEXT.md 验证（小检查）

---

### V2-09 · 文档同步 + 跨模块回归

| 项 | 内容 |
|---|---|
| **ID** | V2-09（GitHub #80） |
| **类型** | docs + verify（文档同步 + 跨模块回归） |
| **估时** | S（0.5-1 天） |
| **依赖** | V2-01 ~ V2-08 全部完成 |
| **Window** | W4（最后串行） |
| **风险** | LOW（文档 + 测试校验） |
| **关联 EP** | — |
| **GitHub 模板** | [`docs/issues/github/v2-09-docs-regression.md`](./github/v2-09-docs-regression.md) |

**目标**：更新 `ROADMAP.md` §3 P0 标记 v2 三大功能已完成；`AGENTS.md` / `docs/agents/domain.md` / `src/runtime/CONTEXT.md` 同步新模块；跨模块回归（`pytest tests/` 全绿 + 230+ tests / 92%+ 覆盖率）；`docs/audit/phase3-v2p0-summary.md` 写 v2 P0 完工总结。

**验收标准**（全部必须通过）：

1. **`docs/ROADMAP.md` 更新**：
   - §3.1 PyQt6 GUI 标记 ✅（v2 P0 完成）
   - §3.2 章节加载器标记 ✅
   - §3.3 存档/读档标记 ✅
   - §2.1 v0 遗留的"PyQt6 GUI 窗口"/"章节图 DAG"/"存档/读档"标记 ✅ 已解决
2. **`AGENTS.md` 更新**（如存在）：
   - 新增 `src/runtime/audio.py` / `video.py` / `renderer.py` 占位说明
   - 新增 `src/core/decorators/style.py` 钩子说明
3. **`docs/agents/domain.md` 更新**：
   - 验证 `CONTEXT-MAP.md` 指向各 CONTEXT.md 仍准确
   - runtime CONTEXT 增补 save/audio/video/renderer 关键类型
4. **`src/runtime/CONTEXT.md` 验证**：
   - `SaveManager` 已实现（V2-07）—— 关键类型表移除"v3+ 落地"标记
   - `TextRenderer` / `AudioManager` / `VideoPlayer` / `PlatformBridge` 仍标"v3+ 落地"
5. **`docs/audit/phase3-v2p0-summary.md` 新建**（完工总结）：
   - 9 个 issue 完成状态
   - 测试从 211 → 230+（V2-01~V2-08 新增测试）
   - 覆盖率从 92% → 92%+（维持）
   - 6 个新模块（`src/runtime/{save,audio,video,renderer}.py` + `src/core/decorators/style.py` + `src/runtime/gui/pyqt6_main.py`）
   - EP-03 / EP-05 / EP-06 / EP-07 / EP-08 / EP-09 / EP-10 / EP-11 共 8 个 EP 落地
6. **跨模块回归**：
   - `pytest tests/` 全绿（230+ tests / 92%+ 覆盖率）
   - `ruff check src/` 0 errors（新增模块 ruff 合规）
   - 5 个 v0/v1 commit（b5edf5b / e631dae / 6979d8c / 766e407 / f1f39f4）未受影响
7. **分支合并**：`feature/v2-p0-gui-first` → `master`（MR / PR）

**复杂度判断依据**：
- 文档更新（标准模式）
- 跨模块回归（自动化校验）

---

## 附录 A：估时与依赖矩阵

| Issue | 估时 | 依赖 | Window | 风险 | 类别 |
|---|---|---|---|---|---|
| V2-01 | M（2-3 天） | 无 | W1 | MEDIUM | PyQt6 |
| V2-02 | M（1-2 天） | V2-01 | W2 | MEDIUM | PyQt6 |
| V2-03 | S（0.5-1 天） | V2-01 + V2-02 | W3 | LOW | PyQt6 |
| V2-04 | M（2-3 天） | 无 | W1 | MEDIUM | 章节 |
| V2-05 | S（0.5-1 天） | V2-04 | W2 | MEDIUM | 章节 |
| V2-06 | S（1 天） | 无 | W1 | MEDIUM | 存档 |
| V2-07 | M（2-3 天） | V2-06 | W2 | MEDIUM | 存档 |
| V2-08 | S（0.5-1 天） | V2-07 | W3 | LOW | 骨架 |
| V2-09 | S（0.5-1 天） | V2-01~V2-08 | W4 | LOW | 回归 |
| **合计** | **11-15 天** | — | — | — | — |

> **优化并行后**：3 个 W1 全并行 + 3 个 W2 全并行 + 2 个 W3 全并行 + 1 个 W4，3 人小团队 **5-7 天**完工。

---

## 附录 B：分配建议（3 人小团队）

| 工程师 | Issue 链 | 耗时 | 累计 |
|---|---|---|---|
| **A（PyQt6 专长）** | V2-01 → V2-02 → V2-03 | 2-3 + 1-2 + 0.5-1 = 3.5-6 天 | 3.5-6 天 |
| **B（章节加载器）** | V2-04 → V2-05 | 2-3 + 0.5-1 = 2.5-4 天 | 2.5-4 天 |
| **C（存档 + 骨架 + 回归）** | V2-06 → V2-07 → V2-08 → V2-09 | 1 + 2-3 + 0.5-1 + 0.5-1 = 4-6 天 | 4-6 天 |

> **总耗时**：3 路并行最长 = **4-6 天**（C 路径最长），但 V2-09 在所有 issue 完成后才启动，所以实际 = **5-7 天**（含 V2-09 的 0.5-1 天）。

---

## 附录 C：决策交叉引用（D1-D5）

| 决策 | 关联 issue | 关联 § |
|---|---|---|
| D1 顺序（PyQt6 → 章节 → 存档） | V2-01（先做）→ V2-04（次做）→ V2-06（后做） | §1 依赖图 + §附录 B |
| D2 JSON 复用 | V2-06（GameState 序列化）+ V2-07（SaveManager） | §4 存档 issue |
| D3 PyQt6 fallback | V2-01（GUI 入口切换） | §2 PyQt6 issue |
| D4 存档位置 | V2-07（SaveManager 默认目录） | §4 存档 issue |
| D5 不引入 asyncio | V2-01（QThread 替代）+ V2-02（同步钩子） | §2 PyQt6 issue |

---

## 附录 D：EP 接入位对照

| EP | 难度 | 接入位 | 改造 issue |
|---|---|---|---|
| EP-03 `EventSink` Protocol | S | `executor.py:28-32` | V2-01 |
| EP-05 `_try_spawn_gui` | S | `main.py:54-64` | V2-01 |
| EP-06 `DecoratorEvt.kind` | M | `protocol.py:151-169` | V2-02 |
| EP-07 `src/runtime/` 占位 | S | `src/runtime/__init__.py` | V2-07 + V2-08 |
| EP-08 `src/core/decorators/` 占位 | S | `src/core/decorators/__init__.py` | V2-02 |
| EP-09 `GameState` 序列化 | M | `executor.py:63-68` | V2-06 |
| EP-10 `RouteEvt` 处理 | S | `executor.py:350-351` + `protocol.py:172-182` | V2-04 |
| EP-11 IPC 协议扩展 | S | `protocol.py:93-97` | V2-07 |

> **未在本 PDR 落地的 EP**（推后到 v3+）：EP-01 / EP-02 / EP-04

---

## 附录 E：不做的（明确排除）

- **不修 v1 偏差** —— 已修（5 commit 已合并 master）
- **不修阶段二 P0** —— 已修（5 commit 已合并 master）
- **不动 v0/v1 解析器/执行器/表达式核心** —— v2 三大功能仅"加新文件 + 扩 EP 接入位"
- **不引入 asyncio** —— D5 决策，用 Qt 事件循环 + QThread
- **不写 v3+ 功能** —— `@LLM-jud` / 表达式系统增强 / 剧情编辑器 / 章节图可视化均推后
- **不写新 ADR** —— 5 决策 D1-D5 已拍板；8 条 OQ 推 PM 拍板（详见 PDR §10）
- **不修 v2 审计剩余 P1/P2 项** —— 阶段二已修 5 P0；其余 P1/P2 推后到 v3+
- **不创建 fix 分支** —— 在 `feature/v2-p0-gui-first` 分支上工作（已基于 master）

---

## 附录 F：交付物路径

- **PDR**：`docs/pdr/phase3-v2p0.md`
- **Issue 列表**：`docs/issues/phase3-v2p0.md`（本文件）
- **GitHub 模板目录**：`docs/issues/github/`
- **GitHub 模板文件**：9 个（`v2-01-pyqt6-entry.md` ~ `v2-09-docs-regression.md`）
- **GitHub issue 编号**：#72-#80

---

*哈尼斯 · pdr-analyst · 2026-06-26 · 阶段三·v2 P0 三大功能 issue 列表待 PM 分派*
