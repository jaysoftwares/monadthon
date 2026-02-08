"""
CLAW ARENA - Bot Player

Simulates players joining arenas and playing games.
Useful for testing game mechanics without real users.

Usage:
    python bot_player.py --arena <address> --num-bots 3

This script is Windows-compatible (no emoji characters).
"""

import os
import sys
import time
import random
import asyncio
import argparse
import httpx
from datetime import datetime
from typing import List, Dict, Optional
from eth_account import Account

# Configuration
API_BASE = os.getenv("API_BASE", "http://localhost:8000")
ADMIN_KEY = os.getenv("ADMIN_KEY", "test-key")


class BotPlayer:
    """Simulates a player bot that joins and plays games."""

    def __init__(self, bot_id: int):
        self.bot_id = bot_id
        self.account = Account.create()
        self.address = self.account.address
        self.private_key = self.account.key.hex()
        self.current_arena: Optional[str] = None
        self.client = httpx.AsyncClient(timeout=30.0)

    def log(self, msg: str):
        """Print log message with bot identifier."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Bot-{self.bot_id} ({self.address[:8]}...): {msg}")

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def get_arena_info(self, arena_address: str) -> Optional[Dict]:
        """Fetch arena information."""
        try:
            resp = await self.client.get(f"{API_BASE}/arenas/{arena_address}")
            if resp.status_code == 200:
                return resp.json()
            else:
                self.log(f"Failed to get arena: {resp.status_code}")
                return None
        except Exception as e:
            self.log(f"Error getting arena: {e}")
            return None

    async def get_game_state(self, arena_address: str) -> Optional[Dict]:
        """Fetch current game state."""
        try:
            resp = await self.client.get(f"{API_BASE}/arenas/{arena_address}/game")
            if resp.status_code == 200:
                return resp.json()
            else:
                return None
        except Exception as e:
            self.log(f"Error getting game state: {e}")
            return None

    async def submit_move(self, arena_address: str, move_data: Dict) -> Optional[Dict]:
        """Submit a game move."""
        try:
            payload = {
                "player_address": self.address,
                **move_data
            }
            resp = await self.client.post(
                f"{API_BASE}/arenas/{arena_address}/game/move",
                json=payload
            )
            if resp.status_code == 200:
                return resp.json()
            else:
                self.log(f"Move failed: {resp.status_code} - {resp.text}")
                return None
        except Exception as e:
            self.log(f"Error submitting move: {e}")
            return None

    async def play_blackjack_round(self, arena_address: str, game_state: Dict) -> bool:
        """Play a round of blackjack with simple strategy."""
        challenge = game_state.get("current_challenge", {})
        player_hands = challenge.get("player_hands", {})
        my_hand = player_hands.get(self.address, {})

        if my_hand.get("status") != "playing":
            return True  # Already done this round

        cards = my_hand.get("cards", [])
        total = self._calculate_hand_value(cards)

        # Simple strategy: hit until 17
        if total < 17:
            action = "hit"
        else:
            action = "stand"

        self.log(f"Hand value: {total}, action: {action}")
        result = await self.submit_move(arena_address, {"action": action})

        if result and result.get("success"):
            new_total = result.get("game_state", {}).get("total", total)
            if action == "hit" and new_total < 21:
                # Might need to act again
                await asyncio.sleep(0.5)
                new_game_state = await self.get_game_state(arena_address)
                if new_game_state:
                    return await self.play_blackjack_round(arena_address, new_game_state)
        return True

    def _calculate_hand_value(self, cards: List[Dict]) -> int:
        """Calculate blackjack hand value."""
        total = 0
        aces = 0

        for card in cards:
            rank = card.get("rank", "")
            if rank in ["J", "Q", "K"]:
                total += 10
            elif rank == "A":
                aces += 1
                total += 11
            else:
                try:
                    total += int(rank)
                except ValueError:
                    pass

        # Adjust aces
        while total > 21 and aces > 0:
            total -= 10
            aces -= 1

        return total

    async def play_claw_round(self, arena_address: str, game_state: Dict) -> bool:
        """Play a round of claw machine."""
        challenge = game_state.get("current_challenge", {})
        grid_width = challenge.get("grid_width", 10)

        # Pick random position and drop
        x = random.randint(0, grid_width - 1)
        y = random.randint(0, grid_width - 1)

        self.log(f"Dropping claw at ({x}, {y})")
        result = await self.submit_move(arena_address, {
            "x": x,
            "y": y
        })

        if result and result.get("success"):
            points = result.get("points_earned", 0)
            self.log(f"Grabbed prize worth {points} points")
        return True

    async def play_prediction_round(self, arena_address: str, game_state: Dict) -> bool:
        """Make a prediction."""
        challenge = game_state.get("current_challenge", {})
        min_val = challenge.get("min_value", 0)
        max_val = challenge.get("max_value", 100)

        # Make random prediction
        prediction = random.randint(min_val, max_val)
        self.log(f"Predicting: {prediction}")

        result = await self.submit_move(arena_address, {
            "prediction": prediction
        })
        return result is not None

    async def play_speed_round(self, arena_address: str, game_state: Dict) -> bool:
        """Answer speed challenge."""
        challenge = game_state.get("current_challenge", {})
        challenge_type = challenge.get("type", "math")

        if challenge_type == "math":
            # Try to solve simple math
            answer = challenge.get("answer", random.randint(1, 100))
        elif challenge_type == "pattern":
            options = challenge.get("options", [1, 2, 3, 4])
            answer = random.choice(options)
        else:
            answer = True  # Reaction test

        self.log(f"Speed answer: {answer}")
        result = await self.submit_move(arena_address, {
            "answer": answer
        })
        return result is not None

    async def play_game(self, arena_address: str):
        """Main game loop for a bot."""
        self.current_arena = arena_address
        self.log(f"Joining arena {arena_address[:10]}...")

        # Wait for game to be active
        max_wait = 120
        wait_time = 0
        game_state = None

        while wait_time < max_wait:
            game_state = await self.get_game_state(arena_address)
            if not game_state:
                self.log("Waiting for game to start...")
                await asyncio.sleep(3)
                wait_time += 3
                continue

            status = game_state.get("status", "")
            if status == "learning":
                self.log("In learning phase, waiting...")
                await asyncio.sleep(5)
                wait_time += 5
            elif status == "active":
                break
            elif status == "finished":
                self.log("Game already finished")
                return
            else:
                await asyncio.sleep(2)
                wait_time += 2

        if not game_state or game_state.get("status") != "active":
            self.log("Game did not become active in time")
            return

        game_type = game_state.get("game_type", "blackjack")
        self.log(f"Game is active! Type: {game_type}")

        # Play rounds until game ends
        last_round = 0
        while True:
            game_state = await self.get_game_state(arena_address)
            if not game_state:
                await asyncio.sleep(1)
                continue

            if game_state.get("status") == "finished":
                self.log("Game finished!")
                break

            current_round = game_state.get("round_number", 1)
            if current_round != last_round:
                self.log(f"Round {current_round}")
                last_round = current_round

                # Play based on game type
                if game_type == "blackjack":
                    await self.play_blackjack_round(arena_address, game_state)
                elif game_type == "claw":
                    await self.play_claw_round(arena_address, game_state)
                elif game_type == "prediction":
                    await self.play_prediction_round(arena_address, game_state)
                elif game_type == "speed":
                    await self.play_speed_round(arena_address, game_state)

            await asyncio.sleep(2)

        # Show final results
        leaderboard = game_state.get("leaderboard", [])
        my_entry = next((p for p in leaderboard if p.get("address") == self.address), None)
        if my_entry:
            self.log(f"Final score: {my_entry.get('score', 0)} points, Rank: {my_entry.get('rank', '?')}")


async def resolve_blackjack_via_api(arena_address: str):
    """Call API to resolve blackjack round."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{API_BASE}/arenas/{arena_address}/game/resolve-blackjack",
                headers={"X-Admin-Key": ADMIN_KEY}
            )
            if resp.status_code == 200:
                print(f"[ADMIN] Resolved blackjack round: {resp.json()}")
            else:
                print(f"[ADMIN] Failed to resolve: {resp.status_code}")
        except Exception as e:
            print(f"[ADMIN] Error: {e}")


async def advance_round_via_api(arena_address: str):
    """Call API to advance to next round."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{API_BASE}/arenas/{arena_address}/game/advance-round",
                headers={"X-Admin-Key": ADMIN_KEY}
            )
            if resp.status_code == 200:
                print(f"[ADMIN] Advanced round: {resp.json()}")
            else:
                print(f"[ADMIN] Failed to advance: {resp.status_code}")
        except Exception as e:
            print(f"[ADMIN] Error: {e}")


async def run_game_master(arena_address: str, num_rounds: int = 5):
    """
    Runs as game master to control round progression.
    Useful for testing when agent is not running.
    """
    print(f"[MASTER] Starting game master for {arena_address}")

    async with httpx.AsyncClient() as client:
        for round_num in range(1, num_rounds + 1):
            print(f"[MASTER] === Round {round_num} ===")

            # Wait for players to act
            await asyncio.sleep(15)

            # Resolve blackjack if needed
            await resolve_blackjack_via_api(arena_address)

            # Advance to next round
            if round_num < num_rounds:
                await asyncio.sleep(2)
                await advance_round_via_api(arena_address)

    print("[MASTER] Game complete!")


async def main():
    parser = argparse.ArgumentParser(description="Bot player for Claw Arena games")
    parser.add_argument("--arena", required=True, help="Arena address to join")
    parser.add_argument("--num-bots", type=int, default=3, help="Number of bots to spawn")
    parser.add_argument("--master", action="store_true", help="Also run as game master")
    args = parser.parse_args()

    print(f"=== Claw Arena Bot Player ===")
    print(f"Arena: {args.arena}")
    print(f"Bots: {args.num_bots}")
    print()

    # Create bots
    bots = [BotPlayer(i) for i in range(args.num_bots)]

    # Log bot addresses
    for bot in bots:
        print(f"Bot-{bot.bot_id}: {bot.address}")
    print()

    try:
        # Run bots concurrently
        tasks = [bot.play_game(args.arena) for bot in bots]

        if args.master:
            # Also run game master
            tasks.append(run_game_master(args.arena))

        await asyncio.gather(*tasks)

    finally:
        # Cleanup
        for bot in bots:
            await bot.close()

    print("\n=== All bots finished ===")


if __name__ == "__main__":
    asyncio.run(main())
