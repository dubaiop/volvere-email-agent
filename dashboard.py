"""
Web dashboard for the Volvere Email Agent.
Runs the scheduler in a background thread and serves a modern interactive UI.
"""

import threading
import schedule
import time
import anthropic
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, render_template_string, jsonify, request
from database import get_all_emails, get_stats, init_db
from config import CLIENTS, CLAUDE_MODEL

app = Flask(__name__)


def run_scheduler():
    from main import run
    run()
    schedule.every(10).minutes.do(run)
    while True:
        schedule.run_pending()
        time.sleep(30)


scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()


# ── Advisor metadata for UI ──────────────────────────────────────────────────

ADVISOR_META = {
    "ceo_advisor": {"short": "CEO", "name": "Alex",   "color": "#60a5fa"},
    "coo_advisor": {"short": "COO", "name": "Jordan", "color": "#34d399"},
    "cfo_advisor": {"short": "CFO", "name": "Morgan", "color": "#facc15"},
    "cmo_advisor": {"short": "CMO", "name": "Taylor", "color": "#f472b6"},
    "cto_advisor": {"short": "CTO", "name": "Riley",  "color": "#fb923c"},
}


# ── Dashboard HTML ───────────────────────────────────────────────────────────

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Volvere — Email Agent</title>
    <style>
        :root {
            --bg: #0f0f13; --surface: #1a1a24; --surface2: #22222f;
            --border: #2e2e3e; --accent: #6c63ff; --accent2: #a78bfa;
            --text: #e8e8f0; --muted: #6b6b80;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               background: var(--bg); color: var(--text); min-height: 100vh; }

        header { padding: 24px 40px; display: flex; align-items: center;
                 justify-content: space-between; border-bottom: 1px solid var(--border);
                 background: var(--surface); }
        .logo { display: flex; align-items: center; gap: 12px; }
        .logo-icon { width: 36px; height: 36px;
                     background: linear-gradient(135deg, var(--accent), var(--accent2));
                     border-radius: 10px; display: flex; align-items: center;
                     justify-content: center; font-size: 18px; }
        .logo h1 { font-size: 18px; font-weight: 600; letter-spacing: -0.3px; }
        .logo span { font-size: 12px; color: var(--muted); margin-top: 1px; }
        .header-right { display: flex; align-items: center; gap: 16px; }
        .live-badge { display: flex; align-items: center; gap: 6px;
                      font-size: 12px; color: var(--muted); }
        .live-dot { width: 7px; height: 7px; background: #34d399; border-radius: 50%;
                    animation: pulse 2s infinite; }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
        #countdown { color: var(--accent2); font-weight: 500; }

        .meeting-btn {
            display: flex; align-items: center; gap: 8px;
            background: linear-gradient(135deg, var(--accent), var(--accent2));
            border: none; border-radius: 10px; padding: 10px 20px;
            color: white; font-size: 13px; font-weight: 600;
            cursor: pointer; text-decoration: none;
            transition: opacity 0.2s;
        }
        .meeting-btn:hover { opacity: 0.85; }

        .stats { display: flex; gap: 16px; padding: 28px 40px 0; flex-wrap: wrap; }
        .stat-card { background: var(--surface); border: 1px solid var(--border);
                     border-radius: 14px; padding: 20px 24px; min-width: 150px;
                     position: relative; overflow: hidden; transition: border-color 0.2s; }
        .stat-card:hover { border-color: var(--accent); }
        .stat-card::before { content:''; position:absolute; top:0; left:0; right:0; height:2px;
                              background: linear-gradient(90deg, var(--accent), var(--accent2)); }
        .stat-number { font-size: 36px; font-weight: 700; letter-spacing: -1px;
                       background: linear-gradient(135deg,#fff,var(--accent2));
                       -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
        .stat-label { font-size: 12px; color: var(--muted); margin-top: 4px; }

        .controls { display: flex; align-items: center; gap: 12px;
                    padding: 24px 40px 16px; flex-wrap: wrap; }
        .search-wrap { position: relative; flex: 1; max-width: 360px; }
        .search-icon { position:absolute; left:12px; top:50%; transform:translateY(-50%);
                       color:var(--muted); font-size:14px; }
        #search { width:100%; background:var(--surface); border:1px solid var(--border);
                  border-radius:10px; padding:9px 12px 9px 34px; color:var(--text);
                  font-size:14px; outline:none; transition:border-color .2s; }
        #search:focus { border-color:var(--accent); }
        #search::placeholder { color:var(--muted); }
        .filter-btns { display:flex; gap:8px; flex-wrap:wrap; }
        .filter-btn { background:var(--surface); border:1px solid var(--border);
                      border-radius:8px; padding:7px 14px; font-size:12px; color:var(--muted);
                      cursor:pointer; transition:all .2s; }
        .filter-btn:hover, .filter-btn.active { border-color:var(--accent); color:var(--accent2);
                                                background:rgba(108,99,255,.1); }
        .count-label { margin-left:auto; font-size:12px; color:var(--muted); }

        .table-wrap { padding: 0 40px 40px; }
        table { width:100%; border-collapse:collapse; background:var(--surface);
                border:1px solid var(--border); border-radius:14px; overflow:hidden; }
        thead { background:var(--surface2); }
        th { padding:13px 16px; text-align:left; font-size:11px; font-weight:600;
             color:var(--muted); text-transform:uppercase; letter-spacing:.5px;
             border-bottom:1px solid var(--border); }
        td { padding:14px 16px; font-size:13px; border-bottom:1px solid var(--border);
             vertical-align:middle; }
        tr:last-child td { border-bottom:none; }
        tbody tr { cursor:pointer; transition:background .15s; }
        tbody tr:hover td { background:rgba(108,99,255,.06); }

        .badge { display:inline-flex; align-items:center; gap:5px; border-radius:20px;
                 padding:3px 10px; font-size:11px; font-weight:600; white-space:nowrap; }
        .badge-dot { width:5px; height:5px; border-radius:50%; }
        .badge-ceo{background:rgba(96,165,250,.15);color:#60a5fa}
        .badge-coo{background:rgba(52,211,153,.15);color:#34d399}
        .badge-cfo{background:rgba(250,204,21,.15);color:#facc15}
        .badge-cmo{background:rgba(244,114,182,.15);color:#f472b6}
        .badge-cto{background:rgba(251,146,60,.15);color:#fb923c}
        .badge-ceo .badge-dot{background:#60a5fa}
        .badge-coo .badge-dot{background:#34d399}
        .badge-cfo .badge-dot{background:#facc15}
        .badge-cmo .badge-dot{background:#f472b6}
        .badge-cto .badge-dot{background:#fb923c}

        .sender{color:var(--text);font-weight:500}
        .sender-email{font-size:11px;color:var(--muted);margin-top:1px}
        .subject{font-weight:500}
        .preview{color:var(--muted);max-width:280px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .time{color:var(--muted);font-size:11px;white-space:nowrap}
        .open-icon{color:var(--muted);font-size:14px;transition:color .2s}
        tr:hover .open-icon{color:var(--accent2)}

        .empty{text-align:center;padding:80px 40px;color:var(--muted)}
        .empty-icon{font-size:40px;margin-bottom:12px}

        .overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);
                 backdrop-filter:blur(4px);z-index:100;align-items:center;justify-content:center}
        .overlay.open{display:flex}
        .modal{background:var(--surface);border:1px solid var(--border);border-radius:18px;
               width:680px;max-width:95vw;max-height:85vh;display:flex;flex-direction:column;
               overflow:hidden;animation:slideUp .2s ease}
        @keyframes slideUp{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}
        .modal-header{padding:20px 24px;border-bottom:1px solid var(--border);
                      display:flex;align-items:flex-start;justify-content:space-between;gap:16px}
        .modal-meta{display:flex;flex-direction:column;gap:6px}
        .modal-subject{font-size:16px;font-weight:600}
        .modal-info{font-size:12px;color:var(--muted);display:flex;gap:16px;flex-wrap:wrap}
        .close-btn{background:var(--surface2);border:1px solid var(--border);border-radius:8px;
                   width:32px;height:32px;display:flex;align-items:center;justify-content:center;
                   cursor:pointer;color:var(--muted);font-size:16px;flex-shrink:0;transition:all .2s}
        .close-btn:hover{border-color:var(--accent);color:var(--text)}
        .modal-tabs{display:flex;border-bottom:1px solid var(--border);padding:0 24px}
        .tab-btn{padding:12px 16px;font-size:13px;color:var(--muted);cursor:pointer;
                 border-bottom:2px solid transparent;transition:all .2s;margin-bottom:-1px}
        .tab-btn.active{color:var(--accent2);border-bottom-color:var(--accent2)}
        .modal-body{padding:24px;overflow-y:auto;flex:1}
        .tab-content{display:none}
        .tab-content.active{display:block}
        .email-text{font-size:14px;line-height:1.75;color:var(--text);
                    white-space:pre-wrap;font-family:inherit}
        .hidden{display:none!important}
    </style>
</head>
<body>
<header>
    <div class="logo">
        <div class="logo-icon">✉</div>
        <div>
            <h1>Volvere Email Agent</h1>
            <span>AI-powered C-suite advisors</span>
        </div>
    </div>
    <div class="header-right">
        <div class="live-badge">
            <div class="live-dot"></div>
            <span>Live · refreshing in <span id="countdown">60</span>s</span>
        </div>
        <a href="/meeting" class="meeting-btn">🎙 Start Board Meeting</a>
    </div>
</header>

<div class="stats">
    <div class="stat-card">
        <div class="stat-number">{{ stats.total }}</div>
        <div class="stat-label">Total Emails</div>
    </div>
    {% for c in stats.by_client %}
    <div class="stat-card">
        <div class="stat-number">{{ c.count }}</div>
        <div class="stat-label">{{ c.name }}</div>
    </div>
    {% endfor %}
</div>

<div class="controls">
    <div class="search-wrap">
        <span class="search-icon">🔍</span>
        <input id="search" type="text" placeholder="Search by sender, subject, or reply…">
    </div>
    <div class="filter-btns">
        <button class="filter-btn active" data-filter="all">All</button>
        <button class="filter-btn" data-filter="ceo">CEO</button>
        <button class="filter-btn" data-filter="coo">COO</button>
        <button class="filter-btn" data-filter="cfo">CFO</button>
        <button class="filter-btn" data-filter="cmo">CMO</button>
        <button class="filter-btn" data-filter="cto">CTO</button>
    </div>
    <span class="count-label" id="row-count"></span>
</div>

<div class="table-wrap">
{% if emails %}
<table>
    <thead>
        <tr>
            <th>Advisor</th><th>From</th><th>Subject</th>
            <th>Reply Preview</th><th>Time</th><th></th>
        </tr>
    </thead>
    <tbody id="email-table">
        {% for e in emails %}
        {% set role = e.client_name.split(' ')[0].lower() %}
        <tr class="email-row"
            data-filter="{{ role }}"
            data-subject="{{ e.subject | lower }}"
            data-sender="{{ e.sender | lower }}"
            data-reply="{{ e.reply | lower }}"
            onclick="openModal({{ e.id }},'{{ e.client_name }}','{{ e.sender|replace("'","\\'") }}','{{ e.subject|replace("'","\\'") }}','{{ e.processed_at }}',{{ e.body|tojson }},{{ e.reply|tojson }})">
            <td><span class="badge badge-{{ role }}"><span class="badge-dot"></span>{{ e.client_name }}</span></td>
            <td>
                <div class="sender">{{ e.sender.split('<')[0].strip() }}</div>
                {% if '<' in e.sender %}<div class="sender-email">{{ e.sender.split('<')[1].replace('>','') }}</div>{% endif %}
            </td>
            <td class="subject">{{ e.subject }}</td>
            <td class="preview">{{ e.reply }}</td>
            <td class="time">{{ e.processed_at }}</td>
            <td><span class="open-icon">↗</span></td>
        </tr>
        {% endfor %}
    </tbody>
</table>
{% else %}
<div class="empty">
    <div class="empty-icon">📭</div>
    <p>No emails processed yet.</p>
</div>
{% endif %}
</div>

<div class="overlay" id="overlay" onclick="closeOnOverlay(event)">
    <div class="modal">
        <div class="modal-header">
            <div class="modal-meta">
                <div id="modal-badge"></div>
                <div class="modal-subject" id="modal-subject"></div>
                <div class="modal-info">
                    <span>From: <strong id="modal-sender"></strong></span>
                    <span id="modal-time"></span>
                </div>
            </div>
            <div class="close-btn" onclick="closeModal()">✕</div>
        </div>
        <div class="modal-tabs">
            <div class="tab-btn active" onclick="switchTab('reply')">Reply</div>
            <div class="tab-btn" onclick="switchTab('original')">Original Email</div>
        </div>
        <div class="modal-body">
            <div class="tab-content active" id="tab-reply"><pre class="email-text" id="modal-reply"></pre></div>
            <div class="tab-content" id="tab-original"><pre class="email-text" id="modal-body-text"></pre></div>
        </div>
    </div>
</div>

<script>
    let seconds = 60;
    const cd = document.getElementById('countdown');
    setInterval(() => { seconds--; if(seconds<=0){location.reload();return;} cd.textContent=seconds; }, 1000);

    const rows = Array.from(document.querySelectorAll('.email-row'));
    const searchEl = document.getElementById('search');
    const countEl = document.getElementById('row-count');
    let activeFilter = 'all';

    function applyFilters() {
        const q = searchEl.value.toLowerCase();
        let visible = 0;
        rows.forEach(r => {
            const mf = activeFilter==='all' || r.dataset.filter===activeFilter;
            const ms = !q || r.dataset.subject.includes(q) || r.dataset.sender.includes(q) || r.dataset.reply.includes(q);
            const show = mf && ms;
            r.classList.toggle('hidden', !show);
            if(show) visible++;
        });
        countEl.textContent = visible + ' email' + (visible!==1?'s':'');
    }
    searchEl.addEventListener('input', applyFilters);
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active'));
            btn.classList.add('active');
            activeFilter = btn.dataset.filter;
            applyFilters();
        });
    });
    applyFilters();

    function openModal(id, advisor, sender, subject, time, body, reply) {
        const role = advisor.split(' ')[0].toLowerCase();
        document.getElementById('modal-badge').innerHTML = `<span class="badge badge-${role}"><span class="badge-dot"></span>${advisor}</span>`;
        document.getElementById('modal-subject').textContent = subject;
        document.getElementById('modal-sender').textContent = sender;
        document.getElementById('modal-time').textContent = time;
        document.getElementById('modal-reply').textContent = reply;
        document.getElementById('modal-body-text').textContent = body;
        switchTab('reply');
        document.getElementById('overlay').classList.add('open');
    }
    function closeModal() { document.getElementById('overlay').classList.remove('open'); }
    function closeOnOverlay(e) { if(e.target===document.getElementById('overlay')) closeModal(); }
    function switchTab(name) {
        document.querySelectorAll('.tab-btn').forEach((b,i)=>b.classList.toggle('active',(i===0&&name==='reply')||(i===1&&name==='original')));
        document.getElementById('tab-reply').classList.toggle('active',name==='reply');
        document.getElementById('tab-original').classList.toggle('active',name==='original');
    }
    document.addEventListener('keydown', e=>{ if(e.key==='Escape') closeModal(); });
</script>
</body>
</html>
"""


# ── Meeting Room HTML ────────────────────────────────────────────────────────

MEETING_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Volvere — Board Meeting</title>
    <style>
        :root {
            --bg: #0f0f13; --surface: #1a1a24; --surface2: #22222f;
            --border: #2e2e3e; --accent: #6c63ff; --accent2: #a78bfa;
            --text: #e8e8f0; --muted: #6b6b80;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               background: var(--bg); color: var(--text); height: 100vh;
               display: flex; flex-direction: column; overflow: hidden; }

        /* Header */
        header { padding: 16px 32px; background: var(--surface);
                 border-bottom: 1px solid var(--border);
                 display: flex; align-items: center; justify-content: space-between;
                 flex-shrink: 0; }
        .header-left { display: flex; align-items: center; gap: 16px; }
        .back-btn { background: var(--surface2); border: 1px solid var(--border);
                    border-radius: 8px; padding: 7px 14px; color: var(--muted);
                    font-size: 13px; cursor: pointer; text-decoration: none;
                    transition: all .2s; }
        .back-btn:hover { border-color: var(--accent); color: var(--text); }
        .meeting-title { display: flex; align-items: center; gap: 10px; }
        .rec-dot { width: 8px; height: 8px; background: #f87171; border-radius: 50%;
                   animation: pulse 1.5s infinite; }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
        .meeting-title h1 { font-size: 16px; font-weight: 600; }
        .meeting-title span { font-size: 12px; color: var(--muted); }

        /* Advisor Pills */
        .advisors { display: flex; gap: 8px; }
        .advisor-pill { display: flex; align-items: center; gap: 6px;
                        background: var(--surface2); border: 1px solid var(--border);
                        border-radius: 20px; padding: 5px 12px; font-size: 12px; }
        .advisor-pill .dot { width: 6px; height: 6px; border-radius: 50%; }

        /* Chat area */
        #chat { flex: 1; overflow-y: auto; padding: 24px 32px; display: flex;
                flex-direction: column; gap: 24px; }

        /* Welcome */
        .welcome { text-align: center; padding: 40px 20px; }
        .welcome-icon { font-size: 48px; margin-bottom: 16px; }
        .welcome h2 { font-size: 20px; font-weight: 600; margin-bottom: 8px; }
        .welcome p { color: var(--muted); font-size: 14px; max-width: 400px; margin: 0 auto; }

        /* User message */
        .msg-user { display: flex; justify-content: flex-end; }
        .msg-user .bubble { background: linear-gradient(135deg, var(--accent), var(--accent2));
                            color: white; border-radius: 18px 18px 4px 18px;
                            padding: 12px 18px; max-width: 60%; font-size: 14px;
                            line-height: 1.6; }

        /* Advisor responses grid */
        .responses { display: flex; flex-direction: column; gap: 12px; }
        .responses-label { font-size: 11px; color: var(--muted); text-transform: uppercase;
                           letter-spacing: .5px; padding-left: 4px; }
        .responses-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 12px; }

        .advisor-card { background: var(--surface); border: 1px solid var(--border);
                        border-radius: 14px; overflow: hidden; transition: border-color .2s; }
        .advisor-card:hover { border-color: var(--border); }
        .card-header { display: flex; align-items: center; gap: 8px;
                       padding: 12px 16px; border-bottom: 1px solid var(--border); }
        .card-avatar { width: 28px; height: 28px; border-radius: 50%;
                       display: flex; align-items: center; justify-content: center;
                       font-size: 11px; font-weight: 700; color: #0f0f13; flex-shrink: 0; }
        .card-name { font-size: 13px; font-weight: 600; }
        .card-role { font-size: 11px; color: var(--muted); }
        .card-body { padding: 14px 16px; font-size: 13px; line-height: 1.75;
                     color: var(--text); white-space: pre-wrap; }

        /* Thinking skeleton */
        .thinking .card-body { display: flex; flex-direction: column; gap: 8px; padding: 16px; }
        .skeleton { height: 12px; border-radius: 6px; background: var(--surface2);
                    animation: shimmer 1.4s infinite; }
        .skeleton.s1 { width: 80%; }
        .skeleton.s2 { width: 95%; }
        .skeleton.s3 { width: 65%; }
        @keyframes shimmer {
            0%,100% { opacity: .4; } 50% { opacity: .8; }
        }

        /* Input bar */
        .input-bar { padding: 20px 32px; border-top: 1px solid var(--border);
                     background: var(--surface); flex-shrink: 0; }
        .input-wrap { display: flex; gap: 12px; align-items: flex-end;
                      max-width: 900px; margin: 0 auto; }
        #input { flex: 1; background: var(--surface2); border: 1px solid var(--border);
                 border-radius: 12px; padding: 12px 16px; color: var(--text);
                 font-size: 14px; font-family: inherit; outline: none; resize: none;
                 line-height: 1.5; max-height: 140px; transition: border-color .2s; }
        #input:focus { border-color: var(--accent); }
        #input::placeholder { color: var(--muted); }
        .send-btn { background: linear-gradient(135deg, var(--accent), var(--accent2));
                    border: none; border-radius: 12px; width: 44px; height: 44px;
                    display: flex; align-items: center; justify-content: center;
                    cursor: pointer; font-size: 18px; transition: opacity .2s; flex-shrink: 0; }
        .send-btn:hover { opacity: .85; }
        .send-btn:disabled { opacity: .4; cursor: not-allowed; }
        .input-hint { text-align: center; font-size: 11px; color: var(--muted);
                      margin-top: 10px; }
    </style>
</head>
<body>

<header>
    <div class="header-left">
        <a href="/" class="back-btn">← Dashboard</a>
        <div class="meeting-title">
            <div class="rec-dot"></div>
            <h1>Board Meeting</h1>
            <span>All 5 advisors present</span>
        </div>
    </div>
    <div class="advisors">
        <div class="advisor-pill"><div class="dot" style="background:#60a5fa"></div>Alex · CEO</div>
        <div class="advisor-pill"><div class="dot" style="background:#34d399"></div>Jordan · COO</div>
        <div class="advisor-pill"><div class="dot" style="background:#facc15"></div>Morgan · CFO</div>
        <div class="advisor-pill"><div class="dot" style="background:#f472b6"></div>Taylor · CMO</div>
        <div class="advisor-pill"><div class="dot" style="background:#fb923c"></div>Riley · CTO</div>
    </div>
</header>

<div id="chat">
    <div class="welcome">
        <div class="welcome-icon">🎙</div>
        <h2>The board is ready</h2>
        <p>Ask anything — all five advisors will respond with their perspective instantly.</p>
    </div>
</div>

<div class="input-bar">
    <div class="input-wrap">
        <textarea id="input" rows="1" placeholder="Ask your board a question…"></textarea>
        <button class="send-btn" id="send-btn" onclick="sendMessage()">↑</button>
    </div>
    <div class="input-hint">Press Enter to send · Shift+Enter for new line</div>
</div>

<script>
const ADVISORS = [
    { id: 'ceo_advisor', name: 'Alex', role: 'CEO Advisor', color: '#60a5fa' },
    { id: 'coo_advisor', name: 'Jordan', role: 'COO Advisor', color: '#34d399' },
    { id: 'cfo_advisor', name: 'Morgan', role: 'CFO Advisor', color: '#facc15' },
    { id: 'cmo_advisor', name: 'Taylor', role: 'CMO Advisor', color: '#f472b6' },
    { id: 'cto_advisor', name: 'Riley', role: 'CTO Advisor', color: '#fb923c' },
];

let history = [];
let busy = false;

const chat = document.getElementById('chat');
const input = document.getElementById('input');
const sendBtn = document.getElementById('send-btn');

// Auto-resize textarea
input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 140) + 'px';
});

input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});

function scrollBottom() {
    chat.scrollTop = chat.scrollHeight;
}

function addUserMsg(text) {
    // Remove welcome screen on first message
    const welcome = chat.querySelector('.welcome');
    if (welcome) welcome.remove();

    const div = document.createElement('div');
    div.className = 'msg-user';
    div.innerHTML = `<div class="bubble">${text.replace(/\\n/g,'<br>')}</div>`;
    chat.appendChild(div);
    scrollBottom();
}

function addThinkingCards() {
    const wrap = document.createElement('div');
    wrap.className = 'responses';
    wrap.innerHTML = `<div class="responses-label">Board responding…</div>
        <div class="responses-grid" id="responses-grid">
            ${ADVISORS.map(a => `
            <div class="advisor-card thinking" id="card-${a.id}">
                <div class="card-header">
                    <div class="card-avatar" style="background:${a.color}">${a.role.slice(0,3)}</div>
                    <div>
                        <div class="card-name">${a.name}</div>
                        <div class="card-role">${a.role}</div>
                    </div>
                </div>
                <div class="card-body">
                    <div class="skeleton s1"></div>
                    <div class="skeleton s2"></div>
                    <div class="skeleton s3"></div>
                </div>
            </div>`).join('')}
        </div>`;
    chat.appendChild(wrap);
    scrollBottom();
    return wrap;
}

function fillCard(advisorId, text) {
    const card = document.getElementById('card-' + advisorId);
    if (!card) return;
    card.classList.remove('thinking');
    card.querySelector('.card-body').textContent = text;
    scrollBottom();
}

async function sendMessage() {
    const text = input.value.trim();
    if (!text || busy) return;

    busy = true;
    sendBtn.disabled = true;
    input.value = '';
    input.style.height = 'auto';

    addUserMsg(text);
    const wrap = addThinkingCards();

    // Add user turn to history
    history.push({ role: 'user', content: text });

    try {
        const res = await fetch('/api/meeting', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, history: history.slice(0, -1) })
        });
        const data = await res.json();

        // Build combined assistant content for memory (use CEO reply as representative)
        const firstReply = Object.values(data)[0]?.reply || '';
        history.push({ role: 'assistant', content: firstReply });

        // Fill each card
        ADVISORS.forEach(a => {
            const reply = data[a.id]?.reply || 'No response.';
            fillCard(a.id, reply);
        });

        // Update label
        wrap.querySelector('.responses-label').textContent = 'Board responded';
    } catch (err) {
        wrap.querySelector('.responses-label').textContent = 'Error — please try again';
        console.error(err);
    }

    busy = false;
    sendBtn.disabled = false;
    input.focus();
}
</script>
</body>
</html>
"""


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    init_db()
    emails = get_all_emails()
    stats = get_stats()
    return render_template_string(DASHBOARD_HTML, emails=emails, stats=stats)


@app.route("/meeting")
def meeting():
    return render_template_string(MEETING_HTML)


@app.route("/api/meeting", methods=["POST"])
def meeting_chat():
    data = request.json
    message = data.get("message", "")
    history = data.get("history", [])

    messages = history + [{"role": "user", "content": message}]

    def ask_advisor(client_id, client_config):
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=client_config["system_prompt"],
            messages=messages,
        )
        return client_id, resp.content[0].text

    results = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(ask_advisor, cid, cfg): cid for cid, cfg in CLIENTS.items()}
        for future in as_completed(futures):
            client_id, reply = future.result()
            results[client_id] = {"reply": reply}

    return jsonify(results)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
