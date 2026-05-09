import gradio as gr
import json, os, hashlib, time
from datetime import datetime
from huggingface_hub import InferenceClient

MODEL_ID = "meta-llama/Llama-3.2-3B-Instruct"
client   = InferenceClient(model=MODEL_ID)

SYSTEM_PROMPT = (
    "You are StudyMate, an intelligent and friendly study assistant. "
    "Help students learn concepts, solve problems, and prepare for exams. "
    "Explain clearly with examples. Be encouraging and patient. "
    "Keep responses concise. Use bullet points when helpful."
)

DATA_DIR = "user_data"
os.makedirs(DATA_DIR, exist_ok=True)

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()
def user_file(u): return os.path.join(DATA_DIR, f"{u}.json")
def load_user(u):
    fp = user_file(u)
    return json.load(open(fp)) if os.path.exists(fp) else None
def save_user(d): json.dump(d, open(user_file(d["username"]), "w"), indent=2)

def register_user(username, password):
    username = username.strip()
    if not username or not password: return False, "Username and password required."
    if load_user(username): return False, "Username exists. Please log in."
    save_user({"username": username, "password": hash_pw(password), "chats": {}})
    return True, "Account created! You can now log in."

def login_user(username, password):
    username = username.strip()
    data = load_user(username)
    if not data: return False, "User not found. Please register."
    if data["password"] != hash_pw(password): return False, "Incorrect password."
    return True, username

def generate_response(history, user_msg):
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in history: msgs.append({"role": m["role"], "content": m["content"]})
    msgs.append({"role": "user", "content": user_msg})
    try:
        r = client.chat_completion(messages=msgs, max_tokens=512, temperature=0.7)
        return r.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ Error: {e}"

def save_chat(username, sid, history, title):
    data = load_user(username)
    if not data: return
    data.setdefault("chats", {})[sid] = {
        "title": title, "history": history,
        "updated": datetime.now().isoformat()
    }
    save_user(data)

def get_chat_list(username):
    data = load_user(username)
    if not data: return []
    items = sorted([{"id":k,**v} for k,v in data.get("chats",{}).items()],
                   key=lambda x: x.get("updated",""), reverse=True)
    return items[:25]

# ── HTML renderers ─────────────────────────────────────────────────────────────

def render_auth_screen(msg="", msg_type=""):
    msg_html = ""
    if msg:
        color = "#10b981" if msg_type == "ok" else "#ef4444"
        bg    = "#f0fdf4" if msg_type == "ok" else "#fef2f2"
        msg_html = f'<div style="color:{color};background:{bg};padding:9px 13px;border-radius:9px;font-size:.85rem;margin-top:10px;border-left:3px solid {color}">{msg}</div>'

    return f"""
<div id="app-root" style="
  display:flex; align-items:center; justify-content:center;
  min-height:100vh; padding:20px;
  background:linear-gradient(135deg,#ede9fe,#ddd6fe,#c4b5fd);
  font-family:'DM Sans',sans-serif;
">
  <div style="width:100%;max-width:420px;">
    <div style="
      background:#fff; border-radius:28px; padding:44px 38px;
      box-shadow:0 20px 60px rgba(139,92,246,.22); border:1px solid #e9d5ff;
    ">
      <!-- Logo -->
      <div style="text-align:center;margin-bottom:28px;">
        <div style="
          font-family:Georgia,serif; font-size:2.2rem; font-weight:700;
          background:linear-gradient(135deg,#7c3aed,#a855f7);
          -webkit-background-clip:text; -webkit-text-fill-color:transparent;
          margin-bottom:6px;
        ">✦ StudyMate</div>
        <div style="color:#6b7280;font-size:.88rem;">Your intelligent study assistant · Llama 3</div>
      </div>

      <!-- Tabs -->
      <div style="display:flex;border-bottom:2px solid #e9d5ff;margin-bottom:20px;">
        <button onclick="showTab('login')" id="tab-login" style="
          flex:1; padding:10px; border:none; background:transparent;
          font-weight:700; font-size:.92rem; cursor:pointer;
          color:#8b5cf6; border-bottom:2px solid #8b5cf6; margin-bottom:-2px;
          font-family:'DM Sans',sans-serif;
        ">Login</button>
        <button onclick="showTab('register')" id="tab-register" style="
          flex:1; padding:10px; border:none; background:transparent;
          font-weight:700; font-size:.92rem; cursor:pointer;
          color:#9ca3af; border-bottom:2px solid transparent; margin-bottom:-2px;
          font-family:'DM Sans',sans-serif;
        ">Register</button>
      </div>

      <!-- Login form -->
      <div id="pane-login">
        <input id="inp-lu" type="text" placeholder="Username" style="{INPUT_STYLE}" />
        <input id="inp-lp" type="password" placeholder="Password" style="{INPUT_STYLE}" />
        <button onclick="doLogin()" style="{BTN_STYLE}">Sign In →</button>
        {msg_html}
      </div>

      <!-- Register form -->
      <div id="pane-register" style="display:none;">
        <input id="inp-ru" type="text" placeholder="Choose a username" style="{INPUT_STYLE}" />
        <input id="inp-rp" type="password" placeholder="Choose a password" style="{INPUT_STYLE}" />
        <button onclick="doRegister()" style="{BTN_STYLE}">Create Account →</button>
        <div id="reg-msg"></div>
      </div>
    </div>
  </div>
</div>

<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
* {{ box-sizing: border-box; }}
input:focus {{ border-color:#8b5cf6!important; box-shadow:0 0 0 3px rgba(139,92,246,.12)!important; outline:none!important; }}
</style>

<script>
function showTab(t) {{
  document.getElementById('pane-login').style.display    = t==='login'    ? 'block' : 'none';
  document.getElementById('pane-register').style.display = t==='register' ? 'block' : 'none';
  document.getElementById('tab-login').style.color       = t==='login'    ? '#8b5cf6' : '#9ca3af';
  document.getElementById('tab-register').style.color    = t==='register' ? '#8b5cf6' : '#9ca3af';
  document.getElementById('tab-login').style.borderBottom    = t==='login'    ? '2px solid #8b5cf6' : '2px solid transparent';
  document.getElementById('tab-register').style.borderBottom = t==='register' ? '2px solid #8b5cf6' : '2px solid transparent';
}}
function setHidden(id, val) {{
  var el = document.querySelector('#' + id + ' textarea') || document.querySelector('#' + id + ' input');
  if (el) {{ el.value = val; el.dispatchEvent(new Event('input', {{bubbles:true}})); }}
}}
function doLogin() {{
  var u = document.getElementById('inp-lu').value.trim();
  var p = document.getElementById('inp-lp').value;
  if (!u || !p) return;
  setHidden('_cmd', 'login|' + u + '|' + p);
}}
function doRegister() {{
  var u = document.getElementById('inp-ru').value.trim();
  var p = document.getElementById('inp-rp').value;
  if (!u || !p) return;
  setHidden('_cmd', 'register|' + u + '|' + p);
}}
</script>
"""

def render_chat_screen(username, history, hist_items, welcome_msg=""):
    # Build chat bubbles HTML
    bubbles = ""
    for msg in history:
        if msg["role"] == "user":
            bubbles += f"""
            <div style="display:flex;justify-content:flex-end;margin-bottom:12px;">
              <div style="
                background:linear-gradient(135deg,#8b5cf6,#a78bfa);
                color:#fff; border-radius:20px 20px 4px 20px;
                padding:11px 16px; max-width:70%; font-size:.9rem;
                box-shadow:0 3px 12px rgba(139,92,246,.28); line-height:1.5;
              ">{msg['content']}</div>
            </div>"""
        else:
            content = msg['content'].replace('\n', '<br>')
            bubbles += f"""
            <div style="display:flex;justify-content:flex-start;margin-bottom:12px;">
              <div style="
                background:#fff; color:#1e1b4b;
                border-radius:20px 20px 20px 4px;
                padding:11px 16px; max-width:70%; font-size:.9rem;
                box-shadow:0 2px 8px rgba(139,92,246,.08);
                border:1px solid #e9d5ff; line-height:1.5;
              ">{content}</div>
            </div>"""

    if not bubbles:
        bubbles = """
        <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                    height:100%;text-align:center;color:#8b5cf6;padding:40px;">
          <div style="font-size:3rem;margin-bottom:14px;">📚</div>
          <div style="font-size:1.2rem;font-weight:700;color:#7c3aed;margin-bottom:8px;
                      font-family:Georgia,serif;">Hi! I'm StudyMate</div>
          <div style="font-size:.9rem;color:#6b7280;max-width:300px;line-height:1.6;">
            Ask me anything — concepts, problems, exam prep, or explanations.</div>
        </div>"""

    # History sidebar items
    hist_rows = ""
    for it in hist_items:
        title = it.get("title","Untitled")[:36]
        sid   = it["id"]
        hist_rows += f"""
        <div onclick="loadChat('{sid}')" style="
          cursor:pointer; padding:9px 11px; border-radius:11px; margin-bottom:3px;
          font-size:.83rem; color:#374151; border:1px solid transparent;
          white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-weight:500;
          transition:all .15s;
        " onmouseover="this.style.background='#f5f3ff';this.style.borderColor='#e9d5ff';this.style.color='#8b5cf6'"
           onmouseout="this.style.background='';this.style.borderColor='transparent';this.style.color='#374151'">
          💬 {title}
        </div>"""
    if not hist_rows:
        hist_rows = '<p style="color:#9ca3af;font-size:.82rem;padding:10px 6px;">No chats yet</p>'

    return f"""
<div style="
  display:flex; height:100vh; padding:14px; gap:12px; overflow:hidden;
  background:linear-gradient(135deg,#ede9fe,#ddd6fe,#c4b5fd);
  font-family:'DM Sans',sans-serif; box-sizing:border-box;
">

  <!-- ── SIDEBAR ── -->
  <div style="
    width:270px; min-width:250px; flex-shrink:0;
    background:#fff; border-radius:22px; border:1px solid #e9d5ff;
    box-shadow:0 4px 24px rgba(139,92,246,.14);
    display:flex; flex-direction:column; overflow:hidden;
  ">
    <!-- Logo -->
    <div style="padding:22px 20px 14px;border-bottom:1px solid #e9d5ff;
                background:linear-gradient(180deg,#faf5ff,#fff);flex-shrink:0;">
      <div style="font-family:Georgia,serif;font-size:1.2rem;font-weight:700;color:#8b5cf6;">✦ StudyMate</div>
      <div style="font-size:.76rem;color:#6b7280;margin-top:3px;">Study Assistant · Online</div>
      <div style="font-size:.75rem;color:#a78bfa;margin-top:2px;">👤 {username}</div>
    </div>

    <!-- New chat -->
    <div style="padding:14px 16px 6px;flex-shrink:0;">
      <button onclick="newChat()" style="
        width:100%; background:linear-gradient(135deg,#8b5cf6,#a78bfa);
        color:#fff; border:none; border-radius:14px; font-weight:700;
        font-size:.9rem; padding:12px; cursor:pointer;
        box-shadow:0 4px 14px rgba(139,92,246,.3);
        font-family:'DM Sans',sans-serif; letter-spacing:.01em;
      ">＋  New Chat</button>
    </div>

    <!-- History -->
    <div style="flex:1;overflow-y:auto;padding:8px 12px 12px;min-height:0;">
      <div style="font-size:.68rem;font-weight:700;color:#6b7280;
                  letter-spacing:.1em;padding:10px 6px 6px;">RECENT CHATS</div>
      {hist_rows}
    </div>

    <!-- Logout -->
    <div style="padding:10px 14px;border-top:1px solid #e9d5ff;flex-shrink:0;">
      <button onclick="doLogout()" style="
        width:100%; background:transparent; color:#6b7280;
        border:1px solid #e9d5ff; border-radius:11px;
        font-size:.84rem; padding:9px; cursor:pointer;
        font-family:'DM Sans',sans-serif; transition:all .15s;
      " onmouseover="this.style.background='#faf5ff';this.style.color='#8b5cf6'"
         onmouseout="this.style.background='transparent';this.style.color='#6b7280'">← Log Out</button>
    </div>
  </div>

  <!-- ── CHAT PANEL ── -->
  <div style="
    flex:1; min-width:0;
    background:#fff; border-radius:22px; border:1px solid #e9d5ff;
    box-shadow:0 4px 24px rgba(139,92,246,.14);
    display:flex; flex-direction:column; overflow:hidden;
  ">
    <!-- Header -->
    <div style="padding:15px 22px;border-bottom:1px solid #e9d5ff;
                display:flex;align-items:center;gap:13px;
                background:linear-gradient(180deg,#faf5ff,#fff);flex-shrink:0;">
      <div style="
        width:42px;height:42px;flex-shrink:0;
        background:linear-gradient(135deg,#8b5cf6,#a78bfa);
        border-radius:14px;color:#fff;display:flex;align-items:center;
        justify-content:center;font-weight:700;font-size:1.1rem;
        box-shadow:0 3px 10px rgba(139,92,246,.3);
      ">S</div>
      <div>
        <div style="font-weight:700;font-size:1rem;color:#1e1b4b;">Chat with StudyMate</div>
        <div style="font-size:.74rem;color:#10b981;font-weight:600;">● Online</div>
      </div>
    </div>

    <!-- Messages -->
    <div id="chat-msgs" style="
      flex:1;overflow-y:auto;padding:20px;
      background:#faf5ff;min-height:0;
    ">{bubbles}</div>

    <!-- Typing indicator (hidden) -->
    <div id="typing-ind" style="display:none;padding:0 20px 8px;background:#faf5ff;">
      <div style="
        background:#fff;border:1px solid #e9d5ff;border-radius:20px 20px 20px 4px;
        padding:10px 16px;display:inline-block;font-size:.85rem;color:#6b7280;
      ">StudyMate is thinking<span id="dots">...</span></div>
    </div>

    <!-- Input bar -->
    <div style="
      display:flex;gap:10px;align-items:flex-end;padding:14px 18px;
      border-top:1px solid #e9d5ff;background:#fff;flex-shrink:0;
    ">
      <textarea id="chat-input" placeholder="Ask StudyMate anything…" rows="1"
        onkeydown="if(event.key==='Enter'&&!event.shiftKey){{event.preventDefault();sendMsg();}}"
        oninput="this.style.height='auto';this.style.height=Math.min(this.scrollHeight,120)+'px'"
        style="
          flex:1;border:1.5px solid #e9d5ff;border-radius:15px;
          background:#faf5ff;color:#1e1b4b;font-size:.92rem;
          padding:13px 16px;resize:none;min-height:50px;max-height:120px;
          font-family:'DM Sans',sans-serif;transition:border-color .2s,box-shadow .2s;
          outline:none;line-height:1.4;
        "
        onfocus="this.style.borderColor='#8b5cf6';this.style.boxShadow='0 0 0 3px rgba(139,92,246,.12)'"
        onblur="this.style.borderColor='#e9d5ff';this.style.boxShadow='none'"
      ></textarea>
      <button onclick="sendMsg()" style="
        background:linear-gradient(135deg,#8b5cf6,#a78bfa);
        color:#fff;border:none;border-radius:15px;font-weight:700;
        font-size:.92rem;padding:13px 24px;cursor:pointer;white-space:nowrap;
        box-shadow:0 4px 14px rgba(139,92,246,.35);
        transition:transform .15s,box-shadow .15s;height:50px;
        font-family:'DM Sans',sans-serif;flex-shrink:0;
      "
      onmouseover="this.style.transform='translateY(-2px)';this.style.boxShadow='0 7px 20px rgba(139,92,246,.45)'"
      onmouseout="this.style.transform='';this.style.boxShadow='0 4px 14px rgba(139,92,246,.35)'"
      >Send ↗</button>
    </div>
  </div>
</div>

<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
* {{ box-sizing: border-box; }}
::-webkit-scrollbar {{ width: 4px; }}
::-webkit-scrollbar-thumb {{ background: #e9d5ff; border-radius: 4px; }}
</style>

<script>
function setHidden(id, val) {{
  var el = document.querySelector('#' + id + ' textarea') || document.querySelector('#' + id + ' input');
  if (el) {{ el.value = val; el.dispatchEvent(new Event('input', {{bubbles:true}})); }}
}}
function sendMsg() {{
  var inp = document.getElementById('chat-input');
  var msg = inp.value.trim();
  if (!msg) return;
  inp.value = ''; inp.style.height = '';
  // Show user bubble immediately
  var msgs = document.getElementById('chat-msgs');
  msgs.innerHTML += '<div style="display:flex;justify-content:flex-end;margin-bottom:12px;"><div style="background:linear-gradient(135deg,#8b5cf6,#a78bfa);color:#fff;border-radius:20px 20px 4px 20px;padding:11px 16px;max-width:70%;font-size:.9rem;box-shadow:0 3px 12px rgba(139,92,246,.28);line-height:1.5;">' + msg.replace(/</g,'&lt;').replace(/>/g,'&gt;') + '</div></div>';
  msgs.scrollTop = msgs.scrollHeight;
  document.getElementById('typing-ind').style.display = 'block';
  setHidden('_msg', msg);
}}
function newChat() {{ setHidden('_cmd', 'newchat'); }}
function doLogout() {{ setHidden('_cmd', 'logout'); }}
function loadChat(sid) {{ setHidden('_cmd', 'load|' + sid); }}
</script>
"""

# Shared style constants
INPUT_STYLE = (
    "width:100%;border:1.5px solid #e9d5ff;border-radius:13px;"
    "background:#faf5ff;color:#1e1b4b;font-size:.92rem;"
    "padding:12px 15px;font-family:'DM Sans',sans-serif;"
    "transition:border-color .2s;margin-bottom:10px;display:block;"
)
BTN_STYLE = (
    "width:100%;background:linear-gradient(135deg,#8b5cf6,#a78bfa);"
    "color:#fff;border:none;border-radius:14px;font-weight:700;"
    "font-size:.92rem;padding:13px;cursor:pointer;"
    "box-shadow:0 4px 14px rgba(139,92,246,.35);"
    "font-family:'DM Sans',sans-serif;margin-top:4px;"
)

CSS = """
html, body {
  margin: 0 !important; padding: 0 !important; height: 100% !important;
  background: linear-gradient(135deg,#ede9fe,#ddd6fe,#c4b5fd) !important;
}
.gradio-container {
  margin: 0 !important; padding: 0 !important;
  max-width: 100% !important; min-height: 100vh !important;
  background: transparent !important;
}
.gradio-container > .main,
.gradio-container > .main > .wrap,
.gradio-container > .main > .wrap > .gap {
  height: 100vh !important;
  padding: 0 !important;
  gap: 0 !important;
  margin: 0 !important;
  background: transparent !important;
}
footer { display: none !important; }
.block { background: transparent !important; border: none !important;
         box-shadow: none !important; padding: 0 !important; }
"""

# ══════════════════════════════════════════════════════════════════════════════
with gr.Blocks(title="StudyMate", fill_height=True) as demo:

    # State
    s_user    = gr.State("")
    s_sid     = gr.State("")
    s_history = gr.State([])

    # Single HTML component — the entire UI
    ui = gr.HTML(render_auth_screen(), label="")

    # Hidden plumbing — these never appear visually
    _cmd = gr.Textbox(visible=False, elem_id="_cmd", label="")
    _msg = gr.Textbox(visible=False, elem_id="_msg", label="")

    # ── Command dispatcher ─────────────────────────────────────────────────────
    def dispatch(cmd, username, sid, history):
        if not cmd: return gr.update(), username, sid, history
        parts = cmd.split("|", 2)
        action = parts[0]

        if action == "login" and len(parts) == 3:
            u, p = parts[1], parts[2]
            ok, result = login_user(u, p)
            if not ok:
                return render_auth_screen(result, "err"), "", "", []
            items = get_chat_list(result)
            new_sid = str(int(time.time()))
            return render_chat_screen(result, [], items), result, new_sid, []

        elif action == "register" and len(parts) == 3:
            u, p = parts[1], parts[2]
            ok, msg = register_user(u, p)
            return render_auth_screen(msg, "ok" if ok else "err"), "", "", []

        elif action == "logout":
            return render_auth_screen(), "", "", []

        elif action == "newchat":
            new_sid = str(int(time.time()))
            items = get_chat_list(username)
            return render_chat_screen(username, [], items), username, new_sid, []

        elif action == "load" and len(parts) == 2:
            load_sid = parts[1]
            data = load_user(username)
            stored = (data or {}).get("chats", {}).get(load_sid, {}).get("history", [])
            items = get_chat_list(username)
            return render_chat_screen(username, stored, items), username, load_sid, stored

        return gr.update(), username, sid, history

    # ── Message sender ─────────────────────────────────────────────────────────
    def send_message(msg, username, sid, history):
        if not msg.strip() or not username:
            return gr.update(), username, sid, history
        history = list(history or [])
        response = generate_response(history, msg)
        history += [{"role":"user","content":msg}, {"role":"assistant","content":response}]
        data = load_user(username)
        existing = (data or {}).get("chats",{}).get(sid,{}).get("title", msg[:50])
        title = existing if len(history) > 2 else msg[:50]
        save_chat(username, sid, history, title)
        items = get_chat_list(username)
        return render_chat_screen(username, history, items), username, sid, history

    # Wire up
    _cmd.change(dispatch,
        inputs=[_cmd, s_user, s_sid, s_history],
        outputs=[ui, s_user, s_sid, s_history])

    _msg.change(send_message,
        inputs=[_msg, s_user, s_sid, s_history],
        outputs=[ui, s_user, s_sid, s_history])

if __name__ == "__main__":
    demo.launch(css=CSS, theme=gr.themes.Base())
