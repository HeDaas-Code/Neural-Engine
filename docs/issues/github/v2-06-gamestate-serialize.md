## Parent

PDR：[`docs/pdr/phase3-v2p0.md`](../../pdr/phase3-v2p0.md) §5.3（存档/读档）
Issue 列表：[`docs/issues/phase3-v2p0.md`](../../issues/phase3-v2p0.md) V2-06
关联 EP：EP-09（`GameState` 序列化）
关联决策：D2（JSON 复用 protocol.py）

## What to build

在 `src/core/engine/executor.py:63-68` 扩展 `GameState` 加 `current_block_id` 字段 + `to_dict/from_dict` 方法（**D2 决策：JSON 复用 protocol.py**）；`Executor.run` 入口 / `_next_block` 后置更新 `current_block_id`。

### 步骤

1. **`src/core/engine/executor.py:63-68` `GameState` 扩展**：
   ```python
   @dataclass
   class GameState:
       """执行期状态（v0 全字符串变量）。"""
       vars: dict = field(default_factory=dict)
       path: list = field(default_factory=list)
       next_table: dict = field(default_factory=dict)
       current_block_id: str | None = None  # v2 新增；存档恢复用

       def to_dict(self) -> dict:
           """序列化为 dict（v2 存档用）。D2 决策：复用 protocol.py json.dumps 模式。"""
           return {
               "version": 1,  # 存档版本字段（v3+ 升级时写迁移函数）
               "vars": dict(self.vars),
               "path": list(self.path),
               "current_block_id": self.current_block_id,
           }

       @classmethod
       def from_dict(cls, d: dict) -> "GameState":
           """从 dict 反序列化（v2 读档用）。"""
           return cls(
               vars=dict(d.get("vars", {})),
               path=list(d.get("path", [])),
               current_block_id=d.get("current_block_id"),
           )
   ```

2. **`Executor.run` / `_next_block` 更新 `current_block_id`**（executor.py:145-163）：
   ```python
   def run(self) -> None:
       entry_block = self._find_entry_block()
       self.state.current_block_id = entry_block.id  # v2 新增
       self._execute_block_loop(entry_block)

   def _next_block(self, current: Block) -> Block | None:
       if self.next is None:
           return None
       _, target_id = self.next
       next_block = self._find_block_by_id(target_id)
       self.state.current_block_id = next_block.id  # v2 新增
       return next_block
   ```
   注意：`_find_entry_block` 也要返回 block.id

3. **D2 决策落地**：序列化/反序列化用 `json.dumps + utf-8`（与 `protocol.py` 一致），存档格式与 IPC 消息同一序列化模式
   - **不在本 issue 写 `json.dumps` 调用**（V2-07 SaveManager 写）；本 issue 仅提供 `to_dict/from_dict`

4. **存档版本字段**：`to_dict` 写 `"version": 1`，`from_dict` 检查版本（v2 仅读 v1；v3+ 升级时写迁移函数）
   - 当前 v2 仅支持 `version: 1`；不匹配时抛 `ValueError`

5. **OQ-5 默认值**：仅允许 `vars` 含 `str / int / list / dict`（其他类型需先 `to_dict()` 再存档）—— PM 拍板后可能改
   - v2 暂不加类型校验（信任 v0 表达式系统仅返回 str/int）

6. **测试**：
   - `tests/core/test_executor_skeleton.py::test_gamestate_to_dict_round_trip` —— 序列化后反序列化恢复
   - `tests/core/test_executor_skeleton.py::test_gamestate_version_field` —— `to_dict()` 含 `"version": 1`
   - `tests/core/test_executor_skeleton.py::test_gamestate_from_dict_missing_fields` —— 缺字段时默认值
   - `tests/core/test_executor_skeleton.py::test_current_block_id_updated_on_run` —— `Executor.run` 入口设置 `state.current_block_id`
   - `tests/core/test_executor_skeleton.py::test_current_block_id_updated_on_next_block` —— `_next_block` 后置更新
   - 现有 `tests/core/test_executor_*.py` 全套不破

7. **OQ-3 默认值**：跨章节变量保留（`GameState.vars` 跨块已隐式全局）—— PM 拍板后可能改为每章节重置

## Acceptance criteria

- [ ] `src/core/engine/executor.py:63-68` `GameState` 加 `current_block_id` 字段
- [ ] `GameState.to_dict()` 方法实现（含 `version: 1`）
- [ ] `GameState.from_dict()` classmethod 实现
- [ ] `Executor.run` 入口设置 `state.current_block_id`
- [ ] `Executor._next_block` 后置更新 `state.current_block_id`
- [ ] `tests/core/test_executor_skeleton.py` 加 5 个新测试
- [ ] 现有 `tests/core/test_executor_*.py` 全套不破（211+ tests 维持）
- [ ] 现有 211+ tests 维持 + 5+ 新测试
- [ ] v0/v1 解析器/执行器核心仅扩字段（不破坏现有 89% 覆盖率）

## Blocked by

无（Window 1 · 3 人并行启动）

## 关联依赖

- 阻塞 V2-07（SaveManager，依赖本 issue 的 `to_dict/from_dict`）
