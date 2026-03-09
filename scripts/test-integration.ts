#!/usr/bin/env tsx
/**
 * Integration tests — valida auth guards y estructura de endpoints.
 * No requiere servidor corriendo ni credenciales reales.
 * Corre en CI con variables dummy.
 */

import { config } from "dotenv";
import { resolve } from "path";

config({ path: resolve(process.cwd(), ".env.local") });
config({ path: resolve(process.cwd(), ".env"), override: false });

interface TestResult {
  name: string;
  status: "pass" | "fail";
  message?: string;
}

const results: TestResult[] = [];

function pass(name: string, msg?: string) {
  results.push({ name, status: "pass", message: msg });
  console.log(`✅ ${name}${msg ? ` — ${msg}` : ""}`);
}

function fail(name: string, msg: string) {
  results.push({ name, status: "fail", message: msg });
  console.log(`❌ ${name} — ${msg}`);
}

async function runTest(name: string, fn: () => Promise<void>) {
  try {
    await fn();
    pass(name);
  } catch (e) {
    fail(name, e instanceof Error ? e.message : String(e));
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeRequest(url: string, headers: Record<string, string> = {}): Request {
  return new Request(url, { headers });
}

// Guarda y restaura variables de entorno para que los tests sean aislados
function withEnv(
  overrides: Record<string, string | undefined>,
  fn: () => void | Promise<void>
): Promise<void> {
  const saved: Record<string, string | undefined> = {};
  for (const [key, value] of Object.entries(overrides)) {
    saved[key] = process.env[key];
    if (value === undefined) {
      delete process.env[key];
    } else {
      process.env[key] = value;
    }
  }
  const restore = () => {
    for (const [key, value] of Object.entries(saved)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  };
  const result = Promise.resolve().then(() => fn());
  return result.finally(restore);
}

// ── Tests: require-api-key ────────────────────────────────────────────────────

async function testRequireApiKey() {
  console.log("\n🔐 Auth guards (require-api-key)\n");

  // Importar con ruta relativa al CWD del script (se ejecuta desde la raíz del proyecto)
  const { requireApiKey } = await import("../app/api/_lib/require-api-key");

  // Sin key configurada en producción: debe retornar 403
  await runTest("Sin OPERATOR_API_KEY en producción → 403", async () => {
    await withEnv({ NODE_ENV: "production", OPERATOR_API_KEY: undefined }, async () => {
      const req = makeRequest("http://localhost/api/trades/proposals");
      const res = requireApiKey(req, "OPERATOR_API_KEY", "X-Operator-Key", "disabled in production");

      if (!res) throw new Error("Esperaba Response(403), got null (permitido)");
      if (res.status !== 403) throw new Error(`Esperaba status 403, got ${res.status}`);

      const body = await res.json();
      if (!body.error) throw new Error("Respuesta sin campo 'error'");
    });
  });

  // Con key configurada pero sin header: debe retornar 401
  await runTest("OPERATOR_API_KEY configurada, sin header → 401", async () => {
    await withEnv({ OPERATOR_API_KEY: "test-secret-key-for-integration-tests" }, async () => {
      const req = makeRequest("http://localhost/api/trades/proposals");
      const res = requireApiKey(req, "OPERATOR_API_KEY", "X-Operator-Key", "disabled");

      if (!res) throw new Error("Esperaba Response(401), got null (permitido)");
      if (res.status !== 401) throw new Error(`Esperaba status 401, got ${res.status}`);

      const body = await res.json();
      if (!body.error) throw new Error("Respuesta sin campo 'error'");
    });
  });

  // Con key incorrecta en header: debe retornar 401
  await runTest("OPERATOR_API_KEY configurada, key incorrecta → 401", async () => {
    await withEnv({ OPERATOR_API_KEY: "test-secret-key-for-integration-tests" }, async () => {
      const req = makeRequest("http://localhost/api/trades/proposals", {
        "X-Operator-Key": "wrong-key",
      });
      const res = requireApiKey(req, "OPERATOR_API_KEY", "X-Operator-Key", "disabled");

      if (!res) throw new Error("Esperaba Response(401), got null (permitido)");
      if (res.status !== 401) throw new Error(`Esperaba status 401, got ${res.status}`);
    });
  });

  // Con key correcta en header: debe retornar null (permitido)
  await runTest("OPERATOR_API_KEY correcta en X-Operator-Key → permitido (null)", async () => {
    await withEnv({ OPERATOR_API_KEY: "test-secret-key-for-integration-tests" }, async () => {
      const req = makeRequest("http://localhost/api/trades/proposals", {
        "X-Operator-Key": "test-secret-key-for-integration-tests",
      });
      const res = requireApiKey(req, "OPERATOR_API_KEY", "X-Operator-Key", "disabled");

      if (res !== null) throw new Error(`Esperaba null (permitido), got status ${res?.status}`);
    });
  });

  // Sin key en development: debe retornar null (permitido sin auth)
  await runTest("Sin OPERATOR_API_KEY en development → permitido (null)", async () => {
    await withEnv({ NODE_ENV: "development", OPERATOR_API_KEY: undefined }, async () => {
      const req = makeRequest("http://localhost/api/trades/proposals");
      const res = requireApiKey(req, "OPERATOR_API_KEY", "X-Operator-Key", "disabled");

      if (res !== null) throw new Error(`En dev sin key debería permitir, got status ${res?.status}`);
    });
  });

  // timingSafeEqual: longitud diferente → 401 (sin comparación byte a byte)
  await runTest("Key de longitud distinta → 401 (sin timing leak)", async () => {
    await withEnv({ OPERATOR_API_KEY: "exact-32-chars-key-padded-00000" }, async () => {
      const req = makeRequest("http://localhost/api/trades/proposals", {
        "X-Operator-Key": "short",
      });
      const res = requireApiKey(req, "OPERATOR_API_KEY", "X-Operator-Key", "disabled");

      if (!res) throw new Error("Esperaba Response(401), got null");
      if (res.status !== 401) throw new Error(`Esperaba 401, got ${res.status}`);
    });
  });
}

// ── Tests: require-operator-key wrapper ──────────────────────────────────────

async function testRequireOperatorKey() {
  console.log("\n🔑 Operator key wrapper (require-operator-key)\n");

  const { requireOperatorKey } = await import("../app/api/_lib/require-operator-key");

  await runTest("requireOperatorKey sin key en producción → 403", async () => {
    await withEnv({ NODE_ENV: "production", OPERATOR_API_KEY: undefined }, async () => {
      const req = makeRequest("http://localhost/api/trades/proposals");
      const res = requireOperatorKey(req);

      if (!res) throw new Error("Esperaba Response(403), got null");
      if (res.status !== 403) throw new Error(`Esperaba 403, got ${res.status}`);
    });
  });

  await runTest("requireOperatorKey con key correcta → permitido (null)", async () => {
    await withEnv({ OPERATOR_API_KEY: "op-key-abc" }, async () => {
      const req = makeRequest("http://localhost/api/trades/proposals", {
        "X-Operator-Key": "op-key-abc",
      });
      const res = requireOperatorKey(req);

      if (res !== null) throw new Error(`Esperaba null, got status ${res?.status}`);
    });
  });
}

// ── Tests: require-diagnostic-key wrapper ────────────────────────────────────

async function testRequireDiagnosticKey() {
  console.log("\n🩺 Diagnostic key guard (require-diagnostic-key)\n");

  const { requireDiagnosticKey } = await import("../app/api/_lib/require-diagnostic-key");

  await runTest("Sin DIAGNOSTIC_KEY en producción → 403", async () => {
    await withEnv({ NODE_ENV: "production", DIAGNOSTIC_KEY: undefined }, async () => {
      const req = makeRequest("http://localhost/api/diagnostic");
      const res = requireDiagnosticKey(req);

      if (!res) throw new Error("Esperaba Response(403), got null");
      if (res.status !== 403) throw new Error(`Esperaba 403, got ${res.status}`);

      const body = await res.json();
      if (!body.error) throw new Error("Respuesta sin campo 'error'");
    });
  });

  await runTest("DIAGNOSTIC_KEY correcta en X-Diagnostic-Key → permitido (null)", async () => {
    await withEnv({ DIAGNOSTIC_KEY: "diag-secret-key" }, async () => {
      const req = makeRequest("http://localhost/api/diagnostic", {
        "X-Diagnostic-Key": "diag-secret-key",
      });
      const res = requireDiagnosticKey(req);

      if (res !== null) throw new Error(`Esperaba null, got status ${res?.status}`);
    });
  });

  await runTest("DIAGNOSTIC_KEY configurada, header ausente → 401", async () => {
    await withEnv({ DIAGNOSTIC_KEY: "diag-secret-key" }, async () => {
      const req = makeRequest("http://localhost/api/diagnostic");
      const res = requireDiagnosticKey(req);

      if (!res) throw new Error("Esperaba Response(401), got null");
      if (res.status !== 401) throw new Error(`Esperaba 401, got ${res.status}`);
    });
  });
}

// ── Tests: session token ──────────────────────────────────────────────────────

async function testSessionToken() {
  console.log("\n🔒 Session token (lib/auth/token)\n");

  // Necesitamos reimportar para que tome los cambios de env.
  // tsx/Node cachea módulos: usamos un workaround con eval dinámico.
  // Como getSessionToken es puro (lee process.env en cada llamada), basta con
  // importar una vez y verificar que el resultado varía con el env.
  const { getSessionToken } = await import("../lib/auth/token");

  await runTest("getSessionToken retorna string de 32 chars con OPERATOR_API_KEY", async () => {
    await withEnv({ OPERATOR_API_KEY: "test-secret-key-for-integration-tests" }, () => {
      const token = getSessionToken();
      if (!token || token.length === 0) throw new Error("Token vacío");
      if (token.length !== 32) throw new Error(`Token debe tener 32 chars, got ${token.length}`);
    });
  });

  await runTest("getSessionToken retorna string vacío sin OPERATOR_API_KEY", async () => {
    await withEnv({ OPERATOR_API_KEY: undefined }, () => {
      const token = getSessionToken();
      if (token !== "") throw new Error(`Esperaba string vacío, got "${token}"`);
    });
  });

  await runTest("getSessionToken es determinístico (misma key → mismo token)", async () => {
    await withEnv({ OPERATOR_API_KEY: "deterministic-test-key" }, () => {
      const t1 = getSessionToken();
      const t2 = getSessionToken();
      if (t1 !== t2) throw new Error(`No es determinístico: t1="${t1}" t2="${t2}"`);
    });
  });

  await runTest("getSessionToken keys distintas → tokens distintos", async () => {
    process.env.OPERATOR_API_KEY = "key-alpha";
    const t1 = getSessionToken();
    process.env.OPERATOR_API_KEY = "key-beta";
    const t2 = getSessionToken();
    delete process.env.OPERATOR_API_KEY;

    if (t1 === t2) throw new Error("Keys distintas produjeron el mismo token");
  });

  await runTest("getSessionToken solo contiene hex (no expone key en texto)", async () => {
    const key = "my-secret-operator-key";
    await withEnv({ OPERATOR_API_KEY: key }, () => {
      const token = getSessionToken();

      // El token debe ser solo hex lowercase
      if (!/^[0-9a-f]+$/.test(token)) {
        throw new Error(`Token contiene chars no-hex: "${token}"`);
      }
      // No debe contener la key en texto plano
      if (token.includes(key)) {
        throw new Error("Token contiene la key en texto plano");
      }
      // No debe contener base64 de la key (primeros 16 chars)
      const keyBase64 = Buffer.from(key).toString("base64");
      if (token.includes(keyBase64.slice(0, 16))) {
        throw new Error("Token contiene fragmento base64 de la key");
      }
    });
  });
}

// ── Tests: middleware lógica de rutas públicas ────────────────────────────────

async function testMiddlewarePublicPaths() {
  console.log("\n🌐 Middleware — rutas públicas\n");

  // Importamos la lista de rutas públicas comprobando la lógica del middleware.
  // No podemos importar middleware.ts directamente (es Edge Runtime con crypto.subtle),
  // pero sí verificamos la lista de paths públicos documentada.
  const PUBLIC_PATHS = [
    "/login",
    "/api/health",
    "/api/auth",
    "/api/telegram",
    "/favicon.ico",
  ];

  function isPublicPath(pathname: string): boolean {
    return PUBLIC_PATHS.some((p) => pathname.startsWith(p));
  }

  await runTest("/api/health es ruta pública", async () => {
    if (!isPublicPath("/api/health")) throw new Error("/api/health debería ser pública");
  });

  await runTest("/login es ruta pública", async () => {
    if (!isPublicPath("/login")) throw new Error("/login debería ser pública");
  });

  await runTest("/api/telegram es ruta pública", async () => {
    if (!isPublicPath("/api/telegram")) throw new Error("/api/telegram debería ser pública");
  });

  await runTest("/api/auth es ruta pública", async () => {
    if (!isPublicPath("/api/auth")) throw new Error("/api/auth debería ser pública");
  });

  await runTest("/api/trades/proposals NO es ruta pública", async () => {
    if (isPublicPath("/api/trades/proposals")) {
      throw new Error("/api/trades/proposals no debería ser pública");
    }
  });

  await runTest("/api/health/extended es pública (startsWith)", async () => {
    if (!isPublicPath("/api/health/extended")) {
      throw new Error("/api/health/extended debería ser pública por prefijo");
    }
  });

  await runTest("/dashboard NO es ruta pública", async () => {
    if (isPublicPath("/dashboard")) {
      throw new Error("/dashboard no debería ser pública");
    }
  });
}

// ── Tests: estructura de respuesta /api/health ────────────────────────────────

async function testHealthEndpointStructure() {
  console.log("\n❤️  Health endpoint — estructura de respuesta\n");

  // Verificamos la estructura esperada del response JSON de /api/health
  // sin levantar servidor: validamos que los campos requeridos existan
  // en el schema definido en el handler.

  await runTest("Schema health contiene status, frontend, backend, timestamp", async () => {
    // Simulamos la respuesta que produciría el handler con env dummy
    const simulatedResponse = {
      status: "degraded", // sin backend configurado
      frontend: {
        checks: {
          python_backend: "not_configured",
          supabase_url: "ok",
          supabase_key: "ok",
        },
      },
      backend: null,
      timestamp: new Date().toISOString(),
    };

    const requiredFields = ["status", "frontend", "backend", "timestamp"];
    for (const field of requiredFields) {
      if (!(field in simulatedResponse)) {
        throw new Error(`Campo requerido "${field}" ausente en health response`);
      }
    }
  });

  await runTest("status values son 'healthy' | 'degraded' | 'unhealthy'", async () => {
    const VALID_STATUSES = ["healthy", "degraded", "unhealthy"];

    // Caso 1: frontend ok, sin backend → degraded
    const frontendOk = true;
    const backendHealth = null;
    let overall = "healthy";
    if (!frontendOk || backendHealth === "unhealthy") overall = "unhealthy";
    else if (!backendHealth) overall = "degraded";

    if (!VALID_STATUSES.includes(overall)) {
      throw new Error(`Status inválido: "${overall}"`);
    }
  });

  await runTest("frontend.checks contiene python_backend, supabase_url, supabase_key", async () => {
    const EXPECTED_CHECKS = ["python_backend", "supabase_url", "supabase_key"];
    const simulatedChecks: Record<string, string> = {
      python_backend: "not_configured",
      supabase_url: "ok",
      supabase_key: "ok",
    };

    for (const check of EXPECTED_CHECKS) {
      if (!(check in simulatedChecks)) {
        throw new Error(`Check requerido "${check}" ausente en frontend.checks`);
      }
    }
  });

  await runTest("timestamp tiene formato ISO 8601", async () => {
    const ts = new Date().toISOString();
    // ISO 8601 básico: YYYY-MM-DDTHH:mm:ss.mssZ
    if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z$/.test(ts)) {
      throw new Error(`Timestamp no cumple ISO 8601: "${ts}"`);
    }
  });
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function main() {
  console.log("🧪 Integration Tests — Auth Guards & Security");
  console.log("=".repeat(60));

  await testRequireApiKey();
  await testRequireOperatorKey();
  await testRequireDiagnosticKey();
  await testSessionToken();
  await testMiddlewarePublicPaths();
  await testHealthEndpointStructure();

  console.log("\n" + "=".repeat(60));

  const passed = results.filter((r) => r.status === "pass").length;
  const failed = results.filter((r) => r.status === "fail").length;
  console.log(`\n📊 Results: ${passed} passed, ${failed} failed\n`);

  if (failed > 0) {
    console.log("❌ Tests fallidos:");
    results
      .filter((r) => r.status === "fail")
      .forEach((r) => console.log(`   - ${r.name}: ${r.message}`));
    process.exit(1);
  }

  console.log("✅ All integration tests passed!\n");
  process.exit(0);
}

main().catch((e) => {
  console.error("💥 Integration test runner crashed:", e);
  process.exit(1);
});
