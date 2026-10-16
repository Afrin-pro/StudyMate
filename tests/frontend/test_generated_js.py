"""Tests for the JavaScript the browser actually receives.

These exist because of two real production incidents:
  1. A bare `\\n` inside a Python f-string became a real newline inside a JS regex
     literal -> SyntaxError -> the whole <script> died -> send & upload broke.
  2. Server (Python) and client (JS) markdown renderers drifted apart.
Static review can't see either; rendering + executing the output can.
"""
import json, re, shutil, subprocess
import pytest
import app

pytestmark = pytest.mark.frontend
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="Node.js not installed")


def script_of(html):
    s = html.index("<script>") + len("<script>")
    return html[s:html.index("</script>")]

def node_check(js, tmp_path):
    f = tmp_path / "page.js"; f.write_text(js)
    return subprocess.run([NODE, "--check", str(f)], capture_output=True, text=True)

@pytest.fixture
def chat_js():
    return script_of(app.chat_page("u", "TOK", [], [], "sid1"))


@needs_node
class TestSyntax:
    def test_chat_page_script_parses(self, chat_js, tmp_path):
        r = node_check(chat_js, tmp_path)
        assert r.returncode == 0, r.stderr

    def test_auth_page_script_parses(self, tmp_path):
        r = node_check(script_of(app.auth_page()), tmp_path)
        assert r.returncode == 0, r.stderr

    @pytest.mark.parametrize("tab", ["login", "reg"])
    def test_auth_page_variants_parse(self, tab, tmp_path):
        assert node_check(script_of(app.auth_page(error="e", success="s", tab=tab)), tmp_path).returncode == 0

    def test_script_has_no_literal_newline_inside_regex_literal(self, chat_js):
        # the exact signature of incident #1
        for line in chat_js.splitlines():
            if "replace(/" in line:
                assert line.count("/") >= 2, f"regex literal broken across lines: {line!r}"


class TestRequiredFunctionsExist:
    @pytest.mark.parametrize("fn", ["handleFile", "getMime", "send", "renderMarkdown", "bubble"])
    def test_function_defined(self, chat_js, fn):
        assert re.search(rf"function\s+{fn}\s*\(", chat_js), f"{fn}() missing from generated script"

    def test_file_input_wired_to_handler(self):
        assert 'onchange="handleFile(this)"' in app.chat_page("u", "T", [], [], "s")

    def test_token_and_sid_injected(self):
        js = script_of(app.chat_page("u", "TOK123", [], [], "SID9"))
        assert "TOK123" in js and "SID9" in js


@needs_node
class TestGetMime:
    """Android reports file.type == '' — getMime must infer from extension."""
    def run(self, chat_js, name, typ):
        m = re.search(r"function getMime\(file\)\s*\{.*?\n\}", chat_js, re.S)
        prog = m.group(0) + f"\nconsole.log(JSON.stringify(getMime({{name:{json.dumps(name)},type:{json.dumps(typ)}}})));"
        return json.loads(subprocess.run([NODE, "-e", prog], capture_output=True, text=True, check=True).stdout)

    @pytest.mark.parametrize("name,expected", [
        ("a.png", "image/png"), ("a.JPG", "image/jpeg"), ("a.jpeg", "image/jpeg"),
        ("a.webp", "image/webp"), ("a.gif", "image/gif"), ("n.pdf", "application/pdf"),
        ("n.txt", "text/plain"), ("n.md", "text/markdown"), ("n.xyz", ""),
    ])
    def test_infers_when_type_empty(self, chat_js, name, expected):
        assert self.run(chat_js, name, "") == expected

    def test_prefers_browser_type_when_present(self, chat_js):
        assert self.run(chat_js, "a.png", "image/webp") == "image/webp"


@needs_node
class TestRendererParity:
    """JS renderMarkdown (live chat) and render_markdown_py (reloaded history)
    must produce identical HTML, or users see formatting 'flip' on reload."""
    CORPUS = [
        "plain text",
        "**bold** and *italic* and `code`",
        "## Heading\nbody",
        "### Sub\n- a\n- b\n* c",
        "line1\nline2\n\nline4",
        "**Key Points**\n- Entropy always increases\n- Energy is conserved",
        "5 < 6 & 7 > 3",
        "<script>alert(1)</script>",
        "# H1\n## H2\n###### H6",
        "no markdown, just a # hash mid-line",
    ]

    def js_render(self, chat_js, text):
        m = re.search(r"function renderMarkdown\(s\)\s*\{.*?\n\}", chat_js, re.S)
        prog = m.group(0) + f"\nprocess.stdout.write(renderMarkdown({json.dumps(text)}));"
        return subprocess.run([NODE, "-e", prog], capture_output=True, text=True, check=True).stdout

    @pytest.mark.parametrize("text", CORPUS)
    def test_js_and_python_agree(self, chat_js, text):
        assert self.js_render(chat_js, text) == app.render_markdown_py(text)

    def test_js_strips_think_blocks(self, chat_js):
        assert self.js_render(chat_js, "<think>x</think>Hi") == "Hi"
