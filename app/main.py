from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.mock_services.routes import router as mock_router
from app.routers import admin, api_keys, audit, auth, cases, consents, demo, pages, public_api
from app.templating import BASE_DIR, templates

app = FastAPI(
    title=f"{settings.app_name} (Prototype)",
    description="Helps people use public services safely. All data is mock.",
    version="0.1.0",
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(mock_router)
app.include_router(auth.router)
app.include_router(pages.router)
app.include_router(demo.router)
app.include_router(api_keys.router)
app.include_router(admin.router)
app.include_router(public_api.router)
app.include_router(consents.router)
app.include_router(audit.router)
app.include_router(cases.router)


@app.get("/health")
def health():
    return {"status": "ok", "prototype": True}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "home.html", {"title": "Home"})