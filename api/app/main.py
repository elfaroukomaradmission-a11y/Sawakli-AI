from fastapi import FastAPI

app = FastAPI(title="Sawakli API")


@app.get("/health")
def health_check():
    return {"status": "ok"}