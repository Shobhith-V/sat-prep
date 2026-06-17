# Parser Fix — Before / After Report

**Scope:** applied the two approved parser fixes, re-extracted **tests 8 and 11 only**,
re-merged + re-classified those two tests, rebuilt the consolidated dataset, and
re-ran the quality audit. No other tests were modified. No LLM repair was performed.

## Fixes applied (`scripts/extract_questions.py`)
1. **Newline-separated choices** — generalized the inline-choice splitter from
   `\s*\|\s*(?=[ABCD]\))` to `\s*[|\n]\s*(?=[ABCD]\))`, so choices merged into one
   block by newlines (the test-11 layout) are split. Lookahead leaves wrapped
   choice text intact.
2. **Bullet-marker choices** — added a fallback: when a question has no `A)–D)`
   markers but exactly four `•`-bullet lines after the "Which choice" prompt, they
   map to A–D in source order (the test-8 layout). Guarded so passage/notes bullets
   are never captured.

## Headline metrics

| Metric | Before | After | Δ |
|---|---|---|---|
| **Total flagged** | 330 / 945 (34.9%) | **257 / 945 (27.2%)** | **−73** |
| **broken_choices (total)** | 162 | **74** | **−88** |
| **broken_choices (reading)** | 69 | **0** | **−69** |
| Test 8 flagged | 28 | 25 | −3 |
| Test 11 flagged | 109 | 39 | −70 |

## What changed
- **All 69 reading `broken_choices` are resolved** (66 test-11 newline-merge + 3
  test-8 bullets). Reading broken_choices is now **0** across all eight tests.
- Fix 1 also recovered **19 math merged-choice cases** in tests 8/11 (math
  `broken_choices` 93 → 74), since those choices were merged by the same
  newline pattern.
- Test 11's flagged count fell the most (109 → 39); its remaining flags are
  math formula/figure OCR noise (single-char lines, isolated operators), not
  choice defects.

## Spot-verification (post-fix)
| Question | Repaired choices | Answer key ↔ explanation |
|---|---|---|
| `test11_rw_m1_q1` | A comprehend · B dislike · C interrupt · D overlook | consistent |
| `test8_rw_m2_q1` | A confusing for · B attractive to · C corrected by · D similar to | correct=B "attractive to" ↔ "Choice B is the best answer" ✓ |
| `test8_rw_m2_q2` | A preventable · B undeniable · C common · D concerning | correct=A ↔ "Choice A…" ✓ |
| `test8_rw_m2_q3` | A resilient · B inadequate · C dynamic · D satisfactory | correct=B ↔ "Choice B…" ✓ |

Bullet ordering (A–D = source order) matches the answer-key letters and the
explanation text — **no manual repair required**.

Merge type-corrections for test 8 dropped from **3 → 0** (the previously
`choices:null` questions now extract real choices and the correct type).

## Remaining flagged (not addressed — by design)
- **Math 199 flagged** — formula/figure OCR fragmentation; not text-repairable
  (cropped-figure track).
- **~50 of math `broken_choices` are audit false positives** (valid single-digit
  numeric answers like `{"A":"6"}`); fix the audit heuristic separately.

## Artifacts updated
- `output/test8.json`, `output/test11.json` (re-extracted, merged, classified)
- `output/all_questions.json` (consolidated 945-question dataset, rebuilt)
- `reports/corrupted_questions.json` (re-run audit)
