## Parent

PDR：[`docs/pdr/phase3-v2p0.md`](../../pdr/phase3-v2p0.md) §11.4（关键源文件改造位）
Issue 列表：[`docs/issues/phase3-v2p0.md`](../../issues/phase3-v2p0.md) V2-09
关联 EP：—

## What to build

更新 `ROADMAP.md` §3 P0 标记 v2 三大功能已完成；`AGENTS.md` / `docs/agents/domain.md` / `src/runtime/CONTEXT.md` 同步新模块；跨模块回归（`pytest tests/` 全绿 + 230+ tests / 92%+ 覆盖率）；`docs/audit/phase3-v2p0-summary.md` 写 v2 P0 完工总结。

### 步骤

1. **`docs/ROADMAP.md` 更新**：
   - §3.1 PyQt6 GUI 标记 ✅（v2 P0 完成）
   - §3.2 章节加载器标记 ✅
   - §3.3 存档/读档标记 ✅
   - §2.1 v0 遗留的"PyQt6 GUI 窗口"/"章节图 DAG"/"存档/读档"标记 ✅ 已解决

2. **`AGENTS.md` 更新**（如存在）：
   - 新增 `src/runtime/audio.py` / `video.py` / `renderer.py` 占位说明
   - 新增 `src/core/decorators/style.py` 钩子说明
   - 新增 `src/runtime/gui/pyqt6_main.py` 说明
   - 新增 `src/runtime/chapter_manager.py` 说明
   - 新增 `src/runtime/load_chapter.py` 说明
   - 新增 `src/runtime/save.py` 说明

3. **`docs/agents/domain.md` 更新**：
   - 验证 `CONTEXT-MAP.md` 指向各 CONTEXT.md 仍准确
   - runtime CONTEXT 增补 save/audio/video/renderer 关键类型

4. **`src/runtime/CONTEXT.md` 验证**：
   - `SaveManager` 已实现（V2-07）—— 关键类型表移除"v3+ 落地"标记
   - `TextRenderer` / `AudioManager` / `VideoPlayer` / `PlatformBridge` 仍标"v3+ 落地"

5. **`docs/audit/phase3-v2p0-summary.md` 新建**（完工总结）：
   - 9 个 issue 完成状态（V2-01 ~ V2-09）
   - 测试从 211 → 230+（V2-01~V2-08 新增测试）
   - 覆盖率从 92% → 92%+（维持）
   - 6 个新模块（`src/runtime/{save,audio,video,renderer}.py` + `src/core/decorators/style.py` + `src/runtime/gui/pyqt6_main.py`）
   - EP-03 / EP-05 / EP-06 / EP-07 / EP-08 / EP-09 / EP-10 / EP-11 共 8 个 EP 落地
   - 5 决策 D1-D5 落地验证
   - 已知 limitation（_drain 异常吞咽 / GUI 进程意外退出未检测 / G5 推迟）

6. **跨模块回归**：
   - `pytest tests/` 全绿（230+ tests / 92%+ 覆盖率）
   - `ruff check src/` 0 errors（新增模块 ruff 合规）
   - 5 个 v0/v1 commit（b5edf5b / e631dae / 6979d8c / 766e407 / f1f39f4）未受影响
   - 跨章节变量保留（OQ-3）验证
   - 存档 round-trip（OQ-5）验证
   - 装饰器钩子 call/stop 区分（EP-06）验证

7. **分支合并**：`feature/v2-p0-gui-first` → `master`（MR / PR）
   - 合并前确认所有 issue 已 close
   - 合并后 close 本 issue

## Acceptance criteria

- [ ] `docs/ROADMAP.md` 更新（§3 P0 三项标记 ✅ + §2.1 v0 遗留标记 ✅）
- [ ] `AGENTS.md` 更新（如存在；6 个新模块说明）
- [ ] `docs/agents/domain.md` 更新（CONTEXT-MAP 验证 + runtime CONTEXT 增补）
- [ ] `src/runtime/CONTEXT.md` 验证（`SaveManager` 落地标记）
- [ ] `docs/audit/phase3-v2p0-summary.md` 新建（完工总结 + 8 个 EP 落地 + 5 决策验证）
- [ ] `pytest tests/` 全绿（230+ tests / 92%+ 覆盖率）
- [ ] `ruff check src/` 0 errors
- [ ] 5 个 v0/v1 commit 未受影响
- [ ] `feature/v2-p0-gui-first` → `master` MR 已合并
- [ ] 9 个 issue（V2-01 ~ V2-09）全部 close

## Blocked by

- V2-01（PyQt6 入口切换，#72）
- V2-02（装饰器渲染，#73）
- V2-03（PyQt6 GUI 测试，#74）
- V2-04（ChapterManager，#75）
- V2-05（章节加载器测试，#76）
- V2-06（GameState 序列化，#77）
- V2-07（SaveManager，#78）
- V2-08（EP-07 骨架，#79）

## 关联依赖

- 不阻塞其他 issue（本 issue 是收尾）
