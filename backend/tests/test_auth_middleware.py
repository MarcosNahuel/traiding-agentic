"""Tests for AuthMiddleware.

Regression (2026-06-03): el middleware hacía ``raise HTTPException(401)``, pero
una HTTPException dentro de un BaseHTTPMiddleware NO la capturan los handlers de
FastAPI → Starlette devolvía 500 plano. Toda llamada sin token (o token malo) a
endpoints protegidos (/portfolio, /quant/*, /backtest/*) respondía 500 en vez de
401, simulando que el backend estaba caído. El fix devuelve JSONResponse(401).
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware import AuthMiddleware
from app.config import settings


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(AuthMiddleware)

    @app.get("/health")  # open path
    async def health():
        return {"status": "ok"}

    @app.get("/quant/status")  # protected
    async def protected():
        return {"data": "secret"}

    return app


@pytest.fixture
def client(monkeypatch):
    # TestClient sin context manager => no corre lifespan (ni loop ni sync Binance)
    monkeypatch.setattr(settings, "backend_secret", "s3cret")
    return TestClient(_make_app(), raise_server_exceptions=True)


def test_no_token_returns_401_not_500(client):
    """El bug: devolvía 500. Debe ser 401."""
    resp = client.get("/quant/status")
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Unauthorized"}


def test_wrong_token_returns_401(client):
    resp = client.get("/quant/status", headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401


def test_malformed_header_returns_401(client):
    resp = client.get("/quant/status", headers={"Authorization": "s3cret"})  # sin "Bearer "
    assert resp.status_code == 401


def test_correct_token_passes(client):
    resp = client.get("/quant/status", headers={"Authorization": "Bearer s3cret"})
    assert resp.status_code == 200
    assert resp.json() == {"data": "secret"}


def test_open_path_bypasses_auth(client):
    resp = client.get("/health")  # sin token
    assert resp.status_code == 200


def test_no_secret_configured_skips_auth(monkeypatch):
    """Si BACKEND_SECRET no está seteado, el middleware deja pasar todo."""
    monkeypatch.setattr(settings, "backend_secret", "")
    client = TestClient(_make_app(), raise_server_exceptions=True)
    resp = client.get("/quant/status")  # sin token, pero sin secret => pasa
    assert resp.status_code == 200
