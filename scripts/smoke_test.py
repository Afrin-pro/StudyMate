"""Post-deploy smoke test.

    python scripts/smoke_test.py https://<space>.hf.space
    SPACE_URL=https://<space>.hf.space python scripts/smoke_test.py

After a push, Hugging Face rebuilds the Docker image, which takes a few
minutes; during that time the URL answers 503 or doesn't connect at all. So
this waits (polling /health) up to `retries * wait` seconds before judging.
Exit code 0 = healthy, 1 = failed.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request


def get(url):
    """Never raises: returns (status, body); status 0 means no connection."""
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return 0, str(e)


def wait_until_up(base, retries, wait, sleep):
    for attempt in range(1, retries + 1):
        status, _ = get(f"{base}/health")
        if status == 200:
            return True
        print(f"[{attempt}/{retries}] /health -> {status or 'no connection'}; waiting {wait}s for the Space to build...")
        if attempt < retries:
            sleep(wait)
    return False


def run(base, retries=20, wait=30, sleep=time.sleep):
    base = base.rstrip("/")
    if not wait_until_up(base, retries, wait, sleep):
        print("SMOKE TEST FAILED - Space never became healthy")
        return 1

    failures = []
    status, body = get(f"{base}/health")
    try:
        ok = status == 200 and json.loads(body).get("status") == "ok"
    except ValueError:
        ok = False
    if not ok:
        failures.append(f"/health not ok (status={status})")

    status, body = get(f"{base}/")
    if status != 200 or "StudyMate" not in body:
        failures.append(f"login page not served (status={status})")

    status, body = get(f"{base}/metrics")
    if status != 200 or "studymate_uptime_seconds" not in body:
        failures.append(f"/metrics not exposing telemetry (status={status})")

    for f in failures:
        print("FAIL:", f)
    print("SMOKE TEST", "FAILED" if failures else "PASSED")
    return 1 if failures else 0


def main(argv=None, env=None):
    argv = sys.argv[1:] if argv is None else argv
    env = os.environ if env is None else env
    url = argv[0] if argv else env.get("SPACE_URL", "")
    if not url:
        print("error: pass the Space URL as an argument or set SPACE_URL")
        return 2
    return run(url)


if __name__ == "__main__":
    sys.exit(main())
