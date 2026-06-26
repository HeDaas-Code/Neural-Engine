## Parent

PDR：[`docs/pdr/phase3-v2p0.md`](../../pdr/phase3-v2p0.md) §5.3（存档/读档）
Issue 列表：[`docs/issues/phase3-v2p0.md`](../../issues/phase3-v2p0.md) V2-07
关联 EP：EP-07（`src/runtime/` 占位）+ EP-11（IPC 协议扩展）
关联决策：D2（JSON 复用 protocol.py）+ D4（`~/.neural-engine/saves/{slot}.json`）

## What to build

在 `src/core/engine/protocol.py` 新增 `SaveCmd/LoadCmd` 数据类 + 注册到 `_CMD_REGISTRY`（**EP-11**）；新建 `src/runtime/save.py`（SaveManager，JSON 文件 + 槽位管理，**D2 复用 + D4 位置**）；`main.py` 加 cmd 循环（v0 简化下 main 不读 cmd_q——v2 改造）。

### 步骤

1. **`src/core/engine/protocol.py:93-97` 新增**（EP-11）：
   ```python
   @dataclass(frozen=True, slots=True)
   class SaveCmd:
       slot: str
       def to_dict(self) -> dict:
           return {"cmd": "save", "slot": self.slot}
       @classmethod
       def from_dict(cls, d: dict) -> "SaveCmd":
           _check_dict(d, "SaveCmd")
           return cls(slot=_require_str(d, "slot", "SaveCmd"))

   @dataclass(frozen=True, slots=True)
   class LoadCmd:
       slot: str
       def to_dict(self) -> dict:
           return {"cmd": "load", "slot": self.slot}
       @classmethod
       def from_dict(cls, d: dict) -> "LoadCmd":
           _check_dict(d, "LoadCmd")
           return cls(slot=_require_str(d, "slot", "LoadCmd"))

   _CMD_REGISTRY["save"] = SaveCmd
   _CMD_REGISTRY["load"] = LoadCmd
   ```

2. **新建 `src/runtime/save.py`**（EP-07 + D4 决策）：
   ```python
   """存档/读档管理（v2 落地）—— D4 决策：~/.neural-engine/saves/{slot}.json。"""
   from __future__ import annotations
   import json
   import re
   from pathlib import Path
   from core.engine.executor import GameState

   _SLOT_PATTERN = re.compile(r"^[\w-]+$")  # 防止路径穿越

   class SaveManager:
       def __init__(self, save_dir: Path = Path.home() / ".neural-engine" / "saves"):
           self.save_dir = save_dir
           self.save_dir.mkdir(parents=True, exist_ok=True)

       def save(self, slot: str, state: GameState) -> None:
           """存档：state → JSON 文件。"""
           if not _SLOT_PATTERN.match(slot):
               raise ValueError(f"invalid slot name: {slot!r}")
           path = self.save_dir / f"{slot}.json"
           # D2 决策：复用 protocol.py json.dumps + utf-8
           path.write_text(
               json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
               encoding="utf-8",
           )

       def load(self, slot: str) -> GameState:
           """读档：JSON 文件 → state。"""
           if not _SLOT_PATTERN.match(slot):
               raise ValueError(f"invalid slot name: {slot!r}")
           path = self.save_dir / f"{slot}.json"
           data = json.loads(path.read_text(encoding="utf-8"))
           return GameState.from_dict(data)

       def list_slots(self) -> list[str]:
           """列出所有存档槽。"""
           return sorted([p.stem for p in self.save_dir.glob("*.json")])
   ```

3. **`src/core/engine/main.py:67-137` cmd 循环**：
   - v0 简化下 main 不读 cmd_q——v2 改造：在 main 启动 `QThread` 读 `cmd_q`（与 V2-01 PyQt6 集成；CLI 占位走 polling）
   ```python
   import threading
   from core.engine.protocol import SaveCmd, LoadCmd, ShutdownCmd
   from runtime.save import SaveManager

   def main(chapter_path: str) -> int:
       # ... existing code ...
       save_mgr = SaveManager()  # D4 决策
       exe = Executor(story, bus)

       def cmd_loop():
           while True:
               cmd = bus.get_cmd()
               if isinstance(cmd, SaveCmd):
                   save_mgr.save(cmd.slot, exe.state)
               elif isinstance(cmd, LoadCmd):
                   exe.state = save_mgr.load(cmd.slot)
               elif isinstance(cmd, ShutdownCmd):
                   break

       cmd_thread = threading.Thread(target=cmd_loop, daemon=True)
       cmd_thread.start()
       exe.run()  # 同步阻塞
       # ... cleanup ...
   ```
   - 注意：实际集成与 V2-01 PyQt6 cmd 消费统一——本 issue 优先确保 `SaveManager` 工作，cmd 循环详细集成在 V2-09 文档同步阶段收尾

4. **路径校验**：`save()` / `load()` 加 slot 名字校验（仅允许 `[\w-]+`，防止路径穿越）

5. **OQ-2 默认值**：slot 短名 + 序号（`"01"` / `"02"`）—— PM 拍板后可能改

6. **测试**：
   - `tests/runtime/test_save_manager.py::test_save_creates_json_file` —— `save("01", state)` 写入 `~/.neural-engine/saves/01.json`（用 `tmp_path` fixture 注入 `save_dir`）
   - `tests/runtime/test_save_manager.py::test_load_reads_json_file` —— `load("01")` 恢复 `GameState`
   - `tests/runtime/test_save_manager.py::test_round_trip_preserves_state` —— `state → save → load → state` 一致
   - `tests/runtime/test_save_manager.py::test_list_slots` —— `list_slots()` 返回所有槽
   - `tests/runtime/test_save_manager.py::test_invalid_slot_raises` —— `save("../escape", state)` → `ValueError`
   - `tests/core/test_protocol_cmd.py::test_save_cmd_from_dict` —— `SaveCmd.from_dict({"cmd": "save", "slot": "01"})` 正确
   - `tests/core/test_protocol_cmd.py::test_load_cmd_from_dict` —— `LoadCmd.from_dict({"cmd": "load", "slot": "01"})` 正确
   - `tests/integration/test_save_load_e2e.py` —— 游戏中途存档 → 重启 → 读档 → 恢复状态
   - 现有 `tests/core/test_protocol_cmd.py` 跑现有 3 cmd 不破

7. **测试用临时目录**：`tmp_path` fixture 注入 `save_dir`（避免污染 `~/.neural-engine/saves/`）
   - 写入 `conftest.py` fixture: `def save_mgr(tmp_path): return SaveManager(save_dir=tmp_path)`

8. **D4 决策验证**：默认 `save_dir = Path.home() / ".neural-engine" / "saves"` —— 测试时显式覆盖

## Acceptance criteria

- [ ] `src/core/engine/protocol.py:93-97` 新增 `SaveCmd` / `LoadCmd` + 注册到 `_CMD_REGISTRY`
- [ ] `src/runtime/save.py` 新建（`SaveManager` 类 + `save` / `load` / `list_slots` + 路径校验）
- [ ] `src/core/engine/main.py:67-137` cmd 循环（QThread 读 `cmd_q` + 处理 `SaveCmd` / `LoadCmd` / `ShutdownCmd`）
- [ ] `tests/runtime/test_save_manager.py` 新建，至少 5 个测试
- [ ] `tests/core/test_protocol_cmd.py` 加 2 个新测试（`SaveCmd` / `LoadCmd`）
- [ ] `tests/integration/test_save_load_e2e.py` 新建（端到端存档/读档）
- [ ] `conftest.py` 加 `save_mgr` fixture（注入 `tmp_path`）
- [ ] D4 决策验证：默认 `save_dir = Path.home() / ".neural-engine" / "saves"`
- [ ] D2 决策验证：序列化用 `json.dumps + utf-8`（与 `protocol.py` 一致）
- [ ] 路径校验：slot 名仅允许 `[\w-]+`
- [ ] 现有 `tests/core/test_protocol_cmd.py` 现有 3 cmd 不破
- [ ] 现有 211+ tests 维持 + 8+ 新测试

## Blocked by

- V2-06（GameState 序列化，#77）—— `to_dict/from_dict` 必须先有

## 关联依赖

- 阻塞 V2-08（EP-07 runtime 骨架，依赖本 issue 的 `src/runtime/save.py` 已建）
