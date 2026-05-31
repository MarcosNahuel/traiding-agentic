"""Tests for the balance-mismatch detection in reconciliation.

Bug (2026-05-31): the check was bidirectional (abs diff), so a testnet/pre-funded
account holding MORE than the bot tracked produced perpetual false-positive
divergences. Only a SHORTFALL (DB claims more than the exchange holds) is a real risk.
"""

from app.services.reconciliation import _balance_shortfall_divergence


def test_extra_balance_on_exchange_is_not_flagged():
    # Testnet: exchange holds ~1 BTC but the bot only tracked 0.0008 → benign extra, no alert.
    assert _balance_shortfall_divergence("BTC", db_qty=0.00081, exchange_qty=1.00099) is None


def test_missing_assets_is_flagged():
    # The bot's DB claims 1.0 ETH but the exchange only has 0.1 → real problem (missing assets).
    d = _balance_shortfall_divergence("ETH", db_qty=1.0, exchange_qty=0.1)
    assert d is not None
    assert d["type"] == "balance_mismatch"
    assert d["symbol"] == "ETHUSDT"
    assert "ETH" in d["detail"]


def test_within_tolerance_not_flagged():
    # 3% shortfall is within the 5% tolerance → no alert.
    assert _balance_shortfall_divergence("ETH", db_qty=1.0, exchange_qty=0.97) is None


def test_exact_match_not_flagged():
    assert _balance_shortfall_divergence("BTC", db_qty=0.5, exchange_qty=0.5) is None
