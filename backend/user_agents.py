"""
CLAW ARENA - User Agent System

Allows users to create automated agents that:
1. Join tournaments automatically (with EIP-712 authorization)
2. Play games using configurable strategies
3. Play games on behalf of users who manually joined
4. Earn rewards while users are away

Two modes:
- AUTO-JOIN: Agent uses EIP-712 signature authorization to join arenas
- AUTO-PLAY: Agent plays games for users who manually joined an arena

This enables "passive income" gameplay where agents compete 24/7.
"""

import os
import asyncio
import random
import hashlib
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('user_agents')


class AgentMode(Enum):
    """How the agent operates"""
    AUTO_PLAY = "auto_play"    # Only plays games user manually joined
    AUTO_JOIN = "auto_join"    # Joins and plays games automatically (needs authorization)


class AgentStrategy(Enum):
    """Pre-defined playing strategies for agents"""
    CONSERVATIVE = "conservative"  # Play safe, minimize losses
    BALANCED = "balanced"          # Mix of safe and risky plays
    AGGRESSIVE = "aggressive"      # High risk, high reward
    RANDOM = "random"              # Completely random (for testing)


class AgentStatus(Enum):
    """Agent operational status"""
    ACTIVE = "active"              # Agent is running and will join games
    PAUSED = "paused"              # Agent is paused, won't join new games
    DISABLED = "disabled"          # Agent is disabled permanently
    IN_GAME = "in_game"            # Currently playing a game


@dataclass
class AgentConfig:
    """Configuration for a user agent"""
    agent_id: str
    owner_address: str                  # Wallet that owns this agent
    name: str                           # Display name for the agent
    strategy: AgentStrategy
    max_entry_fee_wei: str              # Maximum entry fee willing to pay
    min_entry_fee_wei: str              # Minimum entry fee (skip tiny games)
    preferred_games: List[str]          # Game types to join (empty = all)
    auto_join: bool = True              # Automatically join matching tournaments
    max_concurrent_games: int = 1       # Max games to play simultaneously
    daily_budget_wei: str = "0"         # Daily spending limit (0 = unlimited)

    # Mode determines how agent operates
    mode: AgentMode = AgentMode.AUTO_PLAY  # Default to safe auto-play only

    # Authorization status (for auto-join mode)
    has_authorization: bool = False
    authorization_expires_at: Optional[str] = None

    # Stats
    total_games: int = 0
    total_wins: int = 0
    total_earnings_wei: str = "0"
    total_spent_wei: str = "0"

    # Status
    status: AgentStatus = AgentStatus.ACTIVE
    current_game_id: Optional[str] = None
    current_arena_address: Optional[str] = None  # Arena being played
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_active_at: Optional[str] = None


@dataclass
class AgentGameResult:
    """Record of an agent's game result"""
    game_id: str
    arena_address: str
    agent_id: str
    game_type: str
    entry_fee_wei: str
    final_rank: int
    total_players: int
    earnings_wei: str
    played_at: str


class UserAgentManager:
    """Manages user-created agents"""

    def __init__(self, db=None, api_base: str = "http://localhost:8000"):
        self.db = db  # MongoDB database reference
        self.api_base = api_base
        self.running_agents: Dict[str, asyncio.Task] = {}
        self.http_client: Optional[httpx.AsyncClient] = None

    async def start(self):
        """Start the agent manager"""
        self.http_client = httpx.AsyncClient(timeout=30.0)
        logger.info("User Agent Manager started")

        # Load and start all active agents
        if self.db:
            agents = await self.get_all_active_agents()
            for agent in agents:
                await self.start_agent(agent.agent_id)

    async def stop(self):
        """Stop the agent manager"""
        # Stop all running agents
        for agent_id, task in self.running_agents.items():
            task.cancel()
        self.running_agents.clear()

        if self.http_client:
            await self.http_client.aclose()
        logger.info("User Agent Manager stopped")

    async def create_agent(
        self,
        owner_address: str,
        name: str,
        strategy: AgentStrategy = AgentStrategy.BALANCED,
        max_entry_fee_wei: str = "100000000000000000",  # 0.1 MON default
        min_entry_fee_wei: str = "1000000000000000",    # 0.001 MON default
        preferred_games: List[str] = None,
        auto_join: bool = False,  # Default to False (safer - auto_play mode)
        daily_budget_wei: str = "0",
        mode: AgentMode = AgentMode.AUTO_PLAY,  # Default to auto-play only
    ) -> AgentConfig:
        """
        Create a new user agent.

        Modes:
        - AUTO_PLAY: Agent only plays games that user manually joined
        - AUTO_JOIN: Agent joins and plays games automatically (needs authorization)
        """

        # Generate unique agent ID
        agent_id = hashlib.sha256(
            f"{owner_address}{time.time()}{random.random()}".encode()
        ).hexdigest()[:16]

        agent = AgentConfig(
            agent_id=agent_id,
            owner_address=owner_address.lower(),
            name=name,
            strategy=strategy,
            max_entry_fee_wei=max_entry_fee_wei,
            min_entry_fee_wei=min_entry_fee_wei,
            preferred_games=preferred_games or [],
            auto_join=auto_join,
            daily_budget_wei=daily_budget_wei,
            mode=mode,
        )

        # Save to database
        if self.db:
            agent_data = asdict(agent)
            # Convert enums to strings for MongoDB
            agent_data['strategy'] = agent.strategy.value
            agent_data['status'] = agent.status.value
            agent_data['mode'] = agent.mode.value
            await self.db.user_agents.insert_one(agent_data)

        logger.info(f"Created agent {agent_id} for {owner_address} (mode: {mode.value})")

        # Start the agent
        await self.start_agent(agent_id)

        return agent

    async def get_agent(self, agent_id: str) -> Optional[AgentConfig]:
        """Get an agent by ID"""
        if not self.db:
            return None

        data = await self.db.user_agents.find_one({"agent_id": agent_id})
        if data:
            data.pop('_id', None)
            # Convert string enums back
            data['strategy'] = AgentStrategy(data['strategy'])
            data['status'] = AgentStatus(data['status'])
            if 'mode' in data:
                data['mode'] = AgentMode(data['mode'])
            else:
                data['mode'] = AgentMode.AUTO_PLAY  # Default for old agents
            return AgentConfig(**data)
        return None

    async def get_agents_by_owner(self, owner_address: str) -> List[AgentConfig]:
        """Get all agents owned by an address"""
        if not self.db:
            return []

        agents = []
        cursor = self.db.user_agents.find({"owner_address": owner_address.lower()})
        async for data in cursor:
            data.pop('_id', None)
            data['strategy'] = AgentStrategy(data['strategy'])
            data['status'] = AgentStatus(data['status'])
            if 'mode' in data:
                data['mode'] = AgentMode(data['mode'])
            else:
                data['mode'] = AgentMode.AUTO_PLAY
            agents.append(AgentConfig(**data))
        return agents

    async def get_all_active_agents(self) -> List[AgentConfig]:
        """Get all active agents"""
        if not self.db:
            return []

        agents = []
        cursor = self.db.user_agents.find({"status": AgentStatus.ACTIVE.value})
        async for data in cursor:
            data.pop('_id', None)
            data['strategy'] = AgentStrategy(data['strategy'])
            data['status'] = AgentStatus(data['status'])
            if 'mode' in data:
                data['mode'] = AgentMode(data['mode'])
            else:
                data['mode'] = AgentMode.AUTO_PLAY
            agents.append(AgentConfig(**data))
        return agents

    async def update_agent(self, agent_id: str, updates: Dict) -> bool:
        """Update agent configuration"""
        if not self.db:
            return False

        # Don't allow updating certain fields
        protected_fields = ['agent_id', 'owner_address', 'created_at']
        for field in protected_fields:
            updates.pop(field, None)

        # Convert enums to strings for storage
        if 'strategy' in updates and isinstance(updates['strategy'], AgentStrategy):
            updates['strategy'] = updates['strategy'].value
        if 'status' in updates and isinstance(updates['status'], AgentStatus):
            updates['status'] = updates['status'].value
        if 'mode' in updates and isinstance(updates['mode'], AgentMode):
            updates['mode'] = updates['mode'].value

        result = await self.db.user_agents.update_one(
            {"agent_id": agent_id},
            {"$set": updates}
        )
        return result.modified_count > 0

    async def delete_agent(self, agent_id: str, owner_address: str) -> bool:
        """Delete an agent (only owner can delete)"""
        if not self.db:
            return False

        # Stop the agent first
        await self.stop_agent(agent_id)

        result = await self.db.user_agents.delete_one({
            "agent_id": agent_id,
            "owner_address": owner_address.lower()
        })
        return result.deleted_count > 0

    async def start_agent(self, agent_id: str) -> bool:
        """Start an agent's game loop"""
        if agent_id in self.running_agents:
            return True  # Already running

        agent = await self.get_agent(agent_id)
        if not agent or agent.status == AgentStatus.DISABLED:
            return False

        # Update status
        await self.update_agent(agent_id, {"status": AgentStatus.ACTIVE.value})

        # Create and start the agent's task
        task = asyncio.create_task(self._agent_loop(agent_id))
        self.running_agents[agent_id] = task

        logger.info(f"Started agent {agent_id}")
        return True

    async def stop_agent(self, agent_id: str) -> bool:
        """Stop an agent's game loop"""
        if agent_id in self.running_agents:
            self.running_agents[agent_id].cancel()
            del self.running_agents[agent_id]

        await self.update_agent(agent_id, {"status": AgentStatus.PAUSED.value})
        logger.info(f"Stopped agent {agent_id}")
        return True

    async def _agent_loop(self, agent_id: str):
        """Main loop for an agent - looks for games and plays them"""
        logger.info(f"Agent {agent_id} loop started")

        while True:
            try:
                agent = await self.get_agent(agent_id)
                if not agent or agent.status != AgentStatus.ACTIVE:
                    break

                # Look for available tournaments
                tournaments = await self._find_matching_tournaments(agent)

                if tournaments and agent.current_game_id is None:
                    # Join the best matching tournament
                    tournament = tournaments[0]
                    success = await self._join_tournament(agent, tournament)

                    if success:
                        # Play the game
                        await self._play_game(agent, tournament)

                # Wait before next check
                await asyncio.sleep(30)  # Check every 30 seconds

            except asyncio.CancelledError:
                logger.info(f"Agent {agent_id} loop cancelled")
                break
            except Exception as e:
                logger.error(f"Agent {agent_id} error: {e}")
                await asyncio.sleep(60)  # Wait longer on error

    async def _find_matching_tournaments(self, agent: AgentConfig) -> List[Dict]:
        """Find tournaments that match agent's criteria"""
        try:
            response = await self.http_client.get(f"{self.api_base}/api/arenas")
            if response.status_code != 200:
                return []

            arenas = response.json()
            matching = []

            for arena in arenas:
                # Skip closed or finalized
                if arena.get('is_closed') or arena.get('is_finalized'):
                    continue

                # Check entry fee range
                entry_fee = int(arena.get('entry_fee', '0'))
                if entry_fee < int(agent.min_entry_fee_wei):
                    continue
                if entry_fee > int(agent.max_entry_fee_wei):
                    continue

                # Check game type preference
                game_type = arena.get('game_type', '')
                if agent.preferred_games and game_type not in agent.preferred_games:
                    continue

                # Check if arena has space
                players = arena.get('players', [])
                max_players = arena.get('max_players', 8)
                if len(players) >= max_players:
                    continue

                # Check if agent is already in this arena
                agent_address = f"agent_{agent.agent_id}"
                if agent_address in players:
                    continue

                matching.append(arena)

            # Sort by entry fee (prefer higher stakes based on strategy)
            if agent.strategy == AgentStrategy.AGGRESSIVE:
                matching.sort(key=lambda x: int(x.get('entry_fee', '0')), reverse=True)
            elif agent.strategy == AgentStrategy.CONSERVATIVE:
                matching.sort(key=lambda x: int(x.get('entry_fee', '0')))
            else:
                random.shuffle(matching)

            return matching

        except Exception as e:
            logger.error(f"Error finding tournaments: {e}")
            return []

    async def _join_tournament(self, agent: AgentConfig, tournament: Dict) -> bool:
        """Join a tournament on behalf of the agent"""
        try:
            arena_address = tournament.get('address')

            # For now, we'll simulate joining - in production this would
            # use the owner's wallet to sign the transaction
            response = await self.http_client.post(
                f"{self.api_base}/api/arenas/{arena_address}/join-agent",
                json={
                    "agent_id": agent.agent_id,
                    "owner_address": agent.owner_address,
                }
            )

            if response.status_code == 200:
                # Update agent status
                await self.update_agent(agent.agent_id, {
                    "status": AgentStatus.IN_GAME.value,
                    "current_game_id": arena_address,
                    "last_active_at": datetime.now(timezone.utc).isoformat(),
                })
                logger.info(f"Agent {agent.agent_id} joined tournament {arena_address}")
                return True
            else:
                logger.warning(f"Agent {agent.agent_id} failed to join: {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error joining tournament: {e}")
            return False

    async def _play_game(self, agent: AgentConfig, tournament: Dict):
        """Play a game using the agent's strategy"""
        arena_address = tournament.get('address')
        game_type = tournament.get('game_type', 'blackjack')

        logger.info(f"Agent {agent.agent_id} playing {game_type} at {arena_address}")

        try:
            # Wait for game to start
            game_started = False
            for _ in range(60):  # Wait up to 5 minutes
                response = await self.http_client.get(
                    f"{self.api_base}/arenas/{arena_address}/game"
                )
                if response.status_code == 200:
                    game_state = response.json()
                    if game_state.get('status') == 'active':
                        game_started = True
                        break
                await asyncio.sleep(5)

            if not game_started:
                logger.warning(f"Game didn't start for agent {agent.agent_id}")
                return

            # Play based on game type and strategy
            if game_type == 'blackjack':
                await self._play_blackjack(agent, arena_address)
            elif game_type == 'claw':
                await self._play_claw(agent, arena_address)
            elif game_type == 'prediction':
                await self._play_prediction(agent, arena_address)
            elif game_type == 'speed':
                await self._play_speed(agent, arena_address)

            # Wait for game to finish and record result
            await self._record_game_result(agent, arena_address)

        except Exception as e:
            logger.error(f"Error playing game: {e}")
        finally:
            # Reset agent status
            await self.update_agent(agent.agent_id, {
                "status": AgentStatus.ACTIVE.value,
                "current_game_id": None,
            })

    async def _play_blackjack(self, agent: AgentConfig, arena_address: str):
        """Play blackjack using strategy"""
        agent_address = f"agent_{agent.agent_id}"

        while True:
            # Get current game state
            response = await self.http_client.get(
                f"{self.api_base}/arenas/{arena_address}/game"
            )
            if response.status_code != 200:
                break

            game_state = response.json()
            if game_state.get('status') == 'finished':
                break

            # Get our hand
            challenge = game_state.get('current_challenge', {})
            player_hands = challenge.get('player_hands', {})
            my_hand = player_hands.get(agent_address, {})

            if my_hand.get('status') != 'playing':
                await asyncio.sleep(2)
                continue

            # Calculate hand value
            total = self._calculate_blackjack_total(my_hand.get('cards', []))

            # Decide action based on strategy
            if agent.strategy == AgentStrategy.CONSERVATIVE:
                action = "stand" if total >= 15 else "hit"
            elif agent.strategy == AgentStrategy.AGGRESSIVE:
                action = "stand" if total >= 19 else "hit"
            else:  # BALANCED or RANDOM
                action = "stand" if total >= 17 else "hit"

            # Submit move
            await self.http_client.post(
                f"{self.api_base}/arenas/{arena_address}/game/move",
                json={
                    "player_address": agent_address,
                    "action": action,
                }
            )

            await asyncio.sleep(1)

    def _calculate_blackjack_total(self, cards: List[Dict]) -> int:
        """Calculate blackjack hand value"""
        total = 0
        aces = 0

        for card in cards:
            rank = card.get('rank', '')
            if rank in ['J', 'Q', 'K']:
                total += 10
            elif rank == 'A':
                aces += 1
                total += 11
            else:
                try:
                    total += int(rank)
                except ValueError:
                    pass

        while total > 21 and aces > 0:
            total -= 10
            aces -= 1

        return total

    async def _play_claw(self, agent: AgentConfig, arena_address: str):
        """Play claw machine"""
        agent_address = f"agent_{agent.agent_id}"

        for _ in range(5):  # 5 attempts
            response = await self.http_client.get(
                f"{self.api_base}/arenas/{arena_address}/game"
            )
            if response.status_code != 200:
                break

            game_state = response.json()
            if game_state.get('status') == 'finished':
                break

            # Pick a random position
            x = random.randint(10, 90)
            y = random.randint(20, 80)

            # Strategy affects prize targeting
            challenge = game_state.get('current_challenge', {})
            prizes = challenge.get('prizes', [])
            available_prizes = [p for p in prizes if not p.get('grabbed')]

            if available_prizes:
                if agent.strategy == AgentStrategy.AGGRESSIVE:
                    # Target golden/rare prizes
                    target = max(available_prizes, key=lambda p: p.get('value', 0))
                elif agent.strategy == AgentStrategy.CONSERVATIVE:
                    # Target any prize
                    target = random.choice(available_prizes)
                else:
                    target = random.choice(available_prizes)

                x = target.get('x', x)
                y = target.get('y', y)

            await self.http_client.post(
                f"{self.api_base}/arenas/{arena_address}/game/move",
                json={
                    "player_address": agent_address,
                    "x": x,
                    "y": y,
                    "prize_id": target.get('id') if available_prizes else None,
                }
            )

            await asyncio.sleep(2)

    async def _play_prediction(self, agent: AgentConfig, arena_address: str):
        """Play prediction game"""
        agent_address = f"agent_{agent.agent_id}"

        for round_num in range(3):  # 3 rounds
            response = await self.http_client.get(
                f"{self.api_base}/arenas/{arena_address}/game"
            )
            if response.status_code != 200:
                break

            game_state = response.json()
            if game_state.get('status') == 'finished':
                break

            challenge = game_state.get('current_challenge', {})
            min_val = challenge.get('min', 0)
            max_val = challenge.get('max', 100)

            # Strategy affects prediction
            if agent.strategy == AgentStrategy.CONSERVATIVE:
                # Predict near middle
                prediction = (min_val + max_val) // 2
            elif agent.strategy == AgentStrategy.AGGRESSIVE:
                # Take bigger risks
                prediction = random.choice([min_val, max_val])
            else:
                prediction = random.randint(min_val, max_val)

            await self.http_client.post(
                f"{self.api_base}/arenas/{arena_address}/game/move",
                json={
                    "player_address": agent_address,
                    "prediction": prediction,
                }
            )

            await asyncio.sleep(15)  # Wait for round to complete

    async def _play_speed(self, agent: AgentConfig, arena_address: str):
        """Play speed challenge"""
        agent_address = f"agent_{agent.agent_id}"

        for _ in range(10):  # 10 challenges
            response = await self.http_client.get(
                f"{self.api_base}/arenas/{arena_address}/game"
            )
            if response.status_code != 200:
                break

            game_state = response.json()
            if game_state.get('status') == 'finished':
                break

            challenge = game_state.get('current_challenge', {})
            challenge_type = challenge.get('type', 'math')

            # Calculate answer
            if challenge_type == 'math':
                answer = challenge.get('answer', 0)
            elif challenge_type == 'pattern':
                answer = challenge.get('answer', 0)
            else:
                answer = True

            # Response time based on strategy
            if agent.strategy == AgentStrategy.AGGRESSIVE:
                response_time = random.randint(500, 1500)  # Fast but risky
            elif agent.strategy == AgentStrategy.CONSERVATIVE:
                response_time = random.randint(2000, 4000)  # Slower but safer
            else:
                response_time = random.randint(1000, 3000)

            await asyncio.sleep(response_time / 1000)

            await self.http_client.post(
                f"{self.api_base}/arenas/{arena_address}/game/move",
                json={
                    "player_address": agent_address,
                    "answer": answer,
                    "response_time_ms": response_time,
                }
            )

            await asyncio.sleep(2)

    async def _record_game_result(self, agent: AgentConfig, arena_address: str):
        """Record the result of a game"""
        try:
            # Wait for game to be finalized
            for _ in range(30):
                response = await self.http_client.get(
                    f"{self.api_base}/api/arenas/{arena_address}"
                )
                if response.status_code == 200:
                    arena = response.json()
                    if arena.get('is_finalized'):
                        break
                await asyncio.sleep(5)

            # Get final results
            response = await self.http_client.get(
                f"{self.api_base}/arenas/{arena_address}/game/leaderboard"
            )
            if response.status_code != 200:
                return

            leaderboard = response.json()
            agent_address = f"agent_{agent.agent_id}"

            # Find agent's result
            rank = 0
            for i, entry in enumerate(leaderboard):
                if entry.get('address') == agent_address:
                    rank = i + 1
                    break

            # Calculate earnings (simplified)
            entry_fee = int(agent.current_game_id or '0')  # Would need actual fee
            earnings = 0
            if rank == 1:
                earnings = int(entry_fee * 1.7)  # 70% of pool
            elif rank == 2:
                earnings = int(entry_fee * 0.3)  # 30% of pool

            # Update agent stats
            new_total_games = agent.total_games + 1
            new_total_wins = agent.total_wins + (1 if rank <= 2 else 0)
            new_earnings = int(agent.total_earnings_wei) + earnings
            new_spent = int(agent.total_spent_wei) + entry_fee

            await self.update_agent(agent.agent_id, {
                "total_games": new_total_games,
                "total_wins": new_total_wins,
                "total_earnings_wei": str(new_earnings),
                "total_spent_wei": str(new_spent),
            })

            logger.info(f"Agent {agent.agent_id} finished rank {rank}")

        except Exception as e:
            logger.error(f"Error recording result: {e}")


# Global instance
user_agent_manager = UserAgentManager()
