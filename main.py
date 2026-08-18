from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router

app = FastAPI(
    title="Bet Aggregator MVP",
    version="0.1.0",
    description="Aggregates free football predictions and ranks top-20 value matches."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://s0k0s.github.io",
        "http://localhost:3000",
        "http://localhost:5500",
    ],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(router)
