## Parent

#22（PRD-0001 父 issue）

## What to build

[HITL 守护] 自动化跑 ADR §11 全部 10 条关键不变量 + ADR §8 MVP 表逐条勾。

## 验收（自动化 + 人工核验）

**§11 关键不变量**（10 条）—— 每条都写一个 pytest 用例：

1. **ID 与变量命名空间严格分离**——`id:xxx` 只能在 `node start` 之前（v0-issue-8 已测）
2. **块级作用域不跨块继承**——`@` 修饰器状态在 `node end` 时清空（v0-issue-15 已测）
3. **NEXT 是 next 变量表项的引用，不是字符串**——`grep -r '"NEXT"' src/` 应为 0 命中（**新加** pytest 用例：执行 `subprocess.run(["grep", "-r", '"NEXT"', "src/"], check=False)` + 断言 exit code 1）
4. **单 next 自动设 NEXT，多 next 必须显式**——v0-issue-9 已测
5. **endX 同时承担结局标记 + 路由目标 + 玩家路径记录**——v0-issue-16 已测
6. **数据总线消息一律 JSON dict**——v0-issue-5 + v0-issue-19 e2e 已测
7. **单 next 简写与多 next 完整互斥**——v0-issue-9 已测
8. **v0 仅支持整行注释**——v0-issue-10 已测（行尾注释应抛 ParserError）
9. **`<-` 冒号右边是 ID 命名空间，左边是变量命名空间**——v0-issue-9 已测
10. **分支项内允许省略 `node` 前缀**——v0-issue-11 已测

**§8 MVP 表逐条勾**（18 条）—— `tests/test_mvp_table.py` 列出所有条目 + 关联到对应测试函数 + 逐项 assert。

**人工核验步骤**（写进本 issue 评论）：
- 跑 `python -m pytest tests/ -v` 全绿
- 跑 `grep -r '"NEXT"' src/` 0 命中
- 跑 `grep -r 'pickle\|msgpack' src/` 0 命中（不变量 #6 序列化约束）
- 跑 `grep -r 'TODO\|FIXME' src/` 0 命中（PRD 硬约束）
- 逐条勾 §8 MVP 表
- 写 `docs/audit/v0-invariant-audit.md` 记录结果

## 验收标准（HITL）

- [ ] §11 10 条不变量全部有自动化 pytest 用例
- [ ] §8 MVP 表 18 条全部勾上
- [ ] 人工 grep 三条全 0 命中
- [ ] `docs/audit/v0-invariant-audit.md` 写完
- [ ] 在 v0-issue-21 父 issue 贴完成评论

## Blocked by

- #22（父 PRD）
- #42（v0-issue-19 fixture + 端到端）
