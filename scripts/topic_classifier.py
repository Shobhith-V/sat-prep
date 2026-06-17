"""
topic_classifier.py — Assign topic and subtopic to every extracted SAT question.

Usage:
    python topic_classifier.py --test 4
    python topic_classifier.py --all
    python topic_classifier.py --all --report        # detailed report only, no file write
    python topic_classifier.py --all --use-llm       # LLM fallback for unclassified Qs

Input / output: output/test{N}.json  (reads and rewrites in place)

Design
------
Two-stage pipeline:

  Stage 1 — Rule-based (covers ~95% of questions)
    Reading & Writing: pattern match on question stem (last sentence before choices)
                       and explanation opening phrase.
    Math:              keyword scoring on full question + explanation text.

  Stage 2 — LLM fallback  (optional, --use-llm flag)
    Sends unclassified questions to Claude API with the full taxonomy.
    Results are cached per question_id.

The classifier is idempotent: re-running it overwrites previous classifications.
Questions that cannot be classified retain topic=null, subtopic=null.

Topic taxonomy
--------------
READING & WRITING
  words_in_context          vocabulary_in_context | precise_word_choice
  central_ideas             main_idea | purpose
  command_of_evidence       textual_evidence | quotation_support | graph_analysis | table_analysis
  inferences                inference | logical_completion
  text_structure            function_of_sentence | overall_structure
  rhetorical_synthesis      student_notes | synthesis
  transitions               logical_transition
  grammar                   punctuation | verb_agreement | verb_tense | sentence_boundaries | modifiers
  boundaries                sentence_boundaries | run_on
  form_structure_sense      modifier_placement | subordination | coordination
  data_interpretation       graph_analysis | table_analysis

MATH
  linear_equations          one_variable | two_variable | word_problems | inequalities
  systems                   substitution | elimination | word_problems
  quadratics                factoring | vertex_form | roots | standard_form
  functions                 function_notation | interpretation | transformations | linear_function
  exponents                 exponential_growth | properties | percent
  geometry                  triangles | area | volume | coordinate_geometry | similar_figures
  circles                   arc_length | area | equations
  trigonometry              right_triangles | unit_circle
  statistics                mean | median | standard_deviation | distributions | sampling
  probability               simple_probability | conditional_probability
  data_interpretation       graph_analysis | table_analysis | scatterplot
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "output"

sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _stem(question_text: str) -> str:
    """Return the last non-empty line of the question text (the prompt sentence)."""
    lines = [ln.strip() for ln in (question_text or "").split("\n") if ln.strip()]
    return lines[-1].lower() if lines else ""


def _expl(explanation: str, chars: int = 400) -> str:
    """Return lowercased explanation excerpt."""
    return (explanation or "").lower()[:chars]


def _qtext(question: str) -> str:
    """Return full question text as a single lowercased, whitespace-normalised string."""
    return re.sub(r"\s+", " ", (question or "")).lower()


def _choices_text(choices: Optional[Dict]) -> str:
    if not choices:
        return ""
    return " ".join(choices.values()).lower()


# ── Reading & Writing classifier ───────────────────────────────────────────────

def _classify_rw(q: Dict) -> Tuple[Optional[str], Optional[str]]:
    st   = _stem(q.get("question", ""))
    qt   = _qtext(q.get("question", ""))
    ex   = _expl(q.get("explanation", ""))
    ch   = _choices_text(q.get("choices"))

    # ── 1. Rhetorical synthesis / student notes ────────────────────────────────
    # qt is whitespace-normalised so newlines inside "taken the\nfollowing" are handled
    if "student has taken the following notes" in qt or "accomplish this goal" in qt:
        return "rhetorical_synthesis", "student_notes"

    # ── 2. Words in context ────────────────────────────────────────────────────
    if ("most logical and precise word or phrase" in st
            or "logical and precise word or phrase" in st
            or "most nearly mean" in st
            or "nearly mean" in st
            or "as used in the text" in st
            or "most nearly mean" in ex[:60]):
        return "words_in_context", "vocabulary_in_context"

    # ── 3. Transitions ─────────────────────────────────────────────────────────
    # Match "logical transition" with or without "most" — the stem extraction
    # may capture only the tail of a multi-line sentence
    if "logical transition" in st:
        return "transitions", "logical_transition"
    # Choices that are discourse markers (start with capital + comma)
    if re.search(r"\b(however|therefore|additionally|instead|likewise|"
                 r"consequently|similarly|finally|conversely|thus|"
                 r"furthermore|nevertheless|accordingly)\s*,", ch):
        # Only if the stem is about completing text
        if "completes the text" in st or "transition" in st:
            return "transitions", "logical_transition"

    # ── 4. Standard English (grammar) ─────────────────────────────────────────
    if "conventions of standard english" in st:
        return _classify_grammar(ex, qt, ch)

    # ── 5. Data interpretation (explicit chart/table reference) ───────────────
    if ("most effectively uses data from the" in st
            or "effectively uses data from the" in st
            or "from the graph to complete" in st
            or "from the table to complete" in st
            or "from the graph to illustrate" in st
            or "from the table to illustrate" in st
            or st.endswith("graph to complete the text?")
            or st.endswith("graph to complete the sentence?")
            or st.endswith("table to complete the statement?")
            or st.endswith("graph to complete the statement?")
            or st.endswith("statement?")):
        sub = "table_analysis" if "table" in st else "graph_analysis"
        return "data_interpretation", sub

    # ── 6. Command of evidence ─────────────────────────────────────────────────
    # Check both the last-line stem (st) and the full normalised text (qt)
    # because "if true" may appear on a different line than the stem
    _coe_qt = ("most directly support" in qt
               or "if true, would" in qt
               or "most likely respond" in qt
               or "based on the texts" in qt
               or ("text 1" in qt and "text 2" in qt))
    _coe_st = ("illustrates the claim" in st
               or "effectively illustrates the claim" in st
               or "best supports" in st
               or "support the student" in st
               or "support the researcher" in st
               or ("support" in st and ("hypothesis" in st or "conclusion" in st))
               or "would most strongly support" in st
               or "would most directly support" in st
               or "the underlined claim" in st)
    # Also catch short stems like "the researchers' hypothesis?" by checking qt
    _coe_qt2 = (("hypothesis" in qt or "conclusion" in qt)
                and re.search(r"\bsupport|directly\b|if true", qt))

    if _coe_qt or _coe_st or _coe_qt2:
        sub = _coe_subtopic(st, qt, ex)
        return "command_of_evidence", sub

    # ── 7. Inferences ("most logically completes the text") ───────────────────
    # Checked BEFORE the central-ideas endswith("text?") branch because the
    # inference stem "which choice most logically completes the text?" would
    # otherwise be greedily swallowed as a central-ideas question.
    if ("most logically completes the text" in st
            or "most logically completes" in st
            or "logically completes the text" in ex[:200]
            or "logically follows from" in ex[:200]
            or "presents the conclusion that most logically" in ex[:200]):
        return "inferences", "logical_completion"

    # ── 8. Central ideas ───────────────────────────────────────────────────────
    if ("main idea" in st or "main purpose" in st
            or "best states the main" in st
            or "main idea" in ex[:80] or "main purpose" in ex[:80]):
        sub = "purpose" if "purpose" in st or "purpose" in ex[:80] else "main_idea"
        return "central_ideas", sub

    if st.endswith("text?") or st.endswith("happening in the text?"):
        # Short stems that end with just "text?" — explanation reveals topic
        if "main purpose" in ex or "main idea" in ex:
            return "central_ideas", "purpose" if "purpose" in ex[:120] else "main_idea"
        if "overall structure" in ex or "structure of the text" in ex:
            return "text_structure", "overall_structure"
        if "function" in ex[:120]:
            return "text_structure", "function_of_sentence"
        # Default for ambiguous short stems
        return "central_ideas", "main_idea"

    # ── 8. Text structure ─────────────────────────────────────────────────────
    if ("overall structure" in st
            or "best describes the overall" in st
            or "underlined sentence in the text as a whole" in st
            or "underlined portion in the text as a whole" in st
            or "underlined portion of the text" in st
            or "underlined phrase in the text" in st
            or "underlined statement in the text" in st
            or "function of the underlined" in st
            or ("function of the" in st and ("sentence" in st or "portion" in st))):
        sub = "overall_structure" if "overall structure" in st else "function_of_sentence"
        return "text_structure", sub

    if st.endswith("the text?") or st.endswith("sentence?") or st.endswith("portion?"):
        if "overall structure" in ex:
            return "text_structure", "overall_structure"
        if "function" in ex[:120] or "role" in ex[:80]:
            return "text_structure", "function_of_sentence"
        if "main idea" in ex or "main purpose" in ex:
            return "central_ideas", "main_idea"

    # ── 9. Inferences ("most logically completes") ────────────────────────────
    if "most logically completes" in st or "most logically" in st:
        return "inferences", "logical_completion"

    # ── 10. Words-in-context: bullet-point choice stems ───────────────────────
    # When OCR extracts an answer choice (e.g. "• similar to") as the last line
    if st.startswith("•") or st.startswith("-") and len(st) < 30:
        # Explanation signal: discussion/context → words_in_context
        if "discussion" in ex[:200] or "context" in ex[:150]:
            return "words_in_context", "vocabulary_in_context"

    # ── 11. Broader central-ideas catch ───────────────────────────────────────
    # Short "about X?" / "for which reason?" stems with explanation confirming
    # a statement, information, or description about the passage
    if re.search(r"presents a statement about|presents information about"
                 r"|most accurately states|most accurately describes what"
                 r"|accurately describes (why|how|what)", ex[:250]):
        return "central_ideas", "main_idea"

    # ── 12. Broader command-of-evidence catch ─────────────────────────────────
    if re.search(r"presents a finding that|most effectively uses a quotation"
                 r"|most strongly supports|directly supports the|best supports the"
                 r"|presents an outcome that|states a conclusion", ex[:250]):
        return "command_of_evidence", "textual_evidence"

    # ── 13. Broader data-interpretation catch ─────────────────────────────────
    if re.search(r"uses data from the|data in the (graph|table)"
                 r"|completes the example|accurately identifies the .*(with|in) the (graph|table)"
                 r"|states the (percentage|number|proportion|count)", ex[:250]):
        sub = "table_analysis" if "table" in ex[:200] else "graph_analysis"
        return "data_interpretation", sub

    # ── 14. Fallback from explanation ─────────────────────────────────────────
    result = _rw_from_explanation(ex)
    if result[0]:
        return result

    # ── 15. Last resort: any "describes/states ... <ProperNoun>" → central_ideas
    if re.search(r"\b(describes|states|presents|provides|explains)\b", ex[:200]):
        return "central_ideas", "main_idea"
    # "most logically completes" appearing only in explanation → inferences
    if "logically completes" in ex[:200] or "logically follows" in ex[:200]:
        return "inferences", "logical_completion"

    return None, None


def _classify_grammar(ex: str, qt: str, ch: str) -> Tuple[str, str]:
    """Determine grammar subtopic from explanation text."""
    # The explanation almost always contains:
    # "The convention being tested is [X]."
    conv_m = re.search(r"the convention being tested is (.{5,80})\.", ex)
    convention = conv_m.group(1) if conv_m else ""

    if "tense" in convention or "tense" in ex[:200]:
        return "grammar", "verb_tense"
    if ("subject-verb" in convention or "subject-verb" in ex
            or ("subject" in convention and "verb" in convention)
            or "singular subject" in ex or "plural subject" in ex
            or "noun agreement" in convention):
        return "grammar", "verb_agreement"
    if ("modifier" in convention or "modifier" in ex[:200]
            or "dangling" in ex or "misplaced" in ex
            or "subject-modifier" in convention):
        return "form_structure_sense", "modifier_placement"
    if ("independent clause" in ex or "run-on" in ex
            or "comma splice" in ex or "punctuation use between sentences" in convention
            or "between sentences" in convention or "two independent" in ex
            or "forms a complete sentence" in ex
            or "cannot be joined by a comma alone" in ex):
        return "boundaries", "sentence_boundaries"
    if ("subordinat" in convention or "coordinat" in convention
            or "conjunction" in convention):
        return "form_structure_sense", "subordination"
    if ("apostrophe" in ex or "possessive" in convention
            or "plural and possessive" in convention):
        return "grammar", "punctuation"
    if ("semicolon" in ex[:200] or "colon" in ex[:200]
            or "semicolon" in convention or "colon" in convention):
        return "grammar", "punctuation"
    if "comma" in ex[:200] or "comma" in convention:
        return "grammar", "punctuation"
    if "dash" in ex[:150] or "parenthetical" in ex[:150]:
        return "grammar", "punctuation"
    # Generic fallback
    return "grammar", "punctuation"


def _coe_subtopic(st: str, qt: str, ex: str) -> str:
    if "graph" in st or "graph" in ex[:200]:
        return "graph_analysis"
    if "table" in st or "table" in ex[:200]:
        return "table_analysis"
    if ("quotation" in ex[:200] or "quote" in ex[:200]
            or "illustrates the claim" in st or "best illustrates" in st):
        return "quotation_support"
    if "text 1" in qt and "text 2" in qt:
        return "textual_evidence"
    return "textual_evidence"


def _rw_from_explanation(ex: str) -> Tuple[Optional[str], Optional[str]]:
    """Last-resort classification using explanation text."""
    if "main idea" in ex[:200] or "main purpose" in ex[:200]:
        return "central_ideas", "main_idea"
    if "overall structure" in ex[:200]:
        return "text_structure", "overall_structure"
    if "function" in ex[:200] and ("sentence" in ex[:200] or "portion" in ex[:200]):
        return "text_structure", "function_of_sentence"
    if "transition" in ex[:200]:
        return "transitions", "logical_transition"
    if "data from the" in ex[:200] or "graph" in ex[:120] or "table" in ex[:120]:
        return "data_interpretation", "graph_analysis"
    if "quotation" in ex[:200] or "illustrate" in ex[:120]:
        return "command_of_evidence", "quotation_support"
    # Catch-all: a "presents a statement/description/information" explanation
    # is almost always a comprehension (central ideas) question
    if re.search(r"presents (a |an |information|the )|describes (a |how |why |what )"
                 r"|states (a |how |why |what |the )|provides (a |information|the )"
                 r"|explains (how|why|what)", ex[:250]):
        return "central_ideas", "main_idea"
    return None, None


# ── Math classifier ────────────────────────────────────────────────────────────

def _classify_math(q: Dict) -> Tuple[Optional[str], Optional[str]]:
    qt  = _qtext(q.get("question", ""))
    ex  = _expl(q.get("explanation", ""))
    combined = qt + " " + ex

    # ── Trigonometry (most specific) ──────────────────────────────────────────
    if re.search(r"\bcos\(|\bsin\(|\btan\(|\bcosine\b|\bsine\b|\btangent\b"
                 r"|\bradian|\btrigonometric", combined):
        return "trigonometry", "right_triangles"

    # ── Circles ───────────────────────────────────────────────────────────────
    if re.search(r"\bcircle\b|\barc\b.*\bdegree|\bdegree.*\barc\b|\bradius\b"
                 r"|\bdiameter\b|\bcircumference\b|\bcenter of a circle", combined):
        sub = "equations" if "equation" in combined and "circle" in combined else (
              "arc_length" if "arc" in combined else "area")
        return "circles", sub

    # ── Sampling / margin of error → statistics (check before probability) ────
    if re.search(r"\bmargin of error\b|\brandom sample\b|\bselected.*sample\b"
                 r"|\bestimate.*proportion\b|\bproportion.*population\b"
                 r"|\brepresentative sample\b|\bsurvey", combined):
        return "statistics", "sampling"

    # ── Probability & statistics (share keyword space, check probability first) ─
    if re.search(r"\bprobability\b|\bproportion\b.*\brandom|\brandomly selected\b"
                 r"|\blikelihood\b|\bat random\b", combined):
        sub = "conditional_probability" if ("given that" in combined or "conditional" in combined) \
              else "simple_probability"
        return "probability", sub

    if re.search(r"\bmean\b|\bmedian\b|\bmode\b|\bstandard deviation\b"
                 r"|\bdata set\b|\bdot plot\b|\brange of\b|\baverage\b"
                 r"|\bsampling\b|\bsurvey\b|\bpopulation\b|\bdistribution\b"
                 r"|\bhistogram\b|\bspread\b|\bvariability\b", combined):
        sub = _stats_subtopic(combined)
        return "statistics", sub

    # ── Geometry ──────────────────────────────────────────────────────────────
    if re.search(r"\btriangle\b|\bright triangle\b|\bhypotenuse\b|\bperimeter\b"
                 r"|\bsimilar.*triangle|\bcongruent\b|\bangle\b|\bparallel\b"
                 r"|\bperpendicular\b|\bpolygon\b|\bprism\b|\bcylinder\b"
                 r"|\bsphere\b|\bpyramid\b|\brectangle\b.*\barea\b"
                 r"|\bvolume\b|\bsurface area\b", combined):
        sub = _geometry_subtopic(combined)
        return "geometry", sub

    # ── Coordinate geometry (check before quadratics) ─────────────────────────
    if re.search(r"\bcoordinate\b|\bx.*y.plane\b|\bxy.plane\b|\bdistance\b"
                 r"|\bmidpoint\b", combined):
        # Might still be quadratic/function — keep going
        pass

    # ── Quadratics ────────────────────────────────────────────────────────────
    # Includes factored-form detection: a product of two binomials such as
    # "(x − 10)(x + 13)" or an explanation that mentions a parabola / vertex,
    # even when the question text superficially looks like a function (f(x)=…).
    factored_form = re.search(r"\([^)]*x[^)]*\)\s*\([^)]*x[^)]*\)", qt)
    quad_minimum = (("minimum" in combined or "maximum" in combined)
                    and ("parabola" in ex or factored_form))
    if (re.search(r"\bquadratic\b|\bparabola\b|\bvertex\b"
                  r"|\bx.intercept\b|\bzero(s)? of\b|\broot(s)? of\b"
                  r"|\bdiscriminant\b|\bcomplete the square\b"
                  r"|\bfactor(s|ed|ing)?\b.*\bequation\b|\bax.2\b"
                  r"|\bfactor of\b|\bhas a factor\b", combined)
            or factored_form or quad_minimum):
        sub = _quad_subtopic(combined)
        return "quadratics", sub

    # ── Exponential / percent ─────────────────────────────────────────────────
    if re.search(r"\bexponential\b|\bgrowth factor\b|\bdecay factor\b"
                 r"|\brational exponent\b|\bnth root\b|\b\d+th root\b"
                 r"|\bpercent greater\b|\bpercent less\b|\bp percent\b"
                 r"|\bgrowth rate\b|\bdecay rate\b", combined):
        sub = ("exponential_growth" if re.search(r"\bgrowth\b|\bdecay\b|\bfactor\b", combined)
               else "properties")
        return "exponents", sub

    # ── Functions ─────────────────────────────────────────────────────────────
    if re.search(r"\bfunction\b|\bf\s*\(|\bg\s*\(|\bh\s*\(|\bdomain\b|\brange\b"
                 r"|\bdefined by\b|\bdefines f\b|\bgraph of y\s*=", combined):
        sub = _func_subtopic(combined)
        return "functions", sub

    # ── Systems of equations ──────────────────────────────────────────────────
    if re.search(r"\bsystem of equations\b|\bsystem of linear\b"
                 r"|\bgiven system\b|\bsolution to the given system\b"
                 r"|\bsolutions.*system\b", combined):
        return "systems", "elimination"

    # Heuristic: two or more distinct equations (count "=" signs in question)
    eq_count = qt.count("=")
    if eq_count >= 2 and re.search(r"[a-z]\s*=\s*[a-z0-9]", qt):
        if "y =" in qt or "y=" in qt:
            return "systems", "substitution"

    # ── Algebraic simplification / "equivalent expression" ───────────────────
    if re.search(r"\bequivalent to\b", qt):
        if re.search(r"x\s*\^?\s*2|x2\b|\bx2\s*[-+]", qt):
            return "quadratics", "standard_form"
        if re.search(r"x\s*\^?\s*3|x3\b", qt):
            return "functions", "function_notation"
        return "linear_equations", "one_variable"

    # ── Linear equations ──────────────────────────────────────────────────────
    if re.search(r"\blinear\b|\bslope\b|\by.intercept\b|\brate\b.*\bper\b"
                 r"|\bproportion(al)?\b|\bequation\b|\bsolve for\b"
                 r"|\binequal(ity|ities)\b|\bno more than\b|\bat least\b"
                 r"|\bmaximum number\b|\bminimum\b.*\bvalue\b", combined):
        sub = _linear_subtopic(combined)
        return "linear_equations", sub

    # ── Data interpretation / visual ──────────────────────────────────────────
    if re.search(r"\bscatterplot\b|\bbar graph\b|\bline graph\b|\bgraph shows\b"
                 r"|\btable shows\b|\bdata.*table\b|\btable.*data\b", combined):
        sub = "scatterplot" if "scatter" in combined else "graph_analysis"
        return "data_interpretation", sub

    # ── Percentage (standalone) ────────────────────────────────────────────────
    if re.search(r"percent(age)?|%", combined):
        return "exponents", "percent"

    # ── Coordinate graph translation (bare "y" stem from rendered graph) ──────
    if re.search(r"translat|shifted|graph is moved|graph shown", combined):
        return "functions", "transformations"

    # ── Word problem catch-all ────────────────────────────────────────────────
    # Questions with physical quantities, purchases, rates, unit conversions
    if re.search(r"\bhow many\b|\bhow much\b|\bhow far\b|\bhow long\b"
                 r"|\bpurchase\b|\bbought\b|\bcost\b|\bearned?\b|\bpaid\b|\bbill\b"
                 r"|\btip\b|\bratio\b|\bmile[s]?\b|\byards?\b|\binche[s]?\b"
                 r"|\bfeet\b|\bfoot\b|\bhours?\b|\bdays?\b|\bweeks?\b|\bmonths?\b"
                 r"|\bvoted\b|\belection\b|\bmembers?\b|\bpeople\b|\bstudent[s]?\b"
                 r"|\bathlete|\bcoache?s\b|\brate\b", combined):
        sub = _linear_subtopic(combined)
        return "linear_equations", sub

    # ── Area / scale model (geometry word problems) ───────────────────────────
    if re.search(r"\barea\b|\bsquare (meter|centimeter|inch|foot|feet)"
                 r"|\bscale model\b|\bdimension|\brectangular\b|\blength\b.*\bwidth\b",
                 combined):
        return "geometry", "area"

    # ── Fallback ──────────────────────────────────────────────────────────────
    return None, None


def _stats_subtopic(text: str) -> str:
    if "standard deviation" in text:
        return "standard_deviation"
    if "median" in text:
        return "median"
    if "mean" in text or "average" in text:
        return "mean"
    if "margin of error" in text or "sample" in text or "population" in text:
        return "sampling"
    return "distributions"


def _quad_subtopic(text: str) -> str:
    if "vertex" in text or "minimum" in text or "maximum" in text:
        return "vertex_form"
    if re.search(r"\bx.intercept\b|\bzero\b|\broot\b", text):
        return "roots"
    if "factor" in text:
        return "factoring"
    return "standard_form"


def _func_subtopic(text: str) -> str:
    if "interpretation" in text or "best interpretation" in text or "context" in text:
        return "interpretation"
    if "transform" in text or "shift" in text or "translation" in text:
        return "transformations"
    if re.search(r"f\s*\(\s*0\s*\)|f\s*\(\s*\d", text):
        return "function_notation"
    if "linear function" in text or "slope" in text:
        return "linear_function"
    return "function_notation"


def _linear_subtopic(text: str) -> str:
    if re.search(r"\bno more than\b|\bno less than\b|\bat least\b|\bat most\b"
                 r"|\bmaximum\b|\bminimum\b|\binequal", text):
        return "inequalities"
    if re.search(r"\bslope\b|\by.intercept\b|\bpasses through\b|\blinear function\b", text):
        return "two_variable"
    if re.search(r"\bper\b|\bcost\b|\bprice\b|\bdeposit\b|\bpay\b|\bhour\b"
                 r"|\bmile\b|\bpound\b|\bbin\b|\bitem\b|\brate\b", text):
        return "word_problems"
    return "one_variable"


def _geometry_subtopic(text: str) -> str:
    if re.search(r"\bvolume\b|\bsurface area\b|\bcylinder\b|\bprism\b|\bsphere\b"
                 r"|\bpyramid\b", text):
        return "volume"
    if re.search(r"\bsimilar\b|\bcongruent\b|\bcorrespond\b", text):
        return "similar_figures"
    if re.search(r"\bcoordinate\b|\bxy.plane\b|\bx.*y.plane\b|\bdistance\b"
                 r"|\bmidpoint\b", text):
        return "coordinate_geometry"
    if re.search(r"\barea\b|\bperimeter\b", text):
        return "area"
    if re.search(r"\btriangle\b|\bangle\b|\bhypotenuse\b", text):
        return "triangles"
    return "triangles"


# ── LLM fallback ───────────────────────────────────────────────────────────────

_LLM_CACHE: Dict[str, Tuple[str, str]] = {}

_TAXONOMY_SUMMARY = """
Reading & Writing topics:
  words_in_context, central_ideas, command_of_evidence, inferences,
  text_structure, rhetorical_synthesis, transitions, grammar, boundaries,
  form_structure_sense, data_interpretation

Math topics:
  linear_equations, systems, quadratics, functions, exponents,
  geometry, circles, trigonometry, statistics, probability, data_interpretation

Return ONLY a JSON object: {"topic": "...", "subtopic": "..."}
"""


def _classify_with_llm(q: Dict) -> Tuple[Optional[str], Optional[str]]:
    """Call Claude API to classify a question that rules couldn't handle."""
    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic package not installed — cannot use LLM fallback")
        return None, None

    qid = q.get("id", "")
    if qid in _LLM_CACHE:
        return _LLM_CACHE[qid]

    client = anthropic.Anthropic()

    section = q.get("section", "")
    qtext = (q.get("question") or "")[:600]
    choices_text = ""
    if q.get("choices"):
        choices_text = "\n".join(f"{k}) {v}" for k, v in q["choices"].items())
    expl_snippet = (q.get("explanation") or "")[:200]

    prompt = f"""Classify this SAT {section} question into the taxonomy below.

Question:
{qtext}

Choices:
{choices_text}

Explanation excerpt:
{expl_snippet}

Taxonomy:
{_TAXONOMY_SUMMARY}
"""

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        parsed = json.loads(re.search(r"\{.*\}", raw, re.DOTALL).group())
        topic = parsed.get("topic")
        subtopic = parsed.get("subtopic")
        _LLM_CACHE[qid] = (topic, subtopic)
        return topic, subtopic
    except Exception as exc:
        logger.debug("LLM classification failed for %s: %s", qid, exc)
        return None, None


# ── Top-level classifier ────────────────────────────────────────────────────────

def classify_question(q: Dict, use_llm: bool = False) -> Tuple[Optional[str], Optional[str]]:
    """Classify one question. Returns (topic, subtopic)."""
    if q["section"] == "reading":
        topic, subtopic = _classify_rw(q)
    else:
        topic, subtopic = _classify_math(q)

    if topic is None and use_llm:
        topic, subtopic = _classify_with_llm(q)

    return topic, subtopic


def classify_test(test_num: int, use_llm: bool = False) -> List[Dict]:
    """Load, classify, and return all questions for one test."""
    path = OUTPUT_DIR / f"test{test_num}.json"
    if not path.exists():
        raise FileNotFoundError(f"Merged JSON not found: {path}\nRun merge.py first.")

    data: List[Dict] = json.loads(path.read_text(encoding="utf-8"))
    classified = unclassified = 0

    for q in data:
        topic, subtopic = classify_question(q, use_llm=use_llm)
        q["topic"] = topic
        q["subtopic"] = subtopic
        if topic:
            classified += 1
        else:
            unclassified += 1

    logger.info(
        "Test %d: classified=%d  unclassified=%d  (%.0f%%)",
        test_num, classified, unclassified,
        classified / len(data) * 100 if data else 0,
    )
    return data


# ── Reports ─────────────────────────────────────────────────────────────────────

def classification_report(all_data: List[Dict], test_nums: List[int]) -> None:
    from collections import Counter

    topic_counts: Counter = Counter()
    subtopic_counts: Counter = Counter()
    unclassified_ids: List[str] = []
    total = len(all_data)

    for q in all_data:
        t = q.get("topic")
        s = q.get("subtopic")
        if t:
            topic_counts[t] += 1
            subtopic_counts[f"{t}/{s}"] += 1
        else:
            unclassified_ids.append(q["id"])

    classified = total - len(unclassified_ids)
    print(f"\n{'═'*64}")
    print(f" Classification Report — Tests {test_nums}")
    print(f"{'═'*64}")
    print(f" Total questions : {total}")
    print(f" Classified      : {classified}  ({classified/total*100:.1f}%)")
    print(f" Unclassified    : {len(unclassified_ids)}")

    print(f"\n {'Topic':<28} {'Count':>6}  {'Subtopics'}")
    print(f" {'─'*60}")
    for topic, count in sorted(topic_counts.items(), key=lambda x: -x[1]):
        subs = [(k.split("/")[1], v) for k, v in subtopic_counts.items()
                if k.startswith(topic + "/")]
        sub_str = "  ".join(f"{s}={c}" for s, c in sorted(subs, key=lambda x: -x[1])[:4])
        print(f" {topic:<28} {count:>6}  {sub_str}")

    if unclassified_ids:
        print(f"\n Unclassified question IDs ({len(unclassified_ids)}):")
        for qid in unclassified_ids[:20]:
            print(f"   {qid}")
        if len(unclassified_ids) > 20:
            print(f"   ... and {len(unclassified_ids)-20} more")

    print(f"{'═'*64}\n")


# ── CLI ─────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Classify SAT questions by topic and subtopic."
    )
    parser.add_argument("--test", type=int, choices=range(4, 12))
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--report", action="store_true",
                        help="Print report without writing files")
    parser.add_argument("--use-llm", action="store_true",
                        help="Use Claude API for questions rules cannot classify")
    args = parser.parse_args()

    if not args.test and not args.all:
        parser.error("Specify --test N or --all")

    test_ids = list(range(4, 12)) if args.all else [args.test]
    all_classified: List[Dict] = []

    for test_num in test_ids:
        logger.info("═══ Classifying test %d ════════════════════════", test_num)
        try:
            data = classify_test(test_num, use_llm=args.use_llm)
        except FileNotFoundError as exc:
            logger.error("%s — skipping", exc)
            continue

        all_classified.extend(data)

        if not args.report:
            out_path = OUTPUT_DIR / f"test{test_num}.json"
            out_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info("Updated → %s", out_path)

    classification_report(all_classified, test_ids)


if __name__ == "__main__":
    main()
