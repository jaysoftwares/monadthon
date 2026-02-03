"""
CLAW ARENA - Contract Deployer

Deploys ArenaEscrow contracts on Monad blockchain.
Used by the autonomous agent to create real tournaments.

This module:
- Connects to Monad RPC
- Deploys ArenaEscrow contracts via ArenaFactory
- Returns deployed contract addresses
"""

import os
import logging
from typing import Optional
from eth_account import Account
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger('contract_deployer')

# Network Configuration
NETWORK_CONFIG = {
    'testnet': {
        'chain_id': 10143,
        'rpc_url': os.environ.get('TESTNET_RPC_URL', 'https://testnet-rpc.monad.xyz'),
        'factory_address': os.environ.get('TESTNET_ARENA_FACTORY_ADDRESS', ''),
    },
    'mainnet': {
        'chain_id': 143,
        'rpc_url': os.environ.get('MAINNET_RPC_URL', 'https://rpc.monad.xyz'),
        'factory_address': os.environ.get('MAINNET_ARENA_FACTORY_ADDRESS', ''),
    }
}

# ArenaFactory ABI (minimal - just createArena function)
ARENA_FACTORY_ABI = [
    {
        "inputs": [
            {"name": "_entryFee", "type": "uint256"},
            {"name": "_maxPlayers", "type": "uint256"},
            {"name": "_protocolFeeBps", "type": "uint256"},
            {"name": "_treasury", "type": "address"}
        ],
        "name": "createArena",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getArenas",
        "outputs": [{"name": "", "type": "address[]"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "operatorSigner",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    }
]


class ContractDeployer:
    """Handles smart contract deployment on Monad"""

    def __init__(self, network: str = 'testnet'):
        self.network = network
        self.config = NETWORK_CONFIG.get(network, NETWORK_CONFIG['testnet'])
        self.w3: Optional[Web3] = None
        self.account: Optional[Account] = None
        self.factory_contract = None

    def connect(self, private_key: str) -> bool:
        """Connect to Monad RPC and set up account"""
        try:
            self.w3 = Web3(Web3.HTTPProvider(self.config['rpc_url']))

            if not self.w3.is_connected():
                logger.error(f"Failed to connect to {self.config['rpc_url']}")
                return False

            # Set up account
            self.account = Account.from_key(private_key)
            logger.info(f"Connected to {self.network}")
            logger.info(f"Operator: {self.account.address}")
            logger.info(f"Chain ID: {self.w3.eth.chain_id}")

            # Set up factory contract
            if self.config['factory_address']:
                self.factory_contract = self.w3.eth.contract(
                    address=Web3.to_checksum_address(self.config['factory_address']),
                    abi=ARENA_FACTORY_ABI
                )
                logger.info(f"Factory: {self.config['factory_address']}")
            else:
                logger.warning("Factory address not configured")

            return True

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    def get_balance(self) -> int:
        """Get operator wallet balance in wei"""
        if not self.w3 or not self.account:
            return 0
        return self.w3.eth.get_balance(self.account.address)

    def get_balance_mon(self) -> float:
        """Get operator wallet balance in MON"""
        return self.get_balance() / 1e18

    async def deploy_arena(
        self,
        entry_fee_wei: int,
        max_players: int,
        protocol_fee_bps: int,
        treasury_address: str
    ) -> Optional[str]:
        """
        Deploy a new ArenaEscrow contract via ArenaFactory.

        Returns the deployed arena contract address, or None on failure.
        """
        if not self.w3 or not self.account or not self.factory_contract:
            logger.error("Not connected or factory not configured")
            return None

        try:
            # Build transaction
            treasury = Web3.to_checksum_address(treasury_address)

            tx = self.factory_contract.functions.createArena(
                entry_fee_wei,
                max_players,
                protocol_fee_bps,
                treasury
            ).build_transaction({
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gas': 3000000,  # Estimate
                'gasPrice': self.w3.eth.gas_price,
                'chainId': self.config['chain_id']
            })

            # Sign and send
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.account.key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

            logger.info(f"Transaction sent: {tx_hash.hex()}")

            # Wait for receipt
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt['status'] == 1:
                # Get arena address from logs or return value
                # For now, get latest arena from factory
                arenas = self.factory_contract.functions.getArenas().call()
                if arenas:
                    arena_address = arenas[-1]
                    logger.info(f"Arena deployed: {arena_address}")
                    return arena_address
                else:
                    logger.error("Could not find deployed arena address")
                    return None
            else:
                logger.error(f"Transaction failed: {receipt}")
                return None

        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            return None

    def get_deployed_arenas(self) -> list:
        """Get all arenas deployed via the factory"""
        if not self.factory_contract:
            return []
        try:
            return self.factory_contract.functions.getArenas().call()
        except Exception as e:
            logger.error(f"Failed to get arenas: {e}")
            return []

    def get_operator_signer(self) -> Optional[str]:
        """Get the operator signer address from factory"""
        if not self.factory_contract:
            return None
        try:
            return self.factory_contract.functions.operatorSigner().call()
        except Exception as e:
            logger.error(f"Failed to get operator signer: {e}")
            return None


# CLI for testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Contract Deployer CLI")
    parser.add_argument("--network", default="testnet", choices=["testnet", "mainnet"])
    parser.add_argument("--check", action="store_true", help="Check connection and balance")
    args = parser.parse_args()

    deployer = ContractDeployer(args.network)

    private_key = os.environ.get('OPERATOR_PRIVATE_KEY')
    if not private_key:
        print("Error: OPERATOR_PRIVATE_KEY not set")
        exit(1)

    if deployer.connect(private_key):
        print(f"Balance: {deployer.get_balance_mon():.4f} MON")
        print(f"Operator Signer: {deployer.get_operator_signer()}")
        print(f"Deployed Arenas: {len(deployer.get_deployed_arenas())}")
    else:
        print("Failed to connect")
