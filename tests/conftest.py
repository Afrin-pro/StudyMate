"""Shared fixtures.

Design rules for this suite:
  * No network. Both AI providers (HF text, Groq vision) are replaced by fakes.
  * No shared state. Every test gets its own temp user/session directories.
  * Tests exercise real code paths (real HTTP routing, real JSON persistence).
"""
import os
import sys
import types

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as studymate  # noqa: E402


# ── Fake AI providers ─────────────────────────────────────────────────────────
class _Msg:
    def __init__(self, content): self.content = content
class _Choice:
    def __init__(self, content): self.message = _Msg(content)
class FakeCompletion:
    def __init__(self, content): self.choices = [_Choice(content)]


class FakeGroq:
    """Stands in for groq.Groq. Configure class attributes per test."""
    reply = "Hello from the model"
    error = None
    reject_reasoning_format = False
    max_chars = None          # simulate Groq's per-request token limit (413)
    calls = []

    def __init__(self, api_key=None):
        self.chat = types.SimpleNamespace(
            completions=types.SimpleNamespace(create=self._create))

    def _create(self, **kw):
        FakeGroq.calls.append(kw)
        if FakeGroq.reject_reasoning_format and "reasoning_format" in kw:
            raise ValueError("400 unknown parameter: reasoning_format")
        if FakeGroq.error: raise FakeGroq.error
        if FakeGroq.max_chars and len(str(kw.get("messages"))) > FakeGroq.max_chars:
            raise RuntimeError("Error code: 413 - Request too large for model (tokens per minute)")
        return FakeCompletion(FakeGroq.reply)

    @classmethod
    def reset(cls):
        cls.reply, cls.error, cls.reject_reasoning_format, cls.calls = (
            "Hello from the model", None, False, [])
        cls.max_chars = None


# ── Fixtures ──────────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    for name in ("user_data", "sessions", "uploads"):
        (tmp_path / name).mkdir()
    monkeypatch.setattr(studymate, "DATA_DIR", str(tmp_path / "user_data"))
    monkeypatch.setattr(studymate, "SESSION_DIR", str(tmp_path / "sessions"))
    monkeypatch.setattr(studymate, "UPLOAD_DIR", str(tmp_path / "uploads"))
    studymate.metrics.reset()
    yield tmp_path


@pytest.fixture
def text_model(monkeypatch):
    """Text and vision both run on Groq now, so both fixtures share one fake."""
    import groq
    FakeGroq.reset()
    monkeypatch.setattr(groq, "Groq", FakeGroq)
    yield FakeGroq
    FakeGroq.reset()


@pytest.fixture
def vision_model(monkeypatch):
    import groq
    FakeGroq.reset()
    monkeypatch.setattr(groq, "Groq", FakeGroq)
    yield FakeGroq
    FakeGroq.reset()


@pytest.fixture
def client():
    return TestClient(studymate.app, follow_redirects=False)


@pytest.fixture
def user(client):
    """A registered + logged-in user. Returns (username, token)."""
    client.post("/register", data={"username": "afrin", "password": "pw12345"})
    r = client.post("/login", data={"username": "afrin", "password": "pw12345"})
    token = r.headers["location"].split("t=")[1]
    return "afrin", token


def make_png_b64(size=(40, 30), color=(200, 30, 30)):
    import base64, io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def make_pdf_bytes(pages=("Entropy always increases.",)):
    import io
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for text in pages:
        c.drawString(72, 720, text)
        c.showPage()
    c.save()
    return buf.getvalue()
