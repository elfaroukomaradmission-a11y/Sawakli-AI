from fastapi import FastAPI

from sawakli.api.routes.analysis import router as analysis_router
from sawakli.api.routes.auth import router as auth_router
from sawakli.api.routes.jobs import router as jobs_router

app = FastAPI()
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(jobs_router, prefix="/api/jobs", tags=["jobs"])
app.include_router(analysis_router, prefix="/api/analysis", tags=["analysis"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
