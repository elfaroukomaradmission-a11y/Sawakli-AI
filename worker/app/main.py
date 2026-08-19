from fastapi import FastAPI

app = FastAPI(title="Sawakli Worker")


@app.get("/health")
def health_check():
    return {"status": "ok"}