"""v2 P0 · V2-07 — 存档/读档 e2e 集成测试。

按 PM 派工 V2-07 任务 5 验收：
- 跑 chapter01_v1.md 到中点 → save slot=01 → restart → load slot=01 → 状态恢复
- 验证 vars / current_block_id 都恢复

测试策略：
- 直接构造 Executor + 真实 chapter01_v1.md + MixedCmdSink（混合 cmd 队列）
- 不走 EngineBus 子进程（GUI/Engine 双进程在 V2-09 文档同步阶段收尾）
- 临时 save_dir 走 tmp_path（不污染 ~/.neural-engine/saves/）
"""
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))


# ─── 测试夹具 ────────────────────────────────────────────────────────────────


class MixedCmdSink:
    """测试 sink：按 list 提供混合 cmd（SaveCmd / LoadCmd / UserInputCmd）。"""

    def __init__(self, cmds=None):
        self._cmds = list(cmds or [])
        self._idx = 0
        self.events: list = []

    def put_evt(self, evt) -> None:
        self.events.append(evt)

    def get_cmd(self):
        if self._idx < len(self._cmds):
            v = self._cmds[self._idx]
            self._idx += 1
            return v
        return None


# ─── 1. chapter01_v1.md 跑通（基线） ────────────────────────────────────────


def test_chapter01_v1_runs_to_chapter_end_baseline():
    """chapter01_v1.md 跑通基线：mood="平静" + pick=1 → 走 ca → ChapterEndEvt。

    验证不存档也能正常跑（确认 SaveCmd/LoadCmd 拦截逻辑不破坏正常流程）。
    """
    from core.engine.executor import Executor
    from core.engine.interpreter import extract_neon_blocks
    from core.engine.protocol import (
        SaveAckEvt, LoadAckEvt, UserInputCmd, ChapterEndEvt,
    )
    from runtime.chapter_manager import ChapterManager  # noqa: F401  # ensure importable

    chapter_path = REPO_ROOT / "chapters" / "chapter01_v1.md"
    # 解析章节（直接用 interpreter，不走 _load_story 因为会触发 ChapterManager 路由）
    text = chapter_path.read_text(encoding="utf-8")
    neon_blocks = extract_neon_blocks(text)
    assert len(neon_blocks) == 4  # start / c1 / ca / cb

    # 简单构造 Story（用 chapter_manager 的 load_chapter_safe 更省事）
    from runtime.load_chapter import load_chapter_safe
    story = load_chapter_safe(chapter_path)

    sink = MixedCmdSink(cmds=[
        UserInputCmd(value="平静"),
        UserInputCmd(value="1"),  # pick=1 → t_a → ca → end0
    ])
    exe = Executor(story, sink)
    exe.run()

    # 不应有任何 SaveAckEvt / LoadAckEvt（无存档命令）
    assert not any(isinstance(e, SaveAckEvt) for e in sink.events)
    assert not any(isinstance(e, LoadAckEvt) for e in sink.events)
    # 应该有 ChapterEndEvt
    assert any(isinstance(e, ChapterEndEvt) for e in sink.events)
    # vars
    assert exe.state.vars.get("mood") == "平静"
    assert exe.state.vars.get("pick") == 1


# ─── 2. e2e 完整 save/load/restart 流程 ──────────────────────────────────


def test_chapter01_v1_save_then_restart_load_restores_state(tmp_path):
    """chapter01_v1.md 跑 → 中点 save → 新 Executor → load → state 恢复。

    流程：
    1. Phase 1（save）：mood=happy → c1.In(pick) 处 SaveCmd("01") → pick=1 → end
       存档时 state: vars={mood:"happy", pick:1}, current_block_id="ca"
    2. Phase 2（load）：新 Executor + mood=placeholder → c1.In(pick) 处 LoadCmd("01") → pick=1
       load 替换 state → 后续 pick=1 写入 → 最终 state: vars={mood:"happy", pick:1}
    3. 验证：Phase 2 终态 == Phase 1 终态（vars + current_block_id 一致）
    """
    from core.engine.executor import Executor
    from core.engine.protocol import (
        SaveCmd, LoadCmd, SaveAckEvt, LoadAckEvt, UserInputCmd,
    )
    from runtime.save import SaveManager
    from runtime.load_chapter import load_chapter_safe

    sm = SaveManager(save_dir=tmp_path)
    chapter_path = REPO_ROOT / "chapters" / "chapter01_v1.md"
    story = load_chapter_safe(chapter_path)

    # ─── Phase 1: save ──────────────────────────────────────────────────
    sink1 = MixedCmdSink(cmds=[
        UserInputCmd(value="happy"),   # start.In(mood)
        SaveCmd(slot="01"),             # c1.In(pick) 拦截存档
        UserInputCmd(value="1"),        # c1.In(pick) 真实输入
    ])
    exe1 = Executor(story, sink1, save_manager=sm)
    exe1.run()

    # Phase 1 验证
    assert (tmp_path / "01.json").exists()
    save_acks_1 = [e for e in sink1.events if isinstance(e, SaveAckEvt)]
    assert len(save_acks_1) == 1
    assert save_acks_1[0].ok is True
    # Phase 1 终态
    phase1_vars = dict(exe1.state.vars)
    phase1_cb = exe1.state.current_block_id
    assert phase1_vars["mood"] == "happy"
    assert phase1_vars["pick"] == 1

    # ─── Phase 2: 新 Executor + load ────────────────────────────────────
    sink2 = MixedCmdSink(cmds=[
        UserInputCmd(value="placeholder"),  # start.In(mood) — load 后会被覆盖
        LoadCmd(slot="01"),                  # c1.In(pick) 拦截读档
        UserInputCmd(value="1"),             # c1.In(pick) 真实输入
    ])
    exe2 = Executor(story, sink2, save_manager=sm)
    exe2.run()

    # Phase 2 验证
    load_acks_2 = [e for e in sink2.events if isinstance(e, LoadAckEvt)]
    assert len(load_acks_2) == 1
    assert load_acks_2[0].ok is True
    # Phase 2 终态：load 后的 vars 应该匹配存档时的 vars（不含 pick，
    # 因为存档时 pick 还未设；后续 pick=1 又写入）
    # mood 应该是存档的 "happy"（被 load 覆盖 placeholder）
    assert exe2.state.vars["mood"] == "happy"
    assert exe2.state.vars["pick"] == 1
    # current_block_id 应该与 Phase 1 终态一致
    assert exe2.state.current_block_id == phase1_cb
    # 完整 vars 等值（order-independent）
    assert exe2.state.vars == phase1_vars


# ─── 3. 存档文件 JSON 内容验证（D2 决策） ──────────────────────────────


def test_save_file_contains_d2_compliant_json(tmp_path):
    """存档文件内容符合 D2 决策：json.dumps + ensure_ascii=False + indent=2。

    验证：
    - 含 "version": 1（V3+ 升级锚点）
    - 含 vars/path/current_block_id
    - ensure_ascii=False → 中文不转义
    """
    import json

    from core.engine.executor import Executor
    from core.engine.protocol import SaveCmd, UserInputCmd
    from runtime.save import SaveManager
    from runtime.load_chapter import load_chapter_safe

    sm = SaveManager(save_dir=tmp_path)
    story = load_chapter_safe(REPO_ROOT / "chapters" / "chapter01_v1.md")

    sink = MixedCmdSink(cmds=[
        UserInputCmd(value="下雨天"),  # 中文
        SaveCmd(slot="cn01"),
        UserInputCmd(value="1"),
    ])
    exe = Executor(story, sink, save_manager=sm)
    exe.run()

    save_path = tmp_path / "cn01.json"
    assert save_path.exists()
    raw = save_path.read_text(encoding="utf-8")
    # 中文不转义（ensure_ascii=False）
    assert "下雨天" in raw
    assert "\\u" not in raw
    # JSON 含 version + current_block_id
    blob = json.loads(raw)
    assert blob["version"] == 1
    assert "vars" in blob
    assert "path" in blob
    assert "current_block_id" in blob
    assert blob["vars"]["mood"] == "下雨天"


# ─── 4. 存档跨进程模拟：手动写存档 → load 恢复 ────────────────────────────


def test_manual_write_save_file_then_load_restores_state(tmp_path):
    """模拟跨进程场景：手动写存档 JSON → 新 Executor load → 状态恢复。

    验证 SaveManager 写入的 JSON 格式可以被任何进程读取（不依赖 Python pickle）。
    """
    import json

    from core.engine.executor import Executor, GameState
    from core.engine.protocol import LoadCmd, UserInputCmd
    from runtime.save import SaveManager
    from runtime.load_chapter import load_chapter_safe

    sm = SaveManager(save_dir=tmp_path)
    # 手动写存档（模拟"其他工具"写存档）
    manual_state = GameState()
    manual_state.vars = {"mood": "雨夜", "pick": 2, "loaded_marker": True}
    manual_state.path = ["start", "c1", "cb"]
    manual_state.current_block_id = "cb"
    (tmp_path / "external.json").write_text(
        json.dumps(manual_state.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 新 Executor 加载存档
    story = load_chapter_safe(REPO_ROOT / "chapters" / "chapter01_v1.md")
    sink = MixedCmdSink(cmds=[
        UserInputCmd(value="placeholder"),
        LoadCmd(slot="external"),
        UserInputCmd(value="never"),  # 不够用，但 LoadAckEvt 后才需要
    ])
    exe = Executor(story, sink, save_manager=sm)
    exe.run()

    # 验证：存档内容被恢复
    assert exe.state.vars["mood"] == "雨夜"
    assert exe.state.vars["loaded_marker"] is True
    assert exe.state.current_block_id == "cb"


# ─── 5. 存档后 list_slots / delete 真实操作 ──────────────────────────────


def test_save_then_list_slots_then_delete_workflow(tmp_path):
    """save → list_slots → delete 完整工作流。"""
    from core.engine.executor import Executor
    from core.engine.protocol import SaveCmd, UserInputCmd
    from runtime.save import SaveManager
    from runtime.load_chapter import load_chapter_safe

    sm = SaveManager(save_dir=tmp_path)
    story = load_chapter_safe(REPO_ROOT / "chapters" / "chapter01_v1.md")

    # 跑两次，每次存不同 slot
    for slot in ("01", "02"):
        sink = MixedCmdSink(cmds=[
            UserInputCmd(value=f"mood_{slot}"),
            SaveCmd(slot=slot),
            UserInputCmd(value="1"),
        ])
        exe = Executor(story, sink, save_manager=sm)
        exe.run()

    # list_slots 返回 2 个
    assert sm.list_slots() == ["01", "02"]

    # delete 01
    assert sm.delete("01") is True
    assert sm.list_slots() == ["02"]

    # delete 不存在的
    assert sm.delete("never") is False
    assert sm.list_slots() == ["02"]


# ─── 6. 跨 Executor 实例状态隔离（v0 行为 + v2 兼容） ────────────────────


def test_executor_state_isolated_per_instance_without_save_load(tmp_path):
    """不存读档：两个 Executor 实例的 state 完全独立（v0 行为）。"""
    from core.engine.executor import Executor
    from core.engine.protocol import UserInputCmd
    from runtime.load_chapter import load_chapter_safe

    story = load_chapter_safe(REPO_ROOT / "chapters" / "chapter01_v1.md")

    # Executor A：mood="A"
    sink_a = MixedCmdSink(cmds=[UserInputCmd("A"), UserInputCmd("1")])
    exe_a = Executor(story, sink_a)
    exe_a.run()

    # Executor B：mood="B"
    sink_b = MixedCmdSink(cmds=[UserInputCmd("B"), UserInputCmd("2")])
    exe_b = Executor(story, sink_b)
    exe_b.run()

    # state 独立
    assert exe_a.state.vars["mood"] == "A"
    assert exe_b.state.vars["mood"] == "B"
    # pick 也独立
    assert exe_a.state.vars["pick"] == 1
    assert exe_b.state.vars["pick"] == 2
