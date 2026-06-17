"""
utils.py — Shared utilities for the SAT PDF extraction pipeline.

Handles:
  - PDF opening
  - OCR artifact normalization
  - Noise / chart-garbage detection
  - Coordinate-aware block extraction (two-column reading order)
  - Dynamic module-boundary detection
"""

import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# ── Page geometry ──────────────────────────────────────────────────────────────

COL_SPLIT_X: float = 295   # x-coord dividing left and right text columns
HEADER_Y_MAX: float = 55   # skip blocks whose bottom edge is above this
FOOTER_Y_MIN: float = 730  # skip blocks whose top edge is below this
Q_NUM_MAX_WIDTH: float = 60  # question-number blocks are always narrow

# ── OCR normalisation table ────────────────────────────────────────────────────

_OCR_STRING_SUBS: List[Tuple[str, str]] = [
    ("percent sign", "%"),
    ("dollar sign", "$"),
    ("degree sign", "°"),
    # Accessible-text markup inserted by the PDF producer
    ("Start referenced content:", ""),
    ("End referenced content.", ""),
    ("End referenced content:", ""),
]

_OCR_REGEX_SUBS: List[Tuple[re.Pattern, str]] = [
    # Footer boilerplate
    (re.compile(r"Unauthorized copying or reuse of any part of this page is illegal\.?", re.I), ""),
    # Navigation text
    (re.compile(r"\b(CONTINUE|STOP)\b"), ""),
    # "If you finish before time is called…" end-of-module note
    (re.compile(r"If you finish before time is called.*", re.DOTALL | re.I), ""),
    # Collapse 3+ blank lines into 2
    (re.compile(r"\n{3,}"), "\n\n"),
    # Collapse multiple spaces
    (re.compile(r"[ \t]{2,}"), " "),
    # Non-breaking space → regular space
    (re.compile(r"\xa0"), " "),
    # Strip Unicode Private-Use Area characters (OCR ligature artifacts)
    (re.compile(r"[-]"), ""),
    # Replace "blank" placeholder with a visible marker
    (re.compile(r"\bblank\b"), "[BLANK]"),
]

# ── Noise patterns ─────────────────────────────────────────────────────────────

# Blocks whose entire text matches one of these are discarded.
_NOISE_FULL_MATCH: List[re.Pattern] = [
    re.compile(r"^[-=~.\s]{3,}$"),            # separator lines: ----, ~~~~, .....
    re.compile(r"^No Test Material"),          # blank-page marker
    re.compile(r"^Unauthorized copying"),      # footer (already cleaned, but defensive)
    re.compile(r"^(CONTINUE|STOP)\b"),         # navigation words (may have trailing text)
    re.compile(r"^n$"),                        # explanation section-end marker "n"
    re.compile(r"^Module\s*\n?\s*[12]\b"),     # "Module 1" / "Module 2" page header
    re.compile(r"^Reading and Writing\s*\nModule", re.I),
    re.compile(r"^\d+\s*QUESTIONS?\s*\n?\s*DIRECTIONS?", re.I),  # header on module page
    re.compile(r"^For multiple-choice questions", re.I),           # math instructions page
    re.compile(r"^For student-produced response", re.I),           # math instructions page
    re.compile(r"^Unless otherwise indicated", re.I),              # math notes section
    re.compile(r"^NOTES?\b", re.I),
    re.compile(r"^REFERENCE\b", re.I),
    re.compile(r"^DIRECTIONS\b", re.I),
    # End-of-test boilerplate (last PDF page)
    re.compile(r"^WF2P0019"),                  # barcode/serial on back cover
    re.compile(r"^©\s*\d{4}\s*College Board", re.I),
    re.compile(r"^GENERAL DIRECTIONS", re.I),
    re.compile(r"^The SAT[®.]?\s*$", re.I),
    re.compile(r"^TIMING\b", re.I),
    re.compile(r"^MARKING YOUR ANSWERS", re.I),
    re.compile(r"^USING YOUR TEST BOOK", re.I),
]

# Blocks containing any of these sub-patterns are likely OCR garbage from
# charts / geometry figures and are discarded.
_CHART_NOISE_SUBS: List[re.Pattern] = [
    re.compile(r"[+]{3,}"),              # repeated + from coordinate grids
    re.compile(r"[-]{6,}"),              # 6+ dashes from chart lines
    re.compile(r"<\/?\s*[a-z]"),         # <l>, </l>, etc. — OCR HTML-like artifacts
    re.compile(r"::\s*[a-z]"),           # ::s, ::l — OCR symbol artifacts
    re.compile(r"\.\.\.\.\.\s*[A-Za-z_]"),  # OCR dotted lines followed by text
    re.compile(r"[~]{3,}"),              # repeated ~ from figure lines
    re.compile(r"[|]{3,}"),              # repeated | from table borders
]


def clean_text(text: str) -> str:
    """Normalise OCR artifacts; return stripped cleaned text."""
    for old, new in _OCR_STRING_SUBS:
        text = text.replace(old, new)
    for pattern, replacement in _OCR_REGEX_SUBS:
        text = pattern.sub(replacement, text)
    return text.strip()


def is_noise_block(text: str) -> bool:
    """Return True if a block's text is boilerplate, a separator, or chart garbage."""
    stripped = text.strip()
    if not stripped:
        return True
    for pattern in _NOISE_FULL_MATCH:
        if pattern.search(stripped):
            return True
    for pattern in _CHART_NOISE_SUBS:
        if pattern.search(stripped):
            return True
    return False


# ── Block extraction ───────────────────────────────────────────────────────────

def get_blocks_in_reading_order(
    page: fitz.Page,
    col_split: float = COL_SPLIT_X,
    header_y: float = HEADER_Y_MAX,
    footer_y: float = FOOTER_Y_MIN,
) -> List[Dict]:
    """
    Extract text blocks from *page* sorted in two-column reading order:
      left column (x0 < col_split) top-to-bottom, then right column top-to-bottom.

    Skips page-header band (y < header_y) and footer band (y > footer_y).
    Skips spans rendered with hidden OCR fonts.

    Each returned dict has keys:
      text  – cleaned text of the block
      x0, y0, x1, y1 – bounding box
      col   – 0 (left) or 1 (right)
      width – x1 - x0
    """
    d = page.get_text("dict")
    blocks: List[Dict] = []

    for block in d["blocks"]:
        if block["type"] != 0:          # 0 = text; skip image blocks
            continue

        x0, y0, x1, y1 = block["bbox"]

        # Skip header / footer bands.
        # Use y0 (top edge) for the header check so that blocks which START
        # inside the header zone (module number, page-border markers) are always
        # excluded even when their bottom edge exceeds the threshold.
        if y0 < header_y or y0 > footer_y:
            continue

        # Collect text from visible spans only
        line_texts: List[str] = []
        for line in block["lines"]:
            span_texts: List[str] = []
            for span in line["spans"]:
                if "Hidden" in span.get("font", ""):
                    continue
                span_texts.append(span["text"])
            if span_texts:
                line_texts.append("".join(span_texts))

        text = "\n".join(line_texts).strip()
        if not text:
            continue

        col = 0 if x0 < col_split else 1

        blocks.append(
            {
                "text": text,
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": y1,
                "col": col,
                "width": x1 - x0,
            }
        )

    # Left column first, then right column; within each column sort top-to-bottom.
    blocks.sort(key=lambda b: (b["col"], b["y0"]))
    return blocks


# ── Module boundary detection ─────────────────────────────────────────────────

# Module header patterns — tested against the full page text (get_text()).
_MODULE_PATTERNS: Dict[Tuple[str, int], re.Pattern] = {
    ("reading", 1): re.compile(r"Module\s*\n\s*1\s*\nReading and Writing", re.I),
    ("reading", 2): re.compile(r"Module\s*\n\s*2\s*\nReading and Writing", re.I),
    ("math", 1): re.compile(r"Module\s*\n\s*1\s*\nMath\b", re.I),
    ("math", 2): re.compile(r"Module\s*\n\s*2\s*\nMath\b", re.I),
}

# Fallback: some tests (e.g. test 11) embed "Module N" differently.
_ALT_DIRECTIONS: Dict[Tuple[str, int], re.Pattern] = {
    ("reading", 1): re.compile(r"DIRECTIONS.*reading and writing skills", re.I | re.DOTALL),
    ("reading", 2): re.compile(r"DIRECTIONS.*reading and writing skills", re.I | re.DOTALL),
    ("math", 1): re.compile(r"DIRECTIONS.*math skills", re.I | re.DOTALL),
    ("math", 2): re.compile(r"DIRECTIONS.*math skills", re.I | re.DOTALL),
}


def find_module_pages(doc: fitz.Document) -> Dict[Tuple[str, int], int]:
    """
    Scan every page and return a mapping of (section, module) → 0-based page index.

    Example: {('reading', 1): 3, ('reading', 2): 17, ('math', 1): 31, ('math', 2): 39}

    Raises ValueError if any of the four expected modules is missing.
    """
    found: Dict[Tuple[str, int], int] = {}
    rw_count = 0
    math_count = 0

    for idx, page in enumerate(doc):
        text = page.get_text()

        for key, pattern in _MODULE_PATTERNS.items():
            if key not in found and pattern.search(text):
                found[key] = idx
                logger.debug("Found %s module %s at page %d (1-based)", key[0], key[1], idx + 1)

    # Fallback for alt-format tests
    if len(found) < 4:
        for idx, page in enumerate(doc):
            text = page.get_text()
            rw_match = _ALT_DIRECTIONS[("reading", 1)].search(text)
            math_match = _ALT_DIRECTIONS[("math", 1)].search(text)
            if rw_match and rw_count < 2:
                rw_count += 1
                key = ("reading", rw_count)
                if key not in found:
                    found[key] = idx
            if math_match and math_count < 2:
                math_count += 1
                key = ("math", math_count)
                if key not in found:
                    found[key] = idx

    missing = [k for k in [("reading", 1), ("reading", 2), ("math", 1), ("math", 2)] if k not in found]
    if missing:
        raise ValueError(f"Could not locate module(s) in PDF: {missing}")

    return found


def open_pdf(path: Path) -> fitz.Document:
    """Open a PDF and verify it has pages."""
    doc = fitz.open(str(path))
    if len(doc) == 0:
        raise ValueError(f"PDF has no pages: {path}")
    logger.info("Opened %s (%d pages)", path.name, len(doc))
    return doc
