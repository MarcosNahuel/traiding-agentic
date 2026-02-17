from fastapi import APIRouter, HTTPException
from ..models import ExecuteRequest
from ..services.executor import execute_proposal, execute_all_approved
from ..db import get_supabase

router = APIRouter(prefix="/execute")


@router.post("")
async def execute(req: ExecuteRequest):
    if req.execute_all:
        result = await execute_all_approved()
        return {
            "success": True,
            "message": f"Executed {result['executed']}/{result['total']} proposals",
            "summary": result,
        }
    elif req.proposal_id:
        result = await execute_proposal(req.proposal_id)
        if not result["success"]:
            raise HTTPException(400, result.get("error", "Execution failed"))
        return {
            "success": True,
            "message": "Trade executed successfully",
            "execution": result,
        }
    else:
        raise HTTPException(400, "Provide proposalId or executeAll=true")
