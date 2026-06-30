"""V2-04 · Task 1 — runtime 章节加载包装。

从 src/core/engine/main.py:_load_story 抽取的可复用包装：
- 走 core.engine.main.validate_chapter_path 做 P0-S1 路径校验
  （4 条闸门：symlink / CHAPTERS_ROOT / .md / 1MB 上限）
- 复用 core.engine.main 的 CHAPTERS_ROOT / MAX_CHAPTER_SIZE 常量
  （不重新定义，避免漂移；测试用 monkeypatch 切常量即可）

用途：
- v2-p0 ChapterManager.handle_route_evt 监听 RouteEvt(target="chapterXX")
  → 拼 chapters_root/chapterXX.md → load_chapter_safe(path) → Story
- 单章节场景 main.py 也可直接调用

v2 阶段不重写路径校验——直接 import main 模块的入口。
"""
from __future__ import annotations

from core.engine.ast_nodes import Block as AstBlock, Story
from core.engine.interpreter import (
    extract_neon_blocks,
    parse_block_skeleton,
    parse_block_meta,
    parse_next_decls,
    parse_block_body,
)

# 复用 main 模块的校验入口（单一校验源；测试 monkeypatch 切常量）
from core.engine.main import (  # noqa: F401
    validate_chapter_path,
    CHAPTERS_ROOT,
    MAX_CHAPTER_SIZE,
)


def load_chapter_safe(chapter_path) -> Story:
    """加载章节 .md → Story。

    Args:
        chapter_path: 章节文件路径（str 或 Path）。会先走
            core.engine.main.validate_chapter_path 校验，再解析。

    Returns:
        Story 对象，含所有 neon blocks。

    Raises:
        FileNotFoundError: 路径不存在（p.read_text() 抛）。
        ValueError: 路径校验失败（symlink / 越界 / 扩展名错 / 超大）。
        core.engine.ast_nodes.ParserError: 解析失败。
    """
    # 1. 路径校验：复用 main 模块的 4 条闸门
    validated = validate_chapter_path(chapter_path)

    # 2. 读取 + 解析
    text = validated.read_text(encoding="utf-8")
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
        blocks.append(AstBlock(
            meta=tuple(meta.ids),
            next_table=tuple(next_decls),
            body=tuple(body),
            loc=nb.loc,
        ))
    return Story(blocks=tuple(blocks))
