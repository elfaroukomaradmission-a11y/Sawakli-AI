from fastapi import FastAPI

app = FastAPI(title="Sawakli Agent")


@app.get("/health")
def health_check():
    return {"status": "ok"}