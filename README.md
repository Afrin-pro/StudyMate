# StudyMate 📚

An intelligent, free, open-source AI study assistant built with FastAPI and deployed on Hugging Face Spaces. Supports text chat, image analysis, and PDF reading — all powered by free-tier AI models.

---

## Features

- **Text chat** — powered by Qwen2.5-72B-Instruct via Hugging Face Inference API
- **Image understanding** — powered by Llama-4-Scout-17B via Groq (free tier)
- **PDF reading** — extracts and analyses up to 20 pages via pypdf
- **Multi-user auth** — register/login with hashed passwords, session tokens
- **Persistent chat history** — up to 30 conversations per user, stored as JSON
- **Responsive purple UI** — pure HTML/CSS/JS, no frontend framework
- **Docker deployment** — runs on HF Spaces CPU Basic (free)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Web framework | FastAPI + Uvicorn |
| Text model | `Qwen/Qwen2.5-72B-Instruct` via HF Inference API |
| Vision model | `meta-llama/llama-4-scout-17b-16e-instruct` via Groq SDK |
| PDF extraction | pypdf |
| Image resizing | Pillow (max 1024px before sending) |
| Auth | SHA-256 password hashing, `secrets.token_hex` sessions |
| Storage | JSON files on disk (`user_data/`, `sessions/`) |
| Deployment | Hugging Face Spaces — Docker runtime, CPU Basic (free) |

---

## Project Structure

```
├── app.py              # Main FastAPI application
├── requirements.txt    # Python dependencies
├── Dockerfile          # HF Spaces Docker config
├── README.md           # This file
├── user_data/          # Per-user JSON files (auto-created)
├── sessions/           # Session token files (auto-created)
└── uploads/            # Temp upload dir (auto-created)
```

---

## Setup & Deployment

### 1. Fork or create a Hugging Face Space

- Go to [huggingface.co/new-space](https://huggingface.co/new-space)
- Choose **Docker** as the SDK
- Hardware: **CPU Basic** (free)

### 2. Add secrets

Go to **Space Settings → Variables and secrets** and add:

| Secret name | Where to get it |
|---|---|
| `HF_TOKEN` | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) — Read token |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) — free, no card needed |

### 3. Add files to your Space

Push these files to your Space repository:

- `app.py`
- `requirements.txt`
- `Dockerfile`

### 4. Deploy

HF Spaces auto-builds and deploys on every push. Check the **Logs** tab for build errors.

---

## Requirements

**`requirements.txt`:**
```
fastapi
uvicorn
pypdf
Pillow
huggingface_hub
groq
```

**`Dockerfile`:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
```

---

## API Routes

| Method | Route | Description |
|---|---|---|
| `GET` | `/` | Login/register page |
| `POST` | `/login` | Authenticate user |
| `POST` | `/register` | Create new account |
| `GET` | `/logout` | Clear session |
| `GET` | `/chat` | Chat home (loads latest conversation) |
| `GET` | `/chat/{sid}` | Load specific conversation by ID |
| `GET` | `/new` | Start a new conversation |
| `POST` | `/api/chat` | Send message (JSON), returns AI reply |

### `/api/chat` request body

```json
{
  "sid": "1234567890",
  "message": "Explain Newton's laws",
  "file": {
    "name": "diagram.png",
    "mime": "image/png",
    "b64": "<base64-encoded data>"
  }
}
```

`file` is optional. Omit it for text-only messages.

### `/api/chat` response

```json
{
  "reply": "Newton's first law states...",
  "sid": "1234567890",
  "refresh_sidebar": false
}
```

---

## Authentication

Sessions are stored as JSON files in `sessions/`. Because Hugging Face's reverse proxy strips `Set-Cookie` headers, the session token is passed as a URL query parameter `?t=TOKEN` alongside the cookie fallback.

Passwords are hashed with SHA-256 before storage. No plaintext passwords are ever written to disk.

---

## File Upload Support

| File type | How it's handled |
|---|---|
| JPEG / PNG / GIF / WebP | Resized to max 1024px, sent to Groq vision model as base64 |
| PDF | Text extracted with pypdf (up to 20 pages, truncated at 12,000 chars), sent to text model |
| TXT / Markdown | Decoded as UTF-8, truncated at 12,000 chars, sent to text model |

---

## Free Tier Limits

| Service | Limit |
|---|---|
| HF Inference API (Qwen text) | Rate-limited, free for low usage |
| Groq free tier (vision) | 30 req/min, 1,000 req/day, no credit card |

For a personal study tool these limits are more than sufficient.

---

## Known Issues & Lessons Learned

- **Gradio abandoned** — layout broke due to Svelte wrapper conflicts, CSS/theme params changed between versions, and HF's iframe rendered blank pages. Switched to pure FastAPI + raw HTML.
- **HF strips Set-Cookie** — session tokens embedded in URL (`?t=TOKEN`) as a workaround.
- **HF serverless inference doesn't support vision models** — `hf-inference` provider is CPU-only for modern models. Tried Llama-3.2-11B-Vision and Qwen2-VL-7B — both returned `model_not_supported`.
- **Gemini free tier** — worked but hit 429 rate limits under even light usage.
- **Groq + urllib = Cloudflare 1010** — raw HTTP requests from HF Space IPs get blocked by Cloudflare. Fixed by using the official `groq` Python SDK which sets correct headers.
- **ZeroGPU is Gradio-only** — cannot be used with Docker Spaces.

---

## License

MIT — free to use, modify, and deploy.