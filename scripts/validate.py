"""
validate.py — End-to-end validation and metrics for the SAT extraction pipeline.

Usage:
    python validate.py            # validate all final output/test{N}.json files
    python validate.py --json     # emit machine-readable metrics to stdout as JSON

Checks performed
----------------
  1. Schema completeness   — every question has all 15 required fields
  2. Coverage              — questions / answers / explanations per test vs 120
  3. Cross-validation      — scoring-PDF answer == explanation "Choice X" answer
  4. Type consistency      — multiple_choice has choices; numeric_response does not
  5. Classification        — topic / subtopic / difficulty fully populated
  6. Asset integrity       — every referenced PNG exists on disk
  7. ID uniqueness & format

Exit code is non-zero if any hard check fails (useful for CI).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "output"

REQUIRED_FIELDS = [
    "id", "test", "section", "module", "question_number",
    "topic", "subtopic", "difficulty", "question_type",
    "question", "choices", "correct_answer", "explanation", "page", "assets",
]

RW_TOPICS = {
    "words_in_context", "central_ideas", "command_of_evidence", "inferences",
    "text_structure", "rhetorical_synthesis", "transitions", "grammar",
    "boundaries", "form_structure_sense", "data_interpretation",
}
MATH_TOPICS = {
    "linear_equations", "systems", "quadratics", "functions", "exponents",
    "geometry", "circles", "trigonometry", "statistics", "probability",
    "data_interpretation",
}

_ID_RE = re.compile(r"^test\d+_(rw|math)_m[12]_q\d+$")
_CHOICE_RE = re.compile(r"\s*Choice\s+([A-D])\s+is")


def validate_test(test_num: int) -> Dict:
    """Run all checks for one test and return a metrics dict."""
    path = OUTPUT_DIR / f"test{test_num}.json"
    metrics: Dict = {
        "test": test_num,
        "exists": path.exists(),
        "errors": [],
        "warnings": [],
    }
    if not path.exists():
        metrics["errors"].append(f"output/test{test_num}.json not found")
        return metrics

    data: List[Dict] = json.loads(path.read_text(encoding="utf-8"))
    n = len(data)
    metrics["question_count"] = n

    # Counters
    schema_ok = ids = unique_ids = 0
    mc = nr = mc_with_choices = nr_with_choices = 0
    topic_ok = subtopic_ok = difficulty_ok = 0
    answer_present = expl_present = 0
    xval_match = xval_total = 0
    asset_refs = asset_missing = 0
    seen_ids = set()

    for q in data:
        # 1. Schema completeness
        if all(f in q for f in REQUIRED_FIELDS):
            schema_ok += 1
        else:
            missing = [f for f in REQUIRED_FIELDS if f not in q]
            metrics["errors"].append(f"{q.get('id','?')}: missing fields {missing}")

        # 7. ID format & uniqueness
        qid = q.get("id", "")
        if _ID_RE.match(qid):
            ids += 1
        else:
            metrics["warnings"].append(f"malformed id: {qid}")
        if qid not in seen_ids:
            unique_ids += 1
            seen_ids.add(qid)
        else:
            metrics["errors"].append(f"duplicate id: {qid}")

        # 4. Type consistency
        qtype = q.get("question_type")
        if qtype == "multiple_choice":
            mc += 1
            if q.get("choices"):
                mc_with_choices += 1
        elif qtype == "numeric_response":
            nr += 1
            if q.get("choices"):
                nr_with_choices += 1

        # 5. Classification completeness + section consistency
        topic = q.get("topic")
        if topic:
            topic_ok += 1
            section = q.get("section")
            if section == "reading" and topic not in RW_TOPICS:
                metrics["errors"].append(f"{qid}: RW question has non-RW topic '{topic}'")
            if section == "math" and topic not in MATH_TOPICS:
                metrics["errors"].append(f"{qid}: math question has non-math topic '{topic}'")
        if q.get("subtopic"):
            subtopic_ok += 1
        if q.get("difficulty") in ("easy", "medium", "hard"):
            difficulty_ok += 1

        # 2. Coverage
        if q.get("correct_answer") is not None:
            answer_present += 1
        if q.get("explanation"):
            expl_present += 1

        # 3. Cross-validation: answer key vs explanation
        ca = q.get("correct_answer")
        if qtype == "multiple_choice" and isinstance(ca, str):
            m = _CHOICE_RE.match(q.get("explanation") or "")
            if m:
                xval_total += 1
                if m.group(1) == ca:
                    xval_match += 1
                else:
                    metrics["errors"].append(
                        f"{qid}: answer key={ca} but explanation says {m.group(1)}"
                    )

        # 6. Asset integrity
        for asset in q.get("assets", []):
            asset_refs += 1
            src = asset.get("src", "")
            asset_path = OUTPUT_DIR / src
            if not asset_path.exists():
                asset_missing += 1
                metrics["errors"].append(f"{qid}: missing asset {src}")

    metrics.update({
        "schema_ok": schema_ok,
        "id_format_ok": ids,
        "unique_ids": unique_ids,
        "multiple_choice": mc,
        "numeric_response": nr,
        "mc_with_choices": mc_with_choices,
        "nr_with_choices": nr_with_choices,
        "topic_classified": topic_ok,
        "subtopic_classified": subtopic_ok,
        "difficulty_classified": difficulty_ok,
        "answer_present": answer_present,
        "explanation_present": expl_present,
        "xval_match": xval_match,
        "xval_total": xval_total,
        "asset_refs": asset_refs,
        "asset_missing": asset_missing,
    })
    return metrics


def print_report(all_metrics: List[Dict]) -> bool:
    """Pretty-print the validation report. Returns True if all hard checks pass."""
    print(f"\n{'═'*72}")
    print(" SAT Pipeline — Final Validation Report")
    print(f"{'═'*72}")

    header = (f" {'Test':>4} {'Qs':>4} {'Schema':>7} {'Ans':>4} {'Expl':>5} "
              f"{'Topic':>6} {'Diff':>5} {'XVal':>9} {'Assets':>8}")
    print(header)
    print(f" {'─'*68}")

    tot = {k: 0 for k in [
        "question_count", "schema_ok", "answer_present", "explanation_present",
        "topic_classified", "difficulty_classified", "xval_match", "xval_total",
        "asset_refs", "asset_missing",
    ]}
    all_errors: List[str] = []

    for m in all_metrics:
        if not m.get("exists"):
            print(f" {m['test']:>4}  MISSING OUTPUT FILE")
            all_errors.extend(m["errors"])
            continue
        n = m["question_count"]
        xval = f"{m['xval_match']}/{m['xval_total']}"
        assets = f"{m['asset_refs']-m['asset_missing']}/{m['asset_refs']}"
        print(f" {m['test']:>4} {n:>4} {m['schema_ok']:>7} {m['answer_present']:>4} "
              f"{m['explanation_present']:>5} {m['topic_classified']:>6} "
              f"{m['difficulty_classified']:>5} {xval:>9} {assets:>8}")
        for k in tot:
            tot[k] += m.get(k, 0)
        all_errors.extend(m["errors"])

    print(f" {'─'*68}")
    print(f" {'ALL':>4} {tot['question_count']:>4} {tot['schema_ok']:>7} "
          f"{tot['answer_present']:>4} {tot['explanation_present']:>5} "
          f"{tot['topic_classified']:>6} {tot['difficulty_classified']:>5} "
          f"{str(tot['xval_match'])+'/'+str(tot['xval_total']):>9} "
          f"{str(tot['asset_refs']-tot['asset_missing'])+'/'+str(tot['asset_refs']):>8}")

    # Summary metrics
    n = tot["question_count"]
    print(f"\n Coverage summary ({n} questions extracted of 960 possible = {n/960*100:.1f}%):")
    print(f"   Schema complete      : {tot['schema_ok']}/{n} ({tot['schema_ok']/n*100:.1f}%)")
    print(f"   Has correct answer   : {tot['answer_present']}/{n} ({tot['answer_present']/n*100:.1f}%)")
    print(f"   Has explanation      : {tot['explanation_present']}/{n} ({tot['explanation_present']/n*100:.1f}%)")
    print(f"   Topic classified     : {tot['topic_classified']}/{n} ({tot['topic_classified']/n*100:.1f}%)")
    print(f"   Difficulty assigned  : {tot['difficulty_classified']}/{n} ({tot['difficulty_classified']/n*100:.1f}%)")
    if tot["xval_total"]:
        print(f"   Answer cross-val     : {tot['xval_match']}/{tot['xval_total']} "
              f"({tot['xval_match']/tot['xval_total']*100:.2f}% agreement)")
    print(f"   Asset files present  : {tot['asset_refs']-tot['asset_missing']}/{tot['asset_refs']}")

    if all_errors:
        print(f"\n ⚠  {len(all_errors)} hard error(s):")
        for e in all_errors[:25]:
            print(f"    ✗ {e}")
        if len(all_errors) > 25:
            print(f"    ... and {len(all_errors)-25} more")
    else:
        print("\n ✓ All hard checks passed — no errors.")

    print(f"{'═'*72}\n")
    return len(all_errors) == 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the SAT pipeline output.")
    parser.add_argument("--json", action="store_true", help="Emit metrics as JSON")
    args = parser.parse_args()

    all_metrics = [validate_test(t) for t in range(4, 12)]

    if args.json:
        print(json.dumps(all_metrics, indent=2))
        ok = all(not m["errors"] for m in all_metrics)
    else:
        ok = print_report(all_metrics)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
