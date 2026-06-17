# Choice Failure — Root-Cause Analysis

**Status:** investigation only. **No extraction/parser code was modified.**
**Method:** cross-referenced `reports/corrupted_questions.json` against the merged
output and the raw source PDFs (re-read with the existing `utils.get_blocks_in_reading_order`),
comparing parsed `choices` to what the source actually contains.

---

## 1. Headline numbers (correcting the earlier "~100" estimate)

`broken_choices` total = **162**, but these are two very different populations:

| Population | Count | Nature |
|---|---|---|
| **Reading** `broken_choices` | **69** | Real defects — all parser-fixable (see §3) |
| **Math** `broken_choices` | **93** | **~50 are audit false positives**; ~37 real (see §6) |

The earlier "~100 reading" figure conflated math. The true reading number is **69**,
and it is concentrated in exactly two tests:

| Test | Reading broken_choices | Failure mode |
|---|---|---|
| 11 | 66 | Choices merged (newline-separated) |
| 8 | 3 | Bullet (`•`) choice markers, not `A) B) C) D)` |
| 4, 5, 6, 7, 9, 10 | **0** | Reading choices parse cleanly |

The clean result on six of eight tests is strong evidence that this is **localized
format variation**, not a general parser failure.

---

## 2. Sample evidence (raw source vs. parsed)

### Test 11 — `test11_rw_m1_q1` (page 4)
**Raw source blocks (reading order):**
```
'A) comprehend'
'B) dislike\nC) interrupt\nD) overlook'      ← B, C, D in ONE block, newline-separated
```
**Parsed choices:**
```json
{ "A": "comprehend", "B": "dislike\nC) interrupt\nD) overlook" }
```
**Expected:**
```json
{ "A": "comprehend", "B": "dislike", "C": "interrupt", "D": "overlook" }
```
All four choices are present in the source. C and D were never split out.

### Test 8 — `test8_rw_m2_q1` (page 18)
**Raw source blocks:**
```
'Which choice completes the text with the most\nlogical and precise word or phrase?'
'• confusing for'
'• attractive to'
'• corrected by'
'• similar to'
```
**Parsed choices:** `null`  →  type was demoted to `numeric_response`, then merge
re-tagged it `multiple_choice` (answer key has a letter) but `choices` stayed `null`.
**Expected:**
```json
{ "A": "confusing for", "B": "attractive to", "C": "corrected by", "D": "similar to" }
```
The four choices exist in the source — as `•` bullets, not `A) B) C) D)` markers.
(Page 18 contains 12 such bullets = 3 questions × 4 choices.)

---

## 3. Failure categories (reading)

| Category | Code | Count | Tests | Root cause |
|---|---|---|---|---|
| **A. Choices merged into a previous choice** | parser bug | **66** | 11 | B/C/D arrive in a single text block separated by `\n`; the inline splitter only handles `\|` separators, so it never splits them. |
| **C. Inline choice format differs from normal SAT layout** | format variant | **3** | 8 | Choices use `•` bullet markers instead of `A) B) C) D)`; the marker-based detector finds none. |
| B. Choices in source but regex missed them | — | 0 | — | (Subsumed by A/C; in both cases the text is present.) |
| D. OCR removed the choice markers | OCR loss | **0** | — | No reading case lost choices to OCR. |
| E. Other parser bug | — | 0 | — | — |

**All 66 test-11 cases are confirmed recoverable**: every merged value still contains
the `C)` and `D)` markers, so a newline-aware split fully reconstructs them.

---

## 4. Recoverability & parser-bug vs OCR split (reading)

| | Count | % of 69 |
|---|---|---|
| Parser bug — fully recoverable, text present | **69** | **100%** |
| OCR / source-quality loss | **0** | 0% |
| Requires manual repair | **0** | 0% |

Of the reading `broken_choices`, **100% are parser bugs and 0% are OCR loss.**
No manual transcription is required — every choice exists in the source text.

(One advisory: the test-8 bullet choices must be mapped to A–D **in source order**;
this should be spot-verified against the answer key for the 3 affected questions.)

---

## 5. Recommended fixes (for approval — not yet applied)

### Parser fix 1 — newline-merged choices (recovers 66, test 11)
In `extract_questions.parse_question_block`, the inline-choice splitter currently is:
```python
_INLINE_CHOICE_SEP = re.compile(r"\s*\|\s*(?=[ABCD]\))")
```
Generalize the separator to also split on a newline that precedes a choice marker:
```python
_INLINE_CHOICE_SEP = re.compile(r"\s*[|\n]\s*(?=[ABCD]\))")
```
The `(?=[ABCD]\))` lookahead means wrapped lines inside a choice (newlines NOT
followed by a marker) are left intact — safe. Expected to fix all 66.

### Parser fix 2 — bullet-marker choices (recovers 3, test 8)
Add a fallback in choice detection: when a question has **no `A)–D)` markers** but is
followed by **exactly four `•`-prefixed short blocks** (after the "Which choice…"
prompt and before the next question number), treat those four as choices A–D in order.
Guard against rhetorical-synthesis "student notes" (which also use `•`) by only
applying this **after** the prompt line, never to passage bullets.

### Extraction fix — re-run + re-audit
After the two parser fixes, re-run `extract_questions.py --test 8 --test 11`, then
`merge.py`, then `audit_question_quality.py`. Expected reading `broken_choices` → **0**.

### Manual repair
**None required** for reading. Only spot-check: confirm the 3 test-8 bullet choices
map to the answer-key letters in source order.

---

## 6. Side finding — audit heuristic false positives (math)

Math `broken_choices` = 93, but the breakdown shows the audit over-fires:

| Sub-pattern | Count | Verdict |
|---|---|---|
| `truncated choice` (value ≤ 1 char) | **50** | **False positive** — valid single-digit numeric MC answers, e.g. `{"A":"6","B":"30","C":"450","D":"900"}` |
| merged / missing keys | 29 | Real — garbled formula choices (e.g. `test4_math_m1_q19`); text present but OCR-mangled |
| duplicate | 6 | Mixed — some valid repeated values, some real |
| missing keys (no merge) | 5 | Real |
| null choices | 3 | Real |

**Recommendation (audit, not parser):** refine the `broken_choices (truncated choice)`
heuristic to ignore single-character choices that are valid numbers, removing ~50 false
positives. The remaining ~37 math cases are formula-OCR damage — **not text-fixable**;
they belong to the cropped-figure roadmap item, not the parser fix.

---

## 7. Bottom line

- **Reading: 69 broken_choices, 100% parser bug, 0% OCR, 0 manual repair.**
  Two small, well-understood format variants (test 11 newline-merge; test 8 bullets).
  Two targeted parser changes recover all 69.
- **Math: 93 broken_choices, but ~50 are audit false positives** (valid short numeric
  answers). Real math choice damage is ~37 and is OCR/source-quality, not parser.
- Evidence supports proceeding with the two reading parser fixes; defer math to the
  image/figure track and tune the audit heuristic separately.
