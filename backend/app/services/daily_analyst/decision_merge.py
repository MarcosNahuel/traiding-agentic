"""Merge audit reports, configs, and briefs by date for the daily dashboard."""

from typing import Any


def merge_decisions(
    audits: list[dict[str, Any]],
    configs: list[dict[str, Any]],
    briefs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge audit, config, and brief data by date.

    Returns list of {date, audit, config, brief} sorted newest first.
    """
    date_map: dict[str, dict[str, Any]] = {}

    for a in audits:
        d = a.get("audit_date", "")
        if not d:
            continue
        if d not in date_map:
            date_map[d] = {"date": d, "audit": None, "config": None, "brief": None}
        date_map[d]["audit"] = a

    for c in configs:
        created = c.get("created_at", "")
        d = str(created)[:10] if created else ""
        if not d:
            continue
        if d not in date_map:
            date_map[d] = {"date": d, "audit": None, "config": None, "brief": None}
        if date_map[d]["config"] is None:
            date_map[d]["config"] = c

    for b in briefs:
        d = b.get("brief_date", "")
        if not d:
            continue
        if d not in date_map:
            date_map[d] = {"date": d, "audit": None, "config": None, "brief": None}
        date_map[d]["brief"] = b

    return sorted(date_map.values(), key=lambda x: x["date"], reverse=True)
