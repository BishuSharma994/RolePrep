from backend.utils.env_loader import load_environment

# MUST be first
load_environment()

from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.audio import router as audio_router
from backend.api.payments import router as payments_router
from backend.api.sessions import router as sessions_router
from backend.routes.payment_webhook import router as payment_router
from backend.services.db import init_db

ALLOWED_ORIGINS = [
    "https://www.roleprep.in",
    "https://roleprep.in",
    "http://localhost:5173",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


app.include_router(audio_router, prefix="/api")
app.include_router(payments_router, prefix="/api")
app.include_router(sessions_router, prefix="/api")
app.include_router(payment_router)


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
