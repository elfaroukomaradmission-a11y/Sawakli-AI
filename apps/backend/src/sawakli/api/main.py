import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sawakli.api.routes import auth, campaigns

app = FastAPI()

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(auth.router)
app.include_router(campaigns.router)

# app.include_router(api_routes.auth, prefix="/api/", tags=["auth"])
# app.include_router(api_routes.campaigns, prefix="/api", tags=["Dashboard"])

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

#Running Command: uv run uvicorn sawakli.api.main:app --reload --port 8000 