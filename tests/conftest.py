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


class FakeTextClient:
    """Stands in for huggingface_hub.InferenceClient."""
    def __init__(self, reply="Hello from the text model", error=None):
        self.reply, self.error, self.calls = reply, error, []
    def chat_completion(self, messages, **kw):
        self.calls.append({"messages": messages, **kw})
        if self.error: raise self.error
        return FakeCompletion(self.reply)


class FakeGroq:
    """Stands in for groq.Groq. Configure class attributes per test."""
    reply = "Hello from the vision model"
    error = None
    reject_reasoning_format = False
    calls = []

    def __init__(self, api_key=None):
        self.chat = types.SimpleNamespace(
            completions=types.SimpleNamespace(create=self._create))

    def _create(self, **kw):
        FakeGroq.calls.append(kw)
        if FakeGroq.reject_reasoning_format and "reasoning_format" in kw:
            raise ValueError("400 unknown parameter: reasoning_format")
        if FakeGroq.error: raise FakeGroq.error
        return FakeCompletion(FakeGroq.reply)

    @classmethod
    def reset(cls):
        cls.reply, cls.error, cls.reject_reasoning_format, cls.calls = (
            "Hello from the vision model", None, False, [])


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
    fake = FakeTextClient()
    monkeypatch.setattr(studymate, "text_client", fake)
    return fake


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
