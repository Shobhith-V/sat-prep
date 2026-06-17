"""
Tests for answer + explanation extraction (extract_answers.py, extract_explanations.py).

Run:  pytest tests/test_explanation_parser.py -v
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import extract_answers as ea


# ── Answer normalisation ────────────────────────────────────────────────────

def test_parse_answer_block_basic():
    block = "\nCORRECT\n1\nB\n2\nA\n3\nD\n"
    answers = ea.parse_answer_block(block, max_q=33)
    assert answers["1"] == "B"
    assert answers["2"] == "A"
    assert answers["3"] == "D"


def test_parse_answer_block_numeric():
    block = "\n6\n9\n7\n10\n13\n1/5; .2\n"
    answers = ea.parse_answer_block(block, max_q=27)
    assert answers["6"] == "9"
    assert answers["7"] == "10"
    assert answers["13"] == "1/5; .2"


def test_parse_answer_block_inline_multivalue():
    """Q# and multi-value answer on the same line."""
    block = "\n21 361/8; 45.12; 45.13\n22\nB\n"
    answers = ea.parse_answer_block(block, max_q=27)
    assert answers["21"] == "361/8; 45.12; 45.13"
    assert answers["22"] == "B"


# ── Multi-value normalisation in merge ──────────────────────────────────────

def test_merge_normalise_answer():
    import merge
    assert merge.normalise_answer("B") == "B"
    assert merge.normalise_answer("9") == "9"
    assert merge.normalise_answer("1/5; .2") == ["1/5", ".2"]
    assert merge.normalise_answer("15; -5") == ["15", "-5"]


# ── Explanation cleaning ────────────────────────────────────────────────────

def test_explanation_clean_strips_section_marker():
    import extract_explanations as ee
    raw = "Choice B is the best answer because it is correct.\nn\n"
    cleaned = ee._clean_explanation(raw)
    assert cleaned.endswith("correct.")
    assert not cleaned.endswith("\nn")


# ── Integration: answers file ───────────────────────────────────────────────

@pytest.fixture(scope="module")
def test4_answers():
    path = REPO_ROOT / "data" / "raw" / "test4_answers.json"
    if not path.exists():
        pytest.skip("run extract_answers.py --test 4 first")
    return json.loads(path.read_text())


def test_answers_complete(test4_answers):
    assert len(test4_answers["reading_m1"]) == 33
    assert len(test4_answers["reading_m2"]) == 33
    assert len(test4_answers["math_m1"]) == 27
    assert len(test4_answers["math_m2"]) == 27


def test_answers_known_values(test4_answers):
    # Verified against the test-4 scoring PDF
    assert test4_answers["reading_m1"]["1"] == "B"
    assert test4_answers["math_m1"]["6"] == "9"
    assert test4_answers["math_m2"]["27"] == "600"


# ── Integration: explanations file ──────────────────────────────────────────

@pytest.fixture(scope="module")
def test4_explanations():
    path = REPO_ROOT / "data" / "raw" / "test4_explanations.json"
    if not path.exists():
        pytest.skip("run extract_explanations.py --test 4 first")
    return json.loads(path.read_text())


def test_explanations_complete(test4_explanations):
    for key in ("reading_m1", "reading_m2", "math_m1", "math_m2"):
        expected = 33 if key.startswith("reading") else 27
        assert len(test4_explanations[key]) == expected


def test_explanations_nonempty(test4_explanations):
    for key, mod in test4_explanations.items():
        if key == "test":
            continue
        for q, text in mod.items():
            assert len(text) > 30, f"{key} Q{q} explanation too short"


def test_explanation_starts_with_choice(test4_explanations):
    """RW MC explanations begin with 'Choice X is …'."""
    expl = test4_explanations["reading_m1"]["1"]
    assert expl.lstrip().startswith("Choice")


# ── Cross-validation: answer key vs explanation ─────────────────────────────

def test_answer_matches_explanation(test4_answers, test4_explanations):
    """The scoring-PDF answer must match the explanation's 'Choice X' for MC."""
    import re
    for mk in ("reading_m1", "reading_m2"):
        for q, ans in test4_answers[mk].items():
            if ans not in "ABCD":
                continue
            expl = test4_explanations[mk][q]
            m = re.match(r"\s*Choice\s+([A-D])\s+is", expl)
            if m:
                assert m.group(1) == ans, f"{mk} Q{q}: key={ans} expl={m.group(1)}"
