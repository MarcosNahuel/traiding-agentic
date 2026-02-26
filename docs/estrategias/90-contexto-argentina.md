# Contexto Argentina para Trading Algoritmico BTC

Este archivo agrega variables locales para que las estrategias no ignoren fricciones reales de Argentina.

## 1) Marco regulatorio operativo (resumen tecnico)

### CNV - PSAV

- La CNV mantiene el `Registro de Proveedores de Servicios de Activos Virtuales (PSAV)`.
- Para operaciones institucionales o escalado comercial, verificar contraparte y estatus registral.

### BCRA - comunicaciones relevantes

- `Comunicacion A 7506` (2022): limita a entidades financieras en operaciones con activos digitales no autorizados por autoridad competente.
- `Comunicacion A 7759` (2023): disposicion equivalente para PSPCP.

Implicancia practica:

- Disenar onboarding/operativa asumiendo que canales bancarios y PSP pueden tener restricciones dinamicas.
- Evitar depender de un unico riel de fondeo/retiro.

## 2) Variables de mercado local que SI importan

1. `usd_ars_oficial` (BCRA principal variables/API).
2. `usd_ars_mep` (fuentes de mercado local).
3. `usdt_ars` (agregadores de mercado crypto local).
4. `spread_usdt_mep = usdt_ars / usd_ars_mep - 1`.
5. `spread_usdt_oficial = usdt_ars / usd_ars_oficial - 1`.

Estas brechas afectan:

- Entry/exit de capital.
- Rentabilidad real en ARS.
- Decisiones de transferir entre spot local e internacional.

## 3) Filtros recomendados para el motor de estrategias

1. Bloquear nuevas posiciones si `spread_usdt_mep` supera umbral extremo.
2. Reducir size cuando sube volatilidad local de tipo de cambio.
3. Reportar PnL en `USDT` y en `ARS` para control real.
4. Etiquetar cada trade con snapshot de variables FX locales.

## Snippet Python (filtro de brecha local)

```python
def local_spread_filters(usd_ars_oficial, usd_ars_mep, usdt_ars):
    spread_mep = (usdt_ars / usd_ars_mep) - 1.0
    spread_official = (usdt_ars / usd_ars_oficial) - 1.0

    risk_flag = "normal"
    size_multiplier = 1.0

    if spread_mep > 0.06:
        risk_flag = "high_local_friction"
        size_multiplier = 0.5
    if spread_mep > 0.10:
        risk_flag = "extreme_local_friction"
        size_multiplier = 0.0

    return {
        "spread_mep": spread_mep,
        "spread_official": spread_official,
        "risk_flag": risk_flag,
        "size_multiplier": size_multiplier,
    }
```

## 4) Impuestos y compliance (practico)

- Mantener trazabilidad completa por trade: timestamp, contraparte, costo y PnL.
- Llevar reportes periodicos para soporte fiscal/contable.
- Tratar reglas impositivas como requisito de sistema, no como postproceso.

Nota:

- Este documento no es asesoramiento legal ni fiscal.
- Validar implementacion final con contador/abogado especializado en Argentina.

## 5) Recomendacion de implementacion en el repo

1. Agregar servicio `local_macro_feed` con fuentes configurables.
2. Inyectar `spread_usdt_mep` en `quant_risk` para ajuste de size.
3. Persistir metricas ARS en tabla de reportes diarios.
