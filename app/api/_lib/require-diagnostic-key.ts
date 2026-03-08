import { requireApiKey } from "./require-api-key";

export function requireDiagnosticKey(request: Request) {
  return requireApiKey(
    request,
    "DIAGNOSTIC_KEY",
    "X-Diagnostic-Key",
    "Diagnostic endpoints disabled in production"
  );
}
