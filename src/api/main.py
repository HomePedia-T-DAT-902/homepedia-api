"""Point d'entrée FastAPI."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import communes, geo, reviews

app = FastAPI(
    title="Homepedia API",
    description="API d'analyse du marché immobilier français",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(communes.router)
app.include_router(geo.router)
app.include_router(reviews.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
