"""Custom server entrypoint — everything `adk api_server` provides, plus a
small /favorites API backed by Firestore (favorites_store.py) that the ADK
CLI has no way to add. Run with `python server.py` instead of
`adk api_server --allow_origins="*"`.
"""
import os

import uvicorn
from fastapi import HTTPException
from google.adk.cli.fast_api import get_fast_api_app

from recifit_agent.favorites_store import get_cached_result, save_cached_result

AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

app = get_fast_api_app(
    agents_dir=AGENTS_DIR,
    web=False,
    allow_origins=["*"],
)


@app.get("/favorites/{cache_key}")
async def get_favorite(cache_key: str):
    result = get_cached_result(cache_key)
    if result is None:
        raise HTTPException(status_code=404, detail="Not cached")
    return result


@app.post("/favorites/{cache_key}")
async def put_favorite(cache_key: str, payload: dict):
    save_cached_result(cache_key, payload)
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
