## Parent

PDR：[`docs/pdr/phase3-v2p0.md`](../../pdr/phase3-v2p0.md) §5.1.2（PyQt6 流程图 + 装饰器运行时钩子）
Issue 列表：[`docs/issues/phase3-v2p0.md`](../../issues/phase3-v2p0.md) V2-02
关联 EP：EP-06（`DecoratorEvt.kind` 扩展）+ EP-08（`src/core/decorators/` 占位）
关联决策：D5（不引入 asyncio）

## What to build

扩展 `DecoratorEvt` 加 `kind: Literal["call", "stop"]` 字段（默认 `"call"`，向后兼容）；新建 `src/core/decorators/style.py` 注册 `@style` 钩子；executor 广播时按 `isinstance(DecoratorCall/Stop)` 区分 kind。

### 步骤

1. **`src/core/engine/protocol.py:151-169` `DecoratorEvt` 扩展**：
   ```python
   @dataclass(frozen=True, slots=True)
   class DecoratorEvt:
       name: str
       args: list[str]
       kind: str = "call"  # v2 新增；"call" | "stop"；默认 "call" 向后兼容

       def to_dict(self) -> dict:
           return {
               "event": "decorator",
               "name": self.name,
               "args": list(self.args),
               "kind": self.kind,
           }

       @classmethod
       def from_dict(cls, d: dict) -> "DecoratorEvt":
           _check_dict(d, "DecoratorEvt")
           return cls(
               name=_require_str(d, "name", "DecoratorEvt"),
               args=_require_str_list(d, "args", "DecoratorEvt"),
               kind=d.get("kind", "call"),  # 旧 dict 无 kind 时默认 "call"
           )
   ```

2. **`src/core/engine/executor.py:240-251` `_emit_decorator` 区分**：
   ```python
   def _emit_decorator(self, deco) -> None:
       if isinstance(deco, DecoratorCall):
           for arg in deco.args:
               if ":" in arg:
                   k, v = arg.split(":", 1)
                   self._deco_state.setdefault(deco.name, {})[k] = v
           self.sink.put_evt(DecoratorEvt(name=deco.name, args=list(deco.args), kind="call"))
       elif isinstance(deco, DecoratorStop):
           if deco.name in self._deco_state:
               self._deco_state[deco.name].pop(deco.key, None)
           self.sink.put_evt(DecoratorEvt(name=deco.name, args=[deco.key], kind="stop"))
   ```

3. **新建 `src/core/decorators/style.py`**（EP-08 落地）：
   ```python
   """@style 装饰器运行时钩子 —— v2 落地（EP-08）。"""
   from __future__ import annotations
   from typing import Callable
   from core.engine.protocol import DecoratorEvt

   _STYLE_HOOKS: dict[str, Callable] = {}

   def register_hook(name: str, fn: Callable) -> None:
       _STYLE_HOOKS[name] = fn

   def dispatch(evt: DecoratorEvt) -> None:
       fn = _STYLE_HOOKS.get(evt.name)
       if fn is None:
           return
       if evt.kind != "call":
           return  # v2 仅处理 call；stop v3+ 落地
       for arg in evt.args:
           if ":" in arg:
               k, v = arg.split(":", 1)
               fn(k, v)  # @style text:rgb:red → fn("text", "rgb:red")
   ```

4. **测试**：
   - `tests/core/test_protocol_evt.py::test_decorator_evt_kind_default` 验证默认 `"call"`
   - `tests/core/test_protocol_evt.py::test_decorator_evt_from_dict_old_compat` 验证旧 dict 无 kind 走默认 `"call"`
   - `tests/core/test_decorator_hooks.py::test_register_and_dispatch` 验证钩子注册 + 派发
   - `tests/core/test_decorator_hooks.py::test_unregistered_hook_silent` 验证未注册钩子静默
   - 现有 `tests/runtime/test_gui_protocol.py::test_main_ignores_decorator_and_log` 不破

5. **G5 推迟**：结构化参数 `[item1,item2,...]`（ADR-0004 §4）v3+ 落地；v2 走"字符串 key/val 解析"路径

## Acceptance criteria

- [ ] `src/core/engine/protocol.py` `DecoratorEvt` 加 `kind: str = "call"` 字段
- [ ] `from_dict` 兼容旧 dict（`d.get("kind", "call")`）
- [ ] `src/core/engine/executor.py:240-251` `_emit_decorator` 区分 call/stop
- [ ] `src/core/decorators/style.py` 新建，含 `register_hook` + `dispatch` + 默认 `@style` 钩子
- [ ] `tests/core/test_protocol_evt.py` 加 2 个 kind 相关测试
- [ ] `tests/core/test_decorator_hooks.py` 新建，至少 2 个测试
- [ ] 现有 `tests/runtime/test_gui_protocol.py` 不破
- [ ] 现有 211+ tests 维持 + 4+ 新测试
- [ ] v0/v1 解析器/执行器/表达式核心不动（仅扩 `DecoratorEvt` 字段 + 新建 `core/decorators/style.py`）

## Blocked by

- V2-01（PyQt6 入口切换，#72）—— 装饰器钩子依赖 V2-01 定义的 `PyQt6Sink.apply_style` 钩子签名

## 关联依赖

- 阻塞 V2-03（PyQt6 测试，依赖本 issue + V2-01）
