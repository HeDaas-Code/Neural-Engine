"""v0 §11 关键不变量守护测试（v0-issue-20 HITL）。

按 ADR-0001 §11 列出的 10 条不变量，每条写一个 pytest 用例。

执行机制：
- 1-9: 由对应模块的单测已覆盖（test_block_meta / test_executor_decorator / test_next_decls / test_if_parse / ...）
- 10: 用 subprocess 跑 grep 守护（不在 pytest 函数里做 import 搜索，避免假阳）
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_invariant_1_namespace_separation():
    """§11 #1: ID 与变量命名空间严格分离。

    已由 test_block_meta.py 覆盖：解析器在 body 里遇到 id:xxx 必须抛 ParserError。
    """
    # Cross-check by running the existing test
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/core/test_block_meta.py", "-q", "--no-header"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert r.returncode == 0, f"block_meta 测试失败:\n{r.stdout}\n{r.stderr}"


def test_invariant_2_block_scope_no_inheritance():
    """§11 #2: @ 修饰器状态不跨块继承。

    已由 test_executor_decorator.py::test_block_scoped_state_cleared_on_new_block 覆盖。
    """
    r = subprocess.run(
        [sys.executable, "-m", "pytest",
         "tests/core/test_executor_decorator.py::test_block_scoped_state_cleared_on_new_block",
         "-v", "--no-header"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert r.returncode == 0, f"decorator block-scope 测试失败:\n{r.stdout}"


def test_invariant_3_next_not_string_literal():
    """§11 #3: NEXT 是 next 变量表项的引用，不是字符串。

    守护：grep -r '"NEXT"' src/ 应 0 命中。
    """
    r = subprocess.run(
        ["grep", "-r", "-E", '"NEXT"', "src/", "--include=*.py"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert r.returncode == 1, (
        f"§11 #3 违规：发现 NEXT 字符串字面量\n{r.stdout}"
    )


def test_invariant_4_single_next_auto_multi_explicit():
    """§11 #4: 单 next 自动设 NEXT，多 next 必须显式。

    已由 test_next_decls.py 覆盖：单 next 简写归一化 + 多 next 互斥校验。
    """
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/core/test_next_decls.py", "-q", "--no-header"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert r.returncode == 0, f"next_decls 测试失败:\n{r.stdout}"


def test_invariant_5_endx_unified():
    """§11 #5: endX 同时承担结局标记 + 路由目标 + 玩家路径记录。

    已由 test_block_meta.py 覆盖：id:endX:chapterYY 解析为 IdEnd(x, route_chapter)。
    """
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/core/test_block_meta.py", "-q", "--no-header"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert r.returncode == 0, f"block_meta 测试失败:\n{r.stdout}"


def test_invariant_6_bus_json_only():
    r"""§11 #6: 数据总线消息一律 JSON dict。

    守护：grep -r 'pickle|msgpack' src/ 应 0 命中。
    """
    r = subprocess.run(
        ["grep", "-r", "-E", "pickle|msgpack", "src/", "--include=*.py"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert r.returncode == 1, (
        f"§11 #6 违规：发现 pickle/msgpack\n{r.stdout}"
    )


def test_invariant_7_single_vs_multi_next_mutex():
    """§11 #7: 单 next 简写与多 next 完整互斥。

    已由 test_next_decls.py 覆盖：混合写法 + 多 next 时简写 抛 ParserError。
    """
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/core/test_next_decls.py", "-q", "--no-header"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert r.returncode == 0, f"next_decls 测试失败:\n{r.stdout}"


def test_invariant_8_full_line_comment_only():
    """§11 #8: v0 仅支持整行注释（行首 #）。

    已由 test_block_body.py 覆盖：行尾注释应抛 ParserError。
    """
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/core/test_block_body.py", "-q", "--no-header"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert r.returncode == 0, f"block_body 测试失败:\n{r.stdout}"


def test_invariant_9_arrow_left_var_right_id():
    """§11 #9: `<-` 冒号右边是 ID 命名空间，左边是变量命名空间。

    已由 test_next_decls.py 覆盖：var_name / target_id 字段分离。
    """
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/core/test_next_decls.py", "-q", "--no-header"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert r.returncode == 0, f"next_decls 测试失败:\n{r.stdout}"


def test_invariant_10_branch_item_omit_node():
    """§11 #10: 分支项内允许省略 node 前缀。

    已由 test_if_parse.py 覆盖：branch item `node xxx` / `echo xxx` / `xxx` 各种省略形式。
    """
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/core/test_if_parse.py", "-q", "--no-header"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert r.returncode == 0, f"if_parse 测试失败:\n{r.stdout}"


# ─────────────────────────────────────────────────────────────────────
# PRD 硬约束（额外守护）
# ─────────────────────────────────────────────────────────────────────


def test_no_todo_or_fixme_in_src():
    """PRD 硬约束：禁止 TODO/FIXME 残留。

    守护：grep -r 'TODO|FIXME' src/ 应 0 命中。
    """
    r = subprocess.run(
        ["grep", "-r", "-E", "TODO|FIXME", "src/", "--include=*.py"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert r.returncode == 1, (
        f"PRD 硬约束违规：发现 TODO/FIXME\n{r.stdout}"
    )