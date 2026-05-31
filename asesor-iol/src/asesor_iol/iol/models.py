"""Modelos de datos de IOL (subset usado en Fase 1)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Holding:
    simbolo: str
    cantidad: float
    ultimo_precio: float
    valorizado: float
    moneda: str = "peso_Argentino"
    ppc: float | None = None  # precio promedio de compra
    ganancia_porcentaje: float | None = None


@dataclass
class Portfolio:
    pais: str
    holdings: list[Holding] = field(default_factory=list)

    @property
    def total_valorizado(self) -> float:
        return sum(h.valorizado for h in self.holdings)


@dataclass
class AccountState:
    moneda: str
    disponible: float
    comprometido: float
    titulos_valorizados: float
    total: float


@dataclass
class Quote:
    simbolo: str
    mercado: str
    ultimo: float
    compra: float | None
    venta: float | None
    moneda: str | None = None


@dataclass
class OrderRequest:
    mercado: str
    simbolo: str
    cantidad: float
    precio: float
    tipo: str  # "comprar" | "vender"
    plazo: str = "t1"
    validez: str | None = None


@dataclass
class OrderResult:
    ok: bool
    numero_operacion: str | None
    mensaje: str
    raw: dict | None = None
