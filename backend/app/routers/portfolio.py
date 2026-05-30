import json
import traceback

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

from ..services.portfolio import get_portfolio_state

router = APIRouter(prefix="/portfolio")


@router.get("")
async def portfolio():
    # Robust: never return an opaque 500. Surface the failing stage + traceback
    # so observability survives. (Diagnostic added 2026-05-30 to find why the
    # endpoint 500s and account_snapshots stopped writing on the server.)
    try:
        data = await get_portfolio_state()
    except Exception:
        return JSONResponse(
            status_code=500,
            content={"_stage": "get_portfolio_state", "_traceback": traceback.format_exc()},
        )
    try:
        content = jsonable_encoder(data)
        json.dumps(content)  # force-validate JSON serialization (the suspected 500)
    except Exception:
        snap_err = data.get("_snapshot_error") if isinstance(data, dict) else None
        keys = list(data.keys()) if isinstance(data, dict) else str(type(data))
        return JSONResponse(
            status_code=500,
            content={
                "_stage": "serialization",
                "_traceback": traceback.format_exc(),
                "_keys": keys,
                "_snapshot_error": snap_err,
            },
        )
    return content
