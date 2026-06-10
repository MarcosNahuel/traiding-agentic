# Strategist Evaluation — 2026-05-31

- **Run at:** 2026-05-31T14:09:43.447473+00:00
- **Decision:** `RECOMMEND_PAUSE`
- **Confidence:** 0.75

## Summary

Múltiples triggers KB confirmados justifican pausa operacional. PF rolling 30d = 0.31 en 72 trades viola umbral KB (0.8); max DD 30d -27.98%; régimen desfavorable (ranging/Fear); y anomalías severas de datos en producción (SL corruptos por encima del entry en 2 instancias). La muestra 7d (21 trades, PF 1.50) es insuficiente para inferir recovery (regla anti-overfitting: <100 trades). Adicionalmente, deploy pipeline potencialmente roto desde ~abr-14 introduce incertidumbre operacional crítica: el código real en producción podría no ser el configurado. Pausa recomendada hasta: (1) verificar y reparar deploy pipeline, (2) corregir bug de registro de SL, (3) aguardar régimen trending_up con confianza >75% y F&G >45.

## Data Quality

PARCIALMENTE BLOQUEANTE. Anomalías detectadas: (A) SL registrado por encima del entry en 2 posiciones LONG ETHUSDT — alta severidad, posible bug en producción en el cálculo o persistencia del SL; (B) Posición ETHUSDT con status=partially_closed pero partial_exit_taken=false — inconsistencia de estado media severidad; (C) Daily research RSS no disponible (feedparser no instalado en MCP) — impacto bajo, compensado con WebSearch; (D) Deploy pipeline roto desde ~abr-14 — CRÍTICO: los parámetros configurados en KB pueden no ser los que corre el bot real; (E) ML review: modelo nunca entrenado, no aporta información. La anomalía D es la más severa: torna inútil cualquier TWEAK_PARAMS hasta verificar que el código nuevo llega a producción.

## Performance Review

Rolling 7d (21 trades): WR 52.38%, PF 1.4964, Sharpe 2.02, Sortino 5.30, expectancy +$0.092/trade. MUESTRA INSUFICIENTE — 21 < 100 trades mínimos para inferir edge. No concluyente según reglas de no-overfitting.
Rolling 30d (72 trades): WR 47.22%, PF 0.3061, Sharpe -3.79, Sortino -3.14, expectancy -$0.343/trade, Kelly -37.46%. MUESTRA SUFICIENTE — edge negativo claro, viola umbral KB de PF 0.8.
All-time (165 trades): WR 47.88%, PF 0.6489, Sharpe -1.78, max DD -30.74%. Kelly all-time negativo (-9.07%) confirma ausencia de edge estadístico histórico.
Trades 48h: BTC 4 trades WR 25% PnL neto -$0.352; ETH 4 trades WR 50% PnL neto -$0.612. El trade con mayor pérdida individual fue un SL hit en ETH (-$0.744 en 23 min) — entrada en momento de alta volatilidad.
Posiciones abiertas: 3 posiciones (1 BTC LONG, 2 ETH LONG), uPnL total -$0.082 — neutrales por ahora.

## Macro Context

F&G Index: 28 (Fear), tendencia plana-deterioro durante todo mayo (rango 27-43 en el mes). BTC precio actual $74,009 — 1.9% bajo VWAP diario ($75,412). ETH precio actual $2,021 — 2.4% bajo VWAP diario ($2,069). Funding rates BTC/ETH: pasaron de negativo a neutro (alivio de presión short, posible floor de corto plazo). Posicionamiento Binance: 34.5% largo vs 65.5% corto — crowd short extremo, señal contrarian-bullish de muy corto plazo. ETF outflows: ~$2B netos en 10 días (20-29 mayo), rompiendo 6 semanas consecutivas de inflows positivos. Options expiry BTC+ETH: HOY 31-may — puede generar pin hacia strikes de mayor interés abierto y volatilidad intraday. US-Iran truce (60 días): pendiente de firma presidencial, catalizador risk-on potencial pero no confirmado. Régimen inferido: ranging con sesgo trending_down — no favorable para estrategia 01-trend-momentum según decision-matrix KB.

## Evidence

- 1. PF rolling 30d = 0.31 en 72 trades — viola umbral KB de PF < 0.8 (muestra suficiente para ser concluyente)
- 2. Max drawdown 30d = -27.98%, all-time -30.74% — mayo concentró casi todo el drawdown histórico del bot
- 3. Expectancy 30d = -$0.343/trade — sistema destruyó valor de forma sistemática durante el mes
- 4. F&G Index = 28 (Fear), tendencia plana/deterioro durante todo mayo — contexto adverso para trend-momentum
- 5. ETF BTC+ETH: outflows netos ~$2B en 10 días (20-29 mayo), rompiendo racha de 6 semanas de inflows positivos (~$3.4B) — salida de capital institucional
- 6. Régimen ETH = ranging confianza 50% (piso del detector); BTC = trending_up 67% pero MACD histogram negativo y precio 1.9% por debajo del VWAP diario — divergencia interna en señales
- 7. SL registrado por encima del entry en posiciones LONG ETHUSDT (2 instancias confirmadas) — anomalía de datos alta severidad, posible bug activo en producción
- 8. Deploy pipeline roto desde ~abr-14 (Dokploy no tira imagen nueva, deploys terminan en ms) — código de fixes no llega a bot; config real en producción es desconocida
- 9. Options expiry BTC+ETH hoy 31-may — volatilidad intraday elevada, entorno adverso para trend-following de señal limpia
- 10. Volume ratio BTC 0.244, ETH 0.397 — volumen anormalmente bajo en ambos activos, confirmando ausencia de momentum institucional

## Proposed Config

(no config change — KEEP_AS_IS / recommendation only)

## Risks

1. FALSO NEGATIVO: Si la recuperación 7d (PF 1.50, Sharpe 2.02) es genuina y no ruido de muestra, pausar hace perder un edge emergente real. Bajo probabilidad dado que 21 trades < 100 umbral mínimo de validación.
2. CATALIZADOR MACRO PERDIDO: US-Iran truce pendiente de firma podría actuar como catalizador risk-on y generar trending_up estable — el bot no estaría operando.
3. PAUSA NO SOLUCIONA INFRA: La recomendación de pausa no repara el deploy pipeline ni corrige el bug de SL. Requiere acción humana explícita sobre Dokploy y el código de producción. Sin esas correcciones, reactivar el bot no resuelve los problemas estructurales.
4. CROWD SHORT CONTRARIAN: 65.5% del retail en Binance está short — señal contrarian-bullish de muy corto plazo que podría generar squeeze alcista intraday.

---
*Dry-run: esta propuesta NO está activa. Requiere aprobación humana para promoverse a `status=active`.*