# Bet Aggregator MVP

FastAPI backend that aggregates free football predictions from multiple sources,
extracts structured picks via LLM, compares odds across bookmakers and ranks the
top 20 best-value matches every run.

## Architecture
- `app/collectors/` — adapters for free prediction sites (PredictZ, FreeSuperTips, StatsBet)
- `app/llm/` — extraction/summarization returning strict JSON per pick
- `app/odds/` — best-price lookup and EV scoring across bookmakers
- `app/ranking/` — consensus + edge scoring → top-20 output
- `app/api/` — FastAPI routes

## Endpoints
| Route | Description |
|---|---|
| `GET /health` | Service health check |
| `GET /sources/raw` | Raw picks from all collectors |
| `GET /ranked-matches` | Top 20 ranked matches |

## Deploy (Render)
1. Connect GitHub repo on [render.com](https://render.com)
2. `render.yaml` handles build + start commands automatically
3. Each push to `main` triggers an auto-deploy

## Local run
```bash
pip install -r requirements.txt
uvicorn main:app --reload
```
