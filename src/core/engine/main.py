"""v0 引擎进程入口（v0-issue-17）。

v0-issue-17 范围：装配 EngineBus + 加载章节 + 命令循环 + GUI 子进程降级 headless。
v0-issue-19 落地端到端 fixture；v0-issue-18 落地 GUI 进程。

phase2 P0-S1：_load_story 加路径校验（防穿越 + 大小 + 扩展名 + symlink）。
v2-p0 chapter-manager 任务：暴露 validate_chapter_path 给 runtime.load_chapter 复用。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from core.engine.ast_nodes import ParserError
from core.engine.bus import EngineBus
from core.engine.executor import Executor
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

# phase2 P0-S1：章节校验常量
# main.py 位于 src/core/engine/main.py，向上一级到仓库根（src/core/engine → src/core → src → 仓库根）
CHAPTERS_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "chapters"
MAX_CHAPTER_SIZE = 1_000_000  # 1MB — 防恶意 /dev/zero 类大文件触发 OOM


def validate_chapter_path(chapter_path) -> Path:
    """P0-S1 路径校验 4 条（顺序很重要 — 先排 symlink 防 read_text 跟随）：
      1. 原始路径不能是符号链接（防 chapters/foo.md → /etc/shadow）
      2. resolve 后必须位于 CHAPTERS_ROOT 下（防路径穿越 / 绝对路径越界）
      3. 扩展名必须是 .md
      4. 文件大小 ≤ MAX_CHAPTER_SIZE（防 OOM）

    Returns:
        校验通过 + resolve 后的绝对 Path。

    Raises:
        ValueError: 校验失败（含具体原因）。
        FileNotFoundError: 文件不存在（由 p.stat() / p.read_text() 抛出）。
    """
    raw = Path(chapter_path)

    # 1. 排 symlink（在 resolve 之前，避免 read_text 跟随到任意位置）
    if raw.is_symlink():
        raise ValueError(f"chapter must not be a symlink: {raw}")

    p = raw.resolve()

    # 2. 必须在 CHAPTERS_ROOT 下
    try:
        p.relative_to(CHAPTERS_ROOT.resolve())
    except ValueError:
        raise ValueError(f"chapter must be under {CHAPTERS_ROOT}: {p}")

    # 3. 必须是 .md
    if p.suffix != ".md":
        raise ValueError(f"chapter must be .md: {p}")

    # 4. 大小限制
    if p.stat().st_size > MAX_CHAPTER_SIZE:
        raise ValueError(f"chapter too large (>{MAX_CHAPTER_SIZE} bytes): {p}")

    return p


def _load_story(chapter_path: str):
    """加载章节 → Story。

    phase2 P0-S1：路径校验走 validate_chapter_path（4 条闸门）。
    复用入口（不重写校验）：runtime/load_chapter.py 也调用 validate_chapter_path。
    """
    p = validate_chapter_path(chapter_path)
    text = p.read_text(encoding="utf-8")
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
    """核心入口：装配 EngineBus + 加载章节 + ChapterManager 跨章节 + GUI 降级。

    v2-p0 chapter-manager 改造：替换 Executor(story, bus).run() 为
    ChapterManager(CHAPTERS_ROOT, bus, initial_story=story).run()。
    ChapterManager 负责：
    - 跑 initial_story（第一个章节）
    - 监听 bus 上的 RouteEvt → 加载新章节 → 跑 executor
    - 收到 ChapterEndEvt → 退出
    - 跨章节状态共享（shared_state GameState）

    CLI 行为保持兼容：单章节（如 chapter01.md 无跨章节路由）走 initial_story + ChapterEndEvt → 退出 0。
    """
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

    # 4. 加载第一个章节
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

    # 5. v2-p0：构造 ChapterManager 处理初始章节 + 跨章节路由
    from runtime.chapter_manager import ChapterManager
    try:
        mgr = ChapterManager(CHAPTERS_ROOT, bus, initial_story=story)
        mgr.run()
    except (FileNotFoundError, ValueError, RuntimeError, NotImplementedError) as e:
        try:
            bus.put_evt(LogEvt(
                level="error",
                message=f"chapter manager failed: {e}",
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
