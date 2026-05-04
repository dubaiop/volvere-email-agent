"""
Web dashboard for the Volvere Email Agent.
Runs the scheduler in a background thread and serves a modern interactive UI.
"""

import json
import os
import re
import threading
import schedule
import time
import anthropic
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, render_template_string, jsonify, request
from database import get_all_emails, get_stats, init_db, get_setting, set_setting
from integrations import ALL_TOOLS, TOOL_FUNCTIONS
from config import CLIENTS, CLAUDE_MODEL

app = Flask(__name__)


def run_scheduler():
    from main import run
    run()
    schedule.every(5).minutes.do(run)
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
        <a href="/operations" class="meeting-btn" style="background:linear-gradient(135deg,#059669,#34d399)">⚙️ Operations</a>
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
            onclick="openModal({{ e.id }})">
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

    const EMAIL_DATA = {{ emails | tojson }};
    const EMAIL_MAP = {};
    EMAIL_DATA.forEach(e => { EMAIL_MAP[e.id] = e; });

    function openModal(id) {
        const e = EMAIL_MAP[id];
        if (!e) return;
        const role = e.client_name.split(' ')[0].toLowerCase();
        document.getElementById('modal-badge').innerHTML = `<span class="badge badge-${role}"><span class="badge-dot"></span>${e.client_name}</span>`;
        document.getElementById('modal-subject').textContent = e.subject;
        document.getElementById('modal-sender').textContent = e.sender;
        document.getElementById('modal-time').textContent = e.processed_at;
        document.getElementById('modal-reply').textContent = e.reply;
        document.getElementById('modal-body-text').textContent = e.body;
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

<div class="seats-strip" id="seats-strip">
{% for a in advisors %}
<div class="seat idle" id="seat-{{ a.id }}">
    <div class="seat-top">
        <div class="seat-avatar" style="background:{{ a.color }}">{{ a.role[:3] }}</div>
        <div>
            <div class="seat-name">{{ a.name }}</div>
            <div class="seat-label">{{ a.role }}</div>
        </div>
    </div>
    <div class="seat-status" id="status-{{ a.id }}">
        <div class="status-dot" style="background:{{ a.color }}"></div>Ready
    </div>
    <div class="seat-teaser" id="teaser-{{ a.id }}"></div>
    <button class="floor-btn" id="floor-{{ a.id }}" onclick="giveFloor('{{ a.id }}')">Give floor &rarr;</button>
</div>
{% endfor %}
</div>

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

// seats rendered server-side

function setSeatState(id, state) {
    advisorState[id] = state;
    const seat   = document.getElementById('seat-' + id);
    const status = document.getElementById('status-' + id);
    const teaser = document.getElementById('teaser-' + id);
    const a      = ADVISORS.find(x => x.id === id);
    if (!seat || !status || !teaser || !a) return; // guard against missing elements
    seat.className = 'seat ' + state.replace('_', '-');
    switch(state) {
        case 'idle':
            status.innerHTML = '<div class="status-dot" style="background:' + a.color + '"></div>Ready';
            teaser.textContent = ''; break;
        case 'listening':
            status.innerHTML = '<span class="listen-dots"><span>•</span><span>•</span><span>•</span></span>';
            teaser.textContent = ''; break;
        case 'hand_raised':
            status.innerHTML = '✋ Wants to speak';
            teaser.textContent = (advisorData[id] && advisorData[id].teaser) || ''; break;
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
    div.innerHTML = '<div class="user-bubble">' + text.split('\\n').join('<br>') + '</div>';
    transcript.appendChild(div);
    transcript.scrollTop = transcript.scrollHeight;
}

function giveFloor(id) {
    if (advisorState[id] !== 'hand_raised') return;
    setSeatState(id, 'speaking');
    const a    = ADVISORS.find(x => x.id === id);
    const data = advisorData[id];
    if (!data) return;

    const responseText = data.response || data.teaser || 'Hello! Ask me something specific and I will give you my full take.';

    const entryId = 'entry-' + id + '-' + round;
    if (document.getElementById(entryId)) {
        document.getElementById(entryId).scrollIntoView({behavior:'smooth'});
        return;
    }
    const div = document.createElement('div');
    div.className = 'advisor-entry';
    div.id = entryId;
    div.style.borderLeftColor = a.color;
    div.innerHTML = '<div class="entry-header">'
        + '<div class="entry-avatar" style="background:' + a.color + '">' + a.role.slice(0,3) + '</div>'
        + '<div><div class="entry-name">' + a.name + '</div><div class="entry-role">' + a.role + '</div></div>'
        + '</div>'
        + '<div class="entry-text">' + responseText + '</div>';
    transcript.appendChild(div);
    transcript.scrollTop = transcript.scrollHeight;

    if (responseText && !history.find(function(h) { return h.role === 'assistant' && h.content === responseText; })) {
        history.push({ role: 'assistant', content: responseText });
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
    history.push({ role: 'user', content: text });

    try {
        ADVISORS.forEach(a => setSeatState(a.id, 'listening'));

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
            if (val && val.wants_to_speak) { setSeatState(a.id, 'hand_raised'); anyRaised = true; }
            else setSeatState(a.id, 'silent');
        });
        if (!anyRaised) ADVISORS.forEach(a => { if(data[a.id]) setSeatState(a.id, 'hand_raised'); });

    } catch(err) {
        ADVISORS.forEach(a => setSeatState(a.id, 'idle'));
        console.error(err);
    } finally {
        busy = false; sendBtn.disabled = false; msgInput.focus();
    }
}

msgInput.addEventListener('input', () => {
    msgInput.style.height = 'auto';
    msgInput.style.height = Math.min(msgInput.scrollHeight, 120) + 'px';
});
msgInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});
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


MEETING_ADVISORS = [
    {"id": "ceo_advisor", "name": "Alex",   "role": "CEO Advisor", "color": "#60a5fa"},
    {"id": "coo_advisor", "name": "Jordan", "role": "COO Advisor", "color": "#34d399"},
    {"id": "cfo_advisor", "name": "Morgan", "role": "CFO Advisor", "color": "#facc15"},
    {"id": "cmo_advisor", "name": "Taylor", "role": "CMO Advisor", "color": "#f472b6"},
    {"id": "cto_advisor", "name": "Riley",  "role": "CTO Advisor", "color": "#fb923c"},
]

@app.route("/meeting")
def meeting():
    return render_template_string(MEETING_HTML, advisors=MEETING_ADVISORS)


MEETING_SUFFIX = (
    "\n\nYou are attending a live board meeting. The founder just spoke. "
    "Decide honestly whether their message is relevant to your specific domain of expertise. "
    "Respond ONLY with valid JSON — no extra text, no markdown:\n"
    '{"wants_to_speak": true, "teaser": "one short sentence hinting at your advice", "response": "your full advice in 2-4 sentences of plain prose"}\n'
    "or if not relevant to your domain:\n"
    '{"wants_to_speak": false, "teaser": "", "response": ""}\n'
    "IMPORTANT: If wants_to_speak is true, response MUST be non-empty — always give substantive advice. "
    "Even for a greeting, introduce yourself and ask what you can help with today."
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


GTM_SYSTEM_PROMPT = """You are Sam, a Go-to-Market (GTM) Engineer. You are an EXECUTOR, not an advisor. You do the work, you do not tell people how to do it.

When someone gives you a task, you produce the actual deliverable — ready to copy, paste, and use immediately. Never say "you should..." or "I recommend..." — just do it.

What you actually produce:
- Complete cold email sequences (subject lines, body, follow-ups) — ready to send
- Full ICP (Ideal Customer Profile) documents with specific criteria, personas, and targeting
- Prospect research on specific companies — real info, actionable intel
- CRM pipeline stages, deal fields, and automation rules — written out precisely
- LinkedIn outreach scripts — complete messages, not templates
- Landing page copy — headline, subheadline, bullets, CTA — complete and ready
- GTM playbooks — step-by-step execution plans with exact actions, tools, and timelines
- Competitive analysis — what each competitor does, where the gap is, how to position against them
- Sales scripts — full conversation flows with objection handling
- Onboarding sequences — emails, tasks, milestones

You use web_search to find real, current information about companies, markets, and competitors before producing any research deliverable.

Rules:
- Always produce the actual output, not instructions on how to create it
- Be specific — name the tools, write the copy, set the numbers
- Format deliverables clearly so they can be used immediately
- If you need to research something, search first, then produce the deliverable with real data
- Sign off as: Sam — GTM Engineer"""


SAM_AVATAR_SM = """<svg viewBox="0 0 36 36" xmlns="http://www.w3.org/2000/svg">
  <rect width="36" height="36" rx="10" fill="#064e3b"/>
  <!-- body / shirt -->
  <rect x="8" y="24" width="20" height="12" rx="4" fill="#059669"/>
  <rect x="13" y="23" width="10" height="5" fill="#065f46"/>
  <!-- neck -->
  <rect x="14" y="19" width="8" height="6" rx="2" fill="#fcd5b0"/>
  <!-- head -->
  <ellipse cx="18" cy="15" rx="8" ry="8.5" fill="#fcd5b0"/>
  <!-- hair -->
  <ellipse cx="18" cy="8" rx="8" ry="5" fill="#1c1917"/>
  <rect x="10" y="8" width="3" height="6" rx="1.5" fill="#1c1917"/>
  <rect x="23" y="8" width="3" height="6" rx="1.5" fill="#1c1917"/>
  <!-- eyes -->
  <ellipse cx="14.5" cy="15" rx="1.3" ry="1.5" fill="#1c1917"/>
  <ellipse cx="21.5" cy="15" rx="1.3" ry="1.5" fill="#1c1917"/>
  <!-- eye shine -->
  <circle cx="15" cy="14.4" r="0.4" fill="white"/>
  <circle cx="22" cy="14.4" r="0.4" fill="white"/>
  <!-- nose -->
  <ellipse cx="18" cy="17.5" rx="1" ry="0.6" fill="#e8b48a"/>
  <!-- smile -->
  <path d="M15 19.5 Q18 21.5 21 19.5" stroke="#c08060" stroke-width="0.8" fill="none" stroke-linecap="round"/>
  <!-- collar -->
  <polygon points="15,23 18,26 21,23" fill="white" opacity="0.9"/>
</svg>"""

SAM_AVATAR_LG = """<svg viewBox="0 0 44 44" xmlns="http://www.w3.org/2000/svg">
  <rect width="44" height="44" rx="12" fill="#064e3b"/>
  <!-- body -->
  <rect x="9" y="30" width="26" height="14" rx="5" fill="#059669"/>
  <rect x="16" y="28" width="12" height="6" fill="#065f46"/>
  <!-- neck -->
  <rect x="17" y="23" width="10" height="7" rx="2" fill="#fcd5b0"/>
  <!-- head -->
  <ellipse cx="22" cy="18" rx="10" ry="10.5" fill="#fcd5b0"/>
  <!-- hair -->
  <ellipse cx="22" cy="10" rx="10" ry="6" fill="#1c1917"/>
  <rect x="12" y="10" width="4" height="7" rx="2" fill="#1c1917"/>
  <rect x="28" y="10" width="4" height="7" rx="2" fill="#1c1917"/>
  <!-- eyes -->
  <ellipse cx="17.5" cy="18" rx="1.6" ry="1.8" fill="#1c1917"/>
  <ellipse cx="26.5" cy="18" rx="1.6" ry="1.8" fill="#1c1917"/>
  <circle cx="18.1" cy="17.3" r="0.5" fill="white"/>
  <circle cx="27.1" cy="17.3" r="0.5" fill="white"/>
  <!-- nose -->
  <ellipse cx="22" cy="21" rx="1.2" ry="0.7" fill="#e8b48a"/>
  <!-- smile -->
  <path d="M18.5 23.5 Q22 26 25.5 23.5" stroke="#c08060" stroke-width="1" fill="none" stroke-linecap="round"/>
  <!-- collar -->
  <polygon points="18,28 22,32 26,28" fill="white" opacity="0.9"/>
</svg>"""


OPERATIONS_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Volvere — Operations Agents</title>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        :root {
            --bg: #0f0f13; --surface: #1a1a24; --surface2: #22222f;
            --border: #2e2e3e; --accent: #059669; --accent2: #34d399;
            --text: #e8e8f0; --muted: #6b6b80;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               background: var(--bg); color: var(--text); min-height: 100vh; display: flex; flex-direction: column; }

        header { padding: 20px 40px; display: flex; align-items: center;
                 justify-content: space-between; border-bottom: 1px solid var(--border);
                 background: var(--surface); }
        .logo { display: flex; align-items: center; gap: 12px; }
        .logo-icon { width: 36px; height: 36px;
                     background: linear-gradient(135deg, var(--accent), var(--accent2));
                     border-radius: 10px; display: flex; align-items: center;
                     justify-content: center; font-size: 18px; }
        .logo h1 { font-size: 18px; font-weight: 600; }
        .logo span { font-size: 12px; color: var(--muted); }
        .nav-links { display: flex; gap: 12px; }
        .nav-btn { display: flex; align-items: center; gap: 6px; padding: 8px 16px;
                   border-radius: 8px; border: 1px solid var(--border); background: var(--surface2);
                   color: var(--text); font-size: 13px; font-weight: 500; text-decoration: none;
                   transition: border-color 0.2s; }
        .nav-btn:hover { border-color: var(--accent2); }

        .page-wrap { display: flex; flex: 1; overflow: hidden; }

        /* Sidebar */
        .sidebar { width: 260px; border-right: 1px solid var(--border); background: var(--surface);
                   padding: 24px 16px; display: flex; flex-direction: column; gap: 8px; flex-shrink: 0; }
        .sidebar-title { font-size: 11px; font-weight: 600; color: var(--muted);
                         letter-spacing: 1px; text-transform: uppercase; padding: 0 8px 8px; }
        .agent-btn { display: flex; align-items: center; gap: 12px; padding: 12px;
                     border-radius: 10px; cursor: pointer; transition: background 0.15s;
                     border: 1px solid transparent; }
        .agent-btn:hover { background: var(--surface2); }
        .agent-btn.active { background: var(--surface2); border-color: var(--accent); }
        .agent-icon { width: 36px; height: 36px; border-radius: 10px; display: flex;
                      align-items: center; justify-content: center; font-size: 18px; flex-shrink: 0;
                      overflow: hidden; }
        .agent-icon img, .agent-icon svg { width: 100%; height: 100%; object-fit: cover; border-radius: 10px; }
        .agent-name { font-size: 14px; font-weight: 600; }
        .agent-tag { font-size: 11px; color: var(--muted); margin-top: 1px; }
        .coming-soon { opacity: 0.4; cursor: default; }
        .coming-soon:hover { background: transparent; }
        .cs-badge { font-size: 10px; background: var(--surface2); border: 1px solid var(--border);
                    padding: 2px 6px; border-radius: 4px; color: var(--muted); margin-left: auto; }

        /* Chat area */
        .chat-wrap { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
        .agent-header { padding: 20px 32px; border-bottom: 1px solid var(--border);
                        background: var(--surface); display: flex; align-items: center; gap: 16px; }
        .agent-header-icon { width: 44px; height: 44px; border-radius: 12px;
                             background: linear-gradient(135deg, #059669, #34d399);
                             display: flex; align-items: center; justify-content: center; font-size: 22px; }
        .agent-header-info h2 { font-size: 17px; font-weight: 600; }
        .agent-header-info p { font-size: 13px; color: var(--muted); margin-top: 2px; }
        .online-dot { width: 8px; height: 8px; background: #34d399; border-radius: 50%;
                      animation: pulse 2s infinite; margin-left: auto; }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }

        .messages { flex: 1; overflow-y: auto; padding: 24px 32px; display: flex;
                    flex-direction: column; gap: 20px; }
        .msg { display: flex; gap: 12px; max-width: 780px; }
        .msg.user { flex-direction: row-reverse; align-self: flex-end; }
        .msg-avatar { width: 34px; height: 34px; border-radius: 10px; flex-shrink: 0;
                      display: flex; align-items: center; justify-content: center; font-size: 16px; }
        .msg.agent .msg-avatar { background: linear-gradient(135deg, #059669, #34d399); }
        .msg.user .msg-avatar { background: var(--surface2); border: 1px solid var(--border); }
        .msg-bubble { background: var(--surface); border: 1px solid var(--border);
                      border-radius: 14px; padding: 14px 18px; font-size: 14px;
                      line-height: 1.65; white-space: pre-wrap; }
        .msg.user .msg-bubble { background: var(--surface2); }
        .msg-name { font-size: 11px; color: var(--muted); margin-bottom: 4px; font-weight: 500; }

        .typing { display: none; align-items: center; gap: 6px; padding: 8px 32px; flex-shrink: 0; flex-direction: row; white-space: nowrap; }
        .typing.show { display: flex; }
        .typing-dots { display: flex; align-items: center; gap: 4px; }
        .typing span.dot { width: 7px; height: 7px; border-radius: 50%; background: var(--accent2);
                       animation: bounce 1.2s infinite; flex-shrink: 0; }
        .typing span.dot:nth-child(2) { animation-delay: 0.2s; }
        .typing span.dot:nth-child(3) { animation-delay: 0.4s; }
        @keyframes bounce { 0%,60%,100%{transform:translateY(0)} 30%{transform:translateY(-6px)} }

        .input-area { padding: 16px 32px 24px; border-top: 1px solid var(--border);
                      background: var(--surface); }
        .input-row { display: flex; gap: 10px; background: var(--surface2);
                     border: 1px solid var(--border); border-radius: 12px; padding: 4px 4px 4px 16px;
                     transition: border-color 0.2s; }
        .input-row:focus-within { border-color: var(--accent); }
        #msg-input { flex: 1; background: none; border: none; outline: none;
                     color: var(--text); font-size: 14px; padding: 10px 0;
                     font-family: inherit; resize: none; max-height: 120px; }
        #msg-input::placeholder { color: var(--muted); }
        .send-btn { background: linear-gradient(135deg, var(--accent), var(--accent2));
                    border: none; border-radius: 9px; width: 38px; height: 38px;
                    display: flex; align-items: center; justify-content: center;
                    cursor: pointer; color: white; font-size: 16px; flex-shrink: 0;
                    align-self: flex-end; margin-bottom: 2px; transition: opacity 0.2s; }
        .send-btn:hover { opacity: 0.85; }

        .welcome { text-align: center; padding: 60px 40px; color: var(--muted); }
        .welcome-icon { font-size: 48px; margin-bottom: 16px; }
        .welcome h3 { font-size: 18px; font-weight: 600; color: var(--text); margin-bottom: 8px; }
        .welcome p { font-size: 14px; line-height: 1.6; max-width: 480px; margin: 0 auto; }
        .suggestions { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-top: 20px; }
        .suggestion { background: var(--surface2); border: 1px solid var(--border);
                      border-radius: 8px; padding: 8px 14px; font-size: 13px; cursor: pointer;
                      transition: border-color 0.2s; }
        .suggestion:hover { border-color: var(--accent2); color: var(--text); }

        /* Markdown rendering */
        .msg-bubble h1,.msg-bubble h2,.msg-bubble h3 { font-size:14px; font-weight:700; margin:14px 0 6px; color:var(--accent2); }
        .msg-bubble h1 { font-size:16px; }
        .msg-bubble p { margin:6px 0; }
        .msg-bubble ul,.msg-bubble ol { padding-left:20px; margin:6px 0; }
        .msg-bubble li { margin:3px 0; }
        .msg-bubble strong { color:var(--text); font-weight:600; }
        .msg-bubble em { color:var(--accent2); font-style:italic; }
        .msg-bubble hr { border:none; border-top:1px solid var(--border); margin:12px 0; }
        .msg-bubble blockquote { border-left:3px solid var(--accent); padding:4px 12px; margin:8px 0; color:var(--muted); font-style:italic; }
        .msg-bubble code { background:var(--surface2); padding:1px 5px; border-radius:4px; font-family:monospace; font-size:12px; }
        .msg-bubble pre { background:var(--surface2); padding:12px; border-radius:8px; overflow-x:auto; margin:8px 0; }
        .msg-bubble pre code { background:none; padding:0; }
        .msg-bubble a { color:var(--accent2); }
    </style>
</head>
<body>
<header>
    <div class="logo">
        <div class="logo-icon">⚙️</div>
        <div>
            <h1>Operations Agents</h1>
            <span>Specialized AI operators</span>
        </div>
    </div>
    <div class="nav-links">
        <button class="nav-btn" onclick="openSettings()" style="cursor:pointer;">⚙️ Settings</button>
        <a href="/api-docs" class="nav-btn">🔑 API Docs</a>
        <a href="/" class="nav-btn">📧 Email Dashboard</a>
        <a href="/meeting" class="nav-btn">🎙 Board Meeting</a>
    </div>
</header>

<!-- Integrations Modal -->
<div id="settings-overlay" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);backdrop-filter:blur(4px);z-index:200;align-items:flex-start;justify-content:center;overflow-y:auto;padding:40px 20px;">
    <div style="background:#1a1a24;border:1px solid #2e2e3e;border-radius:18px;width:600px;max-width:95vw;padding:32px;margin:auto;">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:28px;">
            <div>
                <div style="font-size:18px;font-weight:700;">Integrations</div>
                <div style="font-size:12px;color:#6b6b80;margin-top:3px;">Connect your tools — Sam will use these keys to do real work</div>
            </div>
            <div onclick="closeSettings()" style="cursor:pointer;width:32px;height:32px;background:#22222f;border:1px solid #2e2e3e;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#6b6b80;font-size:16px;">✕</div>
        </div>

        <!-- CRM -->
        <div style="margin-bottom:28px;">
            <div style="font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#6b6b80;margin-bottom:14px;">CRM</div>
            <div style="display:flex;flex-direction:column;gap:12px;">
                <div class="int-row"><span class="int-label">🟠 HubSpot</span><input class="int-input" data-key="hubspot_api_key" type="password" placeholder="HubSpot Private App Token"></div>
                <div class="int-row"><span class="int-label">☁️ Salesforce</span><input class="int-input" data-key="salesforce_api_key" type="password" placeholder="Salesforce Access Token"></div>
                <div class="int-row"><span class="int-label">🟣 Pipedrive</span><input class="int-input" data-key="pipedrive_api_key" type="password" placeholder="Pipedrive API Key"></div>
            </div>
        </div>

        <!-- Email Automation -->
        <div style="margin-bottom:28px;">
            <div style="font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#6b6b80;margin-bottom:14px;">Email Automation</div>
            <div style="display:flex;flex-direction:column;gap:12px;">
                <div class="int-row"><span class="int-label">🦧 Apollo</span><input class="int-input" data-key="apollo_api_key" type="password" placeholder="Apollo.io API Key"></div>
                <div class="int-row"><span class="int-label">⚡ Instantly</span><input class="int-input" data-key="instantly_api_key" type="password" placeholder="Instantly API Key"></div>
                <div class="int-row"><span class="int-label">📧 Mailchimp</span><input class="int-input" data-key="mailchimp_api_key" type="password" placeholder="Mailchimp API Key"></div>
                <div class="int-row"><span class="int-label">🔵 ActiveCampaign</span><input class="int-input" data-key="activecampaign_api_key" type="password" placeholder="ActiveCampaign API Key"></div>
            </div>
        </div>

        <!-- Analytics -->
        <div style="margin-bottom:28px;">
            <div style="font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#6b6b80;margin-bottom:14px;">Analytics</div>
            <div style="display:flex;flex-direction:column;gap:12px;">
                <div class="int-row"><span class="int-label">📊 Mixpanel</span><input class="int-input" data-key="mixpanel_api_key" type="password" placeholder="Mixpanel Project Token"></div>
                <div class="int-row"><span class="int-label">🟢 Segment</span><input class="int-input" data-key="segment_api_key" type="password" placeholder="Segment Write Key"></div>
            </div>
        </div>

        <!-- Customer Engagement -->
        <div style="margin-bottom:28px;">
            <div style="font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#6b6b80;margin-bottom:14px;">Customer Engagement</div>
            <div style="display:flex;flex-direction:column;gap:12px;">
                <div class="int-row"><span class="int-label">💬 Intercom</span><input class="int-input" data-key="intercom_api_key" type="password" placeholder="Intercom Access Token"></div>
                <div class="int-row"><span class="int-label">🎯 Klaviyo</span><input class="int-input" data-key="klaviyo_api_key" type="password" placeholder="Klaviyo Private API Key"></div>
            </div>
        </div>

        <!-- GTM API -->
        <div style="margin-bottom:28px;padding-top:20px;border-top:1px solid #2e2e3e;">
            <div style="font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#6b6b80;margin-bottom:14px;">Sam Access Key</div>
            <div class="int-row"><span class="int-label">🔑 GTM API Key</span><input class="int-input" data-key="gtm_api_key" type="password" placeholder="Key to protect Sam's API endpoint"></div>
            <div id="current-key-status" style="font-size:11px;color:#6b6b80;margin-top:6px;margin-left:140px;"></div>
        </div>

        <div style="display:flex;gap:10px;justify-content:flex-end;">
            <button onclick="closeSettings()" style="background:none;border:1px solid #2e2e3e;border-radius:8px;padding:10px 20px;color:#6b6b80;font-size:13px;cursor:pointer;">Cancel</button>
            <button onclick="saveAllKeys()" style="background:linear-gradient(135deg,#059669,#34d399);border:none;border-radius:8px;padding:10px 20px;color:white;font-size:13px;font-weight:600;cursor:pointer;">Save All</button>
        </div>
    </div>
</div>

<style>
.int-row { display:flex; align-items:center; gap:12px; }
.int-label { font-size:13px; font-weight:500; min-width:128px; flex-shrink:0; }
.int-input { flex:1; background:#22222f; border:1px solid #2e2e3e; border-radius:9px;
             padding:9px 13px; color:#e8e8f0; font-size:13px; outline:none; font-family:monospace;
             transition:border-color 0.2s; }
.int-input:focus { border-color:#059669; }
.int-input.saved { border-color:#34d399; }
</style>

<div class="page-wrap">
    <div class="sidebar">
        <div class="sidebar-title">Agents</div>

        <div class="agent-btn active" onclick="selectAgent('gtm')">
            <div class="agent-icon">{{ sam_avatar_sm | safe }}</div>
            <div>
                <div class="agent-name">Sam</div>
                <div class="agent-tag">GTM Engineer</div>
            </div>
        </div>

        <div class="agent-btn coming-soon">
            <div class="agent-icon" style="opacity:0.4">📊</div>
            <div>
                <div class="agent-name" style="color:var(--muted)">Revenue Ops</div>
                <div class="agent-tag">Coming soon</div>
            </div>
            <span class="cs-badge">Soon</span>
        </div>

        <div class="agent-btn coming-soon">
            <div class="agent-icon" style="opacity:0.4">🎯</div>
            <div>
                <div class="agent-name" style="color:var(--muted)">Sales Ops</div>
                <div class="agent-tag">Coming soon</div>
            </div>
            <span class="cs-badge">Soon</span>
        </div>

        <div class="agent-btn coming-soon">
            <div class="agent-icon" style="opacity:0.4">📈</div>
            <div>
                <div class="agent-name" style="color:var(--muted)">Growth Hacker</div>
                <div class="agent-tag">Coming soon</div>
            </div>
            <span class="cs-badge">Soon</span>
        </div>
    </div>

    <div class="chat-wrap">
        <div class="agent-header">
            <div class="agent-header-icon" style="background:none;padding:0;overflow:hidden;">{{ sam_avatar_lg | safe }}</div>
            <div class="agent-header-info">
                <h2>Sam — GTM Engineer</h2>
                <p>Go-to-Market strategy, tech stack, sales ops, growth execution</p>
            </div>
            <div class="online-dot"></div>
        </div>

        <div class="messages" id="messages">
            <div class="welcome" id="welcome">
                <div class="welcome-icon" style="display:flex;justify-content:center;"><div style="width:72px;height:72px;border-radius:18px;overflow:hidden;">{{ sam_avatar_lg | safe }}</div></div>
                <h3>Hey, I'm Sam — your GTM Engineer</h3>
                <p>I work at the intersection of strategy, technology, and execution. Ask me about CRM setup, sales automation, data pipelines, growth playbooks, or anything Go-to-Market.</p>
                <div class="suggestions">
                    <div class="suggestion" onclick="sendSuggestion(this)">Write me a 5-email cold outreach sequence for SaaS founders</div>
                    <div class="suggestion" onclick="sendSuggestion(this)">Build me a full ICP for a B2B HR tech startup</div>
                    <div class="suggestion" onclick="sendSuggestion(this)">Research HubSpot's pricing and positioning vs Salesforce</div>
                    <div class="suggestion" onclick="sendSuggestion(this)">Write a LinkedIn outreach message for a VP of Sales</div>
                </div>
            </div>
        </div>

        <div class="typing" id="typing">
            <div class="typing-dots">
                <span class="dot"></span><span class="dot"></span><span class="dot"></span>
            </div>
            <span style="font-size:12px;color:var(--muted);margin-left:4px">Sam is working on it…</span>
        </div>

        <div class="input-area">
            <div class="input-row">
                <textarea id="msg-input" placeholder="Ask Sam anything about GTM strategy, tools, or execution…" rows="1"></textarea>
                <button class="send-btn" onclick="sendMessage()">↑</button>
            </div>
        </div>
    </div>
</div>

<script>
    const SAM_SVG = {{ sam_avatar_sm | tojson }};
    let history = [];

    function selectAgent(id) {
        document.querySelectorAll('.agent-btn').forEach(b => b.classList.remove('active'));
        event.currentTarget.classList.add('active');
    }

    function sendSuggestion(el) {
        document.getElementById('msg-input').value = el.textContent;
        sendMessage();
    }

    async function sendMessage() {
        const input = document.getElementById('msg-input');
        const text = input.value.trim();
        if (!text) return;
        input.value = '';
        input.style.height = 'auto';

        document.getElementById('welcome')?.remove();
        addMessage('user', text, 'You');

        document.getElementById('typing').classList.add('show');

        history.push({ role: 'user', content: text });

        try {
            const res = await fetch('/api/gtm', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text, history: history.slice(0, -1) })
            });
            const data = await res.json();
            document.getElementById('typing').classList.remove('show');
            addMessage('agent', data.reply, 'Sam — GTM Engineer');
            history.push({ role: 'assistant', content: data.reply });
        } catch(e) {
            document.getElementById('typing').classList.remove('show');
            addMessage('agent', 'Error: ' + e.message, 'Sam');
        }
    }

    function addMessage(type, text, name) {
        const msgs = document.getElementById('messages');
        const div = document.createElement('div');
        div.className = `msg ${type}`;
        const bubbleContent = type === 'agent' ? marked.parse(text) : escapeHtml(text);
        const copyBtn = type === 'agent'
            ? `<button onclick="copyText(this, ${JSON.stringify(text)})" style="margin-top:8px;background:none;border:1px solid var(--border);border-radius:6px;padding:4px 10px;color:var(--muted);font-size:11px;cursor:pointer;">Copy</button>`
            : '';
        div.innerHTML = `
            <div class="msg-avatar" style="background:none;padding:0;overflow:hidden;border-radius:10px;">${type === 'agent' ? SAM_SVG : '👤'}</div>
            <div>
                <div class="msg-name">${name}</div>
                <div class="msg-bubble">${bubbleContent}</div>
                ${copyBtn}
            </div>`;
        msgs.appendChild(div);
        msgs.scrollTop = msgs.scrollHeight;
    }

    function copyText(btn, text) {
        navigator.clipboard.writeText(text).then(() => {
            btn.textContent = 'Copied!';
            setTimeout(() => btn.textContent = 'Copy', 1500);
        });
    }

    function escapeHtml(t) {
        return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    }

    const input = document.getElementById('msg-input');
    input.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });
    input.addEventListener('input', () => {
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 120) + 'px';
    });

    async function openSettings() {
        document.getElementById('settings-overlay').style.display = 'flex';
        const res = await fetch('/api/settings/all');
        const data = await res.json();
        document.querySelectorAll('.int-input').forEach(inp => {
            const k = inp.dataset.key;
            if (data[k]) {
                inp.placeholder = '••••••••' + data[k];
                inp.classList.add('saved');
            }
        });
    }

    function closeSettings() {
        document.getElementById('settings-overlay').style.display = 'none';
        document.querySelectorAll('.int-input').forEach(inp => inp.value = '');
    }

    async function saveAllKeys() {
        const keys = {};
        document.querySelectorAll('.int-input').forEach(inp => {
            if (inp.value.trim()) keys[inp.dataset.key] = inp.value.trim();
        });
        if (!Object.keys(keys).length) { closeSettings(); return; }
        await fetch('/api/settings/all', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(keys)
        });
        closeSettings();
        const btn = document.querySelector('button[onclick="openSettings()"]');
        btn.textContent = '✓ Saved';
        setTimeout(() => btn.textContent = '⚙️ Settings', 2000);
    }

    document.getElementById('settings-overlay').addEventListener('click', e => {
        if (e.target === document.getElementById('settings-overlay')) closeSettings();
    });
</script>
</body>
</html>
"""


@app.route("/operations")
def operations():
    return render_template_string(OPERATIONS_HTML, sam_avatar_sm=SAM_AVATAR_SM, sam_avatar_lg=SAM_AVATAR_LG)




def check_api_key():
    """Returns True if request has a valid API key (or no key is configured)."""
    api_key = get_setting("gtm_api_key") or os.environ.get("GTM_API_KEY", "")
    if not api_key:
        return True
    provided = request.headers.get("X-API-Key", "")
    if not provided and request.is_json:
        provided = request.json.get("api_key", "")
    return provided == api_key


def build_gtm_system_prompt():
    connected = [name for key, name in INTEGRATION_NAMES.items() if get_setting(key)]
    prompt = GTM_SYSTEM_PROMPT
    if connected:
        prompt += f"\n\nYou have LIVE API access to these connected tools: {', '.join(connected)}."
        prompt += "\nUse the available tools to actually execute work — don't just describe it. Call the tools, get results, report what was done."
    else:
        prompt += "\n\nNo tools connected yet. Produce detailed deliverables and let the user know they can connect tools via Settings to enable live execution."
    return prompt


def get_active_tools():
    active = []
    key_map = {
        "apollo_api_key": ["apollo_search_people", "apollo_add_to_sequence"],
        "hubspot_api_key": ["hubspot_create_contact", "hubspot_create_deal", "hubspot_get_contacts"],
        "instantly_api_key": ["instantly_get_campaigns", "instantly_add_lead"],
        "mailchimp_api_key": ["mailchimp_get_lists", "mailchimp_add_subscriber"],
        "activecampaign_api_key": ["activecampaign_create_contact"],
        "pipedrive_api_key": ["pipedrive_create_person", "pipedrive_create_deal"],
        "intercom_api_key": ["intercom_create_contact", "intercom_send_message"],
        "klaviyo_api_key": ["klaviyo_add_to_list"],
        "mixpanel_api_key": ["mixpanel_track_event"],
        "segment_api_key": ["segment_identify", "segment_track"],
    }
    enabled_names = set()
    for setting_key, tool_names in key_map.items():
        if get_setting(setting_key):
            enabled_names.update(tool_names)
    return [t for t in ALL_TOOLS if t["name"] in enabled_names]


@app.route("/api/gtm", methods=["POST"])
def gtm_chat():
    if not check_api_key():
        return jsonify({"error": "Invalid or missing API key"}), 401
    try:
        data = request.json
        message = data.get("message", "")
        history = data.get("history", [])

        messages = history + [{"role": "user", "content": message}]
        client = anthropic.Anthropic()
        active_tools = get_active_tools()
        tool_log = []

        while True:
            kwargs = dict(model=CLAUDE_MODEL, max_tokens=2048,
                         system=build_gtm_system_prompt(), messages=messages)
            if active_tools:
                kwargs["tools"] = active_tools

            resp = client.messages.create(**kwargs)

            if resp.stop_reason == "tool_use":
                tool_results = []
                for block in resp.content:
                    if block.type == "tool_use":
                        fn = TOOL_FUNCTIONS.get(block.name)
                        if fn:
                            result = fn(**block.input)
                        else:
                            result = f"Unknown tool: {block.name}"
                        tool_log.append(f"[{block.name}] {result}")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })
                messages.append({"role": "assistant", "content": resp.content})
                messages.append({"role": "user", "content": tool_results})
            else:
                reply = next((b.text for b in resp.content if hasattr(b, "text")), "")
                if tool_log:
                    reply = "**Actions executed:**\n" + "\n".join(f"- {l}" for l in tool_log) + "\n\n" + reply
                return jsonify({"reply": reply.strip(), "agent": "sam-gtm", "status": "ok"})

    except Exception as e:
        print(f"GTM chat error: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500


API_DOCS_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Volvere — API Docs</title>
    <style>
        :root { --bg:#0f0f13; --surface:#1a1a24; --surface2:#22222f; --border:#2e2e3e;
                --accent:#059669; --accent2:#34d399; --text:#e8e8f0; --muted:#6b6b80; }
        * { box-sizing:border-box; margin:0; padding:0; }
        body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
               background:var(--bg); color:var(--text); min-height:100vh; }
        header { padding:20px 40px; display:flex; align-items:center; justify-content:space-between;
                 border-bottom:1px solid var(--border); background:var(--surface); position:sticky; top:0; z-index:10; }
        .logo { display:flex; align-items:center; gap:12px; }
        .logo-icon { width:36px; height:36px; background:linear-gradient(135deg,var(--accent),var(--accent2));
                     border-radius:10px; display:flex; align-items:center; justify-content:center; font-size:18px; }
        .logo h1 { font-size:18px; font-weight:600; }
        .logo span { font-size:12px; color:var(--muted); }
        .nav-links { display:flex; gap:10px; }
        .nav-btn { display:flex; align-items:center; gap:6px; padding:8px 14px; border-radius:8px;
                   border:1px solid var(--border); background:var(--surface2); color:var(--text);
                   font-size:13px; font-weight:500; text-decoration:none; transition:border-color 0.2s; }
        .nav-btn:hover { border-color:var(--accent2); }

        .layout { display:flex; min-height:calc(100vh - 73px); }
        .sidebar { width:220px; border-right:1px solid var(--border); padding:24px 16px;
                   position:sticky; top:73px; height:calc(100vh - 73px); overflow-y:auto; flex-shrink:0; }
        .sidebar-title { font-size:10px; font-weight:700; letter-spacing:1px; text-transform:uppercase;
                         color:var(--muted); margin-bottom:10px; }
        .sidebar a { display:block; padding:7px 10px; font-size:13px; color:var(--muted);
                     text-decoration:none; border-radius:6px; transition:all 0.15s; margin-bottom:2px; }
        .sidebar a:hover { color:var(--text); background:var(--surface2); }
        .content { flex:1; max-width:780px; padding:40px; }

        h2 { font-size:24px; font-weight:700; margin-bottom:6px; }
        .subtitle { color:var(--muted); font-size:14px; margin-bottom:36px; line-height:1.6; }
        .section { margin-bottom:48px; }
        .section-title { font-size:15px; font-weight:700; margin-bottom:16px;
                         padding-bottom:10px; border-bottom:1px solid var(--border);
                         color:var(--accent2); }
        .card { background:var(--surface); border:1px solid var(--border); border-radius:12px;
                overflow:hidden; margin-bottom:16px; }
        .card-header { padding:12px 18px; display:flex; align-items:center; gap:10px;
                       border-bottom:1px solid var(--border); background:var(--surface2); }
        .tag { font-size:11px; font-weight:700; padding:3px 8px; border-radius:5px;
               letter-spacing:0.5px; flex-shrink:0; }
        .tag-post { background:#064e3b; color:#34d399; }
        .tag-get { background:#1e3a5f; color:#60a5fa; }
        .tag-curl { background:#3b1a1a; color:#f87171; }
        .tag-python { background:#2d2b1e; color:#fbbf24; }
        .tag-zapier { background:#2a1f3d; color:#c084fc; }
        .tag-tool { background:#1a2d1a; color:#86efac; }
        .card-path { font-family:monospace; font-size:13px; color:var(--text); }
        .card-body { padding:18px; }
        pre { background:var(--surface2); border:1px solid var(--border); border-radius:8px;
              padding:16px; overflow-x:auto; font-family:monospace; font-size:12.5px; line-height:1.7;
              position:relative; }
        .copy-btn { position:absolute; top:10px; right:10px; background:var(--surface);
                    border:1px solid var(--border); border-radius:6px; padding:3px 10px;
                    color:var(--muted); font-size:11px; cursor:pointer; }
        .copy-btn:hover { border-color:var(--accent2); color:var(--text); }
        table { width:100%; border-collapse:collapse; font-size:13px; }
        th { text-align:left; color:var(--muted); font-weight:500; padding:7px 0;
             border-bottom:1px solid var(--border); }
        td { padding:9px 0; border-bottom:1px solid var(--border); vertical-align:top; line-height:1.5; }
        td:first-child { font-family:monospace; color:var(--accent2); width:170px; padding-right:12px; }
        td:nth-child(2) { width:70px; color:var(--muted); font-size:11px; }
        .req { color:#f87171; font-weight:700; }
        .opt { color:var(--muted); }
        code { background:var(--surface2); padding:1px 6px; border-radius:4px;
               font-family:monospace; font-size:12px; color:var(--accent2); }
        .tool-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
        .tool-card { background:var(--surface); border:1px solid var(--border); border-radius:10px;
                     padding:14px 16px; }
        .tool-name { font-size:13px; font-weight:600; margin-bottom:4px; }
        .tool-desc { font-size:12px; color:var(--muted); line-height:1.5; }
        .tool-params { font-size:11px; color:var(--accent2); margin-top:6px; font-family:monospace; }
        .platform-badge { display:inline-flex; align-items:center; gap:5px; padding:3px 8px;
                          background:var(--surface2); border:1px solid var(--border); border-radius:6px;
                          font-size:11px; margin-bottom:10px; }
        .step { display:flex; gap:12px; margin-bottom:12px; align-items:flex-start; }
        .step-n { width:22px; height:22px; background:var(--accent); border-radius:50%;
                  display:flex; align-items:center; justify-content:center; font-size:11px;
                  font-weight:700; flex-shrink:0; margin-top:1px; }
        .step-t { font-size:13px; color:var(--muted); line-height:1.6; }
    </style>
</head>
<body>
<header>
    <div class="logo">
        <div class="logo-icon">🔑</div>
        <div>
            <h1>API Documentation</h1>
            <span>Sam GTM Engineer — live integrations</span>
        </div>
    </div>
    <div class="nav-links">
        <a href="/operations" class="nav-btn">⚙️ Operations</a>
        <a href="/" class="nav-btn">📧 Dashboard</a>
    </div>
</header>

<div class="layout">
<nav class="sidebar">
    <div class="sidebar-title">Reference</div>
    <a href="#overview">Overview</a>
    <a href="#auth">Authentication</a>
    <a href="#endpoint">Main Endpoint</a>
    <a href="#response">Response Format</a>
    <div class="sidebar-title" style="margin-top:16px">Examples</div>
    <a href="#curl">cURL</a>
    <a href="#python">Python</a>
    <a href="#zapier">Zapier</a>
    <a href="#make">Make / n8n</a>
    <div class="sidebar-title" style="margin-top:16px">Live Tools</div>
    <a href="#crm">CRM</a>
    <a href="#email-auto">Email Automation</a>
    <a href="#analytics">Analytics</a>
    <a href="#engagement">Engagement</a>
</nav>

<div class="content">
    <h2>Sam — GTM Engineer API</h2>
    <p class="subtitle">One endpoint. Sam receives your task, uses any connected tools (HubSpot, Apollo, Mailchimp, etc.), executes the work, and returns the result. Add API keys in Settings to activate live integrations.</p>

    <!-- AUTH -->
    <div class="section" id="auth">
        <div class="section-title">Authentication</div>
        <div class="card">
            <div class="card-body">
                <p style="font-size:13px;color:var(--muted);margin-bottom:14px;">Set your GTM API key in <strong>Settings → Sam Access Key</strong>. Then pass it in every request header:</p>
                <pre><button class="copy-btn" onclick="cp(this)">Copy</button>X-API-Key: your-gtm-api-key</pre>
                <p style="font-size:12px;color:var(--muted);margin-top:10px;">If no key is set, the endpoint is open. Once a key is set, all calls without it return <code>401 Unauthorized</code>.</p>
            </div>
        </div>
    </div>

    <!-- ENDPOINT -->
    <div class="section" id="endpoint">
        <div class="section-title">Main Endpoint</div>
        <div class="card">
            <div class="card-header">
                <span class="tag tag-post">POST</span>
                <span class="card-path">/api/gtm</span>
            </div>
            <div class="card-body">
                <table>
                    <tr><th>Header</th><th></th><th>Description</th></tr>
                    <tr><td>X-API-Key</td><td><span class="req">required</span></td><td>Your Sam access key from Settings</td></tr>
                    <tr><td>Content-Type</td><td><span class="req">required</span></td><td><code>application/json</code></td></tr>
                </table>
                <br>
                <table>
                    <tr><th>Body field</th><th></th><th>Description</th></tr>
                    <tr><td>message</td><td><span class="req">required</span></td><td>The task for Sam — plain English, any GTM task</td></tr>
                    <tr><td>history</td><td><span class="opt">optional</span></td><td>Prior conversation turns: <code>[{"role":"user","content":"..."},{"role":"assistant","content":"..."}]</code></td></tr>
                </table>
            </div>
        </div>
    </div>

    <!-- RESPONSE -->
    <div class="section" id="response">
        <div class="section-title">Response Format</div>
        <div class="card">
            <div class="card-body">
                <pre>{
  "reply":  "**Actions executed:**\\n- [hubspot_create_contact] Created John Smith...\\n\\n## Cold Email Sequence...",
  "agent":  "sam-gtm",
  "status": "ok"
}</pre>
                <p style="font-size:12px;color:var(--muted);margin-top:10px;">When Sam uses connected tools, the <code>reply</code> starts with an <strong>Actions executed</strong> block listing every API call made, followed by his full deliverable.</p>
            </div>
        </div>
    </div>

    <!-- CURL -->
    <div class="section" id="curl">
        <div class="section-title">cURL Example</div>
        <div class="card">
            <div class="card-header"><span class="tag tag-curl">cURL</span><span class="card-path">Terminal</span></div>
            <div class="card-body">
                <pre><button class="copy-btn" onclick="cp(this)">Copy</button>curl -X POST https://volvere-email-agent-production.up.railway.app/api/gtm \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: YOUR_GTM_API_KEY" \\
  -d '{
    "message": "Find 5 VP of Sales in Dubai on Apollo and create contacts in HubSpot"
  }'</pre>
            </div>
        </div>
    </div>

    <!-- PYTHON -->
    <div class="section" id="python">
        <div class="section-title">Python Example</div>
        <div class="card">
            <div class="card-header"><span class="tag tag-python">Python</span><span class="card-path">requests library</span></div>
            <div class="card-body">
                <pre><button class="copy-btn" onclick="cp(this)">Copy</button>import requests

res = requests.post(
    "https://volvere-email-agent-production.up.railway.app/api/gtm",
    headers={
        "X-API-Key": "YOUR_GTM_API_KEY",
        "Content-Type": "application/json"
    },
    json={
        "message": "Add john@acme.com to Mailchimp list abc123 and create a HubSpot deal"
    }
)

data = res.json()
print(data["reply"])</pre>
            </div>
        </div>
    </div>

    <!-- ZAPIER -->
    <div class="section" id="zapier">
        <div class="section-title">Zapier Integration</div>
        <div class="card">
            <div class="card-header"><span class="tag tag-zapier">Zapier</span><span class="card-path">Webhooks by Zapier</span></div>
            <div class="card-body">
                <div class="step"><div class="step-n">1</div><div class="step-t">Add action: <strong>Webhooks by Zapier</strong> → Event: <code>POST</code></div></div>
                <div class="step"><div class="step-n">2</div><div class="step-t">URL: <code>https://volvere-email-agent-production.up.railway.app/api/gtm</code></div></div>
                <div class="step"><div class="step-n">3</div><div class="step-t">Headers: <code>X-API-Key: YOUR_KEY</code> · <code>Content-Type: application/json</code></div></div>
                <div class="step"><div class="step-n">4</div><div class="step-t">Data (raw): <code>{"message": "map a field from your trigger here"}</code></div></div>
                <div class="step"><div class="step-n">5</div><div class="step-t">Use <code>reply</code> from the response in any downstream Zapier step (Slack, Gmail, Notion, etc.)</div></div>
            </div>
        </div>
    </div>

    <!-- MAKE / N8N -->
    <div class="section" id="make">
        <div class="section-title">Make / n8n</div>
        <div class="card">
            <div class="card-header"><span class="tag tag-zapier">Make</span><span class="card-path">HTTP module</span></div>
            <div class="card-body">
                <pre><button class="copy-btn" onclick="cp(this)">Copy</button>Module: HTTP → Make a request
URL:    https://volvere-email-agent-production.up.railway.app/api/gtm
Method: POST
Headers:
  X-API-Key: YOUR_GTM_API_KEY
  Content-Type: application/json
Body (JSON):
  { "message": "{{trigger.message}}" }

Output: parse response → use {{reply}}</pre>
            </div>
        </div>
    </div>

    <!-- CRM TOOLS -->
    <div class="section" id="crm">
        <div class="section-title">Live Tools — CRM</div>
        <div class="tool-grid">
            <div class="tool-card">
                <div class="platform-badge">🟠 HubSpot</div>
                <div class="tool-name">hubspot_create_contact</div>
                <div class="tool-desc">Create a new contact in HubSpot CRM</div>
                <div class="tool-params">email, firstname, lastname, company, jobtitle</div>
            </div>
            <div class="tool-card">
                <div class="platform-badge">🟠 HubSpot</div>
                <div class="tool-name">hubspot_create_deal</div>
                <div class="tool-desc">Create a new deal in a pipeline stage</div>
                <div class="tool-params">name, stage, amount</div>
            </div>
            <div class="tool-card">
                <div class="platform-badge">🟠 HubSpot</div>
                <div class="tool-name">hubspot_get_contacts</div>
                <div class="tool-desc">Retrieve recent contacts from HubSpot</div>
                <div class="tool-params">limit</div>
            </div>
            <div class="tool-card">
                <div class="platform-badge">🟣 Pipedrive</div>
                <div class="tool-name">pipedrive_create_person</div>
                <div class="tool-desc">Add a person to Pipedrive CRM</div>
                <div class="tool-params">name, email, phone</div>
            </div>
            <div class="tool-card">
                <div class="platform-badge">🟣 Pipedrive</div>
                <div class="tool-name">pipedrive_create_deal</div>
                <div class="tool-desc">Create a deal linked to a person</div>
                <div class="tool-params">title, person_id, stage_id</div>
            </div>
        </div>
    </div>

    <!-- EMAIL AUTOMATION TOOLS -->
    <div class="section" id="email-auto">
        <div class="section-title">Live Tools — Email Automation & Prospecting</div>
        <div class="tool-grid">
            <div class="tool-card">
                <div class="platform-badge">🦧 Apollo</div>
                <div class="tool-name">apollo_search_people</div>
                <div class="tool-desc">Search for prospects by title, company, location</div>
                <div class="tool-params">title, company, location, limit</div>
            </div>
            <div class="tool-card">
                <div class="platform-badge">🦧 Apollo</div>
                <div class="tool-name">apollo_add_to_sequence</div>
                <div class="tool-desc">Add a contact to an Apollo email sequence</div>
                <div class="tool-params">email, sequence_id</div>
            </div>
            <div class="tool-card">
                <div class="platform-badge">⚡ Instantly</div>
                <div class="tool-name">instantly_get_campaigns</div>
                <div class="tool-desc">List all campaigns in Instantly</div>
                <div class="tool-params">(none)</div>
            </div>
            <div class="tool-card">
                <div class="platform-badge">⚡ Instantly</div>
                <div class="tool-name">instantly_add_lead</div>
                <div class="tool-desc">Add a lead to an Instantly campaign</div>
                <div class="tool-params">email, first_name, last_name, campaign_id</div>
            </div>
            <div class="tool-card">
                <div class="platform-badge">📧 Mailchimp</div>
                <div class="tool-name">mailchimp_get_lists</div>
                <div class="tool-desc">Get all Mailchimp audience lists</div>
                <div class="tool-params">(none)</div>
            </div>
            <div class="tool-card">
                <div class="platform-badge">📧 Mailchimp</div>
                <div class="tool-name">mailchimp_add_subscriber</div>
                <div class="tool-desc">Subscribe an email to a Mailchimp list</div>
                <div class="tool-params">email, first_name, last_name, list_id</div>
            </div>
            <div class="tool-card">
                <div class="platform-badge">🔵 ActiveCampaign</div>
                <div class="tool-name">activecampaign_create_contact</div>
                <div class="tool-desc">Create a contact in ActiveCampaign</div>
                <div class="tool-params">email, first_name, last_name, phone</div>
            </div>
        </div>
    </div>

    <!-- ANALYTICS TOOLS -->
    <div class="section" id="analytics">
        <div class="section-title">Live Tools — Analytics</div>
        <div class="tool-grid">
            <div class="tool-card">
                <div class="platform-badge">📊 Mixpanel</div>
                <div class="tool-name">mixpanel_track_event</div>
                <div class="tool-desc">Track a custom event in Mixpanel</div>
                <div class="tool-params">event, distinct_id, properties</div>
            </div>
            <div class="tool-card">
                <div class="platform-badge">🟢 Segment</div>
                <div class="tool-name">segment_identify</div>
                <div class="tool-desc">Identify a user with traits in Segment</div>
                <div class="tool-params">user_id, traits</div>
            </div>
            <div class="tool-card">
                <div class="platform-badge">🟢 Segment</div>
                <div class="tool-name">segment_track</div>
                <div class="tool-desc">Track an event for a user in Segment</div>
                <div class="tool-params">user_id, event, properties</div>
            </div>
        </div>
    </div>

    <!-- ENGAGEMENT TOOLS -->
    <div class="section" id="engagement">
        <div class="section-title">Live Tools — Customer Engagement</div>
        <div class="tool-grid">
            <div class="tool-card">
                <div class="platform-badge">💬 Intercom</div>
                <div class="tool-name">intercom_create_contact</div>
                <div class="tool-desc">Create a lead or contact in Intercom</div>
                <div class="tool-params">email, name</div>
            </div>
            <div class="tool-card">
                <div class="platform-badge">💬 Intercom</div>
                <div class="tool-name">intercom_send_message</div>
                <div class="tool-desc">Send a message to a user in Intercom</div>
                <div class="tool-params">user_id, message, admin_id</div>
            </div>
            <div class="tool-card">
                <div class="platform-badge">🎯 Klaviyo</div>
                <div class="tool-name">klaviyo_add_to_list</div>
                <div class="tool-desc">Add a profile to a Klaviyo list</div>
                <div class="tool-params">email, first_name, last_name, list_id</div>
            </div>
        </div>
    </div>

</div>
</div>

<script>
    function cp(btn) {
        const pre = btn.parentElement;
        const text = pre.textContent.replace('Copy','').replace('Copied!','').trim();
        navigator.clipboard.writeText(text).then(() => {
            btn.textContent = 'Copied!';
            setTimeout(() => btn.textContent = 'Copy', 1500);
        });
    }
</script>
</body>
</html>
"""


@app.route("/api-docs")
def api_docs():
    return render_template_string(API_DOCS_HTML)


INTEGRATION_KEYS = [
    "gtm_api_key", "hubspot_api_key", "salesforce_api_key", "pipedrive_api_key",
    "apollo_api_key", "instantly_api_key", "mailchimp_api_key", "activecampaign_api_key",
    "mixpanel_api_key", "segment_api_key", "intercom_api_key", "klaviyo_api_key",
]

INTEGRATION_NAMES = {
    "hubspot_api_key": "HubSpot", "salesforce_api_key": "Salesforce",
    "pipedrive_api_key": "Pipedrive", "apollo_api_key": "Apollo",
    "instantly_api_key": "Instantly", "mailchimp_api_key": "Mailchimp",
    "activecampaign_api_key": "ActiveCampaign", "mixpanel_api_key": "Mixpanel",
    "segment_api_key": "Segment", "intercom_api_key": "Intercom",
    "klaviyo_api_key": "Klaviyo",
}


@app.route("/api/settings/all", methods=["GET"])
def get_all_settings():
    result = {}
    for k in INTEGRATION_KEYS:
        val = get_setting(k)
        if val:
            result[k] = val[-4:]
    return jsonify(result)


@app.route("/api/settings/all", methods=["POST"])
def save_all_settings():
    data = request.json
    for k in INTEGRATION_KEYS:
        if k in data and data[k].strip():
            set_setting(k, data[k].strip())
    return jsonify({"status": "saved"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
