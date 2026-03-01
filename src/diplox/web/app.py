"""FastAPI application — registration API, admin API, landing page."""

import logging
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from diplox.config import Settings
from diplox.services.database import Database

logger = logging.getLogger(__name__)


class NoCacheStaticMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        if request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response


# --- Request/Response models ---

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    invite_code: str


class RegisterResponse(BaseModel):
    success: bool
    deep_link: str


class GenerateInvitesRequest(BaseModel):
    count: int = 10
    prefix: str = "alpha"


class ProvisionProUserRequest(BaseModel):
    name: str
    email: EmailStr


def create_app(settings: Settings, db: Database) -> FastAPI:
    app = FastAPI(title="Diplox Alpha", docs_url=None, redoc_url=None)
    app.add_middleware(NoCacheStaticMiddleware)

    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(exist_ok=True)

    # --- Admin auth dependency ---
    async def require_admin(x_admin_key: str = Header()):
        if not settings.admin_api_key or x_admin_key != settings.admin_api_key:
            raise HTTPException(status_code=403, detail="Invalid admin key")

    # --- Public endpoints ---

    @app.get("/")
    async def landing():
        index = static_dir / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return JSONResponse({"message": "Diplox Alpha"})

    @app.get("/api/health")
    async def health():
        stats = await db.get_usage_stats()
        return {"status": "ok", "version": "alpha", **stats}

    @app.post("/api/register", response_model=RegisterResponse)
    async def register(req: RegisterRequest):
        # Validate invite
        valid = await db.validate_invite(req.invite_code)
        if not valid:
            raise HTTPException(status_code=400, detail="Недействительный инвайт-код")

        # Check email uniqueness
        existing = await db.get_user_by_email(req.email)
        if existing:
            raise HTTPException(status_code=400, detail="Email уже зарегистрирован")

        # Create user first, then set up vault using the generated user_id
        user = await db.create_user(
            name=req.name,
            email=req.email,
            vault_path="",  # Updated below
        )

        vault_path = settings.vaults_dir / user.id
        vault_path.mkdir(parents=True, exist_ok=True)
        (vault_path / "daily").mkdir(exist_ok=True)
        (vault_path / "attachments").mkdir(exist_ok=True)
        (vault_path / "docs").mkdir(exist_ok=True)
        (vault_path / ".sessions").mkdir(exist_ok=True)

        await db.update_vault_path(user.id, str(vault_path))

        # Mark invite as used
        await db.use_invite(req.invite_code, user.id)

        deep_link = f"{settings.bot_url}?start={user.onboarding_token}"

        logger.info("User registered: %s (%s)", req.name, req.email)
        return RegisterResponse(success=True, deep_link=deep_link)

    # --- Admin endpoints ---

    @app.post("/api/admin/invites", dependencies=[Depends(require_admin)])
    async def generate_invites(req: GenerateInvitesRequest):
        codes = await db.generate_invites(req.count, req.prefix)
        return {"codes": codes}

    @app.get("/api/admin/users", dependencies=[Depends(require_admin)])
    async def list_users():
        users = await db.list_users()
        return {
            "users": [
                {
                    "id": u.id,
                    "name": u.name,
                    "email": u.email,
                    "telegram_id": u.telegram_id,
                    "is_active": u.is_active,
                    "daily_quota": u.daily_quota,
                    "created_at": u.created_at,
                }
                for u in users
            ]
        }

    @app.post("/api/provision-pro-user", dependencies=[Depends(require_admin)])
    async def provision_pro_user(req: ProvisionProUserRequest):
        """Auto-provision bot access for Pro subscribers (called by web app)."""
        # Idempotent: if email exists, return existing deep link
        existing = await db.get_user_by_email(req.email)
        if existing:
            if existing.onboarding_token:
                deep_link = f"{settings.bot_url}?start={existing.onboarding_token}"
            else:
                deep_link = settings.bot_url
            return {"success": True, "deep_link": deep_link, "existing": True}

        # Create user without invite code
        user = await db.create_user(
            name=req.name,
            email=req.email,
            vault_path="",
        )

        vault_path = settings.vaults_dir / user.id
        vault_path.mkdir(parents=True, exist_ok=True)
        (vault_path / "daily").mkdir(exist_ok=True)
        (vault_path / "attachments").mkdir(exist_ok=True)
        (vault_path / "docs").mkdir(exist_ok=True)
        (vault_path / ".sessions").mkdir(exist_ok=True)

        await db.update_vault_path(user.id, str(vault_path))

        deep_link = f"{settings.bot_url}?start={user.onboarding_token}"
        logger.info("Pro user provisioned: %s (%s)", req.name, req.email)
        return {"success": True, "deep_link": deep_link, "existing": False}

    @app.get("/api/admin/usage", dependencies=[Depends(require_admin)])
    async def usage_stats():
        return await db.get_usage_stats()

    # Mount static files last (to not override API routes)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    return app
