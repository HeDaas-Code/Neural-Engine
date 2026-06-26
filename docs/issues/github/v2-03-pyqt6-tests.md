## Parent

PDR：[`docs/pdr/phase3-v2p0.md`](../../pdr/phase3-v2p0.md) §5.1.3（PyQt6 验收标准）
Issue 列表：[`docs/issues/phase3-v2p0.md`](../../issues/phase3-v2p0.md) V2-03
关联 EP：EP-03（`EventSink` Protocol）

## What to build

用 `MemoryEventSink` / `queue.Queue` mock 测试 `PyQt6Sink` 包装 EngineBus 收发正常；CI 跑测时 PyQt6 不在 PATH 走降级路径；实际 QMainWindow 不在 CI 测（人工手动验证清单写入 `docs/v2-gui-manual-verify.md`）。

### 步骤

1. **`tests/runtime/test_gui_pyqt6.py` 新建**：
   - `test_pyqt6_sink_put_evt_emits_signal` —— `PyQt6Sink.put_evt(TextEvt("hello"))` → `text_received` signal 收到
   - `test_pyqt6_sink_get_cmd_blocks_on_queue` —— `PyQt6Sink.get_cmd()` 阻塞消费 `UserInputCmd`
   - `test_pyqt6_sink_close_drains_queue` —— `PyQt6Sink.close()` 排空残留（与 `EngineBus.close()` 对齐）
   - `test_pyqt6_sink_decorator_dispatch` —— `DecoratorEvt(kind="call")` → `dispatch` 调用
   - `test_pyqt6_sink_decorator_stop_no_dispatch` —— `DecoratorEvt(kind="stop")` → `dispatch` 不调用
   - `test_pyqt6_not_installed_falls_back_to_cli` —— mock `importlib.util.find_spec("PyQt6")` 返回 None，验证走 CLI 占位
   - `test_pyqt6_installed_uses_pyqt6_main` —— mock `find_spec` 返回 `MagicMock`，验证走 pyqt6_main 路径

2. **CI 路径**：
   - `pytest tests/runtime/test_gui_pyqt6.py` 全绿
   - **不**实际启动 QApplication（mock QApplication / QMainWindow / QLineEdit）
   - 现有 `tests/runtime/test_gui_protocol.py` 不破

3. **`docs/v2-gui-manual-verify.md` 新建**（人工手动验证清单）：
   - [ ] 装 PyQt6 后 `python -m runtime.gui.main` 启动 QMainWindow 窗口
   - [ ] TextEvt 渲染到 DisplayPanel（QLineEdit 显示文字）
   - [ ] QLineEdit 回车推 UserInputCmd（Engine 收到）
   - [ ] 装饰器 `@style text:rgb:red` 在窗口中可见
   - [ ] 装饰器 `@style bgm:rain.mp3` 不播放（v3+ 落地）
   - [ ] 关闭窗口优雅退出（ShutdownCmd）

4. **测试覆盖**：`PyQt6Sink` 类 100% 行覆盖（不实际渲染）

## Acceptance criteria

- [ ] `tests/runtime/test_gui_pyqt6.py` 新建，至少 7 个测试（PyQt6Sink 5 个 + 降级路径 2 个）
- [ ] 所有测试用 mock（**不**实际启动 QApplication）
- [ ] `pytest tests/runtime/test_gui_pyqt6.py` 全绿
- [ ] 现有 211+ tests 维持 + 7+ 新测试
- [ ] `docs/v2-gui-manual-verify.md` 新建（人工验证清单）
- [ ] 现有 `tests/runtime/test_gui_protocol.py` 不破
- [ ] CI 路径：PyQt6 不在 PATH 时降级路径走通

## Blocked by

- V2-01（PyQt6 入口切换，#72）
- V2-02（装饰器渲染，#73）

## 关联依赖

- 不阻塞其他 issue
