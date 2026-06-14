## Parent

#22（PRD-0001 父 issue）

## What to build

`src/core/engine/main.py` 进程入口：装配 EngineBus + 加载章节 + 命令循环 + GUI 子进程 spawn。

API：
- `def main(chapter_path: str) -> int` —— **同步阻塞**主函数
- `if __name__ == "__main__": sys.exit(main(sys.argv[1]))` —— CLI 入口 `python -m core.engine.main chapters/chapter01.md`

行为约定：
- 启动时**先** spawn GUI 子进程：`subprocess.Popen([sys.executable, "-m", "runtime.gui.main"])`（**v0 阶段**：`runtime.gui.main` 可能不存在，留给 v0-issue-18——本 issue 用 `try/except FileNotFoundError` 容错，**仅**打 `LogEvt(level="warning", message="GUI not available, running headless")`）
- 创建 `EngineBus(use_multiprocessing=True)`
- 加载章节：`pathlib.Path(chapter_path).read_text(encoding="utf-8")` → `extract_neon_blocks` → 每块走 v0-issue-7..12 全管线 → `Story`
- 构造 `Executor(story, bus_sink=bus)`
- 主循环：
  1. `Executor.run()` 启动（**真** EngineBus 路径：阻塞在 `node in` 时 `bus.get_cmd()` 等用户输入）
  2. `executor.run()` 跨进程时**必须**真阻塞——v0-issue-14 的 `In` 节点实现需要：广播 `PromptInputEvt` 后 `bus.get_cmd()` 阻塞直到收到 `UserInputCmd`（**v0-issue-14 留 NotImplementedError**——本 issue 替换为真实现：用 `EngineBus.get_cmd`）
  3. 收到 `ShutdownCmd` → 退出 0
  4. 异常 → 广播 `LogEvt(level="error", ...)` + 退出 1
- 关闭 GUI 子进程（`proc.terminate()` + `proc.wait(timeout=2)`）
- 关闭 bus（`bus.close()`）

约定：
- **不**做 daemon 化 / PID 文件 / 配置文件 / 日志文件——v0 阶段最小可工作
- `runtime.gui.main` 不存在时**降级**到 headless：所有 `put_evt` 走 `bus`，但 `get_cmd` 用 `MemoryInputSink`（**v0-issue-14 的输入 sink 通过命令行 `--input-file` 提供 JSON 序列**——v0 阶段**简化为**：`stdin` 读一行算一次 `UserInputCmd.value`）

测试策略：
- 本 issue **不**写 e2e 测试——留给 v0-issue-19 fixture
- 本 issue **写** unit test：`main` 函数被 import 后可调（不 spawn 进程）；覆盖"加载章节失败" / "GUI 不可用降级" 两个错误路径

## Acceptance criteria

- [ ] `python -m core.engine.main` import 路径可走（`python -c "from core.engine.main import main; ..."` 成功）
- [ ] `python -m core.engine.main chapters/chapter01.md` 至少能启动（无 chapter01 时**报错退出 1**）——fixture 由 v0-issue-19 落地
- [ ] `tests/core/test_main_entry.py` 覆盖：
  - `main("nonexistent.md")` → exit 1 + LogEvt error
  - `main("/tmp/empty.md")` → exit 0 + headless 路径走通
- [ ] `python -m pytest tests/` 全绿

## Blocked by

- #23（v0-issue-1 仓库骨架）
- #24（v0-issue-2 AST 节点 dataclass，`Story` 来自那里）
- #25（v0-issue-3 命令 schema，`ShutdownCmd`/`UserInputCmd` 来自那里）
- #26（v0-issue-4 事件 schema，`LogEvt` 来自那里）
- #27（v0-issue-5 EngineBus）
- #28（v0-issue-6 neon 围栏）
- #29（v0-issue-7 块级骨架）
- #30（v0-issue-8 元数据区）
- #31（v0-issue-9 next 归一）
- #32（v0-issue-10 块内语句）
- #33（v0-issue-11 node if 解析）
- #34（v0-issue-12 修饰器解析）
- #37（v0-issue-14 核心节点执行）
- #38（v0-issue-15 修饰器执行）
- #39（v0-issue-16 if 打桩 + 路由）
