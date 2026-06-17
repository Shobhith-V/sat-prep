"""
Tests for topic and difficulty classification.

Run:  pytest tests/test_classifier.py -v
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import topic_classifier as tc
import difficulty_classifier as dc


# ── Topic classification (unit) ─────────────────────────────────────────────

def _rw(question, explanation="", choices=None):
    return {
        "section": "reading", "question": question,
        "explanation": explanation, "choices": choices, "id": "x",
    }


def _math(question, explanation=""):
    return {
        "section": "math", "question": question,
        "explanation": explanation, "choices": None, "id": "x",
    }


def test_words_in_context():
    q = _rw("The scientist made a discovery.\n"
            "Which choice completes the text with the most logical and precise word or phrase?",
            choices={"A": "x", "B": "y", "C": "z", "D": "w"})
    assert tc.classify_question(q)[0] == "words_in_context"


def test_transitions():
    q = _rw("The volcano is large.\nWhich choice completes the text with the most logical transition?",
            choices={"A": "However,", "B": "Thus,", "C": "Finally,", "D": "Also,"})
    assert tc.classify_question(q)[0] == "transitions"


def test_grammar_from_explanation():
    q = _rw("The triangle blank among the figures.\n"
            "Which choice completes the text so that it conforms to the conventions of Standard English?",
            explanation="Choice D is the best answer. The convention being tested is "
                        "subject-verb agreement. The singular verb agrees with the subject.",
            choices={"A": "are", "B": "have been", "C": "were", "D": "is"})
    topic, sub = tc.classify_question(q)
    assert topic == "grammar"
    assert sub == "verb_agreement"


def test_boundaries():
    q = _rw("Some text here.\nWhich choice conforms to the conventions of Standard English?",
            explanation="Choice B is the best answer. The convention being tested is "
                        "punctuation use between sentences. These are two independent clauses.",
            choices={"A": "a,", "B": "a;", "C": "a", "D": "a:"})
    assert tc.classify_question(q)[0] == "boundaries"


def test_inferences():
    q = _rw("The data shows a trend. Therefore, the researchers concluded blank\n"
            "Which choice most logically completes the text?",
            explanation="Choice A presents the conclusion that most logically completes the text.",
            choices={"A": "w", "B": "x", "C": "y", "D": "z"})
    assert tc.classify_question(q)[0] == "inferences"


def test_rhetorical_synthesis():
    q = _rw("While researching a topic, a student has taken the following notes:\n"
            "- fact one\n- fact two\nWhich choice accomplishes this goal?",
            choices={"A": "w", "B": "x", "C": "y", "D": "z"})
    assert tc.classify_question(q)[0] == "rhetorical_synthesis"


def test_math_trigonometry():
    q = _math("In triangle JKL, cos(K) = 24/51 and angle J is a right angle. "
              "What is the value of cos(L)?")
    assert tc.classify_question(q)[0] == "trigonometry"


def test_math_circles():
    q = _math("The equation x^2 + (y-1)^2 = 49 represents circle A. "
              "Which equation represents circle B?")
    assert tc.classify_question(q)[0] == "circles"


def test_math_quadratics_factored():
    q = _math("f(x) = (x - 10)(x + 13). For what value of x does f(x) reach its minimum?",
              explanation="Choice C is correct. The given function is a parabola.")
    assert tc.classify_question(q)[0] == "quadratics"


def test_math_statistics_sampling():
    q = _math("A random sample was selected. The estimated proportion of the population "
              "is 0.49 with a margin of error of 0.04.")
    topic, sub = tc.classify_question(q)
    assert topic == "statistics"
    assert sub == "sampling"


# ── Difficulty scoring (unit) ───────────────────────────────────────────────

def test_difficulty_score_increases_with_position():
    early = {"section": "math", "question_number": 1, "explanation": "x" * 300,
             "question": "q", "topic": "linear_equations", "correct_answer": "A",
             "question_type": "multiple_choice"}
    late = {"section": "math", "question_number": 27, "explanation": "x" * 300,
            "question": "q", "topic": "linear_equations", "correct_answer": "A",
            "question_type": "multiple_choice"}
    assert dc._raw_score(late) > dc._raw_score(early)


def test_difficulty_score_increases_with_explanation_length():
    short = {"section": "reading", "question_number": 5, "explanation": "x" * 500,
             "question": "q" * 400, "topic": "central_ideas"}
    long = {"section": "reading", "question_number": 5, "explanation": "x" * 2500,
            "question": "q" * 400, "topic": "central_ideas"}
    assert dc._raw_score(long) > dc._raw_score(short)


def test_tercile_assignment_balanced():
    # 9 questions with ascending scores → 3 easy, 3 medium, 3 hard
    qs = [{"difficulty": None} for _ in range(9)]
    scored = [(q, float(i)) for i, q in enumerate(qs)]
    dc._assign_terciles(scored)
    diffs = [q["difficulty"] for q in qs]
    assert diffs.count("easy") == 3
    assert diffs.count("medium") == 3
    assert diffs.count("hard") == 3
    # ascending score → easy first, hard last
    assert qs[0]["difficulty"] == "easy"
    assert qs[-1]["difficulty"] == "hard"


# ── Integration: final classified output ────────────────────────────────────

@pytest.fixture(scope="module")
def test4_final():
    path = REPO_ROOT / "output" / "test4.json"
    if not path.exists():
        pytest.skip("run the full pipeline for test 4 first")
    return json.loads(path.read_text())


def test_all_classified(test4_final):
    for q in test4_final:
        assert q["topic"], f"{q['id']} missing topic"
        assert q["subtopic"], f"{q['id']} missing subtopic"
        assert q["difficulty"] in ("easy", "medium", "hard"), f"{q['id']} bad difficulty"


def test_section_topic_consistency(test4_final):
    rw = tc._classify_rw  # noqa: F841 (ensure import path valid)
    RW = {"words_in_context", "central_ideas", "command_of_evidence", "inferences",
          "text_structure", "rhetorical_synthesis", "transitions", "grammar",
          "boundaries", "form_structure_sense", "data_interpretation"}
    MATH = {"linear_equations", "systems", "quadratics", "functions", "exponents",
            "geometry", "circles", "trigonometry", "statistics", "probability",
            "data_interpretation"}
    for q in test4_final:
        if q["section"] == "reading":
            assert q["topic"] in RW
        else:
            assert q["topic"] in MATH


def test_difficulty_distribution_balanced(test4_final):
    from collections import Counter
    c = Counter(q["difficulty"] for q in test4_final)
    # roughly balanced terciles (allow some slack)
    assert abs(c["easy"] - c["hard"]) <= 3
