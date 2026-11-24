from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router

load_dotenv()

app = FastAPI()
app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).resolve().parent / "app" / "static"),
    name="static",
)
app.include_router(api_router)