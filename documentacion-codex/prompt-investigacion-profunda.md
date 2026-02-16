# Prompt de Investigacion Profunda para Validar/Ampliar Documentacion

Actua como auditor tecnico senior de trading algoritmico y arquitecto de sistemas multiagente.

## Objetivo

Validar, corregir y ampliar la documentacion de `documentacion-codex` en `D:\OneDrive\GitHub\traiding-agentic`, con foco en Binance API/Testnet/Demo, ejecucion segura de ordenes, risk management, reconciliacion, observabilidad y preparacion para produccion.

## Contexto base a revisar

- `documentacion-codex/README.md`
- `documentacion-codex/01-contexto-interno-y-criterios.md`
- `documentacion-codex/02-binance-api-testnet-demo.md`
- `documentacion-codex/03-arquitectura-bot-y-flujos.md`
- `documentacion-codex/04-snippets-typescript.md`
- `documentacion-codex/05-repositorios-bots-referencia.md`
- `documentacion-codex/06-checklist-implementacion.md`
- `documentacion-codex/07-arreglos-directos-plan-fase2.md`
- `documentacion-codex/FUENTES.md`
- `docs/plans/2026-02-15-fase2-trading-bot-design.md`
- `docs/plans/2026-02-15-mvp-research-trading-agent-design.md`
- `docs/02-2026/PLAN-TECNICO-MVP-COMPLETO.md`
- `docs/02-2026/Sistema Trading Multiagente Institucional.md`

## Reglas de investigacion

1. Usa fuentes primarias y oficiales primero (Binance Developers, repos oficiales de GitHub, docs oficiales de librerias/frameworks).
2. Si usas fuentes secundarias (blogs/videos), marcalas explicitamente como secundarias.
3. Verifica vigencia con fechas concretas (no "reciente").
4. No inventes endpoints, limites, filtros ni comportamientos de la API.
5. Senala incertidumbre cuando no haya evidencia suficiente.

## Tareas

1. Extrae todas las afirmaciones tecnicas verificables de la documentacion actual.
2. Clasifica cada afirmacion como:
   - VALIDA
   - PARCIALMENTE VALIDA
   - DESACTUALIZADA
   - INCORRECTA
   - NO VERIFICABLE
3. Para cada afirmacion, aporta:
   - evidencia (fuente + link + fecha de acceso)
   - impacto (alto/medio/bajo)
   - cambio recomendado
4. Detecta huecos faltantes criticos (ej.: idempotencia real, timeout unknown, user streams, keepalive, filtros, time sync, rate limits, reconexion WS, fallback LLM seguro, seguridad de claves, runbooks).
5. Propon una version ampliada de `documentacion-codex` con:
   - nuevas secciones necesarias
   - snippets corregidos/mejorados
   - checklist operativo endurecido
   - roadmap tecnico priorizado

## Formato de salida requerido

A) Resumen ejecutivo (10-15 lineas)

B) Hallazgos criticos (ordenados por severidad)

C) Matriz de validacion de afirmaciones (tabla completa)

D) Propuesta de mejoras por archivo (que agregar/quitar/corregir)

E) Parches sugeridos listos para aplicar (diff o contenido final markdown por archivo)

F) Riesgos residuales y pruebas faltantes

G) Bibliografia final con URLs y fecha de consulta

## Criterios de calidad

- Precision tecnica > cantidad.
- Recomendaciones accionables, con prioridades P0/P1/P2.
- Lenguaje claro en espanol.

