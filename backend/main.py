from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from backend.bot.telegram_bot import shutdown, startup
from backend.routes.payment_webhook import router as payment_router
from backend.routes.telegram_webhook import router as telegram_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup()
    try:
        yield
    finally:
        await shutdown()


app = FastAPI(lifespan=lifespan)
app.include_router(telegram_router)
app.include_router(payment_router)


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
