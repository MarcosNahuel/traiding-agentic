from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/status")
async def status(request: Request) -> dict:
    return {
        "env": request.app.state.settings.app_env,
        "limits": request.app.state.risk.get_limits(),
    }
