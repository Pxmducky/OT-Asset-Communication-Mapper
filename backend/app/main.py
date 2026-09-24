from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.assets import router as assets_router
from app.api.communications import router as communications_router


app = FastAPI(
    title="OT Asset Mapper",
    description="OT asset inventory and communication mapping API",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(assets_router)
app.include_router(communications_router)


@app.get("/")
def root():
    return {
        "application": "OT Asset Mapper",
        "version": "1.0.0",
        "status": "running",
    }