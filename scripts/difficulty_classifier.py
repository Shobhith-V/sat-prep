"""
difficulty_classifier.py — Assign easy / medium / hard to every SAT question.

Usage:
    python difficulty_classifier.py --test 4
    python difficulty_classifier.py --all
    python difficulty_classifier.py --all --report     # report only, no file write

Input / output: output/test{N}.json  (reads and rewrites in place)

Why estimation, not ground truth
--------------------------------
The College Board PDFs do not publish a per-question difficulty label, so
difficulty here is *estimated* from observable proxies. The estimate is designed
to be stable, explainable, and useful for adaptive sequencing — not to reproduce
an official IRT b-parameter.

Signals (validated against the corpus in Phase 8 analysis)
----------------------------------------------------------
Math (questions are ordered by difficulty within each module domain):
  - position within module          STRONG  (Q1 avg-explanation 589 → Q26 1600 chars)
  - explanation length              MODERATE
  - answer complexity               WEAK    (multi-value / long numeric → harder)

Reading & Writing (digital format orders by DOMAIN, not difficulty,
so position is unreliable; reasoning complexity is captured by length):
  - explanation length              STRONG  (more distractor analysis → harder)
  - passage + question length       MODERATE
  - question-type base difficulty   MODERATE (words_in_context easy;
                                              inferences / command_of_evidence hard)

Method
------
1. Compute a composite raw score per question from the weighted signals.
2. Rank questions WITHIN each section (reading / math) and assign difficulty by
   percentile terciles: bottom third = easy, middle = medium, top third = hard.
   This yields a balanced, defensible distribution without an absolute-threshold
   guess that would drift between tests.

The classifier is idempotent and can be re-run without re-extracting PDFs.
It depends only on fields already present in output/test{N}.json
(topic from Phase 7 is used as a minor signal but is not required).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "output"

sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

# Questions per module, used to normalise position to [0, 1]
_MODULE_SIZE = {"reading": 33, "math": 27}

# Per-question-type base difficulty contribution for Reading & Writing.
# Range roughly [0, 1]; higher = harder reasoning load.
_RW_TYPE_WEIGHT: Dict[str, float] = {
    "words_in_context": 0.15,
    "transitions": 0.30,
    "grammar": 0.30,
    "boundaries": 0.30,
    "form_structure_sense": 0.35,
    "rhetorical_synthesis": 0.45,
    "central_ideas": 0.50,
    "data_interpretation": 0.55,
    "text_structure": 0.65,
    "command_of_evidence": 0.75,
    "inferences": 0.80,
}

# Per-topic base difficulty contribution for Math.
_MATH_TOPIC_WEIGHT: Dict[str, float] = {
    "linear_equations": 0.25,
    "exponents": 0.35,
    "data_interpretation": 0.35,
    "statistics": 0.40,
    "probability": 0.45,
    "functions": 0.50,
    "systems": 0.50,
    "geometry": 0.55,
    "circles": 0.60,
    "quadratics": 0.65,
    "trigonometry": 0.75,
}


# ── Signal extraction ────────────────────────────────────────────────────────

def _norm(value: float, lo: float, hi: float) -> float:
    """Clamp value into [lo, hi] then scale to [0, 1]."""
    if hi <= lo:
        return 0.0
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


def _raw_score(q: Dict) -> float:
    """
    Compute a composite difficulty score in roughly [0, 1] for one question.
    Higher = harder.
    """
    section = q["section"]
    expl_len = len(q.get("explanation") or "")
    q_len = len(q.get("question") or "")
    pos = q.get("question_number", 1)
    topic = q.get("topic")

    if section == "math":
        # Position is the strongest signal (calibrated lo/hi from corpus terciles)
        pos_score = _norm(pos, 1, _MODULE_SIZE["math"])
        expl_score = _norm(expl_len, 384, 1449)        # p10–p90 from analysis
        type_score = _MATH_TOPIC_WEIGHT.get(topic, 0.45)

        # Answer complexity: multi-value or long numeric answers tend to be harder
        ans = q.get("correct_answer")
        ans_bonus = 0.0
        if isinstance(ans, list):
            ans_bonus = 0.10
        elif isinstance(ans, str) and q.get("question_type") == "numeric_response" and len(ans) >= 4:
            ans_bonus = 0.05

        score = (0.45 * pos_score
                 + 0.30 * expl_score
                 + 0.20 * type_score
                 + ans_bonus)
    else:  # reading
        expl_score = _norm(expl_len, 681, 2226)        # p10–p90 from analysis
        len_score = _norm(q_len, 338, 816)             # p10–p90 from analysis
        type_score = _RW_TYPE_WEIGHT.get(topic, 0.45)

        score = (0.50 * expl_score
                 + 0.20 * len_score
                 + 0.30 * type_score)

    return score


# ── Difficulty assignment via per-section terciles ───────────────────────────

def _assign_terciles(scored: List[Tuple[Dict, float]]) -> None:
    """
    Given (question, raw_score) pairs for ONE section, sort by score and assign
    difficulty by tercile: bottom third easy, middle medium, top third hard.
    Mutates each question dict in place.
    """
    scored.sort(key=lambda x: x[1])
    n = len(scored)
    if n == 0:
        return
    t1 = n // 3
    t2 = 2 * n // 3
    for i, (q, _score) in enumerate(scored):
        if i < t1:
            q["difficulty"] = "easy"
        elif i < t2:
            q["difficulty"] = "medium"
        else:
            q["difficulty"] = "hard"


def classify_test(test_num: int) -> List[Dict]:
    """Load, score, and assign difficulty for all questions in one test."""
    path = OUTPUT_DIR / f"test{test_num}.json"
    if not path.exists():
        raise FileNotFoundError(f"Merged JSON not found: {path}\nRun merge.py first.")

    data: List[Dict] = json.loads(path.read_text(encoding="utf-8"))

    # Score and assign per section so terciles are computed within section
    for section in ("reading", "math"):
        scored = [(q, _raw_score(q)) for q in data if q["section"] == section]
        _assign_terciles(scored)

    counts = {"easy": 0, "medium": 0, "hard": 0}
    for q in data:
        counts[q["difficulty"]] = counts.get(q["difficulty"], 0) + 1

    logger.info(
        "Test %d: easy=%d  medium=%d  hard=%d",
        test_num, counts["easy"], counts["medium"], counts["hard"],
    )
    return data


# ── Reporting ─────────────────────────────────────────────────────────────────

def difficulty_report(all_data: List[Dict], test_nums: List[int]) -> None:
    from collections import Counter

    overall = Counter()
    by_section = {"reading": Counter(), "math": Counter()}
    by_topic_diff: Dict[str, Counter] = {}

    for q in all_data:
        d = q.get("difficulty")
        overall[d] += 1
        by_section[q["section"]][d] += 1
        topic = q.get("topic") or "unknown"
        by_topic_diff.setdefault(topic, Counter())[d] += 1

    total = len(all_data)
    print(f"\n{'═'*64}")
    print(f" Difficulty Distribution Report — Tests {test_nums}")
    print(f"{'═'*64}")
    print(f" Total questions : {total}")

    print(f"\n {'Level':<10} {'Count':>6} {'Pct':>7}")
    print(f" {'─'*26}")
    for level in ("easy", "medium", "hard"):
        c = overall[level]
        print(f" {level:<10} {c:>6} {c/total*100:>6.1f}%")

    print(f"\n {'Section':<10} {'easy':>6} {'medium':>7} {'hard':>6}")
    print(f" {'─'*34}")
    for section in ("reading", "math"):
        c = by_section[section]
        print(f" {section:<10} {c['easy']:>6} {c['medium']:>7} {c['hard']:>6}")

    print(f"\n {'Topic':<24} {'easy':>5} {'med':>5} {'hard':>5}")
    print(f" {'─'*44}")
    for topic in sorted(by_topic_diff, key=lambda t: -sum(by_topic_diff[t].values())):
        c = by_topic_diff[topic]
        print(f" {topic:<24} {c['easy']:>5} {c['medium']:>5} {c['hard']:>5}")

    print(f"{'═'*64}\n")


# ── CLI ─────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Estimate question difficulty (easy/medium/hard)."
    )
    parser.add_argument("--test", type=int, choices=range(4, 12))
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--report", action="store_true",
                        help="Print report without writing files")
    args = parser.parse_args()

    if not args.test and not args.all:
        parser.error("Specify --test N or --all")

    test_ids = list(range(4, 12)) if args.all else [args.test]
    all_data: List[Dict] = []

    for test_num in test_ids:
        logger.info("═══ Difficulty: test %d ════════════════════════", test_num)
        try:
            data = classify_test(test_num)
        except FileNotFoundError as exc:
            logger.error("%s — skipping", exc)
            continue

        all_data.extend(data)

        if not args.report:
            out_path = OUTPUT_DIR / f"test{test_num}.json"
            out_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info("Updated → %s", out_path)

    difficulty_report(all_data, test_ids)


if __name__ == "__main__":
    main()
