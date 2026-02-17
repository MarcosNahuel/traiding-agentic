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
