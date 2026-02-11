# CLAW ARENA Game Execution Fix

## Problem Summary
Arena was filling, countdown was starting, but games were never actually executing. The flow was:
- ✓ Arena fills
- ✓ Countdown starts (10 seconds)
- ✗ **Game never runs**
- ✗ **game_id remains null in some cases**
- ✗ **Winners/payouts never calculated**

## Root Cause
The `ArenaTimerManager._trigger_game_start()` method was:
1. Creating the game via `game_engine.create_game()`
2. Starting the game via `game_engine.start_game()`
3. Storing the game_id in MongoDB
4. **But stopping there** - never actually playing through the rounds

The game was in "active" status but had no mechanism to auto-execute moves and advance rounds.

## Solution Implemented

### 1. **Auto-Game Execution** (`_play_game_to_completion`)
When the countdown expires and a game is created:
1. Automatically simulate moves for all players through all game rounds
2. Advance rounds until max_rounds is reached
3. Call `game_engine.finish_game()` to complete the game
4. Extract winners from `GameState.winners`

**Key Flow:**
```
Game Created → Start Learning Phase → Active Phase → Loop:
  - Generate auto-moves for each player (based on game type)
  - Submit moves via game_engine.submit_move()
  - Advance round
- Until max_rounds reached
→ Finish Game → Extract Winners → Calculate Payouts
```

### 2. **Smart Auto-Moves** (`_generate_auto_move`)
Different game types get different move generation strategies:

#### **Claw Machine**
- Randomly selects available prizes
- Adds ±5 pixel variance to grab position (realistic attempts)
- Uses `game.current_challenge["prizes"]` for prize data

#### **Prediction Arena**
- Generates random predictions within challenge min/max range
- Respects the challenge constraints

#### **Speed Challenge**
- **Math/Pattern**: 60% success rate with realistic response times (100-5000ms)
- **Reaction**: Quick response times (200-800ms)
- Adds randomness to simulate varied player skill

#### **Blackjack**
- Simple but effective strategy:
  - **Hit** if hand total < 17
  - **Stand** if hand total >= 17
- Uses `game_engine._calculate_blackjack_hand()` for accurate totals

### 3. **Winner Processing** (`_process_game_winners`)
After game completes:

**Extract Winners:**
```python
winners = game.winners  # From GameState after finish_game()
player_scores = {p.address: p.score for p in game.players.values()}
```

**Calculate Payouts:**
```
Total Pool = entry_fee × num_players
Protocol Fee = total_pool × protocol_fee_bps / 10000
Available for Winners = total_pool - protocol_fee
Per Winner = available_for_winners // num_winners
Remainder = available_for_winners % num_winners (goes to first winner)
```

**Store in MongoDB:**
- `arena.winners`: List of winner addresses
- `arena.payouts`: List of payout amounts (strings)
- `arena.game_results`: Complete results object with:
  - Player scores
  - Total pool
  - Protocol fee
  - Per-winner amount
  - Finished timestamp

**Update Leaderboard:**
- Record each individual payout in `payouts` collection
- Update player `leaderboard` entries:
  - `total_payouts` += amount
  - `total_wins` += 1
  - `tournaments_won` += 1

## Code Changes

### File: `/tmp/monadthon/backend/server.py`

#### Added Imports
```python
import random
```

#### Modified `ArenaTimerManager`

1. **`_trigger_game_start()`**
   - Now calls `await self._play_game_to_completion(arena_address, game_id)`
   - Automatically starts the complete game execution pipeline

2. **New Method: `_play_game_to_completion()`**
   - Loops through all game rounds
   - Generates auto-moves for each player per round
   - Advances rounds until completion
   - Calls `_process_game_winners()` when done

3. **New Method: `_generate_auto_move()`**
   - Game-type-specific move generation
   - Handles all 4 game types with appropriate strategies
   - Returns structured move data matching each game's input format

4. **New Method: `_process_game_winners()`**
   - Extracts final winners from game state
   - Calculates payouts with protocol fees
   - Stores everything in MongoDB
   - Updates leaderboard entries

## Test Scenario

**Setup:**
1. Create arena with entry_fee = "1000000000000000" (0.001 MON), max_players = 2
2. Have 2 players join (fills the arena)
3. Observe countdown start (10 seconds)

**Expected Flow:**
1. Countdown expires
2. Game created with game_id (e.g., "a1b2c3d4...")
3. Arena.game_status = "active"
4. Game automatically plays all rounds
5. Winners determined (top scorers based on game rules)
6. Arena.winners = [winner1, winner2, ...]
7. Arena.payouts = [payout1, payout2, ...] (wei strings)
8. Leaderboard updated

**Verification:**
```bash
# Check arena status
curl http://localhost:8000/api/arenas/{address}

# Should show:
# - game_id: non-null
# - game_status: "finished"
# - winners: [...]
# - payouts: [...]
# - game_results: {...}

# Check leaderboard
curl http://localhost:8000/api/leaderboard
# Winners should appear with updated wins/payouts
```

## Integration Points

- **game_engine.py**: Uses existing methods
  - `create_game()`: Creates game state
  - `start_game()`: Transitions to active
  - `submit_move()`: Processes player actions
  - `advance_round()`: Moves to next round
  - `finish_game()`: Completes and ranks players
  - `_calculate_blackjack_hand()`: Card game scoring

- **MongoDB**: Stores results
  - `arenas`: Game metadata and results
  - `payouts`: Individual payout records
  - `leaderboard`: Player statistics

## Future Enhancements

1. **Player-Driven Games**: Modify to handle real player moves (HTTP-based)
   - Generate "pending move" state
   - Wait for player submissions
   - Timeout with auto-move fallback

2. **Weighted Strategies**: More sophisticated auto-play
   - Learning from player history
   - Difficulty-adjusted strategies
   - Risk-aware betting (for prediction)

3. **Tournament Modes**: Support elimination brackets
   - Already implemented in `game_engine.py`
   - Just needs activation in game creation

4. **Replay Simulation**: Debug/audit previous games
   - Store full move history
   - Replay with deterministic seed
