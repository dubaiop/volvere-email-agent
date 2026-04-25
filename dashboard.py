"""
Web dashboard for the Volvere Email Agent.
Runs the scheduler in a background thread and serves a modern interactive UI.
"""

import json
import re
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

        header { padding: 14px 28px; background: var(--surface);
                 border-bottom: 1px solid var(--border);
                 display: flex; align-items: center; gap: 16px; flex-shrink: 0; }
        .back-btn { background: var(--surface2); border: 1px solid var(--border);
                    border-radius: 8px; padding: 6px 12px; color: var(--muted);
                    font-size: 12px; cursor: pointer; text-decoration: none;
                    transition: all .2s; white-space: nowrap; }
        .back-btn:hover { border-color: var(--accent); color: var(--text); }
        .meeting-title { display: flex; align-items: center; gap: 8px; }
        .rec-dot { width: 7px; height: 7px; background: #f87171; border-radius: 50%;
                   animation: blink 1.5s infinite; flex-shrink: 0; }
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:.2} }
        .meeting-title h1 { font-size: 15px; font-weight: 600; }
        .meeting-title span { font-size: 11px; color: var(--muted); }

        /* Seats strip */
        .seats-strip { display: flex; gap: 10px; padding: 16px 28px;
                       border-bottom: 1px solid var(--border); flex-shrink: 0;
                       overflow-x: auto; }

        .seat { background: var(--surface); border: 1.5px solid var(--border);
                border-radius: 14px; padding: 14px 16px; min-width: 158px;
                display: flex; flex-direction: column; gap: 8px;
                transition: all .3s; position: relative; overflow: hidden; }
        .seat.idle    { opacity: .65; }
        .seat.listening { opacity: 1; }
        .seat.listening::after { content:''; position:absolute; inset:0;
            background:linear-gradient(135deg,rgba(108,99,255,.05),transparent);
            animation:breathe 2s ease-in-out infinite; }
        @keyframes breathe { 0%,100%{opacity:0} 50%{opacity:1} }
        .seat.hand-raised { opacity:1; animation:glow 2s ease-in-out infinite; }
        @keyframes glow {
            0%,100%{box-shadow:0 0 0 0 rgba(108,99,255,0)}
            50%     {box-shadow:0 0 20px 3px rgba(108,99,255,.4)}
        }
        .seat.silent   { opacity: .3; }
        .seat.speaking { opacity: 1; }

        .seat-top { display:flex; align-items:center; gap:9px; }
        .seat-avatar { width:32px; height:32px; border-radius:50%; flex-shrink:0;
                       display:flex; align-items:center; justify-content:center;
                       font-size:10px; font-weight:800; color:#0f0f13; }
        .seat-name  { font-size:13px; font-weight:600; }
        .seat-label { font-size:10px; color:var(--muted); }
        .seat-status { font-size:11px; color:var(--muted); min-height:16px;
                       display:flex; align-items:center; gap:5px; }
        .status-dot { width:5px; height:5px; border-radius:50%; flex-shrink:0; }
        .seat-teaser { font-size:11px; color:var(--text); line-height:1.4;
                       display:none; font-style:italic; }
        .hand-raised .seat-teaser { display:block; }
        .floor-btn { background:linear-gradient(135deg,var(--accent),var(--accent2));
                     border:none; border-radius:8px; padding:6px 12px;
                     color:white; font-size:11px; font-weight:600;
                     cursor:pointer; display:none; transition:opacity .2s; }
        .floor-btn:hover { opacity:.85; }
        .hand-raised .floor-btn { display:block; }
        .speaking .floor-btn { display:none; }

        .listen-dots span { animation:dotbounce 1.2s infinite; display:inline-block; }
        .listen-dots span:nth-child(2){animation-delay:.2s}
        .listen-dots span:nth-child(3){animation-delay:.4s}
        @keyframes dotbounce{0%,80%,100%{opacity:.2}40%{opacity:1}}

        /* Transcript */
        #transcript { flex:1; overflow-y:auto; padding:20px 28px;
                      display:flex; flex-direction:column; gap:16px; }
        .welcome { text-align:center; padding:48px 20px; color:var(--muted); }
        .welcome-icon { font-size:40px; margin-bottom:12px; }
        .welcome h2 { font-size:18px; font-weight:600; color:var(--text); margin-bottom:6px; }
        .welcome p  { font-size:13px; max-width:380px; margin:0 auto; line-height:1.6; }

        .msg-user { display:flex; justify-content:flex-end; }
        .user-bubble { background:linear-gradient(135deg,var(--accent),var(--accent2));
                       color:white; border-radius:18px 18px 4px 18px;
                       padding:11px 16px; max-width:65%; font-size:14px; line-height:1.6; }

        .advisor-entry { display:flex; flex-direction:column; gap:0;
                         border-left:2px solid; padding-left:14px;
                         animation:fadeIn .3s ease; }
        @keyframes fadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
        .entry-header { display:flex; align-items:center; gap:8px; margin-bottom:8px; }
        .entry-avatar { width:24px; height:24px; border-radius:50%;
                        display:flex; align-items:center; justify-content:center;
                        font-size:9px; font-weight:800; color:#0f0f13; flex-shrink:0; }
        .entry-name { font-size:13px; font-weight:600; }
        .entry-role { font-size:11px; color:var(--muted); }
        .entry-text { font-size:13px; line-height:1.75; color:var(--text); white-space:pre-wrap; }

        /* Input */
        .input-bar { padding:16px 28px; border-top:1px solid var(--border);
                     background:var(--surface); flex-shrink:0; }
        .input-wrap { display:flex; gap:10px; align-items:flex-end;
                      max-width:860px; margin:0 auto; }
        #msg-input { flex:1; background:var(--surface2); border:1px solid var(--border);
                 border-radius:12px; padding:11px 14px; color:var(--text);
                 font-size:14px; font-family:inherit; outline:none; resize:none;
                 line-height:1.5; max-height:120px; transition:border-color .2s; }
        #msg-input:focus { border-color:var(--accent); }
        #msg-input::placeholder { color:var(--muted); }
        .send-btn { background:linear-gradient(135deg,var(--accent),var(--accent2));
                    border:none; border-radius:12px; width:42px; height:42px;
                    display:flex; align-items:center; justify-content:center;
                    cursor:pointer; font-size:18px; flex-shrink:0; transition:opacity .2s; }
        .send-btn:hover{opacity:.85} .send-btn:disabled{opacity:.35;cursor:not-allowed}
        .input-hint { text-align:center; font-size:11px; color:var(--muted); margin-top:8px; }
    </style>
</head>
<body>

<header>
    <a href="/" class="back-btn">← Dashboard</a>
    <div class="meeting-title">
        <div class="rec-dot"></div>
        <h1>Board Meeting</h1>
        <span>5 advisors present</span>
    </div>
</header>

<div class="seats-strip" id="seats-strip"></div>

<div id="transcript">
    <div class="welcome">
        <div class="welcome-icon">🎙</div>
        <h2>The board is listening</h2>
        <p>Speak your mind. Advisors who have something relevant will raise their hand — you decide who gets the floor.</p>
    </div>
</div>

<div class="input-bar">
    <div class="input-wrap">
        <textarea id="msg-input" rows="1" placeholder="Say something to the board…"></textarea>
        <button class="send-btn" id="send-btn" onclick="sendMessage()">↑</button>
    </div>
    <div class="input-hint">Press Enter to send · Shift+Enter for new line</div>
</div>

<script>
const ADVISORS = [
    { id: 'ceo_advisor', name: 'Alex',   role: 'CEO Advisor', color: '#60a5fa' },
    { id: 'coo_advisor', name: 'Jordan', role: 'COO Advisor', color: '#34d399' },
    { id: 'cfo_advisor', name: 'Morgan', role: 'CFO Advisor', color: '#facc15' },
    { id: 'cmo_advisor', name: 'Taylor', role: 'CMO Advisor', color: '#f472b6' },
    { id: 'cto_advisor', name: 'Riley',  role: 'CTO Advisor', color: '#fb923c' },
];

const advisorState = {};
const advisorData  = {};
ADVISORS.forEach(a => { advisorState[a.id] = 'idle'; advisorData[a.id] = null; });

let history = [];
let busy = false;
let round = 0;

const transcript = document.getElementById('transcript');
const msgInput   = document.getElementById('msg-input');
const sendBtn    = document.getElementById('send-btn');

function renderSeats() {
    document.getElementById('seats-strip').innerHTML = ADVISORS.map(a => `
        <div class="seat idle" id="seat-${a.id}">
            <div class="seat-top">
                <div class="seat-avatar" style="background:${a.color}">${a.role.slice(0,3)}</div>
                <div>
                    <div class="seat-name">${a.name}</div>
                    <div class="seat-label">${a.role}</div>
                </div>
            </div>
            <div class="seat-status" id="status-${a.id}">
                <div class="status-dot" style="background:${a.color}"></div>Ready
            </div>
            <div class="seat-teaser" id="teaser-${a.id}"></div>
            <button class="floor-btn" onclick="giveFloor('${a.id}')">Give floor →</button>
        </div>
    `).join('');
}

function setSeatState(id, state) {
    advisorState[id] = state;
    const seat   = document.getElementById('seat-' + id);
    const status = document.getElementById('status-' + id);
    const teaser = document.getElementById('teaser-' + id);
    const a      = ADVISORS.find(x => x.id === id);
    seat.className = 'seat ' + state.replace('_', '-');
    switch(state) {
        case 'idle':
            status.innerHTML = `<div class="status-dot" style="background:${a.color}"></div>Ready`;
            teaser.textContent = ''; break;
        case 'listening':
            status.innerHTML = '<span class="listen-dots"><span>•</span><span>•</span><span>•</span></span>';
            teaser.textContent = ''; break;
        case 'hand_raised':
            status.innerHTML = '✋ Wants to speak';
            teaser.textContent = advisorData[id]?.teaser || ''; break;
        case 'silent':
            status.innerHTML = '<div class="status-dot" style="background:var(--muted)"></div>Listening';
            teaser.textContent = ''; break;
        case 'speaking':
            status.innerHTML = '🎙 Speaking';
            teaser.textContent = ''; break;
    }
}

function addUserBubble(text) {
    document.querySelector('.welcome')?.remove();
    const div = document.createElement('div');
    div.className = 'msg-user';
    div.innerHTML = `<div class="user-bubble">${text.replace(/
/g,'<br>')}</div>`;
    transcript.appendChild(div);
    transcript.scrollTop = transcript.scrollHeight;
}

function giveFloor(id) {
    if (advisorState[id] !== 'hand_raised') return;
    setSeatState(id, 'speaking');
    const a    = ADVISORS.find(x => x.id === id);
    const data = advisorData[id];
    if (!data?.response) return;

    const entryId = `entry-${id}-${round}`;
    if (document.getElementById(entryId)) {
        document.getElementById(entryId).scrollIntoView({behavior:'smooth'});
        return;
    }
    const div = document.createElement('div');
    div.className = 'advisor-entry';
    div.id = entryId;
    div.style.borderLeftColor = a.color;
    div.innerHTML = `
        <div class="entry-header">
            <div class="entry-avatar" style="background:${a.color}">${a.role.slice(0,3)}</div>
            <div><div class="entry-name">${a.name}</div><div class="entry-role">${a.role}</div></div>
        </div>
        <div class="entry-text">${data.response}</div>`;
    transcript.appendChild(div);
    transcript.scrollTop = transcript.scrollHeight;

    // Save to history once
    if (!history.find(h => h.role === 'assistant' && h.content === data.response)) {
        history.push({ role: 'assistant', content: data.response });
        if (history.length > 8) history = history.slice(-8);
    }
}

async function sendMessage() {
    const text = msgInput.value.trim();
    if (!text || busy) return;
    busy = true; sendBtn.disabled = true;
    msgInput.value = ''; msgInput.style.height = 'auto';
    round++;

    addUserBubble(text);
    ADVISORS.forEach(a => setSeatState(a.id, 'listening'));
    history.push({ role: 'user', content: text });

    try {
        const res = await fetch('/api/meeting', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, history: history.slice(0, -1) })
        });
        const data = await res.json();

        let anyRaised = false;
        ADVISORS.forEach(a => {
            const val = data[a.id];
            advisorData[a.id] = val || null;
            if (val?.wants_to_speak) { setSeatState(a.id, 'hand_raised'); anyRaised = true; }
            else setSeatState(a.id, 'silent');
        });
        // Fallback: if nobody raised hand show all
        if (!anyRaised) ADVISORS.forEach(a => { if(data[a.id]) setSeatState(a.id, 'hand_raised'); });

    } catch(err) {
        ADVISORS.forEach(a => setSeatState(a.id, 'idle'));
        console.error(err);
    }
    busy = false; sendBtn.disabled = false; msgInput.focus();
}

msgInput.addEventListener('input', () => {
    msgInput.style.height = 'auto';
    msgInput.style.height = Math.min(msgInput.scrollHeight, 120) + 'px';
});
msgInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});

renderSeats();
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


MEETING_SUFFIX = (
    "\n\nYou are attending a live board meeting. The founder just spoke. "
    "Decide honestly whether their message is relevant to your specific domain of expertise. "
    "Respond ONLY with valid JSON — no extra text, no markdown:\n"
    '{"wants_to_speak": true, "teaser": "one short sentence hinting at your advice", "response": "your full advice in plain prose"}\n'
    "or if not relevant to your domain:\n"
    '{"wants_to_speak": false, "teaser": "", "response": ""}\n'
    "Be selective. Only raise your hand if you genuinely have something useful to add."
)


def parse_advisor_json(raw):
    try:
        return json.loads(raw)
    except Exception:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
    return {"wants_to_speak": True, "teaser": "I have thoughts on this.", "response": raw}


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
            max_tokens=700,
            system=client_config["system_prompt"] + MEETING_SUFFIX,
            messages=messages,
        )
        return client_id, parse_advisor_json(resp.content[0].text.strip())

    results = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(ask_advisor, cid, cfg): cid for cid, cfg in CLIENTS.items()}
        for future in as_completed(futures):
            client_id, parsed = future.result()
            results[client_id] = parsed

    return jsonify(results)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
