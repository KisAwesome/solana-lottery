from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
import httpx


class RpcClient:
    def __init__(self, rpc_url: str, timeout_s: float = 60.0) -> None:
        self.rpc_url = rpc_url
        self.client = httpx.Client(timeout=timeout_s)

    def close(self) -> None:
        self.client.close()

    def get_slot(self, commitment: str = "finalized") -> int:
        """Returns the current slot."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSlot",
            "params": [{"commitment": commitment}],
        }
        data = self._post(payload)
        return int(data["result"])

    def get_block_time(self, slot: int) -> int:
        """Returns the Unix timestamp for a given slot."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBlockTime",
            "params": [slot],
        }
        data = self._post(payload)
        if data.get("result") is None:
            raise RuntimeError(f"Timestamp not available for slot {slot}")
        return int(data["result"])

    def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        resp = self.client.post(self.rpc_url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"RPC error: {data['error']}")
        return data

    def get_blockhash_for_slot(self, slot: int) -> str:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBlock",
            "params": [
                slot,
                {"encoding": "json", "transactionDetails": "none", "rewards": False},
            ],
        }
        data = self._post(payload)
        result = data.get("result")
        if not result or "blockhash" not in result:
            raise RuntimeError(f"Slot {slot}: getBlock returned no blockhash.")
        return result["blockhash"]

    def get_program_accounts_base64(
        self,
        program_id: str,
        mint: str,
        classic_token_program: bool,
    ) -> List[str]:
        """
        Returns base64 strings for account data.
        Note: For classic SPL Token accounts, we enforce dataSize=165.
        Token-2022 accounts can vary due to extensions.
        """
        filters: List[Dict[str, Any]] = [{"memcmp": {"offset": 0, "bytes": mint}}]
        if classic_token_program:
            filters.append({"dataSize": 165})

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getProgramAccounts",
            "params": [
                program_id,
                {
                    "encoding": "base64",
                    "filters": filters,
                },
            ],
        }
        data = self._post(payload)
        results = data.get("result", [])
        out: List[str] = []
        for item in results:
            # item['account']['data'] is [base64_str, "base64"]
            out.append(item["account"]["data"][0])
        return out


def load_seed_from_block_feed_file(path: str, slot_hint: Optional[int] = None) -> str:
    """
    Supports:
    1) Raw blockhash string in file
    2) JSON object containing:
       - {"blockhash": "..."}
       - {"result": {"blockhash": "..."}}
       - {"slot": 123, "blockhash": "..."}   (optionally verified against slot_hint)
       - {"blocks": {"123": {"blockhash": "..."}}}  (optionally with slot_hint)
    """
    raw = open(path, "r", encoding="utf-8").read().strip()

    # If it's just a blockhash string
    if raw and raw[0] != "{":
        return raw

    try:
        j = json.loads(raw)
    except Exception as e:
        raise RuntimeError(f"Block feed file is not valid JSON or raw string: {e}")

    # Common patterns
    if isinstance(j, dict):
        if "blockhash" in j and isinstance(j["blockhash"], str):
            if (
                slot_hint is not None
                and "slot" in j
                and int(j["slot"]) != int(slot_hint)
            ):
                raise RuntimeError(
                    f"Block feed slot mismatch: file slot={j['slot']} vs expected slot={slot_hint}"
                )
            return j["blockhash"]

        if (
            "result" in j
            and isinstance(j["result"], dict)
            and isinstance(j["result"].get("blockhash"), str)
        ):
            return j["result"]["blockhash"]

        # A feed of many blocks
        if slot_hint is not None and "blocks" in j and isinstance(j["blocks"], dict):
            key = str(int(slot_hint))
            block_obj = j["blocks"].get(key)
            if isinstance(block_obj, dict) and isinstance(
                block_obj.get("blockhash"), str
            ):
                return block_obj["blockhash"]

    raise RuntimeError(
        "Could not find a blockhash in block feed file. "
        "Expected raw string or JSON with blockhash/result.blockhash/(blocks[slot].blockhash)."
    )
