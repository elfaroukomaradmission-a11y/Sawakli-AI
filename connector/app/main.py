from fastapi import FastAPI

app = FastAPI(title="Sawakli Connector")


@app.get("/health")
def health_check():
    return {"status": "ok"}