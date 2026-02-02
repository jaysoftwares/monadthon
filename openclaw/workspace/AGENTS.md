# CLAW ARENA - Agent Runbook

## Overview
This document describes the operational procedures for the Claw Arena Host agent.

## Agent Configuration

```yaml
name: claw-arena-host
version: 1.0.0
chain: monad-testnet
chain_id: 10143
operator_role: tournament-operator
```

## Operational Phases

### Phase 1: Arena Creation
**Trigger**: Admin creates new arena via factory

**Agent Actions**:
1. Log arena creation event
2. Store arena metadata (entry fee, max players, deadline)
3. Begin monitoring for join events

**No signing required in this phase.**

### Phase 2: Registration Period
**Trigger**: Players join arena

**Agent Actions**:
1. Track join events
2. Maintain player list
3. Monitor for capacity (max_players)
4. Alert admin when arena is full

**No signing required in this phase.**

### Phase 3: Registration Close
**Trigger**: Admin closes registration OR deadline reached

**Agent Actions**:
1. Verify arena has minimum players (if required)
2. Generate bracket seeding (if applicable)
3. Mark arena as ready for competition
4. Announce tournament start

### Phase 4: Competition (Off-chain)
**Trigger**: Tournament begins

**Agent Actions**:
1. Run bracket simulation OR wait for external results
2. Track match outcomes
3. Compute final standings
4. Prepare winner/payout list

### Phase 5: Finalize Request
**Trigger**: Admin requests finalize signature

**Agent Actions**:
1. Validate request:
   - Arena is closed (not open)
   - Arena is not already finalized
   - Winners are registered players
   - Payout sum <= escrow - protocol fee
   - Nonce is unused

2. If valid, generate EIP-712 signature:
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

3. Return signature to caller

### Phase 6: Finalize Execution
**Trigger**: Admin submits finalize tx with signature

**Agent Actions**:
1. Monitor for Finalized event
2. Verify payouts executed correctly
3. Update leaderboard
4. Archive arena as complete

## Error Handling

### Invalid Finalize Request
```
Response:
  success: false
  error: "VALIDATION_FAILED"
  reason: "<specific validation failure>"
  suggestion: "<how to fix>"
```

### Signature Generation Failure
```
Response:
  success: false
  error: "SIGNING_FAILED"
  reason: "<technical error>"
  retry: true
```

## Monitoring & Alerts

### Health Checks
- RPC connection status
- Database connectivity
- Signing service availability

### Alert Conditions
- Arena stuck in closed state > 24 hours
- Unusual payout patterns detected
- Multiple failed finalize attempts

## Maintenance Procedures

### Daily
- Check pending finalizations
- Review error logs
- Verify RPC endpoint health

### Weekly
- Audit completed tournaments
- Update leaderboard aggregations
- Clean up archived data

## Escalation Path
1. Automated retry (3 attempts)
2. Alert admin via webhook
3. Pause signing for affected arena
4. Request human intervention
