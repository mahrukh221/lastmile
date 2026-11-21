from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app import audit
from app.config import settings
from app.db import get_db
from app.deps import get_optional_user
from app.models import User
from app.routers.auth import authenticate
from app.security import create_access_token
from app.templating import templates

router = APIRouter(include_in_schema=False)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"title": "Log in", "error": None})


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = authenticate(db, email, password)
    if user is None:
        audit.record(db, "auth.login_failed", actor_role=audit.ACTOR_ANONYMOUS,
                     details={"email": email.lower().strip(), "via": "web"}, commit=True)
        return templates.TemplateResponse(
            request,
            "login.html",
            {"title": "Log in", "error": "Wrong email or password"},
            status_code=401,
        )
    audit.record(db, "auth.login", actor=user, details={"via": "web"}, commit=True)
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie(
        "access_token",
        create_access_token(user.id, user.role),
        httponly=True,   # JavaScript cannot read it
        samesite="lax",  # not sent on cross-site form posts
        max_age=settings.access_token_minutes * 60,
    )
    return response


@router.get("/logout")
def logout(user: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    if user is not None:
        audit.record(db, "auth.logout", actor=user, commit=True)
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("access_token")
    return response


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, user: User | None = Depends(get_optional_user)):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(
        request, "dashboard.html", {"title": "Dashboard", "user": user}
    )