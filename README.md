# Bet Aggregator

Aggregates free football predictions from several sources, compares them for
cross-source consensus, and shows the highest-confidence matches per
continent and league. Runs entirely on GitHub (Actions + Pages) — no server
to host or pay for.

## Dashboard (`docs/`)
Static page deployed via GitHub Pages, mobile/tablet/desktop responsive:
- **Ευρώπη / Ασία / Αμερική / Αφρική** — up to 20 matches per continent.
  Europe and Asia also have a league/cup sub-navigation (top 12 European and
  top 4 Asian leagues, continental competitions, and the domestic cups of the
  same countries).
- Each match is one card. If several picks exist for it (e.g. 1X2 and Double
  Chance) they are grouped as sub-tabs inside the card.
- Sort by score, highest odds or highest consensus, and filter by source
  (the source dropdown is ordered by real graded hit rate).
- **Ιστορικό** — finished, graded predictions only (last 20 shown), filterable
  by source. Pending picks are hidden.
- **Πηγές** — per-source hit/miss counts, hit rate and reliability score.

## Sources
Working collectors in `app/collectors/`: **Vitibet**, **Adibet**, **Statarea**.
`common.py` holds the `1`/`X`/`2`/`1X`/`X2`/`12` tip-code map they share.

Removed: FreeSuperTips (28% graded hit rate) and MyBetsToday. Their graded
entries stay in `history.json`, but the dashboard hides them
(`REMOVED_SOURCES` in `docs/index.html`).

Non-functional by design, kept for visibility in `meta.json`: PredictZ
(Cloudflare bot challenge) and StatsBet (data loaded client-side from a
robots.txt-disallowed `/api/`). Neither can be fixed without bypassing bot
protection or violating robots.txt, so don't try — replace them with new
compliant sources instead.

## Ranking (`app/ranking/`)
- Picks are grouped per fixture (team names normalized across sources) into a
  `MatchCard` whose picks are sorted by `final_score`.
- `final_score` combines source quality, consensus, price edge and EV, with
  consensus acting as a confidence multiplier.
- `MIN_FINAL_SCORE = 0.50`: a match whose best pick scores below this is
  dropped entirely, on top of the `TARGET_COUNT = 20` cap. `MIN_SOURCES` stays
  `1` on purpose — a single strong source is not excluded for being alone.
- Stale matches are removed two ways: kickoff more than 2 hours in the past,
  and a cross-check against Vitibet's finished results for today and yesterday
  (some sources give a bare `HH:MM` with no date, so a finished match can look
  like it is upcoming).
- Odds come from Vitibet's match-detail page first, then The Odds API (if
  `ODDS_API_KEY` is set), then quoted odds. With no real price the odds show
  as `—`.

## Other modules
- `app/history/` — `grader.py` grades a pick (hit/miss/push/unknown) against a
  final score; `reliability.py` computes a Bayesian-shrunk per-source hit rate
  and the raw per-source stats; `store.py` reads/writes the history files.
- `app/odds/` — best-price lookup (needs `ODDS_API_KEY`; skipped if unset).
- `app/llm/` — extraction helper, not wired into the pipeline.

## Data refresh
- `run-pipeline.yml` — every 3 hours (`11 */3 * * *` UTC) and manually. Runs
  `scripts/run_pipeline.py`, commits `ranked-matches.json`, `meta.json` and
  `history.json`.
- `check-results.yml` — daily (`17 6 * * *` UTC) and manually. Runs
  `scripts/check_results.py`, which grades pending history entries and writes
  `history-summary.json`, `source-reliability.json` and `source-stats.json`.
- Both commit with a rebase-and-retry push, so concurrent runs don't fail.
- Each push triggers **Deploy GitHub Pages**.

Cron times avoid the top of the hour on purpose: GitHub delays or drops
`:00` schedules under load. Scheduled runs are still best-effort, and GitHub
disables them after 60 days without repository activity — if the data looks
stale, check the **Actions** tab and re-run manually.

To trigger a run: **Actions** → **Run pipeline** (or **Check results**) →
**Run workflow**.

## Ιστορικό and grading
Real final scores come from Vitibet's own livescore page
(`fetch_results(date)`), not from flashscore.com, whose ToS enforcement
against scrapers is a real risk. Grading supports 1X2, Double Chance, Total
Goals, BTTS, Draw No Bet and Correct Score; anything else is `unknown`, never
guessed. A pick Vitibet doesn't cover stays `pending` for 7 days, then becomes
`unknown`.

`SOURCE_RELIABILITY` in `engine.py` is only the fallback for sources with no
graded history; once `source-reliability.json` exists it overrides the static
value.

## Local run
```bash
pip install -r requirements.txt
python scripts/run_pipeline.py   # ranked-matches.json, meta.json, history.json
python scripts/check_results.py  # grades history, writes summary/reliability/stats
pytest                            # full suite, no network
```

## Known limitations
- Team-name matching is a simple normalizer, not an alias table ("Man Utd" and
  "Manchester United" won't merge).
- Live odds cover a curated list of major leagues only, capped at
  `MAX_ODDS_CALLS = 30` per run; everything else falls back to quoted odds or
  `—`.
- Collector selectors target each site's current markup and can break — check
  the `sources` array in `meta.json` after a run.
- Grading depends on Vitibet's results coverage (~60 leagues); other fixtures
  end up `unknown`.
- Many picks end up `unknown` for markets the grader can't verify.

This app returns research signals, not betting advice, and never claims a
guaranteed outcome. Please gamble responsibly.
