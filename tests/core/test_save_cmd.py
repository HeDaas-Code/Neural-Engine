"""v2 P0 · V2-07 — SaveAckEvt / LoadAckEvt + Executor 集成测试。

按 PM 派工 V2-07 任务 3 验收：
- protocol.py 新增 `SaveAckEvt` / `LoadAckEvt` dataclass + 注册到 `_EVT_REGISTRY`
- Executor 集成 `SaveManager`：run() 中处理 SaveCmd / LoadCmd
- SaveCmd(slot) → SaveManager.save → 发 SaveAckEvt
- LoadCmd(slot) → SaveManager.load → 替换 self.state → 发 LoadAckEvt
- SaveAckEvt / LoadAckEvt 含 ok: bool + slot: str + [可选] error: str
"""
import sys

import pytest

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")


# ─── 0. 测试夹具：MixedCmdSink（混合 cmd 队列） ────────────────────────────


class MixedCmdSink:
    """测试 sink：按 list 提供混合 cmd（SaveCmd / LoadCmd / UserInputCmd）。"""

    def __init__(self, cmds=None):
        self._cmds = list(cmds or [])
        self._idx = 0
        self.events: list = []

    def put_evt(self, evt) -> None:
        self.events.append(evt)

    def get_cmd(self):
        if self._idx < len(self._cmds):
            v = self._cmds[self._idx]
            self._idx += 1
            return v
        return None


def _loc() -> "BlockLocation":
    from core.engine.ast_nodes import BlockLocation
    return BlockLocation(lineno=1, col=1)


# ─── 1. SaveAckEvt round-trip ────────────────────────────────────────────


def test_save_ack_evt_round_trip():
    """SaveAckEvt to_dict/from_dict 往返一致（成功路径）。"""
    from core.engine.protocol import SaveAckEvt

    evt = SaveAckEvt(slot="01", ok=True)
    d = evt.to_dict()
    assert d == {"event": "save_ack", "slot": "01", "ok": True}

    restored = SaveAckEvt.from_dict(d)
    assert restored == evt


# ─── 2. SaveAckEvt 失败路径含 error 字段 ──────────────────────────────────


def test_save_ack_evt_with_error_message():
    """SaveAckEvt 失败时含 error 字段（供 GUI 显示错误）。"""
    from core.engine.protocol import SaveAckEvt

    evt = SaveAckEvt(slot="../escape", ok=False, error="invalid slot")
    d = evt.to_dict()
    assert d["ok"] is False
    assert d["error"] == "invalid slot"

    restored = SaveAckEvt.from_dict(d)
    assert restored == evt


# ─── 3. LoadAckEvt round-trip ────────────────────────────────────────────


def test_load_ack_evt_round_trip():
    """LoadAckEvt to_dict/from_dict 往返一致（成功路径）。"""
    from core.engine.protocol import LoadAckEvt

    evt = LoadAckEvt(slot="02", ok=True)
    d = evt.to_dict()
    assert d == {"event": "load_ack", "slot": "02", "ok": True}

    restored = LoadAckEvt.from_dict(d)
    assert restored == evt


# ─── 4. LoadAckEvt 失败路径含 error 字段 ──────────────────────────────────


def test_load_ack_evt_with_error_message():
    """LoadAckEvt 失败时含 error 字段。"""
    from core.engine.protocol import LoadAckEvt

    evt = LoadAckEvt(slot="nonexistent", ok=False, error="not found")
    d = evt.to_dict()
    assert d["event"] == "load_ack"
    assert d["ok"] is False
    assert d["error"] == "not found"

    restored = LoadAckEvt.from_dict(d)
    assert restored == evt


# ─── 5. _EVT_REGISTRY 含 save_ack / load_ack（防回归） ───────────────────


def test_evt_registry_contains_save_ack_and_load_ack():
    """_EVT_REGISTRY 必须含 save_ack / load_ack（防未来重构漏注册）。"""
    from core.engine.protocol import _EVT_REGISTRY, SaveAckEvt, LoadAckEvt

    assert "save_ack" in _EVT_REGISTRY
    assert "load_ack" in _EVT_REGISTRY
    assert _EVT_REGISTRY["save_ack"] is SaveAckEvt
    assert _EVT_REGISTRY["load_ack"] is LoadAckEvt


# ─── 6. parse_evt 分发 SaveAckEvt / LoadAckEvt ────────────────────────────


def test_parse_evt_dispatches_save_ack_and_load_ack():
    """parse_evt({event: save_ack, ...}) → SaveAckEvt；load_ack → LoadAckEvt。"""
    from core.engine.protocol import parse_evt, SaveAckEvt, LoadAckEvt

    s = parse_evt({"event": "save_ack", "slot": "01", "ok": True})
    assert isinstance(s, SaveAckEvt)
    assert s.slot == "01"
    assert s.ok is True

    l = parse_evt({"event": "load_ack", "slot": "02", "ok": False, "error": "x"})
    assert isinstance(l, LoadAckEvt)
    assert l.slot == "02"
    assert l.ok is False
    assert l.error == "x"


# ─── 7. SaveAckEvt / LoadAckEvt 缺字段抛 ValueError ──────────────────────


def test_save_ack_evt_missing_slot_raises():
    """SaveAckEvt.from_dict 缺 slot → ValueError。"""
    from core.engine.protocol import SaveAckEvt

    with pytest.raises(ValueError):
        SaveAckEvt.from_dict({"event": "save_ack", "ok": True})


def test_save_ack_evt_missing_ok_raises():
    """SaveAckEvt.from_dict 缺 ok → ValueError。"""
    from core.engine.protocol import SaveAckEvt

    with pytest.raises(ValueError):
        SaveAckEvt.from_dict({"event": "save_ack", "slot": "01"})


def test_load_ack_evt_missing_slot_raises():
    """LoadAckEvt.from_dict 缺 slot → ValueError。"""
    from core.engine.protocol import LoadAckEvt

    with pytest.raises(ValueError):
        LoadAckEvt.from_dict({"event": "load_ack", "ok": True})


def test_load_ack_evt_missing_ok_raises():
    """LoadAckEvt.from_dict 缺 ok → ValueError。"""
    from core.engine.protocol import LoadAckEvt

    with pytest.raises(ValueError):
        LoadAckEvt.from_dict({"event": "load_ack", "slot": "01"})


# ─── 8. Executor 接受 save_manager 参数 ───────────────────────────────────


def test_executor_accepts_save_manager_parameter():
    """Executor.__init__ 接受 save_manager: SaveManager | None = None。"""
    from core.engine.executor import Executor
    from core.engine.ast_nodes import Story
    from core.engine.interpreter import extract_neon_blocks
    from runtime.save import SaveManager

    sink = MixedCmdSink()
    sm = SaveManager()
    story = Story(blocks=())
    exe = Executor(story, sink, save_manager=sm)
    assert exe.save_manager is sm

    # 不传 save_manager → None（向后兼容）
    exe2 = Executor(story, sink)
    assert exe2.save_manager is None


# ─── 9. Executor 处理 SaveCmd → 发 SaveAckEvt.ok=True ───────────────────


def test_executor_processes_save_cmd_emits_save_ack_evt(tmp_path):
    """Send SaveCmd via sink → Executor 调 SaveManager.save → 发 SaveAckEvt.ok=True。"""
    from core.engine.executor import Executor
    from core.engine.ast_nodes import (
        Story, Block, IdMeta, IdEnd, Start, Text, End, NextDecl,
    )
    from core.engine.protocol import SaveCmd, SaveAckEvt, UserInputCmd
    from runtime.save import SaveManager

    sm = SaveManager(save_dir=tmp_path)
    # 单 In 节点 block（触发 get_cmd()）
    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=2)),
        next_table=(),
        body=(Start(), Text(content="hi"), End()),
        loc=_loc(),
    )
    story = Story(blocks=(block,))
    sink = MixedCmdSink(cmds=[
        SaveCmd(slot="01"),  # 拦截为存档命令
        UserInputCmd(value="never_used"),  # 第二个 cmd（不在 In 节点触发）
    ])
    exe = Executor(story, sink, save_manager=sm)
    # 预填 vars 让 save 内容非空
    exe.state.vars["key"] = "v"
    exe.run()

    # 验证：存档文件已写
    assert (tmp_path / "01.json").exists()
    # 验证：sink 上有 SaveAckEvt.ok=True
    save_acks = [e for e in sink.events if isinstance(e, SaveAckEvt)]
    assert len(save_acks) == 1
    assert save_acks[0].slot == "01"
    assert save_acks[0].ok is True


# ─── 10. Executor 处理 LoadCmd → 发 LoadAckEvt + 替换 self.state ─────────


def test_executor_processes_load_cmd_emits_load_ack_and_replaces_state(tmp_path):
    """先 save state → send LoadCmd → Executor 调 SaveManager.load → 替换 self.state。"""
    from core.engine.executor import Executor
    from core.engine.ast_nodes import (
        Story, Block, IdMeta, IdEnd, Start, Text, End,
    )
    from core.engine.protocol import LoadCmd, LoadAckEvt, UserInputCmd
    from runtime.save import SaveManager

    sm = SaveManager(save_dir=tmp_path)
    # 先存一份 state
    from core.engine.executor import GameState
    saved_state = GameState()
    saved_state.vars["loaded_var"] = "from_save"
    saved_state.current_block_id = "c1"
    sm.save("restore", saved_state)

    # 单 block 触发 In 节点
    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=2)),
        next_table=(),
        body=(Start(), Text(content="hi"), End()),
        loc=_loc(),
    )
    story = Story(blocks=(block,))
    sink = MixedCmdSink(cmds=[
        LoadCmd(slot="restore"),
        UserInputCmd(value="never_used"),
    ])
    exe = Executor(story, sink, save_manager=sm)
    # 预填不同的 vars（验证 load 后被覆盖）
    exe.state.vars["loaded_var"] = "ORIGINAL"

    exe.run()

    # 验证：self.state 被替换
    assert exe.state.vars["loaded_var"] == "from_save"
    assert exe.state.current_block_id == "c1"
    # 验证：LoadAckEvt.ok=True
    load_acks = [e for e in sink.events if isinstance(e, LoadAckEvt)]
    assert len(load_acks) == 1
    assert load_acks[0].slot == "restore"
    assert load_acks[0].ok is True


# ─── 11. SaveCmd + 真实 In 节点：存档后仍能消费 UserInputCmd ─────────────


def test_executor_save_cmd_interleaved_with_user_input(tmp_path):
    """In 节点 cmd 队列：[SaveCmd, UserInputCmd("ok")] → 先存档，后用 ok 作输入。"""
    from core.engine.executor import Executor, GameState
    from core.engine.ast_nodes import (
        Story, Block, IdMeta, IdEnd, Start, In, End,
    )
    from core.engine.protocol import SaveCmd, SaveAckEvt, UserInputCmd
    from runtime.save import SaveManager

    sm = SaveManager(save_dir=tmp_path)
    # 单 block: start + In(var=p_name) + end
    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=2)),
        next_table=(),
        body=(Start(), In(var="p_name"), End()),
        loc=_loc(),
    )
    story = Story(blocks=(block,))
    sink = MixedCmdSink(cmds=[
        SaveCmd(slot="ckpt"),
        UserInputCmd(value="alice"),
    ])
    exe = Executor(story, sink, save_manager=sm)
    exe.run()

    # SaveAckEvt 必须发
    assert any(isinstance(e, SaveAckEvt) and e.ok for e in sink.events)
    # UserInputCmd 最终被消费 → state.vars["p_name"] == "alice"
    assert exe.state.vars.get("p_name") == "alice"
    # 存档文件存在
    assert (tmp_path / "ckpt.json").exists()


# ─── 12. SaveCmd slot 非法 → SaveAckEvt.ok=False + error 字段 ───────────


def test_executor_save_cmd_invalid_slot_emits_ack_with_error(tmp_path):
    """SaveCmd(slot="../escape") → SaveAckEvt.ok=False + error 含 ValueError 原因。"""
    from core.engine.executor import Executor
    from core.engine.ast_nodes import (
        Story, Block, IdMeta, IdEnd, Start, Text, End,
    )
    from core.engine.protocol import SaveCmd, SaveAckEvt, UserInputCmd
    from runtime.save import SaveManager

    sm = SaveManager(save_dir=tmp_path)
    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=2)),
        next_table=(),
        body=(Start(), Text(content="hi"), End()),
        loc=_loc(),
    )
    story = Story(blocks=(block,))
    sink = MixedCmdSink(cmds=[
        SaveCmd(slot="../escape"),
        UserInputCmd(value="never"),
    ])
    exe = Executor(story, sink, save_manager=sm)
    exe.run()

    save_acks = [e for e in sink.events if isinstance(e, SaveAckEvt)]
    assert len(save_acks) == 1
    assert save_acks[0].slot == "../escape"
    assert save_acks[0].ok is False
    assert save_acks[0].error  # 非空
    # 验证：文件未创建
    assert not (tmp_path / "../escape.json").exists()


# ─── 13. LoadCmd slot 不存在 → LoadAckEvt.ok=False + error ──────────────


def test_executor_load_cmd_nonexistent_slot_emits_ack_with_error(tmp_path):
    """LoadCmd(slot="ghost") → LoadAckEvt.ok=False + error。state 不被覆盖。"""
    from core.engine.executor import Executor
    from core.engine.ast_nodes import (
        Story, Block, IdMeta, IdEnd, Start, Text, End,
    )
    from core.engine.protocol import LoadCmd, LoadAckEvt, UserInputCmd
    from runtime.save import SaveManager

    sm = SaveManager(save_dir=tmp_path)
    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=2)),
        next_table=(),
        body=(Start(), Text(content="hi"), End()),
        loc=_loc(),
    )
    story = Story(blocks=(block,))
    sink = MixedCmdSink(cmds=[
        LoadCmd(slot="ghost"),
        UserInputCmd(value="never"),
    ])
    exe = Executor(story, sink, save_manager=sm)
    original_state = exe.state
    exe.state.vars["untouched"] = "still_here"
    exe.run()

    load_acks = [e for e in sink.events if isinstance(e, LoadAckEvt)]
    assert len(load_acks) == 1
    assert load_acks[0].slot == "ghost"
    assert load_acks[0].ok is False
    assert load_acks[0].error
    # state 未被替换
    assert exe.state is original_state
    assert exe.state.vars["untouched"] == "still_here"


# ─── 14. 无 save_manager + SaveCmd → SaveAckEvt.ok=False（不抛） ─────────


def test_executor_without_save_manager_save_cmd_emits_error_ack():
    """Executor 没传 save_manager + SendCmd → SaveAckEvt.ok=False（不抛错）。"""
    from core.engine.executor import Executor
    from core.engine.ast_nodes import (
        Story, Block, IdMeta, IdEnd, Start, Text, End,
    )
    from core.engine.protocol import SaveCmd, SaveAckEvt, UserInputCmd

    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=2)),
        next_table=(),
        body=(Start(), Text(content="hi"), End()),
        loc=_loc(),
    )
    story = Story(blocks=(block,))
    sink = MixedCmdSink(cmds=[
        SaveCmd(slot="01"),
        UserInputCmd(value="never"),
    ])
    exe = Executor(story, sink)  # no save_manager
    exe.run()  # 不抛错

    save_acks = [e for e in sink.events if isinstance(e, SaveAckEvt)]
    assert len(save_acks) == 1
    assert save_acks[0].ok is False
    assert save_acks[0].error  # 提到 save_manager 缺失


# ─── 15. SaveCmd 在 run() 主循环（多 block 跳转）下也工作 ─────────────────


def test_executor_save_cmd_works_across_multiple_blocks(tmp_path):
    """多 block 场景：第一个 In 触发 SaveCmd，第二个 In 触发 UserInputCmd。"""
    from core.engine.executor import Executor
    from core.engine.ast_nodes import (
        Story, Block, IdMeta, IdEnd, Start, In, End, Text, NextId, NextDecl,
    )
    from core.engine.protocol import SaveCmd, SaveAckEvt, UserInputCmd
    from runtime.save import SaveManager

    sm = SaveManager(save_dir=tmp_path)

    start_block = Block(
        meta=(IdMeta(id="start", lineno=1),),
        next_table=(NextDecl(var_name=None, target_id="c1", lineno=2),),
        body=(Start(), In(var="p_mood"), NextId(target_id="c1")),
        loc=_loc(),
    )
    c1_block = Block(
        meta=(IdMeta(id="c1", lineno=10), IdEnd(x=0, route_chapter=None, lineno=11)),
        next_table=(),
        body=(Start(), Text(content="done"), End()),
        loc=_loc(),
    )
    story = Story(blocks=(start_block, c1_block))
    sink = MixedCmdSink(cmds=[
        SaveCmd(slot="ckpt"),  # 第一个 In 拦截存档
        UserInputCmd(value="happy"),  # 第一个 In 真实输入
    ])
    exe = Executor(story, sink, save_manager=sm)
    exe.run()

    # 验证：SaveAckEvt 发
    assert any(isinstance(e, SaveAckEvt) and e.ok for e in sink.events)
    # 验证：UserInputCmd 被消费
    assert exe.state.vars["p_mood"] == "happy"
    # 验证：存档存在
    assert (tmp_path / "ckpt.json").exists()
    # 验证：current_block_id 更新到 c1
    assert exe.state.current_block_id == "c1"
