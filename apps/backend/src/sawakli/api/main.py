from fastapi import FastAPI

from sawakli.api.routes.auth import router as auth_router
from sawakli.api.routes.jobs import router as jobs_router

app = FastAPI()
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(jobs_router, prefix="/api/jobs", tags=["jobs"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
