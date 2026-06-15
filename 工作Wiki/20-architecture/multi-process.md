# 20 · 多进程架构

> **TL;DR**：core 和 GUI 是**两个独立 Python 进程**，通过 multiprocessing.Queue 双向通信——core 永不直接调 UI。

## 进程拓扑

```
┌─────────────────────────┐         ┌─────────────────────────┐
│   core 进程              │         │   runtime 进程           │
│  (core/engine/main.py)  │         │  (runtime/gui/main.py)   │
│                         │         │                         │
│  interpreter ── Story   │         │  path A: MainWindow     │
│  executor   ── run()    │         │   ├─ DisplayPanel       │
│  protocol.to_dict/from_  │         │   └─ InputPanel         │
│                         │         │  path B: CLI print/input│
└────────────┬────────────┘         └──────────┬──────────────┘
             │                                │
       cmd_q  │  GUI → Engine (Cmd)    evt_q  │
       ◀──────┼────────────────────────────────┘
             │                                │
       evt_q │  Engine → GUI (Evt)     cmd_q  │
       ──────┼────────────────────────────────▶
             │                                │
             └──────── multiprocessing.Queue ┘
```

每个方向一个 Queue；EngineBus 封装四个方法 `put_cmd / get_cmd / put_evt / get_evt`。

## 进程边界规则（强约束 #5, #7）

1. **禁止共享内存 / 全局变量 / 文件锁**——只走 Queue
2. **禁止 dataclass 直接跨进程传输**——`pickle` 走的是 Python 对象语义，跨语言无法消费；统一 `json.dumps` + `protocol.to_dict / from_dict`
3. **错误传播**：`from_dict` 抛 `ValueError` 时，`bus.get_*` **直接传播** ValueError——v0 决策**不**包装成 `ProtocolError`（v0-issue-3 / v0-issue-4 / v0-issue-5 三个 spec 一致决定）

## 进程启动序列（v0-issue-17）

```python
# core/engine/main.py  装配流程（v0-issue-17 决策）
def main():
    cmd_q = multiprocessing.Queue()   # GUI → Engine
    evt_q = multiprocessing.Queue()   # Engine → GUI
    bus = EngineBus(cmd_q, evt_q)

    # 启 GUI 子进程（v0-issue-17 acceptance）
    gui_proc = multiprocessing.Process(
        target=gui_main,
        args=(cmd_q, evt_q),          # 把 Queue 反向交给 GUI
    )
    gui_proc.start()

    # Engine 主循环
    cmd = bus.get_cmd()               # 阻塞等首个 Cmd
    if isinstance(cmd, LoadChapterCmd):
        story = parse_chapter(cmd.path)
        Executor(story, bus).run()
    elif isinstance(cmd, ShutdownCmd):
        sys.exit(0)
```

GUI 端（v0-issue-18 路径 B）：

```python
# runtime/gui/main.py  CLI fallback
def main(cmd_q, evt_q):
    bus = EngineBus(cmd_q, evt_q)     # 视角反向
    # 启动后立即发 LoadChapterCmd
    cmd_q.put(LoadChapterCmd(path="chapters/chapter01.md"))

    # 事件分发循环
    while True:
        evt = bus.get_evt()
        if isinstance(evt, TextEvt):
            print(f"[text] {evt.content}")
        elif isinstance(evt, PromptInputEvt):
            print(f"[input] {evt.var}")
            user_input = input("> ")
            cmd_q.put(UserInputCmd(value=user_input))
        elif isinstance(evt, ChapterEndEvt):
            print("[chapter end]")
            break
        elif isinstance(evt, ShutdownCmd):
            break
        # decorator / log / route → 静默忽略
```

## 协议稳定性（软约束）

> 消息 schema 一旦发布**不向后兼容地修改**；新增字段用可选键。

v0-issue-3 / v0-issue-4 敲定的 3 Cmd + 6 Evt schema 是**契约**——后续 v0-issue 不能改字段名，只能加可选字段。

## v0 不做的进程特性

| 特性 | 原因 |
| --- | --- |
| 心跳 | v0 进程生命周期对齐章节（章节结束 GUI 也退）|
| 重连 | v0 单章节运行，不存在跨章节长连 |
| 反压 | 单章节事件量小，Queue 默认无限缓冲 |
| 安全沙箱 | v0 内部工具不解析外部输入 |

## 与 v0-issue-18 三路径 GUI 集成

**v0-issue-18** 实施时 agent 决定走路径 A/B/C：
- 路径 A（PyQt6 装上）：同进程事件循环，`bus.get_evt()` 跑在 QTimer
- 路径 B（CLI fallback）：同进程，但 `input()` 阻塞同步
- 路径 C（pytest）：不启 GUI 进程，只验证总线层

**`core/engine/main.py` 不关心 GUI 走哪条路径**——它只通过 cmd_q / evt_q 通信。

→ 相关：[[overview]] / [[state-machine]] / [[../30-protocol/bus]] / [[../30-protocol/messages]]

## 引用源

- ADR-0001 §7.1 / §7.2 / §7.5 / §11 #5 #7 —— [[raw-docs/ADR-0001-v0-baseline-script-spec]]
- v0-issue-5 EngineBus —— [[raw-docs/工程笔记/v0-issue-5-bus.md]]
- v0-issue-17 core 进程入口 —— [[raw-docs/工程笔记/v0-issue-17-core-main.md]]
- v0-issue-18 GUI 三路径 —— [[raw-docs/工程笔记/v0-issue-18-gui.md]]
- CONTEXT-core 强约束 —— [[raw-docs/CONTEXT-core.md]]