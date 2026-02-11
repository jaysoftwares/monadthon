# Game-Start Logic and Timer Implementation

## Overview

This document describes the game-start logic and timer management system for CLAW ARENA. The system handles:

1. **Game Start Countdown** - When an arena becomes full, a 10-second countdown begins before the game starts
2. **Idle Timer** - Empty or 1-player arenas are automatically deleted after 20 seconds of inactivity
3. **Game Execution** - Game engine integration and winner processing
4. **Payout Calculation** - Automatic calculation and distribution of winnings

---

## Backend Implementation

### ArenaTimerManager Class

Located in `backend/server.py`, the `ArenaTimerManager` class manages all timer-related operations.

#### Key Methods

- **`start_game_countdown(arena_address, countdown_seconds=10)`**
  - Initiates a 10-second countdown before game starts
  - Called automatically when arena reaches max players
  - Sets `game_start` timestamp in arena document

- **`start_idle_timer(arena_address, idle_seconds=20)`**
  - Starts a 20-second idle timer for empty/1-player arenas
  - Triggers auto-deletion or auto-start based on player count

- **`cancel_timer(arena_address)`**
  - Cancels any active timer for an arena

- **`process_timers()`**
  - Background async task that runs continuously
  - Checks for expired timers every 1 second
  - Executes appropriate actions when timers expire

#### Timer Types

##### Game Start Countdown
- **Trigger:** When arena reaches max players
- **Duration:** 10 seconds
- **On Expiry:** Game is created and started via GameEngine
- **Frontend Effect:** Shows countdown banner with time remaining

##### Idle Timer
- **Trigger:** When arena has 0 or 1 player for 20 seconds
- **Duration:** 20 seconds
- **On Expiry (0 players):** Arena is deleted
- **On Expiry (1 player):** Arena is deleted and entry fee is refunded
- **On Expiry (2+ players):** Game starts immediately
- **Frontend Effect:** Arena auto-closes if still empty

---

## New API Endpoints

### Game Status Management

#### `GET /api/admin/arena/{address}/check-game-status`
Returns current game status, timer info, and player scores.

**Response:**
```json
{
  "arena_address": "0x...",
  "arena_name": "Arena Name",
  "status": "closed|open",
  "is_finalized": false,
  "player_count": 3,
  "max_players": 8,
  "players": ["0x...", "0x..."],
  "game_status": "waiting|learning|active|finished",
  "game_id": "abc123",
  "timer": {
    "type": "game_start_countdown",
    "countdown_ends_at": "2024-02-11T21:43:15Z",
    "countdown_seconds": 10
  },
  "time_remaining_seconds": 5,
  "game": {
    "id": "abc123",
    "type": "prediction",
    "status": "active",
    "round": 1,
    "leaderboard": [
      { "address": "0x...", "score": 100 }
    ]
  }
}
```

#### `POST /api/admin/arena/{address}/process-winners`
Processes game results and calculates payouts.

**Functionality:**
1. Gets winners from GameEngine
2. Calculates total prize pool (entry_fee × player_count)
3. Deducts protocol fee (e.g., 2.5%)
4. Distributes remaining pool equally among winners
5. Stores winners and payouts in arena

**Response:**
```json
{
  "success": true,
  "arena_address": "0x...",
  "winners": ["0x...", "0x..."],
  "payouts": ["50000000000000000", "50000000000000000"],
  "total_pool": "400000000000000000",
  "protocol_fee": "10000000000000000",
  "payout_per_winner": "50000000000000000"
}
```

#### `POST /api/admin/arena/{address}/check-if-full`
Checks if arena is full and triggers game start countdown.

**Response:**
```json
{
  "success": true,
  "is_full": true,
  "player_count": 8,
  "max_players": 8,
  "countdown_started": true,
  "countdown_seconds": 10
}
```

#### `POST /api/admin/arena/{address}/start-idle-timer`
Manually starts idle timer for empty/1-player arenas.

**Response:**
```json
{
  "success": true,
  "arena_address": "0x...",
  "player_count": 1,
  "idle_seconds": 20
}
```

---

## Frontend Implementation

### Timer Display Components

#### Game Countdown Banner
Displayed when arena is full and countdown is active.

```jsx
{arena?.is_closed && gameCountdown !== null && gameCountdown > 0 && (
  <div className="game-countdown-banner">
    <p>GAME STARTING IN</p>
    <p className="countdown">{gameCountdown}s</p>
  </div>
)}
```

#### "How to Play" Modal
Shown when game starts. Contains rules and tips.

```jsx
{showHowToPlay && gameRules && (
  <Modal>
    <h2>{gameRules.name}</h2>
    <p>{gameRules.description}</p>
    <ol>{gameRules.how_to_play.map(...)}</ol>
    <ul>{gameRules.tips.map(...)}</ul>
  </Modal>
)}
```

#### Active Game Display
Shows current game state, round number, and leaderboard.

```jsx
{arena?.game_status === 'active' && gameState && (
  <div className="game-active">
    <h3>Game in Progress</h3>
    <p>Round {gameState.round_number}</p>
    <Leaderboard data={gameState.leaderboard} />
  </div>
)}
```

### Custom Hook: `useArenaTimer`

Located in `frontend/src/hooks/useArenaTimer.js`, handles countdown logic.

```jsx
const { countdown, timerType } = useArenaTimer(arena);

// timerType can be: 'game_start', 'idle', or null
// countdown is seconds remaining or null
```

### Arena State Polling

The ArenaPage component polls arena status every 2 seconds when:
- Game is active
- Countdown is running
- Arena is closed but game hasn't started

```jsx
useEffect(() => {
  const interval = setInterval(fetchData, 2000);
  return () => clearInterval(interval);
}, [address]);
```

---

## Payout Calculation

### Formula

```
Total Pool = entry_fee × number_of_players
Protocol Fee = (Total Pool × protocol_fee_bps) / 10000
Available for Winners = Total Pool - Protocol Fee
Payout per Winner = Available for Winners ÷ number_of_winners
```

### Example

- Entry fee: 1 MON = 1e18 wei
- Players: 4
- Protocol fee: 2.5% (250 bps)

```
Total Pool = 1e18 × 4 = 4e18 wei
Protocol Fee = (4e18 × 250) / 10000 = 0.1e18 wei
Available = 3.9e18 wei
Per Winner (2 winners) = 1.95e18 wei
```

---

## Game Flow

### Step 1: Arena Registration
1. Arena created with max_players and entry_fee
2. Players join one by one
3. When registration_deadline passes, no more joins allowed

### Step 2: Arena Fills Up
1. Final player joins, bringing count to max_players
2. Arena automatically closes registration (is_closed = true)
3. Game countdown starts (10 seconds)
4. Frontend shows countdown banner
5. Frontend auto-shows "How to Play" modal

### Step 3: Game Starts
1. 10-second countdown expires
2. GameEngine.create_game() called with all players
3. GameEngine.start_game() begins the game
4. game_status changes to 'learning' → 'active'
5. Frontend shows game UI and leaderboard
6. Arena state polling fetches game leaderboard every 2 seconds

### Step 4: Game Completes
1. GameEngine determines winners and final scores
2. game_status changes to 'finished'
3. Frontend shows "Game Complete" message
4. Admin calls /api/admin/arena/{address}/process-winners
5. Winners and payouts calculated and stored

### Step 5: Finalization
1. Admin submits finalize transaction on-chain
2. Smart contract transfers payouts to winners
3. Frontend records finalization with tx hash
4. Arena marked as is_finalized = true

---

## Idle Timer Behavior

### Scenario 1: Empty Arena
- Arena created with no registrations
- After 20 seconds with 0 players → **DELETED**

### Scenario 2: Single Player Arena
- One player joins, but second player doesn't
- After 20 seconds with 1 player → **DELETED + REFUND**
- Entry fee refunded to the single player

### Scenario 3: Arena with 2+ Players
- Arena has 2+ players but still waiting for more
- After 20 seconds → **GAME STARTS IMMEDIATELY**
- No additional waiting, countdown skipped

---

## Error Handling

### Backend
- Timer task catches and logs exceptions
- Expired timers removed even on error
- Failed operations logged for debugging

### Frontend
- API errors caught and displayed as toasts
- Failed timer fetch retried in next polling cycle
- Game state updates gracefully handle missing data

---

## Configuration

### Timer Durations
- Game start countdown: **10 seconds** (configurable)
- Idle timer: **20 seconds** (configurable)
- Timer check interval: **1 second**
- Arena state polling: **2 seconds**

### Protocol Fees
- Default: **2.5%** (250 basis points)
- Configurable per arena in ArenaCreate

---

## Testing

### Manual Testing Steps

1. **Create Arena**
   ```
   POST /api/admin/arena/create
   - entry_fee: "1000000000000000000" (1 MON)
   - max_players: 2
   - game_type: "prediction"
   ```

2. **Join with Players**
   ```
   POST /api/arenas/join (x2)
   - arena_address: "0x..."
   - player_address: "0x..."
   - tx_hash: "0x..."
   ```

3. **Observe Countdown**
   - Open ArenaPage in browser
   - Should see countdown banner
   - Should see "How to Play" modal appear at 0s

4. **Check Game Status**
   ```
   GET /api/admin/arena/{address}/check-game-status
   ```

5. **Process Winners**
   ```
   POST /api/admin/arena/{address}/process-winners
   ```

6. **Verify Results**
   - Check arena.winners and arena.payouts
   - Verify payout amounts match formula

---

## Future Enhancements

1. **Dynamic Countdown Duration**
   - Allow arena creator to set countdown length
   - Range: 5-60 seconds

2. **Bracket Elimination**
   - Support tournament bracket-style games
   - Multiple rounds before finals

3. **Leaderboard Updates**
   - Real-time WebSocket updates for active games
   - Live score streaming

4. **Pause/Resume**
   - Ability to pause countdown if needed
   - Refund mechanism if cancelled

5. **Multiple Timers**
   - Concurrent timers for different arenas
   - Better performance with event-driven architecture

---

## Troubleshooting

### Timer Not Starting
- Check arena.is_closed == true
- Verify player_count >= max_players
- Check server logs for TimerManager errors

### Game Not Starting After Countdown
- Verify GameEngine.create_game() succeeds
- Check arena.game_type is valid
- Ensure all players in arena.players array

### Incorrect Payouts
- Verify entry_fee format (wei string)
- Check protocol_fee_bps value
- Confirm number of winners matches GameEngine results

### Frontend Not Updating
- Clear browser cache
- Check network tab for API 200 responses
- Verify polling interval is set to 2s
- Check browser console for JS errors
