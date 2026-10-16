import pytest
import app

pytestmark = pytest.mark.functional


def metric(text, prefix):
    return [l for l in text.splitlines() if l.startswith(prefix)]


def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"

def test_metrics_is_prometheus_text(client):
    r = client.get("/metrics")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain")
    assert "studymate_uptime_seconds" in r.text

def test_request_counter_increments_with_labels(client):
    client.get("/health"); client.get("/health")
    line = metric(client.get("/metrics").text, 'studymate_http_requests_total{method="GET",path="/health",status="200"}')
    assert line and line[0].endswith(" 2")

def test_latency_summary_recorded(client):
    client.get("/health")
    text = client.get("/metrics").text
    assert metric(text, 'studymate_http_request_seconds_count{path="/health"}')
    assert metric(text, 'studymate_http_request_seconds_sum{path="/health"}')

def test_chat_and_model_latency_metrics(client, user, text_model):
    client.post(f"/api/chat?t={user[1]}", json={"sid": "s", "message": "hi"})
    text = client.get("/metrics").text
    assert metric(text, 'studymate_chat_total{has_file="false",route="text"} 1')
    assert metric(text, 'studymate_model_seconds_count{route="text"}')

def test_model_errors_are_counted_by_kind(client, user, text_model):
    text_model.error = RuntimeError("429 rate limit")
    client.post(f"/api/chat?t={user[1]}", json={"sid": "s", "message": "hi"})
    text_model.error = RuntimeError("kaboom")
    client.post(f"/api/chat?t={user[1]}", json={"sid": "s", "message": "hi"})
    text = client.get("/metrics").text
    assert metric(text, 'studymate_model_errors_total{kind="rate_limit",route="text"} 1')
    assert metric(text, 'studymate_model_errors_total{kind="other",route="text"} 1')

def test_unauthorized_requests_visible_in_metrics(client):
    client.post("/api/chat", json={"message": "x"})
    assert metric(client.get("/metrics").text, 'studymate_http_requests_total{method="POST",path="/api/chat",status="401"} 1')

def test_metrics_reset_helper():
    app.metrics.inc("x_total")
    app.metrics.reset()
    assert "x_total" not in app.metrics.render()

def test_structured_log_event_is_json(caplog):
    import json, logging
    with caplog.at_level(logging.INFO, logger="studymate"):
        app.log_event("unit_test", a=1)
    assert json.loads(caplog.records[-1].message)["event"] == "unit_test"
