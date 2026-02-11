"""On-chain interactions for CLAW ARENA.

Backend DB is used for UI/game orchestration, but escrow settlement must happen
on-chain so winners are actually paid.

This module provides a minimal Web3 helper to:
- read ArenaEscrow.usedNonce
- call ArenaEscrow.finalize(...) (permissionless in the patched contract)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from web3 import Web3
from eth_account import Account


# Minimal ABI for ArenaEscrow settlement
ARENA_ESCROW_ABI = [
    {
        "type": "function",
        "name": "usedNonce",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "type": "function",
        "name": "finalize",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "winners", "type": "address[]"},
            {"name": "amounts", "type": "uint256[]"},
            {"name": "signature", "type": "bytes"},
        ],
        "outputs": [],
    },
]


@dataclass
class Network:
    chain_id: int
    rpc_url: str


class OnchainClient:
    def __init__(self, network: Network, relayer_private_key: str):
        if not relayer_private_key:
            raise ValueError("RELAYER_PRIVATE_KEY (or OPERATOR_PRIVATE_KEY fallback) is required")

        self.network = network
        self.w3 = Web3(Web3.HTTPProvider(network.rpc_url))
        if not self.w3.is_connected():
            raise RuntimeError(f"Failed to connect to RPC: {network.rpc_url}")

        self.account = Account.from_key(relayer_private_key)

    def _arena(self, arena_address: str):
        return self.w3.eth.contract(
            address=Web3.to_checksum_address(arena_address),
            abi=ARENA_ESCROW_ABI,
        )

    def get_used_nonce(self, arena_address: str) -> int:
        arena = self._arena(arena_address)
        return int(arena.functions.usedNonce().call())

    def finalize(
        self,
        arena_address: str,
        winners: List[str],
        amounts_wei: List[int],
        signature: str,
        gas: int = 1_500_000,
    ) -> str:
        """Submit ArenaEscrow.finalize. Returns tx hash hex string."""

        arena = self._arena(arena_address)

        winners_cs = [Web3.to_checksum_address(a) for a in winners]
        sig_bytes = Web3.to_bytes(hexstr=signature)

        tx = arena.functions.finalize(winners_cs, amounts_wei, sig_bytes).build_transaction(
            {
                "from": self.account.address,
                "nonce": self.w3.eth.get_transaction_count(self.account.address),
                "gas": gas,
                "gasPrice": self.w3.eth.gas_price,
                "chainId": self.network.chain_id,
            }
        )

        signed = self.w3.eth.account.sign_transaction(tx, self.account.key)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
        if receipt.get("status") != 1:
            raise RuntimeError(f"Finalize tx failed: {tx_hash.hex()}")
        return tx_hash.hex()
