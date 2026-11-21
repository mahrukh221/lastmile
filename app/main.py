from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.mock_services.routes import router as mock_router

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title=f"{settings.app_name} (Prototype)",
    description="Helps people use public services safely. All data is mock.",
    version="0.1.0",
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
app.include_router(mock_router)


@app.get("/health")
def health():
    return {"status": "ok", "prototype": True}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        request,
        "home.html",
        {"title": "Home", "label": settings.prototype_label},
    )