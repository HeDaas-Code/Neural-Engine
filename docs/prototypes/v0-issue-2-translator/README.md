# v1-issue-2 translator prototype

**问**: ExprTranslator 的 Chinese 关键字替换规则，**边界处理对不对**?

具体风险:
1. `非` 句首 vs `非法`/`非常` (避免误吃)
2. `大于等于` 必须先匹配, 否则被 `大于` + `=` 误拆
3. `且`/`或`/`包含` 在括号边界 (lookbehind/lookahead)
4. collapse 重复空白

## 运行

```bash
python3 docs/prototypes/v0-issue-2-translator/tui.py
```

按 `1-7` 加载预设 case, 直接看结果. 按 `p` 列所有预设.

## 7 个预设 case

| # | 输入 | 期望 | 说明 |
|---|---|---|---|
| 1 | `非 p_a` | `not p_a` | 句首 `非` |
| 2 | `非常 p_a` | `非常 p_a` | `非常` 不应被吃 |
| 3 | `p_a 大于等于 18` | `p_a >= 18` | 顺序敏感 |
| 4 | `非 p_a 且 p_b` | `not p_a and p_b` | 句首非 + 中缀 |
| 5 | `p_a 大于 0 且 p_b 等于 1` | `p_a > 0 and p_b == 1` | 组合 |
| 6 | `(p_a 大于 0) 或 p_c` | `(p_a > 0) or p_c` | 括号边界 |
| 7 | `在古代` | `在古代` | 未知词保留 |

## 文件

- `logic.py` — 纯函数 `translate_dsl` (升 v2 translator 时会迁移到 v0 translator)
- `tui.py` — TUI shell (用完即扔)

## 答案

见 `NOTES.md`.
