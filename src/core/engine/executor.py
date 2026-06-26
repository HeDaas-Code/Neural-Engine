"""v0/v1 引擎执行器（Executor）。

v0-issue-13 落地 GameState + Executor 骨架 + MemoryEventSink（mock sink），
不依赖 EngineBus——通过 EventSink Protocol 抽象隔离。

v0-issue-14..16 逐步实现节点调度。
v1 (ADR-0004): _execute_if 接入 ExprDispatcher 真求值。
v2-p0 chapter-manager: Executor.__init__ 接受 state: GameState | None = None
    （V2-04 · OQ-3 决策）—— 跨章节状态共享，ChapterManager 跨章节跳转时
    复用同一 GameState 让 vars 跨章节保留。
v2-p0 save-load (V2-06 · EP-09):
    - GameState 加 `current_block_id` 字段 + `to_dict()` / `from_dict()`
    - Executor.run() 入口 / _next_block 后置更新 current_block_id
    - D2 决策：to_dict 输出 `version: 1` + `vars/path/current_block_id` 字段
v2-p0 save-load (V2-07 · EP-11):
    - Executor.__init__ 接受 save_manager: SaveManager | None = None
    - Executor.run_block 处理 In 节点时拦截 SaveCmd / LoadCmd
      （在 sink.get_cmd() 返回值上做 dispatch）
    - SaveCmd(slot) → SaveManager.save → 发 SaveAckEvt
    - LoadCmd(slot) → SaveManager.load → 替换 self.state → 发 LoadAckEvt
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from core.engine.ast_nodes import (
    Story, Block, Start, End, IdMeta, IdEnd,
    Text, In, Echo, NextId, If, Branch, CallExpression, NextDecl,
    DecoratorCall, DecoratorStop,
    VAR_KIND, EXPR_KIND, BOOL_EXPR_KIND,
)
from core.engine.protocol import (
    RouteEvt, ChapterEndEvt,
    TextEvt, PromptInputEvt, UserInputCmd,
    SaveCmd, LoadCmd, SaveAckEvt, LoadAckEvt,
    DecoratorEvt, LogEvt,
)
from core.engine.expr import ExprDispatcher, ExprError


class EventSink(Protocol):
    """事件 sink 抽象接口（v0-issue-13 引入，v0-issue-17 替换为 EngineBus）。"""
    def put_evt(self, evt) -> None: ...
    def get_cmd(self): ...  # v0-issue-14 引入；返回 None 表示无输入


class MemoryEventSink:
    """测试用内存事件 sink——累积所有事件。"""

    def __init__(self):
        self.events: list = []

    def put_evt(self, evt) -> None:
        self.events.append(evt)

    def get_cmd(self):  # 默认无输入
        return None


class MemoryInputSink(MemoryEventSink):
    """测试用输入 sink——按预设顺序消费 UserInputCmd。"""

    def __init__(self, inputs: list[str] = None):
        super().__init__()
        self._inputs = list(inputs) if inputs else []
        self._idx = 0

    def get_cmd(self):
        if self._idx < len(self._inputs):
            v = self._inputs[self._idx]
            self._idx += 1
            return UserInputCmd(value=v)
        return None


# ─── 存档支持：当前支持的存档版本常量 ─────────────────────────────────────────
# v3+ 升级时写迁移函数（from_dict 检测 version 字段，不匹配抛 ValueError）
GAMESTATE_SAVE_VERSION: int = 1


@dataclass
class GameState:
    """执行期状态（v0 全字符串变量）。

    v2-p0 save-load (V2-06 · EP-09) 扩展：
    - `current_block_id`: str | None  —— 当前所在块 id（存档恢复用）
    - `to_dict()`: 序列化为 dict（含 `version: 1` + vars/path/current_block_id）
    - `from_dict(d)`: 类方法，反序列化恢复（带 version 校验）
    """
    vars: dict = field(default_factory=dict)
    path: list = field(default_factory=list)
    next_table: dict = field(default_factory=dict)
    current_block_id: str | None = None  # v2 新增：存档恢复锚点

    def to_dict(self) -> dict:
        """序列化为 dict（D2 决策：复用 protocol.py JSON 模式 + 版本字段）。

        Returns:
            dict 形如 `{"version": 1, "vars": {...}, "path": [...], "current_block_id": "..."}`
            - `vars` / `path` 用防御性拷贝，外部修改不影响 GameState
        """
        return {
            "version": GAMESTATE_SAVE_VERSION,
            "vars": dict(self.vars),
            "path": list(self.path),
            "current_block_id": self.current_block_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GameState":
        """从 dict 反序列化（v2 读档用）。

        向后兼容：
        - 缺 `vars` / `path` / `current_block_id` 字段 → 用默认值
        - 缺 `version` 字段 → 视作 v1 老存档（兼容）
        - `version` > 当前支持版本 → 抛 ValueError（V3+ 升级保护）

        防御性：内部 vars/path/current_block_id 都是 d 的拷贝，外部改 d 不影响 state。
        """
        if not isinstance(d, dict):
            raise ValueError(
                f"GameState.from_dict 期望 dict，得到 {type(d).__name__}"
            )
        # version 校验（V3+ 升级锚点）
        ver_raw = d.get("version")
        if ver_raw is not None:
            if not isinstance(ver_raw, int):
                raise ValueError(
                    f"GameState.from_dict.version 应为 int，得到 {type(ver_raw).__name__}"
                )
            if ver_raw > GAMESTATE_SAVE_VERSION:
                raise ValueError(
                    f"GameState 存档 version {ver_raw} > 当前支持版本 "
                    f"{GAMESTATE_SAVE_VERSION}（V3+ 升级请写迁移函数）"
                )
            # ver_raw < GAMESTATE_SAVE_VERSION 也允许（向下兼容旧版）
        # vars 字段
        vars_raw = d.get("vars", {})
        if not isinstance(vars_raw, dict):
            raise ValueError(
                f"GameState.from_dict.vars 应为 dict，得到 {type(vars_raw).__name__}"
            )
        # path 字段
        path_raw = d.get("path", [])
        if not isinstance(path_raw, list):
            raise ValueError(
                f"GameState.from_dict.path 应为 list，得到 {type(path_raw).__name__}"
            )
        # current_block_id 字段
        cb_raw = d.get("current_block_id")
        if cb_raw is not None and not isinstance(cb_raw, str):
            raise ValueError(
                f"GameState.from_dict.current_block_id 应为 str 或 None，"
                f"得到 {type(cb_raw).__name__}"
            )
        return cls(
            vars=dict(vars_raw),  # 防御性拷贝
            path=list(path_raw),
            current_block_id=cb_raw,
        )


class Executor:
    """v0 引擎执行器。

    入口 id:start 块，按 Start→...→End 顺序调度节点。
    """

    def __init__(
        self,
        story: Story,
        sink: EventSink,
        *,
        entry_id: str = "start",
        state: GameState | None = None,
        save_manager = None,
    ):
        """构造 Executor。

        Args:
            story: 章节 AST。
            sink: 事件 sink（GUI / MemoryInputSink / EngineBus 等）。
            entry_id: 入口块 id，默认 'start'。
            state: 跨章节状态共享入口。V2-04 引入：ChapterManager 跨章节跳转时
                复用同一个 GameState 让 vars 跨章节保留。None → 新建空 GameState
                （v0 行为，向后兼容）。
            save_manager: v2-p0 save-load (V2-07) 引入：SaveManager 实例。
                None → 收到 SaveCmd/LoadCmd 时发 `ok=False` ack 事件（不抛错）。
        """
        self.story = story
        self.sink = sink
        # v2-p0 chapter-manager 扩展：state 可选外部注入，实现跨章节状态共享
        self.state = state if state is not None else GameState()
        self.save_manager = save_manager  # v2-p0 save-load：可选 SaveManager
        self._entry_id = entry_id
        self.next: tuple = None  # NEXT 跳转目标
        self._deco_state: dict = {}  # v0-issue-15 修饰器状态 {name: {key: val}}
        self._dispatcher = ExprDispatcher(self.state)
        # 跨块 ID 校验：所有 next_table target_id + NextId 目标 + if 分支目标 必须在 story
        self._validate_target_ids()

    def _validate_target_ids(self) -> None:
        """构造时一次性校验所有 target_id 在 story 内能找到。"""
        all_ids = set()
        for block in self.story.blocks:
            for item in block.meta:
                if isinstance(item, IdMeta):
                    all_ids.add(item.id)
        # 收集所有 target_id
        targets: list[tuple[str, int]] = []  # (target_id, lineno)
        for block in self.story.blocks:
            for d in block.next_table:
                if d.target_id:
                    targets.append((d.target_id, d.lineno))
            for node in block.body:
                if isinstance(node, NextId):
                    targets.append((node.target_id, 0))
        for tid, lineno in targets:
            if tid not in all_ids:
                loc_str = f" at line {lineno}" if lineno else ""
                raise ValueError(
                    f"unknown target id {tid!r}{loc_str}"
                )
        # v0-issue-16: If 分支项是 NextDecl 的 target_id
        for block in self.story.blocks:
            for node in block.body:
                if isinstance(node, If):
                    for branch in node.branches:
                        if isinstance(branch.target, NextDecl):
                            if branch.target.target_id not in all_ids:
                                raise ValueError(
                                    f"unknown target id {branch.target.target_id!r} "
                                    f"in if branch at line {branch.target.lineno}"
                                )

    def _find_entry_block(self) -> Block:
        """找 entry_id 块（默认 'start'）。"""
        for block in self.story.blocks:
            for item in block.meta:
                if isinstance(item, IdMeta) and item.id == self._entry_id:
                    return block
        raise ValueError(f"no id:{self._entry_id} block in story")

    def _find_block_by_id(self, block_id: str) -> Block:
        """按 id 找块。"""
        for block in self.story.blocks:
            for item in block.meta:
                if isinstance(item, IdMeta) and item.id == block_id:
                    return block
        raise ValueError(f"no id:{block_id} block in story")

    def _get_end_marker(self, block: Block) -> IdEnd | None:
        """取块内 id:endX 标记（v0 单 end 假设）。"""
        for item in block.meta:
            if isinstance(item, IdEnd):
                return item
        return None

    @staticmethod
    def _block_id(block: Block) -> str:
        """取块的 id（从 meta 找 IdMeta；不存在抛 RuntimeError）。"""
        for item in block.meta:
            if isinstance(item, IdMeta):
                return item.id
        raise RuntimeError(f"block has no IdMeta: {block}")

    def run(self) -> None:
        """从 entry 块开始执行。"""
        entry_block = self._find_entry_block()
        # v2-p0 save-load (V2-06): 入口处设置 current_block_id（存档恢复锚点）
        self.state.current_block_id = self._block_id(entry_block)
        self._execute_block_loop(entry_block)

    def _execute_block_loop(self, start_block: Block) -> None:
        """跑当前块 + 按 NEXT 跳到下一块 + 循环。"""
        current = start_block
        while current is not None:
            self.next = None
            self.run_block(current)
            current = self._next_block(current)

    def _next_block(self, current: Block) -> Block | None:
        """根据 self.next 决定下一块；None 表示停止。

        v2-p0 save-load (V2-06): 跳转成功后置更新 `state.current_block_id` 到下一块。
        """
        if self.next is None:
            return None
        _, target_id = self.next
        next_block = self._find_block_by_id(target_id)
        self.state.current_block_id = self._block_id(next_block)
        return next_block

    def run_block(self, block: Block) -> None:
        """单块执行：v0-issue-14 实现 Text/In/Echo/NextId，v0-issue-15 修饰器。"""
        # v0-issue-15: 块级作用域——进入时清空（不变量 #2）
        self._deco_state.clear()
        # 初始化 next_table
        self.state.next_table = {
            d.var_name: d.target_id
            for d in block.next_table
            if d.var_name is not None
        }
        # bare next（var_name=None）→ NEXT 直接指向（ADR-0001 §5.1）
        bare_decls = [d for d in block.next_table if d.var_name is None]
        if len(bare_decls) == 1:
            self.next = (None, bare_decls[0].target_id)
        else:
            self.next = None  # 多 next 或无 next → 等待竞争

        for node in block.body:
            if isinstance(node, Start):
                continue
            if isinstance(node, End):
                self._handle_end(block)
                return
            if isinstance(node, Text):
                self.sink.put_evt(TextEvt(content=node.content, style="narration"))
                continue
            if isinstance(node, In):
                self.sink.put_evt(PromptInputEvt(var=node.var))
                cmd = self._get_cmd_with_save_load_intercept()
                if cmd is not None:
                    # 尝试 int 转换，失败则保留字符串
                    raw = cmd.value
                    try:
                        self.state.vars[node.var] = int(raw)
                    except (ValueError, TypeError):
                        self.state.vars[node.var] = raw
                else:
                    # 阻塞式等待——v0-issue-17 实现；本 issue 抛错
                    raise NotImplementedError(
                        "blocking prompt_input not yet implemented; "
                        "use MemoryInputSink in tests"
                    )
                continue
            if isinstance(node, Echo):
                # ADR-0004 G4: echo 支持拼接
                if node.parts:
                    # 拼接模式：每个 part 如果是变量名则取值，否则当文本
                    pieces = []
                    for p in node.parts:
                        if p in self.state.vars:
                            pieces.append(str(self.state.vars[p]))
                        else:
                            pieces.append(p)
                    self.sink.put_evt(TextEvt(content="".join(pieces), style="narration"))
                else:
                    val = self.state.vars[node.var]  # KeyError if unset
                    self.sink.put_evt(TextEvt(content=val, style="narration"))
                continue
            if isinstance(node, NextId):
                self.next = (None, node.target_id)
                continue
            if isinstance(node, DecoratorCall):
                self._emit_decorator(node)
                continue
            if isinstance(node, DecoratorStop):
                self._emit_decorator(node)
                continue
            if isinstance(node, If):
                self._execute_if(node)
                continue
            # 留给未来
            raise NotImplementedError(
                f"node not yet implemented: {type(node).__name__}"
            )

    def _emit_decorator(self, deco) -> None:
        """v0-issue-15: 调度修饰器调用 / 休止符。"""
        if isinstance(deco, DecoratorCall):
            for arg in deco.args:
                if ":" in arg:
                    k, v = arg.split(":", 1)
                    self._deco_state.setdefault(deco.name, {})[k] = v
            self.sink.put_evt(DecoratorEvt(name=deco.name, args=list(deco.args)))
        elif isinstance(deco, DecoratorStop):
            if deco.name in self._deco_state:
                self._deco_state[deco.name].pop(deco.key, None)
            self.sink.put_evt(DecoratorEvt(name=deco.name, args=[deco.key]))

    # ─── v2-p0 save-load (V2-07)：SaveCmd / LoadCmd 拦截 ──────────────────
    #
    # 在 In 节点的 `sink.get_cmd()` 返回值上做 dispatch：
    # - SaveCmd/LoadCmd → 调 SaveManager → 发 SaveAckEvt/LoadAckEvt → 继续 get_cmd()
    # - 其他（含 UserInputCmd）→ 返回给 In handler 消费
    #
    # 设计动机：GUI 进程可能在玩家输入框聚焦时同时按 F5（存档），把 SaveCmd
    # 推到 cmd_q 前端；Executor 在 In 节点 get_cmd() 时看到 SaveCmd，
    # 处理后再回到 get_cmd() 拿真正输入。

    def _get_cmd_with_save_load_intercept(self):
        """从 sink.get_cmd() 取 cmd；遇 SaveCmd/LoadCmd 拦截处理后继续取。

        Returns:
            UserInputCmd 或其他可消费 cmd（含 None 表示无输入）。
            注意：本方法**永远不返回** SaveCmd/LoadCmd —— 都被内部处理。
        """
        while True:
            cmd = self.sink.get_cmd()
            if cmd is None:
                return None
            if isinstance(cmd, SaveCmd):
                self._handle_save_cmd(cmd)
                continue
            if isinstance(cmd, LoadCmd):
                self._handle_load_cmd(cmd)
                continue
            return cmd

    def _handle_save_cmd(self, cmd: "SaveCmd") -> None:
        """处理 SaveCmd：SaveManager.save → 发 SaveAckEvt。"""
        if self.save_manager is None:
            self.sink.put_evt(SaveAckEvt(
                slot=cmd.slot,
                ok=False,
                error="no save_manager configured",
            ))
            return
        try:
            self.save_manager.save(cmd.slot, self.state)
        except Exception as e:  # ValueError / OSError / TypeError 都接住
            self.sink.put_evt(SaveAckEvt(
                slot=cmd.slot,
                ok=False,
                error=f"{type(e).__name__}: {e}",
            ))
            return
        self.sink.put_evt(SaveAckEvt(slot=cmd.slot, ok=True))

    def _handle_load_cmd(self, cmd: "LoadCmd") -> None:
        """处理 LoadCmd：SaveManager.load → 替换 self.state → 发 LoadAckEvt。

        失败时不替换 state（保留原 GameState 实例以防 caller 引用悬空）。
        """
        if self.save_manager is None:
            self.sink.put_evt(LoadAckEvt(
                slot=cmd.slot,
                ok=False,
                error="no save_manager configured",
            ))
            return
        try:
            loaded_state = self.save_manager.load(cmd.slot)
        except FileNotFoundError as e:
            self.sink.put_evt(LoadAckEvt(
                slot=cmd.slot,
                ok=False,
                error=f"FileNotFoundError: {e}",
            ))
            return
        except Exception as e:  # ValueError / JSONDecodeError / KeyError 都接住
            self.sink.put_evt(LoadAckEvt(
                slot=cmd.slot,
                ok=False,
                error=f"{type(e).__name__}: {e}",
            ))
            return
        # 成功：替换 self.state（清空 next_table 因为跨章节）
        self.state = loaded_state
        # 重新初始化 dispatcher 引用新 state（v1 表达式求值用）
        self._dispatcher = ExprDispatcher(self.state)
        self.sink.put_evt(LoadAckEvt(slot=cmd.slot, ok=True))

    def _execute_if(self, if_node: If) -> None:
        """v1 (ADR-0004): node if 真求值。

        cond[0] kind 分支:
        - "var":      值匹配——取 state.vars[cond[1]] 的值, 匹配 branch.value
        - "expr":     Python 表达式值匹配——dispatcher.eval(expr) 返回值匹配 branch.value
        - "bool_expr": Python 表达式布尔求值——dispatcher.eval_bool(expr) 决定
                       branches[0] (True) 或 branches[1] (False)
        """
        kind, expr = if_node.cond
        chosen = None

        if kind == BOOL_EXPR_KIND:
            # 表达式布尔求值 (D1 修法: 显式 kind, 区别于 "expr" 的值匹配)
            try:
                result = self._dispatcher.eval_bool(expr)
            except ExprError as e:
                self.sink.put_evt(LogEvt(
                    level="error",
                    message=f"node if bool_expr failed: {e}",
                ))
                raise
            if len(if_node.branches) != 2:
                raise RuntimeError(
                    f"node if bool_expr: requires exactly 2 branches, "
                    f"got {len(if_node.branches)}"
                )
            chosen = if_node.branches[0] if result else if_node.branches[1]
        elif kind == EXPR_KIND:
            # Python 表达式求值, 值匹配 (多元素值匹配场景)
            try:
                result = self._dispatcher.eval(expr)
            except ExprError as e:
                self.sink.put_evt(LogEvt(
                    level="error",
                    message=f"node if expr failed: {e}",
                ))
                raise
            # 二元: True → branches[0], False → branches[1]
            if len(if_node.branches) == 2:
                chosen = if_node.branches[0] if result else if_node.branches[1]
            else:
                # 多元: result 当值匹配
                for b in if_node.branches:
                    if b.value == result:
                        chosen = b
                        break
                if chosen is None:
                    raise RuntimeError(
                        f"node if: no branch matched value {result!r}"
                    )
        else:
            # VAR_KIND 值匹配 (v0 兼容)
            assert kind == VAR_KIND, f"unknown if cond kind: {kind!r}"
            var_name = expr
            val = self.state.vars.get(var_name)
            # 尝试 int 匹配
            try:
                val_int = int(val)
            except (ValueError, TypeError):
                val_int = val
            for b in if_node.branches:
                if b.value == val_int:
                    chosen = b
                    break
            if chosen is None:
                raise RuntimeError(
                    f"node if: no branch matched value {val!r} for var {var_name!r}"
                )

        self.sink.put_evt(LogEvt(
            level="info",
            message=f"node if: chose branch {chosen.value}",
        ))
        # 解析分支目标
        target = chosen.target
        if isinstance(target, NextDecl):
            self.next = (target.var_name, target.target_id)
        elif isinstance(target, CallExpression):
            # echo / in：广播对应事件
            if target.kind == "echo":
                val = self.state.vars.get(target.var, "")
                self.sink.put_evt(TextEvt(content=val, style="narration"))
            elif target.kind == "in":
                self.sink.put_evt(PromptInputEvt(var=target.var))
            return  # 不走下面的 NextDecl/CallExpression 分支

    def _handle_end(self, block: Block) -> None:
        """处理 node end：NEXT 跳转 / RouteEvt / ChapterEndEvt / RuntimeError。"""
        if self.next is not None:
            # NEXT 跳转——不做 RouteEvt，run() 主循环负责跳
            return
        end_marker = self._get_end_marker(block)
        if end_marker is None:
            raise RuntimeError(
                f"block ended with empty NEXT and no endX marker"
            )
        if end_marker.route_chapter is not None:
            self.sink.put_evt(RouteEvt(target=end_marker.route_chapter))
        else:
            self.sink.put_evt(ChapterEndEvt())
