"""Post-deploy smoke test: python scripts/smoke_test.py https://<space>.hf.space"""
import json, sys, time, urllib.request, urllib.error


def get(url):
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:
        return 0, str(e)


def run(base, retries=15, wait=30):
    base = base.rstrip("/")

    for attempt in range(1, retries + 1):
        status, body = get(f"{base}/health")
        if status == 200:
            break
        print(f"[{attempt}/{retries}] /health returned {status}, waiting {wait}s...")
        if attempt == retries:
            print("SMOKE TEST FAILED — space never came up")
            return 1
        time.sleep(wait)

    failures = []

    status, body = get(f"{base}/health")
    if status != 200 or json.loads(body).get("status") != "ok":
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


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: smoke_test.py <base-url>")
    sys.exit(run(sys.argv[1]))
