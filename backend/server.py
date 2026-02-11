from fastapi import FastAPI, APIRouter, HTTPException, Header, Depends, Query
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Literal, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import hashlib
import httpx
import asyncio

from game_engine import (
    GameType, GameEngine, GameState, GAME_RULES,
    get_game_rules_json, get_all_game_types, game_engine, TournamentMode
)
from user_agents import (
    UserAgentManager, AgentConfig, AgentStrategy, AgentStatus,
    user_agent_manager
)

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
# ARENA TIMER MANAGEMENT
# ===========================================

class ArenaTimerManager:
    """Manages game start countdowns and idle timers for arenas"""
    
    def __init__(self):
        self.arena_timers: Dict[str, Dict[str, Any]] = {}  # arena_address -> {timer_type, countdown_ends_at, ...}
        self.background_task = None
    
    async def start_game_countdown(self, arena_address: str, countdown_seconds: int = 10):
        """Start a countdown timer before game begins"""
        countdown_ends_at = (datetime.now(timezone.utc) + timedelta(seconds=countdown_seconds)).isoformat()
        
        self.arena_timers[arena_address] = {
            "type": "game_start_countdown",
            "countdown_starts": datetime.now(timezone.utc).isoformat(),
            "countdown_ends_at": countdown_ends_at,
            "countdown_seconds": countdown_seconds,
            "game_started": False
        }
        
        logger.info(f"Started game countdown for arena {arena_address}, ends in {countdown_seconds}s")
    
    async def start_idle_timer(self, arena_address: str, idle_seconds: int = 20):
        """Start an idle timer for arenas with 0 or 1 player"""
        idle_ends_at = (datetime.now(timezone.utc) + timedelta(seconds=idle_seconds)).isoformat()
        
        self.arena_timers[arena_address] = {
            "type": "idle_timer",
            "idle_starts": datetime.now(timezone.utc).isoformat(),
            "idle_ends_at": idle_ends_at,
            "idle_seconds": idle_seconds
        }
        
        logger.info(f"Started idle timer for arena {arena_address}, expires in {idle_seconds}s")
    
    async def cancel_timer(self, arena_address: str):
        """Cancel any timer for an arena"""
        if arena_address in self.arena_timers:
            del self.arena_timers[arena_address]
            logger.info(f"Cancelled timer for arena {arena_address}")
    
    async def get_timer_status(self, arena_address: str) -> Optional[Dict[str, Any]]:
        """Get current timer status for an arena"""
        return self.arena_timers.get(arena_address)
    
    async def process_timers(self):
        """Background task to process expiring timers"""
        while True:
            try:
                await asyncio.sleep(1)  # Check every second
                now = datetime.now(timezone.utc)
                
                expired_arenas = []
                
                for arena_address, timer in list(self.arena_timers.items()):
                    try:
                        if timer["type"] == "game_start_countdown":
                            countdown_ends = datetime.fromisoformat(timer["countdown_ends_at"].replace("Z", "+00:00"))
                            if now >= countdown_ends and not timer.get("game_started"):
                                # Countdown expired, start the game
                                await self._trigger_game_start(arena_address)
                                timer["game_started"] = True
                                expired_arenas.append(arena_address)
                        
                        elif timer["type"] == "idle_timer":
                            idle_ends = datetime.fromisoformat(timer["idle_ends_at"].replace("Z", "+00:00"))
                            if now >= idle_ends:
                                # Idle timer expired, handle based on player count
                                await self._handle_idle_expiration(arena_address)
                                expired_arenas.append(arena_address)
                    except Exception as e:
                        logger.error(f"Error processing timer for arena {arena_address}: {e}")
                
                # Clean up expired timers
                for arena_address in expired_arenas:
                    await self.cancel_timer(arena_address)
            
            except Exception as e:
                logger.error(f"Error in timer processing loop: {e}")
                await asyncio.sleep(5)  # Delay before retrying
    
    async def _trigger_game_start(self, arena_address: str):
        """Trigger game start after countdown expires"""
        try:
            arena = await db.arenas.find_one({"address": arena_address})
            if not arena:
                logger.warning(f"Arena {arena_address} not found for game start")
                return
            
            players = arena.get("players", [])
            if len(players) < 2:
                logger.warning(f"Arena {arena_address} has less than 2 players, cannot start game")
                return
            
            game_type_str = arena.get("game_type", "prediction")
            try:
                game_type = GameType(game_type_str)
            except ValueError:
                game_type = GameType.PREDICTION
            
            # Create and start game
            game = game_engine.create_game(
                arena_address=arena_address,
                game_type=game_type,
                players=players
            )
            
            # Start the game (moves from learning to active)
            game_engine.start_game(game.game_id)
            
            # Update arena
            await db.arenas.update_one(
                {"address": arena_address},
                {"$set": {
                    "game_id": game.game_id,
                    "game_status": "active",
                    "game_start": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            logger.info(f"Game started for arena {arena_address}, game_id: {game.game_id}")
        
        except Exception as e:
            logger.error(f"Error triggering game start for arena {arena_address}: {e}")
    
    async def _handle_idle_expiration(self, arena_address: str):
        """Handle idle timer expiration based on player count"""
        try:
            arena = await db.arenas.find_one({"address": arena_address})
            if not arena:
                logger.warning(f"Arena {arena_address} not found for idle handling")
                return
            
            players = arena.get("players", [])
            player_count = len(players)
            
            if player_count == 0:
                # Delete empty arena
                await db.arenas.delete_one({"address": arena_address})
                logger.info(f"Deleted empty arena {arena_address}")
            
            elif player_count == 1:
                # Delete arena and refund the player
                player_address = players[0]
                entry_fee = arena.get("entry_fee", "0")
                
                # Record refund (in production, trigger actual refund tx)
                refund_record = {
                    "arena_address": arena_address,
                    "player_address": player_address,
                    "amount": entry_fee,
                    "reason": "idle_timeout_single_player",
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                await db.refunds.insert_one(refund_record)
                
                await db.arenas.delete_one({"address": arena_address})
                logger.info(f"Deleted arena {arena_address} with 1 player, refunded {player_address}")
            
            elif player_count >= 2:
                # Start game immediately
                game_type_str = arena.get("game_type", "prediction")
                try:
                    game_type = GameType(game_type_str)
                except ValueError:
                    game_type = GameType.PREDICTION
                
                game = game_engine.create_game(
                    arena_address=arena_address,
                    game_type=game_type,
                    players=players
                )
                
                game_engine.start_game(game.game_id)
                
                await db.arenas.update_one(
                    {"address": arena_address},
                    {"$set": {
                        "game_id": game.game_id,
                        "game_status": "active",
                        "game_start": datetime.now(timezone.utc).isoformat()
                    }}
                )
                
                logger.info(f"Started game immediately for arena {arena_address} after idle timeout")
        
        except Exception as e:
            logger.error(f"Error handling idle expiration for arena {arena_address}: {e}")

timer_manager = ArenaTimerManager()

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
    game_type: Optional[str] = None  # "claw", "prediction", "speed", "blackjack"
    game_config: Optional[Dict[str, Any]] = None  # Game rules and config
    learning_phase_seconds: int = 60  # Duration of learning phase (1 minute default)

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
    # Timer fields for autonomous agent
    registration_deadline: Optional[str] = None  # ISO timestamp
    tournament_end_estimate: Optional[str] = None  # ISO timestamp
    created_by: str = "admin"  # "admin" or "agent"
    creation_reason: Optional[str] = None  # Agent's reasoning for creation
    # Game fields
    game_type: Optional[str] = None  # "claw", "prediction", "speed", "blackjack"
    game_config: Optional[Dict[str, Any]] = None  # Game rules and config
    game_id: Optional[str] = None  # Active game session ID
    game_status: Optional[str] = None  # "waiting", "learning", "active", "finished"
    learning_phase_start: Optional[str] = None  # When 1-min learning phase starts
    learning_phase_end: Optional[str] = None  # When learning phase ends
    game_start: Optional[str] = None  # When actual game starts
    game_results: Optional[Dict[str, Any]] = None  # Final game results
    learning_phase_seconds: int = 60  # Duration of learning phase

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


# Game-related models
class GameMove(BaseModel):
    """A player's move in a game"""
    arena_address: str
    player_address: str
    move_data: Dict[str, Any]  # Game-specific move data


class GameMoveResponse(BaseModel):
    """Response after submitting a move"""
    success: bool
    message: str
    player_score: Optional[int] = None
    game_state: Optional[Dict[str, Any]] = None


class GameRulesResponse(BaseModel):
    """Game rules for frontend display"""
    game_type: str
    name: str
    description: str
    how_to_play: List[str]
    tips: List[str]
    duration_seconds: int
    min_players: int
    max_players: int


class GameStateResponse(BaseModel):
    """Current game state"""
    game_id: str
    arena_address: str
    game_type: str
    status: str
    round_number: int
    current_challenge: Optional[Dict[str, Any]] = None
    leaderboard: List[Dict[str, Any]] = []
    time_remaining_seconds: int = 0

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
# AGENT STATUS & SCHEDULE ENDPOINTS
# ===========================================

@api_router.get("/agent/status")
async def get_agent_status():
    """Get autonomous agent status and schedule"""
    schedule = await db.agent_schedule.find_one({"_id": "current"}, {"_id": 0})

    if not schedule:
        return {
            "agent_status": "inactive",
            "message": "Agent has not reported status yet. Start autonomous_agent.py.",
            "next_tournament_at": None,
            "next_tournament_countdown_seconds": 0,
            "last_cycle_at": None,
            "tournaments_created_today": 0,
        }

    # Calculate countdown
    next_at = schedule.get("next_tournament_at")
    countdown = 0
    if next_at:
        try:
            next_dt = datetime.fromisoformat(next_at.replace("Z", "+00:00"))
            diff = (next_dt - datetime.now(timezone.utc)).total_seconds()
            countdown = max(0, int(diff))
        except (ValueError, TypeError):
            countdown = 0

    return {
        "agent_status": schedule.get("status", "active"),
        "next_tournament_at": next_at,
        "next_tournament_countdown_seconds": countdown,
        "last_cycle_at": schedule.get("last_cycle_at"),
        "tournaments_created_today": schedule.get("tournaments_created_today", 0),
        "last_analysis": schedule.get("last_analysis"),
    }

@api_router.get("/agent/schedule")
async def get_agent_schedule():
    """Get full agent schedule with active tournaments and timers"""
    schedule = await db.agent_schedule.find_one({"_id": "current"}, {"_id": 0})

    # Get active (non-finalized) tournaments
    active_arenas = await db.arenas.find(
        {"is_finalized": False},
        {"_id": 0}
    ).sort("created_at", -1).to_list(20)

    # Get recently completed tournaments
    recent_completed = await db.arenas.find(
        {"is_finalized": True},
        {"_id": 0}
    ).sort("finalized_at", -1).to_list(5)

    now = datetime.now(timezone.utc)

    # Build active tournament list with countdowns
    active_list = []
    for arena in active_arenas:
        item = {
            "address": arena.get("address"),
            "name": arena.get("name"),
            "status": "closed" if arena.get("is_closed") else "registration_open",
            "players_joined": len(arena.get("players", [])),
            "max_players": arena.get("max_players", 8),
            "entry_fee": arena.get("entry_fee"),
            "created_by": arena.get("created_by", "admin"),
        }

        # Registration deadline countdown
        reg_deadline = arena.get("registration_deadline")
        if reg_deadline and not arena.get("is_closed"):
            try:
                dl_dt = datetime.fromisoformat(reg_deadline.replace("Z", "+00:00"))
                diff = (dl_dt - now).total_seconds()
                item["registration_deadline"] = reg_deadline
                item["registration_countdown_seconds"] = max(0, int(diff))
            except (ValueError, TypeError):
                pass

        # Tournament end estimate countdown
        end_est = arena.get("tournament_end_estimate")
        if end_est and arena.get("is_closed") and not arena.get("is_finalized"):
            try:
                end_dt = datetime.fromisoformat(end_est.replace("Z", "+00:00"))
                diff = (end_dt - now).total_seconds()
                item["tournament_end_estimate"] = end_est
                item["tournament_end_countdown_seconds"] = max(0, int(diff))
            except (ValueError, TypeError):
                pass

        active_list.append(item)

    # Next tournament countdown
    next_at = schedule.get("next_tournament_at") if schedule else None
    next_countdown = 0
    if next_at:
        try:
            next_dt = datetime.fromisoformat(next_at.replace("Z", "+00:00"))
            diff = (next_dt - now).total_seconds()
            next_countdown = max(0, int(diff))
        except (ValueError, TypeError):
            pass

    return {
        "agent_status": schedule.get("status", "inactive") if schedule else "inactive",
        "next_tournament_at": next_at,
        "next_tournament_countdown_seconds": next_countdown,
        "last_cycle_at": schedule.get("last_cycle_at") if schedule else None,
        "active_tournaments": active_list,
        "recent_completed": [
            {
                "address": a.get("address"),
                "name": a.get("name"),
                "finalized_at": a.get("finalized_at"),
                "winners": a.get("winners", []),
            }
            for a in recent_completed
        ],
    }

@api_router.post("/agent/update-schedule")
async def update_agent_schedule(
    next_tournament_at: Optional[str] = None,
    status: str = "active",
    last_analysis: Optional[dict] = None,
    _: bool = Depends(verify_admin_key)
):
    """Update agent schedule (called by autonomous_agent.py)"""
    update_data = {
        "status": status,
        "last_cycle_at": datetime.now(timezone.utc).isoformat(),
    }

    if next_tournament_at:
        update_data["next_tournament_at"] = next_tournament_at

    if last_analysis:
        update_data["last_analysis"] = last_analysis

    # Increment daily counter
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    current = await db.agent_schedule.find_one({"_id": "current"})
    if current and current.get("date") == today:
        update_data["tournaments_created_today"] = current.get("tournaments_created_today", 0)
    else:
        update_data["tournaments_created_today"] = 0
        update_data["date"] = today

    await db.agent_schedule.update_one(
        {"_id": "current"},
        {"$set": update_data},
        upsert=True
    )

    return {"success": True, "message": "Agent schedule updated"}

@api_router.post("/agent/tournament-created")
async def agent_tournament_created(_: bool = Depends(verify_admin_key)):
    """Increment the agent's daily tournament creation counter"""
    await db.agent_schedule.update_one(
        {"_id": "current"},
        {"$inc": {"tournaments_created_today": 1}},
        upsert=True
    )
    return {"success": True}

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
    
    # Check if arena is now full and start countdown if so
    updated_arena = await db.arenas.find_one({"address": join_data.arena_address})
    players = updated_arena.get("players", [])
    max_players = updated_arena.get("max_players", 8)
    
    response = {"success": True, "message": "Player joined arena", "tx_hash": join_data.tx_hash}
    
    if len(players) >= max_players and not updated_arena.get("is_closed"):
        # Arena is now full, close it and start countdown
        await db.arenas.update_one(
            {"address": join_data.arena_address},
            {"$set": {"is_closed": True, "closed_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        await timer_manager.start_game_countdown(join_data.arena_address, countdown_seconds=10)
        
        response["arena_full"] = True
        response["countdown_starts"] = True
        response["countdown_seconds"] = 10
        logger.info(f"Arena {join_data.arena_address} is now full, starting game countdown")
    
    # Check if we should start idle timer
    elif len(players) <= 1 and not updated_arena.get("is_closed"):
        # Start idle timer for empty/1-player arena
        await timer_manager.start_idle_timer(join_data.arena_address, idle_seconds=20)
        response["idle_timer_started"] = True
        response["idle_seconds"] = 20
        logger.info(f"Arena {join_data.arena_address} has {len(players)} player(s), idle timer started")

    return response

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

    # If no game type specified, randomly select one
    game_type = arena_data.game_type
    if not game_type:
        import random
        game_type = random.choice(["claw", "prediction", "speed", "blackjack"])

    # Get game config if not provided
    game_config = arena_data.game_config
    if not game_config:
        try:
            gt = GameType(game_type)
            game_config = get_game_rules_json(gt)
        except ValueError:
            game_config = {}

    arena = Arena(
        address=arena_data.contract_address,
        name=arena_data.name,
        entry_fee=arena_data.entry_fee,
        max_players=arena_data.max_players,
        protocol_fee_bps=arena_data.protocol_fee_bps,
        treasury=config.treasury,
        network=network,
        game_type=game_type,
        game_config=game_config,
        game_status="waiting",
        learning_phase_seconds=arena_data.learning_phase_seconds
    )

    await db.arenas.insert_one(arena.model_dump())

    logger.info(f"Created arena {arena.name} at {arena_data.contract_address} on {network} with game: {game_type}")

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

@api_router.get("/admin/arena/{address}/check-game-status")
async def check_game_status(address: str, _: bool = Depends(verify_admin_key)):
    """
    Check the current game status for an arena.
    Returns the game state including timer status and game progress.
    """
    arena = await db.arenas.find_one({"address": address}, {"_id": 0})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")
    
    game_id = arena.get("game_id")
    game_status = arena.get("game_status", "waiting")
    players = arena.get("players", [])
    
    response = {
        "arena_address": address,
        "arena_name": arena.get("name"),
        "status": "closed" if arena.get("is_closed") else "open",
        "is_finalized": arena.get("is_finalized", False),
        "player_count": len(players),
        "max_players": arena.get("max_players"),
        "players": players,
        "game_status": game_status,
        "game_id": game_id,
    }
    
    # Add timer info if exists
    timer_status = await timer_manager.get_timer_status(address)
    if timer_status:
        response["timer"] = timer_status
        
        # Calculate time remaining
        if timer_status["type"] == "game_start_countdown":
            ends_at = datetime.fromisoformat(timer_status["countdown_ends_at"].replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            response["time_remaining_seconds"] = max(0, int((ends_at - now).total_seconds()))
        elif timer_status["type"] == "idle_timer":
            ends_at = datetime.fromisoformat(timer_status["idle_ends_at"].replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            response["time_remaining_seconds"] = max(0, int((ends_at - now).total_seconds()))
    
    # Add game state if active game exists
    if game_id and game_id in game_engine.active_games:
        game = game_engine.active_games[game_id]
        leaderboard = game_engine.get_leaderboard(game_id)
        response["game"] = {
            "id": game_id,
            "type": game.game_type.value,
            "status": game.status,
            "round": game.round_number,
            "leaderboard": leaderboard
        }
    
    return response

@api_router.post("/admin/arena/{address}/process-winners")
async def process_winners(
    address: str,
    _: bool = Depends(verify_admin_key)
):
    """
    Process winners from completed game and calculate payouts.
    This endpoint:
    1. Gets game results from the game engine
    2. Calculates payouts based on entry fees and protocol fees
    3. Stores winners and payouts in the arena
    """
    arena = await db.arenas.find_one({"address": address})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")
    
    if arena.get("is_finalized"):
        raise HTTPException(status_code=400, detail="Arena is already finalized")
    
    game_id = arena.get("game_id")
    if not game_id or game_id not in game_engine.active_games:
        raise HTTPException(status_code=400, detail="No active game session")
    
    game = game_engine.active_games[game_id]
    
    if game.status != "finished":
        raise HTTPException(status_code=400, detail=f"Game is {game.status}, not finished")
    
    # Get winners from game
    winners = game.winners if game.winners else []
    if not winners:
        raise HTTPException(status_code=400, detail="No winners determined by game engine")
    
    # Calculate payouts
    entry_fee = int(arena.get("entry_fee", "0"))
    protocol_fee_bps = int(arena.get("protocol_fee_bps", 250))  # 2.5% default
    players = arena.get("players", [])
    player_count = len(players)
    
    # Total pool = entry_fee * number of players
    total_pool = entry_fee * player_count
    
    # Calculate protocol fee
    protocol_fee = int(total_pool * protocol_fee_bps / 10000)
    
    # Available for distribution to winners
    available_for_winners = total_pool - protocol_fee
    
    # Distribute evenly among winners
    payout_per_winner = available_for_winners // len(winners) if winners else 0
    remainder = available_for_winners % len(winners) if winners else 0
    
    # Build payouts list (add remainder to first winner)
    payouts = []
    payout_amounts = []
    for i, winner in enumerate(winners):
        amount = payout_per_winner
        if i == 0:
            amount += remainder
        payouts.append(winner)
        payout_amounts.append(str(amount))
    
    # Store winners and payouts
    await db.arenas.update_one(
        {"address": address},
        {"$set": {
            "winners": payouts,
            "payouts": payout_amounts,
            "game_results": {
                "winners": game.winners,
                "player_scores": {p.address: p.score for p in game.players.values()},
                "total_pool": str(total_pool),
                "protocol_fee": str(protocol_fee),
                "payout_per_winner": str(payout_per_winner)
            }
        }}
    )
    
    # Record individual payout records
    for winner, amount in zip(payouts, payout_amounts):
        payout = PayoutRecord(
            arena_address=address,
            winner_address=winner,
            amount=amount,
            tx_hash=""  # Will be set when finalized on-chain
        )
        await db.payouts.insert_one(payout.model_dump())
    
    logger.info(f"Processed winners for arena {address}: {payouts}")
    
    return {
        "success": True,
        "arena_address": address,
        "winners": payouts,
        "payouts": payout_amounts,
        "total_pool": str(total_pool),
        "protocol_fee": str(protocol_fee),
        "payout_per_winner": str(payout_per_winner),
        "message": "Winners processed successfully"
    }

@api_router.post("/admin/arena/{address}/check-if-full")
async def check_if_full(address: str, _: bool = Depends(verify_admin_key)):
    """
    Check if arena is full and trigger game start countdown if so.
    Returns True if full and countdown started, False otherwise.
    """
    arena = await db.arenas.find_one({"address": address})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")
    
    players = arena.get("players", [])
    max_players = arena.get("max_players", 8)
    
    is_full = len(players) >= max_players
    
    if is_full and not arena.get("is_closed"):
        # Close arena and start countdown
        await db.arenas.update_one(
            {"address": address},
            {"$set": {"is_closed": True, "closed_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        # Start the countdown
        await timer_manager.start_game_countdown(address, countdown_seconds=10)
        
        logger.info(f"Arena {address} is full, starting 10-second countdown")
        
        return {
            "success": True,
            "is_full": True,
            "player_count": len(players),
            "max_players": max_players,
            "countdown_started": True,
            "countdown_seconds": 10,
            "message": "Arena is full, game will start in 10 seconds"
        }
    
    return {
        "success": True,
        "is_full": is_full,
        "player_count": len(players),
        "max_players": max_players,
        "countdown_started": False,
        "message": f"Arena has {len(players)}/{max_players} players"
    }

@api_router.post("/admin/arena/{address}/start-idle-timer")
async def start_idle_timer(address: str, _: bool = Depends(verify_admin_key)):
    """
    Start idle timer for an arena with 0 or 1 player.
    If arena is still empty/1-player after 20 seconds, it will be deleted.
    """
    arena = await db.arenas.find_one({"address": address})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")
    
    players = arena.get("players", [])
    
    if len(players) > 1:
        return {
            "success": False,
            "message": f"Arena has {len(players)} players, idle timer not needed"
        }
    
    await timer_manager.start_idle_timer(address, idle_seconds=20)
    
    return {
        "success": True,
        "arena_address": address,
        "player_count": len(players),
        "idle_seconds": 20,
        "message": "Idle timer started, arena will be deleted if still empty/1-player after 20 seconds"
    }

# ===========================================
# GAME ENDPOINTS
# ===========================================

@api_router.get("/games/types", response_model=List[GameRulesResponse])
async def get_game_types():
    """Get all available game types with their rules"""
    return get_all_game_types()


@api_router.get("/games/rules/{game_type}", response_model=GameRulesResponse)
async def get_game_rules(game_type: str):
    """Get rules for a specific game type"""
    try:
        gt = GameType(game_type)
        return get_game_rules_json(gt)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid game type: {game_type}")


@api_router.get("/arenas/{address}/game", response_model=GameStateResponse)
async def get_arena_game_state(address: str):
    """Get current game state for an arena"""
    arena = await db.arenas.find_one({"address": address}, {"_id": 0})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")

    game_id = arena.get("game_id")
    if not game_id or game_id not in game_engine.active_games:
        # Return waiting state if no active game
        return GameStateResponse(
            game_id="",
            arena_address=address,
            game_type=arena.get("game_type", "prediction"),
            status=arena.get("game_status", "waiting"),
            round_number=0,
            current_challenge=None,
            leaderboard=[],
            time_remaining_seconds=0
        )

    game = game_engine.active_games[game_id]
    leaderboard = game_engine.get_leaderboard(game_id)

    # Calculate time remaining
    time_remaining = 0
    if game.ends_at:
        try:
            ends_at = datetime.fromisoformat(game.ends_at.replace("Z", "+00:00"))
            diff = (ends_at - datetime.now(timezone.utc)).total_seconds()
            time_remaining = max(0, int(diff))
        except (ValueError, TypeError):
            pass

    # Filter challenge data for client (hide answers)
    challenge = None
    if game.current_challenge:
        challenge = {k: v for k, v in game.current_challenge.items()
                     if k not in ["answer", "secret", "deck"]}

    return GameStateResponse(
        game_id=game.game_id,
        arena_address=address,
        game_type=game.game_type.value,
        status=game.status,
        round_number=game.round_number,
        current_challenge=challenge,
        leaderboard=leaderboard,
        time_remaining_seconds=time_remaining
    )


@api_router.post("/arenas/{address}/game/start")
async def start_arena_game(address: str, _: bool = Depends(verify_admin_key)):
    """Start the game for an arena (after learning phase)"""
    arena = await db.arenas.find_one({"address": address})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")

    if not arena.get("is_closed"):
        raise HTTPException(status_code=400, detail="Arena registration must be closed first")

    players = arena.get("players", [])
    if len(players) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 players")

    game_type_str = arena.get("game_type", "prediction")
    try:
        game_type = GameType(game_type_str)
    except ValueError:
        game_type = GameType.PREDICTION

    # Create new game session
    game = game_engine.create_game(
        arena_address=address,
        game_type=game_type,
        players=players
    )

    # Update arena with game ID
    await db.arenas.update_one(
        {"address": address},
        {"$set": {
            "game_id": game.game_id,
            "game_status": "learning"
        }}
    )

    logger.info(f"Created game {game.game_id} for arena {address}")

    return {
        "success": True,
        "game_id": game.game_id,
        "game_type": game_type.value,
        "status": "learning",
        "message": "Game created. Learning phase started."
    }


@api_router.post("/arenas/{address}/game/activate")
async def activate_arena_game(address: str, _: bool = Depends(verify_admin_key)):
    """Activate the game after learning phase ends"""
    arena = await db.arenas.find_one({"address": address})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")

    game_id = arena.get("game_id")
    if not game_id or game_id not in game_engine.active_games:
        raise HTTPException(status_code=400, detail="No active game session")

    game = game_engine.start_game(game_id)

    await db.arenas.update_one(
        {"address": address},
        {"$set": {"game_status": "active"}}
    )

    logger.info(f"Activated game {game_id} for arena {address}")

    return {
        "success": True,
        "game_id": game_id,
        "status": "active",
        "message": "Game is now active!"
    }


@api_router.post("/arenas/{address}/game/move", response_model=GameMoveResponse)
async def submit_game_move(address: str, move: GameMove):
    """Submit a move in the current game"""
    arena = await db.arenas.find_one({"address": address})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")

    game_id = arena.get("game_id")
    if not game_id or game_id not in game_engine.active_games:
        raise HTTPException(status_code=400, detail="No active game session")

    game = game_engine.active_games[game_id]
    if game.status != "active":
        raise HTTPException(status_code=400, detail=f"Game is {game.status}, not active")

    if move.player_address not in arena.get("players", []):
        raise HTTPException(status_code=403, detail="Player not in this arena")

    # Process the move
    success, message, result = game_engine.submit_move(
        game_id=game_id,
        player_address=move.player_address,
        move=move.move_data
    )

    player_score = None
    if move.player_address in game.players:
        player_score = game.players[move.player_address].score

    return GameMoveResponse(
        success=success,
        message=message,
        player_score=player_score,
        game_state=result
    )


@api_router.post("/arenas/{address}/game/advance-round")
async def advance_game_round(address: str, _: bool = Depends(verify_admin_key)):
    """Advance to the next round"""
    arena = await db.arenas.find_one({"address": address})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")

    game_id = arena.get("game_id")
    if not game_id:
        raise HTTPException(status_code=400, detail="No active game session")

    game = game_engine.advance_round(game_id)
    if not game:
        raise HTTPException(status_code=400, detail="Could not advance round")

    if game.status == "finished":
        # Game is complete, store results
        await db.arenas.update_one(
            {"address": address},
            {"$set": {
                "game_status": "finished",
                "game_results": {
                    "winners": game.winners,
                    "player_scores": {p.address: p.score for p in game.players.values()}
                }
            }}
        )
        logger.info(f"Game {game_id} finished. Winners: {game.winners}")

    return {
        "success": True,
        "game_id": game_id,
        "status": game.status,
        "round": game.round_number
    }


@api_router.post("/arenas/{address}/game/resolve-blackjack")
async def resolve_blackjack_round(address: str, _: bool = Depends(verify_admin_key)):
    """
    Resolve a blackjack round - dealer plays and points are awarded.
    Call this after all players have acted (hit/stand) to complete the round.
    """
    arena = await db.arenas.find_one({"address": address})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")

    game_id = arena.get("game_id")
    if not game_id or game_id not in game_engine.active_games:
        raise HTTPException(status_code=400, detail="No active game session")

    game = game_engine.active_games[game_id]
    if game.game_type.value != "blackjack":
        raise HTTPException(status_code=400, detail="Not a blackjack game")

    # Resolve the round (dealer plays, points awarded)
    results = game_engine.resolve_blackjack_round(game_id)

    if "error" in results:
        raise HTTPException(status_code=400, detail=results["error"])

    # Get updated leaderboard
    leaderboard = game_engine.get_leaderboard(game_id)

    return {
        "success": True,
        "dealer_cards": results.get("dealer_cards"),
        "dealer_total": results.get("dealer_total"),
        "dealer_bust": results.get("dealer_bust"),
        "player_results": results.get("player_results"),
        "leaderboard": leaderboard
    }


@api_router.get("/arenas/{address}/game/leaderboard")
async def get_game_leaderboard(address: str):
    """Get current leaderboard for the active game"""
    arena = await db.arenas.find_one({"address": address})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")

    game_id = arena.get("game_id")
    if not game_id:
        return {"arena_address": address, "leaderboard": []}

    leaderboard = game_engine.get_leaderboard(game_id)
    return {"arena_address": address, "leaderboard": leaderboard}


@api_router.post("/arenas/{address}/game/finish")
async def finish_arena_game(address: str, _: bool = Depends(verify_admin_key)):
    """Manually finish a game and determine winners"""
    arena = await db.arenas.find_one({"address": address})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")

    game_id = arena.get("game_id")
    if not game_id or game_id not in game_engine.active_games:
        raise HTTPException(status_code=400, detail="No active game session")

    game = game_engine.finish_game(game_id)

    # Store results
    await db.arenas.update_one(
        {"address": address},
        {"$set": {
            "game_status": "finished",
            "game_results": {
                "winners": game.winners,
                "player_scores": {p.address: p.score for p in game.players.values()}
            }
        }}
    )

    logger.info(f"Game {game_id} finished manually. Winners: {game.winners}")

    return {
        "success": True,
        "game_id": game_id,
        "winners": game.winners,
        "player_scores": {p.address: p.score for p in game.players.values()}
    }


# ===========================================
# USER AGENT ENDPOINTS
# ===========================================

class CreateAgentRequest(BaseModel):
    """Request to create a new user agent"""
    name: str
    strategy: str = "balanced"  # conservative, balanced, aggressive, random
    max_entry_fee_wei: str = "100000000000000000"  # 0.1 MON
    min_entry_fee_wei: str = "1000000000000000"     # 0.001 MON
    preferred_games: List[str] = []
    auto_join: bool = True
    daily_budget_wei: str = "0"

class UpdateAgentRequest(BaseModel):
    """Request to update an agent"""
    name: Optional[str] = None
    strategy: Optional[str] = None
    max_entry_fee_wei: Optional[str] = None
    min_entry_fee_wei: Optional[str] = None
    preferred_games: Optional[List[str]] = None
    auto_join: Optional[bool] = None
    daily_budget_wei: Optional[str] = None
    status: Optional[str] = None  # active, paused

class AgentResponse(BaseModel):
    """Agent details response"""
    agent_id: str
    owner_address: str
    name: str
    strategy: str
    max_entry_fee_wei: str
    min_entry_fee_wei: str
    preferred_games: List[str]
    auto_join: bool
    daily_budget_wei: str
    total_games: int
    total_wins: int
    total_earnings_wei: str
    total_spent_wei: str
    status: str
    current_game_id: Optional[str]
    created_at: str
    last_active_at: Optional[str]
    # Computed fields
    win_rate: float = 0.0
    net_profit_wei: str = "0"


def agent_to_response(agent: AgentConfig) -> AgentResponse:
    """Convert AgentConfig to response model"""
    win_rate = (agent.total_wins / agent.total_games * 100) if agent.total_games > 0 else 0.0
    net_profit = int(agent.total_earnings_wei) - int(agent.total_spent_wei)

    return AgentResponse(
        agent_id=agent.agent_id,
        owner_address=agent.owner_address,
        name=agent.name,
        strategy=agent.strategy.value,
        max_entry_fee_wei=agent.max_entry_fee_wei,
        min_entry_fee_wei=agent.min_entry_fee_wei,
        preferred_games=agent.preferred_games,
        auto_join=agent.auto_join,
        daily_budget_wei=agent.daily_budget_wei,
        total_games=agent.total_games,
        total_wins=agent.total_wins,
        total_earnings_wei=agent.total_earnings_wei,
        total_spent_wei=agent.total_spent_wei,
        status=agent.status.value,
        current_game_id=agent.current_game_id,
        created_at=agent.created_at,
        last_active_at=agent.last_active_at,
        win_rate=round(win_rate, 2),
        net_profit_wei=str(net_profit),
    )


@api_router.post("/agents/create", response_model=AgentResponse)
async def create_user_agent(
    request: CreateAgentRequest,
    owner_address: str = Query(..., description="Wallet address that owns this agent")
):
    """Create a new automated agent for a user"""
    # Validate strategy
    try:
        strategy = AgentStrategy(request.strategy)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid strategy: {request.strategy}")

    # Initialize manager with database
    user_agent_manager.db = db

    # Create the agent
    agent = await user_agent_manager.create_agent(
        owner_address=owner_address,
        name=request.name,
        strategy=strategy,
        max_entry_fee_wei=request.max_entry_fee_wei,
        min_entry_fee_wei=request.min_entry_fee_wei,
        preferred_games=request.preferred_games,
        auto_join=request.auto_join,
        daily_budget_wei=request.daily_budget_wei,
    )

    return agent_to_response(agent)


@api_router.get("/agents", response_model=List[AgentResponse])
async def get_user_agents(
    owner_address: str = Query(..., description="Wallet address to get agents for")
):
    """Get all agents owned by an address"""
    user_agent_manager.db = db
    agents = await user_agent_manager.get_agents_by_owner(owner_address)
    return [agent_to_response(a) for a in agents]


@api_router.get("/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str):
    """Get a specific agent by ID"""
    user_agent_manager.db = db
    agent = await user_agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent_to_response(agent)


@api_router.put("/agents/{agent_id}", response_model=AgentResponse)
async def update_user_agent(
    agent_id: str,
    request: UpdateAgentRequest,
    owner_address: str = Query(..., description="Owner wallet address for verification")
):
    """Update an agent's configuration"""
    user_agent_manager.db = db

    # Get the agent and verify ownership
    agent = await user_agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.owner_address.lower() != owner_address.lower():
        raise HTTPException(status_code=403, detail="Not authorized to modify this agent")

    # Build update dict
    updates = {}
    if request.name is not None:
        updates["name"] = request.name
    if request.strategy is not None:
        try:
            updates["strategy"] = AgentStrategy(request.strategy)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid strategy: {request.strategy}")
    if request.max_entry_fee_wei is not None:
        updates["max_entry_fee_wei"] = request.max_entry_fee_wei
    if request.min_entry_fee_wei is not None:
        updates["min_entry_fee_wei"] = request.min_entry_fee_wei
    if request.preferred_games is not None:
        updates["preferred_games"] = request.preferred_games
    if request.auto_join is not None:
        updates["auto_join"] = request.auto_join
    if request.daily_budget_wei is not None:
        updates["daily_budget_wei"] = request.daily_budget_wei
    if request.status is not None:
        try:
            updates["status"] = AgentStatus(request.status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {request.status}")

    if updates:
        await user_agent_manager.update_agent(agent_id, updates)

    # Return updated agent
    agent = await user_agent_manager.get_agent(agent_id)
    return agent_to_response(agent)


@api_router.delete("/agents/{agent_id}")
async def delete_user_agent(
    agent_id: str,
    owner_address: str = Query(..., description="Owner wallet address for verification")
):
    """Delete an agent (only owner can delete)"""
    user_agent_manager.db = db

    success = await user_agent_manager.delete_agent(agent_id, owner_address)
    if not success:
        raise HTTPException(status_code=404, detail="Agent not found or not authorized")

    return {"success": True, "message": "Agent deleted"}


@api_router.post("/agents/{agent_id}/start")
async def start_agent(
    agent_id: str,
    owner_address: str = Query(..., description="Owner wallet address for verification")
):
    """Start an agent (begin auto-joining games)"""
    user_agent_manager.db = db

    agent = await user_agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.owner_address.lower() != owner_address.lower():
        raise HTTPException(status_code=403, detail="Not authorized")

    success = await user_agent_manager.start_agent(agent_id)
    return {"success": success, "status": "active"}


@api_router.post("/agents/{agent_id}/stop")
async def stop_agent(
    agent_id: str,
    owner_address: str = Query(..., description="Owner wallet address for verification")
):
    """Stop an agent (pause auto-joining games)"""
    user_agent_manager.db = db

    agent = await user_agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.owner_address.lower() != owner_address.lower():
        raise HTTPException(status_code=403, detail="Not authorized")

    success = await user_agent_manager.stop_agent(agent_id)
    return {"success": success, "status": "paused"}


@api_router.get("/agents/{agent_id}/history")
async def get_agent_history(
    agent_id: str,
    limit: int = Query(default=20, le=100)
):
    """Get an agent's game history"""
    user_agent_manager.db = db

    agent = await user_agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Get game history from database
    cursor = db.agent_game_history.find(
        {"agent_id": agent_id}
    ).sort("played_at", -1).limit(limit)

    history = []
    async for record in cursor:
        record.pop('_id', None)
        history.append(record)

    return {"agent_id": agent_id, "history": history}


@api_router.post("/arenas/{address}/join-agent")
async def join_arena_with_agent(
    address: str,
    agent_id: str = Query(...),
    owner_address: str = Query(...),
):
    """Join an arena using an automated agent"""
    user_agent_manager.db = db

    # Verify agent ownership
    agent = await user_agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.owner_address.lower() != owner_address.lower():
        raise HTTPException(status_code=403, detail="Not authorized")

    # Get arena
    arena = await db.arenas.find_one({"address": address})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")

    # Check if arena is open
    if arena.get('is_closed') or arena.get('is_finalized'):
        raise HTTPException(status_code=400, detail="Arena is closed")

    # Check if arena has space
    players = arena.get('players', [])
    if len(players) >= arena.get('max_players', 8):
        raise HTTPException(status_code=400, detail="Arena is full")

    # Create agent player address (prefixed to identify as agent)
    agent_player_address = f"agent_{agent_id}"

    # Check if already joined
    if agent_player_address in players:
        raise HTTPException(status_code=400, detail="Agent already in arena")

    # Add agent to arena
    await db.arenas.update_one(
        {"address": address},
        {"$push": {"players": agent_player_address}}
    )

    logger.info(f"Agent {agent_id} joined arena {address}")

    return {
        "success": True,
        "agent_id": agent_id,
        "arena_address": address,
        "player_address": agent_player_address
    }


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

    # Initialize and start user agent manager
    user_agent_manager.db = db
    await user_agent_manager.start()
    logger.info("User Agent Manager initialized")
    
    # Start timer manager background task
    timer_manager.background_task = asyncio.create_task(timer_manager.process_timers())
    logger.info("Arena Timer Manager started")

@app.on_event("shutdown")
async def shutdown_db_client():
    # Stop user agent manager
    await user_agent_manager.stop()
    logger.info("User Agent Manager stopped")
    
    # Cancel timer manager task
    if timer_manager.background_task:
        timer_manager.background_task.cancel()
        try:
            await timer_manager.background_task
        except asyncio.CancelledError:
            pass
    logger.info("Arena Timer Manager stopped")

    client.close()
