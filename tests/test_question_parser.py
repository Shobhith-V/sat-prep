"""
Tests for the question extraction / parsing logic (extract_questions.py).

Run:  pytest tests/test_question_parser.py -v
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import extract_questions as eq
import utils


# ── parse_question_block ────────────────────────────────────────────────────

def test_parse_multiple_choice():
    blocks = [
        "The spacecraft made contact with the asteroid.",
        "Which choice completes the text?",
        "A) attached",
        "B) collected",
        "C) followed",
        "D) replaced",
    ]
    question, choices, qtype = eq.parse_question_block(blocks)
    assert qtype == "multiple_choice"
    assert choices == {"A": "attached", "B": "collected",
                       "C": "followed", "D": "replaced"}
    assert "spacecraft" in question
    assert "A)" not in question


def test_parse_numeric_response():
    blocks = [
        "A customer spent $27 to purchase oranges at $3 per pound.",
        "How many pounds of oranges did the customer purchase?",
    ]
    question, choices, qtype = eq.parse_question_block(blocks)
    assert qtype == "numeric_response"
    assert choices is None
    assert "oranges" in question


def test_parse_multiline_choice():
    """Choices that span multiple text blocks should be concatenated."""
    blocks = [
        "Which choice best states the main idea?",
        "A) Mary hides in the garden to avoid",
        "doing her chores.",
        "B) Mary is getting bored.",
        "C) Mary is clearing the garden.",
        "D) Mary feels satisfied.",
    ]
    _q, choices, qtype = eq.parse_question_block(blocks)
    assert qtype == "multiple_choice"
    assert choices["A"] == "Mary hides in the garden to avoid doing her chores."


def test_parse_inline_merged_choices():
    """Test-11 style: several choices merged into one block with ' | '."""
    blocks = [
        "Ezra Pound's poetry can be hard to comprehend.",
        "Which choice completes the text?",
        "A) comprehend",
        "B) dislike | C) interrupt | D) overlook",
    ]
    _q, choices, qtype = eq.parse_question_block(blocks)
    assert qtype == "multiple_choice"
    assert set(choices.keys()) == {"A", "B", "C", "D"}
    assert choices["C"] == "interrupt"


# ── OCR cleaning (utils.clean_text) ─────────────────────────────────────────

@pytest.mark.parametrize("raw,expected_substr", [
    ("25 percent sign", "25 %"),
    ("dollar sign 27", "$ 27"),
    ("the answer is blank here", "[BLANK]"),
])
def test_clean_text_substitutions(raw, expected_substr):
    assert expected_substr in utils.clean_text(raw)


def test_clean_text_strips_footer():
    raw = "Real content here.\nUnauthorized copying or reuse of any part of this page is illegal.\nCONTINUE"
    cleaned = utils.clean_text(raw)
    assert "Unauthorized copying" not in cleaned
    assert "Real content here." in cleaned


# ── Noise detection ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "---------~",
    "..............................",
    "No Test Material On This Page",
    "CONTINUE",
    "+++---+--+--i------",
])
def test_is_noise_block(text):
    assert utils.is_noise_block(text)


@pytest.mark.parametrize("text", [
    "The spacecraft made contact with the asteroid.",
    "A) attached",
    "Which choice completes the text?",
])
def test_is_not_noise_block(text):
    assert not utils.is_noise_block(text)


# ── Integration: full output JSON shape ─────────────────────────────────────

@pytest.fixture(scope="module")
def test4_questions():
    path = REPO_ROOT / "data" / "raw" / "test4_questions.json"
    if not path.exists():
        pytest.skip("run extract_questions.py --test 4 first")
    import json
    return json.loads(path.read_text())


def test_test4_question_count(test4_questions):
    assert len(test4_questions) == 120


def test_test4_module_structure(test4_questions):
    from collections import Counter
    counts = Counter((q["section"], q["module"]) for q in test4_questions)
    assert counts[("reading", 1)] == 33
    assert counts[("reading", 2)] == 33
    assert counts[("math", 1)] == 27
    assert counts[("math", 2)] == 27


def test_test4_ids_unique_and_formatted(test4_questions):
    import re
    ids = [q["id"] for q in test4_questions]
    assert len(ids) == len(set(ids))
    pattern = re.compile(r"^test4_(rw|math)_m[12]_q\d+$")
    assert all(pattern.match(i) for i in ids)


def test_test4_mc_have_four_choices(test4_questions):
    for q in test4_questions:
        if q["question_type"] == "multiple_choice" and q["choices"]:
            assert set(q["choices"].keys()) == {"A", "B", "C", "D"}
