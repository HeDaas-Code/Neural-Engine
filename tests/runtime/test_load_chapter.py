"""V2-04 · Task 1 — runtime.load_chapter.load_chapter_safe 路径校验 + 加载测试。

按 PM 派工 V2-04 任务 1 验收：
- 从 core.engine.main._load_story 抽出可复用包装到 src/runtime/load_chapter.py
- 复用阶段二 P0-S1 路径校验（防穿越 + 大小 + 扩展名 + symlink）—— 不在此处重写
- 给 ChapterManager 后续消费 RouteEvt 准备

策略：
- 用 tmp_path 创建临时 chapters 目录 + chapter01.md
- 用 monkeypatch 替换 core.engine.main.CHAPTERS_ROOT / MAX_CHAPTER_SIZE 控制校验常量
- load_chapter_safe 内部必须复用 main.py 的 validate_chapter_path（同一校验源）
- 校验失败抛 ValueError；缺失文件抛 FileNotFoundError
"""
import os
import pathlib
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")


# ─── 1. happy path：合法 .md → 返回 Story，blocks 数对得上 ────────────────────


def test_load_chapter_safe_returns_story_for_valid_md(tmp_path, monkeypatch):
    """最小可用 chapter .md → load_chapter_safe 返回 Story，blocks 数量正确。"""
    from core.engine import main as main_mod
    from runtime.load_chapter import load_chapter_safe

    # 临时 chapters 目录
    chapters_dir = tmp_path / "chapters"
    chapters_dir.mkdir()
    chapter = chapters_dir / "valid.md"
    chapter.write_text(
        "```neon\n"
        "id:start\n"
        "node start\n"
        "hello\n"
        "node end\n"
        "```\n",
        encoding="utf-8",
    )
    # 把 P0-S1 校验常量指向 tmp 目录
    monkeypatch.setattr(main_mod, "CHAPTERS_ROOT", chapters_dir)

    story = load_chapter_safe(chapter)

    # 1 个块：start
    assert len(story.blocks) == 1
    block = story.blocks[0]
    # meta 含 id:start
    from core.engine.ast_nodes import IdMeta
    assert any(isinstance(m, IdMeta) and m.id == "start" for m in block.meta)


# ─── 2. 文件不存在 → FileNotFoundError ────────────────────────────────────────


def test_load_chapter_safe_raises_for_missing_file(tmp_path, monkeypatch):
    """不存在的 .md 路径 → FileNotFoundError（不让程序静默继续）。"""
    from core.engine import main as main_mod
    from runtime.load_chapter import load_chapter_safe

    chapters_dir = tmp_path / "chapters"
    chapters_dir.mkdir()
    missing = chapters_dir / "nonexistent.md"
    monkeypatch.setattr(main_mod, "CHAPTERS_ROOT", chapters_dir)

    with pytest.raises(FileNotFoundError):
        load_chapter_safe(missing)


# ─── 3. P0-S1 校验 1：扩展名不是 .md → ValueError ─────────────────────────────


def test_load_chapter_safe_rejects_non_md_extension(tmp_path, monkeypatch):
    """非 .md 文件（malware.exe）→ ValueError（P0-S1 漏点 3）。"""
    from core.engine import main as main_mod
    from runtime.load_chapter import load_chapter_safe

    chapters_dir = tmp_path / "chapters"
    chapters_dir.mkdir()
    evil = chapters_dir / "malware.exe"
    evil.write_text("not a chapter", encoding="utf-8")
    monkeypatch.setattr(main_mod, "CHAPTERS_ROOT", chapters_dir)

    with pytest.raises(ValueError, match=r"\.md"):
        load_chapter_safe(evil)


# ─── 4. P0-S1 校验 2：路径穿越（resolve 后越出 CHAPTERS_ROOT） → ValueError ────


def test_load_chapter_safe_blocks_path_traversal(tmp_path, monkeypatch):
    """../../etc/passwd → resolve 后越出 CHAPTERS_ROOT → ValueError（P0-S1 漏点 2）。"""
    from core.engine import main as main_mod
    from runtime.load_chapter import load_chapter_safe

    chapters_dir = tmp_path / "chapters"
    chapters_dir.mkdir()
    # tmp_path/../<其他> 一定越出 chapters_dir
    outside = tmp_path / "outside.md"
    outside.write_text("hi", encoding="utf-8")
    monkeypatch.setattr(main_mod, "CHAPTERS_ROOT", chapters_dir)

    with pytest.raises(ValueError, match=r"under"):
        load_chapter_safe(outside)


# ─── 5. P0-S1 校验 3：文件 > 1MB → ValueError ─────────────────────────────────


def test_load_chapter_safe_rejects_oversized_file(tmp_path, monkeypatch):
    """文件 > 1MB → ValueError 防 OOM（P0-S1 漏点 4）。"""
    from core.engine import main as main_mod
    from runtime.load_chapter import load_chapter_safe

    chapters_dir = tmp_path / "chapters"
    chapters_dir.mkdir()
    big = chapters_dir / "big.md"
    # 写 1MB+10 字节的内容
    big.write_text("a" * (1_000_001), encoding="utf-8")
    monkeypatch.setattr(main_mod, "CHAPTERS_ROOT", chapters_dir)
    # 紧一点：MAX_CHAPTER_SIZE 默认 1_000_000
    monkeypatch.setattr(main_mod, "MAX_CHAPTER_SIZE", 1_000_000)

    with pytest.raises(ValueError, match=r"large|size"):
        load_chapter_safe(big)


# ─── 6. P0-S1 校验 4：原始路径是 symlink → ValueError ────────────────────────


def test_load_chapter_safe_rejects_symlink(tmp_path, monkeypatch):
    """原始路径 is_symlink() == True → ValueError（P0-S1 漏点 1）。

    Windows 上创建 symlink 需要 admin/developer mode，失败时
    用 monkeypatch 模拟 is_symlink() 返回 True（与 P0-S1 test_main_entry.py 同款 fallback）。
    """
    from core.engine import main as main_mod
    from runtime.load_chapter import load_chapter_safe

    chapters_dir = tmp_path / "chapters"
    chapters_dir.mkdir()
    target = chapters_dir / "real.md"
    target.write_text(
        "```neon\n"
        "id:start\n"
        "node start\n"
        "node end\n"
        "```\n",
        encoding="utf-8",
    )
    sym = chapters_dir / "linked.md"
    try:
        sym.symlink_to(target)
    except (OSError, NotImplementedError):
        # Windows 无 admin/developer mode：mock is_symlink 让该路径报告为 symlink
        real_is_symlink = pathlib.Path.is_symlink

        def fake_is_symlink(self):
            try:
                if str(self.resolve()) == str(sym.resolve()):
                    return True
            except (OSError, RuntimeError):
                pass
            return real_is_symlink(self)

        monkeypatch.setattr(pathlib.Path, "is_symlink", fake_is_symlink)
    monkeypatch.setattr(main_mod, "CHAPTERS_ROOT", chapters_dir)

    with pytest.raises(ValueError, match=r"symlink"):
        load_chapter_safe(sym)


# ─── 7. 不重写校验：校验函数从 core.engine.main 引用同一对象 ─────────────────


def test_load_chapter_safe_reuses_validation_from_main_module():
    """runtime.load_chapter 必须 import 走 core.engine.main 的校验源，
    不能在自己的模块里复制一份路径校验常量 / 函数（防漂移）。

    注意：测试必须在没有 monkeypatch 的状态下进行 —— CHAPTERS_ROOT 是 Path 对象，
    跨测试若被 monkeypatch 改过，load_chapter 导入时绑定的可能不是当前 main 的值。
    我们用 direct identity check on the function object（不会被 monkeypatch 影响）。
    """
    import importlib
    # 重新加载 runtime.load_chapter 以确保它在"无 monkeypatch"状态下被导入
    from core.engine import main as main_mod
    from runtime import load_chapter

    # 暴露一个校验入口（validate_chapter_path 或类似），runtime 必须能拿到同一个对象
    assert hasattr(main_mod, "validate_chapter_path"), (
        "core.engine.main 必须暴露 validate_chapter_path 给 runtime.load_chapter 复用，"
        "禁止在 load_chapter.py 里复制路径校验常量"
    )
    # load_chapter 模块从 main 模块引用 validate_chapter_path（函数对象 identity 不受 monkeypatch 影响）
    assert load_chapter.validate_chapter_path is main_mod.validate_chapter_path, (
        "runtime.load_chapter.validate_chapter_path 必须 === core.engine.main.validate_chapter_path"
    )
    # validate_chapter_path 内部走 main 的 globals()（CHAPTERS_ROOT / MAX_CHAPTER_SIZE）
    # 函数对象的 __globals__['CHAPTERS_ROOT'] 必须 === main_mod.CHAPTERS_ROOT
    assert load_chapter.validate_chapter_path.__globals__["CHAPTERS_ROOT"] is main_mod.CHAPTERS_ROOT
    assert load_chapter.validate_chapter_path.__globals__["MAX_CHAPTER_SIZE"] is main_mod.MAX_CHAPTER_SIZE
