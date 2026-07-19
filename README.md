# Vigil

An autonomous monitoring agent that watches TxLINE's live odds stream for World Cup matches,
detects statistically significant win-probability shifts, logs
them, and automatically grades each signal against the real match outcome once it
finishes.

Built for the TxODDS/TxLINE Hackathon (July 2026).

**Live Dashboard:** https://vigil-th9f.onrender.com/
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
   checks whether each signal correctly predicted the winner. A match is
   considered finished when either TxLINE's `game_finalised` action fires, or the
   game clock reports a terminal status (full-time, after extra time, or after
   penalties), whichever arrives first.
4. **Fixture name resolution** (`vigil-python/fixtures.py`): a background service
   that looks up real team names for every fixture Vigil sees, so signals are
   shown as "Spain vs Argentina" rather than raw fixture IDs or `part1`/`part2`
   codes. Names are saved to the database as they're discovered, so they load
   instantly on restart instead of being rebuilt from scratch.
5. **Live dashboard** (`vigil-python/app.py`): a Flask web app that runs the
   detector in a background thread and serves a live-updating analytics
   dashboard: connection status, signal counts (resolved/correct/incorrect/
   unresolved), accuracy, a signal-outcomes doughnut chart, a movement-magnitude
   distribution chart, a signal-activity timeline, and a scrollable recent-signals
   table — all shown with real team names. The dashboard updates in place via a
   background data fetch every few seconds, no full-page reloads.
6. **Telegram bot** (`vigil-python/telegram_bot.py`): a second way to interact
   with Vigil. Subscribers get a push message the instant a signal is detected,
   and can query Vigil directly with commands (`/status`, `/summary`,
   `/accuracy`, `/recent`, `/matches`).
7. **Persistent storage** (`vigil-python/db.py`): a small database abstraction
   that uses PostgreSQL when deployed (via `DATABASE_URL`), and falls back
   automatically to a local SQLite file when running locally with no database
   configured. Signals, Telegram subscribers, and known fixture names all persist
   across restarts and redeploys on the live instance.

## Project structure

```
vigil-connect/ Wallet subscribe + API token activation (JS, browser-based)
vigil-python/ Live odds monitoring, signal detection, outcome grading, dashboard, and Telegram bot
documentation/ Technical overview and TxLINE API feedback
```


## Understanding the dashboard

When you open Vigil's dashboard (locally or at the live demo link), here's what
each part means and why it matters:

- **Connection status**: shows whether Vigil is actively connected to TxLINE's
  live odds stream right now. "Connected" means it's actively watching matches
  in real time; "reconnecting" means it briefly lost the stream and is
  automatically recovering (no manual intervention needed).
- **Updates processed**: the raw count of odds updates Vigil has read from the
  stream since it started. This is almost always much higher than "signals
  logged," since most updates are small, ordinary price movements that don't
  cross the significance threshold.
- **Signals logged**: the number of times Vigil detected a genuinely sharp
  move (a win-probability shift above the configured threshold) and recorded it.
- **Resolved/Correct/Incorrect/Unresolved**: once a signal's match
  actually finishes, Vigil checks whether the team whose probability rose
  actually won. "Resolved" is the total graded so far; "Unresolved" means the
  match the signal belongs to hasn't finished yet. This number climbs over time
  as matches conclude.
- **Accuracy**: of the resolved signals, what percentage correctly predicted
  the winner. This is the core metric Vigil exists to produce: not just "did
  the odds move," but "did that move actually mean something."
- **Signal Outcomes** (doughnut chart): the same correct/incorrect/unresolved
  split, visually.
- **Movement Magnitude Distribution** (bar chart): how big the detected shifts
  tend to be.
- **Signal Activity Over Time** (line chart): how frequently Vigil is firing
  signals, over the session.
- **Recent Signals** (table): a scrollable, chronological log of individual
  signals, shown with real team names, e.g. "Spain vs Argentina - Argentina -
  26.8% → 21.2%".

## Telegram bot

Search for Vigil's bot on Telegram and send `/start` to subscribe. You'll get a
push message every time a signal is detected, formatted like:

```
📉 Signal detected
Fixture: Spain vs Argentina
Outcome: Argentina
26.8% → 21.2%  (-5.6)
```

Available commands:
- `/status` — connection state and updates processed
- `/summary` — full stats: signals, grading breakdown, movement sizes, matches tracked
- `/accuracy` — resolved/correct/incorrect/unresolved/accuracy
- `/recent` — last 5 signals
- `/matches` — which matches Vigil currently knows about
- `/stop` — unsubscribe from alerts

## Setup

### 1. Wallet & activation (`vigil-connect/`)

```bash
cd vigil-connect
npm install
npm run dev
```

Open the local page, connect a Phantom wallet on **Solana devnet**, and click
"Subscribe & Get API Key". Copy the resulting JWT and API token.

### 2. Detector, dashboard & bot (`vigil-python/`)

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
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

By default this runs against local SQLite. To use Postgres instead (matching the
deployed setup), also set:

```
DATABASE_URL=postgres://...
```

Run Vigil with the live dashboard and Telegram bot:
```bash
python app.py
```
Then open `http://localhost:5000` in a browser.

Or run just the detector, without the dashboard or bot:
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
- **Environment variables:** `TXLINE_API_TOKEN`, `TXLINE_JWT`, `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`

**Database**
- Render PostgreSQL (free tier), providing persistent storage for signals,
  Telegram subscribers, and known fixture names across restarts and redeploys,
  see [`db.py`](vigil-python/db.py) for the connection logic and automatic
  SQLite fallback.

## Technical documentation

See [`documentation/technical-overview.md`](documentation/technical-overview.md)
for the core idea, architecture, and full list of TxLINE endpoints used.

## Notes on the TxLINE API

See [`documentation/feedback.md`](documentation/feedback.md) for our experience
using the API, including some undocumented behavior we ran into.nto.