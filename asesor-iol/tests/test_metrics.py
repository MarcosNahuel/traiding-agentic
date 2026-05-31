from asesor_iol.analytics.metrics import compute_metrics
from asesor_iol.iol.models import AccountState, Holding, Portfolio


def test_metrics_allocation_and_cash():
    p = Portfolio(
        pais="argentina",
        holdings=[
            Holding(simbolo="SPY", cantidad=10, ultimo_precio=100, valorizado=1000),
            Holding(simbolo="AAPL", cantidad=5, ultimo_precio=200, valorizado=1000),
        ],
    )
    accounts = [AccountState(moneda="dolar", disponible=500, comprometido=0, titulos_valorizados=2000, total=2500)]

    m = compute_metrics(p, accounts)

    assert m.total_valorizado == 2500
    assert m.cash_total == 500
    assert m.cash_pct == 20.0
    assert m.allocation_pct == {"SPY": 50.0, "AAPL": 50.0}
    assert m.top_concentration_pct == 50.0


def test_metrics_empty_portfolio():
    m = compute_metrics(Portfolio(pais="argentina", holdings=[]), [])
    assert m.total_valorizado == 0.0
    assert m.allocation_pct == {}
    assert m.top_symbol is None
