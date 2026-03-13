"""Unit tests for executor.py SL/TP ATR-based calculation."""

import pytest
from unittest.mock import patch, MagicMock


def _indicators(atr=500.0):
    m = MagicMock()
    m.atr_14 = atr
    return m


def test_sl_tp_uses_atr():
    """SL/TP should use ATR when available."""
    with patch("app.services.executor.compute_indicators", return_value=_indicators(500.0)), \
         patch("app.services.executor.settings") as mock_settings:
        mock_settings.quant_primary_interval = "1h"
        mock_settings.sl_atr_multiplier = 1.5
        mock_settings.tp_atr_multiplier = 3.0
        mock_settings.sl_fallback_pct = 0.03
        mock_settings.tp_fallback_pct = 0.06

        from app.services.executor import _compute_sl_tp
        sl, tp = _compute_sl_tp("BTCUSDT", 50000.0)

    # SL = 50000 - 1.5 * 500 = 49250
    assert sl == 49250.0
    # TP = 50000 + 3.0 * 500 = 51500
    assert tp == 51500.0


def test_sl_tp_fallback_no_atr():
    """SL/TP should fallback to percentage when ATR is None."""
    indicators = MagicMock()
    indicators.atr_14 = None
    with patch("app.services.executor.compute_indicators", return_value=indicators), \
         patch("app.services.executor.settings") as mock_settings:
        mock_settings.quant_primary_interval = "1h"
        mock_settings.sl_atr_multiplier = 1.5
        mock_settings.tp_atr_multiplier = 3.0
        mock_settings.sl_fallback_pct = 0.03
        mock_settings.tp_fallback_pct = 0.06

        from app.services.executor import _compute_sl_tp
        sl, tp = _compute_sl_tp("BTCUSDT", 50000.0)

    # SL = 50000 * 0.97 = 48500
    assert sl == 48500.0
    # TP = 50000 * 1.06 = 53000
    assert tp == 53000.0


def test_sl_tp_ratio_1_to_2():
    """Risk:reward ratio should be approximately 1:2."""
    with patch("app.services.executor.compute_indicators", return_value=_indicators(1000.0)), \
         patch("app.services.executor.settings") as mock_settings:
        mock_settings.quant_primary_interval = "1h"
        mock_settings.sl_atr_multiplier = 1.5
        mock_settings.tp_atr_multiplier = 3.0
        mock_settings.sl_fallback_pct = 0.03
        mock_settings.tp_fallback_pct = 0.06

        from app.services.executor import _compute_sl_tp
        sl, tp = _compute_sl_tp("BTCUSDT", 60000.0)

    risk = 60000.0 - sl   # 1500
    reward = tp - 60000.0  # 3000
    ratio = reward / risk
    assert abs(ratio - 2.0) < 0.01


def test_sl_tp_atr_aberrante_fallback():
    """ATR > 25% del precio debe caer al fallback."""
    # ATR = 20000, price = 50000 → ratio = 0.4 > 0.25 → fallback
    with patch("app.services.executor.compute_indicators", return_value=_indicators(atr=20000.0)), \
         patch("app.services.executor.settings") as mock_settings:
        mock_settings.quant_primary_interval = "1h"
        mock_settings.sl_atr_multiplier = 1.5
        mock_settings.tp_atr_multiplier = 3.0
        mock_settings.sl_fallback_pct = 0.03
        mock_settings.tp_fallback_pct = 0.06

        from app.services.executor import _compute_sl_tp
        sl, tp = _compute_sl_tp("BTCUSDT", 50000.0)

    # Debe usar fallback, no ATR aberrante
    assert sl == 48500.0
    assert tp == 53000.0


def test_sl_tp_sanity_check_sl_must_be_below_price():
    """SL generado por ATR que resulta <= 0 debe caer al fallback."""
    # ATR = 40000, price = 30000 → SL = 30000 - 1.5*40000 = -30000 (inválido)
    with patch("app.services.executor.compute_indicators", return_value=_indicators(atr=40000.0)), \
         patch("app.services.executor.settings") as mock_settings:
        mock_settings.quant_primary_interval = "1h"
        mock_settings.sl_atr_multiplier = 1.5
        mock_settings.tp_atr_multiplier = 3.0
        mock_settings.sl_fallback_pct = 0.03
        mock_settings.tp_fallback_pct = 0.06

        from app.services.executor import _compute_sl_tp
        sl, tp = _compute_sl_tp("BTCUSDT", 30000.0)

    assert sl > 0
    assert sl < 30000.0


def test_sl_tp_fallback_on_exception():
    """SL/TP should fallback to percentage when compute_indicators raises."""
    with patch("app.services.executor.compute_indicators", side_effect=Exception("no data")), \
         patch("app.services.executor.settings") as mock_settings:
        mock_settings.quant_primary_interval = "1h"
        mock_settings.sl_atr_multiplier = 1.5
        mock_settings.tp_atr_multiplier = 3.0
        mock_settings.sl_fallback_pct = 0.03
        mock_settings.tp_fallback_pct = 0.06

        from app.services.executor import _compute_sl_tp
        sl, tp = _compute_sl_tp("BTCUSDT", 50000.0)

    assert sl == 48500.0
    assert tp == 53000.0
