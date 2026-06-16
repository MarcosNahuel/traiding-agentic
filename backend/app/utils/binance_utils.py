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

# Filtro NOTIONAL de Binance: minNotional en USDT. Una orden por debajo se rechaza
# con 400 Bad Request. Se usa para detectar "dust" (residuos sub-mínimos) y evitar
# que el fast-loop regenere una venta imposible cada tick.
_MIN_NOTIONAL = {
    "BTCUSDT": 5.0,
    "ETHUSDT": 5.0,
    "SOLUSDT": 5.0,
    "BNBUSDT": 5.0,
    "XRPUSDT": 5.0,
}
_DEFAULT_MIN_NOTIONAL = 5.0


def meets_min_notional(symbol: str, qty: float, price: float) -> bool:
    """True si qty*price alcanza el minNotional de Binance (orden ejecutable)."""
    return qty * price >= _MIN_NOTIONAL.get(symbol, _DEFAULT_MIN_NOTIONAL)


def is_dust(symbol: str, qty: float, price: float) -> bool:
    """True si la cantidad es 'dust': por debajo del minNotional (orden NO ejecutable)."""
    return not meets_min_notional(symbol, qty, price)


def round_quantity(symbol: str, qty: float) -> float:
    """
    Trunca (floor) la cantidad al step size requerido por Binance (filtro LOT_SIZE).
    Usa floor para nunca exceder la tenencia disponible.
    Evita errores 400 Bad Request por cantidad inválida.
    """
    decimals, step = _SYMBOL_PRECISION.get(symbol, _DEFAULT_PRECISION)
    floored = _floor(qty / step) * step
    return round(floored, decimals)
