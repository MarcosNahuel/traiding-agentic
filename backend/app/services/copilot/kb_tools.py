"""SDK-free implementations behind the co-pilot's @tool wrappers.

Kept import-free of claude_agent_sdk so they can be unit-tested without the SDK
and without spawning the Claude CLI. The thin @tool wrappers live in veto_tools.py.

RAG v1 = agentic filesystem search over docs/knowledge-base (~25 markdowns).
No vector DB. pgvector/Pinecone is the scale path when the corpus grows.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

# backend/app/services/copilot/kb_tools.py → parents[4] == repo root
KB_ROOT = Path(__file__).resolve().parents[4] / "docs" / "knowledge-base"

_MAX_FILE_CHARS = 8000
_MAX_RESULTS = 8


def read_kb_impl(rel_path: str, kb_root: Path = KB_ROOT) -> dict[str, Any]:
    """Read one KB doc by path relative to the KB root. Anti path-traversal."""
    try:
        root = Path(kb_root).resolve()
        target = (root / rel_path).resolve()
        try:
            target.relative_to(root)  # raises ValueError if target escapes root
        except ValueError:
            return {"ok": False, "error": "path outside KB"}
        if not target.is_file():
            return {"ok": False, "error": "not found"}
        return {
            "ok": True,
            "path": rel_path,
            "content": target.read_text(encoding="utf-8")[:_MAX_FILE_CHARS],
        }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def search_kb_impl(query: str, kb_root: Path = KB_ROOT, max_results: int = _MAX_RESULTS) -> dict[str, Any]:
    """Case-insensitive substring search over *.md in the KB. Returns path + snippet."""
    q = (query or "").lower().strip()
    if not q:
        return {"ok": True, "query": query, "results": []}
    root = Path(kb_root)
    if not root.exists():
        return {"ok": False, "error": "KB root not found", "results": []}

    results: list[dict[str, str]] = []
    for path in sorted(root.rglob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            continue
        if q in text.lower():
            snippet = ""
            for line in text.splitlines():
                if q in line.lower():
                    snippet = line.strip()[:200]
                    break
            results.append({"path": str(path.relative_to(root)), "snippet": snippet})

    return {"ok": True, "query": query, "results": results[:max_results]}


def get_recent_trades_impl(symbol: str, n: int, supabase: Any) -> dict[str, Any]:
    """Last N closed positions for a symbol (PnL, closed_at) — for veto context."""
    try:
        resp = (
            supabase.table("positions")
            .select("symbol,realized_pnl,closed_at,opened_at,entry_price")
            .eq("symbol", symbol)
            .eq("status", "closed")
            .order("closed_at", desc=True)
            .limit(int(n))
            .execute()
        )
        trades = resp.data or []
        return {"ok": True, "symbol": symbol, "count": len(trades), "trades": trades}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "trades": []}
