from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

import time
from datetime import datetime, timedelta, timezone

from .config import Settings
from .rpc import RpcClient, load_seed_from_block_feed_file
from .token_accounts import (
    TOKEN_PROGRAM_ID,
    TOKEN_2022_PROGRAM_ID,
    aggregate_holders_from_b64,
    apply_exclusions_and_min,
    load_excluded_wallets,
)
from .draw import build_ranges, compute_ticket, find_winner, to_tokens
from .verify import verify_audit

from .project_constants import (
    TOKEN_MINT,
    MIN_RAW_BALANCE,
    EXCLUDED_WALLETS_FILE,
)


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def cmd_draw(args: argparse.Namespace) -> int:
    settings = Settings.from_env(rpc_url_override=args.rpc_url)
    log = logging.getLogger("draw")

    excluded = load_excluded_wallets(EXCLUDED_WALLETS_FILE)

    # Seed source
    if args.block_feed_file:
        seed = load_seed_from_block_feed_file(args.block_feed_file, slot_hint=args.slot)
        seed_source = f"file:{args.block_feed_file}"
    else:
        rpc = RpcClient(settings.rpc_url, timeout_s=args.timeout)
        try:
            seed = rpc.get_blockhash_for_slot(args.slot)
            seed_source = "rpc:getBlock"
        finally:
            rpc.close()

    log.info("Seed (blockhash): %s", seed)
    log.info("Seed source      : %s", seed_source)

    rpc = RpcClient(settings.rpc_url, timeout_s=args.timeout)
    try:
        log.info("Scanning classic SPL Token program...")
        classic_b64 = rpc.get_program_accounts_base64(
            program_id=TOKEN_PROGRAM_ID,
            mint=TOKEN_MINT,
            classic_token_program=True,
        )

        log.info("Scanning Token-2022 program...")
        t22_b64 = rpc.get_program_accounts_base64(
            program_id=TOKEN_2022_PROGRAM_ID,
            mint=TOKEN_MINT,
            classic_token_program=False,
        )
    finally:
        rpc.close()

    all_b64 = classic_b64 + t22_b64
    log.info("Accounts fetched  : %d", len(all_b64))

    owner_to_balance = aggregate_holders_from_b64(all_b64)
    log.info("Unique owners     : %d", len(owner_to_balance))

    eligible = apply_exclusions_and_min(
        owner_to_balance=owner_to_balance,
        excluded=excluded,
        min_raw_balance=MIN_RAW_BALANCE,
    )

    ranges, total_tickets = build_ranges(eligible)
    log.info("Eligible entrants : %d", len(ranges))
    log.info("Total tickets     : %d", to_tokens(total_tickets))

    if total_tickets <= 0:
        raise SystemExit("No eligible tickets. Check mint / exclusions / min balance.")

    ticket, seed_hash_hex, seed_int = compute_ticket(seed, total_tickets)
    winner = find_winner(ranges, ticket)

    # Audit output (this is what makes it “trustless”)
    audit: Dict[str, Any] = {
        "metadata": {
            "tool": "solana-verifiable-lottery",
            "version": "1.0.0",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "rpc_url_redacted": "(set via env/cli; not embedded)",
            "token_mint": TOKEN_MINT,
            "target_slot": args.slot,
            "seed_blockhash": seed,
            "seed_source": seed_source,
            "seed_hash_hex": seed_hash_hex,
            "seed_int": str(seed_int),  # big int; store as string for safety
            "min_raw_balance": MIN_RAW_BALANCE,
            "excluded_wallets_file": EXCLUDED_WALLETS_FILE,
            "total_supply": total_tickets,
            "winning_ticket": ticket,
        },
        "winner": {
            "address": winner.address,
            "balance": winner.balance,
        },
        # Store entrants in deterministic order with ranges so anyone can re-run.
        "all_entrants": [
            {
                "address": r.address,
                "balance": r.balance,
                "start_ticket": r.start_ticket,
                "end_ticket": r.end_ticket,
            }
            for r in ranges
        ],
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(audit, f, indent=2)

    print("========================================")
    print("🔒 VERIFIABLE SOLANA LOTTERY DRAW")
    print("========================================")
    print(f"Mint          : {TOKEN_MINT}")
    print(f"Block number          : {args.slot}")
    print(f"Seed          : {seed}")
    print(f"Seed SHA-256   : {seed_hash_hex}")
    print("----------------------------------------")
    print("🏆 WINNER")
    print(f"Address       : {winner.address}")
    print(f"Balance       : {to_tokens(winner.balance)}")
    print(f"Winning $Ticket: {to_tokens(ticket)}")
    print("----------------------------------------")
    print(f"🧾 Wrote audit: {args.out}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    result = verify_audit(args.audit)
    print("✅ AUDIT VERIFIED")
    print(f"Winner        : {result['winner']}")
    print(f"Winning Ticket: {to_tokens(result['winning_ticket'])}")
    print(f"Total Tickets : {to_tokens(result['total_tickets'])}")
    print(f"Seed SHA-256   : {result['seed_hash_hex']}")
    return 0


def cmd_predict(args: argparse.Namespace) -> int:
    """Calculates the estimated slot for a given time today."""
    settings = Settings.from_env(rpc_url_override=args.rpc_url)
    rpc = RpcClient(settings.rpc_url, timeout_s=args.timeout)

    try:
        # 1. Get current network state
        curr_slot = rpc.get_slot()  # Use your existing RpcClient slot method
        # Note: You might need to add get_slot and get_block_time to your RpcClient class
        curr_time = rpc.get_block_time(curr_slot)

        # 2. Parse target time (HH:MM)
        target_h, target_m = map(int, args.time.split(":"))
        now = datetime.now()
        target_dt = now.replace(hour=target_h, minute=target_m, second=0, microsecond=0)

        # If the time already passed, assume tomorrow
        if target_dt.timestamp() < time.time():
            target_dt += timedelta(days=1)

        # 3. Calculate distance
        seconds_to_wait = target_dt.timestamp() - curr_time
        # Solana target: 400ms per slot
        estimated_slots = int(seconds_to_wait / 0.4)
        target_slot = curr_slot + estimated_slots

        print("--- SLOT PREDICTION ---")
        print(f"Target Time   : {target_dt.strftime('%Y-%m-%d %H:%M:%S')} local")
        print(
            f"Target Time (UTC)   : {target_dt.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
        )
        print(f"Current Slot  : {curr_slot}")
        print(f"Projected Slot: {target_slot}")
        print(f"Assumed Slot Time  : 400 ms (heuristic)")
        print("-" * 23)
        print(f'PUBLIC ANNOUNCEMENT:\n"Draw slot is {target_slot}"')

    finally:
        rpc.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="solana-lottery",
        description="Verifiable Solana token-holder lottery tool.",
    )
    p.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    p.add_argument("--rpc-url", default=None, help="Override RPC URL (else use env).")
    p.add_argument("--timeout", type=float, default=60.0, help="RPC timeout seconds.")

    sub = p.add_subparsers(dest="cmd", required=True)

    pred = sub.add_parser(
        "predict", help="Calculate a future slot for a specific time."
    )
    pred.add_argument(
        "--time", required=True, help="Target time in 24h format (e.g. 22:00)"
    )
    pred.set_defaults(func=cmd_predict)

    d = sub.add_parser("draw", help="Run the draw and write an audit JSON.")
    d.add_argument("--slot", required=True, type=int, help="Finalized target slot.")

    d.add_argument(
        "--block-feed-file",
        default=None,
        help=(
            "Path to a block feed file to source the seed (blockhash). "
            "Can be raw string or JSON containing blockhash."
        ),
    )
    d.add_argument("--out", default="audit.json", help="Audit output JSON path.")
    d.set_defaults(func=cmd_draw)

    v = sub.add_parser(
        "verify", help="Verify an existing audit.json deterministically."
    )
    v.add_argument("--audit", required=True, help="Path to audit.json.")
    v.set_defaults(func=cmd_verify)

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    setup_logging(args.verbose)
    raise SystemExit(args.func(args))
