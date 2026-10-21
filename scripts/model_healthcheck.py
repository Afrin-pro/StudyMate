"""Detects silent model deprecations BEFORE users do.

Background: Groq retired llama-4-scout-17b-16e-instruct with no in-app warning
and image analysis started returning 404 in production. Run this on a schedule
(see .github/workflows/model-healthcheck.yml) and on every deploy.

Exit codes: 0 = all configured models listed, 1 = a model is missing,
            2 = could not query Groq at all (bad/missing key, network) -
                a different problem from a deprecation, so it is reported separately.
"""
import difflib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _norm(model_id):
    return model_id.strip().lower()


def check_models(available_ids, expected):
    """Pure function (unit-testable): returns {model_id: bool}.

    A model counts as available on an exact (case-insensitive) match, or when
    the only difference is the 'org/' prefix, so 'qwen/x' matches a listing of 'x'.
    """
    available = {_norm(a) for a in available_ids}
    available |= {a.split("/")[-1] for a in available}
    return {m: (_norm(m) in available or _norm(m).split("/")[-1] in available) for m in expected}


def suggestions(available_ids, model_id, n=3):
    return difflib.get_close_matches(model_id, list(available_ids), n=n, cutoff=0.4)


def main():
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        print("ERROR: GROQ_API_KEY is empty. Add it under GitHub -> Settings -> Secrets -> Actions.")
        return 2
    import app
    from groq import Groq
    try:
        ids = [m.id for m in Groq(api_key=key).models.list().data]
    except Exception as e:  # auth failure, network, API change
        print(f"ERROR: could not list Groq models: {type(e).__name__}: {str(e)[:200]}")
        return 2

    result = check_models(ids, [app.VISION_MODEL])
    for model, ok in result.items():
        print(f"{'OK     ' if ok else 'MISSING'} {model}")
        if not ok:
            print(f"  closest listed IDs: {suggestions(ids, model) or 'none'}")
            print(f"  all {len(ids)} listed IDs: {sorted(ids)}")
    return 0 if all(result.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
