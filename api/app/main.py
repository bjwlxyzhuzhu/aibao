"""爱宝园务大脑 · FastAPI 入口。"""
from __future__ import annotations

import threading
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .db import SessionLocal
from .routers import admin, auth, dashboard, inspect, parent_council
from .seed import run_all

app = FastAPI(title="爱宝园务大脑 API", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

for r in (auth.router, inspect.router, dashboard.router, parent_council.router, admin.router):
    app.include_router(r, prefix="/api")


@app.get("/api/health")
def health():
    from .llm.client import llm_enabled
    return {"ok": True, "llm": llm_enabled(), "demo_mode": config.DEMO_MODE}


def _sla_loop():
    from .services.workorders import tick
    while True:
        try:
            with SessionLocal() as db:
                tick(db)
                db.commit()
        except Exception:  # noqa: BLE001
            pass
        time.sleep(60)


@app.on_event("startup")
def startup():
    run_all(with_demo=config.env("SEED_DEMO", "true").lower() == "true")
    threading.Thread(target=_sla_loop, daemon=True).start()


# 生产环境：同一进程托管前端构建产物（Docker 中由 Nginx 托管，此处作兜底）
DIST = config.ROOT_DIR / "web" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        f = DIST / full_path
        if full_path and f.is_file():
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
