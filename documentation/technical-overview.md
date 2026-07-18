# Vigil Technical Overview

## Core idea

Sports betting markets react to new information almost instantly, often before most bettors can respond. Vigil is an autonomous monitoring agent that continuously analyzes TxLINE's live World Cup odds feed, identifies statistically significant shifts in win probability, and records them as trading signals. Once a match concludes, each signal is automatically evaluated against the actual result to measure predictive accuracy. The entire process is surfaced through a live, responsive analytics dashboard that transforms real-time market movements into measurable performance insights

## Architecture

**Wallet & activation** (`vigil-connect/`)
A small browser app connects a Phantom wallet on Solana devnet, submits the
on-chain `subscribe` transaction for TxLINE's free World Cup tier, and activates
an API token via signed message authentication.

**Detection engine** (`vigil-python/detector.py`)
- Connects to TxLINE's live odds stream (Server-Sent Events) rather than polling,
  this means Vigil reacts to a shift the instant it's published, with no
  possibility of missing fast movement between poll intervals.
- Tracks implied win probability per fixture/outcome using TxLINE's precomputed
  `Pct` field.
- Flags a "signal" when probability shifts by more than a configurable threshold,
  with a cooldown window to prevent one volatile market from flooding the log.
- Logs every signal with full before/after values via the shared database layer
  (see below).
- Automatically reconnects on stream drops, so it keeps running unattended.
- Automatically refreshes its short-lived guest JWT when the stream rejects a
  connection with a 401/403, so a deployed instance can run indefinitely without
  manual intervention.
- Requests `gzip, deflate` encoding explicitly (see Known limitations) to avoid
  a Zstandard decoding failure encountered on Linux-based hosts.

**Outcome grading** (`vigil-python/check_outcomes.py`)
Once a monitored fixture reaches `game_finalised`, Vigil pulls the real final
score (including penalty shootouts, when regular time ends level) and checks
whether the direction of each signal correctly predicted the winner — producing
a running accuracy percentage across all resolved signals.

**Persistent storage** (`vigil-python/db.py`)
A thin database abstraction shared by the detector, outcome grader, and
dashboard. When a `DATABASE_URL` environment variable is present (as on the
deployed Render instance), it connects to PostgreSQL; otherwise it falls back
automatically to a local SQLite file. This means the deployed dashboard's
signal history survives service restarts and redeploys, instead of resetting
on every restart (Render's free-tier filesystem is otherwise ephemeral).

**Live dashboard** (`vigil-python/app.py`)
A Flask web app runs the detection engine in a background thread and serves:
- A status bar showing connection state, updates processed, total signals,
  and resolved / correct / incorrect / unresolved counts plus overall accuracy.
- A signal-outcomes doughnut chart, a movement-magnitude distribution bar
  chart, and a signal-activity-over-time line chart (Chart.js).
- A scrollable, sticky-header table of recent signals.
- A JSON API endpoint (`/api/signals`) that the dashboard itself polls every
  few seconds to update numbers and charts in place, without a full-page
  reload, and that could equally be consumed by external tooling.
- A fully responsive layout, with distinct breakpoints for desktop, tablet,
  and phone screen widths.

## Business/technical highlights

- Fully autonomous once started: no manual intervention between stream
  connection, detection, and grading.
- Uses TxLINE's live push stream instead of periodic polling, minimizing
  detection latency.
- Self-healing: reconnects automatically on network/stream failures and
  refreshes its own auth token, allowing indefinite unattended operation.
- Grading logic correctly handles edge cases in the real data (e.g. matches
  decided by penalty shootout rather than regular-time goals).
- Persistent storage via PostgreSQL means signal history and accuracy stats
  survive redeploys and restarts on the live instance, not just locally.
- Deployed and publicly accessible on a responsive dashboard usable across
  desktop, tablet, and phone; note the free hosting tier spins down after
  inactivity, so the first request after idle time may take up to a minute
  to respond.
- Zero cost to run: built entirely on TxLINE's free World Cup devnet tier and
  free-tier hosting/database.

## Known limitations

**Outcome labeling.** Signals are currently labeled by TxLINE's raw
`part1`/`draw`/`part2` outcome codes rather than resolved team names, since
`part1` does not always correspond to the home team (this depends on the
fixture's `Participant1IsHome` flag). Grading logic is unaffected by this, but
a future version could join fixture data to show real team names on the
dashboard.

**Zstandard decoding on Linux hosts.** The `/scores/historical/{fixtureId}`
endpoint's compressed response failed to decode on Render's Linux environment
with a `Zstandard data is incomplete` error, while working fine on Windows
locally. Explicitly restricting `Accept-Encoding` to `gzip, deflate` resolved
it; see `documentation/feedback.md` for more detail.

## TxLINE endpoints used

**Base URL:** `https://txline-dev.txodds.com/api`
**Auth headers required on every request:**

Authorization: Bearer {jwt}
X-Api-Token: {api_token}

| Endpoint | Method | Purpose | Notes |
|---|---|---|---|
| `/auth/guest/start` | POST | Get a short-lived guest JWT | Called on activation and automatically re-called by the detector whenever the stream rejects the current JWT |
| `/token/activate` | POST | Exchange an on-chain `subscribe` tx signature for a long-lived API token | Requires `txSig`, a base64 wallet signature, and `leagues` |
| `/fixtures/updates/{epochDay}/{hourOfDay}` | GET | List fixture updates for a given day/hour window | `epochDay` = days since Unix epoch; `hourOfDay` = UTC hour (0–23) |
| `/odds/stream` | GET (SSE) | Live push stream of odds updates across all subscribed fixtures | Server-Sent Events format (`data: {...}` lines), stays open indefinitely; includes precomputed implied probabilities in the `Pct` field |
| `/scores/historical/{fixtureId}` | GET | Full historical message log for one fixture | Also SSE-formatted despite being a "historical" endpoint, not a plain JSON array, undocumented, we found this out via trial and error |

**Not used, but discovered and available:** `/odds/snapshot/{fixtureId}`, `/scores/snapshot/{fixtureId}`, `/scores/stream`, `/scores/updates/{epochDay}/{hourOfDay}/{interval}`, `/fixtures/snapshot`, `/fixtures/validation`, `/scores/stat-validation`, these support on-chain cryptographic validation of the data, which we didn't build into the detector itself but could be a natural next step.

**Key data fields relied on:**
- Odds: `FixtureId`, `SuperOddsType` (filtered to `1X2_PARTICIPANT_RESULT`), `PriceNames`, `Pct`
- Scores: `Action` (filtered to `game_finalised`), `Score.Participant1/2.Total.Goals`, `Score.Participant1/2.PE.Goals` (penalty shootout, when regular time is tied)