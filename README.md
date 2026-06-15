# Neural Engine

> 中文文字游戏引擎 · v0 baseline 已完工

## 状态

| 维度 | 状态 | 证据 |
|---|---|---|
| v0 基础版引擎 | ✅ **已闭环** | v0-issue-1 ~ 19 全部落地（19 feat commit） |
| pytest | ✅ **182/182 PASSED** | `python3 -m pytest tests/ -q` |
| §8 MVP 表 | ✅ **18/18** | `tests/test_mvp_table.py` |
| §11 关键不变量 | ✅ **10/10** | `tests/test_invariants.py` |
| 端到端跑通路径 | ✅ **in → echo → end** | `tests/integration/test_echo_path.py` |
| GitHub Issues | ✅ **22/22 closed** | 含 19 AFK + 2 HITL + 1 父 issue |
| 实现偏差登记 | 4 条（owner 已接受） | [ADR-0002 §5](docs/adr/0002-v0-engine-implementation.md) |

> v0 阶段边界：引擎解析 + 核心调度 + CLI 占位 GUI 跑通；真跨进程 PyQt6 窗口（v0-issue-18 路径 A）**推迟到 v1**。

## 这是什么

一个面向中文创作者的文字游戏引擎。剧情写作者用 Markdown + 内嵌的 ` ```neon ` DSL 描述剧情节点，引擎进程解析并执行节点、广播事件给 GUI 进程，GUI 渲染文本 / 接收玩家输入。

**v0 设计核心**：
- 剧情格式 = Markdown + `neon` 代码块
- 节点 = `node start` ~ `node end` 的连续语句
- 控制流 = 隐藏变量 `NEXT` 引用 `next` 声明表项
- 跨块路由 = `id:endX:chapterYY` 块执行到 `node end` 时广播 `RouteEvt`
- 进程模型 = Engine（core 进程） + GUI（runtime 进程）双向 `multiprocessing.Queue`
- 修饰器 = `@style key:val, ...` 块内作用域、last-wins

## 快速跑通

### 安装

```bash
python3 -m pip install -r requirements-dev.txt
# 可选（v1 用）：python3 -m pip install -r requirements-gui.txt
```

### 跑测

```bash
python3 -m pytest tests/ -q
# 期望：182 passed in ~9s
```

### 跑引擎（v0 CLI 占位 GUI）

```bash
# v0 入口：解析 + 调度 + CLI 占位渲染（不用 PyQt6）
python3 -m core.engine.main chapters/chapter01.md
```

GUI 进程是 `python3 -m runtime.gui.main`，由 `core.engine.main` 自动 spawn 启动；GUI 不可用时降级为 headless 模式（事件走 `EngineBus` 但无人渲染），日志里会写 `GUI not available, running headless`。

### 跑 v0 唯一端到端路径

```bash
python3 -m pytest tests/integration/test_echo_path.py -v
# 走 fixture tests/test_echo.md：in → echo → end
```

## 架构

### 双进程

```text
┌────────────────────┐    EngineBus      ┌────────────────────┐
│  core/engine/main  │ ◀──JSON dict──▶  │  runtime/gui/main  │
│  - interpreter.py  │  cmd_q / evt_q    │  (v0: CLI 占位)    │
│  - executor.py     │  multiprocessing  │  (v1: PyQt6 路径 A)│
│  - bus.py          │  .Queue           │                    │
└────────────────────┘                   └────────────────────┘
        │                                         │
        ▼                                         ▼
  chapters/*.md 章节                  文本 / 输入框 / 富文本渲染
```

- 消息 schema：[`src/core/engine/protocol.py`](src/core/engine/protocol.py) — 3 条 `Cmd` + 6 条 `Evt`，全部 `@dataclass` + `to_dict` / `from_dict` JSON
- 传输层：[`src/core/engine/bus.py`](src/core/engine/bus.py) — `EngineBus` 封装 `multiprocessing.Queue`（真进程）/ `queue.Queue`（测试注入）

### 核心模块

| 模块 | 行数（实） | 职责 | 入口符号 |
|---|---|---|---|
| `src/core/engine/ast_nodes.py` | AST dataclass | 17 AST 节点 + 3 sentinels + `ParserError` | `Story`, `Block`, `Text`, `In`, `Echo`, `NextId`, `If`, `Branch`, `NextDecl`, `CallExpression` |
| `src/core/engine/protocol.py` | 进程协议 | 3 Cmd + 6 Evt 消息 dataclass | `LoadChapterCmd`, `UserInputCmd`, `TextEvt`, `PromptInputEvt`, `RouteEvt`, `ChapterEndEvt`... |
| `src/core/engine/bus.py` | 数据总线 | 双向 Queue + JSON 序列化 | `EngineBus` |
| `src/core/engine/interpreter.py` | 解析器 | 6 段流水线：fence → skeleton → meta → next → body → if | `extract_neon_blocks`, `parse_block_skeleton`, `parse_block_meta`, `parse_next_decls`, `parse_block_body`, `parse_if_stmt`, `parse_decorator` |
| `src/core/engine/executor.py` | 调度器 | 节点循环 + 修饰器 + 分支桩 + 跨块 ID 校验 | `Executor`, `GameState`, `EventSink`, `MemoryEventSink`, `MemoryInputSink` |
| `src/core/engine/main.py` | 进程入口 | 装配 + 加载 + GUI spawn + 降级 | `main()` |
| `src/runtime/gui/main.py` | GUI 入口 | v0 CLI 占位（v1 切 PyQt6） | `main()` |

> 行数 / 符号数来源：[`codegraph files`](.codegraph/) 索引（37 文件 / 470 nodes / 1566 edges）。

## 项目结构

```
.
├── src/
│   ├── core/
│   │   ├── decorators/         # 修饰器实现（@style 等，v0 解析 + 占位调度）
│   │   └── engine/             # 核心引擎 7 文件
│   │       ├── ast_nodes.py    # AST dataclass
│   │       ├── bus.py          # EngineBus
│   │       ├── executor.py     # Executor + GameState + Sinks
│   │       ├── interpreter.py  # 6 段解析流水线
│   │       ├── main.py         # core 进程入口
│   │       └── protocol.py     # Cmd / Evt schema
│   ├── editor/                 # 剧情编辑器（v0 不实现）
│   └── runtime/
│       └── gui/                # GUI 进程（v0 CLI 占位 / v1 PyQt6）
├── tests/
│   ├── core/                   # 单元测试（16 文件）
│   ├── integration/            # 端到端测试（2 文件）
│   ├── runtime/                # GUI 协议测试（1 文件）
│   ├── test_invariants.py      # §11 10 条不变量守护（11 用例）
│   ├── test_mvp_table.py       # §8 18 条 MVP 表逐条勾（19 用例）
│   └── test_skeleton_smoke.py  # 包导入冒烟
├── chapters/
│   └── chapter01.md            # v0 官方 fixture（ADR-0001 附录 A）
├── docs/
│   ├── adr/                    # 架构决策记录
│   │   ├── 0001-v0-baseline-script-spec.md   # v0 规范
│   │   └── 0002-v0-engine-implementation.md  # v0 完工 + 4 条偏差登记
│   ├── prds/
│   │   └── 0001-v0-engine-implementation.md   # v0 PRD（22 user stories）
│   ├── audit/
│   │   └── v0-invariant-audit.md              # §11 + §8 验收报告
│   └── agents/                 # Agent 协作说明
├── 工作Wiki/                   # 项目 wiki（Obsidian vault）
│   ├── 00-index/
│   ├── 10-design/
│   ├── 20-architecture/
│   ├── 30-protocol/            # 含 implementation-deviations.md
│   └── 90-meta/
├── pyproject.toml
├── pytest.ini
├── requirements.txt
├── requirements-dev.txt
├── requirements-gui.txt
└── README.md
```

## 文档与设计

| 主题 | 路径 |
|---|---|
| v0 脚本规范 | [docs/adr/0001-v0-baseline-script-spec.md](docs/adr/0001-v0-baseline-script-spec.md) |
| v0 完工记录 + 4 条实现偏差 | [docs/adr/0002-v0-engine-implementation.md](docs/adr/0002-v0-engine-implementation.md) |
| v0 PRD（22 user stories） | [docs/prds/0001-v0-engine-implementation.md](docs/prds/0001-v0-engine-implementation.md) |
| §11 不变量审计 | [docs/audit/v0-invariant-audit.md](docs/audit/v0-invariant-audit.md) |
| 实现偏差详细分析 | [工作Wiki/30-protocol/implementation-deviations.md](工作Wiki/30-protocol/implementation-deviations.md) |
| Agent 协作约定 | [CLAUDE.md](CLAUDE.md) |
| 多上下文域文档 | [CONTEXT-MAP.md](CONTEXT-MAP.md) |

### v0 实现偏差摘要（4 条，owner 已接受）

完整登记见 ADR-0002 §5。

1. **D1-confirmed** · `decorator_state` 在 `run_block` **入口**清（不是 `End` 时清）—— owner 接受，理由是更稳妥
2. **D-NEW-1** · 分支项用 `CallExpression(kind, var)` 包装 echo/in —— owner 接受，理由是和块内 `In`/`Echo` 节点语义解耦
3. **D-NEW-2** · `ParserError.loc` 变可选 —— owner 接受
4. **D-main** · `core.engine.main` 在 GUI 不可用时降级为 headless 日志 —— owner 接受

### v0 已知未实现（推到 v1+）

- **PyQt6 GUI 窗口**（v0-issue-18 路径 A）
- **CodeGraph 4 个 internal helper 单测**（`EngineBus._drain/_close_queue`、`Executor._emit_decorator/_validate_target_ids`、`main._try_spawn_gui`）—— 当前 152 测试已间接覆盖，缺边界单测
- **GUI 跨进程联调**（v0 阶段 CLI 占位即满足 AC）
- **v0-issue-22** 待 owner 开启 v1

## 开发

### 跑单测

```bash
# 全部
python3 -m pytest tests/ -q

# 单文件
python3 -m pytest tests/core/test_executor_nodes.py -v

# 单用例
python3 -m pytest tests/test_mvp_table.py::test_mvp_18 -v

# 不变量守护（含 3 条 grep）
python3 -m pytest tests/test_invariants.py -v
```

### CodeGraph（推荐代码探索工具）

仓库已初始化 CodeGraph 索引（37 文件 / 470 nodes / 1566 edges，1.38 MB SQLite）：

```bash
# 列出文件结构
codegraph files

# 看某符号的源码 + 调用者 + 被调用者
codegraph explore Executor
codegraph node EngineBus
codegraph callers run
codegraph callees parse_block_body
```

详见 [CLAUDE.md](CLAUDE.md) "Agent 工具链"节。

### 分支与 commit

- 分支：`feature/功能描述`、`fix/问题描述`、`chore/任务描述`
- Commit：中文简述，例 `feat: 添加存档系统`、`fix: 修复选项无法跳转的bug`
- 当前活跃分支：`cursor/setup-issues-v0-vertical-slices`（领先 remote 22+ commits）

## 许可

MIT（见 [pyproject.toml](pyproject.toml)）
