# Derivados, Carry y Basis

## Estrategias cubiertas (SSRN 3247865)

- `6.2 Cash-and-carry arbitrage`
- `10.2 Calendar spread`
- `10.4 Trend following (momentum) en futures`
- `8.2 Carry trade` y `8.4 Momentum & carry combo` (adaptacion conceptual)

## Validacion externa (resumen)

- El funding rate y la base spot-perpetuo son drivers centrales en futures crypto.
- Hay evidencia reciente de estrategias que explotan estructura de funding/carry.
- La rentabilidad depende de ejecucion neta de costos, no solo del spread observado.

Ver fuentes:

- `fuentes-validadas-2026-02-19.md` (Funding, Perpetual Futures, Carry)

## Cuando aplicar

### Scalping

- Menos recomendado para carry puro.

### Intraday

- Bueno para oportunidades de basis transitorio y rebalance de cobertura.

### Swing

- Principal horizonte para cash-and-carry/funding carry.

## Spot vs Futures

- Spot: pierna de cobertura para cash-and-carry.
- Futures: principal instrumento para capturar basis/funding.

## Reglas operativas recomendadas

1. Abrir solo si edge neto anualizado supera umbral objetivo.
2. Monitorear funding real cobrado/pagado por ciclo.
3. Controlar riesgo de desconexion entre spot y perp.
4. Definir plan de unwind ante stress de mercado.

## Snippet Python (edge neto funding+basis)

```python
def basis_pct(spot, perp):
    return (perp / spot) - 1.0

def annualized_funding(funding_rate_8h):
    return funding_rate_8h * 3 * 365

def net_edge(spot, perp, funding_rate_8h, taker_fee, borrow_daily):
    b = basis_pct(spot, perp)
    f = annualized_funding(funding_rate_8h)
    costs = (2 * taker_fee) + (borrow_daily * 365)
    return b + f - costs
```

## Riesgos tipicos

- Funding cambia de signo y destruye edge esperado.
- Riesgo de ejecucion parcial en una de las piernas.
- Riesgo de margen/liquidacion por movimientos extremos.

## Recomendacion para este repo

- Prioridad media-alta: modulo de monitoreo funding/basis en Demo Futures.
- Prioridad media: calendar spread simulator para validar execution risk.
