import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.assets import router as assets_router
from app.api.communications import router as communications_router
from app.api.excel import router as excel_router
from app.api.graph import router as graph_router
from app.api.scans import router as scans_router
from app.database.database import SessionLocal
from app.database.models import create_tables
from app.scanning.local_scanner import ensure_local_scanner
from app.scanning.worker import local_worker
from app.api.findings import router as findings_router
from app.api.asset_services import router as asset_services_router
from app.api.backups import router as backups_router
from app.api.networks import router as networks_router

# CORS_ORIGINS=http://localhost:5173,http://192.168.1.50:5173
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    db = SessionLocal()
    try:
        ensure_local_scanner(db)   # registra el escáner local y sincroniza redes del config
    finally:
        db.close()
    local_worker.start()           # enciende el trabajador interno (modo integrado)
    try:
        yield
    finally:
        local_worker.stop()


app = FastAPI(
    title="OT Asset Mapper",
    description="OT asset inventory and communication mapping API",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in CORS_ORIGINS if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app.include_router(assets_router)
app.include_router(communications_router)
app.include_router(graph_router)
app.include_router(excel_router)
app.include_router(scans_router)
app.include_router(findings_router)
app.include_router(asset_services_router)
app.include_router(backups_router)
app.include_router(networks_router)

@app.get("/")
def root():
    return {"application": "OT Asset Mapper", "version": "2.0.0", "status": "running"}