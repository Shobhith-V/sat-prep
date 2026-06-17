"""
run_pipeline.py — Orchestrate the full SAT extraction pipeline end-to-end.

Usage:
    python run_pipeline.py                 # run all phases for all tests (4-11)
    python run_pipeline.py --test 4        # single test
    python run_pipeline.py --skip-images   # skip the slow page-render step
    python run_pipeline.py --use-llm       # use LLM fallback in topic classification

Phases (in order):
    1. extract_questions      → data/raw/test{N}_questions.json
    2. extract_answers        → data/raw/test{N}_answers.json
    3. extract_explanations   → data/raw/test{N}_explanations.json
    4. extract_images         → output/assets/test{N}/*.png + manifest
    5. merge                  → output/test{N}.json
    6. topic_classifier       → adds topic / subtopic
    7. difficulty_classifier  → adds difficulty
    8. validate               → final metrics report

Each phase is a separate module invoked in-process so a failure halts the run
with a clear message.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import extract_questions
import extract_answers
import extract_explanations
import extract_images
import merge
import topic_classifier
import difficulty_classifier
import validate

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)


def run(test_ids, skip_images: bool, use_llm: bool) -> None:
    t_start = time.time()

    for test_num in test_ids:
        logger.info("╔══ TEST %d ════════════════════════════════════════════", test_num)

        # Phase 1-3: text extraction
        logger.info("Phase 1/8: extracting questions…")
        questions = extract_questions.extract_all_modules(test_num)
        out = extract_questions.OUTPUT_DIR
        out.mkdir(parents=True, exist_ok=True)
        (out / f"test{test_num}_questions.json").write_text(
            __import__("json").dumps(questions, indent=2, ensure_ascii=False),
            encoding="utf-8")

        logger.info("Phase 2/8: extracting answers…")
        answers = extract_answers.extract_answers(test_num)
        (out / f"test{test_num}_answers.json").write_text(
            __import__("json").dumps(answers, indent=2, ensure_ascii=False),
            encoding="utf-8")

        logger.info("Phase 3/8: extracting explanations…")
        expl = extract_explanations.extract_explanations(test_num)
        (out / f"test{test_num}_explanations.json").write_text(
            __import__("json").dumps(expl, indent=2, ensure_ascii=False),
            encoding="utf-8")

        # Phase 4: images
        if skip_images:
            logger.info("Phase 4/8: SKIPPED (--skip-images)")
        else:
            logger.info("Phase 4/8: rendering images…")
            extract_images.process_test(test_num, force=False)

        # Phase 5: merge
        logger.info("Phase 5/8: merging…")
        merged = merge.merge_test(test_num)
        merge.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        (merge.OUTPUT_DIR / f"test{test_num}.json").write_text(
            __import__("json").dumps(merged, indent=2, ensure_ascii=False),
            encoding="utf-8")

        # Phase 6: topic classification
        logger.info("Phase 6/8: classifying topics…")
        classified = topic_classifier.classify_test(test_num, use_llm=use_llm)
        (topic_classifier.OUTPUT_DIR / f"test{test_num}.json").write_text(
            __import__("json").dumps(classified, indent=2, ensure_ascii=False),
            encoding="utf-8")

        # Phase 7: difficulty
        logger.info("Phase 7/8: assigning difficulty…")
        with_diff = difficulty_classifier.classify_test(test_num)
        (difficulty_classifier.OUTPUT_DIR / f"test{test_num}.json").write_text(
            __import__("json").dumps(with_diff, indent=2, ensure_ascii=False),
            encoding="utf-8")

    # Phase 8: validation across all processed tests
    logger.info("Phase 8/8: validating…")
    metrics = [validate.validate_test(t) for t in test_ids]
    ok = validate.print_report(metrics)

    logger.info("Pipeline finished in %.1fs — %s",
                time.time() - t_start, "OK" if ok else "ERRORS FOUND")
    if not ok:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full SAT extraction pipeline.")
    parser.add_argument("--test", type=int, choices=range(4, 12))
    parser.add_argument("--skip-images", action="store_true",
                        help="Skip the page-render step (faster re-runs)")
    parser.add_argument("--use-llm", action="store_true",
                        help="Use LLM fallback in topic classification")
    args = parser.parse_args()

    test_ids = [args.test] if args.test else list(range(4, 12))
    run(test_ids, skip_images=args.skip_images, use_llm=args.use_llm)


if __name__ == "__main__":
    main()
