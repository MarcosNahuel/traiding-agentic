import urllib.request
import json

BASE = "http://localhost:3000"

def api(method, path, data=None):
    url = BASE + path
    headers = {"Content-Type": "application/json"}
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())

def trade(label, type_, symbol, qty, reasoning):
    print(f"\n{'='*60}")
    print(f"  {label}: {type_.upper()} {qty} {symbol}")
    print(f"{'='*60}")

    # Create proposal
    prop = api("POST", "/api/trades/proposals", {
        "type": type_, "symbol": symbol, "quantity": qty,
        "orderType": "MARKET", "reasoning": reasoning
    })

    p = prop.get("proposal", {})
    pid = p.get("id")
    status = p.get("status")
    print(f"  Proposal: {pid}")
    print(f"  Status:   {status}")

    if status == "rejected":
        print(f"  ❌ Rejected: {p.get('error_message')}")
        return None

    if status == "validated":
        # Approve it
        approve = api("PATCH", f"/api/trades/proposals/{pid}", {"action": "approve", "notes": "Test approval"})
        print(f"  Approved: {approve.get('status')}")

    # Execute
    exec_r = api("POST", "/api/trades/execute", {"proposalId": pid})
    if exec_r.get("success"):
        e = exec_r.get("execution", {})
        print(f"  ✅ EXECUTED!")
        print(f"     Order ID: {e.get('orderId')}")
        print(f"     Price:    ${e.get('executedPrice')}")
        print(f"     Qty:      {e.get('executedQuantity')}")
        return e
    else:
        print(f"  ❌ Execute failed: {exec_r.get('error')}")
        return None

# === TEST ALL FEATURES ===
print("\n🚀 TRADING SYSTEM - FULL TEST SUITE")
print("="*60)

# Trade 3: BUY BTC
t3 = trade("TRADE 3", "buy", "BTCUSDT", 0.002, "Test 3: BUY BTC - enter position")

# Trade 4: BUY ETH
t4 = trade("TRADE 4", "buy", "ETHUSDT", 0.01, "Test 4: BUY ETH - diversification")

# Trade 5: BUY BNB
t5 = trade("TRADE 5", "buy", "BNBUSDT", 0.01, "Test 5: BUY BNB - third asset")

# Check portfolio
print("\n" + "="*60)
print("📊 PORTFOLIO AFTER TRADES")
print("="*60)
portfolio = api("GET", "/api/portfolio")
bal = portfolio.get("balance", {})
pos = portfolio.get("positions", {})
perf = portfolio.get("performance", {})
pnl = portfolio.get("pnl", {})

print(f"  USDT Balance:    ${bal.get('available', 0):.2f}")
print(f"  Total Portfolio: ${bal.get('total', 0):.2f}")
print(f"  In Positions:    ${bal.get('inPositions', 0):.2f}")
print(f"  Open Positions:  {pos.get('openCount', 0)}")
print(f"  Total Unrealized PnL: ${pos.get('totalUnrealizedPnL', 0):.4f}")
print(f"\n  📈 Performance:")
print(f"     Total Trades: {perf.get('totalTrades', 0)}")
print(f"     Win Rate:     {perf.get('winRate', 0)}%")
print(f"     Daily PnL:    ${pnl.get('daily', {}).get('total', 0):.4f}")
print(f"     All-Time PnL: ${pnl.get('allTime', {}).get('total', 0):.4f}")

print(f"\n  Open Positions:")
for p in pos.get("open", []):
    upnl = p.get("unrealized_pnl", 0)
    upnlp = p.get("unrealized_pnl_percent", 0)
    symbol = "📈" if upnl >= 0 else "📉"
    print(f"    {symbol} {p.get('side','').upper()} {p.get('entry_quantity')} {p.get('symbol')} @ ${p.get('entry_price')} | uPnL: ${upnl:.4f} ({upnlp:.2f}%)")

# Check DB
print("\n" + "="*60)
print("🗄️  DATABASE CHECK - PROPOSALS")
print("="*60)
props = api("GET", "/api/trades/proposals?limit=10")
proposals = props.get("proposals", [])
print(f"  Total proposals in DB: {props.get('total', len(proposals))}")
for p in proposals[:6]:
    icon = "✅" if p["status"] == "executed" else ("❌" if p["status"] == "rejected" else "⏳")
    print(f"  {icon} [{p['status']}] {p['type'].upper()} {p['quantity']} {p['symbol']} @ ${p['price']:.2f}")

# Check Risk Events
print("\n" + "="*60)
print("⚠️  RISK EVENTS")
print("="*60)
risk = api("GET", "/api/risk-events")
events = risk.get("events", [])
print(f"  Total risk events: {len(events)}")
for e in events[:5]:
    sev = {"critical": "🔴", "warning": "🟡", "info": "🟢"}.get(e.get("severity"), "⚪")
    print(f"  {sev} [{e.get('event_type')}] {e.get('message','')[:60]}")

# Check Diagnostic
print("\n" + "="*60)
print("🔍 SYSTEM DIAGNOSTIC")
print("="*60)
diag = api("GET", "/api/diagnostic")
if "error" not in diag:
    print(f"  Supabase: {'✅' if diag.get('supabase') else '❌'}")
    print(f"  Binance:  {'✅' if diag.get('binance') else '❌'}")
    print(f"  Config:   {'✅' if diag.get('config') else '❌'}")
else:
    print(f"  Error: {diag}")

print("\n" + "="*60)
print("✅ TEST SUITE COMPLETE!")
print("="*60)
