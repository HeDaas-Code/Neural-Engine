"""存档/读档管理器 —— v2 落地（V2-07 · EP-07/EP-09/EP-11）。

设计决策：
- D4 决策：默认存档目录 `~/.neural-engine/saves/{slot}.json`（用户级存档）
- D2 决策：序列化复用 protocol.py 的 `json.dumps + utf-8 + ensure_ascii=False + indent=2`
- 路径校验：slot 名仅允许 `[\\w-]+`，防路径穿越（`../escape`、`/etc/passwd` 等）
- 跨平台：Windows / Unix 都用 `pathlib.Path`，分隔符由 Path 自动处理

API：
- `SaveManager(save_dir=...)` —— 默认 `~/.neural-engine/saves`
- `save(slot, state)` —— state → JSON 文件（覆盖写）
- `load(slot) -> GameState` —— JSON 文件 → state（缺文件 → FileNotFoundError）
- `list_slots() -> list[str]` —— 所有存档 slot 名（sorted）
- `delete(slot) -> bool` —— 删现有存档返 True；不存在返 False

v2 阶段未实现（v3+ 任务）：
- 存档元数据（游玩时长 / 截图 / 时间戳）
- 自动存档（autosave）
- 存档校验和 / 加密
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from core.engine.executor import GameState


# 合法 slot 名：字母数字 + 下划线 + 短横线（防路径穿越 + 跨平台文件名安全）
_SLOT_PATTERN = re.compile(r"^[\w-]+$")


def _validate_slot(slot: str) -> None:
    """校验 slot 名合法：仅允许 `[\\w-]+`（防路径穿越 + 空 + 特殊字符）。

    Raises:
        ValueError: slot 非法（含具体原因）。
    """
    if not isinstance(slot, str):
        raise ValueError(
            f"slot 必须为 str，得到 {type(slot).__name__}"
        )
    if not slot:
        raise ValueError("slot 不能为空字符串")
    if not _SLOT_PATTERN.match(slot):
        raise ValueError(
            f"非法 slot 名 {slot!r}：仅允许字母数字、下划线、短横线（[\\w-]+）"
        )


class SaveManager:
    """存档/读档管理 —— v2 落地（V2-07）。

    默认存档目录：`~/.neural-engine/saves/`（D4 决策）。
    实例化时若 save_dir 不存在则自动创建（parents=True, exist_ok=True）。

    Example:
        >>> mgr = SaveManager()
        >>> mgr.save("01", game_state)
        >>> loaded = mgr.load("01")
        >>> mgr.list_slots()
        ['01']
        >>> mgr.delete("01")
        True
    """

    def __init__(self, save_dir: Path | str | None = None):
        """构造 SaveManager。

        Args:
            save_dir: 存档目录路径。None → `Path.home() / ".neural-engine" / "saves"`
                （D4 决策）。其他类型自动转 Path。
        """
        if save_dir is None:
            # D4 决策：用户级存档目录
            self.save_dir: Path = Path.home() / ".neural-engine" / "saves"
        else:
            self.save_dir = Path(save_dir)
        # 自动创建目录（parents=True, exist_ok=True）
        self.save_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, slot: str) -> Path:
        """取 slot 对应文件路径（不校验 slot 合法性——save/load/delete 入口会校验）。"""
        return self.save_dir / f"{slot}.json"

    def save(self, slot: str, state: GameState) -> None:
        """存档：state → JSON 文件。

        D2 决策：序列化用 `json.dumps(ensure_ascii=False, indent=2) + utf-8`（与 protocol.py 一致）。

        Args:
            slot: 存档槽位名（仅允许 `[\\w-]+`）。
            state: 当前 GameState（GameState.to_dict() 输出含 version/vars/path/current_block_id）。

        Raises:
            ValueError: slot 非法（路径穿越 / 空 / 含特殊字符）。
            OSError: 文件写入失败（权限 / 磁盘满）。
        """
        _validate_slot(slot)
        path = self._path_for(slot)
        # D2 决策：json.dumps + ensure_ascii=False（中文不转义）+ indent=2（人可读）
        path.write_text(
            json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load(self, slot: str) -> GameState:
        """读档：JSON 文件 → GameState。

        Args:
            slot: 存档槽位名（仅允许 `[\\w-]+`）。

        Returns:
            反序列化的 GameState（含 vars/path/current_block_id/version 校验）。

        Raises:
            ValueError: slot 非法。
            FileNotFoundError: 存档文件不存在。
            json.JSONDecodeError: 存档文件 JSON 格式损坏。
        """
        _validate_slot(slot)
        path = self._path_for(slot)
        # FileNotFoundError / JSONDecodeError 自然传播
        data = json.loads(path.read_text(encoding="utf-8"))
        return GameState.from_dict(data)

    def list_slots(self) -> list[str]:
        """列出所有存档槽位名（按字母排序）。

        Returns:
            所有 `{slot}.json` 文件的 slot 名（sorted 升序）。空目录返回 []。
        """
        return sorted([p.stem for p in self.save_dir.glob("*.json")])

    def delete(self, slot: str) -> bool:
        """删除存档槽位。

        Args:
            slot: 存档槽位名（仅允许 `[\\w-]+`）。

        Returns:
            True —— 文件存在并删除成功；False —— 文件不存在（不抛错）。

        Raises:
            ValueError: slot 非法（路径穿越 / 空 / 含特殊字符）。
        """
        _validate_slot(slot)
        path = self._path_for(slot)
        if not path.exists():
            return False
        path.unlink()
        return True
