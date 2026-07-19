# Feedback on the TxLINE API

**What I liked:** The live SSE streams for odds and scores are genuinely well
designed, getting implied win probabilities (`Pct`) precomputed in the odds
feed saved us from writing our own conversion logic. The free devnet tier made
it possible to build a fully working prototype with zero cost.

**Where I hit friction:** The published documentation examples (subscribe/
activate flow, endpoint paths) didn't match the real, current API I had to go
into the `tx-on-chain` GitHub repo directly and read the actual example scripts
to find working endpoint paths (`/fixtures/updates/{epochDay}/{hourOfDay}`,
`/odds/stream`, `/scores/historical/{fixtureId}`), since the docs site's listed
shapes returned 404s. The `/scores/historical` endpoint also returns
Server-Sent-Events format rather than a plain JSON array, which isn't mentioned
anywhere and took some trial and error to figure out. It would help to have the
devnet IDL and a minimal working end-to-end example (wallet → subscribe →
activate → first data call) linked directly and prominently from the main docs.

**One more friction point (deployment):** When running on a Linux-based host
(Render), the `/scores/historical/{fixtureId}` endpoint's response failed to
decode with a `Zstandard data is incomplete` error, the same code worked fine
on Windows locally. Explicitly restricting `Accept-Encoding` to `gzip, deflate`
resolved it. This suggests the endpoint's Zstandard-compressed response doesn't
always terminate cleanly, or isn't fully supported by all client environments.
Worth flagging on TxLINE's end, since it's not obvious from the client side
which encoding is causing trouble.

**Coverage gaps between odds and scores data:** Some fixtures that appear in
odds/fixture data have no corresponding scores history at all (the
`/scores/historical/{fixtureId}` endpoint returns a 200 with an empty body,
confirmed on a real fixture, Colombia vs Portugal). This appears to reflect
TxLINE's underlying scores coverage approval process rather than a client-side
issue. It would help to have a documented way to check scores-coverage status
for a given fixture ahead of time (the `CoverageStatus` field mentioned in the
Scores API documentation didn't appear to be exposed on the endpoints I used).

**Match finish detection required a fallback.** Relying solely on the
`game_finalised` action to detect a completed match proved unreliable for some
fixtures. Vigil now also treats the game clock reaching a terminal `StatusId`
(5 = full-time, 10 = after extra time, 13 = after penalty shootout) as
confirmation the match is over, using whichever signal arrives first. It's not
fully clear from the documentation which of these should be treated as the
authoritative "match is truly over" signal, or whether they're always meant to
both fire.

**Small but useful:** `/fixtures/updates/{epochDay}/{hourOfDay}` doubles nicely
as a source of real team names, not just fixture metadata, I used it to
resolve human-readable names for our dashboard and Telegram bot, on top of its
primary purpose of fixture discovery.