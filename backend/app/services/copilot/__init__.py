"""Claude veto co-pilot — hot-path BUY gate.

A second gate that runs after the deterministic risk gate (validate_proposal_enhanced)
and before execute_proposal. Vetoes only BUY entries. Fail-open, stateless.
See docs/superpowers/specs/2026-05-30-claude-veto-copilot-design.md
"""

