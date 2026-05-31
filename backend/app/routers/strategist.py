"""Endpoints de aprobación del strategist — se abren tocando los botones de Telegram.

GET (no POST) para que el link del botón funcione directo desde el browser.
Auth por query token (STRATEGIST_APPROVAL_TOKEN), no por Bearer — por eso las rutas
están en OPEN_PATHS del AuthMiddleware.
"""
import hmac

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from ..config import settings
from ..db import get_supabase
from ..services.strategist.approval import promote_latest_pending, reject_latest_pending

router = APIRouter()


def _check_token(token: str) -> None:
    expected = settings.strategist_approval_token
    if not expected or not hmac.compare_digest(token or "", expected):
        raise HTTPException(status_code=401, detail="token inválido")


def _page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"<html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{title}</title></head><body style='font-family:system-ui;max-width:520px;margin:40px auto;"
        f"text-align:center'><h2>{title}</h2><p>{body}</p></body></html>"
    )


@router.get("/strategist/approve", response_class=HTMLResponse)
async def approve(token: str = "") -> HTMLResponse:
    _check_token(token)
    cfg = promote_latest_pending(get_supabase())
    if not cfg:
        return _page("Sin propuesta pendiente", "No hay ninguna config esperando aprobación.")
    return _page(
        "✅ Config aprobada",
        f"La propuesta del strategist quedó <b>active</b>. El bot la adopta en el próximo tick.<br><br>"
        f"<code>{cfg.get('reasoning', '')[:200]}</code>",
    )


@router.get("/strategist/reject", response_class=HTMLResponse)
async def reject(token: str = "") -> HTMLResponse:
    _check_token(token)
    cfg = reject_latest_pending(get_supabase())
    if not cfg:
        return _page("Sin propuesta pendiente", "No hay ninguna config esperando aprobación.")
    return _page("❌ Propuesta rechazada", "La config quedó descartada. El bot sigue con la activa actual.")
