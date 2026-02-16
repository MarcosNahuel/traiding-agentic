# 04 - Snippets TypeScript (listos para adaptar)

## 1) Firma HMAC para endpoints SIGNED

```ts
import crypto from 'node:crypto';

export function signQuery(query: string, apiSecret: string): string {
  return crypto.createHmac('sha256', apiSecret).update(query).digest('hex');
}

export function buildSignedQuery(
  params: Record<string, string | number>,
  apiSecret: string,
): string {
  const query = new URLSearchParams(
    Object.entries(params).map(([k, v]) => [k, String(v)]),
  ).toString();

  const signature = signQuery(query, apiSecret);
  return `${query}&signature=${signature}`;
}
```

## 2) Time sync y recvWindow guard

```ts
type ServerTimeResponse = { serverTime: number };

export async function getServerTime(baseUrl: string): Promise<number> {
  const res = await fetch(`${baseUrl}/api/v3/time`);
  if (!res.ok) throw new Error(`time error: ${res.status}`);
  const json = (await res.json()) as ServerTimeResponse;
  return json.serverTime;
}

export async function computeClockOffsetMs(baseUrl: string): Promise<number> {
  const t0 = Date.now();
  const server = await getServerTime(baseUrl);
  const t1 = Date.now();
  const rtt = t1 - t0;
  const estimatedNowAtServer = server + rtt / 2;
  return estimatedNowAtServer - Date.now();
}
```

## 3) Validacion previa por filtros de simbolo

```ts
type PriceFilter = { filterType: 'PRICE_FILTER'; minPrice: string; maxPrice: string; tickSize: string };
type LotSizeFilter = { filterType: 'LOT_SIZE'; minQty: string; maxQty: string; stepSize: string };
type MinNotionalFilter = { filterType: 'MIN_NOTIONAL'; minNotional: string };
type NotionalFilter = { filterType: 'NOTIONAL'; minNotional: string; maxNotional: string };

type SymbolFilter = PriceFilter | LotSizeFilter | MinNotionalFilter | NotionalFilter | { filterType: string };

function isStepAligned(value: number, step: number): boolean {
  const scaled = Math.round(value / step);
  return Math.abs(scaled * step - value) < 1e-12;
}

export function validateOrderByFilters(input: {
  price?: number;
  qty: number;
  filters: SymbolFilter[];
}): string[] {
  const errors: string[] = [];
  const { price, qty, filters } = input;

  for (const f of filters) {
    if (f.filterType === 'PRICE_FILTER' && price != null) {
      const min = Number(f.minPrice);
      const max = Number(f.maxPrice);
      const tick = Number(f.tickSize);
      if (price < min || price > max) errors.push('price out of PRICE_FILTER bounds');
      if (!isStepAligned(price, tick)) errors.push('price not aligned to tickSize');
    }

    if (f.filterType === 'LOT_SIZE') {
      const min = Number(f.minQty);
      const max = Number(f.maxQty);
      const step = Number(f.stepSize);
      if (qty < min || qty > max) errors.push('qty out of LOT_SIZE bounds');
      if (!isStepAligned(qty, step)) errors.push('qty not aligned to stepSize');
    }

    if (f.filterType === 'MIN_NOTIONAL' && price != null) {
      const min = Number(f.minNotional);
      if (price * qty < min) errors.push('notional below MIN_NOTIONAL');
    }

    if (f.filterType === 'NOTIONAL' && price != null) {
      const min = Number(f.minNotional);
      const max = Number(f.maxNotional);
      const notional = price * qty;
      if (notional < min) errors.push('notional below NOTIONAL.minNotional');
      if (notional > max) errors.push('notional above NOTIONAL.maxNotional');
    }
  }

  return errors;
}
```

## 4) WebSocket reconnect manager (market streams)

```ts
type MessageHandler = (raw: string) => void;

export class WsManager {
  private ws?: WebSocket;
  private retry = 0;
  private readonly maxRetry = 20;

  constructor(private readonly url: string, private readonly onMessage: MessageHandler) {}

  start() {
    this.connect();
  }

  private connect() {
    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      this.retry = 0;
      console.log('[ws] connected');
    };

    this.ws.onmessage = (evt) => this.onMessage(String(evt.data));

    this.ws.onerror = () => {
      this.ws?.close();
    };

    this.ws.onclose = () => {
      const delay = Math.min(30_000, 500 * 2 ** this.retry);
      if (this.retry < this.maxRetry) this.retry += 1;
      setTimeout(() => this.connect(), delay + Math.floor(Math.random() * 250));
    };
  }
}
```

## 5) Idempotencia de ordenes con estado desconocido

```ts
type PlaceOrderResult =
  | { status: 'ack'; orderId: string }
  | { status: 'timeout_unknown' }
  | { status: 'rejected'; reason: string };

type ExistingOrder =
  | { status: 'found'; orderId: string; state: 'NEW' | 'PARTIALLY_FILLED' | 'FILLED' | 'CANCELED' | 'REJECTED' }
  | { status: 'not_found' };

export async function placeOrderIdempotent(input: {
  clientOrderId: string;
  place: () => Promise<PlaceOrderResult>;
  findByClientOrderId: (id: string) => Promise<ExistingOrder>;
}): Promise<{ final: 'submitted' | 'already_exists' | 'failed'; detail: string }> {
  const first = await input.place();

  if (first.status === 'ack') {
    return { final: 'submitted', detail: first.orderId };
  }

  if (first.status === 'rejected') {
    return { final: 'failed', detail: first.reason };
  }

  // timeout_unknown: no reenviar ciegamente
  const existing = await input.findByClientOrderId(input.clientOrderId);
  if (existing.status === 'found') {
    return { final: 'already_exists', detail: `${existing.orderId}:${existing.state}` };
  }

  // Solo aqui evaluar retry, segun politicas de riesgo/latencia
  const second = await input.place();
  if (second.status === 'ack') return { final: 'submitted', detail: second.orderId };
  return { final: 'failed', detail: second.status === 'rejected' ? second.reason : 'timeout_unknown_after_retry' };
}
```

## 6) Keepalive de user stream (futures)

```ts
export function scheduleKeepalive(task: () => Promise<void>): NodeJS.Timeout {
  // Binance recomienda refrescar en torno a 60 min.
  // Se programa un margen conservador.
  return setInterval(async () => {
    try {
      await task();
    } catch (err) {
      console.error('[user-stream] keepalive failed', err);
    }
  }, 50 * 60 * 1000);
}
```

## 7) Guard de precio al aprobar HITL

```ts
export function isPriceStillValid(input: {
  proposedPrice: number;
  currentPrice: number;
  maxDriftBps: number;
}): boolean {
  const driftBps = Math.abs(input.currentPrice - input.proposedPrice) / input.proposedPrice * 10_000;
  return driftBps <= input.maxDriftBps;
}
```

