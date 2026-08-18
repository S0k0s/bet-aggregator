# Bet Aggregator MVP

Aggregates free football predictions from multiple sources, compares them for
cross-source consensus, and ranks the top 20 best-value matches. Runs
entirely on GitHub — no server to host or pay for.

## Architecture
- `app/collectors/` — adapters for free prediction sites (PredictZ, FreeSuperTips, StatsBet)
- `app/llm/` — extraction/summarization helper returning strict JSON per pick (not wired into the pipeline yet — future phase)
- `app/odds/` — best-price lookup and EV scoring across bookmakers (needs `ODDS_API_KEY`; skipped gracefully if unset)
- `app/ranking/` — fixture grouping, consensus + edge scoring → top-20 output
- `scripts/run_pipeline.py` — runs the collectors + ranking engine and writes `docs/data/*.json`
- `docs/` — static dashboard, deployed via GitHub Pages, reads `docs/data/ranked-matches.json` / `meta.json`

## Refreshing the data
There is no live backend. `run-pipeline.yml` runs automatically on a cron
schedule (every 3 hours, UTC) and can also be triggered manually:

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

### Optional: live odds
Add `ODDS_API_KEY` under **Settings → Secrets and variables → Actions** to
enable live odds lookups via [The Odds API](https://the-odds-api.com/).
Without it, the pipeline still runs and falls back to quoted odds from the
collectors.

## Local run
```bash
pip install -r requirements.txt
python scripts/run_pipeline.py   # writes docs/data/ranked-matches.json + meta.json
pytest                            # runs the ranking-engine test suite (no network)
```

## Known limitations (by design, for now)
- Team-name matching across sources uses a simple normalizer (lowercase,
  strip common club suffixes), not a maintained alias table — distinct
  spellings of the same club (e.g. "Man Utd" vs "Manchester United") won't
  merge yet.
- `competition` and `kickoff` are placeholders — no collector currently
  parses them from the source sites.
- Odds matching (`app/odds/adapter.py`) is hardcoded to `soccer_epl` and
  does exact-ish team-name matching only; treat live odds as best-effort.
- No historical reliability tracking, database, or closing-line-value
  scoring yet — `SOURCE_RELIABILITY` in `app/ranking/engine.py` is a fixed
  starting guess, not measured performance.
- Collector selectors are prototypes against each site's current HTML and
  are not guaranteed to still match — check `meta.json`'s `sources` array
  after each run for per-source errors/pick counts.

This app returns research signals, not betting advice, and never claims a
guaranteed outcome. Please gamble responsibly.
