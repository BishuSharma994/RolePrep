from fastapi import FastAPI
from backend.routes.telegram_webhook import router

app = FastAPI()

app.include_router(router)


@app.get("/")
def root():
    return {"status": "RolePrep API running"}