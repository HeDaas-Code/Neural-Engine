"""v1-issue-2 translator prototype TUI shell — 升 v2 translator 时会删除.

运行: python3 docs/prototypes/v0-issue-2-translator/tui.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# 让 prototype 找到 logic.py（同级目录）
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from logic import translate_dsl, PRESET_CASES  # noqa: E402

BOLD = "\x1b[1m"
DIM = "\x1b[2m"
RESET = "\x1b[0m"
CLEAR = "\033[2J\033[H"


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def render_frame(input_str: str, output: str | None, error: str | None) -> None:
    clear()
    print(f"{BOLD}┌─ ExprTranslator Prototype ─────────────────────────{RESET}")
    print(f"{BOLD}│{RESET}")
    print(f"{BOLD}│{RESET} {BOLD}input :{RESET}  {input_str!r}")
    if error is not None:
        print(f"{BOLD}│{RESET} {BOLD}error :{RESET}  {DIM}{error}{RESET}")
    elif output is not None:
        print(f"{BOLD}│{RESET} {BOLD}output:{RESET}  {output!r}")
    else:
        print(f"{BOLD}│{RESET} {BOLD}output:{RESET}  {DIM}(empty input → error){RESET}")
    print(f"{BOLD}│{RESET}")
    print(f"{BOLD}└─ Keys ──────────────────────────────────────────────{RESET}")
    print(f"{BOLD}│{RESET} {BOLD}[1-7]{RESET} 加载预设 case     {BOLD}[p]{RESET} 打印所有预设")
    print(f"{BOLD}│{RESET} {BOLD}[q]{RESET} quit")


def load_case(n: int) -> tuple[str, str, str]:
    return PRESET_CASES[n - 1]


def main() -> None:
    input_str = "非 p_a"
    output: str | None = None
    error: str | None = None

    while True:
        render_frame(input_str, output, error)
        try:
            line = input(f"{BOLD}> {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if line in ("q", "quit", "exit"):
            return
        elif line in ("p", "presets"):
            clear()
            print(f"{BOLD}预设 case:{RESET}")
            for i, (inp, expected, note) in enumerate(PRESET_CASES, 1):
                print(f"  {BOLD}[{i}]{RESET} {inp!r}")
                print(f"      {DIM}期望={expected!r} — {note}{RESET}")
            input(f"\n{BOLD}> {RESET}Enter 回主菜单...")
        elif line in ("1", "2", "3", "4", "5", "6", "7"):
            n = int(line)
            if 1 <= n <= len(PRESET_CASES):
                input_str, expected, note = load_case(n)
                try:
                    output = translate_dsl(input_str)
                    expected_calc = expected
                    if output == expected_calc:
                        error = None
                    else:
                        error = f"❌ 实际 {output!r} ≠ 期望 {expected!r} — {note}"
                except Exception as e:  # noqa: BLE001
                    output = None
                    error = f"💥 {type(e).__name__}: {e}"
        else:
            # 自定义输入
            input_str = line
            try:
                output = translate_dsl(input_str)
                error = None
            except Exception as e:  # noqa: BLE001
                output = None
                error = f"💥 {type(e).__name__}: {e}"


if __name__ == "__main__":
    main()
