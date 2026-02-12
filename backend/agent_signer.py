"""
CLAW ARENA - Agent Signing Service

A simple EIP-712 signing service for tournament finalization.
This service runs alongside your backend and handles signature generation.

Usage:
    python agent_signer.py

Environment Variables:
    OPERATOR_PRIVATE_KEY - Private key for signing (required)
    AGENT_PORT - Port to run the service (default: 8002)
    CHAIN_ID - Chain ID for EIP-712 domain (default: 10143)
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import os
from eth_utils import keccak, to_checksum_address
from eth_abi.packed import encode_packed
from eth_account import Account
import logging
from dotenv import load_dotenv

load_dotenv()

# Configuration
OPERATOR_PRIVATE_KEY = os.environ.get('OPERATOR_PRIVATE_KEY', '')
AGENT_PORT = int(os.environ.get('AGENT_PORT', '8002'))
CHAIN_ID = int(os.environ.get('CHAIN_ID', '10143'))

if not OPERATOR_PRIVATE_KEY:
    raise ValueError("OPERATOR_PRIVATE_KEY environment variable is required")

# Get operator address from private key
account = Account.from_key(OPERATOR_PRIVATE_KEY)
OPERATOR_ADDRESS = account.address

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="CLAW ARENA Agent Signer", version="1.0.0")

# ============ MODELS ============

class SignFinalizeRequest(BaseModel):
    arena_address: str
    winners: List[str]
    amounts: List[str]
    nonce: int
    chain_id: int = CHAIN_ID

class SignFinalizeResponse(BaseModel):
    success: bool
    signature: str
    operator_address: str
    domain: dict
    types: dict
    message: dict

# ============ HELPERS ============

def compute_hash(items: List[str], solidity_type: str) -> str:
    """
    Compute keccak256(abi.encodePacked(...)) compatible with Solidity:
    - addresses: keccak256(abi.encodePacked(address[]))
    - uint256:   keccak256(abi.encodePacked(uint256[]))
    """
    if solidity_type == "address":
        values = [to_checksum_address(v) for v in items]
    elif solidity_type == "uint256":
        values = [int(v) for v in items]
    else:
        raise ValueError(f"Unsupported solidity_type: {solidity_type}")

    if not values:
        return "0x" + keccak(b"").hex()

    packed = encode_packed([solidity_type] * len(values), values)
    return "0x" + keccak(packed).hex()

def sign_finalize_eip712(
    arena_address: str,
    winners: List[str],
    amounts: List[str],
    nonce: int,
    chain_id: int
) -> dict:
    """Generate EIP-712 signature for finalize transaction"""

    # Compute hashes
    winners_hash = compute_hash(winners, 'address')
    amounts_hash = compute_hash(amounts, 'uint256')

    # EIP-712 Domain
    domain = {
        "name": "ClawArena",
        "version": "1",
        "chainId": chain_id,
        "verifyingContract": arena_address
    }

    # EIP-712 Types
    types = {
        "EIP712Domain": [
            {"name": "name", "type": "string"},
            {"name": "version", "type": "string"},
            {"name": "chainId", "type": "uint256"},
            {"name": "verifyingContract", "type": "address"}
        ],
        "Finalize": [
            {"name": "arena", "type": "address"},
            {"name": "winnersHash", "type": "bytes32"},
            {"name": "amountsHash", "type": "bytes32"},
            {"name": "nonce", "type": "uint256"}
        ]
    }

    # Message to sign
    message = {
        "arena": arena_address,
        "winnersHash": winners_hash,
        "amountsHash": amounts_hash,
        "nonce": nonce
    }

    # Create typed data structure for signing
    typed_data = {
        "types": types,
        "primaryType": "Finalize",
        "domain": domain,
        "message": message
    }

    # Sign the typed data
    signed = account.sign_typed_data(
        domain_data=domain,
        message_types={"Finalize": types["Finalize"]},
        message_data=message
    )

    return {
        "signature": '0x' + signed.signature.hex(),
        "domain": domain,
        "types": {"Finalize": types["Finalize"]},
        "message": message
    }

# ============ ENDPOINTS ============

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "claw-arena-agent-signer",
        "operator_address": OPERATOR_ADDRESS,
        "chain_id": CHAIN_ID
    }

@app.get("/operator")
async def get_operator():
    """Get the operator address"""
    return {
        "operator_address": OPERATOR_ADDRESS,
        "chain_id": CHAIN_ID
    }

@app.post("/sign", response_model=SignFinalizeResponse)
async def sign_finalize(request: SignFinalizeRequest):
    """
    Sign a finalize request using EIP-712.

    This endpoint is called by the backend when an admin requests
    a signature to finalize a tournament.
    """
    try:
        logger.info(f"Signing finalize for arena {request.arena_address}")
        logger.info(f"Winners: {request.winners}")
        logger.info(f"Amounts: {request.amounts}")
        logger.info(f"Nonce: {request.nonce}")

        result = sign_finalize_eip712(
            arena_address=request.arena_address,
            winners=request.winners,
            amounts=request.amounts,
            nonce=request.nonce,
            chain_id=request.chain_id
        )

        logger.info(f"Signature generated: {result['signature'][:20]}...")

        return SignFinalizeResponse(
            success=True,
            signature=result["signature"],
            operator_address=OPERATOR_ADDRESS,
            domain=result["domain"],
            types=result["types"],
            message=result["message"]
        )

    except Exception as e:
        logger.error(f"Signing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============ MAIN ============

if __name__ == "__main__":
    import uvicorn

    logger.info("=" * 50)
    logger.info("CLAW ARENA Agent Signer Starting")
    logger.info(f"Operator Address: {OPERATOR_ADDRESS}")
    logger.info(f"Chain ID: {CHAIN_ID}")
    logger.info(f"Port: {AGENT_PORT}")
    logger.info("=" * 50)

    uvicorn.run(app, host="0.0.0.0", port=AGENT_PORT)
