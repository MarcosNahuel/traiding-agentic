# Estrategias de Arbitraje y Statistical Arbitrage

## Estrategias cubiertas (SSRN 3247865)

- `6.2 Cash-and-carry arbitrage`
- `6.4 Intraday arbitrage between index ETFs` (adaptable a venues crypto)
- `8.5 FX triangular arbitrage` (adaptable a triangulos crypto/stablecoin)
- `3.8 Pairs trading` y `3.18 Statistical arbitrage optimization`
- `10.2 Calendar spread` (derivados)

## Validacion externa (resumen)

- Existe evidencia de arbitraje cross-exchange en crypto, pero con barreras operativas reales.
- La rentabilidad neta depende de fricciones: fees, latencia, transferencias, funding, riesgo de contraparte.
- StatArb funciona si el pipeline de datos y ejecucion es robusto, no solo por modelo.

Ver fuentes:

- `fuentes-validadas-2026-02-19.md` (Cross-Exchange Arbitrage, Pairs y StatArb)

## Cuando aplicar

### Scalping

- Arbitraje inter-venue solo con infraestructura dedicada y latencia baja.

### Intraday

- Calendar/funding spreads y pairs en ventanas de horas.

### Swing

- Basis cash-and-carry con control de funding y riesgo de cola.

## Spot vs Futures

- Spot: triangulos y cross-exchange spot arbitrage.
- Futures: basis/carry, calendar spreads, hedges delta-neutrales.

## Reglas operativas recomendadas

1. Modelar costos completos antes de abrir.
2. Usar solo mercados con profundidad y APIs estables.
3. Definir kill-switch por error de ejecucion parcial.
4. Controlar riesgo operacional (retiros, limites, mantenimiento).

## Snippet Python (scanner de basis neto)

```python
def net_basis_annualized(spot_price, perp_price, funding_8h, taker_fee, borrow_cost_daily):
    basis = (perp_price / spot_price) - 1.0
    funding_annual = funding_8h * 3 * 365
    carry_cost_annual = (borrow_cost_daily * 365) + (2 * taker_fee)
    return basis + funding_annual - carry_cost_annual

def should_trade_cash_and_carry(net_basis_ann, min_edge=0.08):
    return net_basis_ann > min_edge
```

## Riesgos tipicos

- "Arbitraje fantasma": spread visible pero no ejecutable.
- Riesgo de cola en movimientos violentos.
- Riesgo de exchange/contraparte.

## Recomendacion para este repo

- Prioridad media-alta: implementar monitor de basis/funding en Demo Futures.
- Prioridad media: pairs trading cointegrado en backtester.
- Prioridad baja inicial: arbitraje cross-exchange real (complejidad operativa alta).
