"""
merge.py — Combine questions, answers, explanations, and image assets into final JSON.

Usage:
    python merge.py --test 4
    python merge.py --all

Inputs (all from data/raw/):
    test{N}_questions.json       — questions + choices + asset refs (from extract_questions.py)
    test{N}_answers.json         — correct answers (from extract_answers.py)
    test{N}_explanations.json    — explanation text  (from extract_explanations.py)

Output:
    output/test{N}.json          — final merged question database

Final schema per question:
{
  "id":              "test4_rw_m1_q13",
  "test":            4,
  "section":         "reading",
  "module":          1,
  "question_number": 13,
  "topic":           null,       ← filled by topic_classifier.py (Phase 7)
  "subtopic":        null,       ← filled by topic_classifier.py (Phase 7)
  "difficulty":      null,       ← filled by difficulty_classifier.py (Phase 8)
  "question_type":   "multiple_choice",
  "question":        "...",
  "choices":         {"A": "...", "B": "...", "C": "...", "D": "..."},
  "correct_answer":  "A",                 ← string for MC / single numeric
                  or ["1/5", ".2"],       ← list for multi-value numeric
  "explanation":     "Choice A is the best answer because ...",
  "page":            10,
  "assets":          [{"type": "image", "src": "assets/test4/page_010.png"}]
}

Correct-answer normalisation rules:
  - MC answers (A/B/C/D) → stored as string
  - Single numeric answer → stored as string (e.g. "9", "-3", "2520")
  - Multi-value numeric (accepts several forms) → stored as list
    e.g. "1/5; .2"   becomes  ["1/5", ".2"]
         "15; -5"    becomes  ["15", "-5"]
         "361/8; 45.12; 45.13"  becomes  ["361/8", "45.12", "45.13"]

Type-consistency check:
  If the answer key shows a letter but the question was extracted as
  numeric_response (OCR failure — choices were not found), the type is
  corrected to multiple_choice and a warning is logged.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw"
OUTPUT_DIR = REPO_ROOT / "output"

sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

_MC_LETTERS = frozenset("ABCD")


# ── Answer normalisation ───────────────────────────────────────────────────────

def normalise_answer(raw: str) -> Union[str, List[str]]:
    """
    Convert a raw answer string from the scoring PDF into the final schema value.

    Single-value answers → string.
    Multi-value answers (semicolon-separated) → list of stripped strings.
    """
    if ";" not in raw:
        return raw.strip()
    parts = [p.strip() for p in raw.split(";") if p.strip()]
    return parts if len(parts) > 1 else parts[0]


# ── Module key helpers ─────────────────────────────────────────────────────────

def module_key(section: str, module_num: int) -> str:
    """Convert (section, module_num) to the key used in answers / explanations JSON."""
    prefix = "reading" if section == "reading" else "math"
    return f"{prefix}_m{module_num}"


# ── Merge logic ────────────────────────────────────────────────────────────────

def merge_test(test_num: int) -> List[Dict]:
    """
    Load all source files for one test and return a list of merged question dicts.
    """
    questions_path = RAW_DIR / f"test{test_num}_questions.json"
    answers_path   = RAW_DIR / f"test{test_num}_answers.json"
    expl_path      = RAW_DIR / f"test{test_num}_explanations.json"

    for p in (questions_path, answers_path, expl_path):
        if not p.exists():
            raise FileNotFoundError(f"Required file missing: {p}")

    questions: List[Dict] = json.loads(questions_path.read_text(encoding="utf-8"))
    answers:   Dict       = json.loads(answers_path.read_text(encoding="utf-8"))
    expl:      Dict       = json.loads(expl_path.read_text(encoding="utf-8"))

    merged: List[Dict] = []
    stats = {"no_answer": 0, "no_expl": 0, "type_corrected": 0}

    for q in questions:
        mk = module_key(q["section"], q["module"])
        q_str = str(q["question_number"])

        # ── Correct answer ─────────────────────────────────────────────────────
        raw_answer: Optional[str] = answers.get(mk, {}).get(q_str)
        if raw_answer is None:
            logger.warning("%s: no answer found in key %s[%s]", q["id"], mk, q_str)
            stats["no_answer"] += 1
            correct_answer: Any = None
        else:
            correct_answer = normalise_answer(raw_answer)

        # ── Type consistency check ─────────────────────────────────────────────
        question_type = q["question_type"]
        if (
            correct_answer is not None
            and isinstance(correct_answer, str)
            and correct_answer in _MC_LETTERS
            and question_type == "numeric_response"
        ):
            logger.warning(
                "%s: type was 'numeric_response' but answer is '%s' — correcting to 'multiple_choice'",
                q["id"], correct_answer,
            )
            question_type = "multiple_choice"
            stats["type_corrected"] += 1

        # ── Explanation ────────────────────────────────────────────────────────
        explanation: Optional[str] = expl.get(mk, {}).get(q_str)
        if explanation is None:
            logger.warning("%s: no explanation found in key %s[%s]", q["id"], mk, q_str)
            stats["no_expl"] += 1

        # ── Build final entry ──────────────────────────────────────────────────
        entry: Dict = {
            "id":              q["id"],
            "test":            q["test"],
            "section":         q["section"],
            "module":          q["module"],
            "question_number": q["question_number"],
            "topic":           q.get("topic"),
            "subtopic":        q.get("subtopic"),
            "difficulty":      q.get("difficulty"),
            "question_type":   question_type,
            "question":        q.get("question", ""),
            "choices":         q.get("choices"),
            "correct_answer":  correct_answer,
            "explanation":     explanation,
            "page":            q.get("page"),
            "assets":          q.get("assets", []),
        }
        merged.append(entry)

    logger.info(
        "Test %d: merged %d questions  (no_answer=%d no_expl=%d type_fixed=%d)",
        test_num, len(merged),
        stats["no_answer"], stats["no_expl"], stats["type_corrected"],
    )
    return merged


# ── Validation report ──────────────────────────────────────────────────────────

def validate(data: List[Dict], test_num: int) -> None:
    total = len(data)
    has_answer = sum(1 for q in data if q["correct_answer"] is not None)
    has_expl   = sum(1 for q in data if q["explanation"])
    has_assets = sum(1 for q in data if q["assets"])
    mc_ok      = sum(1 for q in data
                     if q["question_type"] == "multiple_choice" and q["choices"])
    nr         = sum(1 for q in data if q["question_type"] == "numeric_response")
    mc         = sum(1 for q in data if q["question_type"] == "multiple_choice")
    multi_ans  = sum(1 for q in data if isinstance(q["correct_answer"], list))

    expected = 120
    q_status  = "✓" if total == expected else f"✗ ({expected - total} missing)"
    ans_pct   = has_answer / total * 100 if total else 0
    expl_pct  = has_expl   / total * 100 if total else 0

    print(f"\n─── Merge Validation: Test {test_num} ────────────────────────────────")
    print(f"  Questions  : {total:3d}/{expected}  {q_status}")
    print(f"  w/ answer  : {has_answer:3d}/{total}  ({ans_pct:.0f}%)")
    print(f"  w/ expl.   : {has_expl:3d}/{total}  ({expl_pct:.0f}%)")
    print(f"  w/ assets  : {has_assets:3d}")
    print(f"  Type: MC={mc} (w/choices={mc_ok})  NR={nr}")
    print(f"  Multi-value answers: {multi_ans}")

    # Sample entries
    print("\n  Sample entries:")
    samples = [data[0], next((q for q in data if q["question_type"]=="numeric_response"), None)]
    for q in samples:
        if not q:
            continue
        ans_repr = repr(q["correct_answer"])
        expl_p = (q.get("explanation") or "")[:60].replace("\n", " ")
        print(f"    {q['id']}  ans={ans_repr}  expl='{expl_p}...'")

    print("──────────────────────────────────────────────────────────────\n")


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge SAT question, answer, and explanation data into final JSON."
    )
    parser.add_argument("--test", type=int, choices=range(4, 12))
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--out-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    if not args.test and not args.all:
        parser.error("Specify --test N or --all")

    test_ids = list(range(4, 12)) if args.all else [args.test]
    args.out_dir.mkdir(parents=True, exist_ok=True)

    for test_num in test_ids:
        logger.info("═══ Merging test %d ═══════════════════════════════════", test_num)
        try:
            merged = merge_test(test_num)
        except FileNotFoundError as exc:
            logger.error("%s — skipping", exc)
            continue

        out_path = args.out_dir / f"test{test_num}.json"
        out_path.write_text(
            json.dumps(merged, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Wrote %d questions → %s", len(merged), out_path)
        validate(merged, test_num)


if __name__ == "__main__":
    main()
