"""
CLAW ARENA - Contract Deployer

Deploys ArenaEscrow contracts on Monad blockchain via ArenaFactory.

This module:
- Connects to Monad RPC
- Deploys ArenaEscrow contracts via ArenaFactory.createArena(...)
- Returns deployed arena contract address from ArenaCreated event
"""

import os
import logging
from typing import Optional, Dict, Any
from eth_account import Account
from web3 import Web3
from web3.exceptions import ContractLogicError, TransactionNotFound
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("contract_deployer")
logger.setLevel(logging.INFO)

# Network Configuration
NETWORK_CONFIG = {
    "testnet": {
        "chain_id": 10143,
        "rpc_url": os.environ.get("TESTNET_RPC_URL", "https://testnet-rpc.monad.xyz"),
        "factory_address": os.environ.get("TESTNET_ARENA_FACTORY_ADDRESS", ""),
    },
    "mainnet": {
        "chain_id": 143,
        "rpc_url": os.environ.get("MAINNET_RPC_URL", "https://rpc.monad.xyz"),
        "factory_address": os.environ.get("MAINNET_ARENA_FACTORY_ADDRESS", ""),
    },
}

# ArenaFactory ABI (NEW)
ARENA_FACTORY_ABI = [
    {
        "inputs": [
            {"name": "name", "type": "string"},
            {"name": "entryFee", "type": "uint256"},
            {"name": "maxPlayers", "type": "uint32"},
            {"name": "protocolFeeBps", "type": "uint16"},
            {"name": "registrationDeadline", "type": "uint64"},
        ],
        "name": "createArena",
        "outputs": [{"name": "arena", "type": "address"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "getArenas",
        "outputs": [{"name": "", "type": "address[]"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "operatorSigner",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "treasury",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "owner",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    # Event ArenaCreated(address indexed arena, string name, uint256 entryFee, uint32 maxPlayers, uint16 protocolFeeBps)
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "arena", "type": "address"},
            {"indexed": False, "name": "name", "type": "string"},
            {"indexed": False, "name": "entryFee", "type": "uint256"},
            {"indexed": False, "name": "maxPlayers", "type": "uint32"},
            {"indexed": False, "name": "protocolFeeBps", "type": "uint16"},
        ],
        "name": "ArenaCreated",
        "type": "event",
    },
]


class ContractDeployer:
    """Handles Arena deployments on Monad via ArenaFactory"""

    def __init__(self, network: str = "testnet"):
        self.network = network if network in NETWORK_CONFIG else "testnet"
        self.config = NETWORK_CONFIG[self.network]
        self.w3: Optional[Web3] = None
        self.account: Optional[Account] = None
        self.factory_contract = None

    def connect(self, private_key: str) -> bool:
        """Connect to RPC and set up account + factory contract."""
        try:
            self.w3 = Web3(Web3.HTTPProvider(self.config["rpc_url"]))

            if not self.w3.is_connected():
                logger.error(f"Failed to connect to {self.config['rpc_url']}")
                return False

            # Set up account
            self.account = Account.from_key(private_key)
            logger.info(f"Connected to {self.network}")
            logger.info(f"Operator: {self.account.address}")

            rpc_chain_id = int(self.w3.eth.chain_id)
            cfg_chain_id = int(self.config["chain_id"])
            logger.info(f"RPC Chain ID: {rpc_chain_id} | Config Chain ID: {cfg_chain_id}")

            # Hard fail if mismatch to prevent deploying on wrong chain
            if rpc_chain_id != cfg_chain_id:
                logger.error(
                    f"Chain ID mismatch! RPC={rpc_chain_id} config={cfg_chain_id}. "
                    "Fix RPC URL or NETWORK_CONFIG."
                )
                return False

            # Set up factory contract
            factory_address = self.config.get("factory_address", "").strip()
            if not factory_address:
                logger.warning("Factory address not configured")
                return False

            self.factory_contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(factory_address),
                abi=ARENA_FACTORY_ABI,
            )
            logger.info(f"Factory: {factory_address}")

            return True

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    def get_balance(self) -> int:
        """Get operator wallet balance in wei."""
        if not self.w3 or not self.account:
            return 0
        return int(self.w3.eth.get_balance(self.account.address))

    def get_balance_mon(self) -> float:
        """Get operator wallet balance in MON."""
        return self.get_balance() / 1e18

    def _build_tx_base(self) -> Dict[str, Any]:
        """Common tx fields."""
        assert self.w3 and self.account
        return {
            "from": self.account.address,
            "nonce": self.w3.eth.get_transaction_count(self.account.address),
            "gasPrice": self.w3.eth.gas_price,
            "chainId": int(self.config["chain_id"]),
        }

    def _extract_arena_from_receipt(self, receipt) -> Optional[str]:
        """Parse ArenaCreated event logs to get arena address."""
        try:
            events = self.factory_contract.events.ArenaCreated().process_receipt(receipt)
            if not events:
                return None
            # Arena address is indexed in args
            arena_addr = events[0]["args"]["arena"]
            return Web3.to_checksum_address(arena_addr)
        except Exception:
            return None

    async def deploy_arena(
        self,
        name: str,
        entry_fee_wei: int,
        max_players: int,
        protocol_fee_bps: int,
        registration_deadline: int = 0,
        gas_limit: Optional[int] = None,
    ) -> Optional[str]:
        """
        Deploy a new ArenaEscrow via ArenaFactory.createArena.

        Args:
          name: Arena name
          entry_fee_wei: entry fee in wei
          max_players: >=2
          protocol_fee_bps: <=1000 (10%)
          registration_deadline: unix seconds, or 0 for none
          gas_limit: optional manual gas

        Returns:
          deployed arena contract address, or None on failure
        """
        if not self.w3 or not self.account or not self.factory_contract:
            logger.error("Not connected or factory not configured")
            return None

        try:
            # Prepare function call (NEW signature)
            fn = self.factory_contract.functions.createArena(
                str(name),
                int(entry_fee_wei),
                int(max_players),
                int(protocol_fee_bps),
                int(registration_deadline),
            )

            tx_params = self._build_tx_base()

            # Estimate gas (safer than hardcoding)
            if gas_limit is not None:
                tx_params["gas"] = int(gas_limit)
            else:
                try:
                    estimated = fn.estimate_gas({"from": self.account.address})
                    # add buffer
                    tx_params["gas"] = int(estimated * 1.25)
                except Exception as eg:
                    logger.warning(f"Gas estimate failed ({eg}); using fallback gas=3,000,000")
                    tx_params["gas"] = 3_000_000

            # Build, sign, send
            tx = fn.build_transaction(tx_params)
            signed = self.w3.eth.account.sign_transaction(tx, self.account.key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)

            logger.info(f"createArena tx sent: {tx_hash.hex()}")

            # Wait for receipt
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)

            if int(receipt.get("status", 0)) != 1:
                logger.error(f"Deployment tx reverted. Receipt: {receipt}")
                return None

            # Parse ArenaCreated event for arena address
            arena_address = self._extract_arena_from_receipt(receipt)
            if arena_address:
                logger.info(f"Arena deployed: {arena_address}")
                return arena_address

            # Fallback: read last arena (still safe, but less ideal if concurrent deploys)
            arenas = self.factory_contract.functions.getArenas().call()
            if arenas:
                arena_address = Web3.to_checksum_address(arenas[-1])
                logger.warning(f"Arena address not found in logs; using factory.getArenas() fallback: {arena_address}")
                return arena_address

            logger.error("Deployment succeeded but no arena address could be found.")
            return None

        except ContractLogicError as e:
            # This usually contains revert reason
            logger.error(f"Deployment reverted: {e}")
            return None
        except (TransactionNotFound, TimeoutError) as e:
            logger.error(f"Transaction not confirmed in time: {e}")
            return None
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            return None

    def get_deployed_arenas(self) -> list:
        """Get all arenas deployed via the factory."""
        if not self.factory_contract:
            return []
        try:
            return self.factory_contract.functions.getArenas().call()
        except Exception as e:
            logger.error(f"Failed to get arenas: {e}")
            return []

    def get_operator_signer(self) -> Optional[str]:
        """Get operator signer address from factory."""
        if not self.factory_contract:
            return None
        try:
            return self.factory_contract.functions.operatorSigner().call()
        except Exception as e:
            logger.error(f"Failed to get operator signer: {e}")
            return None

    def get_treasury(self) -> Optional[str]:
        """Get treasury address from factory."""
        if not self.factory_contract:
            return None
        try:
            return self.factory_contract.functions.treasury().call()
        except Exception as e:
            logger.error(f"Failed to get treasury: {e}")
            return None

    def get_owner(self) -> Optional[str]:
        """Get owner address from factory."""
        if not self.factory_contract:
            return None
        try:
            return self.factory_contract.functions.owner().call()
        except Exception as e:
            logger.error(f"Failed to get owner: {e}")
            return None


# CLI for testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Contract Deployer CLI")
    parser.add_argument("--network", default="testnet", choices=["testnet", "mainnet"])
    parser.add_argument("--check", action="store_true", help="Check connection and balance")
    args = parser.parse_args()

    deployer = ContractDeployer(args.network)

    private_key = os.environ.get("OPERATOR_PRIVATE_KEY")
    if not private_key:
        print("Error: OPERATOR_PRIVATE_KEY not set")
        raise SystemExit(1)

    if deployer.connect(private_key):
        print(f"Balance: {deployer.get_balance_mon():.4f} MON")
        print(f"Factory Owner: {deployer.get_owner()}")
        print(f"Operator Signer: {deployer.get_operator_signer()}")
        print(f"Treasury: {deployer.get_treasury()}")
        print(f"Deployed Arenas: {len(deployer.get_deployed_arenas())}")
    else:
        print("Failed to connect")
