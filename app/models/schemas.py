from __future__ import annotations
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str


class SourcePick(BaseModel):
    source_name: str
    source_url: str
    market: str
    pick: str
    quoted_odds: float | None = None
    confidence_text: str | None = None
    reason_summary: str | None = None


class RankedMatch(BaseModel):
    match_id: str
    home_team: str
    away_team: str
    competition: str
    kickoff: str
    market: str
    recommended_pick: str
    best_odds: float = Field(..., gt=1.0)
    consensus_score: float = Field(..., ge=0.0, le=1.0)
    price_edge_score: float = Field(..., ge=0.0, le=1.0)
    source_count: int = Field(..., ge=0)
    final_score: float = Field(..., ge=0.0, le=1.0)
    sources: list[SourcePick]
    explanation: str
