"""存档/读档管理器 —— v2 落地（V2-07 · EP-07/EP-09/EP-11）。

设计决策：
- D4 决策：默认存档目录 `~/.neural-engine/saves/{slot}.json`（用户级存档）
- D2 决策：序列化复用 protocol.py 的 `json.dumps + utf-8 + ensure_ascii=False + indent=2`
- 路径校验：slot 名仅允许 `[\\w-]+`，防路径穿越（`../escape`、`/etc/passwd` 等）
- 跨平台：Windows / Unix 都用 `pathlib.Path`，分隔符由 Path 自动处理

API：
- `SaveManager(save_dir=...)` —— 默认 `~/.neural-engine/saves`
- `save(slot, state, screenshot=None)` —— state → JSON 文件 + 可选截图 PNG（v3-05）
- `load(slot) -> GameState` —— JSON 文件 → state（缺文件 → FileNotFoundError）
- `get_screenshot(slot) -> bytes | None` —— v3-05 取截图 PNG bytes
- `list_slots() -> list[str]` —— 所有存档 slot 名（sorted）
- `list_slots_with_meta() -> list[dict]` —— v3-05 含截图/时间戳/大小元数据
- `delete(slot) -> bool` —— 删现有存档（含截图）返 True；不存在返 False

v3-05 (#95) 扩展：
- 存档截图（PNG bytes 存为 {slot}.png）
- list_slots_with_meta() 返回元数据供 SaveSlotDialog 网格缩略图用

v2 阶段未实现（v3+ 任务）：
- 自动存档（autosave）
- 存档校验和 / 加密
"""
from __future__ import annotations

import json
import re
from datetime import datetime
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
        """取 slot 对应 JSON 文件路径（不校验 slot 合法性——save/load/delete 入口会校验）。"""
        return self.save_dir / f"{slot}.json"

    def _screenshot_path_for(self, slot: str) -> Path:
        """v3-05: 取 slot 对应截图 PNG 文件路径。"""
        return self.save_dir / f"{slot}.png"

    def save(
        self,
        slot: str,
        state: GameState,
        screenshot: bytes | None = None,
    ) -> None:
        """存档：state → JSON 文件 + 可选截图 PNG（v3-05）。

        D2 决策：序列化用 `json.dumps(ensure_ascii=False, indent=2) + utf-8`（与 protocol.py 一致）。

        v3-05 (#95): screenshot 参数非空时，额外写入 `{slot}.png` 截图文件（覆盖写）。
        screenshot=None 时不写截图文件（向后兼容 v2 行为）。

        Args:
            slot: 存档槽位名（仅允许 `[\\w-]+`）。
            state: 当前 GameState（GameState.to_dict() 输出含 version/vars/path/current_block_id）。
            screenshot: v3-05 PNG 截图 bytes（None=不存截图）。

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
        # v3-05: 截图存储
        if screenshot is not None:
            self._screenshot_path_for(slot).write_bytes(screenshot)

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

    def get_screenshot(self, slot: str) -> bytes | None:
        """v3-05: 取 slot 截图 PNG bytes。

        Args:
            slot: 存档槽位名（仅允许 `[\\w-]+`）。

        Returns:
            PNG bytes —— 截图存在；None —— 截图不存在或 slot 无效（不抛错）。
        """
        try:
            _validate_slot(slot)
        except ValueError:
            return None
        path = self._screenshot_path_for(slot)
        if not path.exists():
            return None
        try:
            return path.read_bytes()
        except OSError:
            return None

    def list_slots(self) -> list[str]:
        """列出所有存档槽位名（按字母排序）。

        Returns:
            所有 `{slot}.json` 文件的 slot 名（sorted 升序）。空目录返回 []。
        """
        return sorted([p.stem for p in self.save_dir.glob("*.json")])

    def list_slots_with_meta(self) -> list[dict]:
        """v3-05: 列出所有存档槽位 + 元数据（供 SaveSlotDialog 网格缩略图用）。

        Returns:
            list[dict]，每项含：
            - slot: str —— 槽位名
            - has_screenshot: bool —— 是否有截图
            - mtime: str —— ISO 格式最后修改时间（"" 表示无）
            - size: int —— JSON 文件大小（bytes）
            按 slot 名升序排序。
        """
        result: list[dict] = []
        for slot in self.list_slots():
            json_path = self._path_for(slot)
            shot_path = self._screenshot_path_for(slot)
            try:
                mtime = datetime.fromtimestamp(json_path.stat().st_mtime).isoformat()
                size = json_path.stat().st_size
            except OSError:
                mtime = ""
                size = 0
            result.append({
                "slot": slot,
                "has_screenshot": shot_path.exists(),
                "mtime": mtime,
                "size": size,
            })
        return result

    def delete(self, slot: str) -> bool:
        """删除存档槽位（含截图，v3-05）。

        Args:
            slot: 存档槽位名（仅允许 `[\\w-]+`）。

        Returns:
            True —— JSON 文件存在并删除成功；False —— JSON 文件不存在（不抛错）。
            （v3-05: 截图文件若存在也会被一并删除，但不影响返回值。）

        Raises:
            ValueError: slot 非法（路径穿越 / 空 / 含特殊字符）。
        """
        _validate_slot(slot)
        path = self._path_for(slot)
        if not path.exists():
            return False
        path.unlink()
        # v3-05: 一并删除截图文件（若存在，静默）
        shot = self._screenshot_path_for(slot)
        if shot.exists():
            try:
                shot.unlink()
            except OSError:
                pass
        return True
