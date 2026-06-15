## Parent

本文档来源：[`docs/prds/0001-v0-engine-implementation.md`](../../docs/prds/0001-v0-engine-implementation.md)（PRD-0001）
规范来源：[`docs/adr/0001-v0-baseline-script-spec.md`](../../docs/adr/0001-v0-baseline-script-spec.md)（ADR-0001）

## What to build

发布 PRD-0001 与 ADR-0001 已就绪的 v0 基础版引擎实现——按 vertical slice 拆为 21 条子任务（#2-#21）+ 2 条 HITL 守护（#22 #23），全部完成后 close 本 issue。

## Acceptance criteria

- [ ] 子任务 #2-#21 全部 triage → prototype → tdd → 完成评论已发布
- [ ] 不变量守护 #22 通过
- [ ] ADR-0002 完工记录 #23 已写入
- [ ] §8 MVP 表逐条跑通
- [ ] `python -m core.engine.main chapters/chapter01.md` 可启动

## Blocked by

无（根节点）
