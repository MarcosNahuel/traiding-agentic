"""
Utilidades compartidas para la integración con Binance.
"""

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
    Redondea la cantidad al precision requerido por Binance (filtro LOT_SIZE).
    Evita errores 400 Bad Request por cantidad inválida.
    """
    decimals, min_qty = _SYMBOL_PRECISION.get(symbol, _DEFAULT_PRECISION)
    return max(round(qty, decimals), min_qty)
