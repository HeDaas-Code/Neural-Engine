"""v0 引擎进程入口（v0-issue-17）。

v0-issue-17 范围：装配 EngineBus + 加载章节 + 命令循环 + GUI 子进程降级 headless。
v0-issue-19 落地端到端 fixture；v0-issue-18 落地 GUI 进程。
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

    # 5. 构造 Executor 跑
    try:
        exe = Executor(story, bus)
        exe.run()
    except (ValueError, RuntimeError, NotImplementedError) as e:
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
