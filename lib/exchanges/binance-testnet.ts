/**
 * Binance Testnet Integration
 *
 * Docs: https://testnet.binance.vision/
 * API Docs: https://binance-docs.github.io/apidocs/spot/en/
 */

import crypto from "crypto";

const rawBinanceEnv = process.env.BINANCE_ENV ?? "spot_testnet";
const normalizedBinanceEnv = rawBinanceEnv.trim();

// Proxy configuration (for Vercel deployment)
const USE_PROXY = !!process.env.BINANCE_PROXY_URL;
const PROXY_URL = process.env.BINANCE_PROXY_URL;
const PROXY_AUTH_SECRET = process.env.BINANCE_PROXY_AUTH_SECRET;

// Configuration
export const BINANCE_CONFIG = {
  REST_BASE: USE_PROXY
    ? `${PROXY_URL}/binance`
    : "https://testnet.binance.vision",
  WS_BASE: "wss://stream.testnet.binance.vision/ws",
  API_KEY: process.env.BINANCE_TESTNET_API_KEY,
  API_SECRET: process.env.BINANCE_TESTNET_SECRET,
  ENV: normalizedBinanceEnv,
  USE_PROXY,
} as const;

function assertBinanceEnv(): void {
  if (BINANCE_CONFIG.ENV !== "spot_testnet") {
    throw new Error(
      `BINANCE_ENV must be 'spot_testnet', got: '${BINANCE_CONFIG.ENV}' (raw: ${JSON.stringify(rawBinanceEnv)})`
    );
  }
}

if (!BINANCE_CONFIG.API_KEY || !BINANCE_CONFIG.API_SECRET) {
  console.warn("Binance API keys not configured");
}

if (USE_PROXY) {
  console.log(`🔄 Binance Proxy Mode: Enabled`);
  console.log(`   → Proxy URL: ${PROXY_URL}`);
  console.log(`   → Auth configured: ${!!PROXY_AUTH_SECRET}`);
} else {
  console.log(`🎯 Binance Direct Mode: Enabled`);
  console.log(`   → Endpoint: ${BINANCE_CONFIG.REST_BASE}`);
}

/**
 * Generate HMAC SHA256 signature for Binance API
 */
function generateSignature(queryString: string): string {
  if (!BINANCE_CONFIG.API_SECRET) {
    throw new Error("BINANCE_TESTNET_SECRET not configured");
  }
  return crypto
    .createHmac("sha256", BINANCE_CONFIG.API_SECRET)
    .update(queryString)
    .digest("hex");
}

/**
 * Make signed request to Binance API
 */
async function signedRequest(
  endpoint: string,
  params: Record<string, any> = {},
  method: "GET" | "POST" | "DELETE" = "GET"
): Promise<any> {
  assertBinanceEnv();

  if (!BINANCE_CONFIG.API_KEY) {
    throw new Error("BINANCE_TESTNET_API_KEY not configured");
  }

  // Add timestamp
  const timestamp = Date.now();
  const queryParams = {
    ...params,
    timestamp,
  };

  // Create query string
  const queryString = Object.entries(queryParams)
    .map(([key, value]) => `${key}=${encodeURIComponent(String(value))}`)
    .join("&");

  // Generate signature
  const signature = generateSignature(queryString);
  const signedQuery = `${queryString}&signature=${signature}`;

  // Make request
  const url = `${BINANCE_CONFIG.REST_BASE}${endpoint}?${signedQuery}`;

  // Prepare headers
  const headers: Record<string, string> = USE_PROXY
    ? {
        Authorization: `Bearer ${PROXY_AUTH_SECRET}`,
      }
    : {
        "X-MBX-APIKEY": BINANCE_CONFIG.API_KEY,
      };

  const response = await fetch(url, {
    method,
    headers,
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Binance API error: ${response.status} - ${error}`);
  }

  return response.json();
}

/**
 * Make public (unsigned) request to Binance API
 */
async function publicRequest(
  endpoint: string,
  params: Record<string, any> = {}
): Promise<any> {
  const queryString = Object.entries(params)
    .map(([key, value]) => `${key}=${encodeURIComponent(String(value))}`)
    .join("&");

  const url = `${BINANCE_CONFIG.REST_BASE}${endpoint}${
    queryString ? `?${queryString}` : ""
  }`;

  // Prepare headers for proxy if needed
  const headers: Record<string, string> = USE_PROXY
    ? { Authorization: `Bearer ${PROXY_AUTH_SECRET}` }
    : {};

  const response = await fetch(url, { headers });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Binance API error: ${response.status} - ${error}`);
  }

  return response.json();
}

// ============================================================================
// PUBLIC API (Market Data)
// ============================================================================

/**
 * Get current price for a symbol
 */
export async function getPrice(symbol: string = "BTCUSDT"): Promise<{
  symbol: string;
  price: string;
}> {
  return publicRequest("/api/v3/ticker/price", { symbol });
}

/**
 * Get 24hr ticker statistics
 */
export async function get24hrTicker(symbol: string = "BTCUSDT") {
  return publicRequest("/api/v3/ticker/24hr", { symbol });
}

/**
 * Get order book depth
 */
export async function getOrderBook(
  symbol: string = "BTCUSDT",
  limit: number = 100
) {
  return publicRequest("/api/v3/depth", { symbol, limit });
}

/**
 * Get recent trades
 */
export async function getRecentTrades(
  symbol: string = "BTCUSDT",
  limit: number = 500
) {
  return publicRequest("/api/v3/trades", { symbol, limit });
}

/**
 * Get klines/candlestick data
 */
export async function getKlines(
  symbol: string = "BTCUSDT",
  interval: "1m" | "5m" | "15m" | "1h" | "4h" | "1d" = "1m",
  limit: number = 500
) {
  return publicRequest("/api/v3/klines", { symbol, interval, limit });
}

// ============================================================================
// SIGNED API (Account & Trading)
// ============================================================================

/**
 * Get account information (balances, etc)
 */
export async function getAccountInfo() {
  return signedRequest("/api/v3/account");
}

/**
 * Get account balance for specific asset
 */
export async function getBalance(asset: string = "USDT") {
  const account = await getAccountInfo();
  const balance = account.balances.find((b: any) => b.asset === asset);
  return balance || { asset, free: "0", locked: "0" };
}

/**
 * Get all open orders
 */
export async function getOpenOrders(symbol?: string) {
  const params = symbol ? { symbol } : {};
  return signedRequest("/api/v3/openOrders", params);
}

/**
 * Get order status
 */
export async function getOrder(symbol: string, orderId: number) {
  return signedRequest("/api/v3/order", { symbol, orderId });
}

/**
 * Place new order
 */
export async function placeOrder(params: {
  symbol: string;
  side: "BUY" | "SELL";
  type: "LIMIT" | "MARKET";
  quantity: number;
  price?: number;
  timeInForce?: "GTC" | "IOC" | "FOK";
}) {
  const orderParams: any = {
    symbol: params.symbol,
    side: params.side,
    type: params.type,
    quantity: params.quantity,
  };

  if (params.type === "LIMIT") {
    if (!params.price) {
      throw new Error("Price required for LIMIT orders");
    }
    orderParams.price = params.price;
    orderParams.timeInForce = params.timeInForce || "GTC";
  }

  return signedRequest("/api/v3/order", orderParams, "POST");
}

/**
 * Cancel an order
 */
export async function cancelOrder(symbol: string, orderId: number) {
  return signedRequest("/api/v3/order", { symbol, orderId }, "DELETE");
}

/**
 * Cancel all open orders for a symbol
 */
export async function cancelAllOrders(symbol: string) {
  return signedRequest("/api/v3/openOrders", { symbol }, "DELETE");
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

/**
 * Test connectivity
 */
export async function ping(): Promise<boolean> {
  try {
    await publicRequest("/api/v3/ping");
    return true;
  } catch {
    return false;
  }
}

/**
 * Get server time
 */
export async function getServerTime() {
  return publicRequest("/api/v3/time");
}

/**
 * Get exchange info (trading rules, etc)
 */
export async function getExchangeInfo() {
  return publicRequest("/api/v3/exchangeInfo");
}

/**
 * Format price to Binance precision
 */
export function formatPrice(price: number, decimals: number = 2): string {
  return price.toFixed(decimals);
}

/**
 * Format quantity to Binance precision
 */
export function formatQuantity(quantity: number, decimals: number = 6): string {
  return quantity.toFixed(decimals);
}
