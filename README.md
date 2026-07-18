# Vigil

An autonomous agent that watches TxLINE's live odds stream for World Cup matches,
detects statistically significant win-probability shifts ("sharp movements"), logs
them, and automatically grades each signal against the real match outcome once it
finishes.

Built for the TxODDS/TxLINE Hackathon (July 2026).

**Live demo:** https://vigil-th9f.onrender.com
*(Free-tier hosting, the first load after a period of inactivity may take up to
~50 seconds while the instance wakes up.)*

## How it works

1. **Wallet & subscription** (`vigil-connect/`): a small browser app that connects
   a Phantom wallet, subscribes to TxLINE's free World Cup tier on Solana devnet,
   and activates an API token.
2. **Detection engine** (`vigil-python/detector.py`): connects to TxLINE's live
   odds stream, tracks implied win probabilities per fixture, flags significant
   shifts, and logs them to a local database. Automatically reconnects on stream
   drops and refreshes its auth token when it expires, so it can run unattended.
3. **Outcome grading** (`vigil-python/check_outcomes.py`): once a monitored match
   finishes, looks up the real final score (including penalty shootouts) and
   checks whether each signal correctly predicted the winner.
4. **Live dashboard** (`vigil-python/app.py`): a Flask web app that runs the
   detector in a background thread and serves a live-updating dashboard showing
   connection status, total signals, recent signals, and running accuracy.

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

Vigil is deployed on [Render](https://render.com) as a Python web service:
- **Root directory:** `vigil-python`
- **Build command:** `pip install -r requirements.txt`
- **Start command:** `python app.py`
- **Environment variables:** `TXLINE_API_TOKEN`, `TXLINE_JWT`

## Technical documentation

See [`documentation/technical-overview.md`](documentation/technical-overview.md)
for the core idea, architecture, and full list of TxLINE endpoints used.

## Notes on the TxLINE API

See [`documentation/feedback.md`](documentation/feedback.md) for our experience
using the API, including some undocumented behavior we ran into.