"""
Utilidades compartidas para la integración con Binance.
"""

from math import floor as _floor

# Precisión de cantidad por símbolo (basada en filtros LOT_SIZE del testnet)
_SYMBOL_PRECISION = {
    "BTCUSDT": (5, 0.00001),
    "ETHUSDT": (4, 0.0001),
    "SOLUSDT": (4, 0.0001),
    "BNBUSDT": (3, 0.001),
    "XRPUSDT": (2, 0.01),
}
_DEFAULT_PRECISION = (2, 0.01)


def round_quantity(symbol: str, qty: float) -> float:
    """
    Trunca (floor) la cantidad al step size requerido por Binance (filtro LOT_SIZE).
    Usa floor para nunca exceder la tenencia disponible.
    Evita errores 400 Bad Request por cantidad inválida.
    """
    decimals, step = _SYMBOL_PRECISION.get(symbol, _DEFAULT_PRECISION)
    floored = _floor(qty / step) * step
    return round(floored, decimals)
