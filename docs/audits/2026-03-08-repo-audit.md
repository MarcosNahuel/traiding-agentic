# Auditoría Integral del Repositorio

Fecha: 2026-03-08  
Repositorio: `D:\OneDrive\GitHub\traiding-agentic`  
Base del análisis: `docs/plans/fase-0-foundation.md`, `docs/plans/fase-1-research-agents.md`, `docs/plans/fase-2-trading-core.md`, `docs/plans/fase-3-exchange-hardening.md`, `docs/plans/2026-02-17-Implementacion-Pendiente-Quant-Engine.md`

## Resumen Ejecutivo

El repositorio tiene una base técnica mejor de lo que su documentación sugiere: `lint`, `typecheck`, `build`, `pytest` del backend y la prueba de SSRF pasan. El problema principal no es de compilación sino de arquitectura y seguridad operativa.

Hallazgos clave:

| Severidad | Hallazgo | Impacto |
|---|---|---|
| Crítica | Endpoints operativos públicos con `service_role` y relay al backend Python | Permite lectura/escritura y ejecución sin autenticación efectiva |
| Crítica | Endpoints de diagnóstico/salud exponen metadata sensible y balances | Filtración de infraestructura, estado de cuenta y configuración |
| Alta | Dos loops de trading autónomos en paralelo | Riesgo de señales duplicadas, ejecuciones dobles y estado inconsistente |
| Alta | Ingesta de fuentes bypassa el modelo SSRF al desviar a Jina | Pérdida de garantías de seguridad y fuga de URLs/contenido a terceros |
| Media | CI no ejecuta pruebas del backend ni smoke/integration tests | Regresiones funcionales pueden llegar a producción |
| Media | Documentación y despliegue están desalineados del estado real | Onboarding y operación poco confiables |
| Media | Drift de package manager y artefactos temporales versionados | Builds menos reproducibles y repo más ruidoso |
| Baja | Contrato de entorno y scripts de prueba inconsistentes | Fricción de mantenimiento y pruebas locales |

## Validaciones Ejecutadas

Ejecutadas localmente en esta auditoría:

- `npm run lint` -> OK
- `npm run typecheck` -> OK
- `npm run build` -> OK
- `pytest backend/tests -q` -> OK, `56 passed`, con `6 warnings` en `regime_detector`
- `npm run test:ssrf` -> OK
- `npm run test:chunking` -> FAIL por carga de entorno inconsistente (`scripts/test-chunking.ts` solo lee `.env.local`)

No ejecutadas:

- `tests/features.spec.ts` / Playwright
- `scripts/test-api-routes.ts` porque arranca servidor y depende de Supabase/credenciales reales

## Fortalezas Observadas

- El proyecto compila en Next.js 16 y el pipeline base de calidad (`lint`, `typecheck`, `build`) está sano.
- El backend Python sí tiene una batería de tests real, no solo placeholders.
- La protección SSRF del fetcher principal existe y su prueba dedicada pasa.
- Hay esfuerzo visible de hardening cuantitativo y separación de backend Python/Next.js.

## Hallazgos Detallados

### 1. Crítica: API pública con privilegios administrativos y relay al backend protegido

**Evidencia**

- `lib/supabase.ts:11-20` crea un cliente server-side con `SUPABASE_SERVICE_ROLE_KEY`, saltando RLS.
- `app/api/trades/proposals/route.ts:9-123` crea/lista propuestas sin validar sesión ni token.
- `app/api/trades/execute/route.ts:5-37` ejecuta propuestas o `executeAll` sin autenticación.
- `app/api/pipeline/run/route.ts:16-154` dispara evaluación, extracción y síntesis sin autenticación.
- `app/api/sources/route.ts:12-145` crea y lista fuentes con `service_role` sin auth.
- `lib/trading/python-backend.ts:13-33` añade `Authorization: Bearer ${BACKEND_SECRET}` en cada llamada al backend Python.
- `app/api/health/route.ts:12-37` proxya al backend Python desde una ruta pública.

**Riesgo**

Aunque el backend Python tenga `BACKEND_SECRET`, las rutas públicas de Next.js funcionan como gateway abierto: cualquier cliente que llegue a `/api/*` puede usar la app para leer datos privilegiados o accionar operaciones protegidas porque el servidor reenvía la llamada con secretos internos.

**Arreglo recomendado**

1. Implementar un middleware de autenticación/autoría en Next.js para todas las rutas sensibles de `app/api/**`.
2. Separar rutas públicas de lectura mínima de rutas admin/operativas.
3. Prohibir el uso de `createServerClient()` en handlers públicos; encapsularlo detrás de checks de rol.
4. No reenviar `BACKEND_SECRET` desde handlers públicos si la petición entrante no viene autenticada/autorizada.
5. Agregar auditoría de acceso para todas las acciones que mutan trading, reconciliación o research.

### 2. Crítica: Endpoints de diagnóstico y salud exponen datos sensibles

**Evidencia**

- `.env.example:44-46` documenta `DIAGNOSTIC_KEY`, pero no hay enforcement en código.
- `app/api/diagnostic/route.ts:7-46` expone existencia, longitud y prefijos de variables sensibles.
- `app/api/diagnostic/jwt/route.ts:7-64` decodifica el JWT del service role y devuelve `iss`, `ref`, `role`, expiración y comparación con el proyecto.
- `app/api/binance/test/route.ts:16-125` expone `restBase`, `wsBase`, `apiKeyConfigured`, `secretConfigured`, capacidades de cuenta y balances.
- `backend/app/routers/health.py:63-100` devuelve `total_balance_usdt`, `daily_pnl` y `proxy`.
- `app/api/health/route.ts:12-37` hace público ese payload del backend.

**Riesgo**

Estas rutas entregan información suficiente para mapear infraestructura, verificar credenciales, inferir proveedores y observar saldo/estado operacional sin autenticación.

**Arreglo recomendado**

1. Deshabilitar en producción todas las rutas `/api/diagnostic*` y `/api/binance/test` salvo detrás de auth fuerte.
2. Implementar de verdad `DIAGNOSTIC_KEY` o, mejor, auth de operador con rol.
3. Reducir `/health` a un payload mínimo: `status`, `timestamp`, versión y checks agregados, sin balances ni URLs internas.
4. Revisar que cualquier endpoint de soporte tenga un threat model explícito.

### 3. Alta: Arquitectura split-brain con dos motores de trading activos

**Evidencia**

- `vercel.json:29-33` agenda `/api/cron/trading-loop` cada 5 minutos.
- `app/api/cron/trading-loop/route.ts:22-109` ejecuta el trading loop de Next.js y luego ejecuta propuestas.
- `lib/agents/trading-agent.ts:233-419` evalúa estrategias, genera señales y crea propuestas.
- `lib/trading/executor.ts:48-101` y `:440-487` ejecutan órdenes desde Next.js.
- `backend/app/main.py:45-52` arranca `run_loop()` automáticamente al levantar FastAPI.
- `backend/app/services/trading_loop.py:20-96` corre en bucle cuant, señales, ejecución, portfolio y reconciliación cada 60s.
- `backend/app/config.py:15` usa `binance_env = "testnet"` por defecto, mientras el lado Next exige `spot_testnet` en `lib/trading/executor.ts:87-100` y `lib/exchanges/binance-testnet.ts:30-35`.

**Riesgo**

Hay dos planos de control: Next.js por cron y FastAPI por task de arranque. Esto favorece:

- propuestas duplicadas,
- ejecuciones repetidas,
- reconciliaciones cruzadas,
- señales divergentes,
- reglas de seguridad distintas entre runtimes.

**Arreglo recomendado**

1. Elegir un único orquestador de trading. Mi recomendación: backend Python como autoridad operativa.
2. Si `PYTHON_BACKEND_URL` está configurado, desactivar por completo el loop/ejecutor local de Next.js.
3. Añadir lock distribuido o leader election si el loop Python puede correr en más de una réplica.
4. Unificar el contrato de entorno (`BINANCE_ENV`) y las safety checks entre ambos runtimes.
5. Publicar un ADR corto de “single source of execution truth”.

### 4. Alta: Ingesta de fuentes evade el hardening SSRF al usar Jina como bypass

**Evidencia**

- `app/api/sources/route.ts:162-175` decide usar Jina no solo para PDFs, sino para cualquier `sourceType === "paper"`.
- `lib/utils/jina-fetcher.ts:32-117` solo valida protocolo `http/https`; no valida host privado, DNS, redirects, content-type ni tamaño.
- `lib/utils/fetcher.ts` sí implementa controles SSRF fuertes, pero quedan anulados en el camino Jina.

**Riesgo**

La garantía de “fetch SSRF-safe” solo aplica al camino `safeFetch`. Un usuario puede etiquetar una URL como `paper` y forzar el desvío por un tercero (`r.jina.ai`), lo que:

- rompe la política de fetch prevista en el plan,
- expone URLs/contenido a un servicio externo,
- elimina validaciones de host/IP/tamaño que sí existen en `safeFetch`.

**Arreglo recomendado**

1. Validar siempre la URL con el mismo pipeline de seguridad antes de decidir el fetcher.
2. Limitar Jina a hosts explícitamente permitidos o a PDFs públicos conocidos.
3. No usar `sourceType === "paper"` como equivalente a “usar Jina”.
4. Registrar de forma explícita cuando una fuente se procesa por un tercero.
5. Añadir tests que cubran este bypass, no solo `safeFetch`.

### 5. Media: CI incompleto respecto del riesgo real del sistema

**Evidencia**

- `.github/workflows/ci.yml:25-42` solo corre `pnpm install`, `lint`, `typecheck` y `build`.
- `backend/pytest.ini:1-4` confirma que existe una suite de tests Python lista para correr, pero CI no la usa.
- Existen scripts de verificación adicionales (`test:ssrf`, `test:api`, `test:chunking`, etc.) fuera de CI.

**Riesgo**

El sistema mezcla frontend, research pipeline y trading backend. Validar solo compilación de Next.js deja fuera justo las áreas más sensibles: cuant, reconciliación, señales, ejecución, SSRF y contratos backend/frontend.

**Arreglo recomendado**

1. Añadir un job Python en CI que ejecute `pytest backend/tests -q`.
2. Ejecutar al menos `npm run test:ssrf` y un smoke test de API en CI.
3. Separar checks rápidos de checks integrales para no frenar el pipeline innecesariamente.
4. Publicar un badge o tabla de cobertura real por dominio.

### 6. Media: Documentación y despliegue no describen el sistema actual

**Evidencia**

- `README.md:19-32` habla de `frontend/`, `DATABASE_URL`, IOL/pyRofex y `POST /api/agent/query`, que no reflejan el repo actual.
- `README-DEPLOY.md:1-4` no aporta instrucciones operativas reales.
- `docker-compose.yml:14-16` exige `.env.production`, archivo que no existe actualmente.
- `.env.example:55` fija un `PYTHON_BACKEND_URL` real en lugar de un placeholder.

**Riesgo**

Onboarding, despliegues y troubleshooting dependen de documentación correcta. Hoy el repositorio exige leer el código o `docs/plans` para entender qué corre realmente.

**Arreglo recomendado**

1. Reescribir `README.md` desde cero con la topología actual.
2. Reemplazar `README-DEPLOY.md` por una guía de despliegue real: local, Vercel, backend Python, variables mínimas.
3. Corregir `docker-compose.yml` o agregar el archivo `.env.production.example`.
4. Reemplazar URLs reales en `.env.example` por placeholders.
5. Añadir una sección “Estado actual vs fases del plan”.

### 7. Media: Drift de package manager y repositorio con artefactos temporales

**Evidencia**

- `package.json:1-58` no declara `packageManager`.
- El repositorio versiona tanto `pnpm-lock.yaml` como `package-lock.json`.
- `scripts/test-api-routes.ts` arranca el servidor con `npm run dev`, mientras CI y Docker usan `pnpm`.
- Permanecen artefactos no productivos versionados: `lib/agents/trading-agent-DFC127.ts`, `lib/trading/python-backend-DFC127.ts`, `tmp-execute.json`, `tmp-proposal.json`, `tmp-proposal2.json`, `.next-dev.out.log`, `.next-dev.err.log`.

**Riesgo**

La build puede depender de un lockfile distinto según entorno. Además, los artefactos temporales y backups aumentan ruido, riesgo de confusión y mantenimiento duplicado.

**Arreglo recomendado**

1. Estándar único: `pnpm`.
2. Añadir `"packageManager": "pnpm@<version>"` en `package.json`.
3. Eliminar `package-lock.json` si `pnpm` es el estándar definitivo.
4. Limpiar archivos `-DFC127`, `tmp-*` y logs versionados.
5. Añadir un checklist de “repo hygiene” al PR template o CI.

### 8. Baja: Contrato de entorno y scripts auxiliares inconsistentes

**Evidencia**

- `scripts/test-chunking.ts:6-10` solo carga `.env.local`; en esta auditoría falló por no encontrar `NEXT_PUBLIC_SUPABASE_URL`.
- `.env.example:44-46` documenta `DIAGNOSTIC_KEY` que no se usa.
- `.env.example` no declara `NEXT_PUBLIC_SUPABASE_ANON_KEY`, aunque `lib/supabase.ts:23-27` lo requiere para `createBrowserClient()`.

**Riesgo**

No rompe la app principal hoy, pero sí dificulta reproducibilidad, pruebas locales y futuras integraciones browser-side con Supabase.

**Arreglo recomendado**

1. Unificar estrategia de carga de entorno en scripts (`.env.local` + `.env` fallback).
2. Eliminar variables documentadas que no existen o implementarlas.
3. Completar `.env.example` con todas las variables realmente requeridas.

## Plan de Remediación Priorizado

### Inmediato (24-48h)

1. Cerrar o proteger `/api/diagnostic*`, `/api/binance/test`, `/api/trades/*`, `/api/pipeline/*`, `/api/reconciliation/*`, `/api/dead-letters/*`.
2. Elegir un único motor de ejecución y desactivar el otro en producción.
3. Reducir `/health` a información no sensible.
4. Quitar el bypass por Jina para cualquier `paper` que no sea un caso validado.

### Corto plazo (3-7 días)

1. Añadir auth centralizada para API admin.
2. Meter `pytest backend/tests -q` y `npm run test:ssrf` en CI.
3. Corregir README, despliegue y contrato de variables.
4. Estandarizar `pnpm` y limpiar artefactos temporales.

### Mediano plazo (1-2 semanas)

1. Publicar ADR de arquitectura operativa.
2. Separar frontend público, panel operador y plano de control.
3. Añadir smoke/integration tests reales para trading, research pipeline y proxy Python.
4. Revisar warnings numéricos en `regime_detector` para evitar señales espurias silenciosas.

## Conclusión

El repositorio no está “roto”; está **expuesto y desalineado**. La prioridad no es reescribir el stack, sino cerrar accesos, unificar el motor de trading y restaurar una única verdad operacional. Una vez resuelto eso, el resto de la deuda es manejable y el proyecto queda bastante mejor posicionado para seguir con Fase 2/3 sin introducir riesgo innecesario.
