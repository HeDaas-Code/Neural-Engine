"""v2-skeleton · EP-05 GUI 入口 CLI fallback 测试。

按 PM 派工 + D3 决策（PyQt6 fallback）验证：
- 当 PyQt6 不可用时（`find_spec("PyQt6")` 返回 None），main() 走 v0 CLI 占位主循环
- 当 PyQt6 spec 在但 `runtime.gui.pyqt6_main` 还没建（V2-01 后续任务），main() 降级到 CLI
- 降级路径不抛 ImportError；现有 CLI 行为（print + input + UserInputCmd）保留

约束（来自 PM 派工）：
- 不修改 `runtime/gui/pyqt6_main.py`（留给后续 V2-01 任务）
- 不动现有 `tests/runtime/test_gui_protocol.py`（那是 v0 阶段 CLI 行为基线）

策略：用 `monkeypatch.setattr` mock `importlib.util.find_spec`：
- monkeypatch.setattr("importlib.util.find_spec", lambda name: None)  → 走 CLI
- monkeypatch.setattr("runtime.gui.main.find_spec", ...)             → 同样走 CLI

未来 V2-01 落地 PyQt6 后，会再补 `test_gui_pyqt6.py` 验证 happy path。
"""
import io
import sys
from contextlib import redirect_stdout

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")


# ─── 共享 fake bus（与 test_gui_protocol.py 同款，保证 CLI 行为可观测）───


class FakeBus:
    """测试用 fake bus——记录 put_cmd，喂入 get_evt 序列。"""

    def __init__(self, events: list):
        self._events = list(events)
        self._idx = 0
        self.put_cmd_calls: list = []

    def get_evt(self):
        if self._idx < len(self._events):
            e = self._events[self._idx]
            self._idx += 1
            return e
        return None

    def put_cmd(self, cmd):
        self.put_cmd_calls.append(cmd)

    def close(self):
        pass


def _patch_find_spec_none(monkeypatch, module_path: str = "runtime.gui.main"):
    """把指定模块的 find_spec（绑为模块属性）替换为返回 None 的 lambda。

    关键：必须 patch 模块属性而不是 importlib.util.find_spec 全局，
    否则会破坏同进程内其他测试的 import。
    """
    monkeypatch.setattr(f"{module_path}.find_spec", lambda name: None)


# 1. 无 PyQt6（find_spec=None）时 main() 走 CLI，TextEvt 打印
def test_fallback_no_pyqt6_dispatches_text_event(monkeypatch):
    """find_spec 返回 None → main() 不走 PyQt6 分支；TextEvt 走 CLI print。"""
    _patch_find_spec_none(monkeypatch)
    # 同时确保 pyqt6_main 即使在 sys.modules 中也不会被 import（防 Mock 残留）
    monkeypatch.delitem(sys.modules, "runtime.gui.pyqt6_main", raising=False)

    from runtime.gui.main import main
    from core.engine.protocol import TextEvt

    bus = FakeBus(events=[TextEvt(content="雨夜。", style="narration")])
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(bus=bus)
    assert rc == 0
    assert "[text] 雨夜。" in buf.getvalue()


# 2. 无 PyQt6 + PromptInputEvt → input() + UserInputCmd（验证 CLI 行为完整）
def test_fallback_no_pyqt6_dispatches_prompt_input_and_sends_user_input_cmd(monkeypatch):
    """find_spec=None → PromptInputEvt 走 CLI input；put_cmd(UserInputCmd)。"""
    _patch_find_spec_none(monkeypatch)
    monkeypatch.delitem(sys.modules, "runtime.gui.pyqt6_main", raising=False)
    monkeypatch.setattr("builtins.input", lambda: "平静")

    from runtime.gui.main import main
    from core.engine.protocol import PromptInputEvt, UserInputCmd

    bus = FakeBus(events=[PromptInputEvt(var="p_mood"), None])
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(bus=bus)
    assert rc == 0
    assert len(bus.put_cmd_calls) == 1
    assert isinstance(bus.put_cmd_calls[0], UserInputCmd)
    assert bus.put_cmd_calls[0].value == "平静"


# 3. 无 PyQt6 + RouteEvt → 走 CLI 打印 + bus.close + return 0
def test_fallback_no_pyqt6_dispatches_route_event(monkeypatch):
    """find_spec=None → RouteEvt 走 CLI；打印 [route → target] + return 0。"""
    _patch_find_spec_none(monkeypatch)
    monkeypatch.delitem(sys.modules, "runtime.gui.pyqt6_main", raising=False)

    from runtime.gui.main import main
    from core.engine.protocol import RouteEvt

    bus = FakeBus(events=[RouteEvt(target="chapter02")])
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(bus=bus)
    assert rc == 0
    assert "[route → chapter02]" in buf.getvalue()


# 4. 无 PyQt6 + ChapterEndEvt → 走 CLI
def test_fallback_no_pyqt6_dispatches_chapter_end_event(monkeypatch):
    """find_spec=None → ChapterEndEvt 走 CLI；打印 [chapter end] + return 0。"""
    _patch_find_spec_none(monkeypatch)
    monkeypatch.delitem(sys.modules, "runtime.gui.pyqt6_main", raising=False)

    from runtime.gui.main import main
    from core.engine.protocol import ChapterEndEvt

    bus = FakeBus(events=[ChapterEndEvt()])
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(bus=bus)
    assert rc == 0
    assert "[chapter end]" in buf.getvalue()


# 5. 无 PyQt6 + DecoratorEvt/LogEvt → 走 CLI 静默
def test_fallback_no_pyqt6_silences_decorator_and_log(monkeypatch):
    """find_spec=None → DecoratorEvt/LogEvt 走 CLI 静默（与 v0 行为一致）。"""
    _patch_find_spec_none(monkeypatch)
    monkeypatch.delitem(sys.modules, "runtime.gui.pyqt6_main", raising=False)

    from runtime.gui.main import main
    from core.engine.protocol import DecoratorEvt, LogEvt, ChapterEndEvt

    bus = FakeBus(events=[
        DecoratorEvt(name="style", args=["bgm:rain.mp3"]),
        LogEvt(level="info", message="hello"),
        ChapterEndEvt(),
    ])
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(bus=bus)
    assert rc == 0
    assert "style" not in buf.getvalue()
    assert "hello" not in buf.getvalue()


# 6. PyQt6 spec 在但 pyqt6_main.py 不存在 → 降级到 CLI，不抛 ImportError
def test_fallback_pyqt6_present_but_pyqt6_main_missing(monkeypatch):
    """find_spec 返回 Mock（假装 PyQt6 装了），但 `runtime.gui.pyqt6_main` 模块
    不存在 → main() 必须降级到 CLI 占位，不抛 ImportError/FileNotFoundError。

    这模拟 V2-01 后续任务还没建 pyqt6_main.py 时的中间状态。
    """
    # Mock find_spec 返回非 None（假装 PyQt6 已装）
    monkeypatch.setattr("runtime.gui.main.find_spec", lambda name: object() if name == "PyQt6" else None)
    # 确保 pyqt6_main 不在 sys.modules
    monkeypatch.delitem(sys.modules, "runtime.gui.pyqt6_main", raising=False)

    from runtime.gui.main import main
    from core.engine.protocol import TextEvt

    bus = FakeBus(events=[TextEvt(content="降级。", style="narration")])
    buf = io.StringIO()
    # 关键断言：main() 不抛 ImportError；走 CLI 主循环
    with redirect_stdout(buf):
        rc = main(bus=bus)
    assert rc == 0
    assert "[text] 降级。" in buf.getvalue()


# 7. 暴露 _has_pyqt6 / find_spec 是模块属性（防回归：未来改回全局函数会破 D3）
def test_module_exposes_find_spec_attribute():
    """runtime.gui.main 必须把 find_spec 作为模块属性暴露（用于 monkeypatch）。"""
    from runtime.gui import main as main_module

    assert hasattr(main_module, "find_spec"), (
        "EP-05 要求把 importlib.util.find_spec 暴露为模块属性，"
        "否则测试无法 monkeypatch 切换 PyQt6 探测路径"
    )
    # 默认情况下 find_spec 应是真正的 importlib.util.find_spec（未 mock）
    import importlib.util
    assert main_module.find_spec is importlib.util.find_spec