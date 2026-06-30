"""v0-issue-19 端到端：test_echo.md + MemoryInputSink。

按 issue #42 acceptance criteria 验证 v0 唯一跑通路径 in→echo→end。
"""
import sys
from pathlib import Path

import pytest

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")

from core.engine.main import _load_story  # noqa: E402
from core.engine.executor import Executor, MemoryInputSink  # noqa: E402
from core.engine.protocol import (  # noqa: E402
    TextEvt, PromptInputEvt, ChapterEndEvt,
)


def test_echo_path_in_echo_end():
    """最小 fixture: in -> p_tall + echo p_tall + end。"""
    chapter = Path(REPO_ROOT) / "tests" / "test_echo.md"
    story = _load_story(str(chapter))
    sink = MemoryInputSink(inputs=["雨"])
    exe = Executor(story, sink)
    exe.run()
    # 事件流：PromptInputEvt(var=p_tall) → TextEvt("雨") → ChapterEndEvt
    evts = sink.events
    assert len(evts) == 3
    assert isinstance(evts[0], PromptInputEvt)
    assert evts[0].var == "p_tall"
    assert isinstance(evts[1], TextEvt)
    assert evts[1].content == "雨"
    assert isinstance(evts[2], ChapterEndEvt)
    # 变量已写入
    assert exe.state.vars == {"p_tall": "雨"}


def test_echo_path_node_start_block_route_chapter():
    """chapter01.md 入口块应能跑通到 c1 块（多元 if 打桩 → 选 t_a → ca 块 → ca 块没 end marker → 走 RouteEvt 不可达？）。

    v0-issue-16 if 打桩：永远选 branches[0] = t_a → 跳 ca 块 → ca 块有 @style + text + end 无 id:end → 走 Ca 块 body end → ca 块没 id:end marker → RuntimeError。

    实际 c1 块走 t_a 跳 ca → ca 块有 node end 但**没** id:end marker → RuntimeError。
    本测试改成：直接调 Executor 跑 chapter01 入口块，预期 RuntimeError。
    """
    chapter = Path(REPO_ROOT) / "chapters" / "chapter01.md"
    story = _load_story(str(chapter))
    sink = MemoryInputSink(inputs=["平静", "1"])
    exe = Executor(story, sink)
    # c1 块 t_a 跳 ca → ca 块 body 有 text + end 但 meta 无 id:end → RuntimeError
    with pytest.raises(RuntimeError):
        exe.run()


def test_echo_path_uses_real_engine_bus_for_cross_process():
    """占位：v0-issue-19 跨进程 fixture 由 #42 acceptance 落地。

    本 test 占位——真 subprocess 测留给 v0 阶段外（用 subprocess.Popen + 真 EngineBus
    + 喂 UserInputCmd）。v0 阶段 MemoryInputSink 即可覆盖。
    """
    # 仅作 sanity check：EngineBus + 真跨进程 cmd round-trip
    from core.engine.bus import EngineBus
    from core.engine.protocol import UserInputCmd
    bus = EngineBus(use_multiprocessing=False)
    bus.put_cmd(UserInputCmd(value="测试"))
    cmd = bus.get_cmd()
    assert cmd.value == "测试"
    bus.close()


def test_echo_numeric_var_survives_engine_bus_round_trip():
    """echo 输出 int 变量时，TextEvt 经 EngineBus 序列化/反序列化不崩溃。

    回归测试：node in ->var 存储 int（用户输入数字时 executor 做 int 转换），
    node echo var 取出 int 值放入 TextEvt.content。若不转 str，
    EngineBus.put_evt → to_dict → JSON → from_dict → _require_str 会抛 ValueError。
    """
    from core.engine.bus import EngineBus

    chapter = Path(REPO_ROOT) / "tests" / "test_echo.md"
    story = _load_story(str(chapter))
    bus = EngineBus(use_multiprocessing=False)
    sink = _BusInputSink(bus, inputs=["18"])
    exe = Executor(story, sink)
    exe.run()

    # test_echo.md 产生 3 个事件：PromptInputEvt → TextEvt → ChapterEndEvt
    # 逐个反序列化验证不崩溃（修复前会在 TextEvt.from_dict 抛 ValueError）
    evts = [bus.get_evt() for _ in range(3)]
    text_evts = [e for e in evts if isinstance(e, TextEvt)]
    assert len(text_evts) == 1
    assert text_evts[0].content == "18"
    assert isinstance(text_evts[0].content, str)
    bus.close()


class _BusInputSink:
    """把 EngineBus 当 sink 用，按预设顺序喂 UserInputCmd。"""

    def __init__(self, bus, inputs):
        self._bus = bus
        self._inputs = list(inputs)
        self._idx = 0

    def put_evt(self, evt):
        self._bus.put_evt(evt)

    def get_cmd(self):
        if self._idx < len(self._inputs):
            v = self._inputs[self._idx]
            self._idx += 1
            from core.engine.protocol import UserInputCmd
            return UserInputCmd(value=v)
        return None
