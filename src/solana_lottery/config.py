from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    rpc_url: str

    @staticmethod
    def from_env(rpc_url_override: str | None = None) -> "Settings":
        load_dotenv()

        # If user provides --rpc-url, trust it.
        if rpc_url_override:
            return Settings(rpc_url=rpc_url_override)

        # Otherwise, use RPC_URL from env if present, else build helius url from key.
        env_rpc = os.getenv("RPC_URL", "").strip()
        if env_rpc:
            return Settings(rpc_url=env_rpc)

        helius_key = os.getenv("HELIUS_API_KEY", "").strip()
        if not helius_key:
            raise RuntimeError(
                "Missing HELIUS_API_KEY (or RPC_URL). Put it in .env or export it."
            )

        return Settings(rpc_url=f"https://mainnet.helius-rpc.com/?api-key={helius_key}")
