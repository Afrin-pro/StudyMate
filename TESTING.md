# StudyMate — Test Strategy, Automation & Telemetry

**167 automated tests · 96.7% line coverage (gate: 80%) · runs in ~4 s · 100% offline (AI providers mocked)**

## 1. Test strategy (the "pyramid")

| Layer | Marker | What it proves | Tools |
|---|---|---|---|
| Unit (61) | `unit` | Pure logic: reasoning-leak sanitizers, markdown renderer, PDF/image processing, auth helpers, prompt building | pytest, parametrize |
| Functional / API (73) | `functional` | Real HTTP flows through FastAPI: register → login → chat → upload → history reload; auth, isolation, error paths, security | TestClient, fakes for HF + Groq |
| Frontend contract (33) | `frontend` | The JS the browser *receives* parses, defines `send`/`handleFile`, and renders identically to the Python renderer | `node --check`, node execution |
| Ops / smoke | — | Live service is up; configured models still exist | `scripts/smoke_test.py`, `scripts/model_healthcheck.py` |

**Risk-based design:** each past production incident became a permanent regression test (see §4).
**Isolation:** every test gets its own temp storage dirs and fresh metrics; no network, no shared state, deterministic.
**Test doubles:** `FakeTextClient` / `FakeGroq` in `tests/conftest.py` let tests script rate limits, 400s, leaked reasoning and truncated output.

## 2. Automation framework

- `pytest.ini` — markers, strict mode, coverage with `--cov-fail-under=80`
- `.github/workflows/ci.yml` — Python 3.11 + 3.12 matrix, Node for frontend tests, `ruff` lint, coverage artifacts, post-deploy smoke job
- `.github/workflows/model-healthcheck.yml` — scheduled every 6 h; fails if the configured Groq model disappears (prevents a repeat of the llama-4-scout deprecation outage)
- Run locally: `pip install -r requirements-dev.txt && pytest` · by layer: `pytest -m unit`

## 3. Telemetry & metrics → operational decisions

`app.py` now exposes:
- `GET /health` — liveness probe
- `GET /metrics` — Prometheus text format
- JSON structured logs (`log_event`) for 5xx and model errors

| Metric | Question it answers |
|---|---|
| `studymate_http_requests_total{method,path,status}` | Traffic, error rate (5xx/4xx ratio), auth failures (401 spikes) |
| `studymate_http_request_seconds_{sum,count}` | Average latency per route |
| `studymate_model_seconds_{sum,count}{route=text\|vision}` | Is the AI provider the bottleneck? Which route is slow? |
| `studymate_model_errors_total{route,kind=rate_limit\|other}` | Are we hitting free-tier limits? Is a model deprecated (sudden `other` spike)? |
| `studymate_chat_total{route,has_file}` | Feature usage (vision vs text vs file) → what to optimise |

Suggested SLOs: availability ≥ 99% (`/health`), p95 chat latency < 8 s, model error rate < 2%.
Alert rules: `rate(model_errors_total{kind="other"}[5m]) > 0` → likely deprecation; `rate_limit` > 10/min → add backoff/caching.

## 4. Incident → regression test map

| Production incident | Test that now prevents it |
|---|---|
| Bare `\n` in f-string broke JS regex, killed send + upload | `TestSyntax::*` (`node --check` on rendered page) |
| Android empty `file.type` | `TestGetMime::*` |
| Raw `**bold**` after reload (Python/JS renderer drift) | `TestRendererParity::*` (same corpus through both) |
| Untagged chain-of-thought leaked | `TestStripReasoningPreamble`, `TestModelOutputSanitising`, `test_requests_hidden_reasoning` |
| Groq model deprecated (404) | `test_model_check_detects_deprecated_model` + scheduled workflow |
| **Found by this suite:** stored XSS in sidebar title/username | `TestXss::*` |
| **Found by this suite:** `?t=../user_data/<user>` logged attacker in as that user (auth bypass), and `/logout` could delete arbitrary `.json` | `TestPathTraversal::*` |

Mutation check: re-introducing each historical bug into a copy of `app.py` makes the suite fail (13 failures for the `\n` bug alone), proving the tests detect real regressions rather than just executing lines.

## 5. Known gaps / next steps
- Passwords use unsalted SHA-256 → move to bcrypt/argon2 (add test for hash format + login upgrade path)
- No rate limiting on `/login` (brute force) → add + test
- Browser-level E2E (Playwright) for real upload/click flows
- Prometheus histogram buckets for true p95 (currently sum/count averages)
