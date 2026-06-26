"""v2 P0 · V2-06 — GameState 序列化 + current_block_id 测试。

按 PM 派工 V2-06 任务验收：
- `GameState.to_dict()` 含 version=1 + vars + path + current_block_id
- `GameState.from_dict(d)` 类方法，反序列化恢复
- `Executor.run()` 入口设置 `state.current_block_id`
- `Executor._next_block` 后置更新 `state.current_block_id`

D2 决策：复用 protocol.py JSON 序列化模式（json.dumps + ensure_ascii=False + utf-8）。
V3+ 升级时通过 `version` 字段写迁移函数。

设计参考：
- docs/issues/github/v2-06-gamestate-serialize.md（Issue 模板）
- docs/pdr/phase3-v2p0.md §5.3（存档/读档）
"""
import sys

import pytest

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")

from core.engine.executor import (  # noqa: E402
    GameState, Executor, MemoryEventSink,
)
from core.engine.ast_nodes import (  # noqa: E402
    Story, Block, BlockLocation, IdMeta, IdEnd, NextDecl,
    Start, End, Text, NextId,
)


def _loc() -> BlockLocation:
    return BlockLocation(lineno=1, col=1)


# ─── 1. round-trip：state → to_dict → from_dict → state 一致 ────────────────


def test_gamestate_to_dict_then_from_dict_round_trip_preserves_fields():
    """GameState.to_dict() → GameState.from_dict() 完整恢复 vars/path/current_block_id。"""
    src = GameState()
    src.vars = {"p_mood": "平静", "score": 10, "flag": True}
    src.path = ["start", "c1", "ca"]
    src.current_block_id = "ca"

    blob = src.to_dict()
    assert isinstance(blob, dict)

    restored = GameState.from_dict(blob)
    assert restored.vars == src.vars
    assert restored.path == src.path
    assert restored.current_block_id == src.current_block_id


# ─── 2. to_dict 含 version=1 字段（D2 决策 + V3+ 升级留余地） ───────────────


def test_gamestate_to_dict_contains_version_field():
    """GameState.to_dict() 必须含 "version": 1 字段（V3+ 升级迁移锚点）。"""
    s = GameState()
    blob = s.to_dict()
    assert "version" in blob
    assert blob["version"] == 1


# ─── 3. from_dict 缺字段默认值（向后兼容老存档） ─────────────────────────


def test_gamestate_from_dict_missing_fields_uses_defaults():
    """from_dict 缺 vars/path/current_block_id 字段 → 用默认值（不抛错）。"""
    # 完全空 dict
    s_empty = GameState.from_dict({})
    assert s_empty.vars == {}
    assert s_empty.path == []
    assert s_empty.current_block_id is None
    # next_table 也应该被默认（虽然不在 to_dict 输出里，但 from_dict 必须兼容）
    assert s_empty.next_table == {}

    # 只有 version
    s_ver_only = GameState.from_dict({"version": 1})
    assert s_ver_only.vars == {}
    assert s_ver_only.current_block_id is None


# ─── 4. from_dict 不匹配 version 抛 ValueError（V3+ 升级防御） ─────────────


def test_gamestate_from_dict_unsupported_version_raises_value_error():
    """存档 version > 当前支持版本 → 抛 ValueError（V3+ 升级保护）。

    当前 GameState 仅支持 version=1；传入 version=2 或更大 → ValueError。
    """
    with pytest.raises(ValueError) as exc_info:
        GameState.from_dict({"version": 2, "vars": {}, "path": []})
    assert "version" in str(exc_info.value).lower()

    # 缺失 version → 视作 v1 老存档（向后兼容，不抛错）
    s = GameState.from_dict({"vars": {}, "path": [], "current_block_id": "c1"})
    assert s.current_block_id == "c1"


# ─── 5. 现有 GameState 默认字段不破（向后兼容） ─────────────────────────


def test_gamestate_default_fields_unchanged():
    """GameState 默认 vars={} / path=[] / next_table={} / current_block_id=None。"""
    s = GameState()
    assert s.vars == {}
    assert s.path == []
    assert s.next_table == {}
    assert s.current_block_id is None


# ─── 6. Executor.run 入口设置 current_block_id ─────────────────────────────


def test_executor_run_sets_current_block_id_to_entry_block():
    """Executor.run() 跑完 → state.current_block_id == 入口块 id。

    单块场景：start → end0 → ChapterEndEvt；state.current_block_id 保持 "start"
    （run 入口处设置一次）。
    """
    block = Block(
        meta=(IdMeta(id="start", lineno=1), IdEnd(x=0, route_chapter=None, lineno=2)),
        next_table=(),
        body=(Start(), Text(content="hi"), End()),
        loc=_loc(),
    )
    story = Story(blocks=(block,))
    sink = MemoryEventSink()
    exe = Executor(story, sink)
    exe.run()
    # 单块：入口即终点 → state.current_block_id == "start"
    assert exe.state.current_block_id == "start"


# ─── 7. Executor._next_block 后置更新 current_block_id ─────────────────────


def test_executor_next_block_updates_current_block_id_to_next():
    """跨块 NEXT 跳转 → state.current_block_id 同步更新到下一块 id。

    场景：start → next:c1 → c1 → end0 → ChapterEndEvt；
    跑完后 state.current_block_id == "c1"（最后访问块）。
    """
    start_block = Block(
        meta=(IdMeta(id="start", lineno=1),),
        next_table=(NextDecl(var_name=None, target_id="c1", lineno=2),),
        body=(Start(), Text(content="go"), NextId(target_id="c1")),
        loc=_loc(),
    )
    c1_block = Block(
        meta=(IdMeta(id="c1", lineno=10), IdEnd(x=0, route_chapter=None, lineno=11)),
        next_table=(),
        body=(Start(), End()),
        loc=BlockLocation(lineno=10, col=1),
    )
    story = Story(blocks=(start_block, c1_block))
    sink = MemoryEventSink()
    exe = Executor(story, sink)
    exe.run()
    # 跨块后 state.current_block_id == "c1"
    assert exe.state.current_block_id == "c1"


# ─── 8. GameState vars 中 list/dict 嵌套结构 round-trip ───────────────────


def test_gamestate_round_trip_preserves_list_and_dict_vars():
    """vars 含 list/dict 嵌套值（OQ-5 默认值：str/int/list/dict）→ round-trip 一致。"""
    src = GameState()
    src.vars = {
        "name": "玩家",
        "score": 100,
        "inventory": ["钥匙", "地图", "纸条"],
        "flags": {"has_key": True, "level": 3},
    }
    blob = src.to_dict()
    restored = GameState.from_dict(blob)
    assert restored.vars == src.vars


# ─── 9. to_dict 返回新 dict（防御性拷贝，不引用内部） ─────────────────────


def test_gamestate_to_dict_returns_independent_dict():
    """to_dict() 返回的 dict 改值不影响 state.vars / state.path（防御性拷贝）。"""
    s = GameState()
    s.vars["a"] = 1
    s.path = ["start"]
    blob = s.to_dict()
    blob["vars"]["a"] = 999
    blob["path"].append("HACKED")
    assert s.vars["a"] == 1
    assert s.path == ["start"]


# ─── 10. from_dict 接收 dict 子类型（defensive copy） ──────────────────────


def test_gamestate_from_dict_does_not_alias_input_dict():
    """from_dict(d) 内部 vars/path 是 d 的拷贝，改 d 不影响 state。"""
    d = {"vars": {"a": 1}, "path": ["start"], "current_block_id": "start"}
    s = GameState.from_dict(d)
    d["vars"]["a"] = 999
    d["path"].append("HACKED")
    d["current_block_id"] = "HACKED"
    assert s.vars == {"a": 1}
    assert s.path == ["start"]
    assert s.current_block_id == "start"
