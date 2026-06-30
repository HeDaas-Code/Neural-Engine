# PDR：阶段三·v2 P0 三大功能（PyQt6 GUI / 章节加载器 / 存档）

> **项目**：Neural Engine（中文文字游戏引擎）
> **阶段**：阶段三·v2 P0（v0 + v1 + 阶段二 P0 修复已完工；v2 三大功能启动）
> **作者**：pdr-analyst
> **日期**：2026-06-26
> **状态**：**待 PM 分派**（5 条决策已由用户拍板确认，9 条 issue 待 tdd-coder 接手）
> **基线**：`feature/v2-p0-gui-first` 分支基于 master，5 个 P0 修复（commit b5edf5b / e631dae / 6979d8c / 766e407 / f1f39f4）已合并，211+ tests passed
> **前置文档**：
> - [`docs/audit/phase3-method-audit.md`](../audit/phase3-method-audit.md)（code-auditor · 2026-06-25·方法级审计·11 个 EP）
> - [`docs/pdr/phase3-method-audit.md`](../pdr/phase3-method-audit.md)（pdr-analyst · 2026-06-25·方法级审计 PDR）
> - [`docs/ROADMAP.md`](../ROADMAP.md) v2 P0 三大功能规划
> - [`docs/adr/0001-v0-baseline-script-spec.md`](../adr/0001-v0-baseline-script-spec.md) + `0002-v0-engine-implementation.md` + `0003-v1-expression-subsystem.md` + `0004-v1-refactor-design.md`
> **审计依据**：[`docs/audit/phase3-method-audit.md` §4](../audit/phase3-method-audit.md#4-预留扩展点-extension-points)（11 EP · 接入契约）+ §7（v2 三大功能接入设计建议）

---

## 1. 背景与动机

### 1.1 阶段一/二/三前奏已经做了什么

| 阶段 | 任务 | 性质 | 关键产物 |
|---|---|---|---|
| **v0** | 基础引擎 | 实现 | 解析 + 执行 + 9 节点 dispatch + 双向 EngineBus + 路径校验 |
| **v1** | 表达式重构 + D1/D2/D4/D5 偏差修复 | 重构 | ExprDispatcher + CustomExecutor + 5 节点表达式 |
| **阶段一** | 偏差扫描 + D1/D2/D4/D5 修复落地 | 修 bug | 4 commit + 208 tests / 90% 覆盖率 |
| **阶段二** | v2 独立审计 4 P0 / 15 P1 / 9 P2 + 修复 5 个 P0 + P0-E2 | 修 bug | 5 commit + 287 tests / 92% 覆盖率 |
| **阶段三前奏** | 方法级审计（11 EP + 72 public API + 4 维度状态/进程边界） | 文档 | 1 篇 audit + 1 篇 PDR + 7 个 issue |

**当前架构状态**（v0 + v1 + 阶段二 P0 修复完工）：
- 13 个核心模块 + 5 个 expr 子包 + 1 个 GUI 占位 → 严格 DAG，**0 循环依赖**
- 72 个 public API 中 64 个 100% 覆盖（`MemoryEventSink` / `MemoryInputSink` 范式已稳定）
- 11 个预留扩展点（EP-01~EP-11）按 S/M/L 难度分级
- 进程边界（`multiprocessing.Queue ↔ JSON dict`）已稳定在 `protocol.py` 的 11 个 dataclass
- `Runtime` + `core/decorators/` 占位空文件已留术语表（`CONTEXT.md`）+ ADR 决策 2

### 1.2 阶段三 v2 P0 要做什么

阶段三的核心是 **v2 三大功能**（PyQt6 GUI / 章节加载器 / 存档读档，详见 `ROADMAP.md` §3 P0）。在动手写功能代码之前，需要先把 PDR 拍板、issue 拆解到位。

**核心动机**：
- **PyQt6 GUI**：当前只有 CLI print 路径 B，无法验证视觉体验（音乐/样式/动效）；PyQt6 三组件（QMainWindow + QTextEdit + QLineEdit）能让玩家真正"玩起来"
- **章节加载器**：`RouteEvt` 广播后**无人消费**（v0 收到后只打印退出），跨章节跳转实际不工作；上章节→下章节的故事流是文字游戏的最基本闭环
- **存档/读档**：玩家进度无法保存——游戏玩到一半退出就白玩；这是"产品化"前必须有的功能

**D1-D5 决策已拍板**（详见 §4）—— 不再走 PM 反复征询，tdd-coder 直接按本 PDR 落地。

### 1.3 与阶段一/二/三前奏的差异化定位

| 维度 | 阶段一/二（代码级 bug 修复） | 阶段三前奏（方法级 audit） | 阶段三 v2 P0（本 PDR） |
|---|---|---|---|
| **目标** | 修具体 bug | 看清系统全貌 | 落 v2 三大功能（核心体验闭环） |
| **产出** | commit + 偏差表 | 信息流图 + 依赖图 + 11 EP + 72 API | PDR + 9 个原子 issue + GitHub 模板 |
| **方法** | grep 行号 + 静态对照 | 跨模块追踪 + Mermaid 图示 | 用户拍板 5 决策 + 按 EP 接入契约实施 |
| **使用者** | tdd-coder（按 commit 修） | PM（排期）+ owner（拍板） | tdd-coder（按 issue 接）+ PM（按 issue 派工） |
| **完成标志** | ruff 错误 -1 / 测试 +79 | 6 类产出物全部落 `docs/audit/phase3-method-audit/` | PDR 拍板 + 9 issue 派工 + src/ 改造落 master |

---

## 2. 目标

| 优先级 | 子目标 | 度量 | 关联 EP |
|---|---|---|---|
| **P0** | PyQt6 GUI 接入——`runtime/gui/main.py` 顶部 `importlib.util.find_spec("PyQt6")` 切换 CLI/QMainWindow | issue V2-01 完成；211+ → 230+ tests | EP-03 + EP-05 + EP-06 |
| **P0** | PyQt6 装饰器运行时钩子——`@style` 钩子 + DecoratorEvt.kind 扩展 | issue V2-02 完成；可播 BGM / 切样式 | EP-06 + EP-08 |
| **P0** | PyQt6 GUI 测试——mock bus + 信号槽覆盖 | issue V2-03 完成；QMainWindow 不在 CI 测 | EP-03 |
| **P0** | ChapterManager 路由消费——`RouteEvt` → `_load_story(target)` → 新 Executor.run() | issue V2-04 完成；chapter01→chapter02 端到端通 | EP-10 + EP-11 |
| **P0** | 章节加载器集成测试——端到端 fixture 跨章节 | issue V2-05 完成 | EP-10 |
| **P0** | GameState 序列化——`to_dict/from_dict` + `current_block_id` 字段 | issue V2-06 完成；可 round-trip 序列化 | EP-09 |
| **P0** | SaveManager + SaveCmd/LoadCmd——JSON 存档 + 跨进程命令 | issue V2-07 完成；存档/读档端到端通 | EP-07 + EP-09 + EP-11 |
| **P1** | EP-07 runtime 骨架——`src/runtime/` 三个新子模块 + CONTEXT 更新 | issue V2-08 完成 | EP-07 |
| **P1** | 文档同步 + 跨模块回归——ROADMAP/AGENTS/CONTEXT 更新 + 全 230+ tests / 92%+ 覆盖率 | issue V2-09 完成 | — |

**不做的事**（明确排除）：
- 不修 v1 偏差（已修，5 commit 已合并 master）
- 不修阶段二 P0（已修，5 commit 已合并 master）
- 不动 v0/v1 解析器/执行器/表达式核心（架构稳定）
- 不引入新架构决策（5 决策 D1-D5 已拍板，归 ADR-0005+ 单独拍板的项已转 §10 Open Questions）
- 不写 v3+ 功能（LLM 集成 `@LLM-jud`、编辑器、章节图可视化均推后）

---

## 3. 范围

### 3.1 包含（In Scope）—— v2 三大功能

| 功能 | 范围（做什么） | 不做（明确推后） |
|---|---|---|
| **PyQt6 GUI** | 1) `runtime/gui/main.py` 顶部 `importlib.util.find_spec("PyQt6")` 切换；2) 新建 `pyqt6_main.py`（QMainWindow + QTextEdit + QLineEdit）；3) 装饰器运行时钩子（`core/decorators/style.py` 注册 `@style`）；4) DecoratorEvt 扩 `kind` 字段（默认 `"call"`，向后兼容）；5) PyQt6Sink(QObject) 包装 EngineBus | 不做 BGM/SE/voice 音频播放（v3+ 走 `AudioManager`）；不做立绘/视频（v3+）；不做多窗口/多存档槽 UI（v3+） |
| **章节加载器** | 1) 新建 `src/runtime/chapter_manager.py` 订阅 `RouteEvt`；2) 抽取 `load_chapter_safe` 函数（复用 `_load_story` 路径校验）；3) `main.py` 启动时改用 `ChapterManager.run()` 取代 `Executor.run()`；4) 跨章节变量保留（`GameState.vars` 复用同一对象） | 不做章节图元数据 `index.yaml`（v3+ 章节图可视化）；不做跨章节 Save 钩子（v3+）；不做 GUI 主动 `LoadChapterCmd` 消费（v3+） |
| **存档/读档** | 1) `GameState` 扩 `to_dict/from_dict` + `current_block_id` 字段；2) `protocol.py` 新增 `SaveCmd`/`LoadCmd` + 注册到 `_CMD_REGISTRY`；3) 新建 `src/runtime/save.py`（SaveManager，JSON 文件 + 路径校验 + 槽位管理）；4) `main.py` 新增 cmd 循环（v0 简化下 main 不读 cmd_q——v2 改造） | 不做存档版本迁移（v3+）；不做存档压缩/加密（v3+）；不做云存档（v3+）；不做自动存档（v3+） |

### 3.2 不包含（Out of Scope）—— 明确推后

| 推后项 | 来源 | 推后原因 |
|---|---|---|
| v3+ 表达式系统增强（`randint` / `clamp` / `upper` / `lower` / `contains`） | ROADMAP §3.6 + EP-01 + EP-04 | v2 P0 三大功能完工后再启动；避免一次性引入过多扩展点 |
| v3+ `@LLM-jud` 装饰器框架 | ROADMAP §3.7 + EP-02 | 异步 + API key 管理 + 成本控制需另立 PDR；ROADMAP §3.7 风险标注 MEDIUM |
| v3+ 剧情编辑器 + 章节图可视化 | ROADMAP §3.9 / §3.10 | 需要 PyQt6 + 章节图元数据双前置 |
| v3+ 测试覆盖率提升 | ROADMAP §3.11 | 阶段三 v2 三大功能落地时顺带补边界测试 |
| 阶段三 P0 修复（v2 审计 4 P0 / 15 P1 / 9 P2 剩余项） | `v2-independent-audit-pm.md` | 阶段二已修 5 P0；其余 P1/P2 推后到 v3+ |

### 3.3 行为约束

- **不修改 v0/v1 解析器/执行器/表达式核心**——三大功能仅"加新文件 + 扩 EP 接入位"
- **保持向后兼容**——`DecoratorEvt.kind` 默认 `"call"` 兼容旧 dict；`SaveCmd/LoadCmd` 是新增 cmd，旧 3 cmd 继续工作
- **路径校验复用**——章节加载器不写新路径校验，复用 `main._load_story` 4 项校验（symlink/CHAPTERS_ROOT/.md/1MB）
- **JSON 序列化复用**——存档用 `protocol.py` 已有的 `json.dumps + utf-8` 模式（**D2 决策**）
- **PyQt6 降级**——`importlib.util.find_spec("PyQt6")` 检测，未装时降级 CLI 占位（**D3 决策**）
- **asyncio 不引入**——用 Qt 事件循环 + `QThread`（**D5 决策**）

---

## 4. 关键决策（D1-D5·用户拍板确认）

> **2026-06-26 用户拍板**：5 条决策全部用 readiness 文档推荐值，**不再走 PM 反复征询**。

| # | 决策点 | 用户选择 | 影响 | 落点 |
|---|---|---|---|---|
| **D1** | v2 三大功能**落地顺序** | **PyQt6 GUI 优先 → 章节加载器 → 存档** | ① PyQt6 是"看得见"的功能，先做能给用户最直观反馈；② 章节加载器是"跨章节"前置（存档需要 `current_block_id`）；③ 存档最复杂（需要 GameState 序列化 + IPC 扩展）放最后 | V2-01 → V2-04 → V2-06 |
| **D2** | 存档 JSON 序列化**是否复用** `protocol.py` | **复用** `json.dumps + utf-8` | 序列化格式统一；存档 JSON 与 IPC 消息用同一序列化模式；避免引入新依赖（PyYAML / msgpack） | `SaveManager.save/load` 用 `json.dumps(state.to_dict(), ensure_ascii=False).encode("utf-8")` |
| **D3** | PyQt6 缺失时**降级策略** | **保留 CLI 占位**（`find_spec("PyQt6")` 切换） | ① CI 跑测时无 PyQt6 也能跑；② 玩家无 PyQt6 时有 fallback；③ 实施简单（一行 `find_spec` + 工厂分发） | `runtime/gui/main.py:1-10` 切换 |
| **D4** | 存档**位置** | **`~/.neural-engine/saves/{slot}.json`**（按用户，多项目友好） | ① 多项目不冲突（不同工程在 `~/.neural-engine/saves/` 下不同子目录）；② 玩家可手动备份（标准 home 目录）；③ 跨平台一致（Windows / macOS / Linux 都用 `~`） | `SaveManager.__init__(save_dir=Path.home() / ".neural-engine" / "saves")` |
| **D5** | v2 是否引入 **asyncio** | **不引入**（用 Qt 事件循环 + QThread） | ① asyncio + Qt 事件循环双栈复杂（asyncio.run_in_executor 桥接繁琐）；② 现有 `Executor.run` 是同步阻塞模型，引入 asyncio 需重写主循环；③ 存档/章节路由都是同步事件（`RouteEvt` 触发的加载是阻塞的，简化模型下足够） | `PyQt6Sink.get_cmd()` 用 `QThread` 阻塞消费（`EngineBus.get_cmd` 是 blocking get） |

### 4.1 决策交叉引用

| 决策 | 关联 EP | 关联 issue | 关联 § |
|---|---|---|---|
| D1 顺序 | EP-05 / EP-10 / EP-09 | V2-01 → V2-04 → V2-06 | §6.4 并行窗口 |
| D2 JSON 复用 | EP-09 / EP-11 | V2-06 / V2-07 | §5.3 存档设计 |
| D3 PyQt6 fallback | EP-05 | V2-01 | §5.1 GUI 入口 |
| D4 存档位置 | EP-07 | V2-07 / V2-08 | §5.3 存档设计 |
| D5 不引入 asyncio | EP-03 | V2-01 / V2-02 | §5.1 GUI 入口 |

---

## 5. v2 三大功能设计

### 5.1 PyQt6 GUI（ROADMAP §3.1 + EP-03 / EP-05 / EP-06 / EP-08）

#### 5.1.1 接入点

| 优先级 | 接入点 | 位置 | 改动类型 |
|---|---|---|---|
| **P0** | `runtime.gui.main` 切换 | `src/runtime/gui/main.py:1-10` | **重写**——工厂分发（`find_spec("PyQt6")`） |
| **P0** | PyQt6 窗口 | 新建 `src/runtime/gui/pyqt6_main.py` | **新建**——QMainWindow + QTextEdit + QLineEdit |
| **P0** | `EventSink` Protocol | `src/core/engine/executor.py:28-32` | **不改**——已稳定；实现 `PyQt6Sink(QObject)` |
| **P1** | `DecoratorEvt.kind` 扩展 | `src/core/engine/protocol.py:151-169` | **扩展**（EP-06）—— `kind: Literal["call", "stop"]`（默认 `"call"`） |
| **P1** | 装饰器运行时钩子 | 新建 `src/core/decorators/style.py` | **新建**（EP-08）—— 注册 `@style` 钩子 |
| **P2** | TextRenderer / AudioManager | 新建 `src/runtime/renderer.py` / `audio.py` | **新建**（EP-07）—— 渲染/音频抽象（v3+ 落地） |

#### 5.1.2 流程图（D1 + D3 + D5 决策）

```
runtime/gui/main.py:1-10
├─ importlib.util.find_spec("PyQt6") is not None
│   ├─ YES → from runtime.gui.pyqt6_main import main as _pyqt_main
│   │         return _pyqt_main(bus)   # QApplication + QMainWindow + QThread
│   └─ NO  → return _cli_main(bus)     # v0 CLI 占位保留

runtime/gui/pyqt6_main.py（新建）
├─ QApplication + MainWindow
│   ├─ DisplayPanel(QTextEdit)   # 文本显示（append_text）
│   └─ InputPanel(QLineEdit)     # 用户输入（returnPressed → put_cmd）
├─ QThread 启动 bus 消费循环
│   ├─ while True: bus.get_evt() → QMetaObject.invokeMethod(...)
│   └─ 收到 PromptInputEvt → 激活 input；收到 RouteEvt → 退出
└─ PyQt6Sink(QObject) implements EventSink
    ├─ put_evt(evt) → signal emit（线程安全）
    └─ get_cmd() → 阻塞消费（PyQt6 信号槽）

core/decorators/style.py（新建·EP-08）
└─ register_hook("style", lambda key, val: PyQt6Sink.apply_style(key, val))
    # key/val 解析：@style text:rgb:red → TextRenderer.set_style("text", "rgb:red")
    # @style bgm:rain.mp3 → AudioManager.play("rain.mp3")   [v3+ 落地]
```

#### 5.1.3 验收标准

- `python -m runtime.gui.main` import 路径可走
- `importlib.util.find_spec("PyQt6")` 检测正确（mock 测试覆盖）
- PyQt6 装上时：弹出 QMainWindow 窗口，TextEvt/PromptInputEvt 渲染正常，QLineEdit 回车推 `UserInputCmd`
- PyQt6 没装时：降级 CLI 占位（**D3 决策**）—— `print` 事件 + `input()` 阻塞
- CI 跑 pytest 时 PyQt6 不在 PATH——验证降级路径走通
- `tests/runtime/test_gui_pyqt6.py` mock 测试：PyQt6Sink 包装 EngineBus 收发正常（不实际启动 QApplication）

### 5.2 章节加载器（ROADMAP §3.2 + EP-10 / EP-11）

#### 5.2.1 接入点

| 优先级 | 接入点 | 位置 | 改动类型 |
|---|---|---|---|
| **P0** | `RouteEvt` 处理 | 新建 `src/runtime/chapter_manager.py` | **新建**——订阅 RouteEvt |
| **P0** | `_load_story` 抽取 | `src/core/engine/main.py:28-51` | **抽取**——复用路径校验逻辑到 `runtime/load_chapter.py` |
| **P0** | `EngineBus` 事件循环 | 新建 `src/runtime/chapter_manager.py` | **新建**——独立的 bus consumer（订阅 RouteEvt） |
| **P1** | `LoadChapterCmd` 消费 | `src/core/engine/main.py:67-137` | **新增**（EP-11）—— GUI 主动加载（v2 简化下仍走 RouteEvt 路径） |
| **P2** | `RouteEvt` schema 扩展 | `src/core/engine/protocol.py:172-182` | **扩展**（v3+）—— 可加 `save_state: bool` |

#### 5.2.2 流程图

```
runtime/chapter_manager.py（新建）
├─ class ChapterManager:
│   def __init__(self, chapters_dir: Path, bus: EngineBus):
│       self.chapters_dir = chapters_dir
│       self.bus = bus
│
│   def on_route(self, evt: RouteEvt) -> None:
│       chapter_path = self.chapters_dir / f"{evt.target}.md"
│       story = load_chapter_safe(chapter_path)  # 复用 _load_story 校验
│       executor = Executor(story, sink=self.bus)
│       executor.run()  # 同步阻塞（v2 简化；v3+ 可改异步）
│
│   def run(self) -> None:
│       while True:
│           evt = self.bus.get_evt()
│           if isinstance(evt, RouteEvt):
│               self.on_route(evt)
│           elif isinstance(evt, ChapterEndEvt):
│               break

runtime/load_chapter.py（新建·抽取自 main.py:28-51）
└─ def load_chapter_safe(chapter_path: Path) -> Story:
    # 复用 main._load_story 4 项校验：symlink/CHAPTERS_ROOT/.md/1MB
    ...

main.py:67-137（改造）
├─ bus = EngineBus(use_multiprocessing=True)
├─ mgr = ChapterManager(CHAPTERS_ROOT, bus)
└─ mgr.run()  # 取代直接 Executor.run()
```

#### 5.2.3 跨章节状态保留

- **D1 决策顺序**：先做 PyQt6 GUI → 再做章节加载器 → 最后做存档
- **跨章节变量**：`GameState.vars` 跨块已隐式全局（ADR-0001 §11 不变量 #1），新建 Executor 时**复用同一 state 对象**（`Executor(story, sink, state=self.state)`）
- **验证**：`chapter01.md` → `id:end1:chapter02` → 自动加载 `chapters/chapter02.md` → chapter01 的变量在 chapter02 可读

#### 5.2.4 验收标准

- `python -m core.engine.main chapters/chapter01.md` 启动后能跨章节跳转
- `tests/integration/test_chapter_routing.py` 端到端：`chapter01.md` 触发 `id:end1:chapter02` → 自动加载 `chapter02.md` → 变量 `pick` 跨章节保留
- `_load_story` 4 项校验复用（路径校验不破不重写）
- 章节图元数据 `chapters/index.yaml`：**不做**（v3+）
- GUI 主动 `LoadChapterCmd` 消费：**不做**（v3+，v2 简化下走 RouteEvt 路径）

### 5.3 存档/读档（ROADMAP §3.3 + EP-07 / EP-09 / EP-11）

#### 5.3.1 接入点

| 优先级 | 接入点 | 位置 | 改动类型 |
|---|---|---|---|
| **P0** | `GameState.to_dict/from_dict` | `src/core/engine/executor.py:63-68` | **扩展**（EP-09）—— 序列化方法 + `current_block_id` 字段 |
| **P0** | `SaveCmd/LoadCmd` 新增 | `src/core/engine/protocol.py:93-97` | **新增**（EP-11）—— 注册到 `_CMD_REGISTRY` |
| **P0** | `SaveManager` | 新建 `src/runtime/save.py` | **新建**（EP-07）—— JSON 文件持久化 + 槽位管理 |
| **P0** | main.py cmd 循环 | `src/core/engine/main.py:67-137` | **新增**—— 监听 cmd_q + 处理 SaveCmd/LoadCmd |
| **P2** | 存档元数据（时间/slot 名） | `src/runtime/save.py` | **不做**（v3+） |

#### 5.3.2 流程图（D2 + D4 决策）

```
executor.py:63-68 GameState 扩展（EP-09）
├─ @dataclass class GameState:
│     vars: dict = field(default_factory=dict)
│     path: list = field(default_factory=list)
│     next_table: dict = field(default_factory=dict)
│     current_block_id: str | None = None  # v2 新增
│
│   def to_dict(self) -> dict:
│       return {
│           "version": 1,  # 存档版本字段
│           "vars": dict(self.vars),
│           "path": list(self.path),
│           "current_block_id": self.current_block_id,
│       }
│
│   @classmethod
│   def from_dict(cls, d: dict) -> "GameState":
│       return cls(
│           vars=dict(d.get("vars", {})),
│           path=list(d.get("path", [])),
│           current_block_id=d.get("current_block_id"),
│       )

protocol.py:93-97 新增（EP-11）
├─ @dataclass(frozen=True, slots=True)
│  class SaveCmd:
│      slot: str
│      def to_dict(self) -> dict: return {"cmd": "save", "slot": self.slot}
│      @classmethod
│      def from_dict(cls, d: dict) -> "SaveCmd": ...
│
├─ @dataclass(frozen=True, slots=True)
│  class LoadCmd:
│      slot: str
│      def to_dict(self) -> dict: return {"cmd": "load", "slot": self.slot}
│      @classmethod
│      def from_dict(cls, d: dict) -> "LoadCmd": ...
│
└─ _CMD_REGISTRY["save"] = SaveCmd
   _CMD_REGISTRY["load"] = LoadCmd

runtime/save.py（新建·EP-07 + D4 决策）
├─ class SaveManager:
│   def __init__(self, save_dir: Path = Path.home() / ".neural-engine" / "saves"):
│       self.save_dir = save_dir
│       self.save_dir.mkdir(parents=True, exist_ok=True)
│
│   def save(self, slot: str, state: GameState) -> None:
│       # D2 决策：复用 protocol.py json.dumps + utf-8
│       path = self.save_dir / f"{slot}.json"
│       path.write_text(
│           json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
│           encoding="utf-8",
│       )
│
│   def load(self, slot: str) -> GameState:
│       path = self.save_dir / f"{slot}.json"
│       data = json.loads(path.read_text(encoding="utf-8"))
│       return GameState.from_dict(data)
│
│   def list_slots(self) -> list[str]:
│       return sorted([p.stem for p in self.save_dir.glob("*.json")])

main.py:67-137 cmd 循环
├─ v0 简化下 main 不读 cmd_q——v2 改造：新建 QThread 读 cmd_q
│   ├─ 收到 SaveCmd → SaveManager.save(cmd.slot, executor.state)
│   ├─ 收到 LoadCmd → executor.state = SaveManager.load(cmd.slot)
│   └─ 收到 LoadChapterCmd → 主动加载章节（v3+；v2 走 RouteEvt 路径）
└─ 收到 ShutdownCmd → 优雅退出
```

#### 5.3.3 存档版本兼容

- `to_dict()` 写 `"version": 1` 字段；`from_dict` 检查版本，v3+ 升级时写迁移函数
- 文档化"`vars` 仅含 str/int/list/dict"——其他类型（datetime / custom class）需先 `to_dict()` 再存档

#### 5.3.4 验收标准

- `python -m core.engine.main chapters/chapter01.md` 启动后能存档/读档
- 存档位置：`~/.neural-engine/saves/{slot}.json`（**D4 决策**）
- 存档格式：`json.dumps(state.to_dict(), ensure_ascii=False, indent=2) + utf-8`（**D2 决策**）
- 存档内容：`{"version": 1, "vars": {...}, "path": [...], "current_block_id": "..."}`
- 读档后能恢复到保存前状态（vars + current_block_id）
- 存档 round-trip 100+ 测试（`tests/runtime/test_save_manager.py`）
- `tests/integration/test_save_load_e2e.py`：游戏中途存档 → 重启 → 读档 → 恢复状态

---

## 6. v2 × 11 EP 接入矩阵

> **来源**：[`docs/audit/phase3-method-audit.md` §4.3](../audit/phase3-method-audit.md#43-扩展点交叉引用矩阵v2-三大功能-vs-11-个-ep)
> **图例**：**✓✓** = 该 EP 是此 v2 功能的核心接入点；✓ = 次要依赖；— = 不相关

| v2 功能 | EP-01 | EP-02 | EP-03 | EP-04 | EP-05 | EP-06 | EP-07 | EP-08 | EP-09 | EP-10 | EP-11 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **PyQt6 GUI (§5.1)** | — | — | **✓✓** | — | **✓✓** | **✓✓** | ✓ | **✓✓** | — | — | — |
| **章节加载器 (§5.2)** | — | — | ✓ | — | ✓ | — | — | — | — | **✓✓** | ✓ |
| **存档 (§5.3)** | — | — | — | — | — | — | **✓✓** | — | **✓✓** | — | **✓✓** |
| **合计** | 0 | 0 | 2 | 0 | 2 | 1 | 1 | 1 | 1 | 1 | 1 |

### 6.1 接入位详表

| EP | 难度 | 接入位 | 改造 issue | v2 § |
|---|---|---|---|---|
| **EP-03** `EventSink` Protocol | S | `executor.py:28-32` | V2-01 | §5.1 |
| **EP-05** `_try_spawn_gui` | S | `main.py:54-64` | V2-01 | §5.1 |
| **EP-06** `DecoratorEvt.kind` | M | `protocol.py:151-169` | V2-02 | §5.1 |
| **EP-07** `src/runtime/` 占位 | S | `src/runtime/__init__.py` | V2-07 / V2-08 | §5.3 |
| **EP-08** `src/core/decorators/` 占位 | S | `src/core/decorators/__init__.py` | V2-02 | §5.1 |
| **EP-09** `GameState` 序列化 | M | `executor.py:63-68` | V2-06 | §5.3 |
| **EP-10** `RouteEvt` 处理 | S | `executor.py:350-351` + `protocol.py:172-182` | V2-04 | §5.2 |
| **EP-11** IPC 协议扩展 | S | `protocol.py:93-97` | V2-07 | §5.3 |

> **未在本 PDR 落地的 EP**（推后到 v3+）：
> - EP-01 `register_function`（v3+ 表达式系统增强）
> - EP-02 `register_evaluator`（v3+ `@LLM-jud`）
> - EP-04 `BUILTIN_FUNCS` 扩展（v3+ 表达式系统增强）

### 6.2 风险与依赖

| EP | 风险 | 缓解 |
|---|---|---|
| EP-03 | LOW（Protocol 抽象稳定） | `MemoryEventSink` 范式已稳定；`PyQt6Sink` 实现只需包装 `EngineBus` |
| EP-05 | LOW（Popen 工厂已封装） | v2 改造仅替换 GUI 模块内部 |
| EP-06 | LOW（向后兼容） | `from_dict` 兼容旧 dict（默认 `"call"`） |
| EP-07 | LOW（占位已留） | 目录 + CONTEXT.md 已定义术语表 |
| EP-08 | MEDIUM（`DecoratorEvt.args` 是 `list[str]`） | v2 走"字符串 key/val 解析"——结构化参数（G5）v3+ 落地 |
| EP-09 | MEDIUM（`vars: dict[str, Any]` 类型宽泛） | v2 文档化"vars 仅含 str/int/list/dict"；存档加 `version` 字段 |
| EP-10 | LOW（事件已稳定） | v2 仅加消费方（`ChapterManager.on_route`） |
| EP-11 | LOW（工厂模式可复用） | v2 扩展仅改 `_CMD_REGISTRY` 字典 |

### 6.3 数据契约稳定性

- **11 个 IPC dataclass**（3 cmd + 6 evt + 2 parse）保持 `frozen=True, slots=True` —— 新增字段必须向后兼容
- **DecoratorEvt.kind** 默认 `"call"` —— 旧 GUI 收到 `DecoratorEvt(name, args)`（无 kind）时走默认 call
- **SaveCmd/LoadCmd** 是新增 cmd —— 旧 3 cmd 继续工作；`parse_cmd` 工厂模式直接复用

### 6.4 并行窗口（D1 决策 + 8 个开发 issue 依赖）

```
Window 1 (3 个并行)        Window 2 (3 个并行)        Window 3 (2 个并行)    Window 4
─────────────────────      ─────────────────────      ────────────────────   ───────
V2-01 PyQt6 GUI 入口  ──→  V2-02 装饰器渲染     ──→  V2-03 PyQt6 测试
V2-04 ChapterManager ──→  V2-05 章节加载器测试                            →  V2-09
V2-06 GameState 序列化 ──→ V2-07 SaveManager  ──→                         文档+回归
                                                  V2-08 EP-07 骨架

(本 PDR 不在并行窗口内) ──→ V2-08 依赖 V2-07 ──→ (本 PDR 不在并行窗口内)
```

**详细依赖**：

| Issue | 估时 | 依赖 | 类别 | Window |
|---|---|---|---|---|
| V2-01 PyQt6 GUI 入口 | M（2-3 天） | 无 | PyQt6 | W1 |
| V2-02 装饰器渲染 | M（1-2 天） | V2-01 | PyQt6 | W2 |
| V2-03 PyQt6 GUI 测试 | S（0.5-1 天） | V2-01 + V2-02 | PyQt6 | W3 |
| V2-04 ChapterManager | M（2-3 天） | 无 | 章节 | W1 |
| V2-05 章节加载器测试 | S（0.5-1 天） | V2-04 | 章节 | W2 |
| V2-06 GameState 序列化 | S（1 天） | 无 | 存档 | W1 |
| V2-07 SaveManager | M（2-3 天） | V2-06 | 存档 | W2 |
| V2-08 EP-07 骨架 | S（0.5-1 天） | V2-07 | 骨架 | W3 |
| V2-09 文档同步+回归 | S（0.5-1 天） | V2-01~V2-08 | 回归 | W4 |
| **合计** | **11-15 天** | — | — | — |

**优化并行后**：3 个 W1 issue 全并行 + 3 个 W2 issue 全并行 + 2 个 W3 issue 全并行 + 1 个 W4，总耗时约 **5-7 天**（按 3 人小团队上限计算）。

---

## 7. 验收标准

### 7.1 硬性验收（必须达成）

1. **PDR 落盘**：`docs/pdr/phase3-v2p0.md` 存在（本文件）
2. **Issue 列表落盘**：`docs/issues/phase3-v2p0.md` 存在，9 个原子 issue（V2-01 ~ V2-09）
3. **GitHub 模板落盘**：`docs/issues/github/v2-NN-xxx.md` 9 个文件存在（issue #72-#80）
4. **5 决策已拍板**：D1-D5 全部用 readiness 推荐值（§4 表格）
5. **不动 src/**：本 PDR 任务期间 `git diff src/` 为空
6. **不动 v1 偏差 + 阶段二 P0**：仅文档任务，不动代码
7. **依赖关系明确**：每个 issue 标注依赖 + Window 归属
8. **并行窗口清晰**：6.4 图示 + 表格

### 7.2 软性验收（建议达成）

- 9 个 issue 估时合理（参考阶段一/二历史 commit 量）
- GitHub 模板格式与 v0-issue-*.md 一致（## Parent / What to build / Acceptance criteria / Blocked by）
- Open Questions 转 PM 拍板（§10）

### 7.3 失败定义

- PDR 缺失 §4 决策表 → 任务失败
- Issue 列表 < 7 或 > 10 个 → 任务失败
- GitHub 模板缺失或编号错位（应从 #72 起）→ 任务失败
- 9 个 issue 依赖关系矛盾 → 任务失败
- 改了 `src/` 下任何代码 → 任务失败（pdr 任务边界）

---

## 8. 边界（Out of Scope 详细）

| 推后项 | 来源 | 推到 | 推后原因 |
|---|---|---|---|
| v3+ 表达式系统增强 | ROADMAP §3.6 + EP-01 + EP-04 | v3+ | 避免一次性引入过多扩展点 |
| v3+ `@LLM-jud` 装饰器 | ROADMAP §3.7 + EP-02 | v3+ | 异步 + API key + 成本需另立 PDR |
| v3+ 剧情编辑器 | ROADMAP §3.9 | v3+ | 需要 PyQt6 + 章节图双前置 |
| v3+ 章节图可视化 | ROADMAP §3.10 | v3+ | 需要 `chapters/index.yaml` + DAG 工具 |
| v3+ 音频/视频 | ROADMAP §3.6-§3.8（部分） | v3+ | PyQt6 GUI 仅渲染文字，音频推到 v3+ |
| v3+ 存档元数据（时间/截图） | `runtime/CONTEXT.md` | v3+ | v2 简化版够用 |
| v3+ 存档版本迁移 | §5.3.3 | v3+ | v2 加 `version: 1` 字段为未来迁移留位 |
| v3+ `index.yaml` 章节图 | §5.2 | v3+ | v2 按文件名加载够用 |
| v3+ GUI 主动 `LoadChapterCmd` 消费 | §5.2 | v3+ | v2 走 RouteEvt 路径 |
| 阶段三 P0 修复（v2 审计剩余 P1/P2） | `v2-independent-audit-pm.md` | v3+ | 阶段二已修 5 P0 |
| 测试覆盖率提升 | ROADMAP §3.11 | 阶段三 v2 三大功能落地时顺带补 | 不单独立 issue |

---

## 9. 风险

### 9.1 架构风险

| 风险 | 等级 | 说明 | 缓解 |
|---|---|---|---|
| **架构清晰但"中心枢纽"耦合** | LOW | `executor.py` 是所有事件 / 表达式 / state 的汇聚点 | 严格保持 Protocol 抽象（`EventSink`） |
| **protocol.py 是"数据契约中心"** | LOW | 11 个 dataclass 全模块依赖 | 严格遵守 `frozen=True, slots=True`；新增字段必向后兼容 |
| **`GameState.vars: dict[str, Any]`** | MEDIUM | 当前仅 str/int，v2 可能含 list/dict；存档序列化风险 | 文档化"vars 仅含 str/int/list/dict"；存档加 `version: 1` 字段 |

### 9.2 v2 改造风险（D1-D5 决策相关）

| 风险 | 等级 | 关联决策 | 缓解 |
|---|---|---|---|
| **PyQt6 信号槽跨线程** | MEDIUM | D5（不引入 asyncio） | `Qt.QueuedConnection` + QObject 线程安全 API；QThread 读 cmd_q |
| **DecoratorEvt 不区分 call/stop** | LOW | — | EP-06 扩 `kind` 字段（向后兼容默认 `"call"`） |
| **装饰器运行时钩子未实现** | MEDIUM | — | EP-08 新建 `core/decorators/` 子包；v2 走"字符串 key/val 解析" |
| **跨章节状态保留** | MEDIUM | D1 顺序 | `GameState.vars` 跨块已隐式全局；新建 Executor 时 `state` 复用 |
| **存档版本兼容** | LOW | D2 复用 | 加 `version: int` 字段，迁移函数 v3+ 写 |
| **跨块 `current_block_id` 更新** | LOW | — | Executor.run 入口 / `_next_block` 后置 |
| **存档 slot 命名争议** | LOW | D4 位置 | 文件名 + slot 名（玩家可读），不做 UUID |
| **PyQt6 缺失时** | LOW | D3 降级 | 降级 CLI 占位 + 启动 banner 提示（与 v0 headless 一致） |
| **asyncio + Qt 事件循环双栈** | LOW | D5 不引入 | v2 简化模型足够；v3+ 再评估 |

### 9.3 测试风险

| 风险 | 等级 | 缓解 |
|---|---|---|
| **PyQt6 不在 CI PATH** | LOW | CI 跑降级路径；PyQt6Sink 包装用 mock 测试 |
| **存档位置 `~/.neural-engine/saves/` 在 CI 写入** | LOW | 测试用 `tmp_path` fixture 注入临时目录 |
| **跨章节端到端 fixture 复杂** | MEDIUM | `tests/integration/test_chapter_routing.py` 用最小 chapter01/02 |
| **存档 round-trip 边界（vars 含不可序列化对象）** | MEDIUM | v2 文档化"vars 仅含 str/int/list/dict"；加 `version: 1` |

### 9.4 进度风险

| 风险 | 等级 | 缓解 |
|---|---|---|
| **9 个 issue 全串行** | MEDIUM | 3 个 W1 + 3 个 W2 + 2 个 W3 + 1 个 W4，3 人小团队 5-7 天 |
| **跨模块改造耦合**（EP-06 改 protocol.py 影响所有 evt） | LOW | 严格向后兼容（默认 `"call"`） |
| **tdd-coder 不熟悉 PyQt6 线程模型** | MEDIUM | 实施前先做小 PoC（QApplication + QThread + signal/slot） |

---

## 10. Open Questions（待 PM 拍板）

| # | 问题 | 影响 | 建议 | 关联 EP |
|---|---|---|---|---|
| **OQ-1** | v2 章节加载器用相对路径（`CHAPTERS_ROOT` 拼接）还是绝对路径（GUI 传）？ | `_load_story` 当前只支持相对路径校验；ROADMAP §3.2 章节加载器需新接口 | 推**相对路径**（与 P0-S1 一致）；`ChapterManager.on_route` 用 `CHAPTERS_ROOT / f"{target}.md"` | EP-10 |
| **OQ-2** | 存档 slot 命名（`slot="chapter01_save01"` 长名 vs `slot="01"` 短名）？ | `runtime/save.py` `SaveManager.save` API | 推**短名 + 序号**（玩家可读，可手动备份）；不做 UUID | EP-09 + EP-11 |
| **OQ-3** | 跨章节变量传递：变量随章节保留还是每章节重置？ | `GameState.vars` 生命周期 | 推**保留**（隐式全局已实现，仅文档化） | EP-09 |
| **OQ-4** | `EventSink` Protocol 是否需扩 `close()` 方法？ | 资源清理生命周期 | 推 v2 加 `close()`（与 `EngineBus.close()` 对齐） | EP-03 |
| **OQ-5** | `GameState.vars` 是否允许非 JSON 类型（datetime / custom class）？ | EP-09 序列化范围 | 推**仅 str / int / list / dict**（明确文档）；其他类型序列化前 `to_dict()` | EP-09 |
| **OQ-6** | 存档 round-trip 失败时 GUI 提示策略？ | UX 错误处理 | 推**LogEvt(error) + GUI 弹窗**（与现有错误流一致） | EP-07 + EP-11 |
| **OQ-7** | 跨章节存档：跨章节时是否自动存档？ | 存档时机 | 推**手动存档**（v2 简化；自动存档 v3+） | EP-09 |
| **OQ-8** | PyQt6 缺失时启动 banner 文案？ | UX 一致性 | 推 `"GUI not available, running headless"`（与 v0 `LogEvt` 文案一致） | EP-05 |

> **备注**：8 条 OQ 中，**OQ-1 / OQ-2 / OQ-3 / OQ-4 / OQ-5 已在 `phase3-method-audit.md` §9 列出**（pdr-analyst · 2026-06-25）；**OQ-6 / OQ-7 / OQ-8** 是本 PDR 新增（D1-D5 决策带来的衍生 OQ）。所有 OQ 推 PM 拍板，tdd-coder 实施前必须得到回答。

---

## 11. 引用与索引

### 11.1 前置文档（必读）

- [`docs/audit/phase3-method-audit.md`](../audit/phase3-method-audit.md) — 方法级审计报告（11 EP + 72 public API + 4 维度状态/进程边界）
- [`docs/pdr/phase3-method-audit.md`](../pdr/phase3-method-audit.md) — 方法级审计 PDR
- [`docs/ROADMAP.md`](../ROADMAP.md) — v0 + v1 + 阶段二总结 + v2 P0/P1/P2/P3 路线图
- [`docs/audit/v2-independent-audit-pm.md`](../audit/v2-independent-audit-pm.md) — 阶段一/二基线 + 4 P0 / 15 P1 / 9 P2

### 11.2 ADR（决策记录）

- [ADR-0001](../adr/0001-v0-baseline-script-spec.md) — v0 baseline script spec（命名空间 / NEXT 三阶段 / 协议）
- [ADR-0002](../adr/0002-v0-engine-implementation.md) — v0 引擎实现完工记录（4 条偏差 / D-main：main 不读 cmd_q）
- [ADR-0003](../adr/0003-v1-expression-subsystem.md) — v1 表达式子系统架构（ExprDispatcher / CustomExecutor / BUILTIN_FUNCS）
- [ADR-0004](../adr/0004-v1-refactor-design.md) — v1 重构设计（砍 translator / G5 修饰器结构化 / @LLM-jud 远期）

### 11.3 关联 issue

- 本 PDR 拆解的 9 个 issue（V2-01 ~ V2-09）→ 详见 [`docs/issues/phase3-v2p0.md`](../issues/phase3-v2p0.md)
- GitHub issue 模板（#72-#80）→ 详见 [`docs/issues/github/v2-NN-xxx.md`](../issues/github/)

### 11.4 关键源文件（v2 改造位）

| 文件 | 改造位 | 关联 issue |
|---|---|---|
| `src/runtime/gui/main.py` | 顶部 find_spec 切换 | V2-01 |
| `src/runtime/gui/pyqt6_main.py` | **新建** | V2-01 |
| `src/runtime/chapter_manager.py` | **新建** | V2-04 |
| `src/runtime/load_chapter.py` | **新建**（抽取自 main.py） | V2-04 |
| `src/runtime/save.py` | **新建** | V2-07 |
| `src/core/decorators/style.py` | **新建** | V2-02 |
| `src/core/engine/executor.py` | GameState 扩 `to_dict/from_dict` + `current_block_id` | V2-06 |
| `src/core/engine/protocol.py` | DecoratorEvt 扩 `kind` + 新增 SaveCmd/LoadCmd | V2-02 / V2-07 |
| `src/core/engine/main.py` | cmd 循环（SaveCmd/LoadCmd 消费）+ ChapterManager 启动 | V2-04 / V2-07 |

---

## 12. 一句话总结

**基于 11 个预留扩展点（EP-01~EP-11）+ 5 决策 D1-D5 拍板确认，v2 三大功能（PyQt6 GUI / 章节加载器 / 存档）拆为 9 个原子 issue（V2-01~V2-09，#72-#80），按 3+3+2+1 并行窗口执行，3 人小团队 5-7 天可完工——完工后玩家能"看到 PyQt6 窗口、跨章节跳转、存档读档"三大核心体验闭环。**

---

*哈尼斯 · pdr-analyst · 2026-06-26 · 阶段三·v2 P0 三大功能 PDR 待 PM 分派*
