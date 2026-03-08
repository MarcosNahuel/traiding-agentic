import { NextResponse } from "next/server";

/**
 * Verifica DIAGNOSTIC_KEY en header X-Diagnostic-Key o query param ?key=
 * Retorna null si OK, o NextResponse 401/403 si falla.
 */
export function requireDiagnosticKey(request: Request): NextResponse | null {
  const diagnosticKey = process.env.DIAGNOSTIC_KEY;

  // Si no está configurada, bloquear completamente en producción
  if (!diagnosticKey) {
    if (process.env.NODE_ENV === "production") {
      return NextResponse.json(
        { error: "Diagnostic endpoints disabled in production" },
        { status: 403 }
      );
    }
    // En dev sin key: permitir (facilita desarrollo local)
    return null;
  }

  const url = new URL(request.url);
  const providedKey =
    request.headers.get("X-Diagnostic-Key") ||
    url.searchParams.get("key");

  if (providedKey !== diagnosticKey) {
    return NextResponse.json(
      { error: "Unauthorized: invalid diagnostic key" },
      { status: 401 }
    );
  }

  return null;
}
