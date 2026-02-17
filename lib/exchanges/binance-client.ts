/**
 * Binance Client Adapter
 *
 * Routes to Testnet or Mainnet based on TRADING_MODE env var.
 * Set TRADING_MODE=LIVE to trade with real money.
 *
 * Default: Testnet (safe)
 */

// Re-export everything from the active client
export * from "./binance-testnet";

// Future: when mainnet support is added, switch here:
// const isLive = process.env.TRADING_MODE === "LIVE";
// if (isLive) {
//   export * from "./binance-mainnet";
// } else {
//   export * from "./binance-testnet";
// }
