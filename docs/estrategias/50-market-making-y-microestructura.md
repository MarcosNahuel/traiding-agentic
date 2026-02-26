# Market Making y Microestructura

## Estrategias cubiertas (SSRN 3247865)

- `3.19 Market-making`
- Relacionadas: inventario neutral, microspread y control de adverse selection.

## Validacion externa (resumen)

- El marco Avellaneda-Stoikov sigue siendo referencia para market making cuantitativo.
- La estrategia depende mas de calidad de ejecucion y gestion de inventario que de "prediccion".
- En crypto, riesgo clave: saltos de volatilidad y deterioro instantaneo del spread.

Ver fuentes:

- `fuentes-validadas-2026-02-19.md` (Market Making / Limit Order Book)

## Cuando aplicar

### Scalping

- Principal caso de uso.
- Requiere actualizacion de quotes frecuente y limites de inventario duros.

### Intraday

- Puede combinarse con sesgo direccional suave por regimen.

### Swing

- No recomendado como estrategia principal.

## Spot vs Futures

- Spot: menor complejidad de margen, pero menos herramientas de cobertura.
- Futures: mejor para neutralizar delta, mas riesgo operacional por leverage y liquidaciones.

## Reglas operativas recomendadas

1. Limite de inventario por simbolo y por sesion.
2. Stop de cotizacion en volatilidad extrema.
3. Recalculo de spread segun sigma y profundidad.
4. Monitoreo de fill ratio y adverse selection.

## Snippet Python (quote con sesgo de inventario)

```python
def make_quotes(mid_price, sigma, inventory, gamma=0.1, k=1.5):
    # Spread base proporcional a volatilidad
    half_spread = gamma * sigma

    # Sesgo por inventario: si inventario > 0, bajar bid y ask para descargar
    inv_skew = (gamma / k) * inventory

    bid = mid_price - half_spread - inv_skew
    ask = mid_price + half_spread - inv_skew
    return bid, ask
```

## Riesgos tipicos

- Adverse selection: fills malos antes de movimiento fuerte.
- Inventario acumulado en mercado unilateral.
- Sobre-consumo de rate limits si no hay control.

## Recomendacion para este repo

- Prioridad baja-media para MVP.
- Implementar despues de consolidar trend/mean reversion con riesgo robusto.
- Si se implementa: comenzar en paper/demo con limites de riesgo muy estrictos.
