from fastapi import APIRouter
from app.models.schemas import HealthResponse, SourcePick, RankedMatch
from app.collectors.predictz import PredictZCollector
from app.collectors.freesupertips import FreeSuperTipsCollector
from app.collectors.statsbet import StatsBetCollector
from app.ranking.engine import build_ranked_matches

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="bet-aggregator")


@router.get("/sources/raw", response_model=dict[str, list[SourcePick]])
async def raw_sources() -> dict[str, list[SourcePick]]:
    collectors = [PredictZCollector(), FreeSuperTipsCollector(), StatsBetCollector()]
    result: dict[str, list[SourcePick]] = {}
    for c in collectors:
        result[c.name] = await c.fetch_picks()
    return result


@router.get("/ranked-matches", response_model=list[RankedMatch])
async def ranked_matches() -> list[RankedMatch]:
    collectors = [PredictZCollector(), FreeSuperTipsCollector(), StatsBetCollector()]
    all_picks: list[SourcePick] = []
    for c in collectors:
        all_picks.extend(await c.fetch_picks())
    return await build_ranked_matches(all_picks)
