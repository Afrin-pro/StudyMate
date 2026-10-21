import importlib.util, json, os, sys
import pytest

pytestmark = pytest.mark.unit
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "scripts", f"{name}.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def test_model_check_detects_deprecated_model():
    hc = load("model_healthcheck")
    res = hc.check_models(["qwen/qwen3.6-27b", "other"], ["qwen/qwen3.6-27b", "meta-llama/llama-4-scout-17b-16e-instruct"])
    assert res == {"qwen/qwen3.6-27b": True, "meta-llama/llama-4-scout-17b-16e-instruct": False}

def test_smoke_test_passes_and_fails(monkeypatch):
    st = load("smoke_test")
    good = {"/health": (200, json.dumps({"status": "ok"})), "/": (200, "StudyMate"), "/metrics": (200, "studymate_uptime_seconds 1")}
    monkeypatch.setattr(st, "get", lambda url: good["/" + url.split("//", 1)[1].split("/", 1)[1]] if url.count("/") > 2 else good["/"])
    assert st.run("https://x.test") == 0
    bad = dict(good); bad["/health"] = (503, "down")
    monkeypatch.setattr(st, "get", lambda url: bad["/" + url.split("//", 1)[1].split("/", 1)[1]] if url.count("/") > 2 else bad["/"])
    assert st.run("https://x.test") == 1


def test_model_check_matches_with_or_without_org_prefix():
    hc = load("model_healthcheck")
    assert hc.check_models(["qwen3.6-27b"], ["qwen/qwen3.6-27b"]) == {"qwen/qwen3.6-27b": True}
    assert hc.check_models(["Qwen/Qwen3.6-27B"], ["qwen/qwen3.6-27b"]) == {"qwen/qwen3.6-27b": True}

def test_model_check_suggests_close_matches():
    hc = load("model_healthcheck")
    assert "qwen/qwen3-32b" in hc.suggestions(["qwen/qwen3-32b", "llama-3.1-8b"], "qwen/qwen3.6-27b")

def test_main_exit_2_without_api_key(monkeypatch, capsys):
    hc = load("model_healthcheck")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert hc.main() == 2 and "GROQ_API_KEY" in capsys.readouterr().out

def test_main_reports_missing_model_and_lists_ids(monkeypatch, capsys):
    import types, groq
    hc = load("model_healthcheck")
    monkeypatch.setenv("GROQ_API_KEY", "k")
    fake = types.SimpleNamespace(models=types.SimpleNamespace(list=lambda: types.SimpleNamespace(
        data=[types.SimpleNamespace(id="qwen/qwen3-32b")])))
    monkeypatch.setattr(groq, "Groq", lambda api_key: fake)
    assert hc.main() == 1
    out = capsys.readouterr().out
    assert "MISSING" in out and "qwen/qwen3-32b" in out

def test_main_exit_2_when_api_errors(monkeypatch, capsys):
    import groq
    hc = load("model_healthcheck")
    monkeypatch.setenv("GROQ_API_KEY", "bad")
    def boom(api_key): raise RuntimeError("401 invalid api key")
    monkeypatch.setattr(groq, "Groq", boom)
    assert hc.main() == 2 and "could not list" in capsys.readouterr().out

def test_main_ok_when_listed(monkeypatch):
    import types, groq, app
    hc = load("model_healthcheck")
    monkeypatch.setenv("GROQ_API_KEY", "k")
    fake = types.SimpleNamespace(models=types.SimpleNamespace(list=lambda: types.SimpleNamespace(
        data=[types.SimpleNamespace(id=app.VISION_MODEL)])))
    monkeypatch.setattr(groq, "Groq", lambda api_key: fake)
    assert hc.main() == 0
