# SAT Prep — Extraction & Classification Pipeline

Converts official **College Board SAT Practice Test PDFs** (tests 4–11) into
structured, classified JSON suitable for an adaptive-learning platform
(React + Vite frontend, Supabase backend, GitHub Pages hosting).

> This repository is the **data pipeline**, not the website. It turns raw PDFs
> into `output/test{N}.json` — a clean question bank with answers, explanations,
> page-image references, topic/subtopic labels, and estimated difficulty.

---

## Results at a glance

| Metric | Value |
|---|---|
| Tests processed | 8 (tests 4–11) |
| Questions extracted | **945 / 960 (98.4%)** |
| Correct answers | 945 / 945 (100%) |
| Explanations | 945 / 945 (100%) |
| Topic + subtopic classified | 945 / 945 (100%) |
| Difficulty assigned | 945 / 945 (100%) |
| Answer ⇄ explanation cross-validation | **837 / 837 (100% agreement)** |
| Page images rendered | 444 PNGs (72.6 MB) |
| Unit tests | 47 passing |

---

## Input layout

```
Questions/      sat-practice-test-{4-11}-digital.pdf            (question booklets)
Answers/        scoring-sat-practice-test-{4-11}-digital.pdf    (answer keys)
Explanations/   sat-practice-test-{4-11}-answers-digital.pdf    (explanation booklets)
```

The PDFs are paper-accommodation versions of the digital SAT — they were
**printed, scanned, and OCR'd**, so the pipeline is built to tolerate OCR noise
(garbled math formulas, symbol substitutions, decorative separators).

---

## Output layout

```
output/
├── test4.json … test11.json     # final question banks (see schema below)
└── assets/
    ├── test4/page_001.png … page_056.png
    └── …                         # one PNG per PDF page @ 150 DPI

data/raw/                         # intermediate per-phase JSON (regenerable)
├── test{N}_questions.json
├── test{N}_answers.json
├── test{N}_explanations.json
└── test{N}_image_manifest.json
```

### Final question schema

```json
{
  "id": "test4_rw_m1_q13",
  "test": 4,
  "section": "reading",
  "module": 1,
  "question_number": 13,
  "topic": "data_interpretation",
  "subtopic": "graph_analysis",
  "difficulty": "medium",
  "question_type": "multiple_choice",
  "question": "Organic farming is a method…\n\nWhich choice most effectively…",
  "choices": { "A": "…", "B": "…", "C": "…", "D": "…" },
  "correct_answer": "A",
  "explanation": "Choice A is the best answer because…",
  "page": 10,
  "assets": [ { "type": "image", "src": "assets/test4/page_010.png" } ]
}
```

`correct_answer` is a **string** for multiple-choice (`"A"`) and single numeric
answers (`"9"`), or a **list** for numeric questions that accept several forms
(`["1/5", ".2"]`). `numeric_response` questions have `choices: null`.

---

## Setup

```bash
conda activate mlops            # environment already has PyMuPDF + pandas
# or:
pip install -r requirements.txt
```

---

## Running the pipeline

### One command (recommended)

```bash
python scripts/run_pipeline.py            # all 8 tests, all phases
python scripts/run_pipeline.py --test 4   # single test
python scripts/run_pipeline.py --skip-images   # faster re-run (no page renders)
```

### Phase by phase

```bash
python scripts/extract_questions.py     --all     # → data/raw/*_questions.json
python scripts/extract_answers.py       --all     # → data/raw/*_answers.json
python scripts/extract_explanations.py  --all     # → data/raw/*_explanations.json
python scripts/extract_images.py        --all     # → output/assets/ + manifests
python scripts/merge.py                 --all     # → output/test{N}.json
python scripts/topic_classifier.py      --all     # adds topic / subtopic
python scripts/difficulty_classifier.py --all     # adds difficulty
python scripts/validate.py                        # final metrics report
```

Each phase is **idempotent** and **independently re-runnable**. Classification
can be re-run without re-extracting PDFs. Full run takes **~50 seconds** for all
8 tests.

---

## Pipeline architecture

```
                ┌──────────────────┐
 Questions PDF →│ extract_questions│→ questions.json ─┐
                └──────────────────┘                  │
                ┌──────────────────┐                  │
 Scoring  PDF →│ extract_answers   │→ answers.json ───┤
                └──────────────────┘                  ├→ merge → output/test{N}.json
                ┌──────────────────┐                  │      │
 Expl.    PDF →│extract_explanat. │→ explanations.json┤      │
                └──────────────────┘                  │      ▼
                ┌──────────────────┐                  │  topic_classifier
 Questions PDF →│ extract_images   │→ assets/ + manifest      │
                └──────────────────┘                          ▼
                                                      difficulty_classifier → validate
```

### Key techniques

- **Dynamic module detection** — module start pages vary per test; the parser
  scans for `Module N / Reading and Writing | Math` headers rather than
  hardcoding page numbers (`utils.find_module_pages`).
- **Two-column reading order** — RW/Math pages are two-column; blocks are sorted
  left-column-then-right by x/y coordinates (`utils.get_blocks_in_reading_order`).
- **OCR normalization** — `percent sign`→`%`, `dollar sign`→`$`, `blank`→`[BLANK]`,
  decorative separators and footers stripped (`utils.clean_text`).
- **Dual-source answers** — the clean scoring-PDF answer key is authoritative;
  it is cross-checked against the explanation booklet (100% agreement).
- **Rule-first classification** — deterministic stem/keyword rules classify 100%
  of questions; an optional `--use-llm` Claude fallback exists for edge cases.

---

## Classification

### Topic taxonomy

**Reading & Writing:** words_in_context · central_ideas · command_of_evidence ·
inferences · text_structure · rhetorical_synthesis · transitions · grammar ·
boundaries · form_structure_sense · data_interpretation

**Math:** linear_equations · systems · quadratics · functions · exponents ·
geometry · circles · trigonometry · statistics · probability · data_interpretation

Topic is derived from the question stem and explanation text; validated to
**100%** on grammar / transition / words-in-context ground-truth signals.

### Difficulty

`easy` / `medium` / `hard`, estimated from a composite score (question position,
explanation length, question-type/topic weight, answer complexity) assigned by
per-section terciles. College Board does not publish per-question difficulty in
these PDFs, so this is a **calibrated estimate** for adaptive sequencing, not an
official IRT parameter. Math difficulty correlates strongly with question
position (easy avg pos 5.6 → hard 22.4), confirming the signal.

---

## Validation & testing

```bash
python scripts/validate.py        # end-to-end metrics + cross-validation
pytest tests/ -v                  # 47 unit + integration tests
```

`validate.py` checks schema completeness, coverage, answer/explanation
cross-validation, type consistency, classification coverage, asset integrity,
and ID uniqueness. It exits non-zero on any hard failure (CI-friendly).

---

## Known limitations

- **~1.6% of questions are not extracted** (15 of 960). Their question number is
  embedded inside an OCR'd decorative separator rather than a standalone block,
  so the boundary is undetectable without manual annotation.
- **Math formula text is OCR-garbled** (fractions, radicals, exponents). The
  rendered **page PNG is the authoritative visual source** for math and figure
  questions — the React app should display it alongside the text.
- **Table column order** from OCR may not match visual layout; use the page PNG.
- **Difficulty is estimated**, not an official label (see above).

See `HANDOFF.md` for full phase-by-phase notes and the Supabase schema
recommendation.

---

## Repository structure

```
scripts/
├── utils.py                  # shared: OCR clean, block sort, module detect
├── extract_questions.py      # questions + choices
├── extract_answers.py        # correct answers (scoring PDF)
├── extract_explanations.py   # explanation text
├── extract_images.py         # page renders + image manifest
├── merge.py                  # combine sources → final JSON
├── topic_classifier.py       # topic + subtopic
├── difficulty_classifier.py  # difficulty
├── validate.py               # end-to-end validation + metrics
└── run_pipeline.py           # orchestrate all phases
tests/
├── test_question_parser.py
├── test_explanation_parser.py
└── test_classifier.py
output/                       # final JSON + page assets
data/raw/                     # intermediate JSON
requirements.txt
README.md
HANDOFF.md
```
