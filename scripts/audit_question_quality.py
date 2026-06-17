"""
audit_question_quality.py — flag potentially OCR-corrupted questions.

Read-only. Scans output/test*.json, applies heuristics, and writes
reports/corrupted_questions.json. Does NOT modify any question.

Usage:
    python3 scripts/audit_question_quality.py
    python3 scripts/audit_question_quality.py --verbose

Heuristics (each may flag a question; a question can match several):
    excessive_line_breaks  — runs of blank lines / very high newline count
    isolated_operators     — lines that are a lone math operator (+ - = ^ …)
    single_char_lines      — many single-character lines (fragmented OCR)
    malformed_equation     — operator runs / garbled tokens (e.g. "i,.r3")
    broken_choices         — MC choices missing, empty, truncated, or duplicated
    unusually_short        — question text too short to be a real prompt
    ocr_artifacts          — un-normalized markers, PUA chars, separator runs

Note: math questions are inherently formula-heavy and will dominate the flags —
that is expected and useful (these are the candidates for cropped-figure repair).
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "output"
REPORTS_DIR = REPO_ROOT / "reports"
TESTS = range(4, 12)

# ── Tunable thresholds ──────────────────────────────────────────────────────
NEWLINE_MAX = 40            # raw '\n' count above which text looks fragmented
SINGLE_CHAR_LINE_MIN = 3    # this many single-char lines → fragmented
ISOLATED_OP_MIN = 2         # this many operator-only lines → broken equation
SHORT_WORD_MIN = 4          # fewer words than this → unusually short
SHORT_CHAR_MIN = 15         # fewer chars than this → unusually short

_OPERATOR_CHARS = set("+-=^*/×÷·−–—")

# Standalone math symbols that are valid as a whole answer choice.
_MATH_SYMBOLS = set("π√∅∞°±θλμΩΔΣϕφ")
# OCR layout-bracket fragments — never part of a real answer; signal garble.
_LAYOUT_BRACKETS = set("⎛⎜⎝⎞⎟⎠⎧⎨⎩⎫⎬⎭⌈⌉⌊⌋")
_LONE_BRACKET_LINES = {"(", ")", "[", "]", "{", "}"}

# ── Regexes ─────────────────────────────────────────────────────────────────
_RUN_NEWLINES = re.compile(r"\n[ \t]*\n[ \t]*\n")          # 3+ stacked newlines
_OP_ONLY_LINE = re.compile(r"^[+\-=^*/×÷·−–—]{1,2}$")
_OPERATOR_RUN = re.compile(r"(?:[-+=^]\s+){3,}")            # "+ = + ^ ..."
_GARBLED_TOKEN = re.compile(r"[A-Za-z],\.[A-Za-z]")        # "i,.r"
_DOUBLE_EQ = re.compile(r"[=^]{2,}")
_ARTIFACT_WORDS = re.compile(r"percent sign|dollar sign|degree sign|"
                             r"Start referenced|End referenced", re.IGNORECASE)
_SEP_RUN = re.compile(r"~{4,}|-{6,}|\.{6,}|_{5,}|\|{2,}")
_HTML_ISH = re.compile(r"</?[a-z]\b|::[a-z]")              # "</l", "::s"
_LOWER_BLANK = re.compile(r"(?<!\[)\bblank\b(?!\])")        # lowercase 'blank'


def _has_pua(text: str) -> bool:
    """Private-Use-Area or replacement chars indicate OCR substitution."""
    return any(0xE000 <= ord(c) <= 0xF8FF or c == "�" for c in text)


# ── Per-question heuristics ─────────────────────────────────────────────────

def check_excessive_line_breaks(q: Dict) -> Optional[str]:
    text = q.get("question") or ""
    nl = text.count("\n")
    if _RUN_NEWLINES.search(text):
        return "excessive_line_breaks (blank-line run)"
    if nl > NEWLINE_MAX:
        return f"excessive_line_breaks ({nl} newlines)"
    return None


def check_single_char_lines(q: Dict) -> Optional[str]:
    text = q.get("question") or ""
    lines = [ln.strip() for ln in text.split("\n")]
    singles = [ln for ln in lines if len(ln) == 1 and (ln.isalnum() or ln in _OPERATOR_CHARS)]
    if len(singles) >= SINGLE_CHAR_LINE_MIN:
        return f"single_char_lines ({len(singles)} lines)"
    return None


def check_isolated_operators(q: Dict) -> Optional[str]:
    text = q.get("question") or ""
    lines = [ln.strip() for ln in text.split("\n")]
    ops = [ln for ln in lines if ln and _OP_ONLY_LINE.match(ln)]
    if len(ops) >= ISOLATED_OP_MIN:
        return f"isolated_operators ({len(ops)} lines)"
    return None


def check_malformed_equation(q: Dict) -> Optional[str]:
    text = q.get("question") or ""
    if _OPERATOR_RUN.search(text):
        return "malformed_equation (operator run)"
    if _GARBLED_TOKEN.search(text):
        return "malformed_equation (garbled token)"
    if _DOUBLE_EQ.search(text):
        return "malformed_equation (repeated = or ^)"
    return None


def _is_answer_token(v: str) -> bool:
    """
    True if the choice has real answer content. Accepts valid short math answers
    ("6", "30", "1/2", "0.25", "√2", "π", "2π", "−3", "x") — anything with a
    letter/digit, or a standalone math symbol. Rejects pure punctuation/operator
    junk ("+", ")", "⎟").
    """
    v = v.strip()
    if not v:
        return False
    if any(ch.isalnum() for ch in v):   # digit or letter (incl. Greek π, var x)
        return True
    return any(ch in _MATH_SYMBOLS for ch in v)


def _is_garbled_choice(v: str) -> bool:
    """
    OCR formula garble that is never a valid answer: layout-bracket glyphs
    (⎛⎜⎝…) or a lone parenthesis/bracket on its own line within the choice
    (e.g. "w w + 9\\n(\\n)"). Does NOT trigger on stacked fractions like "1\\n3".
    """
    if any(ch in _LAYOUT_BRACKETS for ch in v):
        return True
    return any(ln.strip() in _LONE_BRACKET_LINES for ln in v.split("\n"))


def check_broken_choices(q: Dict) -> Optional[str]:
    if q.get("question_type") != "multiple_choice":
        return None
    choices = q.get("choices")
    if not choices:
        return "broken_choices (missing choices)"
    keys = {"A", "B", "C", "D"}
    present = set(choices.keys())
    if present != keys:
        return f"broken_choices (keys={sorted(present)})"
    values = [(choices[k] or "").strip() for k in ["A", "B", "C", "D"]]
    if any(v == "" for v in values):
        return "broken_choices (empty choice)"
    if any(_is_garbled_choice(v) for v in values):
        return "broken_choices (garbled choice)"
    # Flag non-answer fragments (pure punctuation/operator), NOT valid short
    # numeric answers like "6" — length alone is no longer a signal.
    if any(not _is_answer_token(v) for v in values):
        return "broken_choices (non-answer fragment)"
    if len(set(values)) < len(values):
        return "broken_choices (duplicate choices)"
    return None


def check_unusually_short(q: Dict) -> Optional[str]:
    text = (q.get("question") or "").strip()
    words = len(text.split())
    chars = len(text)
    if words < SHORT_WORD_MIN or chars < SHORT_CHAR_MIN:
        return f"unusually_short ({words} words, {chars} chars)"
    return None


def check_ocr_artifacts(q: Dict) -> Optional[str]:
    text = q.get("question") or ""
    hits: List[str] = []
    if _ARTIFACT_WORDS.search(text):
        hits.append("un-normalized marker")
    if _has_pua(text):
        hits.append("private-use char")
    if _SEP_RUN.search(text):
        hits.append("separator run")
    if _HTML_ISH.search(text):
        hits.append("html-ish fragment")
    if _LOWER_BLANK.search(text):
        hits.append("lowercase 'blank'")
    return f"ocr_artifacts ({', '.join(hits)})" if hits else None


HEURISTICS = [
    check_excessive_line_breaks,
    check_isolated_operators,
    check_single_char_lines,
    check_malformed_equation,
    check_broken_choices,
    check_unusually_short,
    check_ocr_artifacts,
]


def audit_question(q: Dict) -> List[str]:
    """Return the list of triggered reason strings for one question."""
    reasons: List[str] = []
    for check in HEURISTICS:
        result = check(q)
        if result:
            reasons.append(result)
    return reasons


# ── Driver ──────────────────────────────────────────────────────────────────

def reason_code(reason: str) -> str:
    """Strip the parenthetical detail to get the bare heuristic name."""
    return reason.split(" (")[0]


def run_audit(verbose: bool = False) -> Tuple[List[Dict], Dict]:
    flagged: List[Dict] = []
    scanned = 0
    by_test: Counter = Counter()
    by_section: Counter = Counter()
    by_type: Counter = Counter()
    by_reason: Counter = Counter()

    for t in TESTS:
        path = OUTPUT_DIR / f"test{t}.json"
        if not path.exists():
            print(f"WARN missing {path}")
            continue
        questions = json.loads(path.read_text(encoding="utf-8"))
        for q in questions:
            scanned += 1
            reasons = audit_question(q)
            if not reasons:
                continue
            flagged.append({
                "question_id": q.get("id"),
                "reason": "; ".join(reasons),
                "reasons": [reason_code(r) for r in reasons],
                "test": q.get("test"),
                "section": q.get("section"),
                "topic": q.get("topic"),
                "question_type": q.get("question_type"),
                "question": q.get("question"),
            })
            by_test[t] += 1
            by_section[q.get("section")] += 1
            by_type[q.get("question_type")] += 1
            for r in reasons:
                by_reason[reason_code(r)] += 1
            if verbose:
                print(f"  flag {q.get('id')}: {'; '.join(reasons)}")

    summary = {
        "scanned": scanned,
        "flagged": len(flagged),
        "flagged_pct": round(len(flagged) / scanned * 100, 1) if scanned else 0,
        "by_reason": dict(by_reason.most_common()),
        "by_test": {f"test{t}": by_test[t] for t in TESTS if by_test[t]},
        "by_section": dict(by_section),
        "by_question_type": dict(by_type),
    }
    return flagged, summary


def print_summary(summary: Dict) -> None:
    print("\n" + "=" * 60)
    print(" Question Quality Audit")
    print("=" * 60)
    print(f" Scanned : {summary['scanned']}")
    print(f" Flagged : {summary['flagged']}  ({summary['flagged_pct']}%)")

    print("\n By reason (a question may match several):")
    for reason, count in summary["by_reason"].items():
        print(f"   {reason:24s} {count}")

    print("\n By section:")
    for section, count in summary["by_section"].items():
        print(f"   {section:24s} {count}")

    print("\n By question type:")
    for qtype, count in summary["by_question_type"].items():
        print(f"   {qtype:24s} {count}")

    print("\n By test:")
    for test, count in summary["by_test"].items():
        print(f"   {test:24s} {count}")
    print("=" * 60 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit question quality (read-only).")
    parser.add_argument("--verbose", action="store_true", help="Print each flagged question id")
    parser.add_argument("--out", type=Path, default=REPORTS_DIR / "corrupted_questions.json")
    args = parser.parse_args()

    flagged, summary = run_audit(verbose=args.verbose)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps({"summary": summary, "flagged": flagged}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print_summary(summary)
    print(f"Wrote {len(flagged)} flagged questions → {args.out}")
    print("No questions were modified.")


if __name__ == "__main__":
    main()
