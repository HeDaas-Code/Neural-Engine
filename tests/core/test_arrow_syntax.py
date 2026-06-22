"""ADR-0004 G1/G2 语法对齐测试：← 和 → 箭头符号容忍。

验证新旧两种箭头都能正确解析。
"""
import pytest

from core.engine.interpreter import (  # noqa: E402
    parse_block_skeleton, parse_block_meta, parse_block_body,
    BlockMeta,
)
from core.engine.ast_nodes import In, IdMeta


def _empty_meta(lineno=1):
    """构造一个最小 BlockMeta（只有一个 id:start）。"""
    return BlockMeta(ids=[IdMeta(id="start", lineno=lineno)], start_lineno=lineno)


class TestG1NextArrow:
    """G1: next 声明 ← 符号。"""

    def test_新箭头_单_next(self):
        content = "id:start\nn2 ← next : cn2\nnode start\nnode end\n"
        skel, _ = parse_block_skeleton(content, lineno=1)
        from core.engine.interpreter import parse_next_decls
        decls = parse_next_decls(skel.meta_lines, 1)
        assert len(decls) == 1
        assert decls[0].var_name == "n2"
        assert decls[0].target_id == "cn2"

    def test_新箭头_无空格(self):
        content = "id:start\nn2←next:cn2\nnode start\nnode end\n"
        skel, _ = parse_block_skeleton(content, lineno=1)
        from core.engine.interpreter import parse_next_decls
        decls = parse_next_decls(skel.meta_lines, 1)
        assert len(decls) == 1
        assert decls[0].var_name == "n2"
        assert decls[0].target_id == "cn2"

    def test_新箭头_多next(self):
        content = "id:c1\nt_a ← next : ca\nt_b ← next : cb\nnode start\nnode end\n"
        skel, _ = parse_block_skeleton(content, lineno=1)
        from core.engine.interpreter import parse_next_decls
        decls = parse_next_decls(skel.meta_lines, 1)
        assert len(decls) == 2
        assert decls[0].var_name == "t_a"
        assert decls[0].target_id == "ca"
        assert decls[1].var_name == "t_b"
        assert decls[1].target_id == "cb"

    def test_旧箭头_仍兼容(self):
        content = "id:start\nt_a <- next : ca\nnode start\nnode end\n"
        skel, _ = parse_block_skeleton(content, lineno=1)
        from core.engine.interpreter import parse_next_decls
        decls = parse_next_decls(skel.meta_lines, 1)
        assert len(decls) == 1
        assert decls[0].var_name == "t_a"
        assert decls[0].target_id == "ca"


class TestG2InArrow:
    """G2: node in → 符号。"""

    def test_新箭头_in(self):
        content = "id:start\nnode start\nnode in → mood\nnode end\n"
        skel, _ = parse_block_skeleton(content, lineno=1)
        meta = parse_block_meta(skel.meta_lines, 1)
        body = parse_block_body(skel.body_lines, 1, block_meta=meta)
        in_nodes = [n for n in body if isinstance(n, In)]
        assert len(in_nodes) == 1
        assert in_nodes[0].var == "mood"

    def test_旧箭头_in_仍兼容(self):
        content = "id:start\nnode start\nnode in -> mood\nnode end\n"
        skel, _ = parse_block_skeleton(content, lineno=1)
        meta = parse_block_meta(skel.meta_lines, 1)
        body = parse_block_body(skel.body_lines, 1, block_meta=meta)
        in_nodes = [n for n in body if isinstance(n, In)]
        assert len(in_nodes) == 1
        assert in_nodes[0].var == "mood"
