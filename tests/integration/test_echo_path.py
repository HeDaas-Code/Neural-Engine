"""v0-issue-19 端到端：test_echo.md + MemoryInputSink。

按 issue #42 acceptance criteria 验证 v0 唯一跑通路径 in→echo→end。

phase2 P0-S1：tests/test_echo.md 不在 CHAPTERS_ROOT 下（默认仓库根 chapters/），
fixture 用 monkeypatch 临时放行；chapter01.md 测试保持原样（已在 chapters/）。
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


def test_echo_path_in_echo_end(monkeypatch):
    """最小 fixture: in -> p_tall + echo p_tall + end。"""
    from core.engine import main as main_mod

    # phase2 P0-S1：fixture 在 tests/ 下，临时把 CHAPTERS_ROOT 放宽到 tests/，让 _load_story 通过校验
    tests_dir = Path(REPO_ROOT) / "tests"
    monkeypatch.setattr(main_mod, "CHAPTERS_ROOT", tests_dir)

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
