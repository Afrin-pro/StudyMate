"""Post-deploy smoke test:  python scripts/smoke_test.py https://<space>.hf.space

Verifies the deployed service is up, serving the login page, and exposing
telemetry. Exit code != 0 fails the deploy pipeline.
"""
import json
import sys
import urllib.request


def get(url):
    with urllib.request.urlopen(url, timeout=20) as r:
        return r.status, r.read().decode()


def run(base):
    base = base.rstrip("/")
    failures = []

    status, body = get(f"{base}/health")
    if status != 200 or json.loads(body).get("status") != "ok":
        failures.append("/health not ok")

    status, body = get(f"{base}/")
    if status != 200 or "StudyMate" not in body:
        failures.append("login page not served")

    status, body = get(f"{base}/metrics")
    if status != 200 or "studymate_uptime_seconds" not in body:
        failures.append("/metrics not exposing telemetry")

    for f in failures:
        print("FAIL:", f)
    print("SMOKE TEST", "FAILED" if failures else "PASSED")
    return 1 if failures else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: smoke_test.py <base-url>")
    sys.exit(run(sys.argv[1]))
