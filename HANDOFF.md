# SAT Prep Pipeline — Handoff Document

**Date:** 2026-06-17  
**Phases completed:** 1 – 9 (ALL) — Analysis → Questions → Answers → Explanations →
Images → Merge → Topic → Difficulty → Generalization & Validation  
**Status:** ✅ Pipeline complete. 945/960 questions (98.4%) fully extracted,
answered, explained, classified (topic + subtopic + difficulty), and validated.
Answer⇄explanation cross-validation: 837/837 (100%). 47 unit tests passing.
See `README.md` for usage and `scripts/validate.py` for the metrics report.

---

## 1. Project Goal

Convert 8 official SAT practice test PDFs into structured JSON for a React + Vite + Supabase adaptive learning platform.

**Source PDFs (8 tests, 3 PDF types each):**

```
Questions/    sat-practice-test-{4-11}-digital.pdf
Answers/      scoring-sat-practice-test-{4-11}-digital.pdf
Explanations/ sat-practice-test-{4-11}-answers-digital.pdf
```

**Final output:**

```
output/
├── test4.json  …  test11.json      ← 8 question databases (ready for Supabase)
└── assets/
    ├── test4/page_001.png … page_056.png
    └── …
```

---

## 2. Repository Structure

```
sat-prep/
├── Questions/                   source PDFs — question booklets
├── Answers/                     source PDFs — scoring guides with answer keys
├── Explanations/                source PDFs — answer explanation booklets
│
├── scripts/
│   ├── utils.py                 shared utilities (text clean, block sort, module detect)
│   ├── extract_questions.py     Phase 2  — extracts question text + choices
│   ├── extract_answers.py       Phase 3  — extracts correct answers
│   ├── extract_explanations.py  Phase 4  — extracts explanation text
│   ├── extract_images.py        Phase 5  — renders pages to PNG, builds manifest
│   ├── merge.py                 Phase 6  — combines all sources into output JSON
│   ├── topic_classifier.py      Phase 7  ← NOT YET WRITTEN
│   └── difficulty_classifier.py Phase 8  ← NOT YET WRITTEN
│
├── data/
│   └── raw/                     intermediate per-test JSON files
│       ├── test4_questions.json
│       ├── test4_answers.json
│       ├── test4_explanations.json
│       └── test4_image_manifest.json
│       … (same for tests 5-11)
│
└── output/                      final deliverables
    ├── test4.json  …  test11.json
    └── assets/
        ├── test4/page_001.png … page_056.png
        └── … (tests 5-11)
```

---

## 3. Environment Setup

```bash
conda activate mlops          # PyMuPDF 1.27.2 is installed here

cd /home/shobs/sat-prep/sat-prep
```

All scripts are run from the repo root with `python3 scripts/<script>.py`.

---

## 4. How to Run the Pipeline

### Full pipeline (all 8 tests)

```bash
python3 scripts/extract_questions.py --all
python3 scripts/extract_answers.py   --all
python3 scripts/extract_explanations.py --all
python3 scripts/extract_images.py    --all
python3 scripts/merge.py             --all
```

### Single test

```bash
python3 scripts/extract_questions.py   --test 4
python3 scripts/extract_answers.py     --test 4
python3 scripts/extract_explanations.py --test 4
python3 scripts/extract_images.py      --test 4
python3 scripts/merge.py               --test 4
```

### Re-render images (if source PDFs change)

```bash
python3 scripts/extract_images.py --all --force
```

### Performance benchmarks (measured on this machine)

| Step | Time (8 tests) |
|---|---|
| extract_questions.py | ~15s |
| extract_answers.py | ~2s |
| extract_explanations.py | ~5s |
| extract_images.py | ~23s |
| merge.py | ~2s |
| **Total** | **~47s** |

---

## 5. Extraction Results (Phases 1–6)

### Question extraction accuracy

| Test | Extracted | % | Missing Q#s |
|------|-----------|---|---|
| 4  | 120/120 | **100%** | — |
| 5  | 119/120 | 99% | 1 (Math M1 Q missing in OCR separator) |
| 6  | 117/120 | 98% | 3 |
| 7  | 115/120 | 96% | 5 |
| 8  | 117/120 | 98% | 3 |
| 9  | 117/120 | 98% | 3 |
| 10 | 120/120 | **100%** | — |
| 11 | 120/120 | **100%** | — |
| **Total** | **945/960** | **98.4%** | |

Answer coverage and explanation coverage are both **100%** for every extracted question.

### Content breakdown (merged totals across 8 tests)

| Metric | Count |
|---|---|
| Total questions in output | **945** |
| Multiple-choice | 839 |
| Numeric response (student-produced) | 106 |
| Questions with visual assets (chart/table/diagram) | 148 |
| Multi-value numeric answers (e.g. `["1/5", ".2"]`) | 24 |
| Pages rendered to PNG | 444 |
| Total asset size | 72.6 MB |

### Numeric response question positions

Across all 8 tests, student-produced response questions occur at the same 7 positions in each Math module:

```
Q6, Q7, Q13, Q14, Q20, Q21, Q27
```

This is consistent with official College Board format.

---

## 6. Final JSON Schema

Every entry in `output/test{N}.json` conforms to:

```json
{
  "id":              "test4_rw_m1_q13",
  "test":            4,
  "section":         "reading",
  "module":          1,
  "question_number": 13,
  "topic":           null,
  "subtopic":        null,
  "difficulty":      null,
  "question_type":   "multiple_choice",
  "question":        "Organic farming is a method...\n\nWhich choice most effectively...",
  "choices":         { "A": "Washington had...", "B": "New York had...", "C": "...", "D": "..." },
  "correct_answer":  "A",
  "explanation":     "Choice A is the best answer because...",
  "page":            10,
  "assets": [
    { "type": "image", "src": "assets/test4/page_010.png" }
  ]
}
```

**`correct_answer` encoding:**

| Question type | Example | Python type |
|---|---|---|
| Multiple choice | `"A"` | `str` |
| Numeric (single) | `"9"`, `"-3"`, `"2520"` | `str` |
| Numeric (multi-value) | `["1/5", ".2"]`, `["15", "-5"]` | `list[str]` |

**Fields populated later:**  
`topic`, `subtopic`, `difficulty` are `null` — set by `topic_classifier.py` (Phase 7) and `difficulty_classifier.py` (Phase 8).

---

## 7. Critical PDF Findings (Phase 1 Analysis)

### Source PDF type

These PDFs are **paper accommodation versions** of the digital SAT — printed, then scanned, then OCR'd via *Acrobat Pro 22 Paper Capture Plug-in*. They are **not** clean digital-native PDFs.

Consequences:
- Math formulas are frequently garbled (`V = i,.r3` instead of V = ⁴⁄₃πr³)
- Charts and coordinate grids produce OCR noise text (`+---+--+--i------`)
- Symbol replacements: `%` → `percent sign`, `$` → `dollar sign` (normalized in pipeline)
- The word `blank` appears literally in passage text where the test shows a fill-in underline → normalized to `[BLANK]`

### Module page layout

| Section | Module | Questions | Pages (test 4) |
|---|---|---|---|
| Reading & Writing | 1 | 33 | 4–17 |
| Reading & Writing | 2 | 33 | 18–30 |
| Math | 1 | 27 | 32–39 |
| Math | 2 | 27 | 40–48 |

Module start pages vary slightly across tests (Math M2 can start anywhere from page 40–44). The pipeline detects module boundaries **dynamically** by scanning for `Module\n[12]\nReading and Writing` and `Module\n[12]\nMath` patterns.

### Two-column page layout

RW and Math pages use a **two-column layout** — 2 questions side by side. PyMuPDF's `get_text()` extracts blocks by x-coordinate position. The pipeline sorts blocks into left column (x < 295) then right column (x ≥ 295), each sorted by y, to reconstruct correct reading order.

### Answer key location

The answer key is always on **page 4 (index 3)** of the 5-page scoring PDF. Page 2 of the same PDF embeds a thumbnail replica (with different formatting) — use only page 4.

---

## 8. Known Limitations

### 1. Missing questions (~1.6%)

15 questions across 5 tests have their question number embedded inside an OCR'd visual separator element rather than in a standalone narrow block. The pipeline cannot detect these Q# boundaries without manual annotation.

Affected tests/modules: Tests 5, 6, 7, 8, 9 (1–5 questions each, primarily in RW and Math sections where separator decorations are heavier).

**Mitigation for Phase 9:** A targeted manual patch file can supply missing question numbers and text for these 15 questions.

### 2. Math formula OCR corruption

All equations involving fractions, radicals, Greek letters, superscripts, and subscripts appear as garbled text in both question text and explanation text. Examples:

- `f x\n( ) = −ax + b` (function notation)
- `5\n5 45 \n6\n·\n 3 x \n8\n8 \n 2 x` (expression)
- `⎛ 99 ⎞\n⎜0, − ⎟` (coordinates with fractions)

**Mitigation:** The rendered page PNG (`assets/test{N}/page_{NNN}.png`) is the authoritative visual source for questions with math formulas. The adaptive learning UI should display the image alongside (or instead of) the raw text for Math questions.

### 3. Table OCR column order

For RW questions with data tables (e.g., the Mycorrhizal Fungi table), the OCR extracts columns in a y-sorted order that may not match left-to-right visual reading order. The table data is present and correct but may require client-side re-parsing for display.

**Mitigation:** Use the page PNG as the primary table display mechanism.

### 4. Question type correction via answer key

6 questions (3 in test 7, 3 in test 8) were initially classified as `numeric_response` (no A/B/C/D choices found in OCR) but the answer key confirms they are `multiple_choice`. The merge step auto-corrects `question_type` to `multiple_choice` but the `choices` field remains `null` for these 6 questions.

---

## 9. Intermediate File Reference

All intermediate files in `data/raw/` can be deleted and regenerated by re-running the pipeline. They are kept for speed (avoid re-parsing PDFs) and for debugging.

| File | Created by | Content |
|---|---|---|
| `test{N}_questions.json` | extract_questions.py | List of question dicts with text, choices, assets |
| `test{N}_answers.json` | extract_answers.py | Dict keyed by module → Q# → answer string |
| `test{N}_explanations.json` | extract_explanations.py | Dict keyed by module → Q# → explanation string |
| `test{N}_image_manifest.json` | extract_images.py | List of visual Q entries with page + asset path |

Answer/explanation JSON key format: `reading_m1`, `reading_m2`, `math_m1`, `math_m2`.

---

## 10. Next Steps (Phases 7–9)

### Phase 7 — `topic_classifier.py`

Assign `topic` and `subtopic` to every question. Recommended approach:

**Rule-based pass first:**
- Detect grammar/punctuation questions from stems containing "Standard English", "conforms to the conventions"
- Detect transition questions from stems containing "most logical transition"
- Detect data interpretation from presence of visual assets + "graph", "table"
- Detect Math topic from question text (e.g., "linear equation", "quadratic", "probability")

**LLM classification second (for ambiguous cases):**
- Use the `explanation` text as a high-quality signal — it usually names the skill explicitly
  - "As used in the text" → `words_in_context`
  - "main idea" / "main purpose" → `central_ideas`
  - "function of" → `text_structure`
  - "the texts, how would" → `command_of_evidence`
  - "most logically completes" in Math → `linear_equations` or `functions`

Full taxonomy in `TOPIC_TAXONOMY` section of the project spec.

### Phase 8 — `difficulty_classifier.py`

Assign `easy` / `medium` / `hard`. Signal sources:
- **Q# position within module**: Earlier questions are easier (College Board orders by difficulty)
- **Explanation length**: Longer explanations correlate with harder questions
- **Answer choice complexity**: Very short distractor choices → easier
- **Math answer type**: Multi-value numeric answers tend to be harder
- **LLM fallback** for edge cases

### Phase 9 — Validation and generalization

- Cross-validate extracted correct answers against the explanations text (the explanation always starts with "Choice X is the best answer" — this is a ground-truth check)
- Address the 15 missing questions manually if needed
- Produce a full metrics report

---

## 11. utils.py Reference

All scripts import from `scripts/utils.py`. Key exports:

```python
open_pdf(path: Path) -> fitz.Document
clean_text(text: str) -> str              # OCR normalization
is_noise_block(text: str) -> bool         # separator/footer/boilerplate detector
get_blocks_in_reading_order(page, ...) -> List[Dict]  # 2-column-aware block sort
find_module_pages(doc) -> Dict[Tuple[str,int], int]   # dynamic module boundary detection
```

Key constants:
```python
COL_SPLIT_X = 295   # x-coordinate splitting left and right columns
HEADER_Y_MAX = 55   # blocks starting above this y are page headers (excluded)
FOOTER_Y_MIN = 730  # blocks starting below this y are footers (excluded)
Q_NUM_MAX_WIDTH = 60  # question-number blocks are always narrower than this
```

---

## 12. Supabase Schema Recommendation

For direct ingestion of the output JSON, the recommended Supabase table schema is:

```sql
CREATE TABLE questions (
  id                TEXT PRIMARY KEY,       -- "test4_rw_m1_q13"
  test              INTEGER NOT NULL,
  section           TEXT NOT NULL,          -- "reading" | "math"
  module            INTEGER NOT NULL,       -- 1 | 2
  question_number   INTEGER NOT NULL,
  topic             TEXT,
  subtopic          TEXT,
  difficulty        TEXT,                   -- "easy" | "medium" | "hard"
  question_type     TEXT NOT NULL,          -- "multiple_choice" | "numeric_response"
  question          TEXT NOT NULL,
  choices           JSONB,                  -- {"A":"...","B":"...","C":"...","D":"..."} or null
  correct_answer    JSONB NOT NULL,         -- "A" | "9" | ["1/5", ".2"]
  explanation       TEXT,
  page              INTEGER,
  assets            JSONB DEFAULT '[]'::jsonb  -- [{"type":"image","src":"..."}]
);

CREATE INDEX ON questions (test, section, module);
CREATE INDEX ON questions (topic, subtopic);
CREATE INDEX ON questions (difficulty);
CREATE INDEX ON questions (question_type);
```

Import command:
```bash
# From Node.js / supabase-js
const data = JSON.parse(fs.readFileSync('output/test4.json'))
const { error } = await supabase.from('questions').upsert(data)
```
