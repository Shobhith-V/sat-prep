"""
extract_answers.py — Extract correct answers from SAT scoring PDFs.

Usage:
    python extract_answers.py --test 4
    python extract_answers.py --all

Input:  Answers/scoring-sat-practice-test-{N}-digital.pdf
Output: data/raw/test{N}_answers.json

PDF structure (all tests, 5-page scoring PDF):
    Page 4 (index 3): "SAT Practice Test Worksheet: Answer Key"
        Contains exactly 4 "QUESTION #" blocks in this column order:
            Block 1 → Reading & Writing Module 1  (33 questions)
            Block 2 → Reading & Writing Module 2  (33 questions)
            Block 3 → Math Module 1               (27 questions)
            Block 4 → Math Module 2               (27 questions)

Text format within each block:
    QUESTION #
    CORRECT
    MARK YOUR
    CORRECT
    ANSWERS
    1          ← question number (standalone line)
    B          ← answer (next line)
    2
    A
    ...
    6
    9          ← numeric answer
    ...
    21 361/8; 45.12; 45.13   ← Q# + multi-value answer on same line

Multi-value answers (multiple acceptable forms) are separated by "; ".

Output schema:
{
  "test": 4,
  "reading_m1": {"1": "B", "2": "A", ..., "33": "C"},
  "reading_m2": {"1": "D", ...},
  "math_m1":   {"1": "B", "6": "9", "13": "1/5; .2", ...},
  "math_m2":   {"1": "B", "6": "15; -5", ...}
}
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import fitz

REPO_ROOT = Path(__file__).resolve().parent.parent
ANSWERS_DIR = REPO_ROOT / "Answers"
OUTPUT_DIR = REPO_ROOT / "data" / "raw"

sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

SCORING_FILE_NAMES: Dict[int, str] = {
    4:  "scoring-sat-practice-test-4-digital.pdf",
    5:  "scoring-sat-practice-test-5-digital.pdf",
    6:  "scoring-sat-practice-test-6-digital.pdf",
    7:  "scoring-sat-practice-test-7-digital.pdf",
    8:  "scoring-sat-practice-test-8-digital.pdf",
    9:  "scoring-sat-practice-test-9-digital.pdf",
    10: "scoring-sat-practice-test-10-digital.pdf",
    11: "scoring-sat-practice-test-11-digital.pdf",
}

# Lines to discard when cleaning up each answer block
_NOISE_LINES: List[re.Pattern] = [
    re.compile(r"^CORRECT$", re.I),
    re.compile(r"^MARK YOUR$", re.I),
    re.compile(r"^CORRECT ANSWERS$", re.I),
    re.compile(r"^ANSWERS$", re.I),
    re.compile(r"^Module\s+[12]$", re.I),
    re.compile(r"^Reading and Writing", re.I),
    re.compile(r"^READING AND WRITING", re.I),
    re.compile(r"^Math\s*(Module)?", re.I),
    re.compile(r"^MATH SECTION", re.I),
    re.compile(r"^Total.*Correct", re.I),
    re.compile(r"^\(.*Total.*\)$", re.I),
    re.compile(r"^RAW SCORE$", re.I),
    re.compile(r"^\+\s*=?$"),            # test 9/11 arithmetic symbols
    re.compile(r"^=$"),
    re.compile(r"^WX4P0001$"),           # barcode
    re.compile(r"^\d+VSL\d+$"),          # serial codes like "6VSL01"
]

# Matches a single digit/letter answer line (A, B, C, D or a number)
_ANSWER_RE = re.compile(r"^[A-D]$|^-?\d[\d./;,\s-]*$|^\.\d")


def _is_noise_line(line: str) -> bool:
    return any(p.match(line) for p in _NOISE_LINES)


def parse_answer_block(block_text: str, max_q: int) -> Dict[str, str]:
    """
    Parse a single answer block into {q_num_str: answer_str}.

    Handles both formats:
      - Q# on one line, answer on next line  (normal)
      - "Q# answer" on the same line          (multi-value edge cases)

    multi-value answers (e.g. "1/5; .2") are stored as-is; callers split on "; ".
    """
    raw_lines = [ln.strip() for ln in block_text.splitlines()]
    lines = [ln for ln in raw_lines if ln and not _is_noise_line(ln)]

    answers: Dict[str, str] = {}
    state = "q_num"   # alternates between "q_num" and "answer"
    current_q: Optional[int] = None

    for line in lines:
        if state == "q_num":
            # Try "Q# answer" on the same line first
            m = re.match(r"^(\d+)\s+(.+)$", line)
            if m:
                q = int(m.group(1))
                if 1 <= q <= max_q:
                    answers[str(q)] = m.group(2).strip()
                    # state stays "q_num" (no paired answer expected)
                    continue

            # Try standalone Q#
            if re.match(r"^\d+$", line):
                q = int(line)
                if 1 <= q <= max_q:
                    current_q = q
                    state = "answer"
                    continue

            # Not a recognised Q# → skip (noise / separator)

        else:  # state == "answer"
            if current_q is not None:
                answers[str(current_q)] = line
            current_q = None
            state = "q_num"

    return answers


def find_answer_key_page(doc: fitz.Document) -> int:
    """
    Return the 0-based index of the answer key page.

    The dedicated answer key page (always page 4, index 3) is short (~1100–1300
    chars) and contains exactly 4 occurrences of "QUESTION #". We confirm by
    index rather than scanning, but fall back to scanning if needed.
    """
    # Primary: index 3 (page 4) is the answer key for all 8 tests
    candidate = 3
    if candidate < len(doc):
        text = doc[candidate].get_text()
        if text.count("QUESTION #") == 4:
            return candidate

    # Fallback: scan all pages
    for i, page in enumerate(doc):
        text = page.get_text()
        if text.count("QUESTION #") == 4 and "Answer Key" in text:
            logger.warning("Answer key found on page %d (not the expected page 4)", i + 1)
            return i

    raise ValueError("Could not locate answer key page in scoring PDF")


def extract_answers(test_num: int) -> Dict:
    """Extract all answers for one test and return a structured dict."""
    pdf_path = ANSWERS_DIR / SCORING_FILE_NAMES[test_num]
    if not pdf_path.exists():
        raise FileNotFoundError(f"Scoring PDF not found: {pdf_path}")

    doc = fitz.open(str(pdf_path))
    page_idx = find_answer_key_page(doc)
    page_text = doc[page_idx].get_text()

    logger.info("Test %d: parsing answer key from page %d of %s",
                test_num, page_idx + 1, pdf_path.name)

    # Split on "QUESTION #" — we expect exactly 5 parts (preamble + 4 blocks)
    parts = page_text.split("QUESTION #")
    if len(parts) != 5:
        logger.warning(
            "Expected 5 parts after splitting on 'QUESTION #', got %d", len(parts)
        )

    # parts[0] = preamble; parts[1..4] = answer blocks in order:
    #   [1] RW M1, [2] RW M2, [3] Math M1, [4] Math M2
    rw_m1 = parse_answer_block(parts[1] if len(parts) > 1 else "", max_q=33)
    rw_m2 = parse_answer_block(parts[2] if len(parts) > 2 else "", max_q=33)
    math_m1 = parse_answer_block(parts[3] if len(parts) > 3 else "", max_q=27)
    math_m2 = parse_answer_block(parts[4] if len(parts) > 4 else "", max_q=27)

    result = {
        "test": test_num,
        "reading_m1": rw_m1,
        "reading_m2": rw_m2,
        "math_m1": math_m1,
        "math_m2": math_m2,
    }
    return result


def validate_answers(data: Dict, test_num: int) -> None:
    """Print a validation report for the extracted answers."""
    expected = {
        "reading_m1": 33, "reading_m2": 33,
        "math_m1": 27,    "math_m2": 27,
    }
    print(f"\n─── Answer Validation: Test {test_num} ─────────────────────────")
    total_ok = total_exp = 0
    for key, exp in expected.items():
        found = len(data.get(key, {}))
        ok = found == exp
        status = "✓" if ok else "✗"
        mc = sum(1 for v in data.get(key, {}).values() if v in "ABCD")
        nr = found - mc
        print(f"  {status}  {key:12s}: {found:2d}/{exp}  (MC={mc} NR={nr})")
        total_ok += found
        total_exp += exp

    overall = total_ok / total_exp * 100 if total_exp else 0
    print(f"  {'✓' if total_ok==total_exp else '✗'}  TOTAL       : {total_ok}/{total_exp}  ({overall:.0f}%)")

    # Show numeric response answers
    print("\n  Numeric answers:")
    for key in ["math_m1", "math_m2"]:
        for q, ans in sorted(data.get(key, {}).items(), key=lambda x: int(x[0])):
            if ans not in "ABCD":
                multi = "  [MULTI]" if ";" in ans else ""
                print(f"    {key} Q{q:2s} = {ans!r}{multi}")

    print("────────────────────────────────────────────────────────────\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract SAT answers from scoring PDFs.")
    parser.add_argument("--test", type=int, choices=list(SCORING_FILE_NAMES))
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--out-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    if not args.test and not args.all:
        parser.error("Specify --test N or --all")

    test_ids = list(SCORING_FILE_NAMES) if args.all else [args.test]
    args.out_dir.mkdir(parents=True, exist_ok=True)

    for test_num in test_ids:
        try:
            data = extract_answers(test_num)
        except FileNotFoundError as exc:
            logger.error("%s — skipping", exc)
            continue

        out_path = args.out_dir / f"test{test_num}_answers.json"
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)

        logger.info("Wrote → %s", out_path)
        validate_answers(data, test_num)


if __name__ == "__main__":
    main()
