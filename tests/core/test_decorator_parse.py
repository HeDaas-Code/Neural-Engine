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


# ─── D2 修法: G5 结构化参数 `[item1,item2,...]` 列表语法 ────────────────────


class TestStructuredArgs:
    """D2 修法 (ADR-0004 G5): 修饰器参数支持 `[item1,item2,...]` 结构化列表语法。

    新语法:
        @style text:[rgb:red,Px:12]
        @style text:[rgb:red,Px:12], vol:0.5
        @style [bgm:rain.mp3,vol:0.5]

    解析规则:
    - `[...]` 内的逗号不作为顶层分隔符
    - `[...]` 内的内容作为整体保留在 value 字符串中
    - 未闭合的 `[` 抛 ParserError
    - 嵌套 `[a:[1,2,3]]` 也支持 (深度计数)
    """

    def test_单结构化参数_保留方括号内容(self):
        """`@style text:[rgb:red,Px:12]` → 整个 `[...]` 作为 value 保留。"""
        line = "@style text:[rgb:red,Px:12]\n"
        result = parse_decorator(line, lineno=10)
        assert isinstance(result, DecoratorCall)
        assert result.name == "style"
        assert result.args == ("text:[rgb:red,Px:12]",)

    def test_结构化参数_加_普通参数(self):
        """混合: 结构化参数后接普通参数, 用顶层逗号分隔。"""
        line = "@style text:[rgb:red,Px:12], vol:0.5\n"
        result = parse_decorator(line, lineno=10)
        assert isinstance(result, DecoratorCall)
        assert result.name == "style"
        # 顶层逗号分隔, [] 内逗号不切
        assert result.args == ("text:[rgb:red,Px:12]", "vol:0.5")

    def test_普通参数_加_结构化参数(self):
        """混合: 普通参数在前, 结构化参数在后。"""
        line = "@style vol:0.5, text:[rgb:red,Px:12]\n"
        result = parse_decorator(line, lineno=10)
        assert isinstance(result, DecoratorCall)
        assert result.args == ("vol:0.5", "text:[rgb:red,Px:12]")

    def test_整体结构化参数(self):
        """`@style [bgm:rain.mp3,vol:0.5]` → 整个 arg 是结构化值 (无 key 前缀)。"""
        line = "@style [bgm:rain.mp3,vol:0.5]\n"
        result = parse_decorator(line, lineno=10)
        assert isinstance(result, DecoratorCall)
        assert result.args == ("[bgm:rain.mp3,vol:0.5]",)

    def test_嵌套方括号(self):
        """嵌套: `nested:[a:[1,2,3],b:4]` → 整体作为一个 arg, 深度计数正确。"""
        line = "@style nested:[a:[1,2,3],b:4]\n"
        result = parse_decorator(line, lineno=10)
        assert isinstance(result, DecoratorCall)
        assert result.args == ("nested:[a:[1,2,3],b:4]",)

    def test_空方括号(self):
        """空结构: `text:[]` → 保留空方括号。"""
        line = "@style text:[]\n"
        result = parse_decorator(line, lineno=10)
        assert isinstance(result, DecoratorCall)
        assert result.args == ("text:[]",)

    def test_未闭合方括号_抛错(self):
        """未闭合 `[` → ParserError。"""
        line = "@style text:[rgb:red,Px:12\n"
        with pytest.raises(ParserError):
            parse_decorator(line, lineno=10)

    def test_无嵌套_时_回退为_普通_kv_解析(self):
        """回归: 无 `[]` 时仍按 v0 行为 (按顶层逗号切)。"""
        line = "@style bgm:rain.mp3, vol:0.5\n"
        result = parse_decorator(line, lineno=10)
        assert isinstance(result, DecoratorCall)
        assert result.args == ("bgm:rain.mp3", "vol:0.5")

    def test_结构化_stop_语义(self):
        """`@style text` (裸 key) → DecoratorStop (回归: 无 `[]` 影响 stop 判定)。"""
        line = "@style text\n"
        result = parse_decorator(line, lineno=10)
        assert isinstance(result, DecoratorStop)
        assert result.name == "style"
        assert result.key == "text"
