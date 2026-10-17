"""Detects silent model deprecations BEFORE users do.

Background: Groq retired llama-4-scout-17b-16e-instruct with no in-app warning
and image analysis started returning 404 in production. Run this on a schedule
(see .github/workflows/model-healthcheck.yml) and on every deploy.

Exit code 0 = all configured models available, 1 = something is gone.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_models(available_ids, expected):
    # Groq's models.list() strips the org prefix (e.g. "qwen/qwen3.6-27b" → "qwen3.6-27b")
    # Normalise both sides so the comparison works regardless of format.
    def normalise(mid):
        return mid.split("/")[-1].lower()

    available = {normalise(m) for m in available_ids}
    return {m: normalise(m) in available for m in expected}


def main():
    import app
    from groq import Groq
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    ids = [m.id for m in client.models.list().data]
    result = check_models(ids, [app.VISION_MODEL])
    for model, ok in result.items():
        print(f"{'OK     ' if ok else 'MISSING'} {model}")
    return 0 if all(result.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
