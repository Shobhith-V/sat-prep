"""
extract_explanations.py — Extract answer explanations from SAT explanation PDFs.

Usage:
    python extract_explanations.py --test 4
    python extract_explanations.py --all

Input:  Explanations/sat-practice-test-{N}-answers-digital.pdf
Output: data/raw/test{N}_explanations.json

PDF structure (47–53 pages depending on test):
    Page 1        : Cover (skipped)
    Pages 2–end   : Explanation pages

Each page carries a running module header in the form:
    "SAT ANSWER EXPLANATIONS n READING AND WRITING: MODULE N"
    or
    "SAT ANSWER EXPLANATIONS n MATH: MODULE N"

Content within each page follows the pattern:
    QUESTION N
    Choice B is the best answer because ...
    Choice A is incorrect because ...
    ...
    n           ← section divider (page-end marker, stripped)

Multiple questions may appear on a single page; one question may span two pages.

Algorithm:
    1. Scan each page to determine the current module (from the running header).
    2. Strip the page header boilerplate.
    3. Concatenate cleaned text into one text buffer per module.
    4. Split each module buffer on "QUESTION \\d+" to isolate explanations.
    5. Clean each explanation block.

Output schema:
{
  "test": 4,
  "reading_m1": {"1": "Choice B is correct. ...", "2": "..."},
  "reading_m2": {"1": "..."},
  "math_m1":    {"1": "...", "6": "The correct answer is 9. ..."},
  "math_m2":    {"1": "..."}
}
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Optional, Tuple

import fitz

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPLANATIONS_DIR = REPO_ROOT / "Explanations"
OUTPUT_DIR = REPO_ROOT / "data" / "raw"

sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

EXPLANATION_FILE_NAMES: Dict[int, str] = {
    4:  "sat-practice-test-4-answers-digital.pdf",
    5:  "sat-practice-test-5-answers-digital.pdf",
    6:  "sat-practice-test-6-answers-digital.pdf",
    7:  "sat-practice-test-7-answers-digital.pdf",
    8:  "sat-practice-test-8-answers-digital.pdf",
    9:  "sat-practice-test-9-answers-digital.pdf",
    10: "sat-practice-test-10-answers-digital.pdf",
    11: "sat-practice-test-11-answers-digital.pdf",
}

# ── Regex patterns ──────────────────────────────────────────────────────────────

# Detects which module a page belongs to
_MODULE_DETECT = re.compile(
    r"(READING AND WRITING|MATH):\s*MODULE\s*([12])",
    re.IGNORECASE,
)

# Page header boilerplate to strip (multiple variants found across tests)
_HEADER_PATTERNS = [
    # Running header line: "SAT ANSWER EXPLANATIONS n READING AND WRITING: MODULE N"
    re.compile(
        r"SAT ANSWER EXPLANATIONS\s+\S+\s+(READING AND WRITING|MATH):\s*MODULE\s*[12]",
        re.IGNORECASE,
    ),
    # Page title: "SAT PRACTICE TEST #N ANSWER EXPLANATIONS"
    re.compile(r"SAT PRACTICE TEST\s+#?\d+\s+ANSWER EXPLANATIONS", re.IGNORECASE),
    # Page number patterns: "\t\n7\t\n" or "7\t\n" or lone digits followed by tab
    re.compile(r"\t\n?\d{1,3}\t\n?"),
    re.compile(r"^\d{1,3}\t", re.MULTILINE),
    # Module intro sub-header (first page of each module)
    re.compile(r"Reading and Writing\s*\nModule\s*[12]\s*\n\s*\(\d+ questions\)", re.IGNORECASE),
    re.compile(r"Math\s*\nModule\s*[12]\s*\n\s*\(\d+ questions\)", re.IGNORECASE),
    # Standalone tab characters (OCR tab artifacts)
    re.compile(r"\t"),
]

# QUESTION N delimiter — matches "QUESTION 4" or "QUESTION 4  " (trailing spaces/newlines)
_QUESTION_MARKER = re.compile(r"QUESTION\s+(\d+)\s*", re.IGNORECASE)

# Section-end "n" divider: a standalone "n" on its own line (paragraph mark OCR'd as "n")
_SECTION_N = re.compile(r"^\s*n\s*$", re.MULTILINE)

# Unicode and whitespace cleanup
_NBSP = re.compile(r"\xa0")
_PUA = re.compile(r"[-]")   # Unicode Private Use Area (OCR ligature artifacts)
_MULTI_BLANK = re.compile(r"\n{3,}")


def _strip_page_header(text: str) -> str:
    """Remove running-header boilerplate from a single page's text."""
    for pattern in _HEADER_PATTERNS:
        text = pattern.sub(" ", text)
    return text


def _clean_explanation(text: str) -> str:
    """
    Normalize a raw explanation block:
      - remove 'n' section dividers
      - normalize whitespace
      - remove non-breaking spaces and PUA characters
    """
    text = _SECTION_N.sub("", text)
    text = _NBSP.sub(" ", text)
    text = _PUA.sub("", text)
    text = _MULTI_BLANK.sub("\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


# ── Module key helpers ──────────────────────────────────────────────────────────

def _key_to_name(section: str, module_num: int) -> str:
    prefix = "reading" if section == "reading" else "math"
    return f"{prefix}_m{module_num}"


# ── Core extraction ─────────────────────────────────────────────────────────────

def extract_explanations(test_num: int) -> Dict:
    pdf_path = EXPLANATIONS_DIR / EXPLANATION_FILE_NAMES[test_num]
    if not pdf_path.exists():
        raise FileNotFoundError(f"Explanations PDF not found: {pdf_path}")

    doc = fitz.open(str(pdf_path))
    logger.info("Test %d: %d pages in %s", test_num, len(doc), pdf_path.name)

    # Accumulate cleaned text per (section, module) key
    module_text: Dict[Tuple[str, int], str] = defaultdict(str)
    current_key: Optional[Tuple[str, int]] = None

    for page_idx, page in enumerate(doc):
        raw = page.get_text()

        # Detect module from running header
        m = _MODULE_DETECT.search(raw)
        if m:
            section_word = m.group(1).upper()
            section = "reading" if "READING" in section_word else "math"
            module_num = int(m.group(2))
            current_key = (section, module_num)

        if current_key is None:
            continue  # cover page or pages before first module header

        # Strip page header and append to the module buffer
        cleaned = _strip_page_header(raw)
        module_text[current_key] += cleaned + "\n"

    # Parse each module buffer into {q_num_str: explanation}
    result: Dict[str, Dict[str, str]] = {"test": test_num}
    max_q = {"reading": 33, "math": 27}

    for (section, module_num), text in module_text.items():
        key_name = _key_to_name(section, module_num)
        explanations = _parse_module_explanations(text, max_q[section])
        result[key_name] = explanations

    # Ensure all four modules are present (even if empty)
    for section in ("reading", "math"):
        for module_num in (1, 2):
            key_name = _key_to_name(section, module_num)
            if key_name not in result:
                result[key_name] = {}

    return result


def _parse_module_explanations(text: str, max_q: int) -> Dict[str, str]:
    """
    Split the module text on "QUESTION N" markers and return
    {q_num_str: cleaned_explanation}.
    """
    # Split preserving the Q# captured group
    parts = _QUESTION_MARKER.split(text)
    # parts = [pre_text, "1", expl1, "2", expl2, ...]

    explanations: Dict[str, str] = {}
    i = 1
    while i < len(parts) - 1:
        q_str = parts[i].strip()
        if not q_str.isdigit():
            i += 1
            continue
        q_num = int(q_str)
        if 1 <= q_num <= max_q:
            raw_expl = parts[i + 1] if i + 1 < len(parts) else ""
            explanations[str(q_num)] = _clean_explanation(raw_expl)
        i += 2

    return explanations


# ── Validation and reporting ────────────────────────────────────────────────────

def validate_explanations(data: Dict, test_num: int) -> None:
    expected = {
        "reading_m1": 33, "reading_m2": 33,
        "math_m1": 27,    "math_m2": 27,
    }
    print(f"\n─── Explanation Validation: Test {test_num} ──────────────────")
    total_found = total_exp = 0
    for key, exp in expected.items():
        found = len(data.get(key, {}))
        status = "✓" if found == exp else "✗"
        # Count explanations that look empty or too short
        short = sum(1 for v in data.get(key, {}).values() if len(v) < 50)
        print(f"  {status}  {key:12s}: {found:2d}/{exp}  (short={short})")
        total_found += found
        total_exp += exp

    overall = total_found / total_exp * 100 if total_exp else 0
    print(f"  {'✓' if total_found==total_exp else '✗'}  TOTAL       : "
          f"{total_found}/{total_exp}  ({overall:.0f}%)")

    # Show a sample explanation
    sample_key = "reading_m1"
    sample_q = "1"
    if sample_key in data and sample_q in data[sample_key]:
        preview = data[sample_key][sample_q][:200].replace("\n", " ")
        print(f"\n  Sample (RW M1 Q1): {preview}...")

    print("──────────────────────────────────────────────────────────\n")


# ── CLI ─────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract SAT answer explanations from PDF."
    )
    parser.add_argument("--test", type=int, choices=list(EXPLANATION_FILE_NAMES))
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--out-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    if not args.test and not args.all:
        parser.error("Specify --test N or --all")

    test_ids = list(EXPLANATION_FILE_NAMES) if args.all else [args.test]
    args.out_dir.mkdir(parents=True, exist_ok=True)

    for test_num in test_ids:
        try:
            data = extract_explanations(test_num)
        except FileNotFoundError as exc:
            logger.error("%s — skipping", exc)
            continue

        out_path = args.out_dir / f"test{test_num}_explanations.json"
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)

        logger.info("Wrote → %s", out_path)
        validate_explanations(data, test_num)


if __name__ == "__main__":
    main()
