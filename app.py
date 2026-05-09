from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
import uvicorn, json, os, hashlib, time, secrets
from datetime import datetime
from huggingface_hub import InferenceClient

MODEL_ID  = "Qwen/Qwen2.5-72B-Instruct"
HF_TOKEN  = os.environ.get("HF_TOKEN")          # set in HF Space → Settings → Secrets
client    = InferenceClient(model=MODEL_ID, token=HF_TOKEN)

SYSTEM_PROMPT = (
    "You are StudyMate, an intelligent and friendly study assistant. "
    "Help students learn concepts, solve problems, and prepare for exams. "
    "Explain clearly with examples and break down complex topics. "
    "Be encouraging and patient. Use bullet points or numbered lists when helpful."
)

DATA_DIR    = "user_data"
SESSION_DIR = "sessions"
os.makedirs(DATA_DIR,    exist_ok=True)
os.makedirs(SESSION_DIR, exist_ok=True)

# ── Storage helpers ────────────────────────────────────────────────────────────
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
    json.dump({"username": username, "ts": time.time()},
              open(session_file(tok), "w"))
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

# ── Auth from token in URL query string (?t=TOKEN) ────────────────────────────
def current_user(request: Request):
    tok  = request.query_params.get("t") or request.cookies.get("sm_tok")
    sess = get_session(tok)
    return sess["username"] if sess else None

def tok_from(request: Request):
    return request.query_params.get("t") or request.cookies.get("sm_tok") or ""

# ── Shared CSS pieces ──────────────────────────────────────────────────────────
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
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
html,body{{height:100%;font-family:'DM Sans',sans-serif;
  background:linear-gradient(135deg,#ede9fe,#ddd6fe,#c4b5fd);min-height:100vh;}}
input,textarea,button,a{{font-family:inherit;}}
::-webkit-scrollbar{{width:4px}}
::-webkit-scrollbar-thumb{{background:#e9d5ff;border-radius:4px}}
input:focus,textarea:focus{{border-color:#8b5cf6!important;
  box-shadow:0 0 0 3px rgba(139,92,246,.12)!important;outline:none!important;}}
</style></head><body>"""
FOOT = "</body></html>"

# ── Auth page ──────────────────────────────────────────────────────────────────
def auth_page(error="", success="", tab="login"):
    msg = ""
    if error:
        msg = (f'<div style="color:#ef4444;background:#fef2f2;padding:9px 13px;'
               f'border-radius:9px;font-size:.85rem;margin-top:10px;'
               f'border-left:3px solid #ef4444">{error}</div>')
    if success:
        msg = (f'<div style="color:#10b981;background:#f0fdf4;padding:9px 13px;'
               f'border-radius:9px;font-size:.85rem;margin-top:10px;'
               f'border-left:3px solid #10b981">{success}</div>')

    l_active = "color:#8b5cf6;border-bottom:2.5px solid #8b5cf6;"
    r_active  = "color:#8b5cf6;border-bottom:2.5px solid #8b5cf6;"
    l_inactive = "color:#9ca3af;border-bottom:2.5px solid transparent;"
    r_inactive  = "color:#9ca3af;border-bottom:2.5px solid transparent;"
    ls = l_active if tab == "login" else l_inactive
    rs = r_active if tab == "reg"   else r_inactive
    ld = "block" if tab == "login" else "none"
    rd = "block" if tab == "reg"   else "none"
    lm = msg if tab == "login" else ""
    rm = msg if tab == "reg"   else ""

    return HEAD + f"""
<div style="display:flex;align-items:center;justify-content:center;
            min-height:100vh;padding:20px;">
  <div style="width:100%;max-width:420px;">
    <div style="background:#fff;border-radius:28px;padding:44px 38px;
                box-shadow:0 20px 60px rgba(139,92,246,.22);border:1px solid #e9d5ff;">

      <div style="text-align:center;margin-bottom:28px;">
        <div style="font-family:'Space Grotesk',sans-serif;font-size:2.2rem;
                    font-weight:700;background:linear-gradient(135deg,#7c3aed,#a855f7);
                    -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
          ✦ StudyMate</div>
        <div style="color:#6b7280;font-size:.88rem;margin-top:6px;">
          Your intelligent study assistant · Llama 3</div>
      </div>

      <div style="display:flex;border-bottom:2px solid #e9d5ff;margin-bottom:22px;">
        <button onclick="showTab('login')" id="tl"
          style="flex:1;padding:10px;border:none;background:transparent;
                 font-weight:700;font-size:.92rem;cursor:pointer;
                 margin-bottom:-2px;{ls}">Login</button>
        <button onclick="showTab('reg')" id="tr"
          style="flex:1;padding:10px;border:none;background:transparent;
                 font-weight:700;font-size:.92rem;cursor:pointer;
                 margin-bottom:-2px;{rs}">Register</button>
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
    # token appended to every internal link so auth survives HF proxy
    T = f"?t={tok}"

    hist_rows = ""
    for it in hist_items:
        title  = it.get("title", "Untitled")[:34]
        sid    = it["id"]
        is_active = sid == active_sid
        bg  = "background:#f5f3ff;border-color:#e9d5ff;color:#8b5cf6;" if is_active else ""
        hov_over = "this.style.background='#f5f3ff';this.style.color='#8b5cf6';this.style.borderColor='#e9d5ff'"
        hov_out  = (f"this.style.background='{'#f5f3ff' if is_active else ''}'"
                    f";this.style.color='{'#8b5cf6' if is_active else '#374151'}'"
                    f";this.style.borderColor='{'#e9d5ff' if is_active else 'transparent'}'")
        hist_rows += (
            f'<a href="/chat/{sid}{T}" style="display:block;padding:9px 11px;'
            f'border-radius:11px;margin-bottom:3px;font-size:.83rem;color:#374151;'
            f'border:1px solid transparent;white-space:nowrap;overflow:hidden;'
            f'text-overflow:ellipsis;font-weight:500;text-decoration:none;{bg}"'
            f' onmouseover="{hov_over}" onmouseout="{hov_out}">💬 {title}</a>'
        )
    if not hist_rows:
        hist_rows = '<p style="color:#9ca3af;font-size:.82rem;padding:8px 6px;">No chats yet</p>'

    bubbles = ""
    for msg in history:
        txt = (msg["content"]
               .replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
               .replace("\n","<br/>"))
        if msg["role"] == "user":
            bubbles += (
                f'<div style="display:flex;justify-content:flex-end;margin-bottom:14px;">'
                f'<div style="background:linear-gradient(135deg,#8b5cf6,#a78bfa);color:#fff;'
                f'border-radius:20px 20px 4px 20px;padding:12px 16px;max-width:70%;'
                f'font-size:.92rem;line-height:1.5;box-shadow:0 3px 12px rgba(139,92,246,.28);">'
                f'{txt}</div></div>'
            )
        else:
            bubbles += (
                f'<div style="display:flex;justify-content:flex-start;margin-bottom:14px;">'
                f'<div style="background:#fff;color:#1e1b4b;'
                f'border-radius:20px 20px 20px 4px;padding:12px 16px;max-width:70%;'
                f'font-size:.92rem;line-height:1.5;'
                f'box-shadow:0 4px 24px rgba(139,92,246,.14);border:1px solid #e9d5ff;">'
                f'{txt}</div></div>'
            )

    welcome = "" if bubbles else """
    <div style="display:flex;flex-direction:column;align-items:center;
                justify-content:center;height:100%;text-align:center;padding:40px;">
      <div style="font-size:3rem;margin-bottom:14px;">📚</div>
      <div style="font-family:'Space Grotesk',sans-serif;font-size:1.3rem;
                  font-weight:700;color:#7c3aed;margin-bottom:10px;">Hi! I'm StudyMate</div>
      <div style="font-size:.92rem;color:#6b7280;max-width:320px;line-height:1.7;">
        Ask me anything — concepts, problems, exam prep, or explanations.</div>
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
      <div>
        <div style="font-family:'Space Grotesk',sans-serif;font-weight:700;
                    font-size:1rem;color:#1e1b4b;">Chat with StudyMate</div>
        <div style="font-size:.74rem;color:#10b981;font-weight:600;">● Online</div>
      </div>
    </div>

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

    <div style="display:flex;gap:10px;align-items:flex-end;padding:14px 18px;
                border-top:1px solid #e9d5ff;background:#fff;flex-shrink:0;">
      <textarea id="inp" placeholder="Ask StudyMate anything… (Enter to send, Shift+Enter = new line)"
        rows="1"
        onkeydown="if(event.key==='Enter'&&!event.shiftKey){{event.preventDefault();send();}}"
        oninput="this.style.height='auto';this.style.height=Math.min(this.scrollHeight,120)+'px'"
        style="flex:1;border:1.5px solid #e9d5ff;border-radius:15px;
               background:#faf5ff;color:#1e1b4b;font-size:.92rem;
               padding:13px 16px;resize:none;min-height:50px;max-height:120px;
               outline:none;line-height:1.4;font-family:inherit;"></textarea>
      <button onclick="send()" id="sbtn" style="
        background:linear-gradient(135deg,#8b5cf6,#a78bfa);color:#fff;border:none;
        border-radius:15px;font-weight:700;font-size:.92rem;padding:13px 24px;
        cursor:pointer;white-space:nowrap;height:50px;flex-shrink:0;
        box-shadow:0 4px 14px rgba(139,92,246,.35);font-family:inherit;">Send ↗</button>
    </div>
  </div>
</div>

<script>
var SID = "{active_sid}";
var TOK = "{tok}";
var msgs = document.getElementById('msgs');
msgs.scrollTop = msgs.scrollHeight;

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

function bubble(role,text){{
  var d=document.createElement('div');
  d.style.cssText='display:flex;justify-content:'+(role==='user'?'flex-end':'flex-start')+';margin-bottom:14px;';
  var i=document.createElement('div');
  if(role==='user'){{
    i.style.cssText='background:linear-gradient(135deg,#8b5cf6,#a78bfa);color:#fff;border-radius:20px 20px 4px 20px;padding:12px 16px;max-width:70%;font-size:.92rem;line-height:1.5;box-shadow:0 3px 12px rgba(139,92,246,.28);';
  }}else{{
    i.style.cssText='background:#fff;color:#1e1b4b;border-radius:20px 20px 20px 4px;padding:12px 16px;max-width:70%;font-size:.92rem;line-height:1.5;box-shadow:0 4px 24px rgba(139,92,246,.14);border:1px solid #e9d5ff;';
  }}
  i.innerHTML=esc(text);
  d.appendChild(i);
  msgs.insertBefore(d,document.getElementById('typing'));
  msgs.scrollTop=msgs.scrollHeight;
}}

async function send(){{
  var inp=document.getElementById('inp');
  var msg=inp.value.trim();
  if(!msg)return;
  inp.value='';inp.style.height='';
  document.getElementById('sbtn').disabled=true;
  document.getElementById('typing').style.display='block';
  msgs.scrollTop=msgs.scrollHeight;
  bubble('user',msg);
  try{{
    var r=await fetch('/api/chat?t='+TOK,{{
      method:'POST',
      headers:{{'Content-Type':'application/json'}},
      body:JSON.stringify({{sid:SID,message:msg}})
    }});
    var data=await r.json();
    document.getElementById('typing').style.display='none';
    if(data.reply){{
      bubble('assistant',data.reply);
      if(data.sid) SID=data.sid;
      if(data.refresh_sidebar) setTimeout(function(){{
        location.href='/chat/'+SID+'?t='+TOK;
      }},300);
    }}else{{
      bubble('assistant','⚠️ Something went wrong. Please try again.');
    }}
  }}catch(e){{
    document.getElementById('typing').style.display='none';
    bubble('assistant','⚠️ Network error. Please try again.');
  }}
  document.getElementById('sbtn').disabled=false;
  inp.focus();
}}
</script>""" + FOOT

# ── Routes ─────────────────────────────────────────────────────────────────────
app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    if current_user(request):
        return RedirectResponse(f"/chat?t={tok_from(request)}")
    return HTMLResponse(auth_page())

@app.post("/login")
async def do_login(request: Request,
                   username: str = Form(...), password: str = Form(...)):
    username = username.strip()
    data = load_user(username)
    if not data:
        return HTMLResponse(auth_page(error="User not found. Please register.", tab="login"))
    if data["password"] != hash_pw(password):
        return HTMLResponse(auth_page(error="Incorrect password.", tab="login"))
    tok  = create_session(username)
    # Redirect with token in URL AND set cookie (belt + suspenders)
    resp = RedirectResponse(f"/chat?t={tok}", status_code=303)
    resp.set_cookie("sm_tok", tok, httponly=True,
                    max_age=86400 * 7, samesite="lax")
    return resp

@app.post("/register")
async def do_register(request: Request,
                      username: str = Form(...), password: str = Form(...)):
    username = username.strip()
    if not username or not password:
        return HTMLResponse(auth_page(error="Username and password required.", tab="reg"))
    if load_user(username):
        return HTMLResponse(auth_page(error="Username already exists.", tab="reg"))
    save_user({"username": username, "password": hash_pw(password), "chats": {}})
    return HTMLResponse(auth_page(success="Account created! You can now log in.", tab="login"))

@app.get("/logout")
async def do_logout(request: Request):
    tok  = tok_from(request)
    sf   = session_file(tok)
    if os.path.exists(sf): os.remove(sf)
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie("sm_tok")
    return resp

@app.get("/new", response_class=HTMLResponse)
async def new_chat(request: Request):
    u = current_user(request)
    if not u: return RedirectResponse("/")
    tok   = tok_from(request)
    sid   = str(int(time.time()))
    items = get_chat_list(u)
    return HTMLResponse(chat_page(u, tok, [], items, sid))

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
    sid = str(int(time.time()))
    return HTMLResponse(chat_page(u, tok, [], items, sid))

@app.get("/chat/{sid}", response_class=HTMLResponse)
async def chat_session(request: Request, sid: str):
    u = current_user(request)
    if not u: return RedirectResponse("/")
    tok     = tok_from(request)
    data    = load_user(u)
    history = (data or {}).get("chats", {}).get(sid, {}).get("history", [])
    items   = get_chat_list(u)
    return HTMLResponse(chat_page(u, tok, history, items, sid))

@app.post("/api/chat")
async def api_chat(request: Request):
    u = current_user(request)
    if not u: return JSONResponse({"error": "unauthorized"}, status_code=401)

    body    = await request.json()
    sid     = body.get("sid") or str(int(time.time()))
    msg     = body.get("message", "").strip()
    if not msg: return JSONResponse({"error": "empty"})

    data    = load_user(u)
    history = (data or {}).get("chats", {}).get(sid, {}).get("history", [])

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in history:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": msg})

    try:
        r     = client.chat_completion(messages=messages, max_tokens=512, temperature=0.7)
        reply = r.choices[0].message.content.strip()
    except Exception as e:
        reply = f"⚠️ Error: {e}"

    history = history + [{"role": "user", "content": msg},
                         {"role": "assistant", "content": reply}]

    data = load_user(u)
    is_first = len(history) == 2
    title = msg[:50] if is_first else (data or {}).get("chats", {}).get(sid, {}).get("title", msg[:50])
    data.setdefault("chats", {})[sid] = {
        "title": title, "history": history,
        "updated": datetime.now().isoformat()
    }
    save_user(data)

    return JSONResponse({"reply": reply, "sid": sid, "refresh_sidebar": is_first})

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=7860, reload=False)