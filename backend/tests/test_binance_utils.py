"""Tests para round_quantity — verifica que nunca redondea hacia arriba."""

from app.utils.binance_utils import round_quantity


def test_round_quantity_floor_btcusdt():
    """BTCUSDT: step=0.00001 — debe truncar, no redondear."""
    qty = round_quantity("BTCUSDT", 0.000019)
    assert qty == 0.00001  # floor, no round (0.000019 redondeado arriba sería 0.00002)


def test_round_quantity_floor_xrpusdt():
    """XRPUSDT: step=0.01 — 99.999 debe quedar en 99.99, no 100.00."""
    qty = round_quantity("XRPUSDT", 99.999)
    assert qty == 99.99


def test_round_quantity_exact_multiple():
    """Cantidad exacta no debe cambiar."""
    qty = round_quantity("BTCUSDT", 0.00100)
    assert qty == 0.001


def test_round_quantity_default_symbol():
    """Símbolo desconocido usa precision por defecto (step=0.01)."""
    qty = round_quantity("UNKNOWNUSDT", 1.555)
    assert qty == 1.55  # floor, no round


def test_round_quantity_never_exceeds_input():
    """El resultado nunca debe ser mayor que el input."""
    for qty in [0.000019, 0.001234, 99.999, 10.005, 0.12349]:
        symbol = "BTCUSDT"
        result = round_quantity(symbol, qty)
        assert result <= qty, f"round_quantity({symbol}, {qty}) = {result} > {qty}"
