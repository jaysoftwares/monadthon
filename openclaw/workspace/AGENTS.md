# CLAW ARENA - Agent Runbook

## Overview
This document describes the operational procedures for the Claw Arena Host agent. The agent is the **primary creator and director** of tournaments. It autonomously decides when to create tournaments, with what parameters, and manages the full lifecycle. Admin can also create tournaments, but the agent leads.

## Agent Configuration

```yaml
name: claw-arena-host
version: 2.0.0
chain: monad-testnet
chain_id: 10143
operator_role: tournament-director
autonomous: true
creation_interval_minutes: 30
min_active_tournaments: 2
max_active_tournaments: 5
```

## Tournament Lifecycle

### Phase 0: Market Analysis & Tournament Planning (AUTONOMOUS)
**Trigger**: Scheduled interval (every 30 minutes) OR active tournament count drops below minimum

**Agent Actions**:
1. Analyze current conditions:
   - Count active (non-finalized) tournaments
   - Calculate average fill rate across recent tournaments
   - Check time of day and day of week
   - Identify which tiers are most popular
2. Decide tournament parameters:
   - Select tier (MICRO, SMALL, MEDIUM, LARGE, WHALE) based on demand
   - Set entry fee within tier range
   - Choose player count (4, 8, 16, 32)
   - Set protocol fee (2-3% based on tier)
   - Generate tournament name with flair
3. Set countdown timer for next tournament
4. Announce upcoming tournament to frontend

**Decision Logic**:
```
IF active_count < MIN_ACTIVE:
    CREATE immediately (fill the gap)
ELIF peak_hours AND active_count < MAX_ACTIVE - 1:
    CREATE (capitalize on traffic)
ELIF confidence > 70% AND active_count < MAX_ACTIVE:
    CREATE (data says demand is there)
ELSE:
    WAIT until next cycle
```

### Phase 1: Arena Creation (AUTONOMOUS)
**Trigger**: Agent decision from Phase 0

**Agent Actions**:
1. Deploy arena contract via ArenaFactory (or register via API)
2. Store arena metadata (entry fee, max players, deadline)
3. Set tournament end timer (registration deadline)
4. Announce creation with countdown timer visible on frontend
5. Begin monitoring for join events

### Phase 2: Registration Period
**Trigger**: Arena is created and open

**Agent Actions**:
1. Track join events in real-time
2. Maintain player list
3. Monitor for capacity (max_players)
4. Update countdown timer on frontend
5. When arena is full OR deadline reached, proceed to close

### Phase 3: Registration Close
**Trigger**: Arena full OR registration deadline reached OR agent decides

**Agent Actions**:
1. Verify arena has minimum players (at least 2)
2. Close registration on-chain
3. Generate bracket seeding
4. Mark arena as ready for competition
5. Start tournament end countdown timer
6. Announce tournament start

### Phase 4: Competition (Off-chain)
**Trigger**: Tournament begins

**Agent Actions**:
1. Run bracket simulation OR wait for external results
2. Track match outcomes
3. Compute final standings
4. Prepare winner/payout list
5. Display tournament progress with time remaining

### Phase 5: Finalize
**Trigger**: Competition complete

**Agent Actions**:
1. Validate results:
   - Arena is closed (not open)
   - Arena is not already finalized
   - Winners are registered players
   - Payout sum <= escrow - protocol fee
   - Nonce is unused
2. Generate EIP-712 signature:
   ```
   Domain:
     name: "ClawArena"
     version: "1"
     chainId: 10143
     verifyingContract: <arena_address>

   Types:
     Finalize:
       arena: address
       winnersHash: bytes32
       amountsHash: bytes32
       nonce: uint256
   ```
3. Submit finalize transaction
4. Start countdown to NEXT tournament creation

### Phase 6: Post-Tournament
**Trigger**: Finalize tx confirmed

**Agent Actions**:
1. Verify payouts executed correctly
2. Update leaderboard
3. Archive arena as complete
4. Display "Next tournament in X:XX" countdown
5. Plan next tournament based on updated data

## Timer System

### Visible Timers
The agent manages these timers visible on the frontend:

1. **Next Tournament Countdown**: Shows when the agent will create the next tournament
   - Displayed in lobby when no tournaments are open
   - Also shown after a tournament finalizes

2. **Registration Deadline**: Time remaining to join a tournament
   - Displayed on arena cards and arena detail page

3. **Tournament End Timer**: When the current tournament will conclude
   - Displayed during active competition phase

### Timer Logic
```
AFTER tournament finalize:
    next_tournament_at = NOW + random(5, 15) minutes

DURING peak hours:
    next_tournament_at = NOW + random(3, 10) minutes

DURING off-peak:
    next_tournament_at = NOW + random(15, 30) minutes
```

## Error Handling

### Invalid Finalize Request
```
Response:
  success: false
  error: "VALIDATION_FAILED"
  reason: "<specific validation failure>"
  suggestion: "<how to fix>"
```

### Tournament Creation Failure
```
Response:
  success: false
  error: "CREATION_FAILED"
  reason: "<technical error>"
  retry: true
  retry_in_seconds: 60
```

## Monitoring & Alerts

### Health Checks
- RPC connection status
- Database connectivity
- Signing service availability
- Active tournament count

### Alert Conditions
- Active tournaments drops below minimum
- Arena stuck in closed state > 24 hours
- Unusual payout patterns detected
- Multiple failed finalize attempts
- No players joining any tournament for 1 hour

## Escalation Path
1. Automated retry (3 attempts)
2. Create smaller tournament if large ones aren't filling
3. Alert admin via webhook
4. Pause creation for affected tier
5. Request human intervention
