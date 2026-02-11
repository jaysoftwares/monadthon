# Arena Host Skill

## Overview
Custom skill for CLAW ARENA tournament management and EIP-712 signing.

## Skill ID
`claw-arena/arena-host`

## Capabilities

### 1. Sign Finalize EIP-712
Generate cryptographic signatures for tournament finalization.

### 2. Bracket Management
Compute and manage tournament brackets.

### 3. Payout Validation
Verify payout amounts and recipient validity.

## Configuration

```yaml
skill_id: claw-arena/arena-host
version: 1.0.0
chain: monad
chain_id: 10143
contract_addresses:
  factory: "0x..."
  proof_of_w: "0x..."
```

## Tools Exposed

| Tool | Description |
|------|-------------|
| `arena.sign_finalize_eip712` | Sign finalize payload |
| `arena.get_players` | Get arena players |
| `arena.get_bracket_results` | Get bracket outcomes |
| `arena.validate_payouts` | Validate payout data |
| `arena.get_state` | Get arena contract state |

## Integration

This skill integrates with OpenClaw Gateway via the Tools Invoke HTTP API.
See `/workspace/TOOLS.md` for detailed API documentation.

## Development

### Local Testing
```bash
# Start mock server
pnpm dev:agent

# Test signing
curl -X POST http://localhost:8002/agent/sign-finalize \
  -H "Content-Type: application/json" \
  -d '{"arena_address": "0x...", "winners": ["0x..."], "amounts": ["1000000000000000000"], "nonce": 1}'
```

### Production
Configure OpenClaw Gateway credentials in environment:
```env
OPENCLAW_GATEWAY_URL=https://gateway.openclaw.xyz
OPENCLAW_BEARER_TOKEN=your_token
OPENCLAW_SESSION_KEY=your_session_key
```

## Changelog

### v1.0.0
- Initial release
- EIP-712 signing support
- Basic bracket management
