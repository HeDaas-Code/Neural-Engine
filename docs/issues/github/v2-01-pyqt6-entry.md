## Parent

PDR：[`docs/pdr/phase3-v2p0.md`](../../pdr/phase3-v2p0.md) §5.1（PyQt6 GUI）
Issue 列表：[`docs/issues/phase3-v2p0.md`](../../issues/phase3-v2p0.md) V2-01
关联 EP：EP-03（`EventSink` Protocol）+ EP-05（`_try_spawn_gui`）
关联决策：D3（PyQt6 fallback）+ D5（不引入 asyncio）

## What to build

在 `src/runtime/gui/main.py` 顶部加 `importlib.util.find_spec("PyQt6")` 工厂分发（**D3 决策**）；新建 `src/runtime/gui/pyqt6_main.py` 实现 QMainWindow + QTextEdit + QLineEdit + QThread 消费 bus（**D5 不引入 asyncio，用 QThread**）。

### 步骤

1. **重写 `src/runtime/gui/main.py:1-15`** 工厂分发：
   ```python
   import importlib.util
   from runtime.gui._cli_main import main as _cli_main  # 提取 v0 CLI 占位

   def main(bus=None) -> int:
       if bus is None:
           from core.engine.bus import EngineBus
           bus = EngineBus(use_multiprocessing=True)
       if importlib.util.find_spec("PyQt6") is not None:
           from runtime.gui.pyqt6_main import main as _pyqt_main
           return _pyqt_main(bus)
       return _cli_main(bus)  # v0 CLI 占位保留
   ```

2. **新建 `src/runtime/gui/_cli_main.py`** —— 提取 v0 CLI 占位主循环（原 `main.py:16-55`）

3. **新建 `src/runtime/gui/pyqt6_main.py`**：
   - `QApplication` + `MainWindow`（标题 "Neural Engine"）
   - `DisplayPanel(QTextEdit)` 文本显示（`append_text(content, style)` 方法）
   - `InputPanel(QLineEdit)` 用户输入（`returnPressed` 信号 → `bus.put_cmd(UserInputCmd(...))`）
   - `QThread` 启动 bus 消费循环：`while True: bus.get_evt()` → 通过 `QMetaObject.invokeMethod` 跨线程更新 UI
   - `PyQt6Sink(QObject) implements EventSink`：
     - `put_evt(evt) → signal emit`（线程安全，`Qt.QueuedConnection`）
     - `get_cmd() → 阻塞消费`（PyQt6 信号槽 + `bus._cmd_q.get()`）

4. **`tests/runtime/test_gui_pyqt6.py` 新建**（mock 测试）：
   - `test_pyqt6_sink_put_evt_emits_signal`
   - `test_pyqt6_sink_get_cmd_blocks_on_queue`
   - `test_pyqt6_sink_close_drains_queue`
   - `test_pyqt6_not_installed_falls_back_to_cli`（mock `find_spec` 返回 None）

5. **不动 v0/v1 解析器/执行器/表达式核心**——本 issue 仅新建 GUI 模块

## Acceptance criteria

- [ ] `runtime/gui/main.py:1-15` 工厂分发落地（`find_spec("PyQt6")` + 分发）
- [ ] `src/runtime/gui/_cli_main.py` 提取 v0 CLI 占位（原 26-55 行）
- [ ] `src/runtime/gui/pyqt6_main.py` 新建（QMainWindow + QTextEdit + QLineEdit + QThread + PyQt6Sink）
- [ ] `tests/runtime/test_gui_pyqt6.py` 新建，至少 4 个测试覆盖 PyQt6Sink + 降级路径
- [ ] PyQt6 装上时：`from runtime.gui.pyqt6_main import MainWindow` 可 import（手动验证，**不**在 CI）
- [ ] PyQt6 没装时：D3 降级路径走 CLI 占位（CI 跑测时验证）
- [ ] 现有 211+ tests 维持 + 5+ 新测试（`pytest tests/` 全绿）
- [ ] 现有 `tests/runtime/test_gui_protocol.py` 不破
- [ ] 现有 `src/core/engine/main.py` 不动（`_try_spawn_gui` 保持 Popen 启动方式）
- [ ] v0/v1 解析器/执行器/表达式核心不动

## Blocked by

无（Window 1 · 3 人并行启动）

## 关联依赖

- 阻塞 V2-02（装饰器渲染，依赖本 issue）
- 阻塞 V2-03（PyQt6 测试，依赖本 issue + V2-02）
