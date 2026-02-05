"""
CLAW ARENA - Autonomous Tournament Director Agent

This agent is the PRIMARY CREATOR and DIRECTOR of tournaments.
It autonomously creates and manages tournaments based on:
- Historical tournament performance data
- Time-of-day and day-of-week patterns
- User activity and participation rates
- Market conditions and entry fee optimization

The agent runs on a configurable schedule, makes intelligent decisions
about tournament parameters, and maintains visible countdown timers
for the frontend.

Usage:
    python autonomous_agent.py

Environment Variables:
    AGENT_INTERVAL_MINUTES - Time between tournament creation checks (default: 30)
    MIN_TOURNAMENTS_ACTIVE - Minimum active tournaments to maintain (default: 2)
    MAX_TOURNAMENTS_ACTIVE - Maximum active tournaments allowed (default: 5)
    BACKEND_API_URL - Backend API URL (default: http://localhost:8000)
    ADMIN_API_KEY - Admin API key for backend
"""

import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum
import random
import hashlib
import time
import httpx
from dotenv import load_dotenv

load_dotenv()

# Configuration
AGENT_INTERVAL_MINUTES = int(os.environ.get('AGENT_INTERVAL_MINUTES', '30'))
MIN_TOURNAMENTS_ACTIVE = int(os.environ.get('MIN_TOURNAMENTS_ACTIVE', '2'))
MAX_TOURNAMENTS_ACTIVE = int(os.environ.get('MAX_TOURNAMENTS_ACTIVE', '5'))
BACKEND_API_URL = os.environ.get('BACKEND_API_URL', 'http://localhost:8000')
ADMIN_API_KEY = os.environ.get('ADMIN_API_KEY', '')
DEFAULT_NETWORK = os.environ.get('DEFAULT_NETWORK', 'testnet')

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('autonomous_agent')


class TournamentTier(Enum):
    """Tournament tiers based on entry fee"""
    MICRO = "micro"      # 0.001 - 0.01 MON
    SMALL = "small"      # 0.01 - 0.1 MON
    MEDIUM = "medium"    # 0.1 - 1 MON
    LARGE = "large"      # 1 - 10 MON
    WHALE = "whale"      # 10+ MON


@dataclass
class TournamentConfig:
    """Configuration for a tournament to be created"""
    name: str
    entry_fee_wei: str
    max_players: int
    protocol_fee_bps: int
    tier: TournamentTier
    reason: str  # Why the agent chose these parameters
    registration_deadline_minutes: int = 60  # How long registration stays open
    tournament_duration_minutes: int = 120  # Estimated total tournament time


@dataclass
class MarketAnalysis:
    """Analysis of current market conditions"""
    hour_of_day: int
    day_of_week: int
    is_peak_hours: bool
    is_weekend: bool
    active_tournaments: int
    avg_fill_rate: float
    popular_tier: TournamentTier
    recommended_entry_fee: str
    recommended_players: int
    confidence: float


class TournamentAnalytics:
    """Analyzes tournament data to make intelligent decisions"""

    # Entry fees in wei for each tier
    TIER_FEES = {
        TournamentTier.MICRO: [
            "1000000000000000",      # 0.001 MON
            "5000000000000000",      # 0.005 MON
        ],
        TournamentTier.SMALL: [
            "10000000000000000",     # 0.01 MON
            "50000000000000000",     # 0.05 MON
        ],
        TournamentTier.MEDIUM: [
            "100000000000000000",    # 0.1 MON
            "500000000000000000",    # 0.5 MON
        ],
        TournamentTier.LARGE: [
            "1000000000000000000",   # 1 MON
            "5000000000000000000",   # 5 MON
        ],
        TournamentTier.WHALE: [
            "10000000000000000000",  # 10 MON
            "50000000000000000000",  # 50 MON
        ],
    }

    # Player counts by tier
    TIER_PLAYERS = {
        TournamentTier.MICRO: [4, 8, 16],
        TournamentTier.SMALL: [4, 8, 16],
        TournamentTier.MEDIUM: [4, 8],
        TournamentTier.LARGE: [4, 8],
        TournamentTier.WHALE: [4],
    }

    # Registration deadline (minutes) by tier
    TIER_REGISTRATION = {
        TournamentTier.MICRO: [30, 45],
        TournamentTier.SMALL: [45, 60],
        TournamentTier.MEDIUM: [60, 90],
        TournamentTier.LARGE: [60, 120],
        TournamentTier.WHALE: [120, 180],
    }

    # Peak hours (UTC) - typically evenings in major timezones
    PEAK_HOURS = list(range(14, 23))  # 2 PM - 11 PM UTC

    # Tournament name templates
    NAME_TEMPLATES = {
        TournamentTier.MICRO: [
            "Micro Mayhem #{n}",
            "Starter Showdown #{n}",
            "Beginner's Brawl #{n}",
            "Entry Arena #{n}",
        ],
        TournamentTier.SMALL: [
            "Rising Stars #{n}",
            "Challenger Cup #{n}",
            "Arena Clash #{n}",
            "Battle Royale #{n}",
        ],
        TournamentTier.MEDIUM: [
            "Champions League #{n}",
            "Elite Showdown #{n}",
            "Grand Arena #{n}",
            "Premier Battle #{n}",
        ],
        TournamentTier.LARGE: [
            "High Stakes #{n}",
            "Diamond League #{n}",
            "Masters Tournament #{n}",
            "Prestige Cup #{n}",
        ],
        TournamentTier.WHALE: [
            "Whale Wars #{n}",
            "Titan's Arena #{n}",
            "Ultimate Showdown #{n}",
            "Legendary Battle #{n}",
        ],
    }

    def __init__(self):
        self.tournament_counter = 1

    def analyze_market(self, arenas: List[Dict], leaderboard: List[Dict]) -> MarketAnalysis:
        """Analyze current market conditions to inform tournament creation"""
        now = datetime.now(timezone.utc)
        hour = now.hour
        day = now.weekday()

        # Count active (not finalized) tournaments
        active = [a for a in arenas if not a.get('is_finalized', False)]
        active_count = len(active)

        # Calculate average fill rate
        fill_rates = []
        for arena in arenas:
            players = len(arena.get('players', []))
            max_players = arena.get('max_players', 8)
            if max_players > 0:
                fill_rates.append(players / max_players)
        avg_fill_rate = sum(fill_rates) / len(fill_rates) if fill_rates else 0.5

        # Determine peak hours
        is_peak = hour in self.PEAK_HOURS
        is_weekend = day >= 5

        # Analyze popular tiers from historical data
        tier_participation = {tier: 0 for tier in TournamentTier}
        for arena in arenas:
            entry_fee = int(arena.get('entry_fee', '0'))
            tier = self._fee_to_tier(entry_fee)
            players = len(arena.get('players', []))
            tier_participation[tier] += players

        popular_tier = max(tier_participation, key=tier_participation.get)
        if tier_participation[popular_tier] == 0:
            # Default to SMALL if no data
            popular_tier = TournamentTier.SMALL

        # Recommend entry fee and players based on analysis
        if is_peak and is_weekend:
            # Peak weekend - go bigger
            recommended_tier = self._tier_up(popular_tier)
            confidence = 0.8
        elif is_peak:
            # Peak weekday
            recommended_tier = popular_tier
            confidence = 0.7
        elif is_weekend:
            # Off-peak weekend
            recommended_tier = popular_tier
            confidence = 0.6
        else:
            # Off-peak weekday - smaller tournaments
            recommended_tier = self._tier_down(popular_tier)
            confidence = 0.5

        # Adjust based on fill rate
        if avg_fill_rate < 0.3:
            # Low fill rate - go smaller
            recommended_tier = self._tier_down(recommended_tier)
            confidence *= 0.8
        elif avg_fill_rate > 0.8:
            # High fill rate - can go bigger
            recommended_tier = self._tier_up(recommended_tier)
            confidence *= 1.1

        # Get recommended fee and players
        fees = self.TIER_FEES[recommended_tier]
        players_options = self.TIER_PLAYERS[recommended_tier]

        return MarketAnalysis(
            hour_of_day=hour,
            day_of_week=day,
            is_peak_hours=is_peak,
            is_weekend=is_weekend,
            active_tournaments=active_count,
            avg_fill_rate=avg_fill_rate,
            popular_tier=popular_tier,
            recommended_entry_fee=random.choice(fees),
            recommended_players=random.choice(players_options),
            confidence=min(confidence, 1.0)
        )

    def _fee_to_tier(self, fee_wei: int) -> TournamentTier:
        """Convert entry fee to tier"""
        if fee_wei < 10000000000000000:  # < 0.01 MON
            return TournamentTier.MICRO
        elif fee_wei < 100000000000000000:  # < 0.1 MON
            return TournamentTier.SMALL
        elif fee_wei < 1000000000000000000:  # < 1 MON
            return TournamentTier.MEDIUM
        elif fee_wei < 10000000000000000000:  # < 10 MON
            return TournamentTier.LARGE
        else:
            return TournamentTier.WHALE

    def _tier_up(self, tier: TournamentTier) -> TournamentTier:
        """Move to a higher tier"""
        tiers = list(TournamentTier)
        idx = tiers.index(tier)
        return tiers[min(idx + 1, len(tiers) - 1)]

    def _tier_down(self, tier: TournamentTier) -> TournamentTier:
        """Move to a lower tier"""
        tiers = list(TournamentTier)
        idx = tiers.index(tier)
        return tiers[max(idx - 1, 0)]

    def generate_tournament_config(self, analysis: MarketAnalysis) -> TournamentConfig:
        """Generate tournament configuration based on market analysis"""
        tier = self._fee_to_tier(int(analysis.recommended_entry_fee))

        # Generate tournament name
        name_template = random.choice(self.NAME_TEMPLATES[tier])
        name = name_template.format(n=self.tournament_counter)
        self.tournament_counter += 1

        # Determine protocol fee (higher for larger tournaments)
        if tier in [TournamentTier.WHALE, TournamentTier.LARGE]:
            protocol_fee_bps = 200  # 2%
        elif tier == TournamentTier.MEDIUM:
            protocol_fee_bps = 250  # 2.5%
        else:
            protocol_fee_bps = 300  # 3%

        # Registration deadline based on tier
        reg_options = self.TIER_REGISTRATION[tier]
        reg_deadline = random.randint(reg_options[0], reg_options[1])

        # Tournament duration estimate (registration + competition)
        tournament_duration = reg_deadline + random.randint(30, 90)

        # Build reason string
        reasons = []
        if analysis.is_peak_hours:
            reasons.append("peak hours")
        if analysis.is_weekend:
            reasons.append("weekend boost")
        if analysis.avg_fill_rate > 0.7:
            reasons.append("high engagement")
        elif analysis.avg_fill_rate < 0.3:
            reasons.append("low engagement - smaller tier")
        reasons.append(f"{analysis.confidence:.0%} confidence")

        return TournamentConfig(
            name=name,
            entry_fee_wei=analysis.recommended_entry_fee,
            max_players=analysis.recommended_players,
            protocol_fee_bps=protocol_fee_bps,
            tier=tier,
            reason=", ".join(reasons),
            registration_deadline_minutes=reg_deadline,
            tournament_duration_minutes=tournament_duration,
        )

    def calculate_next_tournament_delay(self, analysis: MarketAnalysis) -> int:
        """Calculate delay (in minutes) before creating the next tournament"""
        if analysis.is_peak_hours and analysis.is_weekend:
            return random.randint(3, 10)
        elif analysis.is_peak_hours:
            return random.randint(5, 15)
        elif analysis.is_weekend:
            return random.randint(10, 20)
        else:
            return random.randint(15, 30)


class AutonomousAgent:
    """The main autonomous agent - PRIMARY TOURNAMENT DIRECTOR"""

    def __init__(self):
        self.analytics = TournamentAnalytics()
        self.http_client: Optional[httpx.AsyncClient] = None
        self.running = False

    async def start(self):
        """Start the autonomous agent"""
        logger.info("=" * 60)
        logger.info("CLAW ARENA Autonomous Tournament Director Starting")
        logger.info(f"   Interval: {AGENT_INTERVAL_MINUTES} minutes")
        logger.info(f"   Min Active: {MIN_TOURNAMENTS_ACTIVE}")
        logger.info(f"   Max Active: {MAX_TOURNAMENTS_ACTIVE}")
        logger.info(f"   Backend: {BACKEND_API_URL}")
        logger.info(f"   Network: {DEFAULT_NETWORK}")
        logger.info("=" * 60)

        if not ADMIN_API_KEY:
            logger.error("ADMIN_API_KEY not set. Agent cannot create tournaments.")
            return

        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.running = True

        try:
            # Run first cycle immediately
            await self.run_cycle()

            while self.running:
                logger.info(f"Sleeping for {AGENT_INTERVAL_MINUTES} minutes...")
                await asyncio.sleep(AGENT_INTERVAL_MINUTES * 60)
                await self.run_cycle()
        except asyncio.CancelledError:
            logger.info("Agent shutdown requested")
        finally:
            if self.http_client:
                await self.http_client.aclose()

    async def stop(self):
        """Stop the autonomous agent"""
        self.running = False

    async def run_cycle(self):
        """Run one cycle of the agent"""
        logger.info("Starting agent cycle...")

        try:
            # Fetch current state
            arenas = await self._get_arenas()
            leaderboard = await self._get_leaderboard()

            # Analyze market
            analysis = self.analytics.analyze_market(arenas, leaderboard)
            logger.info(f"Market Analysis:")
            logger.info(f"   Hour: {analysis.hour_of_day}, Day: {analysis.day_of_week}")
            logger.info(f"   Peak: {analysis.is_peak_hours}, Weekend: {analysis.is_weekend}")
            logger.info(f"   Active Tournaments: {analysis.active_tournaments}")
            logger.info(f"   Avg Fill Rate: {analysis.avg_fill_rate:.1%}")
            logger.info(f"   Popular Tier: {analysis.popular_tier.value}")
            logger.info(f"   Confidence: {analysis.confidence:.1%}")

            # Check if we need to create tournaments
            active_count = analysis.active_tournaments
            tournaments_created = 0

            if active_count >= MAX_TOURNAMENTS_ACTIVE:
                logger.info(f"Max active tournaments reached ({active_count}/{MAX_TOURNAMENTS_ACTIVE})")
            else:
                # Determine how many to create
                tournaments_needed = max(0, MIN_TOURNAMENTS_ACTIVE - active_count)

                # During peak hours, be more aggressive
                if analysis.is_peak_hours and active_count < MAX_TOURNAMENTS_ACTIVE - 1:
                    tournaments_needed = max(tournaments_needed, 1)

                if tournaments_needed == 0 and analysis.confidence > 0.7 and active_count < MAX_TOURNAMENTS_ACTIVE:
                    # High confidence, create one more
                    tournaments_needed = 1

                logger.info(f"Planning to create {tournaments_needed} tournament(s)")

                # Create tournaments
                for i in range(tournaments_needed):
                    config = self.analytics.generate_tournament_config(analysis)
                    success = await self._create_tournament(config)
                    if success:
                        tournaments_created += 1

            # Calculate next tournament time
            delay_minutes = self.analytics.calculate_next_tournament_delay(analysis)
            next_tournament_at = (
                datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)
            ).isoformat()

            # Update schedule in backend
            await self._update_schedule(
                next_tournament_at=next_tournament_at,
                analysis=analysis,
            )

            logger.info(f"Next tournament check in ~{delay_minutes} minutes")

            # Check for tournaments ready to finalize
            await self._check_finalizations(arenas)

        except Exception as e:
            logger.error(f"Cycle error: {e}")

    async def _get_arenas(self) -> List[Dict]:
        """Fetch all arenas from backend"""
        try:
            response = await self.http_client.get(
                f"{BACKEND_API_URL}/api/arenas",
                params={"network": DEFAULT_NETWORK}
            )
            if response.status_code == 200:
                return response.json()
            logger.error(f"Failed to get arenas: {response.status_code}")
            return []
        except Exception as e:
            logger.error(f"Error fetching arenas: {e}")
            return []

    async def _get_leaderboard(self) -> List[Dict]:
        """Fetch leaderboard from backend"""
        try:
            response = await self.http_client.get(
                f"{BACKEND_API_URL}/api/leaderboard",
                params={"limit": 100}
            )
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            logger.error(f"Error fetching leaderboard: {e}")
            return []

    async def _create_tournament(self, config: TournamentConfig) -> bool:
        """Create a tournament via the backend API"""
        logger.info(f"Creating Tournament:")
        logger.info(f"   Name: {config.name}")
        logger.info(f"   Entry Fee: {int(config.entry_fee_wei) / 1e18:.4f} MON")
        logger.info(f"   Max Players: {config.max_players}")
        logger.info(f"   Tier: {config.tier.value}")
        logger.info(f"   Registration: {config.registration_deadline_minutes} min")
        logger.info(f"   Reason: {config.reason}")

        try:
            # Generate a placeholder contract address
            # In production, this would come from actual contract deployment
            placeholder = hashlib.sha256(f"{config.name}{time.time()}".encode()).hexdigest()
            contract_address = f"0x{placeholder[:40]}"

            # Calculate timer timestamps
            now = datetime.now(timezone.utc)
            registration_deadline = (
                now + timedelta(minutes=config.registration_deadline_minutes)
            ).isoformat()
            tournament_end_estimate = (
                now + timedelta(minutes=config.tournament_duration_minutes)
            ).isoformat()

            response = await self.http_client.post(
                f"{BACKEND_API_URL}/api/admin/arena/create",
                params={"network": DEFAULT_NETWORK},
                headers={"X-Admin-Key": ADMIN_API_KEY},
                json={
                    "name": config.name,
                    "entry_fee": config.entry_fee_wei,
                    "max_players": config.max_players,
                    "protocol_fee_bps": config.protocol_fee_bps,
                    "contract_address": contract_address,
                }
            )

            if response.status_code == 200:
                arena = response.json()
                arena_address = arena.get('address', contract_address)
                logger.info(f"Tournament created: {arena_address}")

                # Update the arena with timer fields and agent metadata
                await self._update_arena_timers(
                    arena_address,
                    registration_deadline,
                    tournament_end_estimate,
                    config.reason,
                )

                # Notify backend that agent created a tournament
                await self._notify_tournament_created()

                return True
            else:
                logger.error(f"Failed to create tournament: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error creating tournament: {e}")
            return False

    async def _update_arena_timers(
        self,
        arena_address: str,
        registration_deadline: str,
        tournament_end_estimate: str,
        creation_reason: str,
    ):
        """Update arena with timer fields via direct DB update endpoint"""
        try:
            # Use the indexer endpoint to update arena fields
            response = await self.http_client.post(
                f"{BACKEND_API_URL}/api/indexer/event/arena-created",
                json={
                    "address": arena_address,
                    "registration_deadline": registration_deadline,
                    "tournament_end_estimate": tournament_end_estimate,
                    "created_by": "agent",
                    "creation_reason": creation_reason,
                }
            )
            if response.status_code != 200:
                logger.warning(f"Failed to update arena timers: {response.status_code}")
        except Exception as e:
            logger.warning(f"Error updating arena timers: {e}")

    async def _update_schedule(self, next_tournament_at: str, analysis: MarketAnalysis):
        """Update agent schedule in backend"""
        try:
            response = await self.http_client.post(
                f"{BACKEND_API_URL}/api/agent/update-schedule",
                headers={"X-Admin-Key": ADMIN_API_KEY},
                params={
                    "next_tournament_at": next_tournament_at,
                    "status": "active",
                },
                json={
                    "hour_of_day": analysis.hour_of_day,
                    "day_of_week": analysis.day_of_week,
                    "is_peak_hours": analysis.is_peak_hours,
                    "is_weekend": analysis.is_weekend,
                    "active_tournaments": analysis.active_tournaments,
                    "avg_fill_rate": analysis.avg_fill_rate,
                    "popular_tier": analysis.popular_tier.value,
                    "confidence": analysis.confidence,
                }
            )
            if response.status_code != 200:
                logger.warning(f"Failed to update schedule: {response.status_code}")
        except Exception as e:
            logger.warning(f"Error updating schedule: {e}")

    async def _notify_tournament_created(self):
        """Notify backend that agent created a tournament"""
        try:
            await self.http_client.post(
                f"{BACKEND_API_URL}/api/agent/tournament-created",
                headers={"X-Admin-Key": ADMIN_API_KEY},
            )
        except Exception as e:
            logger.warning(f"Error notifying tournament created: {e}")

    async def _check_finalizations(self, arenas: List[Dict]):
        """Check for tournaments that are ready to finalize"""
        for arena in arenas:
            if arena.get('is_finalized') or not arena.get('is_closed'):
                continue

            players = arena.get('players', [])
            if len(players) < 2:
                continue

            address = arena.get('address')
            logger.info(f"Arena {address[:10]}... is ready for finalization")

            # In production, this would:
            # 1. Run a bracket simulation or get results from a game
            # 2. Determine winners and amounts
            # 3. Request signature and finalize

            # For demo, we select random winners
            # First place gets 70%, second gets 30%
            total_pool = int(arena.get('entry_fee', '0')) * len(players)
            protocol_fee = total_pool * arena.get('protocol_fee_bps', 250) // 10000
            prize_pool = total_pool - protocol_fee

            if len(players) >= 2:
                winners = random.sample(players, min(2, len(players)))
                amounts = [
                    str(int(prize_pool * 0.7)),
                    str(int(prize_pool * 0.3))
                ]

                logger.info(f"   Winners: {winners[0][:10]}..., {winners[1][:10]}...")
                logger.info(f"   Prizes: {int(amounts[0])/1e18:.4f} MON, {int(amounts[1])/1e18:.4f} MON")

                # Note: Actual finalization would be triggered here
                # await self._finalize_tournament(address, winners, amounts)


async def main():
    """Main entry point"""
    agent = AutonomousAgent()

    # Handle shutdown gracefully
    import signal

    def shutdown_handler(signum, frame):
        logger.info("Shutdown signal received...")
        asyncio.create_task(agent.stop())

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    await agent.start()


if __name__ == "__main__":
    asyncio.run(main())
