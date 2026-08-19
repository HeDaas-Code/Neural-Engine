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


class TestSaveManagerCrashSafety:
    """save() 原子写入保护：失败时保留原文件不被破坏。"""

    def test_write_failure_preserves_existing_save(self, manager, save_dir, sample_state, monkeypatch):
        """写入失败（如磁盘满）不应导致原有存档被清空/损坏。

        触发场景：用户覆盖写已有存档时，open(..., 'w') 先截断文件，
        随后 write()/fsync() 因磁盘已满（ENOSPC）失败。
        非原子实现会先截断目标 .json 再写，原数据永久丢失；
        原子实现先写 .json.tmp，失败不碰目标 .json。
        """
        # ── 1. 完好的初始存档，并记录原始字节 ─────────────────────────
        manager.save("critical_slot", sample_state)
        slot_path = save_dir / "critical_slot.json"
        original_bytes = slot_path.read_bytes()
        assert len(original_bytes) > 0, "初始存档写入后应包含数据"

        # ── 2. 劫持 builtins.open：save_dir 下任何文件写时先截断再抛错 ──
        #    无论 SaveManager 写 .json（旧实现）还是 .json.tmp（新实现），
        #    只要进入 save_dir 并使用写模式就模拟磁盘满，验证原文件不被破坏。
        import builtins as _builtins
        _real_open = _builtins.open

        def crashy_open(file, mode="r", *args, **kwargs):
            is_in_save_dir = str(file).startswith(str(save_dir) + os.sep) or str(file) == str(save_dir)
            is_write_mode = isinstance(mode, str) and ("w" in mode or "+" in mode or "a" in mode)
            if is_in_save_dir and is_write_mode:
                # 先用真实 open 打开并截断文件（模拟 open(file, "w") 行为）
                fh = _real_open(file, mode, *args, **kwargs)

                def fail_write(data):
                    fh.flush()  # 确保截断已落盘
                    raise OSError(28, "No space left on device")

                fh.write = fail_write
                return fh
            return _real_open(file, mode, *args, **kwargs)

        monkeypatch.setattr(_builtins, "open", crashy_open)

        new_state = GameState(vars={"attempt": "new"}, path=[], current_block_id=None)
        # 写过程报错是预期的；关键是报错后原 critical_slot.json 完好
        with pytest.raises(OSError, match="[Ss]pace"):
            manager.save("critical_slot", new_state)

        # ── 3. 关键断言 ──────────────────────────────────────────────
        # BUG 表现：save_dir/critical_slot.json 被截断为空（151 字节 → 0 字节）
        # FIX 效果：SaveManager 仅操作 .json.tmp 临时文件，
        #          写入失败后 .json.tmp 被清理，critical_slot.json 原封不动
        # ─────────────────────────────────────────────────────────────
        actual = slot_path.read_bytes()
        assert actual == original_bytes, (
            "save() 失败后原有存档字节不一致！\n"
            f"  期望字节数: {len(original_bytes)}\n"
            f"  实际字节数: {len(actual)}\n"
            "根因: 写入路径不是原子写（目标文件被中途截断）。"
        )
        # 除了字节一致，存档必须仍可被 load() 正常还原
        loaded = manager.load("critical_slot")
        assert loaded.vars == {"name": "hero", "level": "5"}


class TestSaveManagerDeleteRace:
    """delete() 应避免 TOCTOU 竞态导致未处理异常崩溃。"""

    def test_delete_concurrent_removal_does_not_crash(self, manager, save_dir, sample_state, monkeypatch):
        """并发删除同一槽位时，exists()→unlink() 之间的竞态不应导致 FileNotFoundError 崩溃。

        触发场景：两个进程/线程几乎同时删除相同 slot，A 进程 exists()→True，
        B 进程在 A 的 unlink() 之前完成删除，A 的 unlink() 随即抛出未捕获的
        FileNotFoundError，造成调用链崩溃。

        通过让 unlink() 在文件确实存在的情况下抛出 FileNotFoundError，
        模拟 exists() 检查通过后、unlink() 执行前文件被另一进程删除的竞态。
        """
        manager.save("race_slot", sample_state)
        slot_path = save_dir / "race_slot.json"
        assert slot_path.exists(), "save 后文件应存在于磁盘"

        # 仅对目标 slot_path 劫持 unlink：存在也抛 FileNotFoundError，
        # 精确模拟 exists()→True 与 unlink() 之间文件被他人删除的窗口
        import os as _os
        _orig_unlink = _os.unlink

        def race_unlink(path, *args, **kwargs):
            if str(path) == str(slot_path):
                # 先真实删除，保证磁盘上确实没了，然后模拟竞态
                try:
                    _orig_unlink(path, *args, **kwargs)
                except FileNotFoundError:
                    pass
                raise FileNotFoundError(2, f"No such file or directory: {path!r}")
            return _orig_unlink(path, *args, **kwargs)

        monkeypatch.setattr(_os, "unlink", race_unlink)

        # FIX 前：FileNotFoundError 从 unlink() 上抛，无 try/except → 崩溃
        # FIX 后：EAFP 模式 → 捕获 FileNotFoundError → 返回 False
        result = manager.delete("race_slot")
        # 结果只要不抛异常即可；语义上文件已不存在，返回 False 最合理
        assert result in (True, False)
