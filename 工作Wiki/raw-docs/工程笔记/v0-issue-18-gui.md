## Parent

#22（PRD-0001 父 issue）

## What to build

`src/runtime/gui/` 占位 GUI：三种实现路径（**实施 agent 选一种**），目标是"接住 EngineBus 事件流 + 推送 user_input + 不崩"。

**前提**（v0-issue-1 决策）：PyQt6 **可选**——`requirements-gui.txt` 列 PyQt6，**不**强装；CI 跳过 GUI 测试

### 路径 A：PyQt6 三组件（推荐，若 PyQt6 装上）

- `src/runtime/gui/main.py` —— 进程入口；`QApplication` + `MainWindow` + `bus.get_evt()` 主循环
- `src/runtime/gui/window.py` —— `QMainWindow`：上半 `QPlainTextEdit`（display）、下半 `QLineEdit`（input）+ 回车键推送 `UserInputCmd`
- `src/runtime/gui/display.py` —— `DisplayPanel(QPlainTextEdit)`：`append_text(content, style)` 追加文本
- `src/runtime/gui/input.py` —— `InputPanel(QLineEdit)`：回车触发回调
- 事件分发：见下方统一约定

### 路径 B：CLI 占位（PyQt6 不装时 fallback）

- `src/runtime/gui/main.py` —— `print(事件) + input()` 循环
- 接收事件 → `print(f"[text] {content}")` / `print(f"[prompt_input] {var}")` / `print(f"[decorator] {name} {args}")` / `print(f"[route] {target}")` / `print(f"[chapter_end]")` / `print(f"[log] {level}: {message}")`
- 发送 `prompt_input` 事件后阻塞 `input()` → 收到后推送 `UserInputCmd(value=user_input)`
- 收到 `ShutdownCmd` → exit 0

### 路径 C：pytest 自动选（CI / 测试用）

- `tests/runtime/test_gui_dispatch.py` 不 import 任何 GUI 代码，只验证 `bus` 协议层能跨进程跑通（用 v0-issue-19 的 subprocess fixture）

### 实施 agent 决策

- 读 `importlib.util.find_spec("PyQt6")` 判断
- 装了 → 路径 A
- 没装 → 路径 B（**默认推荐**——v0 阶段不强装）
- CI 跑 pytest 时只走路径 C 验证总线层

### 统一事件分发约定（路径 A B 共用）

- `text` → display.append_text
- `prompt_input` → display.append_text("[input requested: var]") + 激活 input
- `decorator` → **静默忽略**（v0 不真渲染）
- `route` → **log 到 display**："[route → chapter02]"
- `chapter_end` → display.append_text("[chapter end]") + 退出
- `log` → **静默忽略**（v0 不暴露给玩家）
- `user_input` 来自 EngineBus 时**不会发生**——`UserInputCmd` 是 GUI→Engine 方向，**v0 阶段** GUI 不会收到 `user_input` cmd

## Acceptance criteria

- [ ] `python -m runtime.gui.main` import 路径可走
- [ ] `tests/runtime/test_gui_protocol.py`（不依赖 PyQt6）覆盖：路径 B（CLI 占位）的事件分发——用 `MemoryEventSink` 模拟 bus，验证 `print()` 输出包含正确事件前缀
- [ ] 路径 A（PyQt6 装上时）：`from runtime.gui.window import MainWindow` 可 import；窗口类**不**在 CI 测
- [ ] 路径 C（pytest）：`tests/runtime/test_cross_process.py` 用真 `multiprocessing.Queue` 验证 GUI 子进程能从 bus 收到事件（v0-issue-19 端到端测试的前置）

## Blocked by

- #23（v0-issue-1 仓库骨架）
- #25（v0-issue-3 命令 schema）
- #26（v0-issue-4 事件 schema）
- #27（v0-issue-5 EngineBus）
