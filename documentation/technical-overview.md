# Vigil Technical Overview

## Core idea

Sports betting odds move the instant new information becomes available, before
most casual bettors ever notice. Vigil is an autonomous agent that watches
TxLINE's live World Cup odds feed in real time, flags statistically significant
shifts in win probability ("sharp movements"), and automatically checks each
flagged signal against the real match outcome once it finishes, turning raw
odds noise into a measurable accuracy record, presented on a live, responsive
dashboard and pushed directly to a Telegram bot.

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
- Logs every signal with full before/after values via the shared database layer.
- Automatically reconnects on stream drops, so it keeps running unattended.
- Automatically refreshes its short-lived guest JWT when the stream rejects a
  connection with a 401/403, so a deployed instance can run indefinitely without
  manual intervention. This JWT is also shared with the fixture-name resolver
  (see below), rather than each component tracking its own copy.
- Requests `gzip, deflate` encoding explicitly (see Known limitations) to avoid
  a Zstandard decoding failure encountered on Linux-based hosts.

**Outcome grading** (`vigil-python/check_outcomes.py`)
Vigil determines a fixture is finished when either TxLINE's `game_finalised`
action fires, or the game clock reports a terminal status (5 = full-time, 10 =
after extra time, 13 = after penalty shootout), whichever arrives first, since
reliance on `game_finalised` alone proved insufficient for some fixtures during
testing. Once finished, Vigil compares final goal totals to determine the
winner; if level, it checks for penalty-shootout data. A shootout only occurs to
break a tie, so its presence always resolves to a winner, while its absence with
a level score confirms a genuine draw.

**Fixture name resolution** (`vigil-python/fixtures.py`)
A background service that periodically scans TxLINE's fixture-updates endpoint
to build a map of fixture ID → real team names, used to display signals as
"Spain vs Argentina - Argentina" rather than raw fixture IDs and `part1`/`part2`
codes. Discovered names are saved to the database immediately, so on restart the
full cache loads instantly rather than being rebuilt from scratch (the initial
scan covers a full week of hourly windows and can take a few minutes).

**Persistent storage** (`vigil-python/db.py`)
A thin database abstraction shared by the detector, outcome grader, fixture
resolver, dashboard, and Telegram bot. When a `DATABASE_URL` environment
variable is present (as on the deployed Render instance), it connects to
PostgreSQL; otherwise it falls back automatically to a local SQLite file.
Signals, Telegram subscriber chat IDs, and known fixture names all persist
across service restarts and redeploys, instead of resetting (Render's free-tier
filesystem is otherwise ephemeral).

**Live dashboard** (`vigil-python/app.py`)
A Flask web app runs the detection engine in a background thread and serves:
- A status bar showing connection state, updates processed, total signals,
  and resolved/correct/incorrect/unresolved counts plus overall accuracy.
- A signal-outcomes doughnut chart, a movement-magnitude distribution bar
  chart, and a signal-activity-over-time line chart (Chart.js).
- A scrollable, sticky-header table of recent signals, shown with real team
  names.
- A JSON API endpoint (`/api/signals`) that the dashboard itself polls every
  few seconds to update numbers and charts in place, without a full-page
  reload.
- A fully responsive layout, with distinct breakpoints for desktop, tablet,
  and phone screen widths.

**Telegram bot** (`vigil-python/telegram_bot.py`)
Runs as a third background thread alongside the detector and fixture resolver.
Provides:
- Automatic push alerts to all subscribers the instant a signal is detected,
  with real team names and a clear before/after percentage breakdown.
- Two-way commands: `/status`, `/summary` (full stats digest), `/accuracy`,
  `/recent`, `/matches`, `/start` (subscribe), `/stop` (unsubscribe).
- Subscriber chat IDs persist in the shared database, so subscriptions survive
  restarts.

## Business/technical highlights

- Fully autonomous once started: no manual intervention between stream
  connection, detection, and grading.
- Uses TxLINE's live push stream instead of periodic polling, minimizing
  detection latency.
- Self-healing: reconnects automatically on network/stream failures and
  refreshes its own auth token, allowing indefinite unattended operation.
- Grading logic correctly handles edge cases in the real data (e.g. matches
  decided by penalty shootout rather than regular-time goals) and uses a
  two-signal approach to detect match completion reliably.
- Two independent, live interfaces onto the same running agent: a responsive
  web dashboard and a Telegram bot with both push alerts and on-demand queries.
- Persistent storage via PostgreSQL means signal history, Telegram
  subscriptions, and fixture name lookups all survive redeploys and restarts.
- Deployed and publicly accessible on a responsive dashboard usable across
  desktop, tablet, and phone; note the free hosting tier spins down after
  inactivity, so the first request after idle time may take up to a minute
  to respond.
- Zero cost to run: built entirely on TxLINE's free World Cup devnet tier and
  free-tier hosting/database.

## Known limitations

**Coverage gaps between odds and scores data.** Some fixtures that appear in
odds/fixture data have no corresponding scores history at all (the
`/scores/historical/{fixtureId}` endpoint returns a 200 with an empty body,
confirmed on a real fixture, Colombia vs Portugal). This appears to reflect
TxLINE's underlying scores coverage approval process rather than a
client-side issue. Vigil's outcome grader correctly treats these as
unresolved rather than erroring, but it means not every odds signal is
guaranteed to eventually become gradeable.

**Zstandard decoding on Linux hosts.** The `/scores/historical/{fixtureId}`
endpoint's compressed response failed to decode on Render's Linux environment
with a `Zstandard data is incomplete` error, while working fine on Windows
locally. Explicitly restricting `Accept-Encoding` to `gzip, deflate` resolved
it.

**Fixture name resolution has a cold-start cost.** The very first time Vigil
sees a fixture it has never encountered before, it's briefly shown by raw ID
until the next background scan resolves it. Once resolved, the name is saved
permanently and shown instantly from then on, including across restarts.

## TxLINE endpoints used

**Base URL:** `https://txline-dev.txodds.com/api`
**Auth headers required on every request:**

Authorization: Bearer {jwt}
X-Api-Token: {api_token}

| Endpoint | Method | Purpose | Notes |
|---|---|---|---|
| `/auth/guest/start` | POST | Get a short-lived guest JWT | Called on activation and automatically re-called by the detector whenever the stream rejects the current JWT; the fixture resolver shares this same, always-current JWT rather than tracking its own |
| `/token/activate` | POST | Exchange an on-chain `subscribe` tx signature for a long-lived API token | Requires `txSig`, a base64 wallet signature, and `leagues` |
| `/fixtures/updates/{epochDay}/{hourOfDay}` | GET | List fixture updates for a given day/hour window, including team names | `epochDay` = days since Unix epoch; `hourOfDay` = UTC hour (0–23); used both for general fixture discovery and for resolving team names |
| `/odds/stream` | GET (SSE) | Live push stream of odds updates across all subscribed fixtures | Server-Sent Events format (`data: {...}` lines), stays open indefinitely; includes precomputed implied probabilities in the `Pct` field |
| `/scores/historical/{fixtureId}` | GET | Full historical message log for one fixture | Also SSE-formatted despite being a "historical" endpoint, not a plain JSON array, undocumented, we found this out via trial and error |

**Not used, but discovered and available:** `/odds/snapshot/{fixtureId}`, `/scores/snapshot/{fixtureId}`, `/scores/stream`, `/scores/updates/{epochDay}/{hourOfDay}/{interval}`, `/fixtures/snapshot`, `/fixtures/validation`, `/scores/stat-validation`, these support on-chain cryptographic validation of the data, which we didn't build into the detector itself but could be a natural next step.

**Key data fields relied on:**
- Odds: `FixtureId`, `SuperOddsType` (filtered to `1X2_PARTICIPANT_RESULT`), `PriceNames`, `Pct`
- Scores: `Action` (filtered to `game_finalised` and `status`), `Data.StatusId`, `Score.Participant1/2.Total.Goals`, `Score.Participant1/2.PE.Goals` (penalty shootout, when regular time is tied)
- Fixtures: `FixtureId`, `Participant1`, `Participant2`