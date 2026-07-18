import threading
import sqlite3
from flask import Flask, jsonify, render_template_string
from detector import run_detector, get_status
from check_outcomes import get_final_result

app = Flask(__name__)

DASHBOARD_HTML = """
<!doctype html>
<html>
<head>
  <title>Vigil</title>
  <meta http-equiv="refresh" content="15">
  <style>
    body { font-family: sans-serif; background: #0b0b0f; color: #eee; padding: 2rem; }
    h1 { color: #ff5a5f; }
    table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
    th, td { text-align: left; padding: 8px; border-bottom: 1px solid #333; }
    .status { color: #7CFC00; }
    .stat { display: inline-block; margin-right: 2rem; font-size: 1.2rem; }
  </style>
</head>
<body>
  <h1>Vigil: Sharp Movement Detector</h1>
  <p class="status">Status: {{ status.status }} | Updates processed: {{ status.update_count }}</p>

  <div>
    <span class="stat">Signals logged: {{ total_signals }}</span>
    <span class="stat">Resolved: {{ resolved }}</span>
    <span class="stat">Accuracy: {{ accuracy }}</span>
  </div>

  <table>
    <tr><th>Time (UTC)</th><th>Fixture</th><th>Outcome</th><th>Change</th></tr>
    {% for s in signals %}
    <tr>
      <td>{{ s[0] }}</td><td>{{ s[1] }}</td><td>{{ s[2] }}</td><td>{{ s[3] }}</td>
    </tr>
    {% endfor %}
  </table>
</body>
</html>
"""


def compute_summary():
    conn = sqlite3.connect("signals.db")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM signals")
    total = cur.fetchone()[0]

    cur.execute("SELECT detected_at, fixture_id, outcome, change FROM signals ORDER BY id DESC LIMIT 20")
    recent = [(t, f, o, round(c, 2)) for t, f, o, c in cur.fetchall()]

    cur.execute("SELECT fixture_id, outcome, change FROM signals WHERE change > 0")
    directional = cur.fetchall()

    correct = incorrect = 0
    cache = {}
    for fixture_id, outcome, change in directional:
        if fixture_id not in cache:
            cache[fixture_id] = get_final_result(fixture_id)
        result = cache[fixture_id]
        if result is None:
            continue
        if outcome == result:
            correct += 1
        else:
            incorrect += 1

    resolved = correct + incorrect
    accuracy = f"{correct / resolved * 100:.1f}%" if resolved else "no resolved signals yet"

    return total, recent, resolved, accuracy


@app.route("/")
def dashboard():
    total, recent, resolved, accuracy = compute_summary()
    return render_template_string(
        DASHBOARD_HTML,
        status=get_status(),
        total_signals=total,
        signals=recent,
        resolved=resolved,
        accuracy=accuracy,
    )


@app.route("/api/signals")
def api_signals():
    total, recent, resolved, accuracy = compute_summary()
    return jsonify({
        "status": get_status(),
        "total_signals": total,
        "resolved": resolved,
        "accuracy": accuracy,
        "recent_signals": recent,
    })


if __name__ == "__main__":
    thread = threading.Thread(target=run_detector, daemon=True)
    thread.start()
    app.run(host="0.0.0.0", port=int(__import__("os").environ.get("PORT", 5000)))