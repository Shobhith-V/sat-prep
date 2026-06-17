"""
extract_questions.py — Extract SAT questions from practice-test PDFs.

Usage:
    python extract_questions.py --test 4
    python extract_questions.py --test 4 --section reading --module 1
    python extract_questions.py --all

Output: data/raw/test{N}_questions.json

Each question entry matches the final schema:
    {
        "id":              "test4_rw_m1_q13",
        "test":            4,
        "section":         "reading",
        "module":          1,
        "question_number": 13,
        "page":            10,
        "question_type":   "multiple_choice",
        "question":        "...",
        "choices":         {"A": "...", "B": "...", "C": "...", "D": "..."},
        "correct_answer":  null,
        "explanation":     null,
        "topic":           null,
        "subtopic":        null,
        "difficulty":      null,
        "assets":          []
    }

Strategy
--------
1. Detect module boundary pages dynamically using find_module_pages().
2. For each page in the module, extract text blocks sorted in two-column
   reading order (left col first, then right col, each top-to-bottom).
3. Build a flat stream of (page_number, block) tuples.
4. Scan the stream for question-number blocks:
     - text matches r'^\\d{1,2}$'
     - block width < 60 px  (question-number boxes are narrow)
     - number is sequential (prev_q + 1) or is 1 (first question)
     - next substantive block has meaningful text (look-ahead guard)
5. Accumulate blocks between Q# markers into a raw block list per question.
6. Parse each raw block list: separate passage + stem from choices,
   detect question type (multiple_choice vs numeric_response).
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import fitz

# ── Project paths (resolve relative to this file's parent) ───────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
QUESTIONS_DIR = REPO_ROOT / "Questions"
OUTPUT_DIR = REPO_ROOT / "data" / "raw"

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import (
    clean_text,
    find_module_pages,
    get_blocks_in_reading_order,
    is_noise_block,
    open_pdf,
    Q_NUM_MAX_WIDTH,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s  %(message)s",
)
logger = logging.getLogger(__name__)

# ── File naming ───────────────────────────────────────────────────────────────

TEST_FILE_NAMES: Dict[int, str] = {
    4:  "sat-practice-test-4-digital.pdf",
    5:  "sat-practice-test-5-digital.pdf",
    6:  "sat-practice-test-6-digital.pdf",
    7:  "sat-practice-test-7-digital.pdf",
    8:  "sat-practice-test-8-digital.pdf",
    9:  "sat-practice-test-9-digital.pdf",
    10: "sat-practice-test-10-digital.pdf",
    11: "sat-practice-test-11-digital.pdf",
}

# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class RawQuestion:
    question_number: int
    page: int
    section: str
    module: int
    test: int
    blocks: List[str] = field(default_factory=list)


# ── Choice parsing ────────────────────────────────────────────────────────────

# Matches the START of a choice line: A) / B) / C) / D)
_CHOICE_START = re.compile(r"^([ABCD])\)\s*(.*)$", re.DOTALL)

# Detects that a block is a standalone choice label line (possibly just "A)")
_CHOICE_ONLY = re.compile(r"^[ABCD]\)$")


# Matches inline runs of choices merged into one block, separated by either a
# pipe ("B) x | C) y | D) z") or a newline ("B) x\nC) y\nD) z" — the test-11
# layout). The lookahead means a newline INSIDE a choice (wrapped text not
# followed by a choice marker) is left intact.
_INLINE_CHOICE_SEP = re.compile(r"\s*[|\n]\s*(?=[ABCD]\))")

# Bullet glyphs used as choice markers in some tests (e.g. test 8) instead of "A)".
_BULLET = re.compile(r"^[•▪●◦‣·]\s*(.+)$", re.DOTALL)
_PROMPT = re.compile(r"which choice", re.IGNORECASE)


def _split_inline_choices(block_text: str) -> List[str]:
    """
    If a single block contains multiple choices merged with "|" or newline
    separators, split them into individual blocks. Otherwise return unchanged.
    """
    parts = _INLINE_CHOICE_SEP.split(block_text)
    return parts if len(parts) > 1 else [block_text]


def parse_question_block(blocks: List[str]) -> Tuple[str, Optional[Dict[str, str]], str]:
    """
    Given the accumulated text blocks for one question, return:
        (question_text, choices_dict_or_None, question_type)

    question_text   : passage + stem combined (everything before the first choice)
    choices_dict    : {"A": "...", "B": "...", "C": "...", "D": "..."} or None
    question_type   : "multiple_choice" | "numeric_response"
    """
    # Expand any blocks that contain multiple choices merged in one line
    expanded: List[str] = []
    for b in blocks:
        expanded.extend(_split_inline_choices(b))
    blocks = expanded

    choices: Dict[str, str] = {}
    question_parts: List[str] = []
    bullet_choices: List[str] = []   # bullet-marker choices seen after the prompt
    current_letter: Optional[str] = None
    current_choice_parts: List[str] = []
    in_choices = False
    seen_prompt = False

    def flush_choice() -> None:
        if current_letter and current_choice_parts:
            choices[current_letter] = " ".join(current_choice_parts).strip()

    for block in blocks:
        block = clean_text(block)
        if not block:
            continue

        if _PROMPT.search(block):
            seen_prompt = True

        m = _CHOICE_START.match(block)
        bullet = _BULLET.match(block)
        if m:
            # Save any open choice
            flush_choice()
            in_choices = True
            current_letter = m.group(1)
            rest = m.group(2).strip()
            current_choice_parts = [rest] if rest else []
        elif in_choices and current_letter:
            # Continuation line of the current choice
            current_choice_parts.append(block)
        elif seen_prompt and bullet and not in_choices:
            # Bullet-style choice (after the prompt) — collected as a fallback;
            # only used if no lettered choices are found.
            bullet_choices.append(bullet.group(1).strip())
        else:
            # Part of the question passage or stem
            question_parts.append(block)

    flush_choice()

    question_text = "\n\n".join(q.strip() for q in question_parts if q.strip())

    if len(choices) == 4 and all(k in choices for k in "ABCD"):
        return question_text, choices, "multiple_choice"
    if choices:
        # Partial lettered choices — still call it MC (may have parsing issues)
        logger.warning("Only %d choices parsed; expected 4.", len(choices))
        return question_text, choices, "multiple_choice"
    if len(bullet_choices) == 4:
        # Fallback: 4 bullet-marker choices map to A–D in source order.
        mapped = {k: v for k, v in zip("ABCD", bullet_choices)}
        return question_text, mapped, "multiple_choice"
    return question_text, None, "numeric_response"


# ── Question-number detection ─────────────────────────────────────────────────

def _is_question_number_block(
    block: Dict,
    max_q: int,
    prev_q_num: Optional[int],
) -> bool:
    """
    Return True if *block* is a question-number marker.

    Criteria:
      1. Text contains only 1-2 digits.
      2. The number is in [1, max_q].
      3. Block width < Q_NUM_MAX_WIDTH (question numbers are narrow boxes).
      4. The number is sequential: either 1 (first question) or prev_q + 1.
         We allow a skip of up to +2 to handle occasional missed questions
         without derailing the entire extraction.
    """
    text = block["text"].strip()
    if not re.match(r"^\d{1,2}$", text):
        return False

    n = int(text)
    if n < 1 or n > max_q:
        return False

    if block["width"] > Q_NUM_MAX_WIDTH:
        return False

    if prev_q_num is None:
        # Accept 1 or small numbers as the first Q# on a module start
        return n <= 3

    # Must advance (allow up to +2 skip in case a question was missed)
    return 1 <= (n - prev_q_num) <= 3


def _has_substantive_followup(
    stream: List[Tuple[int, Dict]],
    candidate_idx: int,
    min_length: int = 12,
) -> bool:
    """
    Look ahead in the stream from candidate_idx to see whether the next
    non-noise block has at least *min_length* characters.

    This guards against axis-label digits being mistaken for Q# markers.
    """
    for j in range(candidate_idx + 1, min(candidate_idx + 8, len(stream))):
        _, blk = stream[j]
        txt = clean_text(blk["text"]).strip()
        if not txt or is_noise_block(txt):
            continue
        # If the next block is ALSO a pure digit, it's likely chart axis labels
        if re.match(r"^\d{1,2}$", txt) and blk["width"] < Q_NUM_MAX_WIDTH:
            return False
        if len(txt) >= min_length:
            return True
        # Short non-digit text (math label, variable name): ok
        return True
    return False


# ── End-of-test sentinel ─────────────────────────────────────────────────────

_END_OF_TEST_RE = re.compile(
    # Anchored patterns (start-of-line) — all specific to back-cover/last-page content
    r"(^WF2P0019"
    r"|^©\s*\d{4}\s*College Board"   # College Board copyright only (NOT passage citations)
    r"|^GENERAL DIRECTIONS"
    r"|^TIMING\b"
    r"|^MARKING YOUR ANSWERS"
    r"|^USING YOUR TEST BOOK"
    # Un-anchored: specific phrases that only appear in back-cover test directions
    r"|You may work on only one module"
    r"|Reading and Writing, Module 1\s*:"
    r"|10-minute break"
    r")",
    re.I | re.MULTILINE,
)


def _is_end_of_test_block(text: str) -> bool:
    """Return True if the block is end-of-test boilerplate (back cover, directions)."""
    return bool(_END_OF_TEST_RE.search(text))


# ── Stream building ───────────────────────────────────────────────────────────

def _build_stream(
    doc: fitz.Document,
    start_page: int,
    end_page: int,
) -> List[Tuple[int, Dict]]:
    """
    Return an ordered list of (1-based page number, block dict) tuples
    for all pages in [start_page, end_page) (0-based indices).
    """
    stream: List[Tuple[int, Dict]] = []
    for page_idx in range(start_page, end_page):
        page = doc[page_idx]
        for block in get_blocks_in_reading_order(page):
            stream.append((page_idx + 1, block))
    return stream


# ── Module extraction ─────────────────────────────────────────────────────────

def extract_module(
    doc: fitz.Document,
    test_num: int,
    section: str,
    module_num: int,
    module_pages: Dict[Tuple[str, int], int],
) -> List[Dict]:
    """
    Extract all questions from one SAT module and return a list of question dicts.

    Parameters
    ----------
    doc          : open PyMuPDF document
    test_num     : integer test number (4-11)
    section      : "reading" or "math"
    module_num   : 1 or 2
    module_pages : output of find_module_pages(doc)
    """
    key = (section, module_num)
    start_page = module_pages[key]

    # Determine end page: start of next module, or end of doc
    ordered_keys = [
        ("reading", 1), ("reading", 2), ("math", 1), ("math", 2)
    ]
    this_idx = ordered_keys.index(key)
    if this_idx + 1 < len(ordered_keys):
        next_key = ordered_keys[this_idx + 1]
        end_page = module_pages.get(next_key, len(doc))
    else:
        end_page = len(doc)

    max_q = 33 if section == "reading" else 27
    section_code = "rw" if section == "reading" else "math"

    logger.info(
        "Extracting test%d %s module %d  (pages %d–%d, up to %d questions)",
        test_num, section, module_num, start_page + 1, end_page, max_q,
    )

    stream = _build_stream(doc, start_page, end_page)

    # ── Pass: collect RawQuestion objects ──────────────────────────────────────
    raw_questions: List[RawQuestion] = []
    current: Optional[RawQuestion] = None
    prev_q_num: Optional[int] = None
    past_directions = False   # wait until we pass the header/directions text

    for i, (page_num, block) in enumerate(stream):
        text = block["text"].strip()
        text_clean = clean_text(text)

        # Skip empty or boilerplate blocks
        if not text_clean or is_noise_block(text_clean):
            continue

        # Hard stop: end-of-test content on last pages (copyright, general directions)
        if _is_end_of_test_block(text_clean):
            logger.debug("End-of-test sentinel at page %d — stopping stream", page_num)
            break

        # Skip the directions / reference section at the start of a module.
        # We consider "past directions" once we have seen the first valid Q#.
        if not past_directions:
            # Check whether this block IS the first question number
            if _is_question_number_block(block, max_q, None) and \
               _has_substantive_followup(stream, i):
                past_directions = True
                prev_q_num = None  # reset; let the block be processed below
            else:
                continue  # still in directions/header — skip

        # ── Question-number block detection ───────────────────────────────────
        if _is_question_number_block(block, max_q, prev_q_num) and \
           _has_substantive_followup(stream, i):

            # Save the previous question (if any)
            if current is not None:
                raw_questions.append(current)

            q_num = int(text)
            current = RawQuestion(
                question_number=q_num,
                page=page_num,
                section=section,
                module=module_num,
                test=test_num,
            )
            prev_q_num = q_num

        elif current is not None:
            # Accumulate text into the current question
            if not is_noise_block(text_clean):
                # Safety net: once we have all expected questions, stop if the
                # page has jumped far ahead (back-cover / general-directions pages).
                if prev_q_num == max_q and (page_num - current.page) > 1:
                    logger.debug(
                        "Q%d: discarding stray block from page %d (started p%d)",
                        prev_q_num, page_num, current.page,
                    )
                    continue
                current.blocks.append(text_clean)

    # Flush the last question
    if current is not None:
        raw_questions.append(current)

    # ── Parse each raw question into the final schema ─────────────────────────
    results: List[Dict] = []
    for rq in raw_questions:
        question_text, choices, question_type = parse_question_block(rq.blocks)

        q_id = f"test{test_num}_{section_code}_m{module_num}_q{rq.question_number}"

        # Detect whether this question likely involves a visual
        has_visual = _question_has_visual(question_text, choices)

        entry: Dict = {
            "id": q_id,
            "test": test_num,
            "section": section,
            "module": module_num,
            "question_number": rq.question_number,
            "page": rq.page,
            "question_type": question_type,
            "question": question_text,
            "choices": choices,
            "correct_answer": None,
            "explanation": None,
            "topic": None,
            "subtopic": None,
            "difficulty": None,
            "assets": _build_asset_refs(test_num, rq.page) if has_visual else [],
        }
        results.append(entry)

    logger.info(
        "  → extracted %d / %d questions for %s module %d",
        len(results), max_q, section, module_num,
    )
    return results


# ── Visual detection ──────────────────────────────────────────────────────────

_VISUAL_KEYWORDS = re.compile(
    r"\b(graph|table|figure|chart|scatterplot|bar graph|line graph|dot plot"
    r"|diagram|coordinate|plot|image|illustration)\b",
    re.I,
)


def _question_has_visual(question_text: str, choices: Optional[Dict]) -> bool:
    """Return True if the question likely references a visual element."""
    combined = question_text or ""
    if choices:
        combined += " " + " ".join(choices.values())
    return bool(_VISUAL_KEYWORDS.search(combined))


def _build_asset_refs(test_num: int, page: int) -> List[Dict]:
    """Build the asset reference entry for a question that needs a page image."""
    return [
        {
            "type": "image",
            "src": f"assets/test{test_num}/page_{page:03d}.png",
        }
    ]


# ── Top-level extract function ────────────────────────────────────────────────

def extract_all_modules(
    test_num: int,
    section_filter: Optional[str] = None,
    module_filter: Optional[int] = None,
) -> List[Dict]:
    """
    Open the questions PDF for *test_num* and extract all (or filtered) modules.

    Returns a flat list of question dicts for all requested modules.
    """
    pdf_path = QUESTIONS_DIR / TEST_FILE_NAMES[test_num]
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = open_pdf(pdf_path)
    module_pages = find_module_pages(doc)

    all_questions: List[Dict] = []

    modules_to_run = [
        ("reading", 1),
        ("reading", 2),
        ("math", 1),
        ("math", 2),
    ]
    if section_filter:
        modules_to_run = [(s, m) for s, m in modules_to_run if s == section_filter]
    if module_filter:
        modules_to_run = [(s, m) for s, m in modules_to_run if m == module_filter]

    for section, module_num in modules_to_run:
        try:
            questions = extract_module(doc, test_num, section, module_num, module_pages)
            all_questions.extend(questions)
        except Exception as exc:
            logger.error("Failed to extract %s module %d: %s", section, module_num, exc)
            raise

    return all_questions


# ── Reporting ─────────────────────────────────────────────────────────────────

def accuracy_report(questions: List[Dict]) -> None:
    """Print a concise extraction accuracy report."""
    expected = {
        ("reading", 1): 33, ("reading", 2): 33,
        ("math", 1): 27, ("math", 2): 27,
    }
    by_module: Dict[Tuple[str, int], List[Dict]] = {}
    for q in questions:
        key = (q["section"], q["module"])
        by_module.setdefault(key, []).append(q)

    print("\n─── Extraction Accuracy Report ───────────────────────────────")
    total_expected = 0
    total_got = 0
    for key in [("reading", 1), ("reading", 2), ("math", 1), ("math", 2)]:
        exp = expected.get(key, 0)
        got = len(by_module.get(key, []))
        section, module = key
        pct = (got / exp * 100) if exp else 0
        status = "✓" if got == exp else "✗"
        print(f"  {status}  {section:8s} module {module}: {got:2d}/{exp:2d}  ({pct:.0f}%)")
        total_expected += exp
        total_got += got

    overall = (total_got / total_expected * 100) if total_expected else 0
    print(f"  {'✓' if total_got == total_expected else '✗'}  TOTAL         : {total_got}/{total_expected}  ({overall:.0f}%)")

    # Question-type breakdown
    mc = sum(1 for q in questions if q["question_type"] == "multiple_choice")
    nr = sum(1 for q in questions if q["question_type"] == "numeric_response")
    vis = sum(1 for q in questions if q.get("assets"))
    print(f"\n  Multiple-choice   : {mc}")
    print(f"  Numeric-response  : {nr}")
    print(f"  With visual asset : {vis}")
    print("──────────────────────────────────────────────────────────────\n")

    # Sample: first 3 questions
    print("─── Sample (first 3 questions) ───────────────────────────────")
    for q in questions[:3]:
        print(f"  id: {q['id']}")
        print(f"  type: {q['question_type']}")
        print(f"  page: {q['page']}")
        q_preview = (q["question"] or "")[:120].replace("\n", " ")
        print(f"  question: {q_preview}...")
        if q["choices"]:
            for letter, text in list(q["choices"].items())[:2]:
                print(f"  choice {letter}: {(text or '')[:60]}")
        print()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Extract SAT questions from practice-test PDFs.")
    parser.add_argument("--test", type=int, choices=list(TEST_FILE_NAMES), help="Test number (4-11)")
    parser.add_argument("--all", action="store_true", help="Extract all tests (4-11)")
    parser.add_argument("--section", choices=["reading", "math"], help="Limit to one section")
    parser.add_argument("--module", type=int, choices=[1, 2], help="Limit to one module")
    parser.add_argument("--out-dir", type=Path, default=OUTPUT_DIR, help="Output directory")
    args = parser.parse_args()

    if not args.test and not args.all:
        parser.error("Specify --test N or --all")

    test_ids = list(TEST_FILE_NAMES) if args.all else [args.test]
    args.out_dir.mkdir(parents=True, exist_ok=True)

    for test_num in test_ids:
        logger.info("═══ Test %d ═══════════════════════════════════════════", test_num)
        try:
            questions = extract_all_modules(test_num, args.section, args.module)
        except FileNotFoundError as exc:
            logger.error("%s — skipping", exc)
            continue

        out_path = args.out_dir / f"test{test_num}_questions.json"
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(questions, fh, indent=2, ensure_ascii=False)

        logger.info("Wrote %d questions → %s", len(questions), out_path)
        accuracy_report(questions)


if __name__ == "__main__":
    main()
