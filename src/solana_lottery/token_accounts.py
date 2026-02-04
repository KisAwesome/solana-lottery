from __future__ import annotations

import base64
import struct
from collections import defaultdict
from typing import Dict, Iterable, List, Set, Tuple

import base58

TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022_PROGRAM_ID = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"


def parse_owner_and_amount(account_data: bytes) -> Tuple[str, int] | None:
    """
    Standard token account layout (works for classic; Token-2022 typically keeps these offsets too).
    Mint(0-32) | Owner(32-64) | Amount(64-72)
    """
    if len(account_data) < 72:
        return None

    owner_bytes = account_data[32:64]
    amount_bytes = account_data[64:72]
    owner = base58.b58encode(owner_bytes).decode("ascii")
    amount = struct.unpack("<Q", amount_bytes)[0]
    return owner, amount


def aggregate_holders_from_b64(b64_items: Iterable[str]) -> Dict[str, int]:
    balances: Dict[str, int] = defaultdict(int)

    for b64_str in b64_items:
        try:
            raw = base64.b64decode(b64_str)
        except Exception:
            continue

        parsed = parse_owner_and_amount(raw)
        if not parsed:
            continue

        owner, amount = parsed
        if amount > 0:
            balances[owner] += int(amount)

    return dict(balances)


def apply_exclusions_and_min(
    owner_to_balance: Dict[str, int],
    excluded: Set[str],
    min_raw_balance: int,
) -> List[Tuple[str, int]]:
    eligible: List[Tuple[str, int]] = []
    for addr, bal in owner_to_balance.items():
        if addr in excluded:
            continue
        if bal < min_raw_balance:
            continue
        eligible.append((addr, int(bal)))

    # Deterministic ordering (critical for reproducibility)
    eligible.sort(key=lambda x: x[0])
    return eligible


def load_excluded_wallets(path: str | None) -> Set[str]:
    if not path:
        return set()
    out: Set[str] = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            w = line.strip()
            if not w or w.startswith("#"):
                continue
            out.add(w)
    return out
