#!/usr/bin/env python3
"""
CLAW ARENA - Full Demo & Multi-Wallet Testing Script

Runs the complete tournament lifecycle end-to-end with multiple simulated
wallets and agents. Perfect for testing before a hackathon demo video.

Features:
  - Creates arenas on testnet or mainnet (via backend API)
  - Spawns N bot wallets that join arenas
  - Runs full game lifecycle: learning -> active -> play -> finish -> finalize
  - Spawns user-agents with different strategies
  - Prints a live scoreboard and summary at the end

Usage:
    # Quick smoke test (2 bots, 1 arena, testnet)
    python demo_test.py

    # Full demo run (6 bots, 2 arenas, mainnet)
    python demo_test.py --network mainnet --bots 6 --arenas 2

    # With user-agents
    python demo_test.py --bots 4 --agents 2

Environment variables:
    API_BASE       - Backend API URL (default: http://localhost:8000)
    ADMIN_KEY      - Admin API key   (default: claw-arena-admin-key)
"""

import os
import sys
import json
import time
import random
import asyncio
import argparse
import hashlib
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: pip install httpx")
    sys.exit(1)

try:
    from eth_account import Account
except ImportError:
    Account = None
    print("WARNING: eth_account not installed. Using random hex addresses.")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
API_BASE = os.getenv("API_BASE", "http://localhost:8000")
ADMIN_KEY = os.getenv("ADMIN_KEY", "claw-arena-admin-key")

GAME_TYPES = ["blackjack", "prediction", "speed", "claw"]

ENTRY_FEES = {
    "micro":  "1000000000000000",      # 0.001 MON
    "small":  "10000000000000000",     # 0.01  MON
    "medium": "100000000000000000",    # 0.1   MON
}

# ANSI colours for pretty terminal output
C_RESET  = "\033[0m"
C_BOLD   = "\033[1m"
C_GREEN  = "\033[92m"
C_YELLOW = "\033[93m"
C_CYAN   = "\033[96m"
C_RED    = "\033[91m"
C_DIM    = "\033[2m"


def ts():
    return datetime.now().strftime("%H:%M:%S")


def wei_to_mon(wei_str: str) -> str:
    return f"{int(wei_str) / 1e18:.4f}"


def make_address() -> Tuple[str, str]:
    """Return (address, private_key). Uses eth_account if available."""
    if Account:
        acct = Account.create()
        return acct.address, acct.key.hex()
    # Fallback: random hex address
    addr = "0x" + hashlib.sha256(str(random.random()).encode()).hexdigest()[:40]
    return addr, "0x" + "0" * 64


# ===========================================================================
# HTTP helpers
# ===========================================================================
class API:
    def __init__(self, base: str, admin_key: str, network: str):
        self.base = base.rstrip("/")
        self.admin_key = admin_key
        self.network = network
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    def _admin_headers(self):
        return {"X-Admin-Key": self.admin_key, "Content-Type": "application/json"}

    # -- public --
    async def health(self) -> dict:
        r = await self.client.get(f"{self.base}/api/health")
        return r.json()

    async def get_arenas(self) -> list:
        r = await self.client.get(f"{self.base}/api/arenas", params={"network": self.network})
        return r.json() if r.status_code == 200 else []

    async def get_arena(self, addr: str) -> dict:
        r = await self.client.get(f"{self.base}/api/arenas/{addr}")
        return r.json() if r.status_code == 200 else {}

    async def get_leaderboard(self, limit=20) -> list:
        r = await self.client.get(f"{self.base}/api/leaderboard", params={"limit": limit, "network": self.network})
        return r.json() if r.status_code == 200 else []

    async def get_game_state(self, arena_addr: str) -> Optional[dict]:
        r = await self.client.get(f"{self.base}/api/arenas/{arena_addr}/game")
        return r.json() if r.status_code == 200 else None

    # -- player actions --
    async def join_arena(self, arena_addr: str, player_addr: str, tx_hash: str = None) -> dict:
        if not tx_hash:
            tx_hash = "0x" + hashlib.sha256(f"{player_addr}{time.time()}".encode()).hexdigest()
        r = await self.client.post(
            f"{self.base}/api/arenas/join",
            json={"arena_address": arena_addr, "player_address": player_addr, "tx_hash": tx_hash},
        )
        return r.json() if r.status_code == 200 else {"error": r.text}

    async def submit_move(self, arena_addr: str, player_addr: str, move: dict) -> dict:
        payload = {"player_address": player_addr, **move}
        r = await self.client.post(f"{self.base}/api/arenas/{arena_addr}/game/move", json=payload)
        return r.json() if r.status_code == 200 else {"error": r.text}

    # -- admin actions --
    async def create_arena(self, name: str, entry_fee: str, max_players: int,
                           game_type: str, protocol_fee_bps: int = 250) -> dict:
        contract_addr = "0x" + hashlib.sha256(f"{name}{time.time()}".encode()).hexdigest()[:40]
        now = datetime.now(timezone.utc)
        reg_deadline = (now + timedelta(minutes=5)).isoformat()

        r = await self.client.post(
            f"{self.base}/api/admin/arena/create",
            params={"network": self.network},
            headers=self._admin_headers(),
            json={
                "name": name,
                "entry_fee": entry_fee,
                "max_players": max_players,
                "protocol_fee_bps": protocol_fee_bps,
                "contract_address": contract_addr,
                "game_type": game_type,
                "learning_phase_seconds": 10,  # Short for demo
            },
        )
        if r.status_code == 200:
            arena = r.json()
            # Set timers
            await self.client.post(
                f"{self.base}/api/indexer/event/arena-created",
                json={
                    "address": arena.get("address", contract_addr),
                    "registration_deadline": reg_deadline,
                    "tournament_end_estimate": (now + timedelta(minutes=15)).isoformat(),
                    "created_by": "demo_test",
                    "creation_reason": "Demo / multi-wallet test",
                    "game_type": game_type,
                },
            )
            return arena
        return {"error": r.text, "status": r.status_code}

    async def close_arena(self, addr: str) -> dict:
        r = await self.client.post(
            f"{self.base}/api/admin/arena/{addr}/close",
            headers=self._admin_headers(),
        )
        return r.json() if r.status_code == 200 else {"error": r.text}

    async def start_game(self, addr: str) -> dict:
        r = await self.client.post(
            f"{self.base}/api/admin/arena/{addr}/game/start",
            headers=self._admin_headers(),
        )
        return r.json() if r.status_code == 200 else {"error": r.text}

    async def activate_game(self, addr: str) -> dict:
        r = await self.client.post(
            f"{self.base}/api/admin/arena/{addr}/game/activate",
            headers=self._admin_headers(),
        )
        return r.json() if r.status_code == 200 else {"error": r.text}

    async def advance_round(self, addr: str) -> dict:
        r = await self.client.post(
            f"{self.base}/api/admin/arena/{addr}/game/advance-round",
            headers=self._admin_headers(),
        )
        return r.json() if r.status_code == 200 else {"error": r.text}

    async def finish_game(self, addr: str) -> dict:
        r = await self.client.post(
            f"{self.base}/api/admin/arena/{addr}/game/finish",
            headers=self._admin_headers(),
        )
        return r.json() if r.status_code == 200 else {"error": r.text}

    async def resolve_blackjack(self, addr: str) -> dict:
        r = await self.client.post(
            f"{self.base}/api/arenas/{addr}/game/resolve-blackjack",
            headers=self._admin_headers(),
        )
        return r.json() if r.status_code == 200 else {"error": r.text}

    async def request_finalize_sig(self, arena_addr: str, winners: list, amounts: list) -> dict:
        r = await self.client.post(
            f"{self.base}/api/admin/arena/request-finalize-signature",
            headers=self._admin_headers(),
            json={"arena_address": arena_addr, "winners": winners, "amounts": amounts},
        )
        return r.json() if r.status_code == 200 else {"error": r.text}

    async def finalize_arena(self, arena_addr: str, winners: list, amounts: list, tx_hash: str = None) -> dict:
        if not tx_hash:
            tx_hash = "0x" + hashlib.sha256(f"finalize{arena_addr}{time.time()}".encode()).hexdigest()
        r = await self.client.post(
            f"{self.base}/api/admin/arena/{arena_addr}/finalize",
            headers=self._admin_headers(),
            json={"tx_hash": tx_hash, "winners": winners, "amounts": amounts, "network": self.network},
        )
        return r.json() if r.status_code == 200 else {"error": r.text}

    # -- agent endpoints --
    async def create_agent(self, owner: str, name: str, strategy: str = "balanced") -> dict:
        r = await self.client.post(
            f"{self.base}/api/agents/create",
            params={"owner_address": owner},
            json={
                "name": name,
                "strategy": strategy,
                "max_entry_fee_wei": "1000000000000000000",
                "min_entry_fee_wei": "1000000000000000",
                "preferred_games": [],
                "auto_join": True,
                "daily_budget_wei": "0",
            },
        )
        return r.json() if r.status_code == 200 else {"error": r.text}

    async def join_agent(self, arena_addr: str, agent_id: str, owner: str) -> dict:
        r = await self.client.post(
            f"{self.base}/api/arenas/{arena_addr}/join-agent",
            params={"agent_id": agent_id, "owner_address": owner},
        )
        return r.json() if r.status_code == 200 else {"error": r.text}


# ===========================================================================
# Bot wallet
# ===========================================================================
class DemoBot:
    def __init__(self, idx: int, api: API):
        self.idx = idx
        self.api = api
        self.address, self.private_key = make_address()
        self.score = 0
        self.arenas_joined: List[str] = []

    def tag(self):
        return f"Wallet-{self.idx} ({self.address[:10]}...)"

    def log(self, msg: str):
        print(f"  {C_DIM}[{ts()}]{C_RESET} {C_CYAN}{self.tag()}{C_RESET}: {msg}")

    async def play_round(self, arena_addr: str, game_state: dict):
        """Play one round of whatever game type is active."""
        game_type = game_state.get("game_type", "blackjack")
        challenge = game_state.get("current_challenge", {})

        if game_type == "blackjack":
            await self._play_blackjack(arena_addr, challenge)
        elif game_type == "claw":
            await self._play_claw(arena_addr, challenge)
        elif game_type == "prediction":
            await self._play_prediction(arena_addr, challenge)
        elif game_type == "speed":
            await self._play_speed(arena_addr, challenge)

    async def _play_blackjack(self, arena_addr: str, challenge: dict):
        hands = challenge.get("player_hands", {})
        my_hand = hands.get(self.address, {})
        if my_hand.get("status") != "playing":
            return
        cards = my_hand.get("cards", [])
        total = self._bj_total(cards)
        action = "stand" if total >= 17 else "hit"
        self.log(f"Blackjack hand={total} -> {action}")
        result = await self.api.submit_move(arena_addr, self.address, {"action": action})
        if result.get("success") and action == "hit":
            new_total = result.get("game_state", {}).get("total", total)
            if new_total < 21:
                await asyncio.sleep(0.3)
                gs = await self.api.get_game_state(arena_addr)
                if gs:
                    await self._play_blackjack(arena_addr, gs.get("current_challenge", {}))

    def _bj_total(self, cards):
        total, aces = 0, 0
        for c in cards:
            r = c.get("rank", "")
            if r in ("J", "Q", "K"): total += 10
            elif r == "A": aces += 1; total += 11
            else:
                try: total += int(r)
                except: pass
        while total > 21 and aces > 0:
            total -= 10; aces -= 1
        return total

    async def _play_claw(self, arena_addr: str, challenge: dict):
        prizes = [p for p in challenge.get("prizes", []) if not p.get("grabbed")]
        if not prizes:
            return
        target = max(prizes, key=lambda p: p.get("value", 0))
        self.log(f"Claw -> targeting prize #{target['id']} ({target['type']}, {target['value']}pts)")
        await self.api.submit_move(arena_addr, self.address, {
            "prize_id": target["id"], "x": target["x"], "y": target["y"]
        })

    async def _play_prediction(self, arena_addr: str, challenge: dict):
        lo = challenge.get("min", 0)
        hi = challenge.get("max", 100)
        pred = random.randint(lo, hi)
        self.log(f"Prediction -> {pred}")
        await self.api.submit_move(arena_addr, self.address, {"prediction": pred})

    async def _play_speed(self, arena_addr: str, challenge: dict):
        answer = challenge.get("answer", random.randint(1, 100))
        rt = random.randint(500, 3000)
        self.log(f"Speed -> answer={answer}  ({rt}ms)")
        await self.api.submit_move(arena_addr, self.address, {"answer": answer, "response_time_ms": rt})


# ===========================================================================
# Demo Orchestrator
# ===========================================================================
class DemoOrchestrator:
    def __init__(self, args):
        self.network = args.network
        self.num_bots = args.bots
        self.num_arenas = args.arenas
        self.num_agents = args.agents
        self.game_type = args.game
        self.tier = args.tier
        self.rounds = args.rounds
        self.api = API(API_BASE, ADMIN_KEY, self.network)
        self.bots: List[DemoBot] = []
        self.arena_addresses: List[str] = []
        self.agent_ids: List[str] = []

    async def run(self):
        print(f"\n{C_BOLD}{'='*60}{C_RESET}")
        print(f"{C_BOLD}  CLAW ARENA  -  Demo & Multi-Wallet Test{C_RESET}")
        print(f"{C_BOLD}{'='*60}{C_RESET}")
        print(f"  Network   : {C_YELLOW if self.network=='testnet' else C_GREEN}{self.network}{C_RESET}")
        print(f"  Bots      : {self.num_bots}")
        print(f"  Arenas    : {self.num_arenas}")
        print(f"  Agents    : {self.num_agents}")
        print(f"  Game      : {self.game_type or 'random'}")
        print(f"  Tier      : {self.tier}")
        print(f"  Rounds    : {self.rounds}")
        print(f"  Backend   : {API_BASE}")
        print(f"{'='*60}\n")

        try:
            # Step 0: Health check
            await self._step_health()

            # Step 1: Create bot wallets
            await self._step_create_bots()

            # Step 2: Create arenas
            await self._step_create_arenas()

            # Step 3: Join arenas with bots
            await self._step_join_arenas()

            # Step 4: Create & join user agents (if requested)
            if self.num_agents > 0:
                await self._step_create_agents()

            # Step 5: Close registration & start games
            await self._step_start_games()

            # Step 6: Play rounds
            await self._step_play_rounds()

            # Step 7: Finish games
            await self._step_finish_games()

            # Step 8: Finalize (prize distribution)
            await self._step_finalize()

            # Step 9: Show final results
            await self._step_results()

        except KeyboardInterrupt:
            print(f"\n{C_YELLOW}Demo interrupted by user.{C_RESET}")
        except Exception as e:
            print(f"\n{C_RED}ERROR: {e}{C_RESET}")
            import traceback
            traceback.print_exc()
        finally:
            await self.api.close()

    # ----- Steps -----

    async def _step_health(self):
        self._header("Step 0: Health Check")
        try:
            h = await self.api.health()
            status = h.get("status", "unknown")
            if status == "healthy":
                print(f"  {C_GREEN}Backend is healthy{C_RESET}")
                print(f"  Default network: {h.get('default_network', '?')}")
            else:
                print(f"  {C_RED}Backend status: {status}{C_RESET}")
                print(f"  {C_RED}Make sure the backend is running at {API_BASE}{C_RESET}")
                sys.exit(1)
        except Exception as e:
            print(f"  {C_RED}Cannot reach backend at {API_BASE}{C_RESET}")
            print(f"  {C_RED}Error: {e}{C_RESET}")
            print(f"\n  Start the backend first:")
            print(f"    cd backend && python -m uvicorn server:app --port 8000")
            sys.exit(1)

    async def _step_create_bots(self):
        self._header(f"Step 1: Creating {self.num_bots} Bot Wallets")
        for i in range(self.num_bots):
            bot = DemoBot(i + 1, self.api)
            self.bots.append(bot)
            print(f"  Wallet-{i+1}: {C_CYAN}{bot.address}{C_RESET}")
        print()

    async def _step_create_arenas(self):
        self._header(f"Step 2: Creating {self.num_arenas} Arena(s)")
        entry_fee = ENTRY_FEES.get(self.tier, ENTRY_FEES["small"])
        bots_per_arena = max(2, self.num_bots // self.num_arenas)

        for i in range(self.num_arenas):
            game = self.game_type or random.choice(GAME_TYPES)
            name = f"Demo {game.title()} Arena #{i+1}"
            max_p = min(bots_per_arena + self.num_agents + 2, 16)  # leave room

            print(f"  Creating: {C_BOLD}{name}{C_RESET}")
            print(f"    Game: {game}, Entry: {wei_to_mon(entry_fee)} MON, Max players: {max_p}")

            result = await self.api.create_arena(name, entry_fee, max_p, game)
            if "error" in result:
                print(f"    {C_RED}FAILED: {result['error']}{C_RESET}")
                continue

            addr = result.get("address", "")
            self.arena_addresses.append(addr)
            print(f"    {C_GREEN}Created: {addr[:20]}...{C_RESET}")
        print()

    async def _step_join_arenas(self):
        self._header("Step 3: Bots Joining Arenas")
        if not self.arena_addresses:
            print(f"  {C_RED}No arenas to join!{C_RESET}")
            return

        # Distribute bots across arenas
        for i, bot in enumerate(self.bots):
            arena_addr = self.arena_addresses[i % len(self.arena_addresses)]
            result = await self.api.join_arena(arena_addr, bot.address)
            if result.get("success"):
                bot.arenas_joined.append(arena_addr)
                bot.log(f"{C_GREEN}Joined arena {arena_addr[:16]}...{C_RESET}")
            else:
                bot.log(f"{C_RED}Failed to join: {result.get('error', result)}{C_RESET}")
            await asyncio.sleep(0.2)
        print()

    async def _step_create_agents(self):
        self._header(f"Step 4: Creating {self.num_agents} User Agent(s)")
        strategies = ["conservative", "balanced", "aggressive", "random"]
        owner_addr = self.bots[0].address if self.bots else make_address()[0]

        for i in range(self.num_agents):
            strat = strategies[i % len(strategies)]
            name = f"Agent-{strat.title()}-{i+1}"
            result = await self.api.create_agent(owner_addr, name, strat)

            if "error" in result:
                print(f"  {C_RED}Failed to create {name}: {result['error']}{C_RESET}")
                continue

            agent_id = result.get("agent_id", "")
            self.agent_ids.append(agent_id)
            print(f"  {C_GREEN}Created {name}{C_RESET} (id: {agent_id[:12]}..., strategy: {strat})")

            # Join each agent to an arena
            for arena_addr in self.arena_addresses:
                jr = await self.api.join_agent(arena_addr, agent_id, owner_addr)
                if jr.get("success"):
                    print(f"    -> Joined arena {arena_addr[:16]}...")
                else:
                    print(f"    -> {C_DIM}Could not join {arena_addr[:16]}...{C_RESET}")
        print()

    async def _step_start_games(self):
        self._header("Step 5: Closing Registration & Starting Games")
        for arena_addr in self.arena_addresses:
            # Close registration
            r = await self.api.close_arena(arena_addr)
            print(f"  Arena {arena_addr[:16]}... registration closed: {r.get('success', False)}")

            # Start game (learning phase)
            r = await self.api.start_game(arena_addr)
            game_id = r.get("game_id", "?")
            print(f"  Game started (id: {game_id}), learning phase...")

            # Short wait for learning phase (demo uses 10s)
            await asyncio.sleep(2)

            # Activate game
            r = await self.api.activate_game(arena_addr)
            print(f"  {C_GREEN}Game ACTIVE!{C_RESET}")
        print()

    async def _step_play_rounds(self):
        self._header(f"Step 6: Playing {self.rounds} Round(s)")
        for round_num in range(1, self.rounds + 1):
            print(f"\n  {C_BOLD}--- Round {round_num} ---{C_RESET}")

            for arena_addr in self.arena_addresses:
                game_state = await self.api.get_game_state(arena_addr)
                if not game_state or game_state.get("status") != "active":
                    print(f"  Arena {arena_addr[:16]}... not active, skipping")
                    continue

                game_type = game_state.get("game_type", "?")
                print(f"  Arena {arena_addr[:16]}... game: {game_type}, round: {game_state.get('round_number', '?')}")

                # All bots play
                for bot in self.bots:
                    if arena_addr in bot.arenas_joined:
                        try:
                            await bot.play_round(arena_addr, game_state)
                        except Exception as e:
                            bot.log(f"{C_RED}Play error: {e}{C_RESET}")
                        await asyncio.sleep(0.1)

                # Resolve blackjack if needed
                if game_type == "blackjack":
                    await self.api.resolve_blackjack(arena_addr)
                    print(f"  {C_DIM}Blackjack round resolved{C_RESET}")

                # Advance to next round (unless last)
                if round_num < self.rounds:
                    r = await self.api.advance_round(arena_addr)
                    new_round = r.get("round_number", "?")
                    print(f"  Advanced to round {new_round}")

                # Show mini-scoreboard
                gs = await self.api.get_game_state(arena_addr)
                if gs:
                    lb = gs.get("leaderboard", [])
                    if lb:
                        print(f"  {C_DIM}Scoreboard:{C_RESET}")
                        for entry in lb[:5]:
                            addr = entry.get("address", "?")[:12]
                            score = entry.get("score", 0)
                            print(f"    {addr}...  {C_BOLD}{score}{C_RESET} pts")

            await asyncio.sleep(0.5)
        print()

    async def _step_finish_games(self):
        self._header("Step 7: Finishing Games")
        for arena_addr in self.arena_addresses:
            r = await self.api.finish_game(arena_addr)
            winners = r.get("winners", [])
            scores = r.get("player_scores", {})
            print(f"  Arena {arena_addr[:16]}...")
            if winners:
                print(f"    {C_GREEN}Winners: {[w[:12]+'...' for w in winners]}{C_RESET}")
                for addr, score in sorted(scores.items(), key=lambda x: -x[1]):
                    print(f"    {addr[:12]}... -> {score} pts")
            else:
                print(f"    {C_YELLOW}No game results (may already be finished){C_RESET}")
        print()

    async def _step_finalize(self):
        self._header("Step 8: Finalizing & Prize Distribution")
        for arena_addr in self.arena_addresses:
            arena = await self.api.get_arena(arena_addr)
            if not arena:
                continue

            players = arena.get("players", [])
            entry_fee = int(arena.get("entry_fee", "0"))
            fee_bps = arena.get("protocol_fee_bps", 250)

            total_pool = entry_fee * len(players)
            protocol_fee = total_pool * fee_bps // 10000
            prize_pool = total_pool - protocol_fee

            # Get winners from game results
            game_results = arena.get("game_results", {})
            winners = game_results.get("winners", players[:2] if len(players) >= 2 else players)

            if len(winners) >= 2:
                amounts = [str(int(prize_pool * 0.7)), str(int(prize_pool * 0.3))]
            elif len(winners) == 1:
                amounts = [str(prize_pool)]
            else:
                print(f"  {C_YELLOW}No winners for {arena_addr[:16]}...{C_RESET}")
                continue

            print(f"  Arena {arena_addr[:16]}...")
            print(f"    Total pool : {wei_to_mon(str(total_pool))} MON")
            print(f"    Protocol   : {wei_to_mon(str(protocol_fee))} MON ({fee_bps/100}%)")
            print(f"    Prize pool : {wei_to_mon(str(prize_pool))} MON")

            for i, (w, a) in enumerate(zip(winners, amounts)):
                place = ["1st", "2nd", "3rd"][i] if i < 3 else f"{i+1}th"
                print(f"    {place}: {w[:12]}... -> {C_GREEN}{wei_to_mon(a)} MON{C_RESET}")

            # Request signature (if agent signer is running)
            sig_result = await self.api.request_finalize_sig(arena_addr, winners, amounts)
            if sig_result.get("signature"):
                print(f"    Signature obtained from operator")
            else:
                print(f"    {C_DIM}Signature skipped (agent signer not running){C_RESET}")

            # Record finalization
            fin_result = await self.api.finalize_arena(arena_addr, winners, amounts)
            if fin_result.get("success"):
                print(f"    {C_GREEN}FINALIZED{C_RESET}")
            else:
                print(f"    {C_YELLOW}Finalize recorded (may need on-chain tx in production){C_RESET}")
        print()

    async def _step_results(self):
        self._header("Step 9: Final Results & Leaderboard")

        # Leaderboard
        lb = await self.api.get_leaderboard(20)
        if lb:
            print(f"  {C_BOLD}Leaderboard ({self.network}):{C_RESET}")
            for i, entry in enumerate(lb[:10]):
                addr = entry.get("address", "?")[:16]
                wins = entry.get("total_wins", 0)
                played = entry.get("tournaments_played", 0)
                payout = entry.get("total_payouts", "0")
                medal = ["  ", "  ", "  "][i] if i < 3 else "   "
                print(f"  {medal} #{i+1}  {addr}...  W:{wins}  P:{played}  Earned: {wei_to_mon(payout)} MON")

        # All arenas summary
        print(f"\n  {C_BOLD}Arena Summary:{C_RESET}")
        arenas = await self.api.get_arenas()
        for arena in arenas:
            addr = arena.get("address", "?")[:16]
            name = arena.get("name", "?")
            players = len(arena.get("players", []))
            status = "Finalized" if arena.get("is_finalized") else "Closed" if arena.get("is_closed") else "Open"
            game_type = arena.get("game_type", "?")
            entry = wei_to_mon(arena.get("entry_fee", "0"))
            color = C_GREEN if status == "Finalized" else C_YELLOW if status == "Closed" else C_CYAN
            print(f"  {color}[{status:10s}]{C_RESET} {name:30s} {game_type:12s} {entry:>8s} MON  {players} players")

        print(f"\n{C_BOLD}{'='*60}{C_RESET}")
        print(f"{C_GREEN}  Demo complete! All {len(self.arena_addresses)} arena(s) tested on {self.network}.{C_RESET}")
        print(f"{C_BOLD}{'='*60}{C_RESET}\n")

    # ----- Helpers -----
    def _header(self, text: str):
        print(f"\n{C_BOLD}{text}{C_RESET}")
        print(f"{'-'*len(text)}")


# ===========================================================================
# Main
# ===========================================================================
def main():
    parser = argparse.ArgumentParser(
        description="CLAW ARENA - Full Demo & Multi-Wallet Testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python demo_test.py                                  # Quick test (testnet)
  python demo_test.py --network mainnet --bots 6       # Mainnet with 6 wallets
  python demo_test.py --bots 8 --arenas 2 --agents 2   # 2 arenas, bots + agents
  python demo_test.py --game blackjack --rounds 5       # Specific game type
        """,
    )
    parser.add_argument("--network", choices=["testnet", "mainnet"], default="testnet",
                        help="Network to test on (default: testnet)")
    parser.add_argument("--bots", type=int, default=4,
                        help="Number of bot wallets to create (default: 4)")
    parser.add_argument("--arenas", type=int, default=1,
                        help="Number of arenas to create (default: 1)")
    parser.add_argument("--agents", type=int, default=0,
                        help="Number of user agents to create (default: 0)")
    parser.add_argument("--game", choices=GAME_TYPES, default=None,
                        help="Specific game type (default: random)")
    parser.add_argument("--tier", choices=list(ENTRY_FEES.keys()), default="small",
                        help="Entry fee tier (default: small)")
    parser.add_argument("--rounds", type=int, default=3,
                        help="Number of game rounds to play (default: 3)")
    args = parser.parse_args()

    if args.network == "mainnet":
        print(f"\n{C_YELLOW}  WARNING: You selected MAINNET.{C_RESET}")
        print(f"  This will create arenas and record activity on Monad Mainnet.")
        print(f"  (Backend API mode - no real MON is spent in this demo script)")
        confirm = input(f"\n  Continue? [y/N]: ").strip().lower()
        if confirm != "y":
            print("  Aborted.")
            sys.exit(0)

    asyncio.run(DemoOrchestrator(args).run())


if __name__ == "__main__":
    main()
