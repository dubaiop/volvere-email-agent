"""
Simple web dashboard to view processed emails.
Run with: python dashboard.py
Then open: http://localhost:5000
"""

from flask import Flask, render_template_string
from database import get_all_emails, get_stats, init_db

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Volvere Email Agent Dashboard</title>
    <meta http-equiv="refresh" content="60">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: Arial, sans-serif; background: #f4f6f9; color: #333; }

        header {
            background: #1a1a2e;
            color: white;
            padding: 20px 40px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        header h1 { font-size: 22px; }
        header span { font-size: 13px; opacity: 0.6; }

        .stats {
            display: flex;
            gap: 20px;
            padding: 30px 40px 10px;
        }
        .stat-card {
            background: white;
            border-radius: 10px;
            padding: 20px 30px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.07);
            min-width: 160px;
        }
        .stat-card .number { font-size: 36px; font-weight: bold; color: #1a1a2e; }
        .stat-card .label { font-size: 13px; color: #888; margin-top: 4px; }

        .table-wrap { padding: 20px 40px 40px; }
        table { width: 100%; border-collapse: collapse; background: white;
                border-radius: 10px; overflow: hidden;
                box-shadow: 0 2px 8px rgba(0,0,0,0.07); }
        th { background: #1a1a2e; color: white; padding: 14px 16px;
             text-align: left; font-size: 13px; }
        td { padding: 12px 16px; border-bottom: 1px solid #f0f0f0;
             font-size: 14px; vertical-align: top; }
        tr:last-child td { border-bottom: none; }
        tr:hover td { background: #fafafa; }

        .badge {
            display: inline-block;
            background: #e8f0fe;
            color: #1a73e8;
            border-radius: 20px;
            padding: 2px 10px;
            font-size: 12px;
            font-weight: bold;
        }
        .preview { color: #555; max-width: 300px; white-space: nowrap;
                   overflow: hidden; text-overflow: ellipsis; }
        .time { color: #aaa; font-size: 12px; white-space: nowrap; }

        .empty { text-align: center; padding: 60px; color: #aaa; font-size: 16px; }
    </style>
</head>
<body>
    <header>
        <h1>Volvere Email Agent Dashboard</h1>
        <span>Auto-refreshes every 60 seconds</span>
    </header>

    <div class="stats">
        <div class="stat-card">
            <div class="number">{{ stats.total }}</div>
            <div class="label">Emails Processed</div>
        </div>
        {% for c in stats.by_client %}
        <div class="stat-card">
            <div class="number">{{ c.count }}</div>
            <div class="label">{{ c.name }}</div>
        </div>
        {% endfor %}
    </div>

    <div class="table-wrap">
        {% if emails %}
        <table>
            <thead>
                <tr>
                    <th>Client</th>
                    <th>From</th>
                    <th>Subject</th>
                    <th>Reply Preview</th>
                    <th>Time</th>
                </tr>
            </thead>
            <tbody>
                {% for e in emails %}
                <tr>
                    <td><span class="badge">{{ e.client_name }}</span></td>
                    <td>{{ e.sender }}</td>
                    <td>{{ e.subject }}</td>
                    <td class="preview">{{ e.reply }}</td>
                    <td class="time">{{ e.processed_at }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <div class="empty">No emails processed yet. The agent will pick them up shortly.</div>
        {% endif %}
    </div>
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
