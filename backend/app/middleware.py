"""Custom ASGI middleware for the trading backend."""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .config import settings


class AuthMiddleware(BaseHTTPMiddleware):
    """Validate Bearer token on all endpoints except the open paths.

    NOTA (fix 2026-06-03): un ``raise HTTPException`` dentro de un
    ``BaseHTTPMiddleware`` NO lo capturan los exception handlers de FastAPI
    (solo aplican en la cadena de routing/dependencias). Starlette lo trata
    como excepción no manejada y devuelve un **500 plano** en vez del 401.
    Eso enmascaraba toda llamada sin token como "Internal Server Error" y
    rompía la observabilidad. Devolvemos un ``JSONResponse(401)`` explícito.
    """

    # /strategist/* se autentican por query token (link de Telegram), no por Bearer.
    # /telegram/webhook se valida por secret-token header, no Bearer.
    OPEN_PATHS = {
        "/health", "/docs", "/openapi.json", "/redoc",
        "/strategist/approve", "/strategist/reject",
        "/telegram/webhook",
    }

    async def dispatch(self, request: Request, call_next):
        if not settings.backend_secret:
            return await call_next(request)  # No secret configured, skip auth

        if request.url.path in self.OPEN_PATHS:
            return await call_next(request)

        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer ") or auth[7:] != settings.backend_secret:
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

        return await call_next(request)
