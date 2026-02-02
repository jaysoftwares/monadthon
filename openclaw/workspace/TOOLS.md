# CLAW ARENA - Tools Reference

## Overview
Tools available to the Claw Arena Host agent for tournament operations.

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
  "balance": "200000000000000000"
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
  "tool": "arena.sign_finalize_eip712",
  "params": {
    "arena_address": "0x...",
    "winners": ["0x..."],
    "amounts": ["1000000000000000000"],
    "nonce": 1
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
