/**
 * Market Data WebSocket Stream
 *
 * Connects to Binance WebSocket to receive real-time market data
 * and stores it in the database for strategy evaluation.
 *
 * Usage:
 *   const stream = new MarketDataStream(['BTCUSDT', 'ETHUSDT']);
 *   stream.start();
 */

import WebSocket from "ws";
import { createServerClient } from "@/lib/supabase";
import { BINANCE_CONFIG } from "@/lib/exchanges/binance-testnet";

// ============================================================================
// TYPES
// ============================================================================

interface KlineData {
  e: string; // Event type
  E: number; // Event time
  s: string; // Symbol
  k: {
    t: number; // Kline start time
    T: number; // Kline close time
    s: string; // Symbol
    i: string; // Interval
    f: number; // First trade ID
    L: number; // Last trade ID
    o: string; // Open price
    c: string; // Close price
    h: string; // High price
    l: string; // Low price
    v: string; // Base asset volume
    n: number; // Number of trades
    x: boolean; // Is this kline closed?
    q: string; // Quote asset volume
    V: string; // Taker buy base asset volume
    Q: string; // Taker buy quote asset volume
  };
}

interface TickerData {
  e: string; // Event type (24hrTicker)
  E: number; // Event time
  s: string; // Symbol
  p: string; // Price change
  P: string; // Price change percent
  w: string; // Weighted average price
  x: string; // First trade price
  c: string; // Last price
  Q: string; // Last quantity
  b: string; // Best bid price
  B: string; // Best bid quantity
  a: string; // Best ask price
  A: string; // Best ask quantity
  o: string; // Open price
  h: string; // High price
  l: string; // Low price
  v: string; // Total traded base asset volume
  q: string; // Total traded quote asset volume
  O: number; // Statistics open time
  C: number; // Statistics close time
  F: number; // First trade ID
  L: number; // Last trade ID
  n: number; // Total number of trades
}

// ============================================================================
// MARKET DATA STREAM CLASS
// ============================================================================

export class MarketDataStream {
  private ws: WebSocket | null = null;
  private symbols: string[];
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectDelay = 5000; // 5 seconds
  private isRunning = false;
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private lastMessageTime = Date.now();

  constructor(symbols: string[] = ["BTCUSDT", "ETHUSDT"]) {
    this.symbols = symbols.map((s) => s.toLowerCase());
  }

  /**
   * Start the WebSocket connection
   */
  start() {
    if (this.isRunning) {
      console.log("Market data stream is already running");
      return;
    }

    this.isRunning = true;
    this.connect();
    this.startHeartbeat();
  }

  /**
   * Stop the WebSocket connection
   */
  stop() {
    this.isRunning = false;

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }

    console.log("Market data stream stopped");
  }

  /**
   * Connect to Binance WebSocket
   */
  private connect() {
    try {
      // Create combined stream for all symbols
      // Format: wss://stream.testnet.binance.vision/stream?streams=btcusdt@kline_1m/ethusdt@kline_1m
      const streams = this.symbols
        .map((symbol) => `${symbol}@ticker`)
        .join("/");

      const wsUrl = `${BINANCE_CONFIG.WS_BASE.replace("/ws", "/stream")}?streams=${streams}`;

      console.log(`Connecting to Binance WebSocket: ${wsUrl}`);

      this.ws = new WebSocket(wsUrl);

      this.ws.on("open", () => {
        console.log("✅ WebSocket connected");
        this.reconnectAttempts = 0;
      });

      this.ws.on("message", (data: WebSocket.Data) => {
        this.handleMessage(data);
      });

      this.ws.on("error", (error: Error) => {
        console.error("WebSocket error:", error.message);
      });

      this.ws.on("close", () => {
        console.log("WebSocket disconnected");
        this.ws = null;

        // Attempt reconnection if still running
        if (this.isRunning) {
          this.attemptReconnect();
        }
      });

      this.ws.on("ping", () => {
        this.ws?.pong();
      });
    } catch (error) {
      console.error("Failed to connect to WebSocket:", error);
      if (this.isRunning) {
        this.attemptReconnect();
      }
    }
  }

  /**
   * Handle incoming WebSocket messages
   */
  private async handleMessage(data: WebSocket.Data) {
    try {
      this.lastMessageTime = Date.now();

      const message = JSON.parse(data.toString());

      // Combined stream format: { stream: "btcusdt@ticker", data: {...} }
      if (message.stream && message.data) {
        const streamData = message.data;

        if (message.stream.includes("@ticker")) {
          await this.handleTickerData(streamData as TickerData);
        } else if (message.stream.includes("@kline")) {
          await this.handleKlineData(streamData as KlineData);
        }
      }
    } catch (error) {
      console.error("Error handling WebSocket message:", error);
    }
  }

  /**
   * Handle ticker data (24h price statistics)
   */
  private async handleTickerData(ticker: TickerData) {
    const supabase = createServerClient();

    try {
      await supabase.from("market_data").insert({
        symbol: ticker.s,
        price: parseFloat(ticker.c),
        bid_price: parseFloat(ticker.b),
        ask_price: parseFloat(ticker.a),
        high_24h: parseFloat(ticker.h),
        low_24h: parseFloat(ticker.l),
        volume_24h: parseFloat(ticker.v),
        price_change_24h: parseFloat(ticker.p),
        price_change_percent_24h: parseFloat(ticker.P),
        exchange_timestamp: new Date(ticker.E).toISOString(),
      });

      // Only log every 10th update to avoid spam
      if (Math.random() < 0.1) {
        console.log(
          `${ticker.s}: $${parseFloat(ticker.c).toLocaleString()} (${parseFloat(ticker.P) > 0 ? "+" : ""}${parseFloat(ticker.P).toFixed(2)}%)`
        );
      }
    } catch (error) {
      console.error("Failed to store ticker data:", error);
    }
  }

  /**
   * Handle kline/candlestick data
   */
  private async handleKlineData(kline: KlineData) {
    // Only store closed candles
    if (!kline.k.x) return;

    console.log(
      `${kline.s} candle closed: O=${kline.k.o} H=${kline.k.h} L=${kline.k.l} C=${kline.k.c}`
    );

    // Store candle data (optional - for future backtesting)
    // You could create a separate 'candles' table for this
  }

  /**
   * Attempt to reconnect after failure
   */
  private attemptReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error(
        "Max reconnection attempts reached. Stopping market data stream."
      );
      this.stop();
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectDelay * this.reconnectAttempts;

    console.log(
      `Reconnecting in ${delay / 1000}s... (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`
    );

    setTimeout(() => {
      if (this.isRunning) {
        this.connect();
      }
    }, delay);
  }

  /**
   * Start heartbeat monitoring
   */
  private startHeartbeat() {
    this.heartbeatInterval = setInterval(() => {
      const timeSinceLastMessage = Date.now() - this.lastMessageTime;

      // If no message received in 60 seconds, reconnect
      if (timeSinceLastMessage > 60000) {
        console.warn("No messages received in 60s, reconnecting...");
        this.ws?.close();
      }
    }, 30000); // Check every 30 seconds
  }

  /**
   * Get current status
   */
  getStatus() {
    return {
      isRunning: this.isRunning,
      isConnected: this.ws?.readyState === WebSocket.OPEN,
      symbols: this.symbols,
      reconnectAttempts: this.reconnectAttempts,
      lastMessageTime: new Date(this.lastMessageTime).toISOString(),
    };
  }

  /**
   * Add symbols to watch
   */
  addSymbols(symbols: string[]) {
    const newSymbols = symbols
      .map((s) => s.toLowerCase())
      .filter((s) => !this.symbols.includes(s));

    if (newSymbols.length === 0) return;

    this.symbols.push(...newSymbols);

    // Restart connection with new symbols
    if (this.isRunning) {
      console.log(`Adding symbols: ${newSymbols.join(", ")}`);
      this.stop();
      this.start();
    }
  }

  /**
   * Remove symbols from watch
   */
  removeSymbols(symbols: string[]) {
    const symbolsToRemove = symbols.map((s) => s.toLowerCase());
    this.symbols = this.symbols.filter((s) => !symbolsToRemove.includes(s));

    // Restart connection with updated symbols
    if (this.isRunning && this.symbols.length > 0) {
      console.log(`Removing symbols: ${symbolsToRemove.join(", ")}`);
      this.stop();
      this.start();
    } else if (this.symbols.length === 0) {
      this.stop();
    }
  }
}

// ============================================================================
// SINGLETON INSTANCE
// ============================================================================

let globalStream: MarketDataStream | null = null;

/**
 * Get or create global market data stream
 */
export function getMarketDataStream(
  symbols?: string[]
): MarketDataStream {
  if (!globalStream) {
    globalStream = new MarketDataStream(symbols);
  }
  return globalStream;
}

/**
 * Start global market data stream
 */
export function startMarketDataStream(symbols?: string[]) {
  const stream = getMarketDataStream(symbols);
  stream.start();
  return stream;
}

/**
 * Stop global market data stream
 */
export function stopMarketDataStream() {
  if (globalStream) {
    globalStream.stop();
    globalStream = null;
  }
}
