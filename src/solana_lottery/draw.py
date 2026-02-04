from __future__ import annotations

import hashlib
from dataclasses import dataclass
from bisect import bisect_right
from typing import Dict, List, Tuple
from .project_constants import TOKEN_DECIMALS


@dataclass(frozen=True)
class HolderRange:
    address: str
    balance: int
    start_ticket: int
    end_ticket: int  # exclusive


def to_tokens(raw_amount: int) -> float:
    return round(raw_amount / (10**TOKEN_DECIMALS), 1)


def build_ranges(eligible: List[Tuple[str, int]]) -> Tuple[List[HolderRange], int]:
    ranges: List[HolderRange] = []
    cursor = 0
    for addr, bal in eligible:
        start = cursor
        end = cursor + bal
        ranges.append(HolderRange(addr, bal, start, end))
        cursor = end
    return ranges, cursor


def compute_ticket(seed: str, total_tickets: int) -> Tuple[int, str, int]:
    seed_hash_hex = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    seed_int = int(seed_hash_hex, 16)
    return seed_int % total_tickets, seed_hash_hex, seed_int


def find_winner(ranges: List[HolderRange], ticket: int) -> HolderRange:
    ends = [r.end_ticket for r in ranges]
    idx = bisect_right(ends, ticket)
    if idx < 0 or idx >= len(ranges):
        raise RuntimeError("Ticket out of range (unexpected).")
    return ranges[idx]
