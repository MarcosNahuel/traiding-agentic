# Research Sources — Índice Maestro

Lista de fuentes externas, papers, y documentación usada para diseñar las estrategias.

## Papers académicos

| Referencia | Tema | Aplicación en el bot |
|---|---|---|
| López de Prado — "Advances in Financial ML" | Triple Barrier Labeling | `MIN_HOLD_MINUTES`, time stop, breakeven gate |
| Cazzola et al. (QS) — Autocorrelation in crypto | Lag-1 AC como filtro pre-trade | `autocorr_1` en signal_generator |
| Lo (2004) — Adaptive Markets | Régimen detection | `regime_detector.py` |
| Chan — "Quantitative Trading" | Kelly sizing, risk-of-ruin | `kelly_dampener` en config |
| Le Baron — Entropy filters | Market noise filtering | `entropy_filter.py` |

## Blogs / sitios web

| Fuente | URL | Uso |
|---|---|---|
| QuantScience.io | https://quantscience.io | PPO, Chandelier Exit, Autocorrelation, Hurst |
| Freqtrade docs | https://www.freqtrade.io | Anti-churn patterns |
| Binance docs | https://binance-docs.github.io | API, OCO orders, filters |
| Machine Learning for Trading (Stefan Jansen) | https://ml4trading.io | ML pipeline reference |

## Documentos internos

| Archivo | Fecha | Tema |
|---|---|---|
| `docs/plans/PLAN-ARQUITECTURA-BOT-AGENTICO.md` | 2025-08-14 | Arquitectura original |
| `docs/AUDITORIA_BACKEND_TRADING_2026-03-13.md` | 2026-03-13 | Auditoría crítica |
| `docs/QA-REPORT-2026-03-31.md` | 2026-03-31 | QA post-refactor |
| `Backend MVP Bot Trading_ Investigación.docx` | 2025-08-13 | Research inicial |
| `Resumen Ejecutivo de Hallazgos y Recomendación.docx` | 2025-08-13 | Recomendaciones iniciales |
| `docs/estrategias/` | varias | Notas de estrategia |
| `docs/algoritmos/` | varias | Detalles algorítmicos |

## Research generado por Claude / análisis

| Archivo | Fecha | Contenido |
|---|---|---|
| `2026-04-05-post-mortem-49trades.md` | 2026-04-05 | Post-mortem de -$18.74 en 49 trades |
| `2026-04-11-improvements-analysis.md` | 2026-04-11 | Análisis de mejoras a la estrategia (este KB) |
| `gaps.md` | 2026-04-11 | Deudas técnicas abiertas |

## Reglas para añadir fuentes nuevas

1. **Siempre registrar la fecha** de acceso (las URLs cambian)
2. **Citar qué parte del bot** usa la fuente
3. **Resumir la idea clave** en 1-2 líneas
4. **Si es un paper, incluir DOI o arXiv ID**
5. **Si es research generado por Claude, commit al repo**
