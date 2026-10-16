"""render_markdown_py: server-side history renderer."""
import pytest
import app

pytestmark = pytest.mark.unit
r = app.render_markdown_py


def test_bold_and_italic():
    assert r("**hi** and *there*") == "<strong>hi</strong> and <em>there</em>"

@pytest.mark.parametrize("level", range(1, 7))
def test_headers_become_bold_blocks(level):
    out = r("#" * level + " Title")
    assert "<strong" in out and ">Title</strong>" in out and "#" not in out

def test_header_only_at_line_start():
    assert "<strong style" not in r("price is #1 today")

def test_bullets_for_dash_and_star():
    out = r("- one\n* two")
    assert out == "&bull; one<br/>&bull; two"

def test_inline_code():
    assert "<code" in r("use `git stash`") and "git stash</code>" in r("use `git stash`")

def test_newlines_become_br():
    assert r("a\nb") == "a<br/>b"

def test_html_is_escaped_xss():
    out = r("<script>alert(1)</script> & <img src=x onerror=alert(1)>")
    assert "<script" not in out and "<img" not in out
    assert "&lt;script&gt;" in out and "&amp;" in out

def test_empty_and_none():
    assert r("") == "" and r(None) == ""

def test_reported_bug_subheading_not_left_as_raw_asterisks():
    # Regression: reload path showed literal **Heading** after first message
    out = r("**Key Points**\n- Entropy rises")
    assert "**" not in out and "<strong>Key Points</strong>" in out
