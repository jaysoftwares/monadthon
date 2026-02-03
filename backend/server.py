from fastapi import FastAPI, APIRouter, HTTPException, Header, Depends, Query
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Literal
import uuid
from datetime import datetime, timezone
import hashlib
import httpx

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'claw_arena')]

# ===========================================
# Environment Configuration
# ===========================================

ADMIN_API_KEY = os.environ.get('ADMIN_API_KEY', '')
DEFAULT_NETWORK = os.environ.get('DEFAULT_NETWORK', 'testnet')

# Network Configuration
NETWORK_CONFIG = {
    'testnet': {
        'chain_id': int(os.environ.get('TESTNET_CHAIN_ID', '10143')),
        'rpc_url': os.environ.get('TESTNET_RPC_URL', 'https://testnet-rpc.monad.xyz'),
        'explorer_url': os.environ.get('TESTNET_EXPLORER_URL', 'https://testnet.monadexplorer.com'),
        'arena_factory': os.environ.get('TESTNET_ARENA_FACTORY_ADDRESS', ''),
        'treasury': os.environ.get('TESTNET_TREASURY_ADDRESS', ''),
    },
    'mainnet': {
        'chain_id': int(os.environ.get('MAINNET_CHAIN_ID', '143')),
        'rpc_url': os.environ.get('MAINNET_RPC_URL', 'https://rpc.monad.xyz'),
        'explorer_url': os.environ.get('MAINNET_EXPLORER_URL', 'https://monadscan.com'),
        'arena_factory': os.environ.get('MAINNET_ARENA_FACTORY_ADDRESS', ''),
        'treasury': os.environ.get('MAINNET_TREASURY_ADDRESS', ''),
    }
}

# Agent Signer Configuration
# Can use either the built-in agent_signer.py or OpenClaw Gateway
AGENT_SIGNER_URL = os.environ.get('AGENT_SIGNER_URL', 'http://localhost:8002')
OPENCLAW_API_URL = os.environ.get('OPENCLAW_API_URL', '')
OPENCLAW_API_KEY = os.environ.get('OPENCLAW_API_KEY', '')
OPERATOR_ADDRESS = os.environ.get('OPERATOR_ADDRESS', '')

# Create the main app
app = FastAPI(title="CLAW ARENA API", version="1.0.0")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===========================================
# MODELS
# ===========================================

class NetworkConfig(BaseModel):
    chain_id: int
    rpc_url: str
    explorer_url: str
    arena_factory: str
    treasury: str

class ArenaCreate(BaseModel):
    name: str
    entry_fee: str  # In MON (wei string)
    max_players: int = 8
    protocol_fee_bps: int = 250  # 2.5%
    contract_address: str  # Real contract address from on-chain deployment

class Arena(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    address: str  # Contract address
    name: str
    entry_fee: str
    max_players: int
    protocol_fee_bps: int
    treasury: str
    network: str = DEFAULT_NETWORK  # "testnet" or "mainnet"
    players: List[str] = []
    is_closed: bool = False
    is_finalized: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    closed_at: Optional[str] = None
    finalized_at: Optional[str] = None
    winners: List[str] = []
    payouts: List[str] = []
    tx_hash: Optional[str] = None

class JoinArena(BaseModel):
    arena_address: str
    player_address: str
    tx_hash: str

class PlayerJoin(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    arena_address: str
    player_address: str
    tx_hash: str
    joined_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class LeaderboardEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    address: str
    total_wins: int = 0
    total_payouts: str = "0"
    tournaments_played: int = 0
    tournaments_won: int = 0

class FinalizeRequest(BaseModel):
    arena_address: str
    winners: List[str]
    amounts: List[str]

class FinalizeSignatureResponse(BaseModel):
    arena_address: str
    winners: List[str]
    amounts: List[str]
    nonce: int
    signature: str
    operator_address: str
    domain: dict
    types: dict
    message: dict

class PayoutRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    arena_address: str
    winner_address: str
    amount: str
    tx_hash: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

# ===========================================
# DEPENDENCIES
# ===========================================

async def verify_admin_key(x_admin_key: str = Header(None)):
    if not ADMIN_API_KEY:
        raise HTTPException(status_code=500, detail="Admin API key not configured")
    if x_admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid admin API key")
    return True

def get_network_config(network: str) -> NetworkConfig:
    """Get configuration for specified network"""
    if network not in NETWORK_CONFIG:
        raise HTTPException(status_code=400, detail=f"Invalid network: {network}. Use 'testnet' or 'mainnet'")
    config = NETWORK_CONFIG[network]
    return NetworkConfig(**config)

# ===========================================
# AGENT SIGNING SERVICE
# ===========================================

async def request_agent_signature(
    arena_address: str,
    winners: List[str],
    amounts: List[str],
    nonce: int,
    chain_id: int
) -> dict:
    """
    Request EIP-712 signature from Agent Signer service.
    Uses the built-in agent_signer.py or OpenClaw Gateway.
    Returns signature data for finalize transaction.
    """
    # Try agent signer first, then OpenClaw
    signer_url = AGENT_SIGNER_URL or OPENCLAW_API_URL

    if not signer_url:
        raise HTTPException(
            status_code=500,
            detail="No signing service configured. Set AGENT_SIGNER_URL or OPENCLAW_API_URL."
        )

    async with httpx.AsyncClient() as http_client:
        try:
            # Prepare request payload
            payload = {
                "arena_address": arena_address,
                "winners": winners,
                "amounts": amounts,
                "nonce": nonce,
                "chain_id": chain_id
            }

            # Set headers based on service type
            headers = {"Content-Type": "application/json"}
            if OPENCLAW_API_KEY:
                headers["Authorization"] = f"Bearer {OPENCLAW_API_KEY}"

            logger.info(f"Requesting signature from {signer_url}/sign")

            response = await http_client.post(
                f"{signer_url}/sign",
                headers=headers,
                json=payload,
                timeout=30.0
            )

            if response.status_code != 200:
                logger.error(f"Signer API error: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=502,
                    detail=f"Signing service error: {response.text}"
                )

            result = response.json()
            signature = result.get("signature")

            if not signature:
                raise HTTPException(
                    status_code=502,
                    detail="Signing service did not return a signature"
                )

            # Update operator address if returned
            global OPERATOR_ADDRESS
            if result.get("operator_address") and not OPERATOR_ADDRESS:
                OPERATOR_ADDRESS = result.get("operator_address")

            return {
                "signature": signature,
                "operator_address": result.get("operator_address", OPERATOR_ADDRESS),
                "domain": result.get("domain", {}),
                "types": result.get("types", {}),
                "message": result.get("message", {})
            }

        except httpx.RequestError as e:
            logger.error(f"Signing service request failed: {e}")
            raise HTTPException(
                status_code=502,
                detail=f"Failed to connect to signing service: {str(e)}. Make sure agent_signer.py is running."
            )

# ===========================================
# PUBLIC ENDPOINTS
# ===========================================

@api_router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "claw-arena-api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "default_network": DEFAULT_NETWORK,
        "openclaw_configured": bool(OPENCLAW_API_URL and OPENCLAW_API_KEY)
    }

@api_router.get("/config")
async def get_config(network: str = Query(default=DEFAULT_NETWORK)):
    """Get network configuration"""
    config = get_network_config(network)
    return {
        "network": network,
        "chain_id": config.chain_id,
        "rpc_url": config.rpc_url,
        "explorer_url": config.explorer_url,
        "arena_factory": config.arena_factory,
        "treasury": config.treasury,
        "operator_address": OPERATOR_ADDRESS
    }

@api_router.get("/arenas", response_model=List[Arena])
async def get_arenas(network: str = Query(default=None)):
    """Get all arenas, optionally filtered by network"""
    query = {}
    if network:
        query["network"] = network
    arenas = await db.arenas.find(query, {"_id": 0}).to_list(100)
    return arenas

@api_router.get("/arenas/{address}", response_model=Arena)
async def get_arena(address: str):
    """Get arena by address"""
    arena = await db.arenas.find_one({"address": address}, {"_id": 0})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")
    return arena

@api_router.get("/leaderboard", response_model=List[LeaderboardEntry])
async def get_leaderboard(limit: int = 50, network: str = Query(default=None)):
    """Get leaderboard sorted by total payouts"""
    # Note: Leaderboard is global, but could be filtered by network if needed
    leaderboard = await db.leaderboard.find({}, {"_id": 0}).sort("total_payouts", -1).to_list(limit)
    return leaderboard

@api_router.get("/arenas/{address}/players")
async def get_arena_players(address: str):
    """Get all players for an arena"""
    joins = await db.joins.find({"arena_address": address}, {"_id": 0}).to_list(100)
    return {"arena_address": address, "players": [j["player_address"] for j in joins]}

@api_router.get("/arenas/{address}/payouts")
async def get_arena_payouts(address: str):
    """Get all payouts for an arena"""
    payouts = await db.payouts.find({"arena_address": address}, {"_id": 0}).to_list(100)
    return {"arena_address": address, "payouts": payouts}

# ===========================================
# JOIN ENDPOINT
# ===========================================

@api_router.post("/arenas/join")
async def join_arena(join_data: JoinArena):
    """Record a player joining an arena (called after on-chain join tx)"""
    arena = await db.arenas.find_one({"address": join_data.arena_address})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")

    if arena.get("is_closed"):
        raise HTTPException(status_code=400, detail="Arena registration is closed")

    if arena.get("is_finalized"):
        raise HTTPException(status_code=400, detail="Arena is already finalized")

    if len(arena.get("players", [])) >= arena.get("max_players", 8):
        raise HTTPException(status_code=400, detail="Arena is full")

    if join_data.player_address in arena.get("players", []):
        raise HTTPException(status_code=400, detail="Player already joined")

    # Record join
    join_record = PlayerJoin(
        arena_address=join_data.arena_address,
        player_address=join_data.player_address,
        tx_hash=join_data.tx_hash
    )
    await db.joins.insert_one(join_record.model_dump())

    # Update arena players
    await db.arenas.update_one(
        {"address": join_data.arena_address},
        {"$push": {"players": join_data.player_address}}
    )

    # Update leaderboard entry
    await db.leaderboard.update_one(
        {"address": join_data.player_address},
        {
            "$setOnInsert": {"address": join_data.player_address, "total_wins": 0, "total_payouts": "0", "tournaments_won": 0},
            "$inc": {"tournaments_played": 1}
        },
        upsert=True
    )

    logger.info(f"Player {join_data.player_address} joined arena {join_data.arena_address}")

    return {"success": True, "message": "Player joined arena", "tx_hash": join_data.tx_hash}

# ===========================================
# ADMIN ENDPOINTS
# ===========================================

@api_router.post("/admin/arena/create", response_model=Arena)
async def create_arena(
    arena_data: ArenaCreate,
    network: str = Query(default=DEFAULT_NETWORK),
    _: bool = Depends(verify_admin_key)
):
    """
    Register a new arena after it's been deployed on-chain.
    The contract_address must be the real deployed contract address.
    """
    config = get_network_config(network)

    # Validate contract address format
    if not arena_data.contract_address.startswith("0x") or len(arena_data.contract_address) != 42:
        raise HTTPException(status_code=400, detail="Invalid contract address format")

    # Check if arena already exists
    existing = await db.arenas.find_one({"address": arena_data.contract_address})
    if existing:
        raise HTTPException(status_code=400, detail="Arena with this address already exists")

    arena = Arena(
        address=arena_data.contract_address,
        name=arena_data.name,
        entry_fee=arena_data.entry_fee,
        max_players=arena_data.max_players,
        protocol_fee_bps=arena_data.protocol_fee_bps,
        treasury=config.treasury,
        network=network
    )

    await db.arenas.insert_one(arena.model_dump())

    logger.info(f"Created arena {arena.name} at {arena_data.contract_address} on {network}")

    return arena

@api_router.post("/admin/arena/{address}/close")
async def close_arena(address: str, _: bool = Depends(verify_admin_key)):
    """Close arena registration"""
    arena = await db.arenas.find_one({"address": address})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")

    if arena.get("is_closed"):
        raise HTTPException(status_code=400, detail="Arena is already closed")

    await db.arenas.update_one(
        {"address": address},
        {"$set": {"is_closed": True, "closed_at": datetime.now(timezone.utc).isoformat()}}
    )

    logger.info(f"Closed arena {address}")

    return {"success": True, "message": "Arena registration closed"}

@api_router.post("/admin/arena/request-finalize-signature", response_model=FinalizeSignatureResponse)
async def request_finalize_signature(request: FinalizeRequest, _: bool = Depends(verify_admin_key)):
    """
    Request EIP-712 signature from OpenClaw for finalize transaction.
    """
    arena = await db.arenas.find_one({"address": request.arena_address})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")

    if arena.get("is_finalized"):
        raise HTTPException(status_code=400, detail="Arena is already finalized")

    if not arena.get("is_closed"):
        raise HTTPException(status_code=400, detail="Arena registration must be closed first")

    # Validate winners and amounts
    if len(request.winners) != len(request.amounts):
        raise HTTPException(status_code=400, detail="Winners and amounts arrays must have same length")

    if len(request.winners) == 0:
        raise HTTPException(status_code=400, detail="Must have at least one winner")

    # Get network config
    network = arena.get("network", DEFAULT_NETWORK)
    config = get_network_config(network)

    # Get nonce for replay protection
    nonce = await db.nonces.count_documents({}) + 1
    await db.nonces.insert_one({
        "arena_address": request.arena_address,
        "nonce": nonce,
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    # Request signature from agent signer
    signature_data = await request_agent_signature(
        arena_address=request.arena_address,
        winners=request.winners,
        amounts=request.amounts,
        nonce=nonce,
        chain_id=config.chain_id
    )

    logger.info(f"Generated finalize signature for arena {request.arena_address} on {network}")

    return FinalizeSignatureResponse(
        arena_address=request.arena_address,
        winners=request.winners,
        amounts=request.amounts,
        nonce=nonce,
        signature=signature_data["signature"],
        operator_address=signature_data.get("operator_address", OPERATOR_ADDRESS),
        domain=signature_data["domain"],
        types=signature_data["types"],
        message=signature_data["message"]
    )

@api_router.post("/admin/arena/{address}/finalize")
async def record_finalize(
    address: str,
    tx_hash: str,
    winners: List[str],
    amounts: List[str],
    _: bool = Depends(verify_admin_key)
):
    """Record finalization after on-chain tx (called by frontend after successful tx)"""
    arena = await db.arenas.find_one({"address": address})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")

    if arena.get("is_finalized"):
        raise HTTPException(status_code=400, detail="Arena is already finalized")

    # Update arena
    await db.arenas.update_one(
        {"address": address},
        {
            "$set": {
                "is_finalized": True,
                "finalized_at": datetime.now(timezone.utc).isoformat(),
                "winners": winners,
                "payouts": amounts,
                "tx_hash": tx_hash
            }
        }
    )

    # Record payouts and update leaderboard
    for winner, amount in zip(winners, amounts):
        payout = PayoutRecord(
            arena_address=address,
            winner_address=winner,
            amount=amount,
            tx_hash=tx_hash
        )
        await db.payouts.insert_one(payout.model_dump())

        # Update leaderboard
        current = await db.leaderboard.find_one({"address": winner})
        current_payouts = int(current.get("total_payouts", "0")) if current else 0
        new_payouts = current_payouts + int(amount)

        await db.leaderboard.update_one(
            {"address": winner},
            {
                "$set": {"total_payouts": str(new_payouts)},
                "$inc": {"total_wins": 1, "tournaments_won": 1}
            },
            upsert=True
        )

    logger.info(f"Finalized arena {address} with tx {tx_hash}")

    return {"success": True, "message": "Arena finalized", "tx_hash": tx_hash}

# ===========================================
# INDEXER ENDPOINTS (for on-chain events)
# ===========================================

@api_router.post("/indexer/event/arena-created")
async def index_arena_created(arena: Arena):
    """Index ArenaCreated event from blockchain"""
    await db.arenas.update_one(
        {"address": arena.address},
        {"$set": arena.model_dump()},
        upsert=True
    )
    logger.info(f"Indexed arena created: {arena.address}")
    return {"success": True, "message": "Arena indexed"}

@api_router.post("/indexer/event/joined")
async def index_joined(join_data: JoinArena):
    """Index Joined event from blockchain"""
    return await join_arena(join_data)

# ===========================================
# APP CONFIGURATION
# ===========================================

# Include the router
app.include_router(api_router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Log configuration on startup"""
    logger.info("=" * 50)
    logger.info("CLAW ARENA API Starting")
    logger.info(f"Default Network: {DEFAULT_NETWORK}")
    logger.info(f"OpenClaw Configured: {bool(OPENCLAW_API_URL and OPENCLAW_API_KEY)}")
    logger.info(f"Operator Address: {OPERATOR_ADDRESS or 'NOT SET'}")

    for network, config in NETWORK_CONFIG.items():
        logger.info(f"{network.upper()} - Chain ID: {config['chain_id']}")
        logger.info(f"{network.upper()} - Arena Factory: {config['arena_factory'] or 'NOT SET'}")
        logger.info(f"{network.upper()} - Treasury: {config['treasury'] or 'NOT SET'}")
    logger.info("=" * 50)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
