import threading
import db
from flask import Flask, jsonify, render_template_string
from stats import compute_summary
from detector import run_detector, get_status
from telegram_bot import run_bot
from fixtures import run_fixture_refresher

app = Flask(__name__)

DASHBOARD_HTML = """
<!doctype html>
<html>
<head>
  <title>Vigil</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
  <style>
    body { font-family: 'Sora', sans-serif; background: #17151f; color: #d8d5e0; padding: 2rem; margin: 0; }
    h1 { color: #a78bfa; margin-bottom: 0.2rem; }
    .subtitle { color: #8b879c; margin-top: 0; }
    .status-bar { display: flex; gap: 2rem; align-items: center; margin: 1rem 0 2rem 0; padding: 1rem;
                  background: #201d2b; border-radius: 8px; border: 1px solid #34304a; }
    .status-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; margin-right: 6px; }
    .status-connected { background: #a78bfa; }
    .status-other { background: #6b6880; }
    .metric { text-align: center; }
    .metric .value { font-size: 1.8rem; font-weight: bold; color: #ece9f2; transition: color 0.3s; }
    .metric .label { font-size: 0.8rem; color: #8b879c; text-transform: uppercase; letter-spacing: 0.05em; }
    .charts { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 2rem; }
    .chart-card { background: #201d2b; border-radius: 8px; border: 1px solid #34304a; padding: 1.2rem;
                  height: 320px; box-sizing: border-box; display: flex; flex-direction: column; min-width: 0; }
    .chart-card h3 { margin-top: 0; color: #b6b2c4; font-size: 0.95rem; text-transform: uppercase;
                     letter-spacing: 0.05em; flex-shrink: 0; }
    .chart-wrap { position: relative; flex-grow: 1; min-height: 0; min-width: 0; }
    .full-width { grid-column: span 2; }
    .table-scroll { max-height: 700px; overflow-y: auto; margin-top: 0.5rem; }
    table { width: 100%; border-collapse: collapse; }
    th, td { text-align: left; padding: 8px; border-bottom: 1px solid #34304a; font-size: 0.9rem; }
    th { color: #8b879c; text-transform: uppercase; font-size: 0.75rem;
         position: sticky; top: 0; background: #201d2b; }
    td:last-child, th:last-child { text-align: right; width: 100px; font-variant-numeric: tabular-nums; }
    .pos { color: #a78bfa; }
    .neg { color: #6b6880; }

    /* Tablet and below */
    @media (max-width: 1024px) {
      body { padding: 1rem; }
      .charts { grid-template-columns: 1fr; }
      .full-width { grid-column: span 1; }
      .status-bar { flex-wrap: wrap; gap: 1rem 1.5rem; }
      .chart-card { height: 280px; }
    }

    /* Phone */
    @media (max-width: 600px) {
      body { padding: 0.75rem; }
      h1 { font-size: 1.5rem; }
      .subtitle { font-size: 0.8rem; }

      .status-bar {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 0.9rem 0.5rem;
        padding: 0.9rem;
      }
      .status-bar > span:first-child {
        grid-column: span 2;
        margin-bottom: 0.3rem;
      }
      .metric { text-align: left; }
      .metric .value { font-size: 1.2rem; }
      .metric .label { font-size: 0.62rem; white-space: nowrap; }

      .chart-card { height: 220px; padding: 0.8rem; }
      .chart-card h3 { font-size: 0.75rem; }

      table { font-size: 0.72rem; }
      th, td { padding: 5px 4px; }
      td:last-child, th:last-child { width: 70px; }
      .table-scroll { overflow-x: auto; }
    }
  </style>
</head>
<body>
  <h1>Vigil</h1>
  <p class="subtitle">Autonomous Monitoring Detector (TxLINE World Cup Odds)</p>

  <div class="status-bar">
    <span><span id="statusDot" class="status-dot"></span><span id="statusText">connecting</span></span>
    <div class="metric"><div id="updateCount" class="value">0</div><div class="label">Updates Processed</div></div>
    <div class="metric"><div id="totalSignals" class="value">0</div><div class="label">Signals Logged</div></div>
    <div class="metric"><div id="resolvedCount" class="value">0</div><div class="label">Resolved</div></div>
    <div class="metric"><div id="correctCount" class="value">0</div><div class="label">Correct</div></div>
    <div class="metric"><div id="incorrectCount" class="value">0</div><div class="label">Incorrect</div></div>
    <div class="metric"><div id="unresolvedCount" class="value">0</div><div class="label">Unresolved</div></div>
    <div class="metric"><div id="accuracyValue" class="value">N/A</div><div class="label">Accuracy</div></div>
  </div>

  <div class="charts">
    <div class="chart-card">
      <h3>Signal Outcomes</h3>
      <div class="chart-wrap"><canvas id="accuracyChart"></canvas></div>
    </div>
    <div class="chart-card">
      <h3>Movement Magnitude Distribution</h3>
      <div class="chart-wrap"><canvas id="magnitudeChart"></canvas></div>
    </div>
    <div class="chart-card full-width">
      <h3>Signal Activity Over Time</h3>
      <div class="chart-wrap"><canvas id="timelineChart"></canvas></div>
    </div>
  </div>

  <div class="chart-card" style="height: auto;">
    <h3>Recent Signals</h3>
    <div class="table-scroll">
      <table>
        <thead><tr><th>Time (UTC)</th><th>Fixture</th><th>Outcome</th><th>Change</th></tr></thead>
        <tbody id="signalsBody"></tbody>
      </table>
    </div>
  </div>

  <script>
    const outcomeColors = ['#a78bfa', '#9ca3af', '#4b5563']; // purple, light grey, dark grey

    const accuracyChart = new Chart(document.getElementById('accuracyChart'), {
      type: 'doughnut',
      data: {
        labels: ['Correct', 'Incorrect', 'Unresolved'],
        datasets: [{ data: [0, 0, 0], backgroundColor: outcomeColors }]
      },
      options: { maintainAspectRatio: false, plugins: { legend: { labels: { color: '#d8d5e0' } } } }
    });

    const magnitudeChart = new Chart(document.getElementById('magnitudeChart'), {
      type: 'bar',
      data: {
        labels: ['2.5-3%', '3-5%', '5-10%', '10-15%', '15%+'],
        datasets: [{ label: 'Signals', data: [0, 0, 0, 0, 0], backgroundColor: '#a78bfa' }]
      },
      options: {
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: '#b6b2c4' }, grid: { color: '#34304a' } },
          y: { ticks: { color: '#b6b2c4' }, grid: { color: '#34304a' }, beginAtZero: true }
        }
      }
    });

    const timelineChart = new Chart(document.getElementById('timelineChart'), {
      type: 'line',
      data: {
        labels: [],
        datasets: [{
          label: 'Signals per interval', data: [],
          borderColor: '#a78bfa', backgroundColor: 'rgba(167,139,250,0.15)',
          fill: true, tension: 0.3
        }]
      },
      options: {
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: '#b6b2c4' }, grid: { color: '#34304a' } },
          y: { ticks: { color: '#b6b2c4' }, grid: { color: '#34304a' }, beginAtZero: true }
        }
      }
    });

    function refreshDashboard() {
      fetch('/api/signals')
        .then(r => r.json())
        .then(data => {
          document.getElementById('statusText').textContent = data.status.status;
          document.getElementById('statusDot').className =
            'status-dot ' + (data.status.status === 'connected' ? 'status-connected' : 'status-other');
          document.getElementById('updateCount').textContent = data.status.update_count;
          document.getElementById('totalSignals').textContent = data.total;
          document.getElementById('resolvedCount').textContent = data.resolved;
          document.getElementById('correctCount').textContent = data.correct;
          document.getElementById('incorrectCount').textContent = data.incorrect;
          document.getElementById('unresolvedCount').textContent = data.unresolved;
          document.getElementById('accuracyValue').textContent = data.accuracy;

          accuracyChart.data.datasets[0].data = [data.correct, data.incorrect, data.unresolved];
          accuracyChart.update();

          magnitudeChart.data.labels = data.magnitude_labels;
          magnitudeChart.data.datasets[0].data = data.magnitude_values;
          magnitudeChart.update();

          timelineChart.data.labels = data.timeline_labels;
          timelineChart.data.datasets[0].data = data.timeline_values;
          timelineChart.update();

          const body = document.getElementById('signalsBody');
          body.innerHTML = '';
          data.recent.forEach(s => {
            const row = document.createElement('tr');
            const changeClass = s[3] > 0 ? 'pos' : 'neg';
            row.innerHTML = `<td>${s[0]}</td><td>${s[1]}</td><td>${s[2]}</td><td class="${changeClass}">${s[3]}</td>`;
            body.appendChild(row);
          });
        })
        .catch(err => console.error('Refresh failed:', err));
    }

    refreshDashboard();
    setInterval(refreshDashboard, 8000);
  </script>
</body>
</html>
"""


@app.route("/")
def dashboard():
    return render_template_string(DASHBOARD_HTML)


@app.route("/api/signals")
def api_signals():
    data = compute_summary()
    return jsonify({"status": get_status(), **data})


if __name__ == "__main__":
    threading.Thread(target=run_detector, daemon=True).start()
    threading.Thread(target=run_bot, daemon=True).start()
    threading.Thread(target=run_fixture_refresher, daemon=True).start()
    app.run(host="0.0.0.0", port=int(__import__("os").environ.get("PORT", 5000)))