# StudyMate 📚

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi)
![License](https://img.shields.io/badge/License-MIT-green)
![HF Spaces](https://img.shields.io/badge/Deployed%20on-HF%20Spaces-yellow?logo=huggingface)
![Free](https://img.shields.io/badge/Cost-100%25%20Free-brightgreen)

> An intelligent AI study assistant that can read your notes, explain diagrams, and answer exam questions — completely free, no paid APIs required.

**Live demo:** [AiWhizkid/StudyMate](https://huggingface.co/spaces/Ai-WhizKid/StudyMate) 

---

## What it does

Upload a photo of your textbook, a PDF of lecture slides, or just type a question — StudyMate explains concepts clearly, breaks down complex topics, and helps you prepare for exams.

- 💬 **Text chat** — ask anything, get clear explanations with examples
- 🖼️ **Image understanding** — upload diagrams, handwritten notes, screenshots
- 📄 **PDF reading** — drop in lecture slides or textbook chapters (up to 20 pages)
- 🔐 **Multi-user** — register/login, your chat history is saved privately
- 🆓 **100% free** — runs on free-tier APIs and free HF Spaces hosting

---

## Tech stack

| Layer | Technology |
|---|---|
| Web framework | FastAPI + Uvicorn |
| Text model | `Qwen/Qwen2.5-72B-Instruct` via HF Inference API (free) |
| Vision model | `meta-llama/llama-4-scout-17b-16e-instruct` via Groq SDK (free) |
| PDF extraction | pypdf |
| Image resizing | Pillow (auto-resized to max 1024px before sending) |
| Auth | SHA-256 password hashing, `secrets.token_hex` sessions |
| Storage | JSON files on disk |
| Deployment | Hugging Face Spaces — Docker runtime, CPU Basic (free) |

---

## Deploy to Hugging Face Spaces (recommended)

### Step 1 — Create a Space

1. Go to [huggingface.co/new-space](https://huggingface.co/new-space)
2. Give it a name (e.g. `studymate`)
3. Set SDK to **Docker**
4. Hardware: **CPU Basic** (free)
5. Visibility: Public or Private

### Step 2 — Get free API keys

| Key | Where to get it | Cost |
|---|---|---|
| `HF_TOKEN` | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) → New token (Read) | Free |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) → Create API key | Free, no card |

### Step 3 — Add secrets to your Space

Go to **Space → Settings → Variables and secrets → New secret** and add both keys above.

### Step 4 — Push the code

```bash
git clone https://github.com/your-username/studymate
cd studymate

# Add your HF Space as a remote
git remote add space https://huggingface.co/spaces/your-username/studymate

git push space main
```

HF Spaces auto-builds on every push. Watch the **Logs** tab for progress.

---

## Run locally

### Prerequisites

- Python 3.11+
- A `HF_TOKEN` and `GROQ_API_KEY` (see above)

### Setup

```bash
git clone https://github.com/your-username/studymate
cd studymate

pip install -r requirements.txt

export HF_TOKEN=hf_...
export GROQ_API_KEY=gsk_...

uvicorn app:app --host 0.0.0.0 --port 7860 --reload
```

Open [http://localhost:7860](http://localhost:7860) in your browser.

### Run with Docker

```bash
docker build -t studymate .
docker run -p 7860:7860 \
  -e HF_TOKEN=hf_... \
  -e GROQ_API_KEY=gsk_... \
  studymate
```

---

## Project structure

```
studymate/
├── app.py              # FastAPI app — routes, auth, AI calls, HTML generation
├── requirements.txt    # Python dependencies
├── Dockerfile          # Docker config for HF Spaces
├── README.md           # This file
├── user_data/          # Per-user JSON files (auto-created at runtime)
├── sessions/           # Session token files (auto-created at runtime)
└── uploads/            # Temp upload directory (auto-created at runtime)
```

---

## Configuration

All config is via environment variables / HF Secrets:

| Variable | Required | Description |
|---|---|---|
| `HF_TOKEN` | Yes | Hugging Face token for text model inference |
| `GROQ_API_KEY` | Yes | Groq API key for vision model inference |

---

## Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
```

## requirements.txt

```
fastapi
uvicorn
pypdf
Pillow
huggingface_hub
groq
```

---

## API reference

### `POST /api/chat`

Send a message and get an AI reply.

**Request body:**
```json
{
  "sid": "1234567890",
  "message": "Explain Newton's laws of motion",
  "file": {
    "name": "diagram.png",
    "mime": "image/png",
    "b64": "<base64-encoded image data>"
  }
}
```

`file` is optional — omit for text-only messages.

**Response:**
```json
{
  "reply": "Newton's first law states that an object at rest...",
  "sid": "1234567890",
  "refresh_sidebar": false
}
```

### Other routes

| Method | Route | Description |
|---|---|---|
| `GET` | `/` | Login / register page |
| `POST` | `/login` | Authenticate user |
| `POST` | `/register` | Create account |
| `GET` | `/logout` | End session |
| `GET` | `/chat` | Chat home |
| `GET` | `/chat/{sid}` | Load specific conversation |
| `GET` | `/new` | Start new conversation |

---

## Supported file types

| Type | Handling |
|---|---|
| JPEG, PNG, GIF, WebP | Auto-resized to max 1024px, sent to Groq vision model |
| PDF | Text extracted (up to 20 pages / 12,000 chars), sent to text model |
| TXT, Markdown | Decoded as UTF-8 (up to 12,000 chars), sent to text model |
| Max file size | 10 MB |

---

## Free tier limits

| Service | Limit | Sufficient for |
|---|---|---|
| HF Inference API | Rate-limited, free | Personal / light usage |
| Groq free tier | 30 req/min, 1,000 req/day | ~1,000 image analyses/day |

---

## Known issues & design decisions

**Why FastAPI instead of Gradio?**
Gradio's layout broke due to Svelte wrapper conflicts, CSS/theme parameters changed between versions, and HF's iframe rendered blank pages after 6+ failed attempts.

**Why is the session token in the URL?**
HF's reverse proxy strips `Set-Cookie` response headers, so standard cookie-based sessions silently fail. The token is embedded as `?t=TOKEN` and also set as a cookie for direct access.

**Why Groq instead of HF Inference API for vision?**
HF's serverless inference (`hf-inference` provider) is CPU-only and doesn't serve modern vision models. Attempts with `Llama-3.2-11B-Vision` and `Qwen2-VL-7B` both returned `model_not_supported`. Groq provides free GPU inference.

**Why the `groq` SDK instead of raw HTTP?**
Raw `urllib` requests from HF Space datacenter IPs get blocked by Cloudflare (error 1010). The official SDK sets headers that pass through correctly.

**Why not ZeroGPU?**
ZeroGPU (free GPU on HF Spaces) only works with Gradio/Streamlit runtimes, not Docker.

---

## Contributing

Pull requests are welcome.

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m 'Add my feature'`
4. Push: `git push origin feature/my-feature`
5. Open a pull request

---

## License

[MIT](LICENSE) — free to use, modify, and deploy.

---

## Acknowledgements

- [Qwen2.5](https://huggingface.co/Qwen/Qwen2.5-72B-Instruct) by Alibaba Cloud
- [Llama 4 Scout](https://huggingface.co/meta-llama/llama-4-scout-17b-16e-instruct) by Meta
- [Groq](https://groq.com) for free fast inference
- [Hugging Face Spaces](https://huggingface.co/spaces) for free hosting
