"""v2 P0 · V2-07 — SaveManager 单元测试。

按 PM 派工 V2-07 任务验收：
- `SaveManager(save_dir)` 默认 `~/.neural-engine/saves/`
- `save(slot, state)` 写 `{slot}.json`（D2 决策：json.dumps + utf-8 + ensure_ascii=False）
- `load(slot)` → GameState（恢复 vars/path/current_block_id）
- `list_slots()` → sorted list[str]
- `delete(slot)` → bool（True 删成功 / False 不存在）
- 路径校验：slot 名仅允许 `[\\w-]+`（防路径穿越）
- 缺省目录自动 mkdir(parents=True, exist_ok=True)

D4 决策：默认存档目录 `~/.neural-engine/saves/{slot}.json`（用户级存档）
D2 决策：复用 protocol.py 的 json.dumps + utf-8 + ensure_ascii=False + indent=2

测试策略：
- 测试用 `tmp_path` fixture 注入 `save_dir`（避免污染 ~/.neural-engine/saves/）
- 测试 D4 默认目录时用 `monkeypatch.setattr(Path, "home")` 注入假 home
"""
import json
import sys

import pytest

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")

from core.engine.executor import GameState  # noqa: E402


# ─── 1. save 写入 JSON 文件到 {save_dir}/{slot}.json ────────────────────────


def test_save_creates_json_file(tmp_path):
    """save(slot, state) 写 save_dir/{slot}.json。"""
    from runtime.save import SaveManager

    mgr = SaveManager(save_dir=tmp_path)
    state = GameState()
    state.vars["a"] = 1
    mgr.save("01", state)

    expected = tmp_path / "01.json"
    assert expected.exists()
    # JSON 内容含 vars（用 ensure_ascii=False 写入中文 OK）
    blob = json.loads(expected.read_text(encoding="utf-8"))
    assert blob["vars"]["a"] == 1


# ─── 2. save 目录不存在时自动创建 ─────────────────────────────────────────


def test_save_creates_directory_if_missing(tmp_path):
    """save_dir 不存在 → mkdir(parents=True, exist_ok=True) 自动创建。"""
    from runtime.save import SaveManager

    nested = tmp_path / "a" / "b" / "c"
    mgr = SaveManager(save_dir=nested)
    state = GameState()
    mgr.save("x", state)

    assert nested.exists()
    assert (nested / "x.json").exists()


# ─── 3. load 读 JSON 文件恢复 GameState ────────────────────────────────────


def test_load_reads_json_file_and_returns_gamestate(tmp_path):
    """load(slot) 读 save_dir/{slot}.json → GameState。"""
    from runtime.save import SaveManager

    mgr = SaveManager(save_dir=tmp_path)
    src = GameState()
    src.vars = {"x": 10, "y": "hello"}
    src.path = ["start", "c1"]
    src.current_block_id = "c1"
    mgr.save("foo", src)

    loaded = mgr.load("foo")
    assert isinstance(loaded, GameState)
    assert loaded.vars == {"x": 10, "y": "hello"}
    assert loaded.path == ["start", "c1"]
    assert loaded.current_block_id == "c1"


# ─── 4. round-trip 完整一致 ──────────────────────────────────────────────


def test_save_load_round_trip_preserves_all_state(tmp_path):
    """state → save → load → 字段完全一致（含 list/dict 嵌套）。"""
    from runtime.save import SaveManager

    mgr = SaveManager(save_dir=tmp_path)
    src = GameState()
    src.vars = {
        "name": "玩家",
        "score": 100,
        "inventory": ["钥匙", "地图"],
        "flags": {"has_key": True, "level": 3},
    }
    src.path = ["start", "c1", "ca"]
    src.current_block_id = "ca"

    mgr.save("rt", src)
    loaded = mgr.load("rt")

    assert loaded.vars == src.vars
    assert loaded.path == src.path
    assert loaded.current_block_id == src.current_block_id


# ─── 5. list_slots 返回所有存档槽（sorted） ──────────────────────────────


def test_list_slots_returns_sorted_slot_names(tmp_path):
    """list_slots() 返回所有 {slot}.json 的 slot 名（按字母排序）。"""
    from runtime.save import SaveManager

    mgr = SaveManager(save_dir=tmp_path)
    state = GameState()
    mgr.save("c", state)
    mgr.save("a", state)
    mgr.save("b", state)
    # 干扰文件（非 .json）
    (tmp_path / "ignore.txt").write_text("not a save", encoding="utf-8")
    (tmp_path / "ignore.md").write_text("# not save", encoding="utf-8")

    assert mgr.list_slots() == ["a", "b", "c"]


# ─── 6. list_slots 空目录返回空列表 ────────────────────────────────────────


def test_list_slots_returns_empty_list_when_no_saves(tmp_path):
    """空目录 → list_slots() 返回 []。"""
    from runtime.save import SaveManager

    mgr = SaveManager(save_dir=tmp_path)
    assert mgr.list_slots() == []


# ─── 7. delete 删现有存档返回 True ─────────────────────────────────────────


def test_delete_existing_slot_returns_true(tmp_path):
    """delete(slot) 删现有存档 → True + 文件消失。"""
    from runtime.save import SaveManager

    mgr = SaveManager(save_dir=tmp_path)
    state = GameState()
    mgr.save("to_del", state)
    assert (tmp_path / "to_del.json").exists()

    assert mgr.delete("to_del") is True
    assert not (tmp_path / "to_del.json").exists()


# ─── 8. delete 不存在存档返回 False ───────────────────────────────────────


def test_delete_nonexistent_slot_returns_false(tmp_path):
    """delete(slot) 不存在 → False（不抛错）。"""
    from runtime.save import SaveManager

    mgr = SaveManager(save_dir=tmp_path)
    assert mgr.delete("never_existed") is False


# ─── 9. invalid slot 名（含路径穿越）抛 ValueError ────────────────────────


@pytest.mark.parametrize("bad_slot", [
    "../escape",        # 父目录穿越
    "..\\escape",       # Windows 反斜杠穿越
    "sub/dir",          # 含路径分隔符
    "sub\\dir",         # 含路径分隔符
    "",                 # 空字符串
    "with space",       # 含空格
    "with.dot",         # 含点号（部分允许但 \w 不含 .）
    "with/slash",       # 含正斜杠
])
def test_save_with_invalid_slot_raises_value_error(tmp_path, bad_slot):
    """非法 slot 名（路径穿越 / 空 / 含特殊字符）→ ValueError。"""
    from runtime.save import SaveManager

    mgr = SaveManager(save_dir=tmp_path)
    state = GameState()
    with pytest.raises(ValueError):
        mgr.save(bad_slot, state)


@pytest.mark.parametrize("bad_slot", [
    "../escape",
    "sub/dir",
    "",
    "with space",
])
def test_load_with_invalid_slot_raises_value_error(tmp_path, bad_slot):
    """load 非法 slot 名 → ValueError。"""
    from runtime.save import SaveManager

    mgr = SaveManager(save_dir=tmp_path)
    with pytest.raises(ValueError):
        mgr.load(bad_slot)


@pytest.mark.parametrize("bad_slot", [
    "../escape",
    "sub/dir",
    "",
])
def test_delete_with_invalid_slot_raises_value_error(tmp_path, bad_slot):
    """delete 非法 slot 名 → ValueError。"""
    from runtime.save import SaveManager

    mgr = SaveManager(save_dir=tmp_path)
    with pytest.raises(ValueError):
        mgr.delete(bad_slot)


# ─── 10. 合法 slot 名允许 [\w-]+（字母数字下划线短横） ─────────────────────


@pytest.mark.parametrize("good_slot", [
    "01",
    "slot-1",
    "save_alpha",
    "ABC",
    "123",
    "a-b-c-1",
    "with_under_score",
])
def test_save_load_with_valid_slot_names(tmp_path, good_slot):
    """合法 slot 名 [\w-]+ → save + load 成功。"""
    from runtime.save import SaveManager

    mgr = SaveManager(save_dir=tmp_path)
    state = GameState()
    state.vars["k"] = good_slot
    mgr.save(good_slot, state)
    loaded = mgr.load(good_slot)
    assert loaded.vars["k"] == good_slot


# ─── 11. load 不存在 slot 抛 FileNotFoundError ────────────────────────────


def test_load_nonexistent_slot_raises_file_not_found(tmp_path):
    """load(slot) 文件不存在 → FileNotFoundError。"""
    from runtime.save import SaveManager

    mgr = SaveManager(save_dir=tmp_path)
    with pytest.raises(FileNotFoundError):
        mgr.load("never_saved")


# ─── 12. save 同名 slot 覆盖 ─────────────────────────────────────────────


def test_save_overwrites_existing_slot(tmp_path):
    """save 同名 slot → 覆盖旧文件（不是 append）。"""
    from runtime.save import SaveManager

    mgr = SaveManager(save_dir=tmp_path)
    state1 = GameState()
    state1.vars["v"] = 1
    mgr.save("dup", state1)

    state2 = GameState()
    state2.vars["v"] = 2
    mgr.save("dup", state2)

    loaded = mgr.load("dup")
    assert loaded.vars["v"] == 2


# ─── 13. 默认 save_dir = ~/.neural-engine/saves/（D4 决策） ───────────────


def test_default_save_dir_is_neural_engine_saves_in_home(monkeypatch, tmp_path):
    """不传 save_dir → 默认 ~/.neural-engine/saves/（D4 决策验证）。"""
    from pathlib import Path
    from runtime import save as save_mod

    # 把 fake home 设为 tmp_path；SaveManager 默认 save_dir = home/.neural-engine/saves
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    # 实例化（不传 save_dir）
    mgr = save_mod.SaveManager()
    assert mgr.save_dir == fake_home / ".neural-engine" / "saves"


# ─── 14. JSON 文件中文编码正确（ensure_ascii=False） ──────────────────────


def test_save_preserves_chinese_characters(tmp_path):
    """save 中文字符 → 文件读回无 \\u 转义（ensure_ascii=False 验证）。"""
    from runtime.save import SaveManager

    mgr = SaveManager(save_dir=tmp_path)
    state = GameState()
    state.vars["玩家名"] = "小李"
    state.vars["日记"] = "今天下雨"
    mgr.save("cn", state)

    raw_text = (tmp_path / "cn.json").read_text(encoding="utf-8")
    # ensure_ascii=False → 中文直接写入，不需要 \uXXXX 转义
    assert "玩家名" in raw_text
    assert "小李" in raw_text
    assert "\\u" not in raw_text  # 验证 ensure_ascii=False


# ─── 15. 多次 save/load 状态机一致（回归测试） ───────────────────────────


def test_multiple_saves_independent_state_recovery(tmp_path):
    """3 个 slot 各存不同状态 → 各自 load 互不污染。"""
    from runtime.save import SaveManager

    mgr = SaveManager(save_dir=tmp_path)

    s1 = GameState()
    s1.vars["chapter"] = "c1"
    s1.current_block_id = "c1"
    mgr.save("ch1", s1)

    s2 = GameState()
    s2.vars["chapter"] = "c2"
    s2.current_block_id = "c2"
    mgr.save("ch2", s2)

    s3 = GameState()
    s3.vars["chapter"] = "c3"
    s3.current_block_id = "c3"
    mgr.save("ch3", s3)

    assert mgr.load("ch1").current_block_id == "c1"
    assert mgr.load("ch2").current_block_id == "c2"
    assert mgr.load("ch3").current_block_id == "c3"
