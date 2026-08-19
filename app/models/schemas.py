from __future__ import annotations
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str


class SourcePick(BaseModel):
    source_name: str
    source_url: str
    home_team: str
    away_team: str
    market: str
    pick: str
    quoted_odds: float | None = None
    confidence_text: str | None = None
    reason_summary: str | None = None
    competition: str | None = None
    kickoff: str | None = None


class RankedMatch(BaseModel):
    match_id: str
    home_team: str
    away_team: str
    competition: str
    kickoff: str
    market: str
    recommended_pick: str
    best_odds: float | None = None
    consensus_score: float = Field(..., ge=0.0, le=1.0)
    price_edge_score: float = Field(..., ge=0.0, le=1.0)
    source_count: int = Field(..., ge=0)
    final_score: float = Field(..., ge=0.0, le=1.0)
    sources: list[SourcePick]
    explanation: str


class MatchCard(BaseModel):
    """One real-world fixture, grouping every recommended (market, pick)
    combo for it under a single card instead of each eating its own
    top-20 slot. `picks` is sorted by final_score descending — picks[0]
    is what the card's own rank/score in a list is based on."""
    match_id: str
    home_team: str
    away_team: str
    competition: str
    kickoff: str
    picks: list[RankedMatch]
