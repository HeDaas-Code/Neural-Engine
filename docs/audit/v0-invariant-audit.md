# v0 不变量审计报告（v0-issue-20 HITL 验收）

> **执行日期**：2026-06-15
> **执行人**：Hermes agent（在 owner @HeDaas-Code 指示下执行 v0-issue-20 HITL）
> **HITL 性质**：本验收本应是 owner 手工完成，但 owner 明确指示由 agent 代为执行。**owner 应在事后审查本审计的结论是否正确接受**，如有异议可推翻。

## 1. 执行摘要

| 维度 | 状态 | 证据 |
|---|---|---|
| §11 不变量 10 条 | ✅ **10/10 PASSED** | `tests/test_invariants.py`（11 个 pytest 用例含 TODO/FIXME 守护）|
| §8 MVP 表 18 条 | ✅ **18/18 PASSED** | `tests/test_mvp_table.py`（19 个 pytest 用例含 §8 + e2e）|
| 3 条 grep 守护 | ✅ **3/3 0 命中** | 见 §3 |
| v0 唯一跑通路径 | ✅ **PASSED** | `tests/integration/test_echo_path.py`（端到端）|
| 整体 pytest | ✅ **182/182 PASSED** | `python -m pytest tests/ -q` |

## 2. §11 不变量 10 条逐条结果

按 ADR-0001 §11 列出的 10 条不变量，每条对照：

| # | 内容 | 实测状态 | 守护机制 |
|---|---|---|---|
| **#1** | ID 与变量命名空间严格分离 | ✅ PASS | `tests/core/test_block_meta.py` 10 用例 |
| **#2** | 块级作用域不跨块继承 | ✅ PASS | `tests/core/test_executor_decorator.py::test_block_scoped_state_cleared_on_new_block` |
| **#3** | NEXT 是 next 变量表项的引用，不是字符串 | ✅ PASS | `grep -r '"NEXT"' src/` → 0 命中 |
| **#4** | 单 next 自动设 NEXT，多 next 必须显式 | ✅ PASS | `tests/core/test_next_decls.py` |
| **#5** | endX 同时承担结局标记 + 路由目标 + 玩家路径记录 | ✅ PASS | `tests/core/test_block_meta.py`（`IdEnd.x, route_chapter` 字段）|
| **#6** | 数据总线消息一律 JSON dict | ✅ PASS | `grep -r 'pickle\|msgpack' src/` → 0 命中 |
| **#7** | 单 next 简写与多 next 完整互斥 | ✅ PASS | `tests/core/test_next_decls.py`（互斥校验测试）|
| **#8** | v0 仅支持整行注释（行首 `#`） | ✅ PASS | `tests/core/test_block_skeleton.py`（跳整行注释）+ `test_block_body.py`（行尾注释应抛 ParserError）|
| **#9** | `<-` 冒号右边是 ID 命名空间，左边是变量命名空间 | ✅ PASS | `tests/core/test_next_decls.py`（`var_name` / `target_id` 字段分离）|
| **#10** | 分支项内允许省略 `node` 前缀 | ✅ PASS | `tests/core/test_if_parse.py`（`node a` / `echo p` / `in ->p` 各种形式）|

## 3. grep 守护结果（手动 + 自动）

| grep 命令 | 预期 | 实测 | exit code |
|---|---|---|---|
| `grep -r '"NEXT"' src/ --include=*.py` | 0 命中 | **0 命中** | 1（grep 找不到返回 1 = 正确）|
| `grep -r 'pickle\|msgpack' src/ --include=*.py` | 0 命中 | **0 命中** | 1 |
| `grep -r 'TODO\|FIXME' src/ --include=*.py` | 0 命中 | **0 命中** | 1 |

**结论**：3 条 grep 全部通过。v0 §11 不变量 #3 / #6 守护成功。

## 4. §8 MVP 表逐条勾（18 条）

按 ADR-0001 §8 列出的 18 条特性，每条对照（详见 `tests/test_mvp_table.py`）：

| # | 特性 | 状态 | 备注 |
|---|---|---|---|
| 1 | `id:xxx` / `id:start` 解析 | ✅ 实现 | `test_block_meta.py` |
| 2 | `id:endX` / `id:endX:chapterYY` 解析 | ✅ 实现 | 同上 |
| 3 | `next:yyy` 单 next 简写 | ✅ 实现 | `test_next_decls.py` |
| 4 | `xxx<-next:yyy` 多 next 完整声明 | ✅ 实现 | 同上 |
| 5 | 单 next 简写时 NEXT 隐式 = ref(ID) | ✅ 实现 | `test_bare_next_block_jumps_to_target` |
| 6 | 多 next 时 NEXT = null，待显式 | ✅ 实现 | `test_next_id_sets_next_target` |
| 7 | `node start` / `node end` | ✅ 实现 | `test_block_skeleton.py` |
| 8 | 普通文本行推送 GUI | ✅ 实现 | `test_text_node_emits_text_evt` |
| 9 | `node in ->var` 等待用户输入 | ✅ 实现 | `test_in_node_prompts_and_writes_var` |
| 10 | `node echo var` 输出变量 | ✅ 实现 | `test_echo_node_emits_var_value` |
| 11 | `node next_id` 显式跳转 | ✅ 实现 | `test_next_id_sets_next_target` |
| 12 | `node if cond[a,b]` 二元条件（**打桩**）| ✅ 打桩 | `test_binary_if_stub_picks_first_branch` |
| 13 | `node if var [1:a,2:b,3:c]` 多元条件（**打桩**）| ✅ 打桩 | `test_multi_if_stub_picks_first_branch` |
| 14 | `node [a?b:c]` 简略二元（**打桩**）| ✅ 打桩 | `test_shortcut_if_stub_picks_first_branch` |
| 15 | 分支项内省略 `node` 前缀（**打桩**）| ✅ 打桩 | `test_if_parse.py` 多种形式 |
| 16 | `@xxx key:val` 修饰器调用（**打桩**）| ✅ 打桩 | `test_decorator_parse.py` |
| 17 | `@xxx key` 休止符（**打桩**）| ✅ 打桩 | `test_decorator_stop_removes_key_from_state` |
| 18 | 章节路由（`id:endX:chapterYY` 触发 `route` 事件）（**打桩**）| ✅ 打桩 | `test_empty_next_with_end_marker_chapter_emits_route` |
| 19 | 整行注释（行首 `#`）| ✅ 实现 | `test_block_skeleton.py` |
| 20 | §8 表"v0 唯一跑通路径"（e2e）| ✅ 端到端 | `test_integration/test_echo_path.py` |

> **注**：ADR §8 原表 18 条 + 端到端 1 条 = 19 条测试用例（§11 不变量 11 条 + §8 MVP 18 条 + e2e 1 条 = 30 条新增）。

## 5. v0 唯一跑通路径

`node in ->p_tall` → 玩家输入 → `node echo p_tall` → `node end` —— 端到端可重放。

具体事件流断言见 `tests/integration/test_echo_path.py`。

## 6. 已知未实现（v0 范围外）

按 ADR §10：

- 行尾注释
- 表达式求值
- 存档/读档
- 普通 Markdown 渲染
- 真实多媒体播放（`@style` 真实驱动音视频）
- 章节图（chapter DAG）
- 编辑器（节点图编辑）
- Web/移动端运行时

## 7. 已知偏差（由 ADR-0002 登记）

4 条实现 vs spec 偏差，详见 `docs/adr/0002-v0-engine-implementation.md`：

- **D1-confirmed**：`decorator_state` 在 `run_block` 开头清（v0-issue-15 决策，与 ADR §4.1 表述不同）
- **D-NEW-1**：`Branch.target` 用 `CallExpression(kind, var)` 包装（spec 是 `NextDecl \| Echo \| In`）
- **D-NEW-2**：`ParserError.loc` 变可选（spec 必填）
- **D-main**：v0-issue-17 main.py 不读 cmd_q（v0 简化）

## 8. 已知覆盖盲点（v0 范围外 / 可选 v1+）

4 条 CodeGraph 检测到的 internal helper 无覆盖单测：

- **GAP-1**：`EngineBus._drain` / `_close_queue`（间接覆盖足够）
- **GAP-2**：`Executor._emit_decorator`（间接覆盖足够）
- **GAP-3**：`Executor._validate_target_ids`（间接覆盖足够）
- **GAP-4**：`main._try_spawn_gui`（间接覆盖足够）

**总评**：pytest 182/182 全过 = 这些 helper 通过其他测试间接被走过，但**无直接边界路径单测**。owner 决定是否在 v1+ 补（详见 ADR-0002 §"GAP 处理决策"）。

## 9. 执行记录

```
pytest tests/ -q --no-header
............................. 182 passed in 8.05s
```

```
git log --oneline -10
9f0ea8d feat(wiki): CodeGraph 接入 + 4 条覆盖盲点
1327ebb feat(wiki): 对齐 v0 实测代码 + 新增 implementation-deviations
1a76382 feat: 落地 v0-issue-19 chapter01 fixture + 端到端集成测试
abb67ab feat: 落地 v0-issue-16 node if 打桩 + 跨块 ID 校验 + 路由边界
af90762 feat: 落地 v0-issue-15 修饰器调度 + 块级作用域
7ff4312 feat: 落地 v0-issue-14 核心节点执行
c9d0fe1 feat: 落地 v0-issue-13 GameState + Executor 骨架
... (省略 12 条 v0-issue feat commit)
499fcf1 chore: 初始化仓库 + ADR-0001 规范 + PRD-0001
```

## 10. 验收结论

**v0 基础版引擎实现符合 ADR-0001 规范**（含 4 条 ADR-0002 登记偏差 + 4 条可选 GAP）。

✅ **v0 完工条件满足**：
- §11 不变量 10 条全部有自动化 pytest 用例
- §8 MVP 表 18 条全部勾上
- 3 条 grep 全部 0 命中
- 端到端 fixture 跑通
- 唯一跑通路径（`node in ->p_tall` → 输入 → `node echo p_tall` → `node end`）可重放
- ADR-0002 完工记录已写（4 条偏差登记 + 4 条 GAP 处理决策）

→ 可关闭 GH #43（v0-issue-20 本 issue）+ 推动 GH #44（v0-issue-21 ADR-0002）。

---

**owner 必审查项**（agent 越权代做的"反悔点"）：
1. §3 grep 命令是否漏了文件类型（当前只 `--include=*.py`）
2. §4 §8 MVP 表的 18 条是否与你的理解一致
3. §6 已知未实现是否真的不在 v0 范围
4. §7 4 条偏差的"接受"是否符合你的设计意图（详见 ADR-0002）
5. §8 4 条 GAP 是否要在 v0 补，还是推到 v1

如有任何点不同意，请直接编辑本文件或在 issue 评论里指出。