# Vigil

An autonomous monitoring agent for TxLINE’s live World Cup odds feed. Vigil identifies statistically significant shifts in win probability, records each movement as a signal, and automatically evaluates prediction accuracy against final match outcomes after completion.

Built for the World Cup Hackathon World Cup Powered by TxODDS (July 2026).

**Live demo:** https://vigil-th9f.onrender.com
*(Free-tier hosting, the first load after a period of inactivity may take up to
~50 seconds while the instance wakes up.)*

The dashboard is fully responsive, usable on desktop, tablet, and phone screens.

## How it works

1. **Wallet & subscription** (`vigil-connect/`): a small browser app that connects
   a Phantom wallet, subscribes to TxLINE's free World Cup tier on Solana devnet,
   and activates an API token.
2. **Detection engine** (`vigil-python/detector.py`): connects to TxLINE's live
   odds stream, tracks implied win probabilities per fixture, flags significant
   shifts, and logs them to a database. Automatically reconnects on stream drops
   and refreshes its auth token when it expires, so it can run unattended.
3. **Outcome grading** (`vigil-python/check_outcomes.py`): once a monitored match
   finishes, looks up the real final score (including penalty shootouts) and
   checks whether each signal correctly predicted the winner.
4. **Live dashboard** (`vigil-python/app.py`): a Flask web app that runs the
   detector in a background thread and serves a live-updating analytics
   dashboard: connection status, signal counts (resolved/correct/incorrect/
   unresolved), accuracy, a signal-outcomes doughnut chart, a movement-magnitude
   distribution chart, a signal-activity timeline, and a scrollable recent-signals
   table. The dashboard updates in place via a background data fetch every few
   seconds — no full-page reloads.
5. **Persistent storage** (`vigil-python/db.py`): a small database abstraction
   that uses PostgreSQL when deployed (via `DATABASE_URL`), and falls back
   automatically to a local SQLite file when running locally with no database
   configured. This means signal history survives restarts and redeploys on the
   live instance, instead of resetting.

## Project structure

```
vigil-connect/ Wallet subscribe + API token activation (JS, browser-based)
vigil-python/ Live odds monitoring, signal detection, and outcome grading
documentation/ Technical overview and TxLINE API feedback
```

## Setup

### 1. Wallet & activation (`vigil-connect/`)

```bash
cd vigil-connect
npm install
npm run dev
```

Open the local page, connect a Phantom wallet on **Solana devnet**, and click
"Subscribe & Get API Key". Copy the resulting JWT and API token.

### 2. Detector & dashboard (`vigil-python/`)

```bash
cd vigil-python
python -m venv venv
venv\Scripts\activate # Windows
pip install -r requirements.txt
```

Create a `.env` file:

```
TXLINE_API_TOKEN=your_token_here
TXLINE_JWT=your_jwt_here
```

By default this runs against local SQLite. To use Postgres instead (matching the
deployed setup), also set:

```
DATABASE_URL=postgres://...
```

Run Vigil with the live dashboard:
```bash
python app.py
```
Then open `http://localhost:5000` in a browser.

Or run just the detector, without the dashboard:
```bash
python odds_monitor.py
```

Check outcomes against real match results directly:
```bash
python check_outcomes.py
```

View a plain-text summary at any time:
```bash
python summary.py
```

## Deployment

Vigil is deployed on [Render](https://render.com):

**Web service**
- **Root directory:** `vigil-python`
- **Build command:** `pip install -r requirements.txt`
- **Start command:** `python app.py`
- **Environment variables:** `TXLINE_API_TOKEN`, `TXLINE_JWT`, `DATABASE_URL`

**Database**
- Render PostgreSQL (free tier), providing persistent signal storage across
  restarts and redeploys, see [`db.py`](vigil-python/db.py) for the connection
  logic and automatic SQLite fallback.

## Technical documentation

See [`documentation/technical-overview.md`](documentation/technical-overview.md)
for the core idea, architecture, and full list of TxLINE endpoints used.

## Notes on the TxLINE API

See [`documentation/feedback.md`](documentation/feedback.md) for our experience
using the API, including some undocumented behavior we ran into.