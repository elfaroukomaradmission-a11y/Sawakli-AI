from fastapi import FastAPI

from src.db import get_connection

app = FastAPI(title="Sawakli Database App")


@app.get("/health")
def health_check():
    try:
        conn = get_connection()
        conn.close()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}