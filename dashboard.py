"""
Web dashboard for the Volvere Email Agent.
Runs the scheduler in a background thread and serves a modern interactive UI.
"""

import threading
import schedule
import time
from flask import Flask, render_template_string, jsonify
from database import get_all_emails, get_stats, init_db

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


HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Volvere — Email Agent</title>
    <style>
        :root {
            --bg: #0f0f13;
            --surface: #1a1a24;
            --surface2: #22222f;
            --border: #2e2e3e;
            --accent: #6c63ff;
            --accent2: #a78bfa;
            --text: #e8e8f0;
            --muted: #6b6b80;
            --green: #34d399;
            --blue: #60a5fa;
            --pink: #f472b6;
            --orange: #fb923c;
            --yellow: #facc15;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
        }

        /* ── Header ── */
        header {
            padding: 24px 40px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid var(--border);
            background: var(--surface);
        }
        .logo {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .logo-icon {
            width: 36px; height: 36px;
            background: linear-gradient(135deg, var(--accent), var(--accent2));
            border-radius: 10px;
            display: flex; align-items: center; justify-content: center;
            font-size: 18px;
        }
        .logo h1 { font-size: 18px; font-weight: 600; letter-spacing: -0.3px; }
        .logo span { font-size: 12px; color: var(--muted); margin-top: 1px; }

        .header-right {
            display: flex;
            align-items: center;
            gap: 16px;
        }
        .live-badge {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 12px;
            color: var(--muted);
        }
        .live-dot {
            width: 7px; height: 7px;
            background: var(--green);
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }
        #countdown { color: var(--accent2); font-weight: 500; }

        /* ── Stats ── */
        .stats {
            display: flex;
            gap: 16px;
            padding: 28px 40px 0;
            flex-wrap: wrap;
        }
        .stat-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 20px 24px;
            min-width: 150px;
            position: relative;
            overflow: hidden;
            transition: border-color 0.2s;
        }
        .stat-card:hover { border-color: var(--accent); }
        .stat-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 2px;
            background: linear-gradient(90deg, var(--accent), var(--accent2));
        }
        .stat-number {
            font-size: 36px;
            font-weight: 700;
            letter-spacing: -1px;
            background: linear-gradient(135deg, #fff, var(--accent2));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .stat-label { font-size: 12px; color: var(--muted); margin-top: 4px; }

        /* ── Controls ── */
        .controls {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 24px 40px 16px;
            flex-wrap: wrap;
        }
        .search-wrap {
            position: relative;
            flex: 1;
            max-width: 360px;
        }
        .search-icon {
            position: absolute;
            left: 12px; top: 50%;
            transform: translateY(-50%);
            color: var(--muted);
            font-size: 14px;
        }
        #search {
            width: 100%;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 9px 12px 9px 34px;
            color: var(--text);
            font-size: 14px;
            outline: none;
            transition: border-color 0.2s;
        }
        #search:focus { border-color: var(--accent); }
        #search::placeholder { color: var(--muted); }

        .filter-btns { display: flex; gap: 8px; flex-wrap: wrap; }
        .filter-btn {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 7px 14px;
            font-size: 12px;
            color: var(--muted);
            cursor: pointer;
            transition: all 0.2s;
        }
        .filter-btn:hover, .filter-btn.active {
            border-color: var(--accent);
            color: var(--accent2);
            background: rgba(108, 99, 255, 0.1);
        }

        .count-label {
            margin-left: auto;
            font-size: 12px;
            color: var(--muted);
        }

        /* ── Table ── */
        .table-wrap { padding: 0 40px 40px; }
        table {
            width: 100%;
            border-collapse: collapse;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 14px;
            overflow: hidden;
        }
        thead { background: var(--surface2); }
        th {
            padding: 13px 16px;
            text-align: left;
            font-size: 11px;
            font-weight: 600;
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 1px solid var(--border);
        }
        td {
            padding: 14px 16px;
            font-size: 13px;
            border-bottom: 1px solid var(--border);
            vertical-align: middle;
        }
        tr:last-child td { border-bottom: none; }
        tbody tr {
            cursor: pointer;
            transition: background 0.15s;
        }
        tbody tr:hover td { background: rgba(108,99,255,0.06); }

        .badge {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            border-radius: 20px;
            padding: 3px 10px;
            font-size: 11px;
            font-weight: 600;
            white-space: nowrap;
        }
        .badge-dot { width: 5px; height: 5px; border-radius: 50%; }

        .badge-ceo  { background: rgba(96,165,250,0.15); color: #60a5fa; }
        .badge-coo  { background: rgba(52,211,153,0.15); color: #34d399; }
        .badge-cfo  { background: rgba(250,204,21,0.15);  color: #facc15; }
        .badge-cmo  { background: rgba(244,114,182,0.15); color: #f472b6; }
        .badge-cto  { background: rgba(251,146,60,0.15);  color: #fb923c; }
        .badge-ceo .badge-dot  { background: #60a5fa; }
        .badge-coo .badge-dot  { background: #34d399; }
        .badge-cfo .badge-dot  { background: #facc15; }
        .badge-cmo .badge-dot  { background: #f472b6; }
        .badge-cto .badge-dot  { background: #fb923c; }

        .sender { color: var(--text); font-weight: 500; }
        .sender-email { font-size: 11px; color: var(--muted); margin-top: 1px; }
        .subject { font-weight: 500; }
        .preview { color: var(--muted); max-width: 280px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .time { color: var(--muted); font-size: 11px; white-space: nowrap; }

        .open-icon { color: var(--muted); font-size: 14px; transition: color 0.2s; }
        tr:hover .open-icon { color: var(--accent2); }

        .empty {
            text-align: center;
            padding: 80px 40px;
            color: var(--muted);
        }
        .empty-icon { font-size: 40px; margin-bottom: 12px; }
        .empty p { font-size: 15px; }

        /* ── Modal ── */
        .overlay {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.7);
            backdrop-filter: blur(4px);
            z-index: 100;
            align-items: center;
            justify-content: center;
        }
        .overlay.open { display: flex; }

        .modal {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 18px;
            width: 680px;
            max-width: 95vw;
            max-height: 85vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            animation: slideUp 0.2s ease;
        }
        @keyframes slideUp {
            from { opacity: 0; transform: translateY(20px); }
            to   { opacity: 1; transform: translateY(0); }
        }

        .modal-header {
            padding: 20px 24px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 16px;
        }
        .modal-meta { display: flex; flex-direction: column; gap: 6px; }
        .modal-subject { font-size: 16px; font-weight: 600; }
        .modal-info { font-size: 12px; color: var(--muted); display: flex; gap: 16px; flex-wrap: wrap; }

        .close-btn {
            background: var(--surface2);
            border: 1px solid var(--border);
            border-radius: 8px;
            width: 32px; height: 32px;
            display: flex; align-items: center; justify-content: center;
            cursor: pointer;
            color: var(--muted);
            font-size: 16px;
            flex-shrink: 0;
            transition: all 0.2s;
        }
        .close-btn:hover { border-color: var(--accent); color: var(--text); }

        .modal-tabs {
            display: flex;
            gap: 0;
            border-bottom: 1px solid var(--border);
            padding: 0 24px;
        }
        .tab-btn {
            padding: 12px 16px;
            font-size: 13px;
            color: var(--muted);
            cursor: pointer;
            border-bottom: 2px solid transparent;
            transition: all 0.2s;
            margin-bottom: -1px;
        }
        .tab-btn.active { color: var(--accent2); border-bottom-color: var(--accent2); }

        .modal-body { padding: 24px; overflow-y: auto; flex: 1; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }

        .email-text {
            font-size: 14px;
            line-height: 1.75;
            color: var(--text);
            white-space: pre-wrap;
            font-family: inherit;
        }

        .hidden { display: none !important; }
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
            <th>Advisor</th>
            <th>From</th>
            <th>Subject</th>
            <th>Reply Preview</th>
            <th>Time</th>
            <th></th>
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
            onclick="openModal(
                {{ e.id }},
                '{{ e.client_name }}',
                '{{ e.sender | replace("'", "\\'") }}',
                '{{ e.subject | replace("'", "\\'") }}',
                '{{ e.processed_at }}',
                {{ e.body | tojson }},
                {{ e.reply | tojson }}
            )">
            <td>
                <span class="badge badge-{{ role }}">
                    <span class="badge-dot"></span>
                    {{ e.client_name }}
                </span>
            </td>
            <td>
                <div class="sender">{{ e.sender.split('<')[0].strip() }}</div>
                {% if '<' in e.sender %}
                <div class="sender-email">{{ e.sender.split('<')[1].replace('>','') }}</div>
                {% endif %}
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
    <p>No emails processed yet. Send one to any advisor to get started.</p>
</div>
{% endif %}
</div>

<!-- Modal -->
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
            <div class="tab-content active" id="tab-reply">
                <pre class="email-text" id="modal-reply"></pre>
            </div>
            <div class="tab-content" id="tab-original">
                <pre class="email-text" id="modal-body"></pre>
            </div>
        </div>
    </div>
</div>

<script>
    // Countdown timer
    let seconds = 60;
    const cd = document.getElementById('countdown');
    setInterval(() => {
        seconds--;
        if (seconds <= 0) { location.reload(); return; }
        cd.textContent = seconds;
    }, 1000);

    // Search + filter
    const rows = Array.from(document.querySelectorAll('.email-row'));
    const searchEl = document.getElementById('search');
    const countEl = document.getElementById('row-count');
    let activeFilter = 'all';

    function applyFilters() {
        const q = searchEl.value.toLowerCase();
        let visible = 0;
        rows.forEach(r => {
            const matchFilter = activeFilter === 'all' || r.dataset.filter === activeFilter;
            const matchSearch = !q ||
                r.dataset.subject.includes(q) ||
                r.dataset.sender.includes(q) ||
                r.dataset.reply.includes(q);
            const show = matchFilter && matchSearch;
            r.classList.toggle('hidden', !show);
            if (show) visible++;
        });
        countEl.textContent = visible + ' email' + (visible !== 1 ? 's' : '');
    }

    searchEl.addEventListener('input', applyFilters);

    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            activeFilter = btn.dataset.filter;
            applyFilters();
        });
    });

    applyFilters();

    // Modal
    function openModal(id, advisor, sender, subject, time, body, reply) {
        const role = advisor.split(' ')[0].toLowerCase();
        document.getElementById('modal-badge').innerHTML =
            `<span class="badge badge-${role}"><span class="badge-dot"></span>${advisor}</span>`;
        document.getElementById('modal-subject').textContent = subject;
        document.getElementById('modal-sender').textContent = sender;
        document.getElementById('modal-time').textContent = time;
        document.getElementById('modal-reply').textContent = reply;
        document.getElementById('modal-body').textContent = body;
        switchTab('reply');
        document.getElementById('overlay').classList.add('open');
    }

    function closeModal() {
        document.getElementById('overlay').classList.remove('open');
    }

    function closeOnOverlay(e) {
        if (e.target === document.getElementById('overlay')) closeModal();
    }

    function switchTab(name) {
        document.querySelectorAll('.tab-btn').forEach((b, i) => {
            b.classList.toggle('active', (i === 0 && name === 'reply') || (i === 1 && name === 'original'));
        });
        document.getElementById('tab-reply').classList.toggle('active', name === 'reply');
        document.getElementById('tab-original').classList.toggle('active', name === 'original');
    }

    document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
</script>
</body>
</html>
"""


@app.route("/")
def index():
    init_db()
    emails = get_all_emails()
    stats = get_stats()
    return render_template_string(HTML, emails=emails, stats=stats)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
