from fastapi import FastAPI, APIRouter, HTTPException, Header, Depends, Query
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import random
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Literal, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import hashlib
import httpx
import time
from web3 import Web3
from eth_account import Account
import asyncio

# Minimal ArenaEscrow ABI for close/finalize
ARENA_ESCROW_ABI = [
    {
        "inputs": [],
        "name": "usedNonce",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {"inputs": [], "name": "closeRegistration", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [], "name": "cancelAndRefund", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {
        "inputs": [
            {"internalType": "address[]", "name": "winners", "type": "address[]"},
            {"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"},
            {"internalType": "bytes", "name": "signature", "type": "bytes"},
        ],
        "name": "finalize",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]

from game_engine import (
    GameType,
    GameEngine,
    GameState,
    GAME_RULES,
    get_game_rules_json,
    get_all_game_types,
    game_engine,
    TournamentMode,
)
from user_agents import (
    UserAgentManager,
    AgentConfig,
    AgentStrategy,
    AgentStatus,
    user_agent_manager,
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# MongoDB connection
mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get("DB_NAME", "claw_arena")]

# ===========================================
# Environment Configuration
# ===========================================

ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "")
DEFAULT_NETWORK = os.environ.get("DEFAULT_NETWORK", "testnet")

# Network Configuration
NETWORK_CONFIG = {
    "testnet": {
        "chain_id": int(os.environ.get("TESTNET_CHAIN_ID", "10143")),
        "rpc_url": os.environ.get("TESTNET_RPC_URL", "https://testnet-rpc.monad.xyz"),
        "explorer_url": os.environ.get("TESTNET_EXPLORER_URL", "https://testnet.monadexplorer.com"),
        "arena_factory": os.environ.get("TESTNET_ARENA_FACTORY_ADDRESS", ""),
        "treasury": os.environ.get("TESTNET_TREASURY_ADDRESS", ""),
    },
    "mainnet": {
        "chain_id": int(os.environ.get("MAINNET_CHAIN_ID", "143")),
        "rpc_url": os.environ.get("MAINNET_RPC_URL", "https://rpc.monad.xyz"),
        "explorer_url": os.environ.get("MAINNET_EXPLORER_URL", "https://monadscan.com"),
        "arena_factory": os.environ.get("MAINNET_ARENA_FACTORY_ADDRESS", ""),
        "treasury": os.environ.get("MAINNET_TREASURY_ADDRESS", ""),
    },
}

# Agent Signer Configuration
# Can use either the built-in agent_signer.py or OpenClaw Gateway
AGENT_SIGNER_URL = os.environ.get("AGENT_SIGNER_URL", "http://localhost:8002")
OPENCLAW_API_URL = os.environ.get("OPENCLAW_API_URL", "")
OPENCLAW_API_KEY = os.environ.get("OPENCLAW_API_KEY", "")
OPERATOR_ADDRESS = os.environ.get("OPERATOR_ADDRESS", "")

# Create the main app
app = FastAPI(title="CLAW ARENA API", version="1.0.0")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def _delete_arena_after_delay(arena_address: str, delay_seconds: int = 8):
    """Delete arena doc after a short delay (lets frontend show refund/cancel state)."""
    try:
        await asyncio.sleep(delay_seconds)
        await db.arenas.delete_one({"address": arena_address})
        logger.info(f"Deleted arena {arena_address} after delay {delay_seconds}s")
    except Exception as e:
        logger.error(f"Failed to delete arena {arena_address} after delay: {e}")


def _normalize_max_players(value: Any, default: int = 8) -> int:
    """
    Normalize max_players from DB/indexer payloads.
    Guarantees at least 2 so first join does not auto-close malformed arenas.
    """
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(2, parsed)


def _normalize_arena_doc(arena: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize arena docs loaded from DB/indexer so response_model validation remains stable.
    """
    normalized = dict(arena)
    address = normalized.get("address", "")

    normalized["address"] = address
    normalized["name"] = normalized.get("name") or f"Arena {address[:8]}"
    normalized["entry_fee"] = str(normalized.get("entry_fee", "0"))
    normalized["max_players"] = _normalize_max_players(normalized.get("max_players", 8))
    normalized["protocol_fee_bps"] = int(normalized.get("protocol_fee_bps", 250))
    normalized["treasury"] = normalized.get("treasury") or "0x0000000000000000000000000000000000000000"
    normalized["is_closed"] = bool(normalized.get("is_closed", False))
    normalized["is_finalized"] = bool(normalized.get("is_finalized", False))
    normalized["players"] = normalized.get("players", []) or []
    normalized["created_at"] = normalized.get("created_at") or datetime.now(timezone.utc).isoformat()
    normalized["network"] = normalized.get("network") or DEFAULT_NETWORK
    normalized["created_by"] = normalized.get("created_by") or "indexer"
    normalized["game_status"] = normalized.get("game_status") or "waiting"

    return normalized

# ===========================================
# ARENA TIMER MANAGEMENT
# ===========================================


class ArenaTimerManager:
    def __init__(self):
        self.timers = {}  # timer_key -> timer_data
        self.background_task = None

    @staticmethod
    def _timer_key(arena_address: str, timer_type: str) -> str:
        return f"{arena_address}:{timer_type}"

    @staticmethod
    def _parse_iso(ts: str) -> datetime:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))

    async def cancel_timer(self, arena_address: str, timer_type: Optional[str] = None):
        """Cancel one timer type for an arena, or all timers if timer_type is None."""
        if timer_type:
            self.timers.pop(self._timer_key(arena_address, timer_type), None)
        else:
            keys = [k for k in self.timers.keys() if k.startswith(f"{arena_address}:")]
            for key in keys:
                self.timers.pop(key, None)

    async def _set_registration_fields(self, arena_address: str, ends_at: str):
        await db.arenas.update_one(
            {"address": arena_address},
            {"$set": {"registration_deadline": ends_at, "idle_starts_at": datetime.now(timezone.utc).isoformat(), "idle_ends_at": ends_at}},
        )

    async def _clear_registration_fields(self, arena_address: str):
        await db.arenas.update_one(
            {"address": arena_address},
            {"$unset": {"idle_starts_at": "", "idle_ends_at": "", "registration_deadline": ""}},
        )

    async def start_registration_timer(self, arena_address: str, countdown_seconds: int = 60):
        """
        Start (or reset) the registration countdown.
        If countdown expires with <2 players, refund; with >=2 players, game starts.
        """
        ends_at = (datetime.now(timezone.utc) + timedelta(seconds=countdown_seconds)).isoformat()
        key = self._timer_key(arena_address, "registration_countdown")
        self.timers[key] = {
            "arena_address": arena_address,
            "type": "registration_countdown",
            "ends_at": ends_at,
            "countdown_seconds": countdown_seconds,
        }
        await self._set_registration_fields(arena_address, ends_at)
        logger.info(f"Started registration countdown for {arena_address}: {countdown_seconds}s")

    async def start_idle_timer(self, arena_address: str, idle_seconds: int = 60):
        """
        Backward-compatible wrapper.
        Existing admin endpoint still calls this, so keep behavior aligned.
        """
        ends_at = (datetime.now(timezone.utc) + timedelta(seconds=idle_seconds)).isoformat()
        key = self._timer_key(arena_address, "idle_timer")
        self.timers[key] = {
            "arena_address": arena_address,
            "type": "idle_timer",
            "ends_at": ends_at,
            "idle_ends_at": ends_at,
            "idle_seconds": idle_seconds,
        }
        await db.arenas.update_one(
            {"address": arena_address},
            {"$set": {"idle_starts_at": datetime.now(timezone.utc).isoformat(), "idle_ends_at": ends_at}},
        )
        logger.info(f"Started idle timer for {arena_address}: {idle_seconds}s")

    async def start_game_countdown(self, arena_address: str, countdown_seconds: int = 10):
        """Start short countdown after registration closes before learning phase begins."""
        ends_at = (datetime.now(timezone.utc) + timedelta(seconds=countdown_seconds)).isoformat()
        key = self._timer_key(arena_address, "game_start_countdown")
        self.timers[key] = {
            "arena_address": arena_address,
            "type": "game_start_countdown",
            "ends_at": ends_at,
            "countdown_ends_at": ends_at,
            "countdown_seconds": countdown_seconds,
        }
        await db.arenas.update_one(
            {"address": arena_address},
            {"$set": {"countdown_ends_at": ends_at}},
        )
        logger.info(f"Started game countdown for {arena_address}: {countdown_seconds}s")

    async def start_round_timer(self, arena_address: str, game_id: str, round_number: int, seconds: int):
        """Advance to next round automatically when round timer expires."""
        ends_at = (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()
        key = self._timer_key(arena_address, "round_timer")
        self.timers[key] = {
            "arena_address": arena_address,
            "type": "round_timer",
            "game_id": game_id,
            "round_number": round_number,
            "ends_at": ends_at,
            "round_seconds": seconds,
        }
        await db.arenas.update_one({"address": arena_address}, {"$set": {"round_ends_at": ends_at}})

    async def start_learning_phase_timer(self, arena_address: str, learning_seconds: int):
        ends_at = (datetime.now(timezone.utc) + timedelta(seconds=learning_seconds)).isoformat()
        key = self._timer_key(arena_address, "learning_phase")
        self.timers[key] = {
            "arena_address": arena_address,
            "type": "learning_phase",
            "ends_at": ends_at,
            "learning_seconds": learning_seconds,
        }
        await db.arenas.update_one(
            {"address": arena_address},
            {"$set": {"learning_phase_end": ends_at}},
        )
        logger.info(f"Started learning phase for {arena_address}: {learning_seconds}s")

    async def start_game_end_timer(self, arena_address: str, ends_at: str):
        key = self._timer_key(arena_address, "game_end")
        self.timers[key] = {
            "arena_address": arena_address,
            "type": "game_end",
            "ends_at": ends_at,
        }
        await db.arenas.update_one({"address": arena_address}, {"$set": {"tournament_end_estimate": ends_at}})

    async def get_timer_status(self, arena_address: str):
        """
        Return a single most-relevant timer for compatibility with existing admin API.
        Priority: game_start_countdown > registration_countdown > idle_timer > learning_phase > round_timer > game_end
        """
        priority = [
            "game_start_countdown",
            "registration_countdown",
            "idle_timer",
            "learning_phase",
            "round_timer",
            "game_end",
        ]
        for timer_type in priority:
            timer = self.timers.get(self._timer_key(arena_address, timer_type))
            if timer:
                if timer_type == "registration_countdown":
                    return {
                        "type": timer_type,
                        "registration_ends_at": timer["ends_at"],
                        "countdown_seconds": timer["countdown_seconds"],
                    }
                if timer_type == "game_start_countdown":
                    return {
                        "type": timer_type,
                        "countdown_ends_at": timer["countdown_ends_at"],
                        "countdown_seconds": timer["countdown_seconds"],
                    }
                if timer_type == "idle_timer":
                    return {
                        "type": timer_type,
                        "idle_ends_at": timer["idle_ends_at"],
                        "idle_seconds": timer["idle_seconds"],
                    }
                return {"type": timer_type, "ends_at": timer["ends_at"]}
        return None

    async def _handle_registration_expiration(self, arena_address: str):
        """
        At registration expiry:
        - 0 players: clear timer and keep arena open.
        - 1 player: cancel/refund and mark arena cancelled/finalized.
        - 2+ players: close registration and start game countdown.
        """
        try:
            arena = await db.arenas.find_one({"address": arena_address})
            if not arena:
                return

            players = arena.get("players", [])
            player_count = len(players)
            await self._clear_registration_fields(arena_address)

            if player_count == 0:
                logger.info(f"Registration expired for {arena_address} with 0 players; arena left open")
                return

            if player_count == 1:
                try:
                    network = arena.get("network", DEFAULT_NETWORK)
                    refund_tx = await _cancel_and_refund_onchain(arena_address, network)
                    player = players[0]
                    refund_amount = arena.get("entry_fee", "0")
                    await db.refunds.insert_one(
                        {
                            "arena_address": arena_address,
                            "player_address": player,
                            "amount": refund_amount,
                            "tx_hash": refund_tx,
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    await db.arenas.update_one(
                        {"address": arena_address},
                        {
                            "$set": {
                                "is_closed": True,
                                "is_finalized": True,
                                "is_cancelled": True,
                                "cancelled_at": datetime.now(timezone.utc).isoformat(),
                                "refund_tx_hash": refund_tx,
                                "closed_at": datetime.now(timezone.utc).isoformat(),
                                "game_status": "cancelled",
                            },
                            "$unset": {"countdown_ends_at": "", "round_ends_at": ""},
                        },
                    )
                    logger.info(f"Registration expired with 1 player. Refunded arena {arena_address}. Tx: {refund_tx}")
                except Exception as e:
                    logger.error(f"Refund failed for {arena_address}: {e}")
                return

            # 2+ players: close registration and start game flow
            await db.arenas.update_one(
                {"address": arena_address},
                {"$set": {"is_closed": True, "closed_at": datetime.now(timezone.utc).isoformat()}},
            )
            network = arena.get("network", DEFAULT_NETWORK)
            try:
                close_tx = await _close_registration_onchain(arena_address, network)
                await db.arenas.update_one({"address": arena_address}, {"$set": {"close_tx_hash": close_tx}})
            except Exception as e:
                logger.error(f"Failed to close registration on-chain for {arena_address}: {e}")

            await self.start_game_countdown(arena_address, countdown_seconds=10)

        except Exception as e:
            logger.error(f"Error handling registration expiration for {arena_address}: {e}")

    async def _handle_idle_expiration(self, arena_address: str):
        """Backward-compatible idle timer expiration (same behavior as registration)."""
        await self._handle_registration_expiration(arena_address)

    async def process_timers(self):
        """Background loop to check for expired timers."""
        while True:
            try:
                now = datetime.now(timezone.utc)
                expired_keys = [k for k, t in self.timers.items() if now >= self._parse_iso(t["ends_at"])]

                for key in expired_keys:
                    timer = self.timers.pop(key, None)
                    if not timer:
                        continue

                    arena_address = timer["arena_address"]
                    timer_type = timer["type"]

                    if timer_type == "registration_countdown":
                        await self._handle_registration_expiration(arena_address)
                    elif timer_type == "idle_timer":
                        await self._handle_idle_expiration(arena_address)
                    elif timer_type == "game_start_countdown":
                        await self._trigger_game_start(arena_address)
                    elif timer_type == "learning_phase":
                        await self._activate_game_after_learning(arena_address)
                    elif timer_type == "round_timer":
                        await self._advance_round_on_timer(arena_address, timer)
                    elif timer_type == "game_end":
                        await self._finish_game_on_timer(arena_address)
            except Exception as e:
                logger.error(f"Timer loop error: {e}")
            await asyncio.sleep(1)

    async def _trigger_game_start(self, arena_address: str):
        """Create game and enter learning phase after the short post-registration countdown."""
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

            # Create game in learning phase first
            game = game_engine.create_game(arena_address=arena_address, game_type=game_type, players=players)
            game_id = game.game_id
            learning_seconds = int(arena.get("learning_phase_seconds", 60))
            learning_start = datetime.now(timezone.utc).isoformat()
            learning_end = (datetime.now(timezone.utc) + timedelta(seconds=learning_seconds)).isoformat()

            await db.arenas.update_one(
                {"address": arena_address},
                {
                    "$set": {
                        "game_id": game_id,
                        "game_status": "learning",
                        "learning_phase_start": learning_start,
                        "learning_phase_end": learning_end,
                    }
                },
            )

            await self.start_learning_phase_timer(arena_address, learning_seconds=learning_seconds)
            logger.info(f"Game created for arena {arena_address}, game_id: {game_id}, learning={learning_seconds}s")

        except Exception as e:
            logger.error(f"Error triggering game start for arena {arena_address}: {e}")

    async def _activate_game_after_learning(self, arena_address: str):
        """Move game from learning -> active, then schedule round/game timers."""
        try:
            arena = await db.arenas.find_one({"address": arena_address})
            if not arena:
                return

            game_id = arena.get("game_id")
            if not game_id or game_id not in game_engine.active_games:
                logger.error(f"Cannot activate game for {arena_address}; missing game_id")
                return

            game = game_engine.active_games[game_id]
            if game.status != "active":
                game_engine.start_game(game_id)

            await db.arenas.update_one(
                {"address": arena_address},
                {
                    "$set": {
                        "game_status": "active",
                        "game_start": datetime.now(timezone.utc).isoformat(),
                        "tournament_end_estimate": game.ends_at,
                    },
                    "$unset": {"countdown_ends_at": ""},
                },
            )

            round_seconds = int(game.current_challenge.get("time_limit", 20)) if game.current_challenge else 20
            await self.start_round_timer(arena_address, game_id, game.round_number, round_seconds)
            if game.ends_at:
                await self.start_game_end_timer(arena_address, game.ends_at)

            logger.info(f"Game activated for arena {arena_address}, game_id: {game_id}")
        except Exception as e:
            logger.error(f"Error activating game for {arena_address}: {e}")

    async def _advance_round_on_timer(self, arena_address: str, timer: Dict[str, Any]):
        """Advance game round when round timer expires."""
        try:
            game_id = timer.get("game_id")
            expected_round = timer.get("round_number")
            if not game_id or game_id not in game_engine.active_games:
                return

            game = game_engine.active_games[game_id]
            if game.status != "active":
                return

            # Ignore stale timer from a previous round
            if expected_round is not None and int(expected_round) != int(game.round_number):
                return

            next_state = game_engine.advance_round(game_id)
            if not next_state:
                return

            if next_state.status == "finished":
                await db.arenas.update_one({"address": arena_address}, {"$set": {"game_status": "finished"}})
                await self.cancel_timer(arena_address, "game_end")
                await self._process_game_winners(arena_address, game_id)
                return

            round_seconds = int(next_state.current_challenge.get("time_limit", 20)) if next_state.current_challenge else 20
            await self.start_round_timer(arena_address, game_id, next_state.round_number, round_seconds)
        except Exception as e:
            logger.error(f"Error advancing round for {arena_address}: {e}")

    async def _finish_game_on_timer(self, arena_address: str):
        """Finish game when its absolute end timestamp is reached."""
        try:
            arena = await db.arenas.find_one({"address": arena_address})
            if not arena:
                return

            game_id = arena.get("game_id")
            if not game_id or game_id not in game_engine.active_games:
                return

            game = game_engine.active_games[game_id]
            if game.status != "finished":
                game_engine.finish_game(game_id)
                await db.arenas.update_one({"address": arena_address}, {"$set": {"game_status": "finished"}})

            await self.cancel_timer(arena_address, "round_timer")
            await self._process_game_winners(arena_address, game_id)
        except Exception as e:
            logger.error(f"Error finishing game on timer for {arena_address}: {e}")

    async def _process_game_winners(self, arena_address: str, game_id: str):
        """
        Extract winners from finished game and calculate payouts.
        Store results in MongoDB arena document.
        """
        try:
            arena = await db.arenas.find_one({"address": arena_address})
            if not arena:
                logger.error(f"Arena {arena_address} not found for winner processing")
                return

            if game_id not in game_engine.active_games:
                logger.error(f"Game {game_id} not found for winner processing")
                return

            game = game_engine.active_games[game_id]

            if game.status != "finished":
                logger.warning(f"Game {game_id} is not finished, cannot process winners")
                return

            winners = game.winners if game.winners else []
            if not winners:
                logger.warning(f"Game {game_id} has no winners")
                return

            player_scores = {p.address: p.score for p in game.players.values()}

            entry_fee = int(arena.get("entry_fee", "0"))
            protocol_fee_bps = int(arena.get("protocol_fee_bps", 250))
            players = arena.get("players", [])
            player_count = len(players)

            total_pool = entry_fee * player_count
            protocol_fee = int(total_pool * protocol_fee_bps / 10000)
            available_for_winners = total_pool - protocol_fee

            payout_per_winner = available_for_winners // len(winners)
            remainder = available_for_winners % len(winners)

            payout_amounts = []
            for i in range(len(winners)):
                amount = payout_per_winner + (remainder if i == 0 else 0)
                payout_amounts.append(str(amount))

            await db.arenas.update_one(
                {"address": arena_address},
                {
                    "$set": {
                        "game_status": "finished",
                        "winners": winners,
                        "payouts": payout_amounts,
                        "game_results": {
                            "winners": winners,
                            "player_scores": player_scores,
                            "total_pool": str(total_pool),
                            "protocol_fee": str(protocol_fee),
                            "payout_per_winner": str(payout_per_winner),
                            "remainder": str(remainder),
                            "finished_at": datetime.now(timezone.utc).isoformat(),
                        },
                    }
                },
            )

            for winner, amount in zip(winners, payout_amounts):
                payout = PayoutRecord(arena_address=arena_address, winner_address=winner, amount=amount, tx_hash="")
                await db.payouts.insert_one(payout.model_dump())

            for winner, amount in zip(winners, payout_amounts):
                current = await db.leaderboard.find_one({"address": winner})
                current_payouts = int(current.get("total_payouts", "0")) if current else 0
                new_payouts = current_payouts + int(amount)

                await db.leaderboard.update_one(
                    {"address": winner},
                    {"$set": {"total_payouts": str(new_payouts)}, "$inc": {"total_wins": 1, "tournaments_won": 1}},
                    upsert=True,
                )

            try:
                network = arena.get("network", os.environ.get("DEFAULT_NETWORK", "testnet"))
                finalize_tx = await _finalize_onchain(arena_address, winners, payout_amounts, network)
                await db.arenas.update_one(
                    {"address": arena_address},
                    {
                        "$set": {
                            "is_finalized": True,
                            "finalize_tx_hash": finalize_tx,
                            "tx_hash": finalize_tx,
                            "finalized_at": datetime.now(timezone.utc).isoformat(),
                        }
                    },
                )
                await db.payouts.update_many({"arena_address": arena_address}, {"$set": {"tx_hash": finalize_tx}})
            except Exception as e:
                logger.error(f"On-chain finalization failed for arena {arena_address}: {e}")

            logger.info(f"Processed winners for arena {arena_address}: {winners}, payouts: {payout_amounts}")

        except Exception as e:
            logger.error(f"Error processing game winners for {arena_address}: {e}")

timer_manager = ArenaTimerManager()


def _get_rpc_url_for_network(network: str) -> str:
    if network == "mainnet":
        return os.environ.get("MAINNET_RPC_URL", "https://rpc.monad.xyz")
    return os.environ.get("TESTNET_RPC_URL", "https://testnet-rpc.monad.xyz")


def _get_chain_id_for_network(network: str) -> int:
    if network == "mainnet":
        return int(os.environ.get("MAINNET_CHAIN_ID", "143"))
    return int(os.environ.get("TESTNET_CHAIN_ID", "10143"))


def _get_operator_account() -> Account:
    pk = os.environ.get("OPERATOR_PRIVATE_KEY", "")
    if not pk:
        raise RuntimeError("OPERATOR_PRIVATE_KEY not set (needed to submit closeRegistration/finalize txs)")
    return Account.from_key(pk)


def _send_contract_tx(w3: Web3, contract, fn, account: Account, value_wei: int = 0) -> str:
    nonce = w3.eth.get_transaction_count(account.address)
    tx = fn.build_transaction(
        {
            "from": account.address,
            "nonce": nonce,
            "gas": 500000,
            "gasPrice": w3.eth.gas_price,
            "value": value_wei,
            "chainId": w3.eth.chain_id,
        }
    )
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    return tx_hash.hex()


async def _close_registration_onchain(arena_address: str, network: str) -> str:
    rpc = _get_rpc_url_for_network(network)
    w3 = Web3(Web3.HTTPProvider(rpc))
    account = _get_operator_account()
    escrow = w3.eth.contract(address=Web3.to_checksum_address(arena_address), abi=ARENA_ESCROW_ABI)
    txh = _send_contract_tx(w3, escrow, escrow.functions.closeRegistration(), account)
    return txh


async def _cancel_and_refund_onchain(arena_address: str, network: str) -> str:
    """Call cancelAndRefund() on the ArenaEscrow contract to refund players if <2 joined."""
    config = get_network_config(network)
    if not config.rpc_url:
        raise Exception("RPC URL not configured")
    operator_private_key = os.environ.get("OPERATOR_PRIVATE_KEY", "")
    if not operator_private_key:
        raise Exception("OPERATOR_PRIVATE_KEY not configured")

    w3 = Web3(Web3.HTTPProvider(config.rpc_url))
    acct = Account.from_key(operator_private_key)
    contract = w3.eth.contract(address=Web3.to_checksum_address(arena_address), abi=ARENA_ESCROW_ABI)

    nonce = w3.eth.get_transaction_count(acct.address)
    tx = contract.functions.cancelAndRefund().build_transaction(
        {
            "from": acct.address,
            "nonce": nonce,
            "gas": 350000,
            "maxFeePerGas": w3.to_wei("2", "gwei"),
            "maxPriorityFeePerGas": w3.to_wei("1", "gwei"),
            "chainId": config.chain_id,
        }
    )
    signed = acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    return tx_hash.hex()


async def _finalize_onchain(arena_address: str, winners: list, amounts: list, network: str) -> str:
    rpc = _get_rpc_url_for_network(network)
    w3 = Web3(Web3.HTTPProvider(rpc))
    account = _get_operator_account()
    escrow = w3.eth.contract(address=Web3.to_checksum_address(arena_address), abi=ARENA_ESCROW_ABI)

    used = escrow.functions.usedNonce().call()
    nonce_to_sign = int(used) + 1

    chain_id = _get_chain_id_for_network(network)
    signer_url = os.environ.get("AGENT_SIGNER_URL", "http://localhost:8002").rstrip("/")
    payload = {
        "arena_address": arena_address,
        "winners": winners,
        "amounts": [str(a) for a in amounts],
        "nonce": nonce_to_sign,
        "chain_id": chain_id,
    }

    async with httpx.AsyncClient(timeout=20) as http_client:
        r = await http_client.post(f"{signer_url}/sign", json=payload)
        r.raise_for_status()
        sig = r.json().get("signature")
        if not sig:
            raise RuntimeError("Signer did not return signature")

    txh = _send_contract_tx(
        w3,
        escrow,
        escrow.functions.finalize(
            [Web3.to_checksum_address(w) for w in winners],
            [int(a) for a in amounts],
            Web3.to_bytes(hexstr=sig),
        ),
        account,
    )
    return txh


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
    game_type: Optional[str] = None
    game_config: Optional[Dict[str, Any]] = None
    learning_phase_seconds: int = 60


class Arena(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    address: str
    name: str
    entry_fee: str
    max_players: int
    protocol_fee_bps: int
    treasury: str
    network: str = DEFAULT_NETWORK
    players: List[str] = []
    is_closed: bool = False
    is_finalized: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    closed_at: Optional[str] = None
    finalized_at: Optional[str] = None
    winners: List[str] = []
    payouts: List[str] = []
    tx_hash: Optional[str] = None
    registration_deadline: Optional[str] = None
    tournament_end_estimate: Optional[str] = None
    created_by: str = "admin"
    creation_reason: Optional[str] = None
    game_type: Optional[str] = None
    game_config: Optional[Dict[str, Any]] = None
    game_id: Optional[str] = None
    game_status: Optional[str] = None
    learning_phase_start: Optional[str] = None
    learning_phase_end: Optional[str] = None
    game_start: Optional[str] = None
    game_results: Optional[Dict[str, Any]] = None
    learning_phase_seconds: int = 60


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


class FinalizeRecordRequest(BaseModel):
    tx_hash: str
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
    arena_address: str
    player_address: str
    move_data: Dict[str, Any]


class GameMoveResponse(BaseModel):
    success: bool
    message: str
    player_score: Optional[int] = None
    game_state: Optional[Dict[str, Any]] = None


class GameRulesResponse(BaseModel):
    game_type: str
    name: str
    description: str
    how_to_play: List[str]
    tips: List[str]
    duration_seconds: int
    min_players: int
    max_players: int


class GameStateResponse(BaseModel):
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
    if network not in NETWORK_CONFIG:
        raise HTTPException(status_code=400, detail=f"Invalid network: {network}. Use 'testnet' or 'mainnet'")
    config = NETWORK_CONFIG[network]
    return NetworkConfig(**config)


# ===========================================
# AGENT SIGNING SERVICE
# ===========================================


async def request_agent_signature(
    arena_address: str, winners: List[str], amounts: List[str], nonce: int, chain_id: int
) -> dict:
    """
    Request EIP-712 signature from Agent Signer service.
    Uses the built-in agent_signer.py or OpenClaw Gateway.
    Returns signature data for finalize transaction.
    """
    signer_url = AGENT_SIGNER_URL or OPENCLAW_API_URL

    if not signer_url:
        raise HTTPException(
            status_code=500, detail="No signing service configured. Set AGENT_SIGNER_URL or OPENCLAW_API_URL."
        )

    async with httpx.AsyncClient() as http_client:
        try:
            payload = {"arena_address": arena_address, "winners": winners, "amounts": amounts, "nonce": nonce, "chain_id": chain_id}

            headers = {"Content-Type": "application/json"}
            if OPENCLAW_API_KEY:
                headers["Authorization"] = f"Bearer {OPENCLAW_API_KEY}"

            logger.info(f"Requesting signature from {signer_url}/sign")

            response = await http_client.post(f"{signer_url}/sign", headers=headers, json=payload, timeout=30.0)

            if response.status_code != 200:
                logger.error(f"Signer API error: {response.status_code} - {response.text}")
                raise HTTPException(status_code=502, detail=f"Signing service error: {response.text}")

            result = response.json()
            signature = result.get("signature")

            if not signature:
                raise HTTPException(status_code=502, detail="Signing service did not return a signature")

            global OPERATOR_ADDRESS
            if result.get("operator_address") and not OPERATOR_ADDRESS:
                OPERATOR_ADDRESS = result.get("operator_address")

            return {
                "signature": signature,
                "operator_address": result.get("operator_address", OPERATOR_ADDRESS),
                "domain": result.get("domain", {}),
                "types": result.get("types", {}),
                "message": result.get("message", {}),
            }

        except httpx.RequestError as e:
            logger.error(f"Signing service request failed: {e}")
            raise HTTPException(
                status_code=502,
                detail=f"Failed to connect to signing service: {str(e)}. Make sure agent_signer.py is running.",
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
        "openclaw_configured": bool(OPENCLAW_API_URL and OPENCLAW_API_KEY),
    }


@api_router.get("/config")
async def get_config(network: str = Query(default=DEFAULT_NETWORK)):
    config = get_network_config(network)
    return {
        "network": network,
        "chain_id": config.chain_id,
        "rpc_url": config.rpc_url,
        "explorer_url": config.explorer_url,
        "arena_factory": config.arena_factory,
        "treasury": config.treasury,
        "operator_address": OPERATOR_ADDRESS,
    }


@api_router.get("/arenas", response_model=List[Arena])
async def get_arenas(network: str = Query(default=None)):
    query = {}
    if network:
        query["network"] = network
    arenas = await db.arenas.find(query, {"_id": 0}).to_list(100)
    return [_normalize_arena_doc(a) for a in arenas]


@api_router.get("/arenas/{address}", response_model=Arena)
async def get_arena(address: str):
    arena = await db.arenas.find_one({"address": address}, {"_id": 0})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")
    return _normalize_arena_doc(arena)


@api_router.get("/leaderboard", response_model=List[LeaderboardEntry])
async def get_leaderboard(limit: int = 50, network: str = Query(default=None)):
    leaderboard = await db.leaderboard.find({}, {"_id": 0}).sort("total_payouts", -1).to_list(limit)
    return leaderboard


@api_router.get("/arenas/{address}/players")
async def get_arena_players(address: str):
    joins = await db.joins.find({"arena_address": address}, {"_id": 0}).to_list(100)
    return {"arena_address": address, "players": [j["player_address"] for j in joins]}




@api_router.get("/arenas/{address}/refunds")
async def get_arena_refunds(address: str):
    refunds = await db.refunds.find({"arena_address": address}, {"_id": 0}).to_list(100)
    return {"arena_address": address, "refunds": refunds}
@api_router.get("/arenas/{address}/payouts")
async def get_arena_payouts(address: str):
    payouts = await db.payouts.find({"arena_address": address}, {"_id": 0}).to_list(100)
    return {"arena_address": address, "payouts": payouts}


# ===========================================
# AGENT STATUS & SCHEDULE ENDPOINTS
# ===========================================


@api_router.get("/agent/status")
async def get_agent_status():
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
    schedule = await db.agent_schedule.find_one({"_id": "current"}, {"_id": 0})

    active_arenas = await db.arenas.find({"is_finalized": False}, {"_id": 0}).sort("created_at", -1).to_list(20)
    recent_completed = await db.arenas.find({"is_finalized": True}, {"_id": 0}).sort("finalized_at", -1).to_list(5)

    now = datetime.now(timezone.utc)

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

        reg_deadline = arena.get("registration_deadline")
        if reg_deadline and not arena.get("is_closed"):
            try:
                dl_dt = datetime.fromisoformat(reg_deadline.replace("Z", "+00:00"))
                diff = (dl_dt - now).total_seconds()
                item["registration_deadline"] = reg_deadline
                item["registration_countdown_seconds"] = max(0, int(diff))
            except (ValueError, TypeError):
                pass

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
            {"address": a.get("address"), "name": a.get("name"), "finalized_at": a.get("finalized_at"), "winners": a.get("winners", [])}
            for a in recent_completed
        ],
    }


@api_router.post("/agent/update-schedule")
async def update_agent_schedule(
    next_tournament_at: Optional[str] = None,
    status: str = "active",
    last_analysis: Optional[dict] = None,
    _: bool = Depends(verify_admin_key),
):
    update_data = {"status": status, "last_cycle_at": datetime.now(timezone.utc).isoformat()}

    if next_tournament_at:
        update_data["next_tournament_at"] = next_tournament_at

    if last_analysis:
        update_data["last_analysis"] = last_analysis

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    current = await db.agent_schedule.find_one({"_id": "current"})
    if current and current.get("date") == today:
        update_data["tournaments_created_today"] = current.get("tournaments_created_today", 0)
    else:
        update_data["tournaments_created_today"] = 0
        update_data["date"] = today

    await db.agent_schedule.update_one({"_id": "current"}, {"$set": update_data}, upsert=True)
    return {"success": True, "message": "Agent schedule updated"}


@api_router.post("/agent/tournament-created")
async def agent_tournament_created(_: bool = Depends(verify_admin_key)):
    await db.agent_schedule.update_one({"_id": "current"}, {"$inc": {"tournaments_created_today": 1}}, upsert=True)
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

    max_players_initial = _normalize_max_players(arena.get("max_players", 8))
    if arena.get("max_players") != max_players_initial:
        await db.arenas.update_one({"address": join_data.arena_address}, {"$set": {"max_players": max_players_initial}})

    if len(arena.get("players", [])) >= max_players_initial:
        raise HTTPException(status_code=400, detail="Arena is full")

    if join_data.player_address in arena.get("players", []):
        raise HTTPException(status_code=400, detail="Player already joined")

    join_record = PlayerJoin(arena_address=join_data.arena_address, player_address=join_data.player_address, tx_hash=join_data.tx_hash)
    await db.joins.insert_one(join_record.model_dump())

    await db.arenas.update_one({"address": join_data.arena_address}, {"$push": {"players": join_data.player_address}})

    await db.leaderboard.update_one(
        {"address": join_data.player_address},
        {"$setOnInsert": {"address": join_data.player_address, "total_wins": 0, "total_payouts": "0", "tournaments_won": 0}, "$inc": {"tournaments_played": 1}},
        upsert=True,
    )

    logger.info(f"Player {join_data.player_address} joined arena {join_data.arena_address}")

    updated_arena = await db.arenas.find_one({"address": join_data.arena_address})
    players = updated_arena.get("players", [])
    max_players = _normalize_max_players(updated_arena.get("max_players", 8))
    if updated_arena.get("max_players") != max_players:
        await db.arenas.update_one({"address": join_data.arena_address}, {"$set": {"max_players": max_players}})

    response = {"success": True, "message": "Player joined arena", "tx_hash": join_data.tx_hash}

    if len(players) >= max_players and not updated_arena.get("is_closed"):
        await timer_manager.cancel_timer(join_data.arena_address, "registration_countdown")
        await timer_manager.cancel_timer(join_data.arena_address, "idle_timer")

        await db.arenas.update_one(
            {"address": join_data.arena_address},
            {"$set": {"is_closed": True, "closed_at": datetime.now(timezone.utc).isoformat()}},
        )

        try:
            network = updated_arena.get("network", os.environ.get("DEFAULT_NETWORK", "testnet"))
            close_tx = await _close_registration_onchain(join_data.arena_address, network)
            await db.arenas.update_one({"address": join_data.arena_address}, {"$set": {"close_tx_hash": close_tx}})
        except Exception as e:
            logger.error(f"Failed to close registration on-chain for {join_data.arena_address}: {e}")

        await timer_manager.start_game_countdown(join_data.arena_address, countdown_seconds=10)

        response["arena_full"] = True
        response["countdown_starts"] = True
        response["countdown_seconds"] = 10
        logger.info(f"Arena {join_data.arena_address} is now full, starting game countdown")

    elif len(players) == 1 and not updated_arena.get("is_closed"):
        # Core flow: once first player joins, start 60s registration countdown.
        await timer_manager.start_registration_timer(join_data.arena_address, countdown_seconds=60)
        response["registration_timer_started"] = True
        response["registration_seconds"] = 60
        logger.info(f"Arena {join_data.arena_address} first join -> registration countdown started (60s)")

    elif len(players) >= 2 and not updated_arena.get("is_closed"):
        # Keep registration window open for countdown duration.
        if not updated_arena.get("registration_deadline"):
            await timer_manager.start_registration_timer(join_data.arena_address, countdown_seconds=60)
        response["registration_open"] = True
        response["player_count"] = len(players)
        logger.info(f"Arena {join_data.arena_address} has {len(players)} players; waiting for registration countdown")

    return response


# ===========================================
# ADMIN ENDPOINTS
# ===========================================


@api_router.post("/admin/arena/create", response_model=Arena)
async def create_arena(
    arena_data: ArenaCreate, network: str = Query(default=DEFAULT_NETWORK), _: bool = Depends(verify_admin_key)
):
    config = get_network_config(network)

    if arena_data.max_players < 2:
        raise HTTPException(status_code=400, detail="max_players must be at least 2")

    if not arena_data.contract_address.startswith("0x") or len(arena_data.contract_address) != 42:
        raise HTTPException(status_code=400, detail="Invalid contract address format")

    existing = await db.arenas.find_one({"address": arena_data.contract_address})
    if existing:
        raise HTTPException(status_code=400, detail="Arena with this address already exists")

    game_type = arena_data.game_type
    if not game_type:
        game_type = random.choice(["claw", "prediction", "speed", "blackjack"])

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
        learning_phase_seconds=arena_data.learning_phase_seconds,
    )

    await db.arenas.insert_one(arena.model_dump())
    logger.info(f"Created arena {arena.name} at {arena_data.contract_address} on {network} with game: {game_type}")
    return arena


@api_router.post("/admin/arena/{address}/close")
async def close_arena(address: str, _: bool = Depends(verify_admin_key)):
    arena = await db.arenas.find_one({"address": address})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")

    if arena.get("is_closed"):
        raise HTTPException(status_code=400, detail="Arena is already closed")

    await db.arenas.update_one({"address": address}, {"$set": {"is_closed": True, "closed_at": datetime.now(timezone.utc).isoformat()}})
    logger.info(f"Closed arena {address}")
    return {"success": True, "message": "Arena registration closed"}


@api_router.post("/admin/arena/request-finalize-signature", response_model=FinalizeSignatureResponse)
async def request_finalize_signature(request: FinalizeRequest, _: bool = Depends(verify_admin_key)):
    arena = await db.arenas.find_one({"address": request.arena_address})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")

    if arena.get("is_finalized"):
        raise HTTPException(status_code=400, detail="Arena is already finalized")

    if not arena.get("is_closed"):
        raise HTTPException(status_code=400, detail="Arena registration must be closed first")

    if len(request.winners) != len(request.amounts):
        raise HTTPException(status_code=400, detail="Winners and amounts arrays must have same length")

    if len(request.winners) == 0:
        raise HTTPException(status_code=400, detail="Must have at least one winner")

    network = arena.get("network", DEFAULT_NETWORK)
    config = get_network_config(network)

    nonce = await db.nonces.count_documents({}) + 1
    await db.nonces.insert_one({"arena_address": request.arena_address, "nonce": nonce, "created_at": datetime.now(timezone.utc).isoformat()})

    signature_data = await request_agent_signature(
        arena_address=request.arena_address,
        winners=request.winners,
        amounts=request.amounts,
        nonce=nonce,
        chain_id=config.chain_id,
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
        message=signature_data["message"],
    )


@api_router.post("/admin/arena/{address}/finalize")
async def record_finalize(address: str, payload: FinalizeRecordRequest, _: bool = Depends(verify_admin_key)):
    arena = await db.arenas.find_one({"address": address})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")

    if arena.get("is_finalized"):
        raise HTTPException(status_code=400, detail="Arena is already finalized")

    await db.arenas.update_one(
        {"address": address},
        {
            "$set": {
                "is_finalized": True,
                "finalized_at": datetime.now(timezone.utc).isoformat(),
                "winners": payload.winners,
                "payouts": payload.amounts,
                "tx_hash": payload.tx_hash,
            }
        },
    )

    for winner, amount in zip(payload.winners, payload.amounts):
        payout = PayoutRecord(arena_address=address, winner_address=winner, amount=amount, tx_hash=payload.tx_hash)
        await db.payouts.insert_one(payout.model_dump())

        current = await db.leaderboard.find_one({"address": winner})
        current_payouts = int(current.get("total_payouts", "0")) if current else 0
        new_payouts = current_payouts + int(amount)

        await db.leaderboard.update_one(
            {"address": winner},
            {"$set": {"total_payouts": str(new_payouts)}, "$inc": {"total_wins": 1, "tournaments_won": 1}},
            upsert=True,
        )

    logger.info(f"Finalized arena {address} with tx {payload.tx_hash}")
    return {"success": True, "message": "Arena finalized", "tx_hash": payload.tx_hash}


@api_router.get("/admin/arena/{address}/check-game-status")
async def check_game_status(address: str, _: bool = Depends(verify_admin_key)):
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

    timer_status = await timer_manager.get_timer_status(address)
    if timer_status:
        response["timer"] = timer_status

        if timer_status["type"] == "game_start_countdown":
            ends_at = datetime.fromisoformat(timer_status["countdown_ends_at"].replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            response["time_remaining_seconds"] = max(0, int((ends_at - now).total_seconds()))
        elif timer_status["type"] == "registration_countdown":
            ends_at = datetime.fromisoformat(timer_status["registration_ends_at"].replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            response["time_remaining_seconds"] = max(0, int((ends_at - now).total_seconds()))
        elif timer_status["type"] == "idle_timer":
            ends_at = datetime.fromisoformat(timer_status["idle_ends_at"].replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            response["time_remaining_seconds"] = max(0, int((ends_at - now).total_seconds()))

    if game_id and game_id in game_engine.active_games:
        game = game_engine.active_games[game_id]
        leaderboard = game_engine.get_leaderboard(game_id)
        response["game"] = {
            "id": game_id,
            "type": game.game_type.value,
            "status": game.status,
            "round": game.round_number,
            "leaderboard": leaderboard,
        }

    return response


@api_router.post("/admin/arena/{address}/process-winners")
async def process_winners(address: str, _: bool = Depends(verify_admin_key)):
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

    winners = game.winners if game.winners else []
    if not winners:
        raise HTTPException(status_code=400, detail="No winners determined by game engine")

    entry_fee = int(arena.get("entry_fee", "0"))
    protocol_fee_bps = int(arena.get("protocol_fee_bps", 250))
    players = arena.get("players", [])
    player_count = len(players)

    total_pool = entry_fee * player_count
    protocol_fee = int(total_pool * protocol_fee_bps / 10000)
    available_for_winners = total_pool - protocol_fee

    payout_per_winner = available_for_winners // len(winners) if winners else 0
    remainder = available_for_winners % len(winners) if winners else 0

    payouts = []
    payout_amounts = []
    for i, winner in enumerate(winners):
        amount = payout_per_winner
        if i == 0:
            amount += remainder
        payouts.append(winner)
        payout_amounts.append(str(amount))

    await db.arenas.update_one(
        {"address": address},
        {
            "$set": {
                "winners": payouts,
                "payouts": payout_amounts,
                "game_results": {
                    "winners": game.winners,
                    "player_scores": {p.address: p.score for p in game.players.values()},
                    "total_pool": str(total_pool),
                    "protocol_fee": str(protocol_fee),
                    "payout_per_winner": str(payout_per_winner),
                },
            }
        },
    )

    for winner, amount in zip(payouts, payout_amounts):
        payout = PayoutRecord(arena_address=address, winner_address=winner, amount=amount, tx_hash="")
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
        "message": "Winners processed successfully",
    }


@api_router.post("/admin/arena/{address}/check-if-full")
async def check_if_full(address: str, _: bool = Depends(verify_admin_key)):
    arena = await db.arenas.find_one({"address": address})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")

    players = arena.get("players", [])
    max_players = _normalize_max_players(arena.get("max_players", 8))
    if arena.get("max_players") != max_players:
        await db.arenas.update_one({"address": address}, {"$set": {"max_players": max_players}})

    is_full = len(players) >= max_players

    if is_full and not arena.get("is_closed"):
        await db.arenas.update_one({"address": address}, {"$set": {"is_closed": True, "closed_at": datetime.now(timezone.utc).isoformat()}})

        await timer_manager.start_game_countdown(address, countdown_seconds=10)

        logger.info(f"Arena {address} is full, starting 10-second countdown")

        return {
            "success": True,
            "is_full": True,
            "player_count": len(players),
            "max_players": max_players,
            "countdown_started": True,
            "countdown_seconds": 10,
            "message": "Arena is full, game will start in 10 seconds",
        }

    return {
        "success": True,
        "is_full": is_full,
        "player_count": len(players),
        "max_players": max_players,
        "countdown_started": False,
        "message": f"Arena has {len(players)}/{max_players} players",
    }


@api_router.post("/admin/arena/{address}/start-idle-timer")
async def start_idle_timer(address: str, _: bool = Depends(verify_admin_key)):
    arena = await db.arenas.find_one({"address": address})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")

    players = arena.get("players", [])

    if len(players) > 1:
        return {"success": False, "message": f"Arena has {len(players)} players, registration timer not needed"}

    # Backward-compatible endpoint for old clients.
    await timer_manager.start_registration_timer(address, countdown_seconds=60)

    return {
        "success": True,
        "arena_address": address,
        "player_count": len(players),
        "registration_seconds": 60,
        "message": "Registration countdown started (60s). If one player remains, that player is refunded.",
    }


# ===========================================
# GAME ENDPOINTS
# ===========================================


@api_router.get("/games/types", response_model=List[GameRulesResponse])
async def get_game_types():
    return get_all_game_types()


@api_router.get("/games/rules/{game_type}", response_model=GameRulesResponse)
async def get_game_rules(game_type: str):
    try:
        gt = GameType(game_type)
        return get_game_rules_json(gt)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid game type: {game_type}")


@api_router.get("/arenas/{address}/game", response_model=GameStateResponse)
async def get_arena_game_state(address: str):
    arena = await db.arenas.find_one({"address": address}, {"_id": 0})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")

    game_id = arena.get("game_id")
    if not game_id or game_id not in game_engine.active_games:
        return GameStateResponse(
            game_id="",
            arena_address=address,
            game_type=arena.get("game_type", "prediction"),
            status=arena.get("game_status", "waiting"),
            round_number=0,
            current_challenge=None,
            leaderboard=[],
            time_remaining_seconds=0,
        )

    game = game_engine.active_games[game_id]
    leaderboard = game_engine.get_leaderboard(game_id)

    time_remaining = 0
    if game.ends_at:
        try:
            ends_at = datetime.fromisoformat(game.ends_at.replace("Z", "+00:00"))
            diff = (ends_at - datetime.now(timezone.utc)).total_seconds()
            time_remaining = max(0, int(diff))
        except (ValueError, TypeError):
            pass

    challenge = None
    if game.current_challenge:
        challenge = {k: v for k, v in game.current_challenge.items() if k not in ["answer", "secret", "deck"]}

    return GameStateResponse(
        game_id=game.game_id,
        arena_address=address,
        game_type=game.game_type.value,
        status=game.status,
        round_number=game.round_number,
        current_challenge=challenge,
        leaderboard=leaderboard,
        time_remaining_seconds=time_remaining,
    )


@api_router.post("/arenas/{address}/game/start")
async def start_arena_game(address: str, _: bool = Depends(verify_admin_key)):
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

    game = game_engine.create_game(arena_address=address, game_type=game_type, players=players)

    await db.arenas.update_one({"address": address}, {"$set": {"game_id": game.game_id, "game_status": "learning"}})

    logger.info(f"Created game {game.game_id} for arena {address}")

    return {"success": True, "game_id": game.game_id, "game_type": game_type.value, "status": "learning", "message": "Game created. Learning phase started."}


@api_router.post("/arenas/{address}/game/activate")
async def activate_arena_game(address: str, _: bool = Depends(verify_admin_key)):
    arena = await db.arenas.find_one({"address": address})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")

    game_id = arena.get("game_id")
    if not game_id or game_id not in game_engine.active_games:
        raise HTTPException(status_code=400, detail="No active game session")

    game_engine.start_game(game_id)

    await db.arenas.update_one({"address": address}, {"$set": {"game_status": "active"}})

    logger.info(f"Activated game {game_id} for arena {address}")

    return {"success": True, "game_id": game_id, "status": "active", "message": "Game is now active!"}


@api_router.post("/arenas/{address}/game/move", response_model=GameMoveResponse)
async def submit_game_move(address: str, move: GameMove):
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

    success, message, result = game_engine.submit_move(game_id=game_id, player_address=move.player_address, move=move.move_data)

    player_score = None
    if move.player_address in game.players:
        player_score = game.players[move.player_address].score

    return GameMoveResponse(success=success, message=message, player_score=player_score, game_state=result)


@api_router.post("/arenas/{address}/game/advance-round")
async def advance_game_round(address: str, _: bool = Depends(verify_admin_key)):
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
        await db.arenas.update_one(
            {"address": address},
            {"$set": {"game_status": "finished", "game_results": {"winners": game.winners, "player_scores": {p.address: p.score for p in game.players.values()}}}},
        )
        logger.info(f"Game {game_id} finished. Winners: {game.winners}")

    return {"success": True, "game_id": game_id, "status": game.status, "round": game.round_number}


@api_router.post("/arenas/{address}/game/resolve-blackjack")
async def resolve_blackjack_round(address: str, _: bool = Depends(verify_admin_key)):
    arena = await db.arenas.find_one({"address": address})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")

    game_id = arena.get("game_id")
    if not game_id or game_id not in game_engine.active_games:
        raise HTTPException(status_code=400, detail="No active game session")

    game = game_engine.active_games[game_id]
    if game.game_type.value != "blackjack":
        raise HTTPException(status_code=400, detail="Not a blackjack game")

    results = game_engine.resolve_blackjack_round(game_id)

    if "error" in results:
        raise HTTPException(status_code=400, detail=results["error"])

    leaderboard = game_engine.get_leaderboard(game_id)

    return {
        "success": True,
        "dealer_cards": results.get("dealer_cards"),
        "dealer_total": results.get("dealer_total"),
        "dealer_bust": results.get("dealer_bust"),
        "player_results": results.get("player_results"),
        "leaderboard": leaderboard,
    }


@api_router.get("/arenas/{address}/game/leaderboard")
async def get_game_leaderboard(address: str):
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
    arena = await db.arenas.find_one({"address": address})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")

    game_id = arena.get("game_id")
    if not game_id or game_id not in game_engine.active_games:
        raise HTTPException(status_code=400, detail="No active game session")

    game = game_engine.finish_game(game_id)

    await db.arenas.update_one(
        {"address": address},
        {"$set": {"game_status": "finished", "game_results": {"winners": game.winners, "player_scores": {p.address: p.score for p in game.players.values()}}}},
    )

    logger.info(f"Game {game_id} finished manually. Winners: {game.winners}")

    return {"success": True, "game_id": game_id, "winners": game.winners, "player_scores": {p.address: p.score for p in game.players.values()}}


# ===========================================
# USER AGENT ENDPOINTS
# ===========================================


class CreateAgentRequest(BaseModel):
    name: str
    strategy: str = "balanced"
    max_entry_fee_wei: str = "100000000000000000"
    min_entry_fee_wei: str = "1000000000000000"
    preferred_games: List[str] = []
    auto_join: bool = True
    daily_budget_wei: str = "0"


class UpdateAgentRequest(BaseModel):
    name: Optional[str] = None
    strategy: Optional[str] = None
    max_entry_fee_wei: Optional[str] = None
    min_entry_fee_wei: Optional[str] = None
    preferred_games: Optional[List[str]] = None
    auto_join: Optional[bool] = None
    daily_budget_wei: Optional[str] = None
    status: Optional[str] = None


class AgentResponse(BaseModel):
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
    win_rate: float = 0.0
    net_profit_wei: str = "0"


def agent_to_response(agent: AgentConfig) -> AgentResponse:
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
async def create_user_agent(request: CreateAgentRequest, owner_address: str = Query(..., description="Wallet address that owns this agent")):
    try:
        strategy = AgentStrategy(request.strategy)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid strategy: {request.strategy}")

    user_agent_manager.db = db

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
async def get_user_agents(owner_address: str = Query(..., description="Wallet address to get agents for")):
    user_agent_manager.db = db
    agents = await user_agent_manager.get_agents_by_owner(owner_address)
    return [agent_to_response(a) for a in agents]


@api_router.get("/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str):
    user_agent_manager.db = db
    agent = await user_agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent_to_response(agent)


@api_router.put("/agents/{agent_id}", response_model=AgentResponse)
async def update_user_agent(agent_id: str, request: UpdateAgentRequest, owner_address: str = Query(..., description="Owner wallet address for verification")):
    user_agent_manager.db = db

    agent = await user_agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.owner_address.lower() != owner_address.lower():
        raise HTTPException(status_code=403, detail="Not authorized to modify this agent")

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

    agent = await user_agent_manager.get_agent(agent_id)
    return agent_to_response(agent)


@api_router.delete("/agents/{agent_id}")
async def delete_user_agent(agent_id: str, owner_address: str = Query(..., description="Owner wallet address for verification")):
    user_agent_manager.db = db
    success = await user_agent_manager.delete_agent(agent_id, owner_address)
    if not success:
        raise HTTPException(status_code=404, detail="Agent not found or not authorized")
    return {"success": True, "message": "Agent deleted"}


@api_router.post("/agents/{agent_id}/start")
async def start_agent(agent_id: str, owner_address: str = Query(..., description="Owner wallet address for verification")):
    user_agent_manager.db = db
    agent = await user_agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.owner_address.lower() != owner_address.lower():
        raise HTTPException(status_code=403, detail="Not authorized")
    success = await user_agent_manager.start_agent(agent_id)
    return {"success": success, "status": "active"}


@api_router.post("/agents/{agent_id}/stop")
async def stop_agent(agent_id: str, owner_address: str = Query(..., description="Owner wallet address for verification")):
    user_agent_manager.db = db
    agent = await user_agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.owner_address.lower() != owner_address.lower():
        raise HTTPException(status_code=403, detail="Not authorized")
    success = await user_agent_manager.stop_agent(agent_id)
    return {"success": success, "status": "paused"}


@api_router.get("/agents/{agent_id}/history")
async def get_agent_history(agent_id: str, limit: int = Query(default=20, le=100)):
    user_agent_manager.db = db
    agent = await user_agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    cursor = db.agent_game_history.find({"agent_id": agent_id}).sort("played_at", -1).limit(limit)

    history = []
    async for record in cursor:
        record.pop("_id", None)
        history.append(record)

    return {"agent_id": agent_id, "history": history}


@api_router.post("/arenas/{address}/join-agent")
async def join_arena_with_agent(address: str, agent_id: str = Query(...), owner_address: str = Query(...)):
    user_agent_manager.db = db

    agent = await user_agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.owner_address.lower() != owner_address.lower():
        raise HTTPException(status_code=403, detail="Not authorized")

    arena = await db.arenas.find_one({"address": address})
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")

    if arena.get("is_closed") or arena.get("is_finalized"):
        raise HTTPException(status_code=400, detail="Arena is closed")

    players = arena.get("players", [])
    if len(players) >= arena.get("max_players", 8):
        raise HTTPException(status_code=400, detail="Arena is full")

    agent_player_address = f"agent_{agent_id}"

    if agent_player_address in players:
        raise HTTPException(status_code=400, detail="Agent already in arena")

    await db.arenas.update_one({"address": address}, {"$push": {"players": agent_player_address}})

    logger.info(f"Agent {agent_id} joined arena {address}")

    return {"success": True, "agent_id": agent_id, "arena_address": address, "player_address": agent_player_address}


# ===========================================
# INDEXER ENDPOINTS (for on-chain events)
# ===========================================


@api_router.post("/indexer/event/arena-created")
async def index_arena_created(payload: Dict[str, Any]):
    address = payload.get("address")
    if not address:
        raise HTTPException(status_code=400, detail="address is required")

    normalized_payload = dict(payload)
    if "max_players" in normalized_payload:
        normalized_payload["max_players"] = _normalize_max_players(normalized_payload.get("max_players"))

    await db.arenas.update_one(
        {"address": address},
        {
            "$set": normalized_payload,
            "$setOnInsert": {
                "address": address,
                "name": normalized_payload.get("name", f"Arena {address[:8]}"),
                "entry_fee": str(normalized_payload.get("entry_fee", "0")),
                "max_players": _normalize_max_players(normalized_payload.get("max_players", 8)),
                "protocol_fee_bps": int(normalized_payload.get("protocol_fee_bps", 250)),
                "treasury": normalized_payload.get("treasury", "0x0000000000000000000000000000000000000000"),
                "is_closed": bool(normalized_payload.get("is_closed", False)),
                "is_finalized": bool(normalized_payload.get("is_finalized", False)),
                "players": normalized_payload.get("players", []),
                "created_at": normalized_payload.get("created_at", datetime.now(timezone.utc).isoformat()),
                "network": normalized_payload.get("network", DEFAULT_NETWORK),
                "created_by": normalized_payload.get("created_by", "indexer"),
                "game_status": normalized_payload.get("game_status", "waiting"),
            },
        },
        upsert=True,
    )
    logger.info(f"Indexed arena created: {address}")
    return {"success": True, "message": "Arena indexed"}


@api_router.post("/indexer/event/joined")
async def index_joined(join_data: JoinArena):
    return await join_arena(join_data)


# ===========================================
# APP CONFIGURATION
# ===========================================

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
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

    user_agent_manager.db = db
    await user_agent_manager.start()
    logger.info("User Agent Manager initialized")

    timer_manager.background_task = asyncio.create_task(timer_manager.process_timers())
    logger.info("Arena Timer Manager started")


@app.on_event("shutdown")
async def shutdown_db_client():
    await user_agent_manager.stop()
    logger.info("User Agent Manager stopped")

    if timer_manager.background_task:
        timer_manager.background_task.cancel()
        try:
            await timer_manager.background_task
        except asyncio.CancelledError:
            pass
    logger.info("Arena Timer Manager stopped")

    client.close()
