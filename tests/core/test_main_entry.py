"""v0-issue-17 core 进程入口测试。

按 issue #40 acceptance criteria 验证 main() 错误路径 + import 可走。

phase2 P0-S1：新增 _load_story 路径校验的 5 个失败测试（路径穿越/越界/大小/扩展名/symlink）。
"""
import os
import pathlib
import sys
import tempfile
from pathlib import Path

import pytest

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")


# 1. import 可走
def test_main_imports_successfully():
    from core.engine.main import main
    assert callable(main)


# 2. 缺文件 → 退出 1
def test_main_nonexistent_path_returns_1(tmp_path):
    from core.engine.main import main
    missing = tmp_path / "missing.md"
    rc = main(str(missing))
    assert rc == 1


# 3. 缺文件 → LogEvt error 广播
def test_main_emits_log_error_for_missing_chapter(tmp_path, monkeypatch):
    from core.engine import main as main_mod
    from core.engine.protocol import LogEvt

    # 替换 EngineBus 为可观察的 MemoryEngineBus
    class MemoryEngineBus:
        def __init__(self, *a, **kw):
            from core.engine.executor import MemoryEventSink
            self._sink = MemoryEventSink()
        @property
        def events(self):
            return self._sink.events
        def put_evt(self, evt):
            self._sink.put_evt(evt)
        def get_cmd(self):
            return None
        def close(self):
            pass

    monkeypatch.setattr(main_mod, "EngineBus", MemoryEngineBus)

    missing = tmp_path / "missing.md"
    rc = main_mod.main(str(missing))
    assert rc == 1
    # 验证 LogEvt error 已发出
    log_err = [e for e in main_mod._last_bus.events if isinstance(e, LogEvt) and e.level == "error"]
    assert len(log_err) >= 1


# 4. 最小可用 chapter → headless 走通
def test_main_with_minimal_chapter_returns_0_headless(tmp_path, monkeypatch):
    from core.engine import main as main_mod

    chapter = tmp_path / "chapter01.md"
    chapter.write_text(
        "```neon\n"
        "id:start\n"
        "next: c1\n"
        "node start\n"
        "node c1\n"
        "node end\n"
        "```\n"
        "```neon\n"
        "id:c1\n"
        "id:end0\n"
        "node start\n"
        "node end\n"
        "```\n",
        encoding="utf-8",
    )

    # 替换 EngineBus 为可观察的
    class MemoryEngineBus:
        def __init__(self, *a, **kw):
            from core.engine.executor import MemoryEventSink
            self._sink = MemoryEventSink()
        def put_evt(self, evt):
            self._sink.put_evt(evt)
        def get_cmd(self):
            return None
        def close(self):
            pass

    monkeypatch.setattr(main_mod, "EngineBus", MemoryEngineBus)
    # phase2 P0-S1：让 chapter 通过路径校验（将 CHAPTERS_ROOT 指向 tmp_path）
    monkeypatch.setattr(main_mod, "CHAPTERS_ROOT", tmp_path)

    rc = main_mod.main(str(chapter))
    assert rc == 0


# ─────────────────────────────────────────────────────────────────────
# phase2 P0-S1：_load_story 路径校验测试（5 个安全漏点）
# ─────────────────────────────────────────────────────────────────────


def _make_minimal_neon_block() -> str:
    """构造一个最小可解析的 neon block（_load_story 走到 read_text 之后需要能过 ParserError 之前的检查）。
    返回的字符串必须是合法 neon block，以便 _load_story 在通过路径校验后能正常返回 Story。
    """
    return (
        "```neon\n"
        "id:start\n"
        "next: c1\n"
        "node start\n"
        "node c1\n"
        "node end\n"
        "```\n"
    )


def test_path_traversal_blocked(tmp_path, monkeypatch):
    """1. 路径穿越（./../etc/passwd）应被拒绝。
    攻击场景：CLI python -m core.engine.main ../../etc/passwd
    期望：ValueError，message 含 'must be under'
    """
    from core.engine import main as main_mod

    chapters_dir = tmp_path / "chapters"
    chapters_dir.mkdir()
    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir()
    secret_file = secret_dir / "passwd.md"
    secret_file.write_text(_make_minimal_neon_block(), encoding="utf-8")

    monkeypatch.setattr(main_mod, "CHAPTERS_ROOT", chapters_dir)

    # 用一个绝对路径，该路径不在 chapters_dir 下（路径穿越等价场景）
    with pytest.raises(ValueError, match="must be under"):
        main_mod._load_story(str(secret_file))


def test_absolute_path_outside_chapters_blocked(tmp_path, monkeypatch):
    """2. 绝对路径在 CHAPTERS_ROOT 之外应被拒绝（../ / 任意绝对路径）。"""
    from core.engine import main as main_mod

    chapters_dir = tmp_path / "chapters"
    chapters_dir.mkdir()
    monkeypatch.setattr(main_mod, "CHAPTERS_ROOT", chapters_dir)

    # 创建一个合法 .md 文件，但放在 chapters_dir 同级的 other 子目录下
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    outside = other_dir / "outside.md"
    outside.write_text(_make_minimal_neon_block(), encoding="utf-8")

    with pytest.raises(ValueError, match="must be under"):
        main_mod._load_story(str(outside))


def test_file_too_large_blocked(tmp_path, monkeypatch):
    """3. 文件大小 > 1MB 应被拒绝（防 /dev/zero OOM）。"""
    from core.engine import main as main_mod

    chapters_dir = tmp_path / "chapters"
    chapters_dir.mkdir()
    monkeypatch.setattr(main_mod, "CHAPTERS_ROOT", chapters_dir)
    monkeypatch.setattr(main_mod, "MAX_CHAPTER_SIZE", 1_000_000)

    big = chapters_dir / "big.md"
    # 2MB 随机内容（> 1MB 阈值）
    big.write_text("a" * 2_000_000, encoding="utf-8")

    with pytest.raises(ValueError, match="too large"):
        main_mod._load_story(str(big))


def test_non_md_extension_blocked(tmp_path, monkeypatch):
    """4. 非 .md 扩展名应被拒绝（malware.exe 伪装成章节）。"""
    from core.engine import main as main_mod

    chapters_dir = tmp_path / "chapters"
    chapters_dir.mkdir()
    monkeypatch.setattr(main_mod, "CHAPTERS_ROOT", chapters_dir)

    fake = chapters_dir / "malware.exe"
    fake.write_text("MZ\x90\x00binary", encoding="utf-8")

    with pytest.raises(ValueError, match=r"must be \.md"):
        main_mod._load_story(str(fake))


def test_symlink_blocked(tmp_path, monkeypatch):
    """5. 符号链接应被拒绝（chapters/foo.md → /etc/passwd）。
    Windows 上创建 symlink 需要 admin 或 developer mode。
    失败时用 monkeypatch 模拟 is_symlink() 返回 True。
    """
    from core.engine import main as main_mod

    chapters_dir = tmp_path / "chapters"
    chapters_dir.mkdir()
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()
    target = secrets_dir / "shadow.md"
    target.write_text(_make_minimal_neon_block(), encoding="utf-8")

    monkeypatch.setattr(main_mod, "CHAPTERS_ROOT", chapters_dir)

    link = chapters_dir / "foo.md"
    try:
        # 尝试创建真实符号链接（Unix / Windows Developer Mode）
        os.symlink(str(target), str(link))
    except (OSError, NotImplementedError):
        # Windows 无 admin/developer mode：mock is_symlink 让该路径报告为 symlink
        real_is_symlink = pathlib.Path.is_symlink

        def fake_is_symlink(self):
            try:
                # mock 的对象是 link（被加载的路径），不是 target
                if str(self.resolve()) == str(link.resolve()):
                    return True
            except (OSError, RuntimeError):
                pass
            return real_is_symlink(self)

        monkeypatch.setattr(pathlib.Path, "is_symlink", fake_is_symlink)

    with pytest.raises(ValueError, match="must not be a symlink"):
        main_mod._load_story(str(link))
