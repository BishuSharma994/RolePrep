from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from backend.routes.telegram_webhook import router
from bot.telegram_bot import shutdown, startup


@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup()
    try:
        yield
    finally:
        await shutdown()


app = FastAPI(lifespan=lifespan)
app.include_router(router)


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
