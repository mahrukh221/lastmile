from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.config import settings

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")
# available in every template, so the prototype banner shows on every page
templates.env.globals["label"] = settings.prototype_label