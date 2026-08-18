from pydantic import BaseModel
import os

class Settings(BaseModel):
    app_name: str = "Bet Aggregator MVP"
    min_sources_per_match: int = 3
    target_rank_count: int = 20
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    odds_api_key: str = os.getenv("ODDS_API_KEY", "")

settings = Settings()
