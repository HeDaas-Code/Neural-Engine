# 20 · 三上下文架构

> **TL;DR**：core / editor / runtime 三个上下文，**v0 只动 core + runtime 占位**；editor 留给 v2+。

## 上下文矩阵

| ID | 路径 | 职责 | v0 状态 |
| --- | --- | --- | --- |
| `core` | `src/core/` | 解析器 / 执行器 / AST / 协议 / 总线 / 修饰器 | **实现中**（v0-issue-1~17）|
| `editor` | `src/editor/` | 剧情编辑器 / 角色管理 / 可视化节点图 | **空**（仅 CONTEXT.md）|
| `runtime` | `src/runtime/` | GUI 进程 / 跨平台渲染 / 存档 | **占位**（v0-issue-18）|

上下文规则见 [[raw-docs/CONTEXT-MAP.md]] + [[raw-docs/domain.md]]：每个上下文有自己的术语表（`CONTEXT.md`）、自己的 ADR、跨上下文决策查 `docs/adr/`。

## v0 包结构（v0-issue-1）

包**物理目录**在 `src/` 下（如 `src/core/engine/`），但**导入路径**不带 `src.` 前缀——`pyproject.toml` 配 `pythonpath = ["src"]` 后 import 路径是 `core.engine.*`：

```python
from core.engine.ast_nodes import Story, Block, Start, End, ...
from core.engine.protocol import Cmd, Evt
from core.engine.bus import EngineBus
from core.engine.executor import Executor
from core.engine.interpreter import parse_chapter
from core.decorators.style import StyleHandler
from runtime.gui.main import main as gui_main
```

### core 上下文内部布局

```
src/core/
├── __init__.py
├── engine/
│   ├── __init__.py
│   ├── ast_nodes.py       # AST 节点 + 错误类（v0-issue-2 纯数据结构）
│   ├── protocol.py        # Cmd + Evt dataclass（v0-issue-3 + 4）
│   ├── bus.py             # EngineBus 双向 Queue 封装（v0-issue-5）
│   ├── interpreter.py     # neon 解析器（v0-issue-6/7/8/9/10/11/12）
│   ├── executor.py        # GameState + Executor（v0-issue-13/14/15/16）
│   ├── main.py            # core 进程入口（v0-issue-17）
│   └── expr/              # ★ v1 表达式子系统（v1-issue-1 骨架，commit 2a83774）
│       ├── __init__.py    #   公开 API（ExprDispatcher/Translator/CustomExecutor/ExprError）
│       ├── errors.py      #   ExprError / DSLSyntaxError / UnsupportedNodeError
│       ├── builtin_funcs.py # BUILTIN_FUNCS 白名单（9 个函数）
│       ├── translator.py  #   DSL → Python 翻译器（Chinese 关键字 + 简略三元）
│       ├── dispatcher.py  #   三层调度（translator→simpleeval→fallback）
│       ├── custom.py      #   simpleeval 兜底 + 业务侧 register_* 钩子
│       └── README.md      #   子系统说明
└── decorators/
    ├── __init__.py        # 注册表
    └── style.py           # @style handler（v0-issue-15）
```

### runtime 上下文内部布局

```
src/runtime/
├── __init__.py
├── protocol.py            # 从 core re-export（v0-issue-3 acceptance）
└── gui/
    ├── __init__.py
    ├── main.py            # GUI 进程入口（三路径）
    ├── window.py          # 路径 A：QMainWindow
    ├── display.py         # 路径 A：QPlainTextEdit
    └── input.py           # 路径 A：QLineEdit
```

## 三上下文的依赖方向

```
editor ──depends on──> core
runtime ──depends on──> core (协议共享)
core ──零依赖──> editor, runtime
```

**强约束 #1**：core 无 UI 依赖——禁止 `import PyQt6 / tkinter`。这让 core 可在 CLI / 测试 / Web 后端复用。

## v0 实施路径（按 GH issue 编号）

| 阶段 | GH issue (v0-issue) | 输出 | 验证 |
| --- | --- | --- | --- |
| 阶段 0（骨架） | `#23` (v0-issue-1) | 仓库骨架 + pytest 配置 + 包结构 | `pytest --collect-only` |
| 阶段 1（数据结构） | `#24` (v0-issue-2) | `ast_nodes.py` 18 个 dataclass + `ParserError` | `tests/core/test_ast_shapes.py` |
| 阶段 2（协议） | `#25` (v0-issue-3) | `protocol.py` 3 个 Cmd dataclass | `tests/protocol/test_cmd.py` |
| 阶段 3（事件） | `#26` (v0-issue-4) | `protocol.py` 6 个 Evt dataclass | `tests/protocol/test_event.py` |
| 阶段 4（总线） | `#27` (v0-issue-5) | `bus.py` EngineBus | `tests/core/test_engine_bus.py` |
| 阶段 5（解析器） | `#28`~`#34` (v0-issue-6~12) | `interpreter.py` 完整解析 | `tests/parser/` 多文件 |
| 阶段 6（执行器） | `#36`~`#39` (v0-issue-13~16) | `executor.py` + `@style` handler | `tests/executor/` |
| 阶段 7（入口） | `#40` (v0-issue-17) | `core/engine/main.py` 装配 + 命令循环 | `tests/integration/test_core_main.py` |
| 阶段 8（GUI） | `#41` (v0-issue-18) | `runtime/gui/main.py` 三路径 | `tests/runtime/test_gui_protocol.py` |
| 阶段 9（端到端） | `#42` (v0-issue-19) | `chapters/chapter01.md` + fixture | `tests/integration/test_chapter01_e2e.py` |
| 阶段 10（HITL 守护） | `#43` (v0-issue-20) | §11 10 条不变量 pytest + §8 MVP 勾 | `tests/test_mvp_table.py` |
| 阶段 11（HITL 完工） | `#44` (v0-issue-21) | `docs/adr/0002-v0-engine-implementation.md` | 人工 review |

## v1 实施路径（PRD-0002 / ADR-0003，2026-06-15 当前状态）

> **v0 完工后启动 v1**——v1 阶段只动 `core` 上下文（不涉及 GUI / runtime / editor）。**v1-issue-1 骨架已完成**（commit `2a83774`，219/219 测试通过）；**v1-issue-2/3/4 已被骨架 commit 超额完成**；**v1-issue-5/6/7 仍未做**——其中 #6（dispatcher 接入 executor）是 v1 闭环的唯一卡点。

| 阶段 | GH issue (v1-issue) | 输出 | 验证 | 实测 commit |
| --- | --- | --- | --- | --- |
| 阶段 12（v1 骨架） | `#52` (v1-issue-1) | `src/core/engine/expr/` 6 个 .py + 公开 API | `tests/core/test_expr_*.py`（37 用例）| ✅ `2a83774` |
| 阶段 13（translator 真实现） | `#46` (v1-issue-2) | `Chinese 关键字` + `keyword_table` | `test_expr_translator.py`（11 用例）| ✅ 骨架 commit 已含（超额）|
| 阶段 14（custom 真实现） | `#47` (v1-issue-3) | `register_function` / `register_evaluator` 完整 | `test_expr_custom.py`（8 用例）| ✅ 骨架 commit 已含（超额）|
| 阶段 15（dispatcher 真实现） | `#48` (v1-issue-4) | 三层调度 + 错误捕获 | `test_expr_dispatcher.py`（10 用例）| ✅ 骨架 commit 已含（超额）|
| 阶段 16（AST 扩 kind） | `#49` (v1-issue-5) | `If.cond` 加 `bool_expr` / `range` 两种 kind | AST 单测 | ❌ OPEN 未做 |
| 阶段 17（executor 接入） | `#50` (v1-issue-6) | `executor._execute_if` 按 kind 分流：`var` 走 v0 / `bool_expr` 走 dispatcher.eval_bool / `range` 走 `lo<=v<=hi` | `test_executor_if.py` 真分支 | ❌ **OPEN 未做（v1 卡点）**|
| 阶段 18（端到端） | `#51` (v1-issue-7) | `chapter01.md` `node if p_pick [...]` 真求值 + `tests/core/test_executor_if.py` 改名 `test_*_eval_*` + 移除 `_stub_*` | `tests/integration/test_chapter01_e2e.py` 真分支 | ❌ OPEN 未做 |
| 阶段 19（HITL 完工） | TBD（v1-issue-8）| `docs/adr/0004-v1-expression-implementation.md` + audit | 人工 review | ❌ OPEN |

**v1 实施关键观察**：
- **0 偏差**——v1-issue-1 commit 对照 ADR-0003 §3 全部 14 个接口签名 + 错误类继承，**完全符合 spec**（v0 4 偏差不同——v1 实施更克制）。详见 [[../30-protocol/implementation-deviations#v1-issue-1-偏差审计-0-偏差]]。
- **超额完成**——v1-issue-2/3/4 的真实现已在 v1-issue-1 骨架 commit 内一并落地，**spec 的工作量被压缩到 1 个 commit**。
- **唯一卡点**——`executor._execute_if` 没动（v1-issue-6，GH #50）。`git diff 1a76382..HEAD -- src/core/engine/executor.py` **0 行变化**（`executor.py:227` 仍 `chosen = if_node.branches[0]`）。预计 ~30 行 executor.py 改动 + ~50 行 test 改名 = 1-2 小时即可 v1 闭环。

## 三路径 GUI 决策（v0-issue-18）

实施 agent 读 `importlib.util.find_spec("PyQt6")` 决定：

- **路径 A**：装了 PyQt6 → Qt 窗口（`QMainWindow` + `QPlainTextEdit` + `QLineEdit`）
- **路径 B**（默认）：没装 PyQt6 → CLI 占位（`print(事件) + input()`）
- **路径 C**：CI / pytest → 不 import GUI，只验证总线协议层

**事件分发约定**（路径 A B 共用）：
- `text` → display.append_text
- `prompt_input` → display 提示 + 激活 input
- `decorator` → 静默忽略（v0 不真渲染）
- `route` → display log "[route → chapter02]"
- `chapter_end` → display.append_text + 退出
- `log` → 静默忽略

→ 相关：[[ast-nodes]] / [[state-machine]] / [[multi-process]] / [[../30-protocol/messages]] / [[../40-issues/dependency-graph]]