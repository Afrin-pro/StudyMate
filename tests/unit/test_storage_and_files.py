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

    def test_caps_at_20_pages(self):
        out = app.extract_pdf_text(make_pdf_bytes([f"page text {i}" for i in range(25)]))
        assert "--- Page 20 ---" in out and "--- Page 21 ---" not in out

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
