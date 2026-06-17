"""
extract_images.py — Render SAT question PDF pages to PNG and build an image manifest.

Usage:
    python extract_images.py --test 4
    python extract_images.py --all
    python extract_images.py --all --force    # re-render even if PNGs exist

Output:
    output/assets/test{N}/page_{NNN}.png    — full-page renders at 150 DPI
    data/raw/test{N}_image_manifest.json    — per-question image associations

Design decisions:
  - Every page of the questions PDF is rendered, not only "visual" pages.
    This ensures the React front-end always has a backing image available,
    even for questions that were not flagged as visual at extraction time.

  - 150 DPI gives 1275 × 1650 px on a standard 8.5 × 11-inch page.
    This is sufficient for reading chart labels and table text without
    producing files that are too large for GitHub Pages.

  - Pages are skipped if the PNG already exists (unless --force).

  - The manifest lists every question that has at least one asset reference.
    It is computed from the previously extracted questions JSON, so
    extract_questions.py must run first.

Manifest entry schema:
{
  "question_id":    "test4_rw_m1_q13",
  "test":           4,
  "section":        "reading",
  "module":         1,
  "question_number": 13,
  "page":           10,
  "assets": [
    {"type": "image", "src": "assets/test4/page_010.png"}
  ]
}
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List

import fitz

REPO_ROOT = Path(__file__).resolve().parent.parent
QUESTIONS_DIR = REPO_ROOT / "Questions"
QUESTIONS_RAW_DIR = REPO_ROOT / "data" / "raw"
OUTPUT_ASSETS_DIR = REPO_ROOT / "output" / "assets"

sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

RENDER_DPI = 150    # output resolution
MATRIX = fitz.Matrix(RENDER_DPI / 72, RENDER_DPI / 72)

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


# ── Page rendering ──────────────────────────────────────────────────────────────

def render_test_pages(test_num: int, force: bool = False) -> Dict[int, Path]:
    """
    Render all pages of the questions PDF to PNG files.

    Returns a dict mapping 1-based PDF page number → output PNG path.
    Pages that already exist are skipped unless force=True.
    """
    pdf_path = QUESTIONS_DIR / TEST_FILE_NAMES[test_num]
    if not pdf_path.exists():
        raise FileNotFoundError(f"Questions PDF not found: {pdf_path}")

    out_dir = OUTPUT_ASSETS_DIR / f"test{test_num}"
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))
    total = len(doc)
    rendered = 0
    skipped = 0
    page_map: Dict[int, Path] = {}

    logger.info("Test %d: rendering %d pages → %s", test_num, total, out_dir)
    t0 = time.time()

    for page_idx in range(total):
        page_num = page_idx + 1                               # 1-based
        out_path = out_dir / f"page_{page_num:03d}.png"
        page_map[page_num] = out_path

        if out_path.exists() and not force:
            skipped += 1
            continue

        pix = doc[page_idx].get_pixmap(matrix=MATRIX, alpha=False)
        pix.save(str(out_path))
        rendered += 1

    elapsed = time.time() - t0
    logger.info(
        "  rendered=%d  skipped=%d  time=%.1fs",
        rendered, skipped, elapsed,
    )
    return page_map


# ── Manifest building ───────────────────────────────────────────────────────────

def build_manifest(test_num: int) -> List[Dict]:
    """
    Read the extracted questions JSON and build an image manifest that
    lists every question with at least one asset reference.

    The manifest is keyed on question_id and records the page image path.
    """
    questions_path = QUESTIONS_RAW_DIR / f"test{test_num}_questions.json"
    if not questions_path.exists():
        raise FileNotFoundError(
            f"Questions JSON not found: {questions_path}\n"
            "Run extract_questions.py first."
        )

    questions: List[Dict] = json.loads(questions_path.read_text(encoding="utf-8"))

    manifest: List[Dict] = []
    for q in questions:
        if not q.get("assets"):
            continue
        manifest.append(
            {
                "question_id": q["id"],
                "test": q["test"],
                "section": q["section"],
                "module": q["module"],
                "question_number": q["question_number"],
                "page": q["page"],
                "assets": q["assets"],
            }
        )

    return manifest


# ── Page-level statistics ───────────────────────────────────────────────────────

def page_stats(test_num: int) -> None:
    """Print a summary of rendered pages and manifest entries."""
    out_dir = OUTPUT_ASSETS_DIR / f"test{test_num}"
    pngs = sorted(out_dir.glob("page_*.png"))

    manifest_path = QUESTIONS_RAW_DIR / f"test{test_num}_image_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        visual_count = len(manifest)
    else:
        visual_count = 0

    sizes_kb = [p.stat().st_size // 1024 for p in pngs]
    total_mb = sum(sizes_kb) / 1024

    print(f"\n─── Image Stats: Test {test_num} ─────────────────────────────────")
    print(f"  Pages rendered : {len(pngs)}")
    print(f"  Total size     : {total_mb:.1f} MB")
    if sizes_kb:
        print(f"  Min / Max / Avg: {min(sizes_kb)} / {max(sizes_kb)} / {sum(sizes_kb)//len(sizes_kb)} KB per page")
    print(f"  Manifest entries (visual Qs): {visual_count}")
    print("────────────────────────────────────────────────────────────\n")


# ── Top-level function ──────────────────────────────────────────────────────────

def process_test(test_num: int, force: bool = False) -> None:
    """Render pages and build manifest for one test."""
    # 1. Render pages
    render_test_pages(test_num, force=force)

    # 2. Build manifest from previously extracted questions
    try:
        manifest = build_manifest(test_num)
    except FileNotFoundError as exc:
        logger.warning("%s — skipping manifest", exc)
        manifest = []

    # 3. Save manifest
    manifest_path = QUESTIONS_RAW_DIR / f"test{test_num}_image_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Manifest: %d visual questions → %s", len(manifest), manifest_path)

    # 4. Report
    page_stats(test_num)


# ── CLI ─────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render SAT question PDF pages to PNG and build image manifests."
    )
    parser.add_argument("--test", type=int, choices=list(TEST_FILE_NAMES))
    parser.add_argument("--all", action="store_true")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-render even if PNG files already exist",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=RENDER_DPI,
        help="Render DPI (default: 150)",
    )
    args = parser.parse_args()

    if not args.test and not args.all:
        parser.error("Specify --test N or --all")

    # Allow overriding DPI at CLI
    global MATRIX
    if args.dpi != RENDER_DPI:
        MATRIX = fitz.Matrix(args.dpi / 72, args.dpi / 72)
        logger.info("Using DPI=%d", args.dpi)

    test_ids = list(TEST_FILE_NAMES) if args.all else [args.test]

    t_start = time.time()
    for test_num in test_ids:
        logger.info("═══ Test %d ════════════════════════════════════", test_num)
        try:
            process_test(test_num, force=args.force)
        except FileNotFoundError as exc:
            logger.error("%s — skipping", exc)

    total_elapsed = time.time() - t_start
    logger.info("Done. Total time: %.1fs", total_elapsed)


if __name__ == "__main__":
    main()
