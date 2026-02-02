from fastapi import FastAPI, APIRouter, HTTPException, Header, Depends
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import hashlib
import json

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Environment variables
ADMIN_API_KEY = os.environ.get('ADMIN_API_KEY', 'claw-arena-admin-key')
AGENT_ORCHESTRATOR_URL = os.environ.get('AGENT_ORCHESTRATOR_URL', 'http://localhost:8002')

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

# ============ MODELS ============

class ArenaCreate(BaseModel):
    name: str
    entry_fee: str  # In MON (wei string)
    max_players: int = 8
    protocol_fee_bps: int = 250  # 2.5%
    treasury: str = "0x0000000000000000000000000000000000000000"

class Arena(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    address: str  # Contract address
    name: str
    entry_fee: str
    max_players: int
    protocol_fee_bps: int
    treasury: str
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

# ============ DEPENDENCIES ============

async def verify_admin_key(x_admin_key: str = Header(None)):
    if x_admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid admin API key")
    return True

# ============ HELPER FUNCTIONS ============

def generate_mock_address():
    """Generate a mock Ethereum address"""
    random_bytes = os.urandom(20)
    return "0x" + random_bytes.hex()

def generate_mock_tx_hash():
    """Generate a mock transaction hash"""
    random_bytes = os.urandom(32)
    return "0x" + random_bytes.hex()

def generate_mock_signature():
    """Generate a mock EIP-712 signature"""
    random_bytes = os.urandom(65)
    return "0x" + random_bytes.hex()

# ============ PUBLIC ENDPOINTS ============

@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "claw-arena-api", "timestamp": datetime.now(timezone.utc).isoformat()}

@api_router.get("/arenas", response_model=List[Arena])
async def get_arenas():
    """Get all arenas"""
    arenas = await db.arenas.find({}, {"_id": 0}).to_list(100)
    return arenas

@api_router.get("/arenas/{address}", response_model=Arena)
async def get_arena(address: str):
    """Get arena by address"""
    arena = await db.arenas.find_one({"address": address}, {"_id": 0})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")
    return arena

@api_router.get("/leaderboard", response_model=List[LeaderboardEntry])
async def get_leaderboard(limit: int = 50):
    """Get leaderboard sorted by total payouts"""
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

# ============ JOIN ENDPOINT (simulates indexer receiving event) ============

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

# ============ ADMIN ENDPOINTS ============

@api_router.post("/admin/arena/create", response_model=Arena)
async def create_arena(arena_data: ArenaCreate, _: bool = Depends(verify_admin_key)):
    """Create a new arena (returns data for frontend to send tx)"""
    arena_address = generate_mock_address()
    
    arena = Arena(
        address=arena_address,
        name=arena_data.name,
        entry_fee=arena_data.entry_fee,
        max_players=arena_data.max_players,
        protocol_fee_bps=arena_data.protocol_fee_bps,
        treasury=arena_data.treasury
    )
    
    await db.arenas.insert_one(arena.model_dump())
    
    logger.info(f"Created arena {arena.name} at {arena_address}")
    
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
    Request EIP-712 signature from OpenClaw agent orchestrator for finalize.
    This endpoint calls the agent-orchestrator service which in turn calls OpenClaw Gateway.
    """
    arena = await db.arenas.find_one({"address": request.arena_address})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")
    
    if arena.get("is_finalized"):
        raise HTTPException(status_code=400, detail="Arena is already finalized")
    
    if not arena.get("is_closed"):
        raise HTTPException(status_code=400, detail="Arena registration must be closed first")
    
    # Get nonce for replay protection
    nonce = await db.nonces.count_documents({}) + 1
    await db.nonces.insert_one({"arena_address": request.arena_address, "nonce": nonce})
    
    # In production, this would call the agent-orchestrator service
    # For now, we generate a mock signature
    
    # EIP-712 Domain
    chain_id = int(os.environ.get('CHAIN_ID', '10143'))  # Monad testnet
    domain = {
        "name": "ClawArena",
        "version": "1",
        "chainId": chain_id,
        "verifyingContract": request.arena_address
    }
    
    # EIP-712 Types
    types = {
        "Finalize": [
            {"name": "arena", "type": "address"},
            {"name": "winnersHash", "type": "bytes32"},
            {"name": "amountsHash", "type": "bytes32"},
            {"name": "nonce", "type": "uint256"}
        ]
    }
    
    # Compute hashes
    winners_hash = "0x" + hashlib.sha256(",".join(request.winners).encode()).hexdigest()
    amounts_hash = "0x" + hashlib.sha256(",".join(request.amounts).encode()).hexdigest()
    
    # Message to sign
    message = {
        "arena": request.arena_address,
        "winnersHash": winners_hash,
        "amountsHash": amounts_hash,
        "nonce": nonce
    }
    
    # Mock operator address (in production, this comes from OpenClaw)
    operator_address = os.environ.get('OPERATOR_ADDRESS', '0x742d35Cc6634C0532925a3b844Bc9e7595f3F4D0')
    
    # Mock signature (in production, OpenClaw signs this)
    signature = generate_mock_signature()
    
    logger.info(f"Generated finalize signature for arena {request.arena_address}")
    
    return FinalizeSignatureResponse(
        arena_address=request.arena_address,
        winners=request.winners,
        amounts=request.amounts,
        nonce=nonce,
        signature=signature,
        operator_address=operator_address,
        domain=domain,
        types=types,
        message=message
    )

@api_router.post("/admin/arena/{address}/finalize")
async def record_finalize(address: str, tx_hash: str, winners: List[str], amounts: List[str], _: bool = Depends(verify_admin_key)):
    """Record finalization after on-chain tx (called by frontend after successful tx)"""
    arena = await db.arenas.find_one({"address": address})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")
    
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

# ============ INDEXER SIMULATION ENDPOINTS ============

@api_router.post("/indexer/event/arena-created")
async def index_arena_created(arena: Arena):
    """Simulate indexer receiving ArenaCreated event"""
    await db.arenas.update_one(
        {"address": arena.address},
        {"$set": arena.model_dump()},
        upsert=True
    )
    return {"success": True, "message": "Arena indexed"}

@api_router.post("/indexer/event/joined")
async def index_joined(join_data: JoinArena):
    """Simulate indexer receiving Joined event"""
    return await join_arena(join_data)

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

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
