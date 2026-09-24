import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.assets import router as assets_router
from app.api.communications import router as communications_router
from app.api.excel import router as excel_router
from app.api.graph import router as graph_router
from app.database.models import create_tables

# Orígenes permitidos separados por coma, p. ej.:
# CORS_ORIGINS=http://localhost:5173,http://192.168.1.50:5173
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield


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


@app.get("/")
def root():
    return {"application": "OT Asset Mapper", "version": "2.0.0", "status": "running"}