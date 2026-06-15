"""v0 §8 MVP 表逐条勾测试（v0-issue-20 HITL）。

按 ADR-0001 §8 MVP 表的 18 条特性，每条写一个 pytest 用例，
关联到对应模块测试函数 + 显式断言。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_pytest(test_path: str, *extra_args: str) -> tuple[int, str, str]:
    """Run pytest on a specific file and return (returncode, stdout, stderr)."""
    r = subprocess.run(
        [sys.executable, "-m", "pytest", test_path, *extra_args],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    return r.returncode, r.stdout, r.stderr


# ── 已实现项（11 条）────────────────────────────────────────────────


def test_mvp_001_id_parsing():
    """§8 #1: id:xxx / id:start / id:endX / id:endX:chapterYY 解析。"""
    rc, out, err = _run_pytest("tests/core/test_block_meta.py")
    assert rc == 0, f"block_meta 测试失败:\n{out}\n{err}"


def test_mvp_002_single_next_shorthand():
    """§8 #2: next:yyy 单 next 简写。"""
    rc, out, err = _run_pytest("tests/core/test_next_decls.py")
    assert rc == 0, f"next_decls 测试失败:\n{out}\n{err}"


def test_mvp_003_multi_next_full():
    """§8 #3: xxx<-next:yyy 多 next 完整声明。"""
    rc, out, err = _run_pytest("tests/core/test_next_decls.py")
    assert rc == 0, f"next_decls 测试失败:\n{out}\n{err}"


def test_mvp_004_single_next_implicit_ref():
    """§8 #4: 单 next 简写时 NEXT 隐式 = ref(ID)。"""
    # executor nodes 测 NEXT 跳转 → c1 块
    rc, out, err = _run_pytest(
        "tests/core/test_executor_nodes.py",
        "-q", "--no-header", "-k", "test_bare_next_block_jumps_to_target",
    )
    assert rc == 0, f"executor_nodes 测试失败:\n{out}"


def test_mvp_005_multi_next_null_explicit():
    """§8 #5: 多 next 时 NEXT = null，待显式。"""
    rc, out, err = _run_pytest(
        "tests/core/test_executor_nodes.py",
        "-q", "--no-header", "-k", "test_next_id_sets_next_target",
    )
    assert rc == 0, f"executor_nodes 测试失败:\n{out}"


def test_mvp_006_node_start_end():
    """§8 #6: node start / node end。"""
    rc, out, err = _run_pytest("tests/core/test_block_skeleton.py")
    assert rc == 0, f"block_skeleton 测试失败:\n{out}"


def test_mvp_007_text_line_push():
    """§8 #7: 普通文本行推送 GUI。"""
    rc, out, err = _run_pytest(
        "tests/core/test_executor_nodes.py",
        "-q", "--no-header", "-k", "text",
    )
    assert rc == 0, f"executor_nodes 测试失败:\n{out}"


def test_mvp_008_node_in_user_input():
    """§8 #8: node in ->var 等待用户输入。"""
    rc, out, err = _run_pytest(
        "tests/core/test_executor_nodes.py",
        "-q", "--no-header", "-k", "test_in_node",
    )
    assert rc == 0, f"executor_nodes 测试失败:\n{out}"


def test_mvp_009_node_echo_var():
    """§8 #9: node echo var 输出变量。"""
    rc, out, err = _run_pytest(
        "tests/core/test_executor_nodes.py",
        "-q", "--no-header", "-k", "test_echo_node",
    )
    assert rc == 0, f"executor_nodes 测试失败:\n{out}"


def test_mvp_010_node_next_id():
    """§8 #10: node next_id 显式跳转。"""
    rc, out, err = _run_pytest(
        "tests/core/test_executor_nodes.py",
        "-q", "--no-header", "-k", "test_next_id",
    )
    assert rc == 0, f"executor_nodes 测试失败:\n{out}"


def test_mvp_017_full_line_comment():
    """§8 #17: 整行注释 (#)。"""
    rc, out, err = _run_pytest("tests/core/test_block_skeleton.py")
    assert rc == 0, f"block_skeleton 测试失败:\n{out}"


# ── 打桩项（7 条）────────────────────────────────────────────────────


def test_mvp_011_if_binary_stub():
    """§8 #11: node if cond[a,b] 二元条件（打桩）。"""
    rc, out, err = _run_pytest(
        "tests/core/test_executor_if.py",
        "-q", "--no-header", "-k", "test_binary_if_stub",
    )
    assert rc == 0, f"executor_if 测试失败:\n{out}"


def test_mvp_012_if_multi_stub():
    """§8 #12: node if var [1:a,2:b,3:c] 多元条件（打桩）。"""
    rc, out, err = _run_pytest(
        "tests/core/test_executor_if.py",
        "-q", "--no-header", "-k", "test_multi_if_stub",
    )
    assert rc == 0, f"executor_if 测试失败:\n{out}"


def test_mvp_013_if_shortcut_stub():
    """§8 #13: node [a?b:c] 简略二元（打桩）。"""
    rc, out, err = _run_pytest(
        "tests/core/test_executor_if.py",
        "-q", "--no-header", "-k", "test_shortcut_if_stub",
    )
    assert rc == 0, f"executor_if 测试失败:\n{out}"


def test_mvp_014_branch_item_omit_node():
    """§8 #14: 分支项内省略 node 前缀（打桩）。"""
    rc, out, err = _run_pytest("tests/core/test_if_parse.py")
    assert rc == 0, f"if_parse 测试失败:\n{out}"


def test_mvp_015_decorator_call():
    """§8 #15: @xxx key:val 修饰器调用（打桩）。"""
    rc, out, err = _run_pytest("tests/core/test_decorator_parse.py")
    assert rc == 0, f"decorator_parse 测试失败:\n{out}"


def test_mvp_016_decorator_stop():
    """§8 #16: @xxx key 休止符（打桩）。"""
    rc, out, err = _run_pytest(
        "tests/core/test_executor_decorator.py",
        "-q", "--no-header", "-k", "test_decorator_stop",
    )
    assert rc == 0, f"executor_decorator 测试失败:\n{out}"


def test_mvp_018_route_event():
    """§8 #18: 章节路由（id:endX:chapterYY 触发 route 事件）（打桩）。"""
    rc, out, err = _run_pytest(
        "tests/core/test_executor_nodes.py",
        "-q", "--no-header", "-k", "test_empty_next_with_end_marker_chapter_emits_route",
    )
    assert rc == 0, f"executor_nodes 测试失败:\n{out}"


# ── 端到端（§8 MVP 表的"v0 唯一跑通路径"）─────────────────────────────


def test_mvp_e2e_chapter01_path():
    """§8 v0 唯一跑通路径：node in ->p_tall → 输入 → node echo p_tall → node end。"""
    rc, out, err = _run_pytest("tests/integration/test_echo_path.py")
    assert rc == 0, f"端到端路径测试失败:\n{out}"