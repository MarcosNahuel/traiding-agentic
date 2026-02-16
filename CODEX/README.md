# Frontend Development Guide - Trading Agentic System

**Generated for:** Codex (Frontend AI Developer)  
**Date:** February 16, 2026  
**Backend Status:** Complete & Production Ready

---

## Project Overview

**Stack:**
- Next.js 16 (App Router) with Turbopack
- TypeScript 5.7 (strict mode)
- Tailwind CSS 4.0
- SWR for data fetching
- Supabase Postgres
- Vercel Pro deployment

**Backend:** 13+ API endpoints fully operational

---

## Key API Endpoints

### Trading

- `GET /api/portfolio` - Current portfolio state
- `GET /api/portfolio/history` - Trade history with pagination
- `GET /api/trades/proposals` - List proposals (supports ?status= filter)
- `POST /api/trades/proposals` - Create new proposal
- `PATCH /api/trades/proposals/:id` - Approve/reject
- `POST /api/trades/execute` - Execute approved trades
- `GET /api/risk-events` - List risk events (supports ?severity= filter)

### Research

- `GET /api/sources` - List research sources
- `POST /api/sources` - Add new source
- `GET /api/strategies` - List extracted strategies
- `GET /api/guides` - List synthesized guides

---

## TypeScript Types

All types in `lib/types/api.ts`:

```typescript
import type {
  TradeProposal,
  Position,
  RiskEvent,
  PortfolioResponse,
  TradeProposalsResponse,
  RiskEventsResponse,
  CreateProposalRequest,
  ApproveProposalRequest,
} from "@/lib/types/api";
```

---

## Existing Components

1. **AppShell** (`components/ui/AppShell.tsx`) - Layout wrapper with navigation
2. **StatusBadge** (`components/ui/StatusBadge.tsx`) - Status indicators
3. **EmptyState** (`components/ui/EmptyState.tsx`) - Empty state display

---

## Pages Status

All pages implemented:
- `/` - Home dashboard
- `/portfolio` - Portfolio dashboard (auto-refresh 30s)
- `/trades` - Trade management (auto-refresh 15s)
- `/sources` - Research sources
- `/sources/new` - Add source
- `/strategies` - Strategies explorer
- `/guides` - Guides viewer
- `/chat` - Chat interface (UI ready)
- `/logs` - System logs

---

## Data Fetching Pattern

Use SWR for all API calls:

```typescript
import useSWR from "swr";

const fetcher = (url: string) => fetch(url).then(r => r.json());

const { data, error, mutate } = useSWR("/api/endpoint", fetcher, {
  refreshInterval: 30000, // Optional auto-refresh
});
```

---

## Styling Guide

**Tailwind Classes:**

- Primary button: `rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700`
- Card: `rounded-lg bg-white p-6 shadow`
- Input: `rounded-lg border border-gray-300 px-3 py-2`
- Success badge: `bg-green-100 text-green-800`
- Error badge: `bg-red-100 text-red-800`

**Colors:**
- Buy/Success: green-600
- Sell/Danger: red-600
- Primary action: blue-600
- Background: gray-50
- Cards: white

---

## Important Rules

1. **Auto-Approval:** Trades < $100 are auto-approved
2. **Refresh Intervals:**
   - Portfolio: 30s
   - Trades: 15s
   - Sources: 10s
3. **Error Handling:** Always show user-friendly error messages
4. **Loading States:** Show loading indicator while fetching

---

## Example Request Patterns

**Create Trade Proposal:**
```typescript
await fetch("/api/trades/proposals", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    type: "buy",
    symbol: "BTCUSDT",
    quantity: 0.001,
    orderType: "MARKET",
    reasoning: "Market analysis"
  })
});
```

**Approve Proposal:**
```typescript
await fetch(`/api/trades/proposals/${id}`, {
  method: "PATCH",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ action: "approve" })
});
```

---

## Deployment

- **URL:** https://traiding-agentic.vercel.app
- **Auto-deploy:** On push to master
- **Cron:** Trading loop runs every 5 minutes

---

## Next Steps for Codex

1. Review existing pages in `/portfolio` and `/trades` for patterns
2. Use TypeScript types from `lib/types/api.ts`
3. Follow SWR data fetching pattern
4. Use existing UI components (AppShell, StatusBadge, EmptyState)
5. Implement any missing features or enhancements

---

**Status:** Backend Complete ✅ | Ready for Frontend Enhancements 🎨
