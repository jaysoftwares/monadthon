# CLAW ARENA - Tools Reference

## Overview
Tools available to the Claw Arena Host agent for autonomous tournament creation, management, and finalization.

---

## Tool: `arena.create_tournament`

### Purpose
Create a new tournament with specified parameters. This is the agent's primary tool for autonomous tournament creation.

### Input Schema
```json
{
  "name": "Rising Stars #42",
  "entry_fee_wei": "50000000000000000",
  "max_players": 8,
  "protocol_fee_bps": 250,
  "registration_deadline_minutes": 60,
  "reason": "peak hours, high engagement, 80% confidence"
}
```

### Output Schema
```json
{
  "success": true,
  "arena_address": "0x...",
  "name": "Rising Stars #42",
  "entry_fee_wei": "50000000000000000",
  "max_players": 8,
  "registration_deadline": "2025-01-15T20:00:00Z",
  "tournament_end_estimate": "2025-01-15T22:00:00Z",
  "next_tournament_at": "2025-01-15T22:15:00Z"
}
```

### Behavior
- Deploys contract via ArenaFactory (or registers via backend API)
- Sets registration deadline timer
- Updates frontend countdown timers
- Logs creation reason for transparency

---

## Tool: `arena.analyze_market`

### Purpose
Analyze current market conditions to inform tournament creation decisions.

### Input Schema
```json
{
  "include_historical": true,
  "lookback_hours": 24
}
```

### Output Schema
```json
{
  "hour_of_day": 18,
  "day_of_week": 5,
  "is_peak_hours": true,
  "is_weekend": true,
  "active_tournaments": 3,
  "avg_fill_rate": 0.75,
  "popular_tier": "SMALL",
  "tier_breakdown": {
    "MICRO": {"fill_rate": 0.9, "count": 2},
    "SMALL": {"fill_rate": 0.75, "count": 3},
    "MEDIUM": {"fill_rate": 0.5, "count": 1},
    "LARGE": {"fill_rate": 0.3, "count": 0},
    "WHALE": {"fill_rate": 0.0, "count": 0}
  },
  "recommended_tier": "SMALL",
  "recommended_entry_fee": "50000000000000000",
  "recommended_players": 8,
  "confidence": 0.8,
  "reasoning": "Peak weekend hours with high fill rates in SMALL tier"
}
```

---

## Tool: `arena.get_schedule`

### Purpose
Get the agent's current tournament schedule and countdown timers.

### Input Schema
```json
{}
```

### Output Schema
```json
{
  "next_tournament_at": "2025-01-15T18:30:00Z",
  "next_tournament_countdown_seconds": 847,
  "active_tournaments": [
    {
      "address": "0x...",
      "name": "Rising Stars #42",
      "status": "registration_open",
      "registration_deadline": "2025-01-15T19:00:00Z",
      "registration_countdown_seconds": 2647,
      "players_joined": 5,
      "max_players": 8
    }
  ],
  "recent_completed": [
    {
      "address": "0x...",
      "name": "Micro Mayhem #41",
      "finalized_at": "2025-01-15T17:45:00Z",
      "winners": ["0x..."]
    }
  ],
  "agent_status": "active",
  "last_cycle_at": "2025-01-15T18:00:00Z"
}
```

---

## Tool: `arena.sign_finalize_eip712`

### Purpose
Generate an EIP-712 typed data signature for the finalize transaction.

### Input Schema
```json
{
  "arena_address": "0x...",
  "winners": ["0x...", "0x..."],
  "amounts": ["1000000000000000000", "500000000000000000"],
  "nonce": 1
}
```

### Output Schema
```json
{
  "success": true,
  "signature": "0x...",
  "operator_address": "0x...",
  "domain": {
    "name": "ClawArena",
    "version": "1",
    "chainId": 10143,
    "verifyingContract": "0x..."
  },
  "types": {
    "Finalize": [
      {"name": "arena", "type": "address"},
      {"name": "winnersHash", "type": "bytes32"},
      {"name": "amountsHash", "type": "bytes32"},
      {"name": "nonce", "type": "uint256"}
    ]
  },
  "message": {
    "arena": "0x...",
    "winnersHash": "0x...",
    "amountsHash": "0x...",
    "nonce": 1
  }
}
```

### Constraints
- Arena must have `is_closed = true`
- Arena must have `is_finalized = false`
- All winners must be in arena's player list
- Sum of amounts must be <= escrow balance - protocol fee
- Nonce must be unique per arena

### Error Codes
| Code | Description |
|------|-------------|
| `ARENA_NOT_CLOSED` | Registration still open |
| `ALREADY_FINALIZED` | Arena already finalized |
| `INVALID_WINNER` | Winner not in player list |
| `PAYOUT_EXCEEDS_ESCROW` | Amounts exceed available balance |
| `NONCE_REUSED` | Replay protection triggered |

---

## Tool: `arena.get_players`

### Purpose
Retrieve the current player list for an arena.

### Input
```json
{
  "arena_address": "0x..."
}
```

### Output
```json
{
  "arena_address": "0x...",
  "players": ["0x...", "0x...", "0x..."],
  "count": 3,
  "max_players": 8
}
```

---

## Tool: `arena.get_bracket_results`

### Purpose
Get computed bracket winners (if using automated bracket).

### Input
```json
{
  "arena_address": "0x..."
}
```

### Output
```json
{
  "arena_address": "0x...",
  "bracket_type": "single_elimination",
  "rounds": [
    {
      "round": 1,
      "matches": [
        {"player1": "0x...", "player2": "0x...", "winner": "0x..."}
      ]
    }
  ],
  "final_standings": [
    {"rank": 1, "player": "0x..."},
    {"rank": 2, "player": "0x..."}
  ]
}
```

---

## Tool: `arena.validate_payouts`

### Purpose
Verify payout amounts are valid before signing.

### Input
```json
{
  "arena_address": "0x...",
  "winners": ["0x...", "0x..."],
  "amounts": ["1000000000000000000", "500000000000000000"]
}
```

### Output
```json
{
  "valid": true,
  "escrow_balance": "1600000000000000000",
  "protocol_fee": "40000000000000000",
  "available_for_payout": "1560000000000000000",
  "requested_total": "1500000000000000000",
  "remaining": "60000000000000000"
}
```

---

## Tool: `arena.get_state`

### Purpose
Get current arena state from contract.

### Input
```json
{
  "arena_address": "0x..."
}
```

### Output
```json
{
  "address": "0x...",
  "entry_fee": "100000000000000000",
  "max_players": 8,
  "protocol_fee_bps": 250,
  "treasury": "0x...",
  "players": ["0x...", "0x..."],
  "is_closed": false,
  "is_finalized": false,
  "balance": "200000000000000000",
  "registration_deadline": "2025-01-15T20:00:00Z",
  "tournament_end_estimate": "2025-01-15T22:00:00Z"
}
```

---

## Integration Notes

### OpenClaw Gateway API

All tools are invoked via the OpenClaw Gateway Tools Invoke HTTP API:

```http
POST /api/v1/tools/invoke
Authorization: Bearer <OPENCLAW_BEARER_TOKEN>
X-Session-Key: <OPENCLAW_SESSION_KEY>

{
  "tool": "arena.create_tournament",
  "params": {
    "name": "Rising Stars #42",
    "entry_fee_wei": "50000000000000000",
    "max_players": 8,
    "protocol_fee_bps": 250,
    "registration_deadline_minutes": 60,
    "reason": "peak hours, high engagement"
  }
}
```

### Response Format
```json
{
  "success": true,
  "result": { ... },
  "execution_time_ms": 123
}
```

### Rate Limits
- 100 requests per minute per session
- 1000 requests per hour per bearer token

### Security
- All requests must include valid bearer token
- Session key provides additional authentication layer
- Signatures are generated in secure enclave
- Private keys never leave OpenClaw runtime
