# Auto-Synthesis System

## 📋 Overview

El sistema de auto-synthesis automáticamente genera guías de trading consolidadas cuando se procesan N papers nuevos. Esto elimina la necesidad de ejecutar manualmente el synthesis agent.

## 🔄 Cómo Funciona

1. **Después de cada paper procesado**: El Reader Agent verifica si es momento de ejecutar synthesis
2. **Conteo de papers**: Se cuentan los papers procesados desde la última síntesis
3. **Trigger automático**: Si se alcanza el threshold (default: 5 papers), se dispara synthesis
4. **Ejecución en background**: La síntesis se ejecuta sin bloquear la respuesta al usuario

## ⚙️ Configuración

### Threshold por Defecto
```typescript
const DEFAULT_CONFIG = {
  threshold: 5,     // Trigger después de 5 papers
  enabled: true,    // Sistema activado
};
```

### Cambiar el Threshold

Edita `lib/services/auto-synthesis.ts`:

```typescript
const DEFAULT_CONFIG = {
  threshold: 3,     // Ahora se dispara después de 3 papers
  enabled: true,
};
```

### Deshabilitar Auto-Synthesis

```typescript
const DEFAULT_CONFIG = {
  threshold: 5,
  enabled: false,   // Sistema desactivado
};
```

## 📊 Verificar Estado

Usa el servicio `getAutoSynthesisStatus()`:

```typescript
import { getAutoSynthesisStatus } from "@/lib/services/auto-synthesis";

const status = await getAutoSynthesisStatus();

console.log({
  lastSynthesis: status.lastSynthesis,              // Última síntesis
  newPapers: status.newPapersSinceLastSynthesis,    // Papers nuevos
  threshold: status.threshold,                       // Umbral actual
  ready: status.readyToTrigger,                     // ¿Listo para disparar?
});
```

## 🧪 Testing

### Test Básico
```bash
npm run test:auto-synthesis
```

### Test con Reader Agent Real
```bash
# 1. Agregar un paper de prueba
npm run test:source-agent

# 2. Procesar el paper (esto debería checkear auto-synthesis)
npm run test:reader-agent

# 3. Verificar que synthesis se disparó automáticamente
npm run test:synthesis-agent
```

## 📁 Archivos del Sistema

### Servicio Principal
- `lib/services/auto-synthesis.ts` - Lógica de auto-trigger

### Integración
- `lib/agents/reader-agent.ts` - Llama a `checkAndTriggerSynthesis()` después de procesar

### Tests
- `scripts/test-auto-synthesis.ts` - Test unitario del servicio

## 🔍 Logs

Cuando se dispara auto-synthesis, verás logs como:

```
Auto-synthesis check: 5 new papers (threshold: 5)
🤖 Auto-triggering synthesis: 5 papers processed
Found 23 strategies to synthesize
Created trading guide v2 (ID: xyz...)
```

## ⚠️ Consideraciones

### Performance
- La síntesis se ejecuta en background con `.catch()` para no bloquear
- Puede tomar 10-30 segundos dependiendo del número de estrategias
- Los logs se guardan en `agent_logs` table

### Errores
- Si synthesis falla, el error se logea pero NO afecta el processing del paper
- Puedes ejecutar synthesis manualmente si el auto-trigger falla

### Costos
- Cada síntesis cuesta ~$0.001-0.003 USD (Gemini 2.5 Flash)
- Con threshold=5, el costo promedio es ~$0.0006 USD por paper

## 🚀 Mejoras Futuras

1. **UI para configurar threshold** - Agregar control en frontend
2. **Notificaciones** - Alertar cuando synthesis se completa
3. **Scheduling** - Opción para ejecutar synthesis en horarios específicos
4. **Incremental synthesis** - Solo re-synthesizar secciones afectadas
5. **Quality gates** - Solo disparar si papers cumplen mínimo de calidad

## 📚 Ejemplo de Flujo Completo

```
User → Add Paper → Source Agent ✅
                         ↓
                  Reader Agent 📖 (extrae estrategias)
                         ↓
                  checkAndTriggerSynthesis() 🔍
                         ↓
              ¿5+ papers procesados? ✅
                         ↓
              Synthesis Agent 🤖 (automático)
                         ↓
              Nueva guía v2 generada 📖
```

## 🔗 Referencias

- Source Agent: `lib/agents/source-agent.ts`
- Reader Agent: `lib/agents/reader-agent.ts`
- Synthesis Agent: `lib/agents/synthesis-agent.ts`
- Auto-Synthesis Service: `lib/services/auto-synthesis.ts`
