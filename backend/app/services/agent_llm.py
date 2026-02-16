import os
from typing import Optional, Dict, Any
import google.generativeai as genai

class GeminiAgent:
    def __init__(self, *, api_key: Optional[str], model_name: str,
                 risk_manager, strategy_engine) -> None:
        if not api_key:
            raise ValueError("GOOGLE_API_KEY no configurada")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        self.risk = risk_manager
        self.strategy = strategy_engine

    def build_system_context(self) -> str:
        limits = self.risk.get_limits() if self.risk else {}
        snapshot = self.strategy.get_signal_snapshot() if self.strategy else {}
        return (
            "Eres un agente de trading con acceso de solo lectura a límites de riesgo y estado de estrategia. "
            "Responde de forma concisa y clara. Si no sabes algo, dilo explícitamente.\n"
            f"Riesgo actual: {limits}\n"
            f"Estado estrategia: {snapshot}\n"
        )

    def answer(self, query: str, extra_context: Optional[Dict[str, Any]] = None) -> str:
        system_ctx = self.build_system_context()
        user_prompt = query
        if extra_context:
            user_prompt += "\nContexto adicional: " + str(extra_context)
        resp = self.model.generate_content([
            {"role": "system", "parts": [system_ctx]},
            {"role": "user", "parts": [user_prompt]},
        ])
        return resp.text if hasattr(resp, 'text') else str(resp)
