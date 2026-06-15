"""v1-issue-7 chapter01 端到端: bool_expr 真求值.

构造一个含 `node if?` 的 v1 fixture .md, 跑全 Executor 链路, 验证 bool_expr 真选分支.
不污染 chapters/chapter01.md (v0 fixture 保持原状).
"""
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = "/home/hedaas/桌面/Neural Engine"
sys.path.insert(0, f"{REPO_ROOT}/src")

from core.engine.executor import Executor, MemoryInputSink  # noqa: E402
from core.engine.main import _load_story  # noqa: E402


V1_FIXTURE = """\
# v1-issue-7 fixture: bool_expr 真求值端到端

```neon
id:start
id:end0
ce_high<-next:high
ce_low<-next:low
node start
node in ->p_score
node if? p_score 大于 50 [1:ce_high,2:ce_low]
node end
```

```neon
id:high
id:end0
node start
node echo p_score
node end
```

```neon
id:low
id:end0
node start
node echo p_score
node end
```
"""


@pytest.fixture
def v1_fixture_path(tmp_path):
    p = tmp_path / "v1_bool_expr.md"
    p.write_text(V1_FIXTURE, encoding="utf-8")
    return p


# 1. 高分组: p_score=60 走 ce_high
def test_bool_expr_high_score_picks_high_branch(v1_fixture_path):
    story = _load_story(str(v1_fixture_path))
    sink = MemoryInputSink(inputs=["60"])
    exe = Executor(story, sink)
    exe.run()
    from core.engine.protocol import TextEvt  # noqa: PLC0415
    echo_evts = [e for e in sink.events if isinstance(e, TextEvt)]
    assert len(echo_evts) == 1
    assert echo_evts[0].content == "60"


# 2. 低分组: p_score=30 走 ce_low
def test_bool_expr_low_score_picks_low_branch(v1_fixture_path):
    story = _load_story(str(v1_fixture_path))
    sink = MemoryInputSink(inputs=["30"])
    exe = Executor(story, sink)
    exe.run()
    from core.engine.protocol import TextEvt  # noqa: PLC0415
    echo_evts = [e for e in sink.events if isinstance(e, TextEvt)]
    assert len(echo_evts) == 1
    assert echo_evts[0].content == "30"


# 3. 边界: p_score=50 走 ce_low (大于 50 是严格大于, 50 不满足)
def test_bool_expr_boundary_score_50_picks_low_branch(v1_fixture_path):
    story = _load_story(str(v1_fixture_path))
    sink = MemoryInputSink(inputs=["50"])
    exe = Executor(story, sink)
    exe.run()
    from core.engine.protocol import TextEvt  # noqa: PLC0415
    echo_evts = [e for e in sink.events if isinstance(e, TextEvt)]
    assert len(echo_evts) == 1
    assert echo_evts[0].content == "50"

