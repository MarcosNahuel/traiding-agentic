# Verificación de Fase 0 - Foundation

## Paso 1: Instalar dependencias

```bash
pnpm install
```

Esto instalará `tsx` (TypeScript executor) necesario para los scripts de verificación.

## Paso 2: Configurar variables de entorno

Asegúrate de que `.env.local` tenga todas las variables necesarias:

```bash
# Copiar del ejemplo si aún no existe
cp .env.example .env.local
```

Luego edita `.env.local` y completa:

```env
GOOGLE_AI_API_KEY=tu_api_key_de_google
NEXT_PUBLIC_SUPABASE_URL=https://tu-proyecto.supabase.co
SUPABASE_SERVICE_ROLE_KEY=tu_service_role_key
TELEGRAM_BOT_TOKEN=opcional
TELEGRAM_CHAT_ID=opcional
```

### ¿Dónde obtener las credenciales?

**Google AI API Key:**
1. Ve a https://aistudio.google.com/apikey
2. Crea una API key
3. Copia y pega en `GOOGLE_AI_API_KEY`

**Supabase:**
1. Ve a tu proyecto en https://supabase.com/dashboard
2. Settings → API
3. Copia `Project URL` → `NEXT_PUBLIC_SUPABASE_URL`
4. Copia `service_role` (secret) → `SUPABASE_SERVICE_ROLE_KEY`

**Telegram (opcional):**
1. Habla con @BotFather en Telegram
2. Crea un bot con `/newbot`
3. Copia el token → `TELEGRAM_BOT_TOKEN`
4. Obtén tu chat ID hablando con @userinfobot → `TELEGRAM_CHAT_ID`

## Paso 3: Aplicar migraciones a Supabase

Tienes 2 opciones:

### Opción A: SQL Editor (Manual - Recomendado para primera vez)

1. Ve a tu proyecto en Supabase: https://supabase.com/dashboard
2. Abre el **SQL Editor**
3. Crea una nueva query
4. Copia el contenido de `supabase/migrations/001_initial_schema.sql`
5. Pégalo y ejecuta (**Run**)
6. Repite con `supabase/migrations/002_pgvector_setup.sql`

### Opción B: Supabase CLI (Automático)

```bash
# Instalar Supabase CLI si no lo tienes
npm install -g supabase

# Vincular tu proyecto
supabase link --project-ref tu-project-ref

# Aplicar migraciones
supabase db push
```

## Paso 4: Ejecutar verificación

```bash
pnpm run verify
```

Este script verificará:

- ✅ Variables de entorno configuradas
- ✅ Conexión a Supabase
- ✅ Todas las tablas existen
- ✅ pgvector habilitado con HNSW index
- ✅ RPC `match_chunks` funciona
- ✅ Generación de embeddings (1024 dims) con Gemini
- ✅ Inserción y búsqueda vectorial funciona
- ✅ RLS habilitado y políticas correctas
- ✅ Fetcher bloquea IPs privadas y metadata endpoints
- ✅ Telegram envía mensajes (si está configurado)

### Resultados esperados

Si todo está bien, verás:

```
🔍 Starting Fase 0 verification...

✅ Environment: GOOGLE_AI_API_KEY - (2ms)
✅ Environment: NEXT_PUBLIC_SUPABASE_URL - (1ms)
✅ Environment: SUPABASE_SERVICE_ROLE_KEY - (1ms)
✅ Supabase: Connection - (156ms)
✅ Supabase: Table 'sources' exists - (45ms)
✅ Supabase: Table 'paper_extractions' exists - (38ms)
✅ Supabase: Table 'strategies_found' exists - (42ms)
✅ Supabase: Table 'paper_chunks' exists - (40ms)
✅ Supabase: Table 'trading_guides' exists - (43ms)
✅ Supabase: Table 'agent_logs' exists - (41ms)
✅ Supabase: Table 'chat_messages' exists - (39ms)
✅ pgvector: Extension enabled - (78ms)
✅ AI SDK: Generate embedding (1024 dims) - (892ms)
✅ pgvector: Insert + search with HNSW - (1234ms)
✅ RLS: Service role has full access - (34ms)
✅ Fetcher: Blocks private IPs (127.0.0.1) - (2ms)
✅ Fetcher: Blocks metadata endpoint - (1ms)
✅ Fetcher: Blocks invalid protocol - (1ms)
⏭️ Telegram: Send test message - No credentials configured

============================================================

📊 Results: 17 passed, 0 failed, 1 skipped

✅ All checks passed! Fase 0 is complete.
```

## Paso 5: Verificar build

```bash
pnpm run typecheck
pnpm run build
```

Ambos comandos deben pasar sin errores.

## Troubleshooting

### Error: "Missing environment variable"
- Verifica que `.env.local` existe y tiene todas las variables
- Reinicia el script después de editar `.env.local`

### Error: "relation does not exist"
- Las migraciones no están aplicadas
- Ve al Paso 3 y aplica las migraciones manualmente

### Error: "function match_chunks does not exist"
- El archivo `002_pgvector_setup.sql` no se ejecutó correctamente
- Verifica que pgvector esté habilitado en tu proyecto Supabase
- Re-ejecuta la migración 002

### Error: Embedding dimensions != 1024
- Verifica que estás usando `gemini-embedding-001`
- Verifica que `providerOptions.google.outputDimensionality: 1024` está presente

### Error en Telegram
- Si no necesitas Telegram, es normal que aparezca como "skip"
- Si lo configuraste y falla, verifica el token y chat ID

---

## 🎉 Siguiente paso

Una vez que **pnpm run verify** pase sin errores, estás listo para **Fase 1: Source Agent**.
