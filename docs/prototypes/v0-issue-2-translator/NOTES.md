# v1-issue-2 translator prototype — 答案

## 跑了 7 个 preset + 3 个边界 case

### ✅ 通过的（10 个）

1. `非 p_a` → `not p_a`（句首 `非`）
2. `非常 p_a` → `非常 p_a`（`非常` 不被吃）
3. `p_a 大于等于 18` → `p_a >= 18`（顺序敏感）
4. `非 p_a 且 p_b` → `not p_a and p_b`
5. `p_a 大于 0 且 p_b 等于 1` → `p_a > 0 and p_b == 1`
6. `(p_a 大于 0) 或 p_c` → `(p_a > 0) or p_c`
7. `在古代` → `在古代`（未知词保留）
8. `"在古代" 且 p_a` → `"在古代" and p_a`（引号包裹中文不动）
9. `在古代 且 p_score 大于 50` → `p_era==1 and p_score > 50`（register_keyword 联调）
10. `register_keyword 测试` → 原样（未知词保留——**这本来就该对**）

### ❌ 失败的（1 个）—— 设计发现

**`"非 const" 等于 1` → `"not const" == 1`** ❌

引号内 `非` 被错误翻译. 当前 prototype 的 lookbehind 保护不了引号.

## 设计结论（升 v2 translator 时要处理）

### 结论 1: 边界规则用 `(?<![一-龥\w])` 即可

`[一-龥]` 覆盖所有 CJK Unicode 范围——`非常`/`非法` 不被吃, 句首 `非` 仍能匹配.

### 结论 2: 比较关键字 (大于等于/小于等于) 必须先于 (大于/小于) 替换

否则 `p_a 大于等于 18` 会被拆成 `p_a > = 18`（非法 Python）.

### 结论 3: collapse 空白是必要的

否则 `p_a 且 p_b` 替换后变 `p_a  and  p_b`（双倍空格）.

### 结论 4 ⚠️ 待发现: 字符串字面量保护

`"非 const"` 里的 `非` 不应被翻译. v1-issue-2 应**新增**: 扫描引号包裹区域, 标记为 "已保护" 跳过替换.

具体实现思路:
- 预扫描: 找出所有 `"..."` 区间, 记录起止 index
- 替换时: 跳过这些区间
- 边界检查也更新: `(?<!...)` 左侧字符是 `"` 时也要保护

### 结论 5: register_keyword 先于关键字替换

`在古代` 替换成 `p_era==1` 后, 字符串里 `p_era` 不会被二次翻译. 但 `1` 也不会被中文比较字吃——OK.

## 升 v1-issue-2 时要做的

1. **把 `logic.py` 的规则挪进 `src/core/engine/expr/translator.py`**（v0 占位 → v1 真实）
2. **加结论 4 的字符串字面量保护**——加测试
3. **加 register_keyword 真实接入到 to_python_expr**（v0 写好了接口但没接）

## 抛掉 prototype 的时机

升完 v1-issue-2 后删 `docs/prototypes/v0-issue-2-translator/`（logic.py 已迁走, TUI 没价值）。
