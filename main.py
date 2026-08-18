from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(
    title="Bet Aggregator MVP",
    version="0.1.0",
    description="Aggregates free football predictions and ranks top-20 value matches."
)
app.include_router(router)
