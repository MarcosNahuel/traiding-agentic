/**
 * Python Trading Backend Client
 * Proxies to the Python FastAPI backend running on VPS.
 * Falls back to direct execution if PYTHON_BACKEND_URL is not set.
 */

const BACKEND_URL = process.env.PYTHON_BACKEND_URL?.replace(/\/$/, "");

export function isPythonBackendEnabled(): boolean {
  return !!BACKEND_URL;
}

async function call(method: string, path: string, body?: unknown): Promise<unknown> {
  if (!BACKEND_URL) throw new Error("PYTHON_BACKEND_URL not configured");

  const url = `${BACKEND_URL}${path}`;
  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(30000),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Backend ${method} ${path} → ${res.status}: ${text}`);
  }

  return res.json();
}

export async function createProposal(data: {
  type: string; symbol: string; quantity: number;
  price?: number; order_type?: string; strategy_id?: string; reasoning?: string;
}) {
  return call("POST", "/proposals", data);
}

export async function listProposals(params: Record<string, string | number> = {}) {
  const qs = new URLSearchParams(params as Record<string, string>).toString();
  return call("GET", `/proposals${qs ? "?" + qs : ""}`);
}

export async function getProposal(id: string) {
  return call("GET", `/proposals/${id}`);
}

export async function updateProposal(id: string, data: { action: string; notes?: string }) {
  return call("PATCH", `/proposals/${id}`, data);
}

export async function executeProposal(data: { proposal_id?: string; execute_all?: boolean }) {
  return call("POST", "/execute", data);
}

export async function getPortfolio() {
  return call("GET", "/portfolio");
}

// ============================================================================
// QUANT ENGINE ENDPOINTS
// ============================================================================

export async function getQuantAnalysis(symbol: string, interval: string = "1h") {
  return call("GET", `/analysis/${symbol}?interval=${interval}`);
}

export async function getIndicators(symbol: string, interval: string = "1h") {
  return call("GET", `/indicators/${symbol}?interval=${interval}`);
}

export async function getRegime(symbol: string) {
  return call("GET", `/analysis/${symbol}`).then((r: any) => r?.regime);
}

export async function getEntropy(symbol: string, interval: string = "1h") {
  return call("GET", `/analysis/${symbol}/entropy?interval=${interval}`);
}

export async function getSRLevels(symbol: string) {
  return call("GET", `/analysis/${symbol}`).then((r: any) => r?.sr_levels);
}

export async function getPositionSizing(symbol: string) {
  return call("GET", `/analysis/${symbol}`).then((r: any) => r?.position_sizing);
}

export async function runBacktest(data: {
  strategy_id: string; symbol?: string; interval?: string;
  lookback_days?: number; parameters?: Record<string, unknown>;
}) {
  return call("POST", "/backtest/run", data);
}

export async function getBacktestResults(strategyId?: string) {
  const qs = strategyId ? `?strategy_id=${strategyId}` : "";
  return call("GET", `/backtest/results${qs}`);
}

export async function getQuantStatus() {
  return call("GET", "/quant/status");
}

export async function getPerformanceMetrics() {
  return call("GET", "/quant/performance");
}

export async function getQuantSnapshot(symbol: string) {
  return call("GET", `/quant/snapshot/${symbol}`);
}
