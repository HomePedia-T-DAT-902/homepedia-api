"""Point d'entrée FastAPI."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import communes, geo

app = FastAPI(
    title="Homepedia API",
    description="API d'analyse du marché immobilier français",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # type: ignore[arg-type]
    allow_credentials=True,  # type: ignore[arg-type]
    allow_methods=["*"],  # type: ignore[arg-type]
    allow_headers=["*"],  # type: ignore[arg-type]
)

app.include_router(communes.router)
app.include_router(geo.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
