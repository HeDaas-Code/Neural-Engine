r"""存档/读档管理器 —— v2 占位。

v2 阶段（EP-07）：仅占位类，不实现 save/load/list_slots 方法。
v3+ 落地路径（V2-07 任务）：
- 默认存档目录：D4 决策 `~/.neural-engine/saves/{slot}.json`
- 序列化：D2 决策复用 `protocol.py` json.dumps + utf-8
- 路径校验：slot 名仅允许 `[\w-]+`，防路径穿越
"""
from __future__ import annotations


class SaveManager:
    """存档/读档管理占位类 —— v3+ 落地。

    v2 阶段：仅暴露类名（EP-07 骨架）。v3+ 任务 V2-07 补
    `save(slot, state)` / `load(slot)` / `list_slots()` 方法。
    """