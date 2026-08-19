"""runtime/save.py (SaveManager) 单元测试。

SaveManager 是存档/读档管理器，包含：
- slot 名校验（防路径穿越）
- save / load / delete / list_slots 操作
- GameState JSON 序列化/反序列化
此前仅有 import 级测试，无功能性覆盖。
"""

import sys
import os
import json
import shutil
from pathlib import Path

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, f"{REPO_ROOT}/src")

from runtime.save import SaveManager, _validate_slot
from core.engine.executor import GameState


@pytest.fixture
def save_dir(tmp_path):
    return tmp_path / "test_saves"


@pytest.fixture
def manager(save_dir):
    return SaveManager(save_dir=save_dir)


@pytest.fixture
def sample_state():
    return GameState(
        vars={"name": "hero", "level": "5"},
        path=["block_1", "block_2"],
        current_block_id="block_3",
    )


class TestSlotValidation:
    """_validate_slot() slot 名校验逻辑。"""

    def test_valid_slot_underscore(self):
        _validate_slot("my_slot")

    def test_valid_slot_hyphen(self):
        _validate_slot("checkpoint-01")

    def test_valid_slot_alphanumeric(self):
        _validate_slot("slot123")

    def test_empty_slot_raises(self):
        with pytest.raises(ValueError, match="不能为空"):
            _validate_slot("")

    def test_non_string_slot_raises(self):
        with pytest.raises(ValueError, match="必须为 str"):
            _validate_slot(123)

    def test_path_traversal_dotdot_raises(self):
        with pytest.raises(ValueError):
            _validate_slot("../escape")

    def test_path_traversal_absolute_raises(self):
        with pytest.raises(ValueError):
            _validate_slot("/etc/passwd")

    def test_special_chars_raises(self):
        with pytest.raises(ValueError):
            _validate_slot("slot;rm -rf /")

    def test_space_in_slot_raises(self):
        with pytest.raises(ValueError):
            _validate_slot("my slot")


class TestSaveManagerSaveLoad:
    """SaveManager.save() / load() 往返。"""

    def test_save_and_load_roundtrip(self, manager, sample_state):
        manager.save("test_slot", sample_state)
        loaded = manager.load("test_slot")
        assert loaded.vars == {"name": "hero", "level": "5"}
        assert loaded.path == ["block_1", "block_2"]
        assert loaded.current_block_id == "block_3"

    def test_save_overwrites_existing(self, manager, sample_state):
        manager.save("slot", sample_state)
        updated = GameState(vars={"name": "villain"}, path=[], current_block_id=None)
        manager.save("slot", updated)
        loaded = manager.load("slot")
        assert loaded.vars == {"name": "villain"}

    def test_load_nonexistent_raises(self, manager):
        with pytest.raises(FileNotFoundError):
            manager.load("nonexistent")

    def test_load_corrupt_json_raises(self, manager, save_dir):
        slot_path = save_dir / "corrupt.json"
        slot_path.write_text("this is not valid json{{{")
        with pytest.raises(json.JSONDecodeError):
            manager.load("corrupt")

    def test_save_creates_directory(self, tmp_path):
        new_dir = tmp_path / "new" / "saves"
        mgr = SaveManager(save_dir=new_dir)
        state = GameState(vars={}, path=[], current_block_id=None)
        mgr.save("auto_created", state)
        assert new_dir.exists()
        loaded = mgr.load("auto_created")
        assert loaded.vars == {}

    def test_save_unicode_content(self, manager):
        state = GameState(
            vars={"名字": "主角", "emoji": "🎉"},
            path=[],
            current_block_id="start",
        )
        manager.save("unicode_test", state)
        loaded = manager.load("unicode_test")
        assert loaded.vars["名字"] == "主角"


class TestSaveManagerDelete:
    """SaveManager.delete() 行为。"""

    def test_delete_existing_returns_true(self, manager, sample_state):
        manager.save("to_delete", sample_state)
        result = manager.delete("to_delete")
        assert result is True
        assert not (manager.save_dir / "to_delete.json").exists()

    def test_delete_nonexistent_returns_false(self, manager):
        result = manager.delete("ghost_slot")
        assert result is False

    def test_delete_invalid_slot_raises(self, manager):
        with pytest.raises(ValueError):
            manager.delete("../escape")


class TestSaveManagerListSlots:
    """SaveManager.list_slots() 行为。"""

    def test_list_slots_empty_dir(self, manager):
        assert manager.list_slots() == []

    def test_list_slots_multiple(self, manager, sample_state):
        manager.save("charlie", sample_state)
        manager.save("alpha", sample_state)
        manager.save("bravo", sample_state)
        slots = manager.list_slots()
        assert slots == ["alpha", "bravo", "charlie"]

    def test_list_slots_excludes_non_json(self, manager, save_dir):
        (save_dir / "readme.txt").write_text("not a save file")
        manager.save("real_slot", GameState())
        slots = manager.list_slots()
        assert "readme" not in slots
        assert "real_slot" in slots