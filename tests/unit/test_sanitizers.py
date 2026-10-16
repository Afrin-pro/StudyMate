"""Regression tests for the reasoning-leak fixes (strip_think / strip_reasoning_preamble)."""
import pytest
import app

pytestmark = pytest.mark.unit


class TestStripThink:
    @pytest.mark.parametrize("raw,expected", [
        ("<think>plan</think>Answer", "Answer"),
        ("<THINK>plan</THINK>Answer", "Answer"),
        ("<thinking>x</thinking>Answer", "Answer"),
        ("<reasoning>x</reasoning>Answer", "Answer"),
        ("<think>a</think>One<think>b</think>Two", "OneTwo"),
        ("<think>multi\nline\nplan</think>\n\nAnswer", "Answer"),
        ("No tags here", "No tags here"),
        ("", ""),
        (None, None),
    ])
    def test_removes_tagged_reasoning(self, raw, expected):
        assert app.strip_think(raw) == expected

    def test_unclosed_tag_drops_everything_after_it(self):
        # generation truncated by max_tokens: no closing tag ever arrives
        assert app.strip_think("Intro <think>half a thought...") == "Intro"

    def test_only_reasoning_yields_empty_string(self):
        assert app.strip_think("<think>only thoughts</think>") == ""


LEAK = """Here's a thinking process:

1. Analyze User Input:
- The user sent a screenshot.

2. Formulate Response:
- Be clear.

3. Draft Response (Internal Refinement):
This screenshot explains API, MCP, Tool and Skill.
"""

class TestStripReasoningPreamble:
    def test_recovers_real_answer_after_draft_marker(self):
        out = app.strip_reasoning_preamble(LEAK)
        assert out == "This screenshot explains API, MCP, Tool and Skill."
        assert "thinking process" not in out.lower()

    def test_uses_last_marker_when_several(self):
        text = LEAK + "\n4. Final Answer:\nThe real final text."
        assert app.strip_reasoning_preamble(text) == "The real final text."

    def test_preamble_without_marker_is_left_alone(self):
        # We never guess: no marker -> no cutting
        text = "Let me think about this. Photosynthesis converts light to energy."
        assert app.strip_reasoning_preamble(text) == text

    @pytest.mark.parametrize("legit", [
        "Sure! Steps to solve it:\n\n1. Identify a, b, c.\n2. Apply the formula.\n3. Simplify.",
        "1. Draft Response is a term used in legal writing...",   # starts like a list, not a preamble
        "Photosynthesis happens in chloroplasts.",
    ])
    def test_no_false_positives_on_normal_answers(self, legit):
        assert app.strip_reasoning_preamble(legit) == legit

    @pytest.mark.parametrize("empty", ["", None])
    def test_empty_input(self, empty):
        assert app.strip_reasoning_preamble(empty) == empty

    def test_pipeline_order_think_then_preamble(self):
        raw = "<think>x</think>" + LEAK
        assert app.strip_reasoning_preamble(app.strip_think(raw)).startswith("This screenshot")
