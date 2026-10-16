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
