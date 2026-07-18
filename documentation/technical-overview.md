# Vigil Technical Overview

## Core idea

Sports betting odds move the instant new information becomes available, before
most casual bettors ever notice. Vigil is an autonomous agent that watches
TxLINE's live World Cup odds feed in real time, flags statistically significant
shifts in win probability ("sharp movements"), and automatically checks each
flagged signal against the real match outcome once it finishes, turning raw
odds noise into a measurable accuracy record.

## Architecture

**Wallet & activation** (`vigil-connect/`)
A small browser app connects a Phantom wallet on Solana devnet, submits the
on-chain `subscribe` transaction for TxLINE's free World Cup tier, and activates
an API token via signed message authentication.

**Detection engine** (`vigil-python/`)
- Connects to TxLINE's live odds stream (Server-Sent Events) rather than polling, 
  this means Vigil reacts to a shift the instant it's published, with no
  possibility of missing fast movement between poll intervals.
- Tracks implied win probability per fixture/outcome using TxLINE's precomputed
  `Pct` field.
- Flags a "signal" when probability shifts by more than a configurable threshold,
  with a cooldown window to prevent one volatile market from flooding the log.
- Logs every signal to a local SQLite database with full before/after values.
- Automatically reconnects on stream drops, so it keeps running unattended.

**Outcome grading**
Once a monitored fixture reaches `game_finalised`, Vigil pulls the real final
score (including penalty shootouts, when regular time ends level) and checks
whether the direction of each signal correctly predicted the winner, producing
a running accuracy percentage across all resolved signals.

## Business/technical highlights

- Fully autonomous once started: no manual intervention between stream
  connection and signal grading.
- Uses TxLINE's live push stream instead of periodic polling, minimizing
  detection latency.
- Self-healing: reconnects automatically on network/stream failures.
- Grading logic correctly handles edge cases in the real data (e.g. matches
  decided by penalty shootout rather than regular-time goals).
- Zero cost to run: built entirely on TxLINE's free World Cup devnet tier.

## TxLINE endpoints used

**Base URL:** `https://txline-dev.txodds.com/api`
**Auth headers required on every request:**

Authorization: Bearer {jwt}
X-Api-Token: {api_token}

| Endpoint | Method | Purpose | Notes |
|---|---|---|---|
| `/auth/guest/start` | POST | Get a short-lived guest JWT | Called once during activation; JWT expires and needs renewal for long-running sessions |
| `/token/activate` | POST | Exchange an on-chain `subscribe` tx signature for a long-lived API token | Requires `txSig`, a base64 wallet signature, and `leagues` |
| `/fixtures/updates/{epochDay}/{hourOfDay}` | GET | List fixture updates for a given day/hour window | `epochDay` = days since Unix epoch; `hourOfDay` = UTC hour (0–23) |
| `/odds/stream` | GET (SSE) | Live push stream of odds updates across all subscribed fixtures | Server-Sent Events format (`data: {...}` lines), stays open indefinitely; includes precomputed implied probabilities in the `Pct` field |
| `/scores/historical/{fixtureId}` | GET | Full historical message log for one fixture | Also SSE-formatted despite being a "historical" endpoint, not a plain JSON array, undocumented, we found this out via trial and error |

**Not used, but discovered and available:** `/odds/snapshot/{fixtureId}`, `/scores/snapshot/{fixtureId}`, `/scores/stream`, `/scores/updates/{epochDay}/{hourOfDay}/{interval}`, `/fixtures/snapshot`, `/fixtures/validation`, `/scores/stat-validation`, these support on-chain cryptographic validation of the data, which we didn't build into the detector itself but could be a natural next step.

**Key data fields relied on:**
- Odds: `FixtureId`, `SuperOddsType` (filtered to `1X2_PARTICIPANT_RESULT`), `PriceNames`, `Pct`
- Scores: `Action` (filtered to `game_finalised`), `Score.Participant1/2.Total.Goals`, `Score.Participant1/2.PE.Goals` (penalty shootout, when regular time is tied)