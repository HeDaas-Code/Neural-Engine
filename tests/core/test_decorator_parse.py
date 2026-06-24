"""v0-issue-12 修饰器解析测试。

按 issue #34 acceptance criteria 验证 parse_decorator。
"""
import re
import sys

import pytest

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f"{REPO_ROOT}/src")

from core.engine.interpreter import parse_decorator  # noqa: E402
from core.engine.ast_nodes import (  # noqa: E402
    DecoratorCall, DecoratorStop, ParserError,
)


# 1. 单 key:val
def test_decorator_call_single_kv_arg():
    line = "@style bgm:rain.mp3\n"
    result = parse_decorator(line, lineno=10)
    assert isinstance(result, DecoratorCall)
    assert result.name == "style"
    assert result.args == ("bgm:rain.mp3",)


# 2. 多 key:val
def test_decorator_call_multi_kv_args():
    line = "@style bgm:rain.mp3, vol:0.5\n"
    result = parse_decorator(line, lineno=10)
    assert isinstance(result, DecoratorCall)
    assert result.name == "style"
    assert result.args == ("bgm:rain.mp3", "vol:0.5")


# 3. 单裸 key → stop
def test_decorator_stop_single_bare_key():
    line = "@style bgm\n"
    result = parse_decorator(line, lineno=10)
    assert isinstance(result, DecoratorStop)
    assert result.name == "style"
    assert result.key == "bgm"


# 4. 缺名
def test_decorator_empty_name_raises():
    line = "@\n"
    with pytest.raises(ParserError):
        parse_decorator(line, lineno=10)


# 5. 非法名
def test_decorator_invalid_name_raises():
    line = "@X-Y args\n"
    with pytest.raises(ParserError):
        parse_decorator(line, lineno=10)


# 6. 裸 @ 无 args → stop 空 key
def test_decorator_no_args_returns_stop_empty():
    line = "@style\n"
    result = parse_decorator(line, lineno=10)
    # 无 args 时按 issue body 行为——可视为 stop 空 key
    assert isinstance(result, DecoratorStop)
    assert result.name == "style"
    assert result.key == "" or result.key is None
