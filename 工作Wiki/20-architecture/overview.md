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

按 v0-issue-1 决策，包**不带 `src.` 前缀**——`pyproject.toml` 配置 `pythonpath = ["src"]` 后：

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
│   └── main.py            # core 进程入口（v0-issue-17）
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