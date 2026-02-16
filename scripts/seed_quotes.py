import time
import httpx

BASE = "http://localhost:8000"


def post_quote(symbol: str, last: float):
    body = {
        "symbol": symbol,
        "bid": None,
        "ask": None,
        "last": last,
        "venue": "DEMO",
        "timestamp_ms": int(time.time() * 1000),
    }
    r = httpx.post(f"{BASE}/api/prices", json=body, timeout=5)
    r.raise_for_status()
    print("posted", symbol, last)


if __name__ == "__main__":
    for i in range(5):
        post_quote("GGAL", 200 + i)
        time.sleep(0.5)
