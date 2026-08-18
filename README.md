# Bet Aggregator MVP

Aggregates free football predictions from multiple sources, compares them for
cross-source consensus, and ranks the top 20 best-value matches. Runs
entirely on GitHub — no server to host or pay for.

## Architecture
- `app/collectors/` — adapters for free prediction sites. Working: FreeSuperTips (embedded Next.js JSON), Vitibet (~200 matches/~60 leagues), Adibet (old table markup, Greek leagues included), MyBetsToday (schema.org-annotated, ~70 fixtures/run), Statarea (semantic markup, Greek leagues included). `common.py` holds the `1`/`X`/`2`/`1X`/`X2`/`12` tip-code map shared by Vitibet/Adibet/MyBetsToday/Statarea. Non-functional by design, kept for visibility in `meta.json`: PredictZ (Cloudflare bot-challenge) and StatsBet (data loaded client-side from a robots.txt-disallowed `/api/`) — neither can be fixed without bypassing bot protection or violating robots.txt, so don't try; replace them with new compliant sources instead. Checked but not pursued: wintips.com (real data, but hashed/regenerating CSS classes — too fragile), betarades.gr (promising, Greek, right URL not found yet), kickoff.com/tipstrr.com (no daily pick data found on inspection).
- `app/llm/` — extraction/summarization helper returning strict JSON per pick (not wired into the pipeline yet — future phase)
- `app/odds/` — best-price lookup and EV scoring across bookmakers (needs `ODDS_API_KEY`; skipped gracefully if unset)
- `app/ranking/` — fixture grouping, consensus + edge scoring → top-20 output
- `app/history/` — `grader.py` grades a finished pick (hit/miss/push/unknown) against a final score; `reliability.py` computes a Bayesian-shrunk per-source hit rate from graded history; `store.py` reads/writes `docs/data/history.json` and `source-reliability.json`
- `scripts/run_pipeline.py` — runs the collectors + ranking engine, writes `docs/data/ranked-matches.json`/`meta.json`, and upserts the current top-20 into `docs/data/history.json`
- `scripts/check_results.py` — daily: grades pending `history.json` entries whose kickoff has passed, writes `docs/data/history-summary.json`
- `docs/` — static dashboard, deployed via GitHub Pages, with a "Κατάταξη"/"Ιστορικό" tab switcher reading `ranked-matches.json`/`meta.json` and `history.json`/`history-summary.json` respectively

## Refreshing the data
There is no live backend. `run-pipeline.yml` runs automatically on a cron
schedule (every 30 minutes, UTC) and can also be triggered manually:

1. It runs `scripts/run_pipeline.py` and commits the updated
   `docs/data/ranked-matches.json` and `docs/data/meta.json` if they changed.
2. That push triggers the existing **Deploy GitHub Pages** workflow, which
   republishes `docs/` with the new data.
3. Open the dashboard and click "Ανανέωση προβολής" (cache-busted fetch of
   the same static files) if it doesn't show the new data right away.

To trigger a run on demand instead of waiting for the schedule: repo's
**Actions** tab → **Run pipeline** → **Run workflow**.

**Caveat:** GitHub disables scheduled (`cron`) workflows automatically after
60 days with no repository activity (pushes/commits) — if the dashboard
ever looks stale for a long stretch, check **Actions → Run pipeline** for a
banner saying the schedule was disabled, and re-enable it there.

## Ιστορικό (results history)
`check-results.yml` runs once a day (`06:00 UTC` cron + manual `workflow_dispatch`)
and grades every past-kickoff `pending` entry in `docs/data/history.json`
against real final scores — **from Vitibet itself**, not a new source:
`app/collectors/vitibet.py:fetch_results(date)` reuses the same livescore
page `fetch_picks()` already scrapes, just with a `&date=YYYY-MM-DD` param,
which returns real FT scores for past dates (confirmed live: 141 finished
matches for a single past day). This was chosen over flashscore.com, which
the user originally suggested — flashscore's robots.txt is technically
permissive but the site is known for aggressively enforcing its ToS against
scrapers, a real risk not worth taking when we already have a compliant,
already-integrated source for the same data.

Grading (`app/history/grader.py`) supports 1X2, Double Chance, Total
Goals (Over/Under), BTTS, Draw No Bet, and Correct Score. Anything else
(e.g. an anytime-goalscorer pick — no player-level data available) is
graded `unknown`, never guessed. A pick whose fixture Vitibet doesn't
cover stays `pending` for up to 7 days, then flips to `unknown` instead of
hanging forever.

### Optional: live odds
Add `ODDS_API_KEY` under **Settings → Secrets and variables → Actions** to
enable live odds lookups via [The Odds API](https://the-odds-api.com/).
Without it, the pipeline still runs and falls back to quoted odds from the
collectors.

## Local run
```bash
pip install -r requirements.txt
python scripts/run_pipeline.py   # writes docs/data/ranked-matches.json + meta.json + history.json
python scripts/check_results.py  # grades pending history.json entries, writes history-summary.json + source-reliability.json
pytest                            # runs the full test suite (no network)
```

## Known limitations (by design, for now)
- Team-name matching across sources uses a simple normalizer (lowercase,
  strip common club suffixes), not a maintained alias table — distinct
  spellings of the same club (e.g. "Man Utd" vs "Manchester United") won't
  merge yet.
- `competition`/`kickoff` are real when the source provides them
  (FreeSuperTips, Vitibet); collectors that don't (PredictZ, StatsBet) fall
  back to "European"/"TBD".
- Odds matching (`app/odds/adapter.py`) maps competition names to a
  curated list of major-league sport keys (Champions/Europa/Conference
  League, top-5 European leagues, Greek Super League) via keyword
  matching — competitions outside that list skip the live-odds call
  entirely and fall back to quoted odds. `MAX_ODDS_CALLS = 30` in
  `app/ranking/engine.py` caps live-odds requests per pipeline run, but
  with `run-pipeline.yml` now firing every 30 minutes (48 runs/day) the
  free tier's 500 req/month can still be exhausted well before the month
  ends if several mapped-league matches are live at once — the adapter
  fails silently (falls back to `None`/quoted odds) when that happens, it
  won't break anything, live odds just stop appearing until next month's
  quota resets. Lower `MAX_ODDS_CALLS` or the run frequency if that
  matters to you. Team-name matching within a mapped league is still
  exact-ish, so treat live odds as best-effort even when a call succeeds.
- `SOURCE_RELIABILITY` in `app/ranking/engine.py` is now just the
  fallback for sources with no graded history yet. Once
  `docs/data/source-reliability.json` exists (written daily by
  `check-results.yml` via `app/history/reliability.py`), a source's
  actual Bayesian-shrunk hit rate overrides its static guess — no
  database needed, `history.json` already has everything.
- `MIN_SOURCES` in `app/ranking/engine.py` is `1` — there's no hard
  cross-source-agreement gate. With only 2 working collectors, requiring
  3+ agreeing sources would mean the dashboard is permanently empty, so
  results are shown for any pick and simply sorted by `final_score`
  (which weights consensus + source_quality), highest agreement first.
  `source_count`/`consensus_score` are shown on every card so a
  single-source pick is never mistaken for a confirmed one. Raise
  `MIN_SOURCES` back to 3 once a 3rd compliant collector exists.
- Collector selectors/parsers target each site's current markup and are
  not guaranteed to still match — check `meta.json`'s `sources` array
  after each run for per-source errors/pick counts.
- Results-checking depends entirely on Vitibet's own results coverage
  (~60 leagues). Picks for fixtures outside that (currently only possible
  from FreeSuperTips) can't be graded and end up `unknown` after 7 days.
- `run-pipeline.yml` (every 30 min) and `check-results.yml` (daily) both commit
  to `docs/data/history.json`; if they ever run at the exact same moment
  one push can fail with a non-fast-forward error — harmless, just re-run
  that workflow.

This app returns research signals, not betting advice, and never claims a
guaranteed outcome. Please gamble responsibly.
