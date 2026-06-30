"""v0 引擎进程入口（v0-issue-17）。

v0-issue-17 范围：装配 EngineBus + 加载章节 + 命令循环 + GUI 子进程降级 headless。
v0-issue-19 落地端到端 fixture；v0-issue-18 落地 GUI 进程。
v2-p0 (V2-04): 暴露 validate_chapter_path + CHAPTERS_ROOT + MAX_CHAPTER_SIZE
  供 runtime.load_chapter 复用 P0-S1 4 条闸门（symlink / 越界 / 扩展名 / 大小）。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from core.engine.ast_nodes import ParserError
from core.engine.bus import EngineBus
from core.engine.interpreter import (
    extract_neon_blocks,
    parse_block_skeleton,
    parse_block_meta,
    parse_next_decls,
    parse_block_body,
)
from core.engine.protocol import LogEvt

# 用于测试时替换的可观察变量
_last_bus = None

# ─── v2-p0 P0-S1 路径校验常量（供 runtime.load_chapter 复用） ────────────────
# CHAPTERS_ROOT：章节文件根目录（CLI 启动时按相对路径解析；测试用 monkeypatch 切）
CHAPTERS_ROOT: Path = Path("chapters")
# MAX_CHAPTER_SIZE：单章节文件大小上限（字节，默认 1MB 防 OOM）
MAX_CHAPTER_SIZE: int = 1_000_000


def validate_chapter_path(chapter_path) -> Path:
    """P0-S1 章节路径校验（4 条闸门）。

    单一校验源——供 runtime.load_chapter.load_chapter_safe 复用，
    禁止在其他模块复制本函数（防漂移）。

    Args:
        chapter_path: 章节文件路径（str / Path）。

    Returns:
        校验通过后的绝对 Path（resolved）。

    Raises:
        ValueError: 任一闸门失败，含具体原因（symlink / under / .md / large|size）。
    """
    p = Path(chapter_path)
    # 闸门 1：拒绝 symlink（防指向 CHAPTERS_ROOT 外的恶意文件）
    if p.is_symlink():
        raise ValueError(
            f"chapter path {p!s} is a symlink, rejected by P0-S1 security gate"
        )
    # 闸门 2：resolve 后必须在 CHAPTERS_ROOT 下（防 ../../etc/passwd 穿越）
    resolved = p.resolve()
    root_resolved = CHAPTERS_ROOT.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        raise ValueError(
            f"chapter path {p!s} (resolved {resolved!s}) is not under "
            f"CHAPTERS_ROOT {root_resolved!s}"
        ) from None
    # 闸门 3：扩展名必须是 .md（防 malware.exe / .py 等）
    if p.suffix != ".md":
        raise ValueError(
            f"chapter path {p!s} must have .md extension, got suffix {p.suffix!r}"
        )
    # 闸门 4：文件大小不超过 MAX_CHAPTER_SIZE（防 OOM）
    if p.exists():
        size = p.stat().st_size
        if size > MAX_CHAPTER_SIZE:
            raise ValueError(
                f"chapter file {p!s} too large: {size} bytes "
                f"(max {MAX_CHAPTER_SIZE} bytes)"
            )
    return resolved


def _load_story(chapter_path: str):
    """加载章节 → Story。"""
    text = Path(chapter_path).read_text(encoding="utf-8")
    blocks_text = extract_neon_blocks(text)
    blocks = []
    for nb in blocks_text:
        skel, _ = parse_block_skeleton(nb.content, lineno=nb.lineno)
        meta = parse_block_meta(skel.meta_lines, start_lineno=nb.lineno)
        next_decls = parse_next_decls(skel.meta_lines, start_lineno=nb.lineno)
        body = parse_block_body(
            skel.body_lines,
            start_lineno=nb.lineno,
            block_meta=meta,
            next_table=next_decls,
        )
        from core.engine.ast_nodes import Block as AstBlock
        blocks.append(AstBlock(
            meta=tuple(meta.ids),
            next_table=tuple(next_decls),
            body=tuple(body),
            loc=nb.loc,
        ))
    from core.engine.ast_nodes import Story
    return Story(blocks=tuple(blocks))


def _try_spawn_gui() -> subprocess.Popen | None:
    """尝试 spawn GUI 子进程。失败（v0-issue-18 尚未落地）返回 None。"""
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "runtime.gui.main"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return proc
    except FileNotFoundError:
        return None


def main(chapter_path: str) -> int:
    """核心入口：装配 EngineBus + 加载章节 + 命令循环 + GUI 降级。"""
    global _last_bus

    # 1. 尝试 spawn GUI（v0-issue-18 落地前容错）
    gui_proc = _try_spawn_gui()

    # 2. 创建 EngineBus
    bus = EngineBus(use_multiprocessing=True)
    _last_bus = bus  # 测试用

    # 3. GUI 不可用降级
    if gui_proc is None:
        try:
            bus.put_evt(LogEvt(
                level="warning",
                message="GUI not available, running headless",
            ))
        except Exception:
            pass

    # 4. 加载章节
    try:
        story = _load_story(chapter_path)
    except (FileNotFoundError, ParserError, ValueError) as e:
        try:
            bus.put_evt(LogEvt(
                level="error",
                message=f"failed to load chapter {chapter_path!r}: {e}",
            ))
        except Exception:
            pass
        bus.close()
        if gui_proc is not None:
            gui_proc.terminate()
            try:
                gui_proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                gui_proc.kill()
        return 1

    # 5. 构造 ChapterManager 跑（v2-p0: 支持跨章节 RouteEvt 路由）
    try:
        from runtime.chapter_manager import ChapterManager
        mgr = ChapterManager(
            chapters_root=CHAPTERS_ROOT,
            bus=bus,
            initial_story=story,
        )
        mgr.run()
    except (ValueError, RuntimeError, NotImplementedError, FileNotFoundError) as e:
        try:
            bus.put_evt(LogEvt(
                level="error",
                message=f"executor failed: {e}",
            ))
        except Exception:
            pass
        bus.close()
        if gui_proc is not None:
            gui_proc.terminate()
            try:
                gui_proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                gui_proc.kill()
        return 1

    # 6. 清理
    bus.close()
    if gui_proc is not None:
        gui_proc.terminate()
        try:
            gui_proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            gui_proc.kill()
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python -m core.engine.main <chapter.md>", file=sys.stderr)
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
