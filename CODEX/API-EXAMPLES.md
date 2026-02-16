# API Usage Examples

Quick reference for common API operations.

---

## Portfolio Data

### Get Current Portfolio

```typescript
const { data } = useSWR("/api/portfolio", fetcher, {
  refreshInterval: 30000
});

// Returns: PortfolioResponse
// - balance: { total, available, locked, inPositions }
// - positions: { open[], openCount, totalValue, totalUnrealizedPnL }
// - pnl: { daily, allTime }
// - performance: { totalTrades, winRate, avgWin, avgLoss }
// - risk: { currentDrawdown, maxDrawdown, unresolvedRiskEvents }
```

### Get Trade History

```typescript
const { data } = useSWR(
  "/api/portfolio/history?limit=50&offset=0",
  fetcher
);

// Returns: PositionsHistoryResponse
// - positions: Position[]
// - summary: { totalPnL, avgPnL, winRate, bestTrade, worstTrade }
```

---

## Trade Proposals

### List Proposals

```typescript
// All proposals
const { data } = useSWR("/api/trades/proposals?limit=100", fetcher);

// Filter by status
const { data } = useSWR(
  "/api/trades/proposals?status=validated",
  fetcher
);

// Returns: TradeProposalsResponse
// - proposals: TradeProposal[]
// - stats: { pending, approved, rejected, executed }
```

### Create Proposal

```typescript
const proposal = {
  type: "buy",
  symbol: "BTCUSDT",
  quantity: 0.001,
  orderType: "MARKET",
  reasoning: "Technical analysis"
};

const response = await fetch("/api/trades/proposals", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(proposal)
});

const result = await response.json();
// Returns: { message, proposal: TradeProposal }
```

### Approve/Reject Proposal

```typescript
// Approve
await fetch(`/api/trades/proposals/${proposalId}`, {
  method: "PATCH",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    action: "approve",
    notes: "Looks good"
  })
});

// Reject
await fetch(`/api/trades/proposals/${proposalId}`, {
  method: "PATCH",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    action: "reject",
    notes: "Too risky"
  })
});
```

### Execute Trade

```typescript
// Execute single proposal
await fetch("/api/trades/execute", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ proposalId: "abc123" })
});

// Execute all approved
await fetch("/api/trades/execute", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ executeAll: true })
});
```

---

## Risk Events

### List Risk Events

```typescript
// All events
const { data } = useSWR("/api/risk-events", fetcher);

// Filter by severity
const { data } = useSWR(
  "/api/risk-events?severity=critical",
  fetcher
);

// Filter by resolution status
const { data } = useSWR(
  "/api/risk-events?resolved=false",
  fetcher
);

// Returns: RiskEventsResponse
// - events: RiskEvent[]
// - summary: { total, critical, warning, info, unresolved }
```

---

## Research

### Add Source

```typescript
const source = {
  url: "https://arxiv.org/abs/1234.5678",
  sourceType: "paper"
};

await fetch("/api/sources", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(source)
});
```

### List Sources

```typescript
const { data } = useSWR("/api/sources", fetcher);
```

### List Strategies

```typescript
const { data } = useSWR("/api/strategies", fetcher);
```

### List Guides

```typescript
const { data } = useSWR("/api/guides", fetcher);
```

---

## Error Handling

```typescript
try {
  const response = await fetch("/api/endpoint", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || "Request failed");
  }

  const result = await response.json();
  alert(result.message);
  mutate(); // Refresh SWR cache
} catch (error) {
  alert(`Error: ${error}`);
}
```

---

## SWR with Error Handling

```typescript
const { data, error, mutate } = useSWR("/api/endpoint", fetcher, {
  refreshInterval: 15000,
  revalidateOnFocus: true
});

if (error) {
  return (
    <div className="rounded-lg bg-red-50 p-4 text-red-800">
      <h3 className="font-semibold">Error</h3>
      <p className="text-sm">{error.message}</p>
    </div>
  );
}

if (!data) {
  return <div>Loading...</div>;
}

return <div>{/* Render data */}</div>;
```
