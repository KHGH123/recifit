"""Custom server entrypoint — everything `adk api_server` provides, plus a
small /favorites API backed by Firestore (favorites_store.py) that the ADK
CLI has no way to add. Run with `python server.py` instead of
`adk api_server --allow_origins="*"`.
"""
import os

AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))

# `adk api_server` loads recifit_agent/.env before importing the agent
# package, so GOOGLE_CLOUD_PROJECT etc. are already set by the time
# discovery_engine_client.py reads them at import time. Importing
# recifit_agent.favorites_store below pulls in the whole recifit_agent
# package (its __init__.py does `from . import agent`) the same way — so
# .env has to be loaded here first, before that import, or
# discovery_engine_client.py picks up PROJECT_ID=None and every Discovery
# Engine call fails with a 403.
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(AGENTS_DIR, "recifit_agent", ".env"))

import uvicorn  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from google.adk.cli.fast_api import get_fast_api_app  # noqa: E402

from recifit_agent.favorites_store import (  # noqa: E402
    delete_favorite_recipe,
    get_cached_result,
    list_favorite_recipes,
    save_cached_result,
    save_favorite_recipe,
)

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


@app.get("/favorite-recipes")
async def get_favorite_recipes(device_id: str):
    return {"favorites": list_favorite_recipes(device_id)}


@app.post("/favorite-recipes")
async def create_favorite_recipe(payload: dict):
    device_id = payload.get("device_id")
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required")
    favorite = {k: v for k, v in payload.items() if k != "device_id"}
    favorite_id = save_favorite_recipe(device_id, favorite)
    return {"id": favorite_id}


@app.delete("/favorite-recipes/{favorite_id}")
async def remove_favorite_recipe(favorite_id: str, device_id: str):
    if not delete_favorite_recipe(device_id, favorite_id):
        raise HTTPException(status_code=404, detail="Not found")
    return {"status": "ok"}


# web/index.html을 같은 서비스에서 같이 서빙한다 — 로컬 개발 때는 이걸
# 따로 python -m http.server로 띄우지만, 배포 환경에서는 백엔드/프론트를
# 별도 서비스로 안 나누는 게 CORS 걱정도 없고 더 간단하다. 반드시 API
# 라우트들을 다 등록한 "다음"에 mount해야 한다 — "/"에 마운트된 정적
# 파일 서버가 더 구체적인 경로들을 가리지 않게 하기 위함이다.
app.mount("/", StaticFiles(directory=os.path.join(AGENTS_DIR, "web"), html=True), name="web")


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
