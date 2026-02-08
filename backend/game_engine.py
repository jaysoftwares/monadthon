"""
CLAW ARENA - Game Engine

Supports 4 game types that rotate each tournament:
1. Claw Mini-Game - Skill-based claw machine
2. Prediction Arena - Predict crypto prices
3. Speed Challenge - Reaction time & puzzles
4. Blackjack Tournament - Card game competition

Each game has:
- Rules/tutorial content for 1-minute learn phase
- Game state management
- Winner determination logic
- Provably fair randomness using block hashes
"""

import os
import random
import hashlib
import time
import asyncio
from enum import Enum
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
import json


class GameType(Enum):
    """Available game types"""
    CLAW = "claw"
    PREDICTION = "prediction"
    SPEED = "speed"
    BLACKJACK = "blackjack"


@dataclass
class GameRules:
    """Rules and tutorial content for a game type"""
    game_type: GameType
    name: str
    description: str
    how_to_play: List[str]
    tips: List[str]
    duration_seconds: int
    min_players: int
    max_players: int


@dataclass
class PlayerState:
    """State for a single player in a game"""
    address: str
    score: int = 0
    moves: List[Dict] = field(default_factory=list)
    is_eliminated: bool = False
    final_rank: Optional[int] = None


@dataclass
class GameState:
    """Complete state for a game session"""
    game_id: str
    arena_address: str
    game_type: GameType
    status: str  # "learning", "active", "finished"
    players: Dict[str, PlayerState] = field(default_factory=dict)
    round_number: int = 1
    current_challenge: Optional[Dict] = None
    started_at: Optional[str] = None
    ends_at: Optional[str] = None
    winners: List[str] = field(default_factory=list)
    prize_amounts: List[str] = field(default_factory=list)
    seed: str = ""  # Provably fair seed from block hash


# Game Rules Definitions
GAME_RULES: Dict[GameType, GameRules] = {
    GameType.CLAW: GameRules(
        game_type=GameType.CLAW,
        name="Claw Machine Madness",
        description="Control the claw to grab prizes! Each prize has different point values. Highest score wins!",
        how_to_play=[
            "Use arrow keys or swipe to position the claw",
            "Press SPACE or tap to drop the claw",
            "Grab prizes worth 10-100 points each",
            "You get 5 attempts to maximize your score",
            "Golden prizes are worth 100 points!",
        ],
        tips=[
            "Aim for the edges of prizes for better grip",
            "Golden prizes are rare but worth it",
            "Watch the claw swing - time your drop!",
        ],
        duration_seconds=120,
        min_players=2,
        max_players=16,
    ),
    GameType.PREDICTION: GameRules(
        game_type=GameType.PREDICTION,
        name="Prediction Arena",
        description="Predict the future! Guess prices, numbers, or outcomes. Closest prediction wins!",
        how_to_play=[
            "A prediction challenge will appear",
            "Enter your best guess before time runs out",
            "Predictions are hidden until reveal",
            "Closest to actual result wins the round",
            "3 rounds total - most round wins takes the prize!",
        ],
        tips=[
            "Use market data if predicting prices",
            "Consider recent trends",
            "Sometimes the obvious answer is right!",
        ],
        duration_seconds=180,
        min_players=2,
        max_players=32,
    ),
    GameType.SPEED: GameRules(
        game_type=GameType.SPEED,
        name="Speed Challenge",
        description="Test your reflexes and brainpower! Solve puzzles and react faster than your opponents!",
        how_to_play=[
            "Complete challenges as fast as possible",
            "Challenges include: math, patterns, reactions",
            "Each challenge has a time limit",
            "Faster correct answers = more points",
            "Wrong answers cost you 5 seconds penalty!",
        ],
        tips=[
            "Stay focused - speed matters!",
            "Don't rush into wrong answers",
            "Practice mental math",
        ],
        duration_seconds=90,
        min_players=2,
        max_players=16,
    ),
    GameType.BLACKJACK: GameRules(
        game_type=GameType.BLACKJACK,
        name="Blackjack Showdown",
        description="Classic 21! Beat the dealer and outlast other players in this card game tournament!",
        how_to_play=[
            "Get cards as close to 21 as possible",
            "Face cards = 10, Aces = 1 or 11",
            "Hit to get another card, Stand to hold",
            "Go over 21 and you bust!",
            "Beat the dealer to win chips, most chips wins!",
        ],
        tips=[
            "Stand on 17 or higher",
            "Hit on 11 or lower",
            "Watch what cards have been played",
        ],
        duration_seconds=180,
        min_players=2,
        max_players=8,
    ),
}


class GameEngine:
    """Main game engine that manages all game types"""

    def __init__(self):
        self.active_games: Dict[str, GameState] = {}
        self.game_history: List[Dict] = []

    def get_rules(self, game_type: GameType) -> GameRules:
        """Get rules for a game type"""
        return GAME_RULES[game_type]

    def select_random_game(self, player_count: int) -> GameType:
        """Select a random game type suitable for the player count"""
        suitable_games = [
            gt for gt, rules in GAME_RULES.items()
            if rules.min_players <= player_count <= rules.max_players
        ]
        if not suitable_games:
            # Default to prediction which supports most players
            return GameType.PREDICTION
        return random.choice(suitable_games)

    def create_game(
        self,
        arena_address: str,
        game_type: GameType,
        players: List[str],
        block_hash: str = None,
    ) -> GameState:
        """Create a new game session"""
        game_id = hashlib.sha256(
            f"{arena_address}{time.time()}{random.random()}".encode()
        ).hexdigest()[:16]

        # Create provably fair seed from block hash or generate one
        if block_hash:
            seed = block_hash
        else:
            seed = hashlib.sha256(f"{game_id}{time.time()}".encode()).hexdigest()

        # Initialize player states
        player_states = {
            addr: PlayerState(address=addr)
            for addr in players
        }

        now = datetime.now(timezone.utc)
        rules = GAME_RULES[game_type]

        game_state = GameState(
            game_id=game_id,
            arena_address=arena_address,
            game_type=game_type,
            status="learning",
            players=player_states,
            started_at=now.isoformat(),
            ends_at=(now + timedelta(seconds=rules.duration_seconds + 60)).isoformat(),
            seed=seed,
        )

        self.active_games[game_id] = game_state
        return game_state

    def start_game(self, game_id: str) -> GameState:
        """Transition game from learning to active"""
        if game_id not in self.active_games:
            raise ValueError(f"Game {game_id} not found")

        game = self.active_games[game_id]
        game.status = "active"

        # Generate first challenge based on game type
        game.current_challenge = self._generate_challenge(game)

        return game

    def _generate_challenge(self, game: GameState) -> Dict:
        """Generate a challenge based on game type"""
        if game.game_type == GameType.CLAW:
            return self._generate_claw_challenge(game)
        elif game.game_type == GameType.PREDICTION:
            return self._generate_prediction_challenge(game)
        elif game.game_type == GameType.SPEED:
            return self._generate_speed_challenge(game)
        elif game.game_type == GameType.BLACKJACK:
            return self._generate_blackjack_challenge(game)
        return {}

    def _generate_claw_challenge(self, game: GameState) -> Dict:
        """Generate claw machine prize layout"""
        # Use seed for deterministic but fair randomness
        rng = random.Random(f"{game.seed}{game.round_number}")

        prizes = []
        for i in range(12):
            prize_type = rng.choices(
                ["common", "uncommon", "rare", "golden"],
                weights=[50, 30, 15, 5]
            )[0]
            value = {"common": 10, "uncommon": 25, "rare": 50, "golden": 100}[prize_type]
            prizes.append({
                "id": i,
                "type": prize_type,
                "value": value,
                "x": rng.randint(10, 90),
                "y": rng.randint(20, 80),
                "grabbed": False,
            })

        return {
            "type": "claw_round",
            "round": game.round_number,
            "prizes": prizes,
            "attempts_per_player": 5,
            "time_limit": 120,
        }

    def _generate_prediction_challenge(self, game: GameState) -> Dict:
        """Generate a prediction challenge"""
        rng = random.Random(f"{game.seed}{game.round_number}")

        challenges = [
            {
                "question": "What will be the last 2 digits of the next block number?",
                "type": "number",
                "min": 0,
                "max": 99,
                "reveal_delay": 30,
            },
            {
                "question": "Guess a number between 1-1000. Closest to the secret wins!",
                "type": "number",
                "min": 1,
                "max": 1000,
                "secret": rng.randint(1, 1000),
                "reveal_delay": 0,
            },
            {
                "question": "How many transactions in the next Monad block?",
                "type": "number",
                "min": 0,
                "max": 10000,
                "reveal_delay": 15,
            },
        ]

        challenge = rng.choice(challenges)
        challenge["round"] = game.round_number
        challenge["time_limit"] = 45

        return challenge

    def _generate_speed_challenge(self, game: GameState) -> Dict:
        """Generate a speed/reaction challenge"""
        rng = random.Random(f"{game.seed}{game.round_number}")

        challenge_types = [
            self._math_challenge,
            self._pattern_challenge,
            self._reaction_challenge,
        ]

        generator = rng.choice(challenge_types)
        challenge = generator(rng, game.round_number)

        return challenge

    def _math_challenge(self, rng: random.Random, round_num: int) -> Dict:
        """Generate a math problem"""
        a = rng.randint(10, 99)
        b = rng.randint(10, 99)
        op = rng.choice(["+", "-", "*"])

        if op == "+":
            answer = a + b
        elif op == "-":
            answer = a - b
        else:
            answer = a * b

        return {
            "type": "math",
            "round": round_num,
            "question": f"What is {a} {op} {b}?",
            "answer": answer,
            "time_limit": 10,
        }

    def _pattern_challenge(self, rng: random.Random, round_num: int) -> Dict:
        """Generate a pattern recognition challenge"""
        start = rng.randint(1, 10)
        step = rng.randint(2, 5)
        sequence = [start + i * step for i in range(4)]
        answer = start + 4 * step

        return {
            "type": "pattern",
            "round": round_num,
            "question": f"What comes next: {', '.join(map(str, sequence))}, ?",
            "answer": answer,
            "time_limit": 15,
        }

    def _reaction_challenge(self, rng: random.Random, round_num: int) -> Dict:
        """Generate a reaction time challenge"""
        return {
            "type": "reaction",
            "round": round_num,
            "question": "Click/tap when the screen turns GREEN!",
            "delay_ms": rng.randint(2000, 5000),
            "time_limit": 10,
        }

    def _generate_blackjack_challenge(self, game: GameState) -> Dict:
        """Generate a blackjack hand"""
        rng = random.Random(f"{game.seed}{game.round_number}")

        # Create and shuffle deck
        suits = ["hearts", "diamonds", "clubs", "spades"]
        ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
        deck = [{"suit": s, "rank": r} for s in suits for r in ranks]
        rng.shuffle(deck)

        # Deal initial hands
        player_hands = {}
        deck_index = 0

        for addr in game.players:
            player_hands[addr] = {
                "cards": [deck[deck_index], deck[deck_index + 1]],
                "status": "playing",
            }
            deck_index += 2

        dealer_hand = {
            "cards": [deck[deck_index], deck[deck_index + 1]],
            "hidden": True,
        }
        deck_index += 2

        return {
            "type": "blackjack_round",
            "round": game.round_number,
            "player_hands": player_hands,
            "dealer_hand": dealer_hand,
            "deck_position": deck_index,
            "deck": deck,  # Full deck for server-side dealing
            "time_limit": 30,
        }

    def submit_move(
        self,
        game_id: str,
        player_address: str,
        move: Dict,
    ) -> Tuple[bool, str, Optional[Dict]]:
        """Submit a player move and return (success, message, updated_state)"""
        if game_id not in self.active_games:
            return False, "Game not found", None

        game = self.active_games[game_id]

        if game.status != "active":
            return False, f"Game is {game.status}", None

        if player_address not in game.players:
            return False, "Player not in game", None

        player = game.players[player_address]
        if player.is_eliminated:
            return False, "Player eliminated", None

        # Process move based on game type
        if game.game_type == GameType.CLAW:
            return self._process_claw_move(game, player, move)
        elif game.game_type == GameType.PREDICTION:
            return self._process_prediction_move(game, player, move)
        elif game.game_type == GameType.SPEED:
            return self._process_speed_move(game, player, move)
        elif game.game_type == GameType.BLACKJACK:
            return self._process_blackjack_move(game, player, move)

        return False, "Unknown game type", None

    def _process_claw_move(
        self, game: GameState, player: PlayerState, move: Dict
    ) -> Tuple[bool, str, Optional[Dict]]:
        """Process a claw grab attempt"""
        challenge = game.current_challenge
        prize_id = move.get("prize_id")
        grab_x = move.get("x")
        grab_y = move.get("y")

        # Find the prize
        for prize in challenge["prizes"]:
            if prize["id"] == prize_id and not prize["grabbed"]:
                # Calculate grab success (simplified)
                distance = ((prize["x"] - grab_x) ** 2 + (prize["y"] - grab_y) ** 2) ** 0.5
                success_chance = max(0, 1 - distance / 20)

                rng = random.Random(f"{game.seed}{player.address}{len(player.moves)}")
                if rng.random() < success_chance:
                    prize["grabbed"] = True
                    player.score += prize["value"]
                    player.moves.append({"type": "grab", "prize": prize_id, "success": True})
                    return True, f"Grabbed {prize['type']} prize! +{prize['value']} points", {"score": player.score}
                else:
                    player.moves.append({"type": "grab", "prize": prize_id, "success": False})
                    return True, "Missed! The claw slipped.", {"score": player.score}

        return False, "Invalid prize", None

    def _process_prediction_move(
        self, game: GameState, player: PlayerState, move: Dict
    ) -> Tuple[bool, str, Optional[Dict]]:
        """Process a prediction submission"""
        prediction = move.get("prediction")

        if prediction is None:
            return False, "No prediction provided", None

        player.moves.append({
            "round": game.round_number,
            "prediction": prediction,
            "timestamp": time.time(),
        })

        return True, "Prediction locked in!", {"prediction": prediction}

    def _process_speed_move(
        self, game: GameState, player: PlayerState, move: Dict
    ) -> Tuple[bool, str, Optional[Dict]]:
        """Process a speed challenge answer"""
        answer = move.get("answer")
        response_time_ms = move.get("response_time_ms", 10000)
        challenge = game.current_challenge

        correct = False
        if challenge["type"] == "reaction":
            # Reaction time - lower is better
            if response_time_ms < 500:
                points = 100 - int(response_time_ms / 5)
                player.score += max(points, 10)
                correct = True
        else:
            # Math or pattern - check answer
            if answer == challenge["answer"]:
                points = max(10, 100 - int(response_time_ms / 100))
                player.score += points
                correct = True
            else:
                player.score = max(0, player.score - 5)

        player.moves.append({
            "round": game.round_number,
            "answer": answer,
            "correct": correct,
            "response_time_ms": response_time_ms,
        })

        if correct:
            return True, f"Correct! +{points} points", {"score": player.score}
        else:
            return True, "Wrong answer! -5 points", {"score": player.score}

    def _process_blackjack_move(
        self, game: GameState, player: PlayerState, move: Dict
    ) -> Tuple[bool, str, Optional[Dict]]:
        """Process a blackjack action (hit/stand)"""
        action = move.get("action")
        challenge = game.current_challenge
        hand = challenge["player_hands"].get(player.address)

        if not hand or hand["status"] != "playing":
            return False, "Cannot act", None

        if action == "hit":
            # Deal another card
            deck = challenge["deck"]
            pos = challenge["deck_position"]
            new_card = deck[pos]
            challenge["deck_position"] = pos + 1
            hand["cards"].append(new_card)

            # Check for bust
            total = self._calculate_blackjack_hand(hand["cards"])
            if total > 21:
                hand["status"] = "bust"
                player.moves.append({"action": "hit", "bust": True})
                return True, f"Bust! Total: {total}", {"hand": hand, "total": total}

            player.moves.append({"action": "hit", "card": new_card})
            return True, f"Hit! Total: {total}", {"hand": hand, "total": total}

        elif action == "stand":
            hand["status"] = "stand"
            total = self._calculate_blackjack_hand(hand["cards"])
            player.moves.append({"action": "stand", "total": total})
            return True, f"Stand at {total}", {"hand": hand, "total": total}

        return False, "Invalid action", None

    def _calculate_blackjack_hand(self, cards: List[Dict]) -> int:
        """Calculate blackjack hand value"""
        total = 0
        aces = 0

        for card in cards:
            rank = card["rank"]
            if rank in ["J", "Q", "K"]:
                total += 10
            elif rank == "A":
                aces += 1
                total += 11
            else:
                total += int(rank)

        # Adjust aces
        while total > 21 and aces > 0:
            total -= 10
            aces -= 1

        return total

    def resolve_blackjack_round(self, game_id: str) -> Dict:
        """
        Resolve a blackjack round:
        1. Dealer plays (hits until 17+)
        2. Compare hands and award points
        3. Return results
        """
        if game_id not in self.active_games:
            return {"error": "Game not found"}

        game = self.active_games[game_id]
        if game.game_type != GameType.BLACKJACK:
            return {"error": "Not a blackjack game"}

        challenge = game.current_challenge
        if not challenge:
            return {"error": "No active challenge"}

        dealer_hand = challenge["dealer_hand"]
        deck = challenge["deck"]
        deck_pos = challenge["deck_position"]

        # Reveal dealer's hidden card
        dealer_hand["hidden"] = False

        # Dealer plays: hit until 17 or higher
        dealer_total = self._calculate_blackjack_hand(dealer_hand["cards"])
        while dealer_total < 17:
            new_card = deck[deck_pos]
            deck_pos += 1
            dealer_hand["cards"].append(new_card)
            dealer_total = self._calculate_blackjack_hand(dealer_hand["cards"])

        challenge["deck_position"] = deck_pos
        dealer_bust = dealer_total > 21

        # Score each player
        results = {
            "dealer_cards": dealer_hand["cards"],
            "dealer_total": dealer_total,
            "dealer_bust": dealer_bust,
            "player_results": {}
        }

        for addr, player_state in game.players.items():
            hand = challenge["player_hands"].get(addr)
            if not hand:
                continue

            player_total = self._calculate_blackjack_hand(hand["cards"])
            player_bust = hand["status"] == "bust"

            # Determine outcome and points
            if player_bust:
                outcome = "bust"
                points = -10  # Penalty for busting
            elif dealer_bust:
                outcome = "win"
                points = 20  # Dealer bust, player wins
            elif player_total > dealer_total:
                outcome = "win"
                points = 15  # Beat dealer
            elif player_total == dealer_total:
                outcome = "push"
                points = 0  # Tie
            else:
                outcome = "lose"
                points = -5  # Lost to dealer

            # Blackjack bonus (21 with 2 cards)
            if player_total == 21 and len(hand["cards"]) == 2:
                outcome = "blackjack"
                points = 25  # Blackjack pays extra

            # Apply points
            player_state.score += points

            results["player_results"][addr] = {
                "cards": hand["cards"],
                "total": player_total,
                "outcome": outcome,
                "points": points,
                "new_score": player_state.score
            }

        return results

    def advance_round(self, game_id: str) -> Optional[GameState]:
        """Advance to next round or finish game"""
        if game_id not in self.active_games:
            return None

        game = self.active_games[game_id]
        rules = GAME_RULES[game.game_type]

        # For blackjack, resolve the current round before advancing
        # This makes the dealer play and awards points
        if game.game_type == GameType.BLACKJACK and game.current_challenge:
            round_results = self.resolve_blackjack_round(game_id)
            # Store results in challenge for frontend display
            if "player_results" in round_results:
                game.current_challenge["round_results"] = round_results

        # Determine max rounds based on game type
        max_rounds = {
            GameType.CLAW: 1,  # Single round, multiple attempts
            GameType.PREDICTION: 3,
            GameType.SPEED: 10,
            GameType.BLACKJACK: 5,
        }

        if game.round_number >= max_rounds[game.game_type]:
            return self.finish_game(game_id)

        game.round_number += 1
        game.current_challenge = self._generate_challenge(game)

        return game

    def finish_game(self, game_id: str) -> Optional[GameState]:
        """Finish game and determine winners"""
        if game_id not in self.active_games:
            return None

        game = self.active_games[game_id]
        game.status = "finished"

        # Rank players by score
        ranked_players = sorted(
            game.players.values(),
            key=lambda p: p.score,
            reverse=True
        )

        # Assign final ranks
        for i, player in enumerate(ranked_players):
            player.final_rank = i + 1

        # Top 2 (or top 3 for larger games) are winners
        num_winners = 2 if len(ranked_players) <= 8 else 3
        game.winners = [p.address for p in ranked_players[:num_winners]]

        # Store in history
        self.game_history.append({
            "game_id": game.game_id,
            "arena_address": game.arena_address,
            "game_type": game.game_type.value,
            "winners": game.winners,
            "player_scores": {p.address: p.score for p in ranked_players},
            "finished_at": datetime.now(timezone.utc).isoformat(),
        })

        return game

    def get_game_state(self, game_id: str) -> Optional[GameState]:
        """Get current game state"""
        return self.active_games.get(game_id)

    def get_leaderboard(self, game_id: str) -> List[Dict]:
        """Get current leaderboard for a game"""
        game = self.active_games.get(game_id)
        if not game:
            return []

        return sorted(
            [
                {"address": p.address, "score": p.score, "eliminated": p.is_eliminated}
                for p in game.players.values()
            ],
            key=lambda x: x["score"],
            reverse=True
        )


# Singleton instance
game_engine = GameEngine()


def get_game_rules_json(game_type: GameType) -> Dict:
    """Get game rules as JSON for frontend"""
    rules = GAME_RULES[game_type]
    return {
        "game_type": rules.game_type.value,
        "name": rules.name,
        "description": rules.description,
        "how_to_play": rules.how_to_play,
        "tips": rules.tips,
        "duration_seconds": rules.duration_seconds,
        "min_players": rules.min_players,
        "max_players": rules.max_players,
    }


def get_all_game_types() -> List[Dict]:
    """Get all available game types"""
    return [get_game_rules_json(gt) for gt in GameType]
