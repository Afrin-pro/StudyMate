---
title: StudyMate
emoji: 📚
colorFrom: purple
colorTo: pink
sdk: docker
app_file: app.py
pinned: false
---

# 📚 StudyMate — AI Study Assistant

> Intelligent study chatbot powered by **Qwen2.5-72B-Instruct** · Built with **FastAPI** · Deployed on **Hugging Face Spaces** (Docker)

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green?logo=fastapi)
![Docker](https://img.shields.io/badge/Docker-Blank-blue?logo=docker)
![HuggingFace](https://img.shields.io/badge/🤗-HuggingFace%20Spaces-yellow)
![Model](https://img.shields.io/badge/Model-Qwen2.5--72B-purple)
![License](https://img.shields.io/badge/License-MIT-green)

---

## ✨ Features

- 🔐 **User Authentication** — Register & login with hashed passwords, session tokens in URL (works behind HF proxy)
- 💬 **Persistent Chat History** — All conversations saved per user, reloadable from sidebar
- 🤖 **Qwen2.5-72B-Instruct** — Near GPT-4 quality, free via HF Serverless Inference API
- 🎨 **Beautiful Purple UI** — Custom HTML/CSS chat interface, no frontend framework needed
- 📱 **Responsive Design** — Works on desktop and mobile
- ⚡ **FastAPI Backend** — Fast, async Python web server
- 🐳 **Docker Deployment** — One-click deploy on HF Spaces Blank template

---

## 🖼️ Preview

```
┌─────────────────┬──────────────────────────────────────┐
│  ✦ StudyMate    │  S  Chat with StudyMate               │
│  Study Asst.    │     ● Online                          │
│  👤 username    ├──────────────────────────────────────┤
│                 │                                        │
│  + New Chat     │  ┌─────────────────────────────────┐  │
│                 │  │ python coding basics      [user] │  │
│  RECENT CHATS   │  └─────────────────────────────────┘  │
│  💬 Python...   │  ┌───────────────────────────────┐    │
│  💬 Math...     │  │ Here's an intro to Python...  │    │
│                 │  └───────────────────────────────┘    │
│  ← Log Out      ├──────────────────────────────────────┤
│                 │  [Ask StudyMate anything…]  [Send ↗]  │
└─────────────────┴──────────────────────────────────────┘
```

---

## 🗂️ Project Structure

```
studymate/
├── app.py               # FastAPI application — all routes, auth, chat logic
├── requirements.txt     # Python dependencies
├── Dockerfile           # Docker build instructions for HF Spaces
├── README.md            # This file
├── user_data/           # Auto-created — stores user JSON files
│   └── {username}.json  #   { username, hashed_password, chats: {} }
└── sessions/            # Auto-created — stores session tokens
    └── {token}.json     #   { username, timestamp }
```

---

## 🚀 Deploy on Hugging Face Spaces

### Step 1 — Create a new Space

1. Go to [huggingface.co/new-space](https://huggingface.co/new-space)
2. Fill in:
   - **Owner** → your username
   - **Space name** → e.g. `StudyMate`
   - **License** → MIT
   - **SDK** → **Docker**
   - **Docker template** → **Blank** (dashed box, top-left)
3. Click **Create Space**

### Step 2 — Upload files

In your new Space, go to **Files** tab → **Add file** → **Upload files**

Upload these 4 files:
```
app.py
requirements.txt
Dockerfile
README.md
```

Click **Commit changes to main**

### Step 3 — Add your HF Token (secret)

The model requires authentication:

1. Get your token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
   - Click **New token** → Type: **Read** → Copy it
2. In your Space → **Settings** tab → **Variables and secrets**
3. Click **New secret**:
   - **Name:** `HF_TOKEN`
   - **Value:** paste your token
4. Click **Save** — Space restarts automatically

### Step 4 — Accept Qwen model license

Visit [huggingface.co/Qwen/Qwen2.5-72B-Instruct](https://huggingface.co/Qwen/Qwen2.5-72B-Instruct)
and click **Agree** to accept the license (one-time, free).

### Step 5 — Done! 🎉

Watch **Logs** tab — build takes ~2 minutes.
Your app is live at: `https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME`

---

## 💻 Deploy on GitHub + HF Spaces (Recommended)

Using Git gives you version control and easy updates.

### Step 1 — Push to GitHub

```bash
# Clone your new HF Space as a git repo
git clone https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME
cd YOUR_SPACE_NAME

# Copy your files in
cp /path/to/app.py .
cp /path/to/requirements.txt .
cp /path/to/Dockerfile .
cp /path/to/README.md .

# Push to HF Space (auto-deploys)
git add .
git commit -m "Initial StudyMate deploy"
git push
```

OR push to GitHub and mirror to HF:

```bash
# 1. Create a GitHub repo at github.com/new
# 2. Push your code there
git init
git remote add origin https://github.com/YOUR_USERNAME/studymate.git
git add .
git commit -m "Initial commit"
git push -u origin main

# 3. In HF Space Settings → Link GitHub repo for auto-sync
```

### Step 2 — Future updates

```bash
# Edit app.py locally, then:
git add app.py
git commit -m "Update model / fix bug"
git push   # HF Space auto-rebuilds in ~1 min
```

---

## 🏃 Run Locally

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/studymate.git
cd studymate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your HF token
export HF_TOKEN=hf_your_token_here   # Linux/Mac
set HF_TOKEN=hf_your_token_here      # Windows

# 4. Run
python app.py

# 5. Open browser
# → http://localhost:7860
```

### Run with Docker locally

```bash
# Build
docker build -t studymate .

# Run
docker run -p 7860:7860 -e HF_TOKEN=hf_your_token_here studymate

# Open → http://localhost:7860
```

---

## ⚙️ How It Works

```
User Browser
     │
     │  HTTP (GET/POST)
     ▼
FastAPI (app.py)  ←──── session token in URL (?t=TOKEN)
     │
     ├── /              → auth page (login/register)
     ├── /login         → validate credentials, create session
     ├── /register      → create user JSON
     ├── /chat          → chat UI (requires token)
     ├── /chat/{sid}    → load specific conversation
     ├── /new           → start new chat session
     ├── /api/chat      → POST: send message, get AI reply
     └── /logout        → delete session
          │
          ▼
    HF Inference API
    Qwen2.5-72B-Instruct
```

### Auth flow (why URL tokens?)

HF Spaces runs behind a reverse proxy that **strips cookies**. Standard `Set-Cookie` sessions don't work. Solution: the session token lives in the URL as `?t=TOKEN` and is passed to every link and API call — completely proxy-transparent.

### Data storage

No database needed. Everything is plain JSON files:

```json
// user_data/alice.json
{
  "username": "alice",
  "password": "sha256_hash_of_password",
  "chats": {
    "1715289600": {
      "title": "Python coding basics",
      "history": [
        {"role": "user", "content": "explain loops"},
        {"role": "assistant", "content": "A loop repeats..."}
      ],
      "updated": "2026-05-09T20:00:00"
    }
  }
}
```

---

## 📦 Dependencies

| Package | Version | Purpose |
|---|---|---|
| `fastapi` | 0.115.0 | Web framework |
| `uvicorn` | 0.30.6 | ASGI server |
| `huggingface_hub` | ≥0.24.0 | Inference API client |
| `python-multipart` | 0.0.12 | Form data parsing |

---

## 🤖 Model

**Qwen2.5-72B-Instruct** by Alibaba Cloud

| Property | Value |
|---|---|
| Parameters | 72 Billion |
| Context window | 128K tokens |
| Strengths | Reasoning, math, coding, instruction following |
| License | Qwen License (free for research & commercial) |
| HF page | [Qwen/Qwen2.5-72B-Instruct](https://huggingface.co/Qwen/Qwen2.5-72B-Instruct) |

---

## 🔧 Configuration

All config is via environment variables:

| Variable | Required | Description |
|---|---|---|
| `HF_TOKEN` | ✅ Yes | HuggingFace API token for model inference |

Set in HF Spaces: **Settings → Variables and secrets → New secret**

---

## 🛠️ Troubleshooting

| Error | Fix |
|---|---|
| `You must provide an api_key` | Add `HF_TOKEN` secret in Space Settings |
| `ModuleNotFoundError: gradio` | Wrong `app.py` uploaded — use the FastAPI version |
| After login, still shows login page | Normal with cookies — this app uses URL tokens (`?t=...`) |
| Build fails at pip install | Check `requirements.txt` has all 4 packages |
| Space shows blank page | Check Logs tab — usually a Python import error |
| Model rate limited | HF free tier has limits — wait 1 min and retry |

---

## 📁 File Reference

### `Dockerfile`
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p user_data sessions
EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
```

### `requirements.txt`
```
fastapi==0.115.0
uvicorn==0.30.6
huggingface_hub>=0.24.0
python-multipart==0.0.12
```

### HF Space `README.md` header (top of this file)
```yaml
---
title: StudyMate
emoji: 📚
colorFrom: purple
colorTo: violet
sdk: docker
app_file: app.py
pinned: false
---
```

---

## 🗺️ Roadmap

- [ ] Markdown rendering in chat bubbles
- [ ] File/PDF upload for document Q&A
- [ ] Export chat as PDF
- [ ] Multiple AI personas (Math tutor, Code tutor, etc.)
- [ ] Flashcard generation from chat

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

## 🙏 Credits

- [Qwen Team @ Alibaba Cloud](https://huggingface.co/Qwen) — for the amazing open model
- [Hugging Face](https://huggingface.co) — for free Spaces hosting and Inference API
- [FastAPI](https://fastapi.tiangolo.com) — for the clean Python web framework