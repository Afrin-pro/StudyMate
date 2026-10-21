"""Auth/storage helpers, PDF extraction, image resizing, prompt building."""
import base64, io, os
import pytest
import app
from tests.conftest import make_png_b64, make_pdf_bytes

pytestmark = pytest.mark.unit


class TestAuthStorage:
    def test_hash_is_deterministic_and_not_plaintext(self):
        assert app.hash_pw("secret") == app.hash_pw("secret")
        assert app.hash_pw("secret") != "secret"
        assert len(app.hash_pw("secret")) == 64

    def test_hash_differs_per_password(self):
        assert app.hash_pw("a") != app.hash_pw("b")

    def test_user_roundtrip(self):
        app.save_user({"username": "u1", "password": "x", "chats": {}})
        assert app.load_user("u1")["username"] == "u1"

    def test_load_missing_user_is_none(self):
        assert app.load_user("ghost") is None

    def test_session_roundtrip_and_token_entropy(self):
        t1, t2 = app.create_session("u"), app.create_session("u")
        assert t1 != t2 and len(t1) == 48
        assert app.get_session(t1)["username"] == "u"

    @pytest.mark.parametrize("tok", [None, "", "does-not-exist"])
    def test_invalid_session_tokens(self, tok):
        assert app.get_session(tok) is None

    def test_chat_list_sorted_newest_first_and_capped(self):
        chats = {f"c{i}": {"title": str(i), "history": [], "updated": f"2026-01-{i+1:02d}"} for i in range(35)}
        app.save_user({"username": "u", "password": "x", "chats": chats})
        items = app.get_chat_list("u")
        assert len(items) == 30
        assert items[0]["id"] == "c34"

    def test_chat_list_unknown_user(self):
        assert app.get_chat_list("nobody") == []


class TestPdf:
    def test_extracts_text(self):
        out = app.extract_pdf_text(make_pdf_bytes(["Entropy always increases."]))
        assert "Entropy always increases." in out and "--- Page 1 ---" in out

    def test_long_pdf_reads_all_pages_up_to_cap(self):
        out = app.extract_pdf_text(make_pdf_bytes([f"page text {i}" for i in range(60)]))
        assert "--- Page 60 ---" in out      # old limit was 20 pages

    def test_page_cap_is_configurable(self, monkeypatch):
        monkeypatch.setattr(app, "MAX_PDF_PAGES", 5)
        out = app.extract_pdf_text(make_pdf_bytes([f"page text {i}" for i in range(9)]))
        assert "--- Page 5 ---" in out and "--- Page 6 ---" not in out

    def test_corrupt_pdf_does_not_raise(self):
        assert app.extract_pdf_text(b"not a pdf").startswith("[Could not read PDF")

    def test_blank_pdf_message(self):
        assert app.extract_pdf_text(make_pdf_bytes([""])) == "[No readable text found in PDF]"

    def test_without_pypdf_installed(self, monkeypatch):
        monkeypatch.setattr(app, "HAS_PDF", False)
        assert "install pypdf" in app.extract_pdf_text(b"x")


class TestImageResize:
    def _size(self, b64):
        from PIL import Image
        return Image.open(io.BytesIO(base64.b64decode(b64))).size

    def test_large_image_downscaled_to_limit(self):
        out, mime = app.resize_image_b64(make_png_b64((3000, 1500)), "image/png")
        assert mime == "image/jpeg" and max(self._size(out)) == app.MAX_IMG_PIXELS

    def test_aspect_ratio_preserved(self):
        out, _ = app.resize_image_b64(make_png_b64((2000, 1000)), "image/png")
        w, h = self._size(out)
        assert abs(w / h - 2.0) < 0.02

    def test_small_image_not_upscaled(self):
        out, _ = app.resize_image_b64(make_png_b64((100, 80)), "image/png")
        assert self._size(out) == (100, 80)

    def test_garbage_input_returned_unchanged(self):
        assert app.resize_image_b64("!!!notbase64", "image/png") == ("!!!notbase64", "image/png")

    def test_no_pillow_passthrough(self, monkeypatch):
        monkeypatch.setattr(app, "HAS_PIL", False)
        assert app.resize_image_b64("abc", "image/png") == ("abc", "image/png")


class TestBuildMessages:
    def test_system_prompt_first_then_history(self):
        hist = [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]
        msgs = app.build_messages_with_file(hist, "next", {"type": "text", "name": "n.txt", "text": "body"})
        assert msgs[0]["role"] == "system" and msgs[1]["content"] == "q"

    def test_text_file_injected_into_prompt(self):
        msgs = app.build_messages_with_file([], "explain", {"type": "pdf", "name": "n.pdf", "text": "BODY"})
        c = msgs[-1]["content"]
        assert "n.pdf" in c and "BODY" in c and c.endswith("explain")

    def test_default_prompt_when_no_question(self):
        msgs = app.build_messages_with_file([], "", {"type": "pdf", "name": "n.pdf", "text": "BODY"})
        assert "summarise" in msgs[-1]["content"].lower()

    def test_image_becomes_multimodal_block(self):
        msgs = app.build_messages_with_file([], "what is this", {"type": "image", "name": "i.png", "mime": "image/png", "b64": "AAA"})
        parts = msgs[-1]["content"]
        assert parts[0] == {"type": "text", "text": "what is this"}
        assert parts[1]["image_url"]["url"] == "data:image/png;base64,AAA"

    def test_image_without_question_has_only_image_part(self):
        msgs = app.build_messages_with_file([], "", {"type": "image", "name": "i.png", "mime": "image/png", "b64": "AAA"})
        assert [p["type"] for p in msgs[-1]["content"]] == ["image_url"]


class TestSelectRelevantText:
    @staticmethod
    def doc(pages=120, hit=90):
        ps = [f"Chapter {i}. Generic filler about operating systems and networks. " * 12 for i in range(1, pages + 1)]
        ps[hit - 1] = "Database normalization: 1NF 2NF 3NF BCNF remove redundancy in a DBMS. " * 6
        return "\n\n".join(f"--- Page {i+1} ---\n{p}" for i, p in enumerate(ps))

    def test_short_document_returned_unchanged(self):
        assert app.select_relevant_text("small doc", "q", 12000) == "small doc"

    def test_empty_and_none(self):
        assert app.select_relevant_text("", "q") == "" and app.select_relevant_text(None, "q") is None

    def test_finds_relevant_section_deep_in_long_document(self):
        out = app.select_relevant_text(self.doc(), "explain normalization in dbms", 12000)
        assert "normalization" in out          # page 90 would be lost by head-truncation
        assert "--- Page 1 ---" in out         # intro always kept

    def test_output_respects_budget(self):
        for q in ("explain normalization", "summarise this", ""):
            out = app.select_relevant_text(self.doc(), q, 12000)
            assert len(out) <= 12000 + 400     # budget + the short explanatory note

    def test_generic_request_spreads_across_whole_document(self):
        import re
        out = app.select_relevant_text(self.doc(), "summarise this", 12000)
        pages = sorted(int(p) for p in re.findall(r"--- Page (\d+) ---", out))
        assert pages[0] <= 5 and pages[-1] >= 100 and "spread across the document" in out

    def test_original_order_preserved(self):
        import re
        out = app.select_relevant_text(self.doc(), "normalization", 12000)
        pages = [int(p) for p in re.findall(r"--- Page (\d+) ---", out)]
        assert pages == sorted(pages)

    def test_note_tells_model_the_document_is_partial(self):
        assert app.select_relevant_text(self.doc(), "normalization", 12000).startswith("[Long document:")

    def test_stopwords_do_not_drive_selection(self):
        out = app.select_relevant_text(self.doc(), "please explain how to use this", 12000)
        assert "spread across the document" in out     # no real keywords -> even spread

    def test_single_giant_paragraph_without_blank_lines(self):
        out = app.select_relevant_text("word " * 20000, "q", 6000)
        assert len(out) <= 6000 + 400

    def test_small_budget_still_returns_something(self):
        assert app.select_relevant_text(self.doc(), "normalization", 100)
