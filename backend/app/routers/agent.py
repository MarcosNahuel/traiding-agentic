from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class AgentQuery(BaseModel):
    query: str


@router.post("/agent/query")
async def agent_query(body: AgentQuery, request: Request) -> dict:
    agent = getattr(request.app.state, "agent", None)
    if agent is not None:
        try:
            ans = agent.answer(body.query)
            return {"answer": ans}
        except Exception as e:
            return {"answer": f"Error al consultar Gemini: {e}"}
    # Fallback simple si no hay LLM configurado
    if body.query.lower().startswith("limites"):
        return {"answer": request.app.state.risk.get_limits()}
    if body.query.lower().startswith("estado"):
        return {"answer": request.app.state.strategy.get_signal_snapshot()}
    return {"answer": "Agente no configurado (falta GOOGLE_API_KEY)."}
