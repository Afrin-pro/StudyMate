from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
import uvicorn, json, os, hashlib, time, secrets, base64, io
from datetime import datetime
from huggingface_hub import InferenceClient

# ── PDF extraction (optional — graceful fallback if not installed) ─────────────
try:
    import pypdf
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

try:
    from PIL import Image as PILImage
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

TEXT_MODEL    = "Qwen/Qwen2.5-72B-Instruct"
VISION_MODEL  = "Qwen/Qwen2-VL-7B-Instruct"
HF_TOKEN      = os.environ.get("HF_TOKEN")
text_client   = InferenceClient(model=TEXT_MODEL,   token=HF_TOKEN)
vision_client = InferenceClient(model=VISION_MODEL, token=HF_TOKEN)

SYSTEM_PROMPT = (
    "You are StudyMate, an intelligent and friendly study assistant. "
    "Help students learn concepts, solve problems, and prepare for exams. "
    "When given document content or images, analyse them carefully and answer questions about them. "
    "Explain clearly with examples and break down complex topics. "
    "Be encouraging and patient. Use bullet points or numbered lists when helpful."
)

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
ALLOWED_DOC_TYPES   = {"application/pdf", "text/plain", "text/markdown"}
MAX_FILE_MB         = 10

MAX_IMG_PIXELS = 1024  # max dimension in pixels before sending to model

def resize_image_b64(b64: str, mime: str) -> tuple[str, str]:
    """Resize image to max MAX_IMG_PIXELS on longest side, return new b64 + mime."""
    if not HAS_PIL:
        return b64, mime
    try:
        raw = base64.b64decode(b64)
        img = PILImage.open(io.BytesIO(raw)).convert("RGB")
        w, h = img.size
        if max(w, h) > MAX_IMG_PIXELS:
            scale = MAX_IMG_PIXELS / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), PILImage.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        new_b64 = base64.b64encode(buf.getvalue()).decode()
        return new_b64, "image/jpeg"
    except Exception:
        return b64, mime


DATA_DIR    = "user_data"
SESSION_DIR = "sessions"
UPLOAD_DIR  = "uploads"
for d in [DATA_DIR, SESSION_DIR, UPLOAD_DIR]:
    os.makedirs(d, exist_ok=True)

# ── Storage ───────────────────────────────────────────────────────────────────
def hash_pw(pw):       return hashlib.sha256(pw.encode()).hexdigest()
def user_file(u):      return os.path.join(DATA_DIR,    f"{u}.json")
def session_file(tok): return os.path.join(SESSION_DIR, f"{tok}.json")

def load_user(u):
    fp = user_file(u)
    return json.load(open(fp)) if os.path.exists(fp) else None

def save_user(d):
    json.dump(d, open(user_file(d["username"]), "w"), indent=2)

def create_session(username):
    tok = secrets.token_hex(24)
    json.dump({"username": username, "ts": time.time()}, open(session_file(tok), "w"))
    return tok

def get_session(tok):
    if not tok: return None
    fp = session_file(tok)
    if not os.path.exists(fp): return None
    return json.load(open(fp))

def get_chat_list(username):
    data = load_user(username)
    if not data: return []
    items = sorted(
        [{"id": k, **v} for k, v in data.get("chats", {}).items()],
        key=lambda x: x.get("updated", ""), reverse=True
    )
    return items[:30]

def current_user(request: Request):
    tok  = request.query_params.get("t") or request.cookies.get("sm_tok")
    sess = get_session(tok)
    return sess["username"] if sess else None

def tok_from(request: Request):
    return request.query_params.get("t") or request.cookies.get("sm_tok") or ""

# ── File processing ───────────────────────────────────────────────────────────
def extract_pdf_text(data: bytes) -> str:
    if not HAS_PDF:
        return "[PDF uploaded — install pypdf to extract text]"
    try:
        reader = pypdf.PdfReader(io.BytesIO(data))
        pages  = []
        for i, page in enumerate(reader.pages):
            if i >= 20: break          # cap at 20 pages
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"--- Page {i+1} ---\n{text.strip()}")
        return "\n\n".join(pages) if pages else "[No readable text found in PDF]"
    except Exception as e:
        return f"[Could not read PDF: {e}]"

def build_messages_with_file(history, user_text, file_info):
    """Build the message list, injecting file content into the user turn."""
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Past history
    for m in history:
        msgs.append({"role": m["role"], "content": m["content"]})

    ftype = file_info.get("type", "")
    fname = file_info.get("name", "file")

    if ftype == "image":
        # Vision: send image as base64 content block
        b64   = file_info["b64"]
        mime  = file_info["mime"]
        parts = []
        if user_text:
            parts.append({"type": "text", "text": user_text})
        parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "auto"}
        })
        msgs.append({"role": "user", "content": parts})
    else:
        # Text / PDF: inject extracted text
        extracted = file_info.get("text", "")
        prompt    = f"I've uploaded a file called '{fname}'.\n\n"
        prompt   += f"File contents:\n{extracted}\n\n"
        prompt   += (user_text if user_text else "Please summarise this document and highlight the key points.")
        msgs.append({"role": "user", "content": prompt})

    return msgs

# ── HTML constants ─────────────────────────────────────────────────────────────
INP = ("width:100%;border:1.5px solid #e9d5ff;border-radius:13px;"
       "background:#faf5ff;color:#1e1b4b;font-size:.92rem;"
       "padding:12px 15px;margin-bottom:12px;display:block;"
       "outline:none;font-family:inherit;box-sizing:border-box;")
BTN = ("width:100%;background:linear-gradient(135deg,#8b5cf6,#a78bfa);"
       "color:#fff;border:none;border-radius:14px;font-weight:700;"
       "font-size:.92rem;padding:13px;cursor:pointer;margin-top:4px;"
       "font-family:inherit;box-sizing:border-box;")
HEAD = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>StudyMate</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@600;700&display=swap" rel="stylesheet"/>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;font-family:'DM Sans',sans-serif;
  background:linear-gradient(135deg,#ede9fe,#ddd6fe,#c4b5fd);min-height:100vh;}
input,textarea,button,a{font-family:inherit;}
::-webkit-scrollbar{width:4px}
::-webkit-scrollbar-thumb{background:#e9d5ff;border-radius:4px}
input:focus,textarea:focus{border-color:#8b5cf6!important;
  box-shadow:0 0 0 3px rgba(139,92,246,.12)!important;outline:none!important;}
</style></head><body>"""
FOOT = "</body></html>"

# ── Auth page ──────────────────────────────────────────────────────────────────
def auth_page(error="", success="", tab="login"):
    msg = ""
    if error:
        msg = f'<div style="color:#ef4444;background:#fef2f2;padding:9px 13px;border-radius:9px;font-size:.85rem;margin-top:10px;border-left:3px solid #ef4444">{error}</div>'
    if success:
        msg = f'<div style="color:#10b981;background:#f0fdf4;padding:9px 13px;border-radius:9px;font-size:.85rem;margin-top:10px;border-left:3px solid #10b981">{success}</div>'

    ls = "color:#8b5cf6;border-bottom:2.5px solid #8b5cf6;" if tab=="login" else "color:#9ca3af;border-bottom:2.5px solid transparent;"
    rs = "color:#8b5cf6;border-bottom:2.5px solid #8b5cf6;" if tab=="reg"   else "color:#9ca3af;border-bottom:2.5px solid transparent;"
    ld, rd = ("block","none") if tab=="login" else ("none","block")
    lm = msg if tab=="login" else ""
    rm = msg if tab=="reg"   else ""

    return HEAD + f"""
<div style="display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px;">
  <div style="width:100%;max-width:420px;">
    <div style="background:#fff;border-radius:28px;padding:44px 38px;
                box-shadow:0 20px 60px rgba(139,92,246,.22);border:1px solid #e9d5ff;">
      <div style="text-align:center;margin-bottom:28px;">
        <div style="font-family:'Space Grotesk',sans-serif;font-size:2.2rem;font-weight:700;
                    background:linear-gradient(135deg,#7c3aed,#a855f7);
                    -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
          ✦ StudyMate</div>
        <div style="color:#6b7280;font-size:.88rem;margin-top:6px;">
          Your intelligent study assistant · Qwen 72B</div>
      </div>
      <div style="display:flex;border-bottom:2px solid #e9d5ff;margin-bottom:22px;">
        <button onclick="showTab('login')" id="tl"
          style="flex:1;padding:10px;border:none;background:transparent;font-weight:700;
                 font-size:.92rem;cursor:pointer;margin-bottom:-2px;{ls}">Login</button>
        <button onclick="showTab('reg')" id="tr"
          style="flex:1;padding:10px;border:none;background:transparent;font-weight:700;
                 font-size:.92rem;cursor:pointer;margin-bottom:-2px;{rs}">Register</button>
      </div>
      <div id="pl" style="display:{ld}">
        <form method="post" action="/login">
          <input name="username" type="text" placeholder="Username" style="{INP}"/>
          <input name="password" type="password" placeholder="Password" style="{INP}"/>
          <button type="submit" style="{BTN}">Sign In →</button>
        </form>{lm}
      </div>
      <div id="pr" style="display:{rd}">
        <form method="post" action="/register">
          <input name="username" type="text" placeholder="Choose a username" style="{INP}"/>
          <input name="password" type="password" placeholder="Choose a password" style="{INP}"/>
          <button type="submit" style="{BTN}">Create Account →</button>
        </form>{rm}
      </div>
    </div>
  </div>
</div>
<script>
function showTab(t) {{
  var login = t==='login';
  document.getElementById('pl').style.display = login ? 'block' : 'none';
  document.getElementById('pr').style.display = login ? 'none'  : 'block';
  document.getElementById('tl').style.color = login ? '#8b5cf6' : '#9ca3af';
  document.getElementById('tr').style.color = login ? '#9ca3af' : '#8b5cf6';
  document.getElementById('tl').style.borderBottom = login ? '2.5px solid #8b5cf6' : '2.5px solid transparent';
  document.getElementById('tr').style.borderBottom = login ? '2.5px solid transparent' : '2.5px solid #8b5cf6';
}}
</script>""" + FOOT

# ── Chat page ──────────────────────────────────────────────────────────────────
def chat_page(username, tok, history, hist_items, active_sid=""):
    T = f"?t={tok}"

    hist_rows = ""
    for it in hist_items:
        title    = it.get("title","Untitled")[:34]
        sid      = it["id"]
        is_act   = sid == active_sid
        bg       = "background:#f5f3ff;border-color:#e9d5ff;color:#8b5cf6;" if is_act else ""
        hov_on   = "this.style.background='#f5f3ff';this.style.color='#8b5cf6';this.style.borderColor='#e9d5ff'"
        hov_off  = (f"this.style.background='{'#f5f3ff' if is_act else ''}';"
                    f"this.style.color='{'#8b5cf6' if is_act else '#374151'}';"
                    f"this.style.borderColor='{'#e9d5ff' if is_act else 'transparent'}'")
        hist_rows += (
            f'<a href="/chat/{sid}{T}" style="display:block;padding:9px 11px;'
            f'border-radius:11px;margin-bottom:3px;font-size:.83rem;color:#374151;'
            f'border:1px solid transparent;white-space:nowrap;overflow:hidden;'
            f'text-overflow:ellipsis;font-weight:500;text-decoration:none;{bg}"'
            f' onmouseover="{hov_on}" onmouseout="{hov_off}">💬 {title}</a>'
        )
    if not hist_rows:
        hist_rows = '<p style="color:#9ca3af;font-size:.82rem;padding:8px 6px;">No chats yet</p>'

    bubbles = ""
    for msg in history:
        content = msg.get("content","")
        # Content can be string or list (multimodal)
        if isinstance(content, list):
            txt_parts = [p.get("text","") for p in content if p.get("type")=="text"]
            display   = " ".join(txt_parts)
            has_img   = any(p.get("type")=="image_url" for p in content)
            if has_img:
                display = "📎 [Image] " + display
        else:
            display = content

        display = (display.replace("&","&amp;").replace("<","&lt;")
                          .replace(">","&gt;").replace("\n","<br/>"))

        if msg["role"] == "user":
            bubbles += (
                f'<div style="display:flex;justify-content:flex-end;margin-bottom:14px;">'
                f'<div style="background:linear-gradient(135deg,#8b5cf6,#a78bfa);color:#fff;'
                f'border-radius:20px 20px 4px 20px;padding:12px 16px;max-width:72%;'
                f'font-size:.92rem;line-height:1.5;box-shadow:0 3px 12px rgba(139,92,246,.28);">'
                f'{display}</div></div>'
            )
        else:
            bubbles += (
                f'<div style="display:flex;justify-content:flex-start;margin-bottom:14px;">'
                f'<div style="background:#fff;color:#1e1b4b;'
                f'border-radius:20px 20px 20px 4px;padding:12px 16px;max-width:72%;'
                f'font-size:.92rem;line-height:1.5;'
                f'box-shadow:0 4px 24px rgba(139,92,246,.14);border:1px solid #e9d5ff;">'
                f'{display}</div></div>'
            )

    welcome = "" if bubbles else """
    <div style="display:flex;flex-direction:column;align-items:center;
                justify-content:center;height:100%;text-align:center;padding:40px;">
      <div style="font-size:3rem;margin-bottom:14px;">📚</div>
      <div style="font-family:'Space Grotesk',sans-serif;font-size:1.3rem;
                  font-weight:700;color:#7c3aed;margin-bottom:10px;">Hi! I'm StudyMate</div>
      <div style="font-size:.92rem;color:#6b7280;max-width:340px;line-height:1.7;">
        Ask me anything, or attach a <strong>PDF</strong> / <strong>image</strong>
        to analyse study material together.</div>
    </div>"""

    return HEAD + f"""
<div style="display:flex;height:100vh;padding:14px;gap:12px;overflow:hidden;">

  <!-- SIDEBAR -->
  <div style="width:270px;min-width:250px;flex-shrink:0;background:#fff;
              border-radius:22px;border:1px solid #e9d5ff;
              box-shadow:0 4px 24px rgba(139,92,246,.14);
              display:flex;flex-direction:column;overflow:hidden;">
    <div style="padding:22px 20px 14px;border-bottom:1px solid #e9d5ff;
                background:linear-gradient(180deg,#faf5ff,#fff);flex-shrink:0;">
      <div style="font-family:'Space Grotesk',sans-serif;font-size:1.2rem;
                  font-weight:700;color:#8b5cf6;">✦ StudyMate</div>
      <div style="font-size:.75rem;color:#6b7280;margin-top:3px;">Study Assistant · Online</div>
      <div style="font-size:.74rem;color:#a78bfa;margin-top:2px;font-weight:500;">👤 {username}</div>
    </div>
    <div style="padding:14px 16px 6px;flex-shrink:0;">
      <a href="/new{T}" style="display:block;text-align:center;text-decoration:none;
        background:linear-gradient(135deg,#8b5cf6,#a78bfa);color:#fff;
        border-radius:14px;font-weight:700;font-size:.9rem;padding:12px;
        box-shadow:0 4px 14px rgba(139,92,246,.3);">＋ New Chat</a>
    </div>
    <div style="flex:1;overflow-y:auto;padding:8px 12px 12px;min-height:0;">
      <div style="font-size:.68rem;font-weight:700;color:#6b7280;
                  letter-spacing:.1em;padding:10px 6px 6px;">RECENT CHATS</div>
      {hist_rows}
    </div>
    <div style="padding:10px 14px;border-top:1px solid #e9d5ff;flex-shrink:0;">
      <a href="/logout{T}" style="display:block;text-align:center;text-decoration:none;
        background:transparent;color:#6b7280;border:1px solid #e9d5ff;
        border-radius:11px;font-size:.84rem;padding:9px;">← Log Out</a>
    </div>
  </div>

  <!-- CHAT PANEL -->
  <div style="flex:1;min-width:0;background:#fff;border-radius:22px;
              border:1px solid #e9d5ff;box-shadow:0 4px 24px rgba(139,92,246,.14);
              display:flex;flex-direction:column;overflow:hidden;">

    <div style="padding:15px 22px;border-bottom:1px solid #e9d5ff;
                display:flex;align-items:center;gap:13px;
                background:linear-gradient(180deg,#faf5ff,#fff);flex-shrink:0;">
      <div style="width:42px;height:42px;flex-shrink:0;
                  background:linear-gradient(135deg,#8b5cf6,#a78bfa);
                  border-radius:14px;color:#fff;display:flex;align-items:center;
                  justify-content:center;font-weight:700;font-size:1.1rem;
                  box-shadow:0 3px 10px rgba(139,92,246,.3);">S</div>
      <div style="flex:1;">
        <div style="font-family:'Space Grotesk',sans-serif;font-weight:700;
                    font-size:1rem;color:#1e1b4b;">Chat with StudyMate</div>
        <div style="font-size:.74rem;color:#10b981;font-weight:600;">● Online</div>
      </div>
      <!-- Upload hint -->
      <div style="font-size:.76rem;color:#a78bfa;font-weight:500;">
        📎 PDF &amp; images supported
      </div>
    </div>

    <!-- Messages -->
    <div id="msgs" style="flex:1;overflow-y:auto;padding:20px;
                           background:#faf5ff;min-height:0;">
      {welcome}{bubbles}
      <div id="typing" style="display:none;margin-bottom:14px;">
        <div style="background:#fff;border:1px solid #e9d5ff;
                    border-radius:20px 20px 20px 4px;padding:10px 16px;
                    display:inline-block;font-size:.85rem;color:#6b7280;">
          StudyMate is thinking<span id="dots">.</span></div>
      </div>
    </div>

    <!-- File preview bar -->
    <div id="file-preview" style="display:none;padding:8px 18px 0;background:#fff;
                                   border-top:1px solid #e9d5ff;">
      <div style="display:flex;align-items:center;gap:10px;padding:8px 12px;
                  background:#f5f3ff;border-radius:12px;border:1px solid #e9d5ff;">
        <span id="file-icon" style="font-size:1.2rem;">📄</span>
        <span id="file-name" style="flex:1;font-size:.84rem;color:#374151;
               white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"></span>
        <span id="file-size" style="font-size:.76rem;color:#9ca3af;flex-shrink:0;"></span>
        <button onclick="clearFile()" style="background:none;border:none;cursor:pointer;
          color:#9ca3af;font-size:1rem;padding:0 4px;line-height:1;">✕</button>
      </div>
      <!-- Image preview (only for images) -->
      <div id="img-preview-wrap" style="display:none;margin-top:8px;margin-bottom:4px;">
        <img id="img-preview" style="max-height:120px;max-width:100%;border-radius:10px;
             border:1px solid #e9d5ff;object-fit:contain;" src="" alt="preview"/>
      </div>
    </div>

    <!-- Input bar -->
    <div style="display:flex;gap:8px;align-items:flex-end;padding:12px 18px 14px;
                background:#fff;flex-shrink:0;">

      <!-- Attach button -->
      <label for="file-inp" title="Attach PDF or image"
        style="flex-shrink:0;cursor:pointer;width:46px;height:50px;
               display:flex;align-items:center;justify-content:center;
               background:#f5f3ff;border:1.5px solid #e9d5ff;border-radius:14px;
               font-size:1.2rem;transition:background .15s;"
        onmouseover="this.style.background='#ede9fe'"
        onmouseout="this.style.background='#f5f3ff'">
        📎
        <input type="file" id="file-inp" accept=".pdf,.txt,.md,image/*"
               style="display:none" onchange="handleFile(this)"/>
      </label>

      <!-- Text input -->
      <textarea id="inp"
        placeholder="Ask anything, or attach a PDF / image first…"
        rows="1"
        onkeydown="if(event.key==='Enter'&&!event.shiftKey){{event.preventDefault();send();}}"
        oninput="this.style.height='auto';this.style.height=Math.min(this.scrollHeight,120)+'px'"
        style="flex:1;border:1.5px solid #e9d5ff;border-radius:15px;
               background:#faf5ff;color:#1e1b4b;font-size:.92rem;
               padding:13px 16px;resize:none;min-height:50px;max-height:120px;
               outline:none;line-height:1.4;font-family:inherit;"></textarea>

      <!-- Send button -->
      <button onclick="send()" id="sbtn"
        style="background:linear-gradient(135deg,#8b5cf6,#a78bfa);color:#fff;border:none;
               border-radius:15px;font-weight:700;font-size:.92rem;padding:13px 20px;
               cursor:pointer;white-space:nowrap;height:50px;flex-shrink:0;
               box-shadow:0 4px 14px rgba(139,92,246,.35);font-family:inherit;">
        Send ↗
      </button>
    </div>
  </div>
</div>

<script>
var SID = "{active_sid}";
var TOK = "{tok}";
var msgs = document.getElementById('msgs');
msgs.scrollTop = msgs.scrollHeight;

var pendingFile = null;  // {{ name, size, mime, data (base64 or null for PDF) }}

// Animated dots
var n=0;
setInterval(function(){{
  n=(n+1)%4;
  var d=document.getElementById('dots');
  if(d) d.textContent='.'.repeat(n||1);
}},400);

function esc(s){{
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;')
          .replace(/>/g,'&gt;').replace(/\\n/g,'<br/>');
}}

function bubble(role, text, extraHtml){{
  var d=document.createElement('div');
  d.style.cssText='display:flex;justify-content:'+(role==='user'?'flex-end':'flex-start')+';margin-bottom:14px;';
  var i=document.createElement('div');
  if(role==='user'){{
    i.style.cssText='background:linear-gradient(135deg,#8b5cf6,#a78bfa);color:#fff;border-radius:20px 20px 4px 20px;padding:12px 16px;max-width:72%;font-size:.92rem;line-height:1.5;box-shadow:0 3px 12px rgba(139,92,246,.28);';
  }}else{{
    i.style.cssText='background:#fff;color:#1e1b4b;border-radius:20px 20px 20px 4px;padding:12px 16px;max-width:72%;font-size:.92rem;line-height:1.5;box-shadow:0 4px 24px rgba(139,92,246,.14);border:1px solid #e9d5ff;';
  }}
  i.innerHTML = esc(text);
  if (extraHtml) i.innerHTML += extraHtml;
  d.appendChild(i);
  msgs.insertBefore(d, document.getElementById('typing'));
  msgs.scrollTop = msgs.scrollHeight;
}}

function handleFile(inp) {{
  var file = inp.files[0];
  if (!file) return;
  if (file.size > {MAX_FILE_MB} * 1024 * 1024) {{
    alert('File too large. Maximum size is {MAX_FILE_MB} MB.');
    inp.value = '';
    return;
  }}
  var allowed = ['application/pdf','text/plain','text/markdown',
                 'image/jpeg','image/png','image/gif','image/webp'];
  if (!allowed.includes(file.type) && !file.name.match(/\\.(pdf|txt|md)$/i)) {{
    alert('Unsupported file. Please upload a PDF, image, or text file.');
    inp.value = '';
    return;
  }}

  var reader = new FileReader();
  reader.onload = function(e) {{
    var b64 = e.target.result.split(',')[1];
    pendingFile = {{ name: file.name, size: file.size, mime: file.type, b64: b64 }};

    // Show preview bar
    document.getElementById('file-name').textContent = file.name;
    document.getElementById('file-size').textContent = (file.size/1024).toFixed(0) + ' KB';
    document.getElementById('file-preview').style.display = 'block';

    if (file.type.startsWith('image/')) {{
      document.getElementById('file-icon').textContent = '🖼️';
      document.getElementById('img-preview-wrap').style.display = 'block';
      document.getElementById('img-preview').src = e.target.result;
    }} else if (file.type === 'application/pdf') {{
      document.getElementById('file-icon').textContent = '📕';
      document.getElementById('img-preview-wrap').style.display = 'none';
    }} else {{
      document.getElementById('file-icon').textContent = '📄';
      document.getElementById('img-preview-wrap').style.display = 'none';
    }}
  }};
  reader.readAsDataURL(file);
}}

function clearFile() {{
  pendingFile = null;
  document.getElementById('file-inp').value = '';
  document.getElementById('file-preview').style.display = 'none';
  document.getElementById('img-preview-wrap').style.display = 'none';
  document.getElementById('img-preview').src = '';
}}

async function send() {{
  var inp = document.getElementById('inp');
  var msg = inp.value.trim();
  if (!msg && !pendingFile) return;

  inp.value = ''; inp.style.height = '';
  document.getElementById('sbtn').disabled = true;
  document.getElementById('typing').style.display = 'block';
  msgs.scrollTop = msgs.scrollHeight;

  // Show user bubble
  var userDisplay = msg || '';
  var imgHtml = '';
  if (pendingFile) {{
    if (pendingFile.mime.startsWith('image/')) {{
      imgHtml = '<br/><img src="data:'+pendingFile.mime+';base64,'+pendingFile.b64+'"'
               +' style="max-width:220px;max-height:160px;border-radius:10px;margin-top:8px;display:block;"/>';
      userDisplay = (msg || '') + (msg ? '' : '');
    }} else {{
      userDisplay = '📎 ' + pendingFile.name + (msg ? '\\n' + msg : '');
    }}
  }}
  bubble('user', userDisplay, imgHtml);

  var payload = {{ sid: SID, message: msg }};
  if (pendingFile) payload.file = pendingFile;
  var f = pendingFile;
  clearFile();

  try {{
    var r = await fetch('/api/chat?t='+TOK, {{
      method: 'POST',
      headers: {{'Content-Type':'application/json'}},
      body: JSON.stringify(payload)
    }});
    var data = await r.json();
    document.getElementById('typing').style.display = 'none';
    if (data.reply) {{
      bubble('assistant', data.reply);
      if (data.sid) SID = data.sid;
      if (data.refresh_sidebar) setTimeout(function(){{
        location.href = '/chat/' + SID + '?t=' + TOK;
      }}, 300);
    }} else {{
      bubble('assistant', '⚠️ Something went wrong. Please try again.');
    }}
  }} catch(e) {{
    document.getElementById('typing').style.display = 'none';
    bubble('assistant', '⚠️ Network error. Please try again.');
  }}
  document.getElementById('sbtn').disabled = false;
  inp.focus();
}}
</script>""" + FOOT

# ── FastAPI App ────────────────────────────────────────────────────────────────
app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    if current_user(request): return RedirectResponse(f"/chat?t={tok_from(request)}")
    return HTMLResponse(auth_page())

@app.post("/login")
async def do_login(request: Request, username: str = Form(...), password: str = Form(...)):
    username = username.strip()
    data = load_user(username)
    if not data:
        return HTMLResponse(auth_page(error="User not found. Please register.", tab="login"))
    if data["password"] != hash_pw(password):
        return HTMLResponse(auth_page(error="Incorrect password.", tab="login"))
    tok  = create_session(username)
    resp = RedirectResponse(f"/chat?t={tok}", status_code=303)
    resp.set_cookie("sm_tok", tok, httponly=True, max_age=86400*7, samesite="lax")
    return resp

@app.post("/register")
async def do_register(request: Request, username: str = Form(...), password: str = Form(...)):
    username = username.strip()
    if not username or not password:
        return HTMLResponse(auth_page(error="Username and password required.", tab="reg"))
    if load_user(username):
        return HTMLResponse(auth_page(error="Username already exists.", tab="reg"))
    save_user({"username": username, "password": hash_pw(password), "chats": {}})
    return HTMLResponse(auth_page(success="Account created! You can now log in.", tab="login"))

@app.get("/logout")
async def do_logout(request: Request):
    tok = tok_from(request)
    sf  = session_file(tok)
    if os.path.exists(sf): os.remove(sf)
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie("sm_tok")
    return resp

@app.get("/new", response_class=HTMLResponse)
async def new_chat(request: Request):
    u = current_user(request)
    if not u: return RedirectResponse("/")
    tok = tok_from(request)
    return HTMLResponse(chat_page(u, tok, [], get_chat_list(u), str(int(time.time()))))

@app.get("/chat", response_class=HTMLResponse)
async def chat_home(request: Request):
    u = current_user(request)
    if not u: return RedirectResponse("/")
    tok   = tok_from(request)
    items = get_chat_list(u)
    if items:
        sid     = items[0]["id"]
        history = items[0].get("history", [])
        return HTMLResponse(chat_page(u, tok, history, items, sid))
    return HTMLResponse(chat_page(u, tok, [], items, str(int(time.time()))))

@app.get("/chat/{sid}", response_class=HTMLResponse)
async def chat_session(request: Request, sid: str):
    u = current_user(request)
    if not u: return RedirectResponse("/")
    tok     = tok_from(request)
    data    = load_user(u)
    history = (data or {}).get("chats", {}).get(sid, {}).get("history", [])
    return HTMLResponse(chat_page(u, tok, history, get_chat_list(u), sid))

@app.post("/api/chat")
async def api_chat(request: Request):
    u = current_user(request)
    if not u: return JSONResponse({"error": "unauthorized"}, status_code=401)

    body = await request.json()
    sid  = body.get("sid") or str(int(time.time()))
    msg  = body.get("message", "").strip()
    file = body.get("file")       # { name, mime, b64 } or None

    if not msg and not file:
        return JSONResponse({"error": "empty"})

    data    = load_user(u)
    history = (data or {}).get("chats", {}).get(sid, {}).get("history", [])

    # ── Build messages ──────────────────────────────────────────────────────
    if file:
        mime  = file.get("mime", "")
        fname = file.get("name", "file")
        b64   = file.get("b64", "")
        raw   = base64.b64decode(b64) if b64 else b""

        if mime.startswith("image/"):
            # Resize to avoid payload too large errors
            b64, mime = resize_image_b64(b64, mime)
            file_info = {"type": "image", "name": fname, "mime": mime, "b64": b64}
        elif mime == "application/pdf":
            text = extract_pdf_text(raw)
            # Truncate to ~12000 chars to stay within context
            if len(text) > 12000:
                text = text[:12000] + "\n\n[...document truncated for length...]"
            file_info = {"type": "pdf", "name": fname, "text": text}
        else:
            # Plain text / markdown
            try:
                text = raw.decode("utf-8", errors="replace")[:12000]
            except Exception:
                text = "[Could not decode file]"
            file_info = {"type": "text", "name": fname, "text": text}

        messages = build_messages_with_file(history, msg, file_info)

        # What to store in history for the user turn
        if mime.startswith("image/"):
            stored_user = f"📎 [Image: {fname}]" + (f"\n{msg}" if msg else "")
        else:
            stored_user = f"📎 [File: {fname}]" + (f"\n{msg}" if msg else "")
    else:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for m in history:
            messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": msg})
        stored_user = msg

    # ── Call model ──────────────────────────────────────────────────────────
    try:
        use_vision = file and file.get("mime","").startswith("image/")
        active_client = vision_client if use_vision else text_client
        r     = active_client.chat_completion(messages=messages, max_tokens=1024, temperature=0.7)
        reply = r.choices[0].message.content.strip()
    except Exception as e:
        reply = f"⚠️ Error: {e}"

    # ── Persist ─────────────────────────────────────────────────────────────
    history = history + [
        {"role": "user",      "content": stored_user},
        {"role": "assistant", "content": reply},
    ]
    data = load_user(u)
    is_first = len(history) == 2
    title = stored_user[:50] if is_first else (data or {}).get("chats",{}).get(sid,{}).get("title", stored_user[:50])
    data.setdefault("chats", {})[sid] = {
        "title": title, "history": history,
        "updated": datetime.now().isoformat()
    }
    save_user(data)

    return JSONResponse({"reply": reply, "sid": sid, "refresh_sidebar": is_first})

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=7860, reload=False)