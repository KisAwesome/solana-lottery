from __future__ import annotations

import json
from typing import Any, Dict

from .draw import build_ranges, compute_ticket, find_winner


def verify_audit(audit_path: str) -> Dict[str, Any]:
    audit = json.load(open(audit_path, "r", encoding="utf-8"))

    meta = audit["metadata"]
    seed = meta["seed_blockhash"]
    total_supply = int(meta["total_supply"])
    winning_ticket_expected = int(meta["winning_ticket"])

    entrants = audit["all_entrants"]
    # Recreate eligible list from stored entrants (deterministic)
    eligible = [(e["address"], int(e["balance"])) for e in entrants]

    ranges, total2 = build_ranges(eligible)
    if total2 != total_supply:
        raise RuntimeError(
            f"Total supply mismatch: audit={total_supply} recomputed={total2}"
        )

    ticket, seed_hash_hex, seed_int = compute_ticket(seed, total_supply)
    if ticket != winning_ticket_expected:
        raise RuntimeError(
            f"Winning ticket mismatch: audit={winning_ticket_expected} recomputed={ticket}"
        )

    winner = find_winner(ranges, ticket)
    winner_expected = audit["winner"]["address"]
    if winner.address != winner_expected:
        raise RuntimeError(
            f"Winner mismatch: audit={winner_expected} recomputed={winner.address}"
        )

    return {
        "ok": True,
        "seed_hash_hex": seed_hash_hex,
        "seed_int": seed_int,
        "winner": winner.address,
        "winning_ticket": ticket,
        "total_tickets": total_supply,
    }
