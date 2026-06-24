# Neural Engine

> 中文文字游戏引擎 · v1 表达式子系统已完工

## 状态

| 维度 | 状态 | 证据 |
|---|---|---|
| v0 基础版引擎 | ✅ **已闭环** | v0-issue-1~19 全部落地 |
| v1 表达式重构 | ✅ **已闭环** | PR #66 已合并，ADR-0004 全部完成 |
| pytest | ✅ **241/244 PASSED**（3 个 POSIX-only grep 测试在 Windows 失败，非代码 bug） | `python3 -m pytest tests/ -q` |
| §8 MVP 表 | ✅ **18/18** | `tests/test_mvp_table.py` |
| §11 关键不变量 | ✅ **10/10（核心）** + 3 个 POSIX-only 守护（Windows 失败） | `tests/test_invariants.py` |
| v0 端到端路径 | ✅ **in → echo → end** | `tests/integration/test_echo_path.py` |
| v1 端到端路径 | ✅ **expr if + echo 拼接 + ←/→** | `tests/integration/test_v1_e2e.py` |
| GitHub Issues | ✅ **全部关闭** | #1~#66 全部 closed |
| 实现偏差登记 | v0: 4 条 · v1: 6 条（**D1/D2/D4/D5 已修复 2026-06-24，剩余 D3/D6 远期**） | [ADR-0002 §5](docs/adr/0002-v0-engine-implementation.md) · [ADR-0004 附录](docs/adr/0004-appendix-deviations.md) |

> v1 阶段边界：translator 砍除 + 表达式真求值 + ←/→ 箭头对齐 + echo 拼接 + executor 真分支。PyQt6 GUI 和 LLM 装饰器推迟到 v2。

## 这是什么

一个面向中文创作者的文字游戏引擎。剧情写作者用 Markdown + 内嵌的 ` ```neon ` DSL 描述剧情节点，引擎进程解析并执行节点、广播事件给 GUI 进程，GUI 渲染文本 / 接收玩家输入。

**核心设计**：
- 剧情格式 = Markdown + `neon` 代码块
- 节点 = `node start` ~ `node end` 的连续语句
- 控制流 = 隐藏变量 `NEXT` 引用 `next` 声明表项
- 跨块路由 = `id:endX:chapterYY` 块执行到 `node end` 时广播 `RouteEvt`
- 进程模型 = Engine（core 进程） + GUI（runtime 进程）双向 `multiprocessing.Queue`
- 修饰器 = `@style key:val, ...` 块级作用域、last-wins
- 表达式 = 原生 Python 语法，simpleeval 沙箱求值（v1）

## v1 新增能力

| 特性 | 语法示例 | 说明 |
|---|---|---|
| 表达式 if 真求值 | `node if pick == 1 [t_a, t_b]` | simpleeval 求值，True→branches[0], False→branches[1] |
| 多元表达式 if | `node if pick == 1 [1:t_a, 2:t_b]` | 求值结果按值匹配分支 |
| echo 拼接 | `node echo P-text + 是吗?我知道了.` | 变量与文本字面量用 ` + ` 拼接 |
| ← 箭头 | `n2 ← next : cn2` | next 声明新箭头符号（兼容旧 `<-`） |
| → 箭头 | `node in → pick` | in 赋值新箭头符号（兼容旧 `->`） |
| 原生 Python 表达式 | `tall == 1 and age >= 18` | 砍除 translator 中文关键字层 |

## 快速跑通

### 安装

```bash
python3 -m pip install -e .          # 安装包（含 simpleeval 依赖）
# 或：python3 -m pip install -r requirements-dev.txt
```

### 跑测试

```bash
python3 -m pytest tests/ -q
# 期望：211 passed
```

### 跑引擎

```bash
# v0 fixture（向后兼容验证）
python3 -m core.engine.main chapters/chapter01.md

# v1 fixture（表达式 + 新箭头）
python3 -m core.engine.main chapters/chapter01_v1.md
```

GUI 进程由 `core.engine.main` 自动 spawn；GUI 不可用时降级为 headless 模式（日志写 `GUI not available, running headless`）。

### 跑端到端测试

```bash
# v0 路径
python3 -m pytest tests/integration/test_echo_path.py -v

# v1 路径（表达式 if + echo 拼接 + 箭头）
python3 -m pytest tests/integration/test_v1_e2e.py -v
```

## 架构

### 双进程

```text
┌────────────────────┐    EngineBus      ┌────────────────────┐
│  core/engine/main  │ ◀──JSON dict──▶  │  runtime/gui/main  │
│  - interpreter.py  │  cmd_q / evt_q    │  (v0: CLI 占位)    │
│  - executor.py     │  multiprocessing  │  (v2: PyQt6 路径 A)│
│  - bus.py          │  .Queue           │                    │
│  - expr/           │                   │                    │
└────────────────────┘                   └────────────────────┘
        │                                         │
        ▼                                         ▼
  chapters/*.md 章节                  文本 / 输入框 / 富文本渲染
```

### 核心模块

| 模块 | 职责 | 入口符号 |
|---|---|---|
| `ast_nodes.py` | 17 AST 节点 + 3 sentinels + `ParserError` | `Story`, `Block`, `Text`, `In`, `Echo`, `If`, `Branch`, `NextDecl` |
| `protocol.py` | 进程协议：3 Cmd + 6 Evt | `LoadChapterCmd`, `TextEvt`, `PromptInputEvt`, `RouteEvt`... |
| `bus.py` | 双向 Queue + JSON 序列化 | `EngineBus` |
| `interpreter.py` | 7 段解析流水线 | `extract_neon_blocks`, `parse_block_skeleton`, `parse_block_meta`, `parse_next_decls`, `parse_block_body`, `parse_if_stmt`, `parse_decorator` |
| `executor.py` | 节点调度 + 修饰器 + if 真求值 | `Executor`, `GameState`, `EventSink` |
| `main.py` | 进程入口：装配 + 加载 + GUI spawn | `main()` |
| `expr/dispatcher.py` | 表达式求值：simpleeval → fallback | `ExprDispatcher` |
| `expr/custom.py` | fallback 执行器 + 业务扩展钩子 | `CustomExecutor` |
| `expr/builtin_funcs.py` | 内置函数白名单 | `BUILTIN_FUNCS` |
| `expr/errors.py` | 表达式错误类 | `ExprError` |
| `runtime/gui/main.py` | GUI 入口（v0 CLI 占位） | `main()` |

### 表达式调度链（v1）

```
ExprDispatcher.eval(expr)
    │
    ├─ 1. simpleeval.eval(expr)  ← 原生 Python 语法求值
    │      names = state.vars    ← 变量注入
    │      functions = BUILTIN_FUNCS + custom.functions
    │
    └─ 2. fallback → CustomExecutor.eval_fallback(expr, vars)
           正则匹配自定义 handler
           无 handler → ExprError
```

## 项目结构

```
.
├── src/
│   ├── core/
│   │   ├── decorators/              # 修饰器实现（v0 占位）
│   │   └── engine/
│   │       ├── ast_nodes.py         # AST dataclass
│   │       ├── bus.py               # EngineBus
│   │       ├── executor.py          # Executor + GameState + Sinks
│   │       ├── interpreter.py       # 7 段解析流水线
│   │       ├── main.py              # core 进程入口
│   │       ├── protocol.py          # Cmd / Evt schema
│   │       └── expr/                # v1 表达式子系统
│   │           ├── dispatcher.py    # simpleeval → fallback 调度
│   │           ├── custom.py        # fallback + 扩展钩子
│   │           ├── builtin_funcs.py # 内置函数白名单
│   │           ├── errors.py        # ExprError
│   │           └── __init__.py
│   ├── editor/                      # 剧情编辑器（未实现）
│   └── runtime/
│       └── gui/                     # GUI 进程（v0 CLI / v2 PyQt6）
├── tests/
│   ├── core/                        # 单元测试（18 文件）
│   ├── integration/                 # 端到端测试（3 文件）
│   ├── runtime/                     # GUI 协议测试
│   ├── test_invariants.py           # §11 10 条不变量守护
│   ├── test_mvp_table.py            # §8 18 条 MVP 表
│   └── test_skeleton_smoke.py       # 包导入冒烟
├── chapters/
│   ├── chapter01.md                 # v0 官方 fixture
│   └── chapter01_v1.md              # v1 表达式 fixture
├── docs/
│   ├── adr/
│   │   ├── 0001-v0-baseline-script-spec.md       # v0 规范
│   │   ├── 0002-v0-engine-implementation.md      # v0 完工 + 偏差
│   │   ├── 0003-v1-expression-subsystem.md       # v1 表达式设计
│   │   ├── 0004-v1-refactor-design.md            # v1 重构设计
│   │   └── 0004-appendix-deviations.md           # v1 偏差登记
│   ├── prds/
│   ├── audit/
│   └── agents/
├── 工作Wiki/                         # Obsidian vault
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
| v0 脚本规范 | [ADR-0001](docs/adr/0001-v0-baseline-script-spec.md) |
| v0 完工 + 4 条偏差 | [ADR-0002](docs/adr/0002-v0-engine-implementation.md) |
| v1 表达式子系统设计 | [ADR-0003](docs/adr/0003-v1-expression-subsystem.md) |
| v1 重构设计（对齐 neon 规范） | [ADR-0004](docs/adr/0004-v1-refactor-design.md) |
| v1 偏差登记（6 条） | [ADR-0004 附录](docs/adr/0004-appendix-deviations.md) |
| v1 独立审计报告 | [docs/audit/v1-independent-audit-hanice.md](docs/audit/v1-independent-audit-hanice.md) |
| 下一步功能路线图 | [docs/ROADMAP.md](docs/ROADMAP.md) |
| Agent 协作约定 | [CLAUDE.md](CLAUDE.md) |
| 多上下文域文档 | [CONTEXT-MAP.md](CONTEXT-MAP.md) |

## 开发

### 跑单测

```bash
# 全部
python3 -m pytest tests/ -q

# 单文件
python3 -m pytest tests/core/test_executor_if.py -v

# v1 端到端
python3 -m pytest tests/integration/test_v1_e2e.py -v

# 不变量守护
python3 -m pytest tests/test_invariants.py -v
```

### 分支与 commit

- 分支：`feature/功能描述`、`fix/问题描述`、`chore/任务描述`
- Commit：中文简述，例 `feat: 添加存档系统`、`fix: 修复选项无法跳转的bug`

## 许可

MIT（见 [pyproject.toml](pyproject.toml)）
