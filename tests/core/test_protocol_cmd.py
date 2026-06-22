"""v0-issue-3 命令 schema dataclass 测试。

按 issue #25 acceptance criteria 验证 3 条命令（GUI→Engine）的 round-trip
+ parse_cmd 分发 + 错误处理。
"""
import sys

import pytest

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")


# 1. LoadChapterCmd round-trip
def test_load_chapter_cmd_round_trip():
    from core.engine.protocol import LoadChapterCmd

    cmd = LoadChapterCmd(path="chapters/chapter01.md")
    d = cmd.to_dict()
    assert d == {"cmd": "load_chapter", "path": "chapters/chapter01.md"}

    restored = LoadChapterCmd.from_dict(d)
    assert restored == cmd


# 2. UserInputCmd round-trip
def test_user_input_cmd_round_trip():
    from core.engine.protocol import UserInputCmd

    cmd = UserInputCmd(value="平静")
    d = cmd.to_dict()
    assert d == {"cmd": "user_input", "value": "平静"}

    restored = UserInputCmd.from_dict(d)
    assert restored == cmd


# 3. ShutdownCmd round-trip（空字段）
def test_shutdown_cmd_round_trip():
    from core.engine.protocol import ShutdownCmd

    cmd = ShutdownCmd()
    d = cmd.to_dict()
    assert d == {"cmd": "shutdown"}

    restored = ShutdownCmd.from_dict(d)
    assert restored == cmd


# 4. parse_cmd 按 cmd 字段分发
def test_parse_cmd_dispatches_by_cmd_field():
    from core.engine.protocol import (
        LoadChapterCmd, UserInputCmd, ShutdownCmd, parse_cmd,
    )

    a = parse_cmd({"cmd": "load_chapter", "path": "x.md"})
    assert isinstance(a, LoadChapterCmd)
    assert a.path == "x.md"

    b = parse_cmd({"cmd": "user_input", "value": "hi"})
    assert isinstance(b, UserInputCmd)
    assert b.value == "hi"

    c = parse_cmd({"cmd": "shutdown"})
    assert isinstance(c, ShutdownCmd)


# 5. 未知 cmd 抛 ValueError
def test_parse_cmd_unknown_raises_value_error():
    from core.engine.protocol import parse_cmd

    with pytest.raises(ValueError):
        parse_cmd({"cmd": "fly_to_mars"})


# 6. 缺 cmd 字段抛 ValueError
def test_parse_cmd_missing_cmd_raises_value_error():
    from core.engine.protocol import parse_cmd

    with pytest.raises(ValueError):
        parse_cmd({"path": "x.md"})


# 7. 字段缺失抛 ValueError
def test_from_dict_missing_field_raises_value_error():
    from core.engine.protocol import LoadChapterCmd

    with pytest.raises(ValueError):
        LoadChapterCmd.from_dict({"cmd": "load_chapter"})


# 8. 字段类型错抛 ValueError
def test_from_dict_wrong_type_raises_value_error():
    from core.engine.protocol import LoadChapterCmd

    # path 应该是 str，传 int
    with pytest.raises(ValueError):
        LoadChapterCmd.from_dict({"cmd": "load_chapter", "path": 42})
