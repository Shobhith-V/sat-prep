# Audit Heuristic Tuning — Before / After

**Scope:** only `scripts/audit_question_quality.py` was modified.
**No extraction pipeline changes. No question data changes.**
**Goal:** better precision — accept valid short/numeric answers, keep flagging genuine corruption.

## What changed
The `broken_choices` "truncated choice" rule used a length test (`len(v) <= 1`),
which flagged valid single-digit answers like `{"A":"6","B":"30"}`. It was replaced by
two content-based tests:

- **non-answer fragment** — a choice with no letter/digit and no math symbol
  (pure punctuation/operator junk, e.g. `"⎟"`, `"+"`). Valid answers — `"6"`,
  `"30"`, `"1/2"`, `"0.25"`, `"√2"`, `"π"`, `"2π"`, `"−3"`, `"x"` — all pass.
- **garbled choice** — OCR formula garble that is never a real answer: layout-bracket
  glyphs (`⎛⎜⎝⎞⎟⎠`) or a lone parenthesis/bracket on its own line (e.g. `"w w + 9\n(\n)"`).
  Stacked fractions like `"1\n3"` are deliberately **not** flagged.

Length alone is no longer a signal. `empty choice`, `missing/incomplete keys`,
and `duplicate choices` checks are unchanged.

## Metrics

| Metric | Before | After | Δ |
|---|---|---|---|
| **Total flagged** | 257 / 945 (27.2%) | **230 / 945 (24.3%)** | **−27** |
| **broken_choices** | 74 | **35** | **−39** |

39 false-positive choice flags removed; total dropped only 27 because 12 of those
questions remain flagged by other heuristics (e.g. `single_char_lines` on their
formula text) — correctly, since their *question text* is still noisy.

## Categorization of the original 74 broken_choices

| Category | Count | Disposition |
|---|---|---|
| Valid numeric / short answers (`"6"`, `"30"`, `"4"`, `"w"`, …) | ~39 | **Now accepted** (were false positives) |
| Garbled formula choices (lone parens, layout brackets) | 18 | **Still flagged** (genuine OCR) |
| Missing / incomplete keys (incl. `null`) | 11 | **Still flagged** (genuine extraction) |
| Duplicate choice values | 6 | **Still flagged** (genuine) |

After tuning, **all 35 remaining `broken_choices` are genuine** — 0 known false
positives. Valid math answers no longer warn.

### Sanity check (valid-digit questions, now NOT flagged)
| Question | Choices | In broken_choices? |
|---|---|---|
| `test4_math_m1_q3` | `{A:6, B:30, C:450, D:900}` | No ✓ |
| `test4_math_m2_q16` | `{A:3, B:21, C:41, D:139}` | No ✓ |
| `test9_math_m1_q1` | `{A:2, B:8, C:10, D:24}` | No ✓ |
| `test11_math_m2_q17` | `{A:4, B:16, C:32, D:36}` | No ✓ |

## Sample of 10 remaining broken_choices (and why)

| # | Question | Reason | Why it's genuine |
|---|---|---|---|
| 1 | `test4_math_m1_q19` | garbled choice | choices are newline-fragmented formulas with `⎛⎜⎝⎟⎠` bracket glyphs |
| 2 | `test5_math_m1_q16` | keys=['B','D'] | A and C missing — graph-option choices not extracted |
| 3 | `test6_math_m1_q2` | keys=['A','C'] | B/D merged into A; choice text is graph OCR noise |
| 4 | `test6_math_m1_q17` | duplicate choices | A == C and B == D (`"C\nP\nN\n= 19 +"`) — OCR produced identical garble |
| 5 | `test6_math_m1_q26` | garbled choice | each choice ends `"…\n(\n)"` — lone parens on their own lines |
| 6 | `test6_math_m2_q8` | garbled choice | polynomial choices fragmented across lines with lone `(` `)` |
| 7 | `test6_math_m2_q18` | keys=['A','B','C'] | D missing; choices are stacked fractions, one dropped |
| 8 | `test6_math_m2_q22` | keys=['A','B','C'] | D missing; choices garbled (`"__t 26 37"`) |
| 9 | `test6_math_m2_q25` | keys=['A','B','C'] | D missing; OCR-garbled radical choices |
| 10 | `test7_math_m1_q1` | missing choices | `choices: null` — choices absent from source extraction |

Every remaining flag points at real OCR/extraction damage (garbled formula
choices, dropped/duplicated choices, null choices) — none are valid answers being
penalized for being short. Genuine extraction failures are preserved.

## Note
These remaining 35 are concentrated in math formula/graph questions and are
**not text-repairable** — they belong to the cropped-figure extraction track, not
a parser fix. The reading section has **0** broken_choices.
