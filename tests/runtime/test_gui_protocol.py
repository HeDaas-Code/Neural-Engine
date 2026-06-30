"""v0-issue-18 GUI CLI 占位测试。

按 issue #41 路径 B（CLI 占位，不依赖 PyQt6）实现 main 事件分发。
"""
import io
import sys
from contextlib import redirect_stdout


import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")


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


# 1. import 可走
def test_main_imports_successfully():
    from runtime.gui.main import main
    assert callable(main)


# 2. text 事件
def test_main_dispatches_text_event():
    from runtime.gui.main import main
    from core.engine.protocol import TextEvt
    bus = FakeBus(events=[TextEvt(content="雨夜。", style="narration")])
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(bus=bus)
    assert rc == 0
    out = buf.getvalue()
    assert "[text] 雨夜。" in out


# 3. prompt_input 事件
def test_main_dispatches_prompt_input_and_sends_user_input_cmd(monkeypatch):
    from runtime.gui.main import main
    from core.engine.protocol import PromptInputEvt, UserInputCmd
    bus = FakeBus(events=[PromptInputEvt(var="p_mood"), None])  # None 触发退出
    monkeypatch.setattr("builtins.input", lambda: "平静")
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(bus=bus)
    assert rc == 0
    # 推送了 UserInputCmd
    assert len(bus.put_cmd_calls) == 1
    assert isinstance(bus.put_cmd_calls[0], UserInputCmd)
    assert bus.put_cmd_calls[0].value == "平静"


# 4. chapter_end 事件
def test_main_dispatches_chapter_end_and_returns_0():
    from runtime.gui.main import main
    from core.engine.protocol import ChapterEndEvt
    bus = FakeBus(events=[ChapterEndEvt()])
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(bus=bus)
    assert rc == 0
    assert "[chapter end]" in buf.getvalue()


# 5. route 事件
def test_main_dispatches_route_and_returns_0():
    from runtime.gui.main import main
    from core.engine.protocol import RouteEvt
    bus = FakeBus(events=[RouteEvt(target="chapter02")])
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(bus=bus)
    assert rc == 0
    assert "[route → chapter02]" in buf.getvalue()


# 6. decorator / log 静默
def test_main_ignores_decorator_and_log():
    from runtime.gui.main import main
    from core.engine.protocol import DecoratorEvt, LogEvt, ChapterEndEvt
    bus = FakeBus(events=[
        DecoratorEvt(name="style", args=["bgm:rain.mp3"]),
        LogEvt(level="info", message="node if stubbed"),
        ChapterEndEvt(),
    ])
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(bus=bus)
    assert rc == 0
    out = buf.getvalue()
    assert "style" not in out
    assert "node if stubbed" not in out
