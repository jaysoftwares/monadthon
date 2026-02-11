# Deployment & Testing Guide

## Deployment Steps

### 1. **Push to GitHub**
```bash
cd /tmp/monadthon
git config user.email "deploy@monadthon.com"
git config user.name "Monadthon Deployer"
git push origin main
```

### 2. **Update AWS Backend**
```bash
# SSH into AWS instance
ssh -i your-key.pem ubuntu@<aws-instance-ip>

# Navigate to project
cd /path/to/monadthon

# Pull latest code
git pull origin main

# Restart the FastAPI backend
# (method depends on your deployment setup)
# Option A: If using systemd
systemctl restart claw-arena-api

# Option B: If using Docker
docker-compose pull && docker-compose up -d

# Option C: If running directly
# Kill existing process and restart:
pkill -f "python.*server.py"
python3 -m uvicorn backend.server:app --host 0.0.0.0 --port 8000 &
```

### 3. **Verify Deployment**
```bash
# Check health endpoint
curl http://localhost:8000/api/health

# Expected response:
# {"status":"healthy","service":"claw-arena-api","timestamp":"2026-02-11T22:22:00Z",...}
```

## Testing Procedure

### Test Setup (Manual)

#### Option 1: Direct API Testing

**1. Create an Arena**
```bash
curl -X POST http://localhost:8000/api/admin/arena/create \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: your_admin_key" \
  -d '{
    "name": "Test Arena",
    "entry_fee": "1000000000000000",
    "max_players": 2,
    "contract_address": "0x1234567890123456789012345678901234567890",
    "game_type": "prediction"
  }'

# Store the returned address in ARENA_ADDR
```

**2. Join Players**
```bash
# Player 1 joins
curl -X POST http://localhost:8000/api/arenas/join \
  -H "Content-Type: application/json" \
  -d '{
    "arena_address": "'$ARENA_ADDR'",
    "player_address": "0xplayer1address",
    "tx_hash": "0xjoinTxHash1"
  }'

# Player 2 joins (this should trigger countdown)
curl -X POST http://localhost:8000/api/arenas/join \
  -H "Content-Type: application/json" \
  -d '{
    "arena_address": "'$ARENA_ADDR'",
    "player_address": "0xplayer2address",
    "tx_hash": "0xjoinTxHash2"
  }'

# Response should include:
# "arena_full": true
# "countdown_starts": true
# "countdown_seconds": 10
```

**3. Wait for Game to Execute**
```bash
# Poll arena status every second for ~15 seconds
for i in {1..15}; do
  echo "Check $i:"
  curl http://localhost:8000/api/arenas/$ARENA_ADDR | jq '.game_status, .game_id, .winners'
  sleep 1
done

# Expected progression:
# Iteration 1-10: game_status="active", game_id=(non-null), winners=[]
# Iteration 11+: game_status="finished", winners=[player1, player2]
```

**4. Verify Results**
```bash
# Get full arena details
curl http://localhost:8000/api/arenas/$ARENA_ADDR | jq '.'

# Should show:
# {
#   "game_status": "finished",
#   "game_id": "a1b2c3d4...",
#   "winners": ["0xplayer1address", "0xplayer2address"],
#   "payouts": ["500000000000000", "500000000000000"],
#   "game_results": {
#     "winners": [...],
#     "player_scores": {...},
#     "total_pool": "2000000000000000",
#     "protocol_fee": "5000000000000",
#     ...
#   }
# }

# Check leaderboard
curl http://localhost:8000/api/leaderboard | jq '.[] | select(.address=="0xplayer1address")'

# Should show updated stats:
# "total_wins": 1
# "total_payouts": "500000000000000"
# "tournaments_played": 1
# "tournaments_won": 1
```

#### Option 2: Automated Test Script

Create `test_game_execution.sh`:

```bash
#!/bin/bash

API_URL="http://localhost:8000/api"
ADMIN_KEY="your_admin_key"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}=== CLAW ARENA Game Execution Test ===${NC}\n"

# 1. Create Arena
echo -e "${YELLOW}1. Creating arena...${NC}"
ARENA_RESPONSE=$(curl -s -X POST "$API_URL/admin/arena/create" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: $ADMIN_KEY" \
  -d '{
    "name": "Auto Test Arena",
    "entry_fee": "1000000000000000",
    "max_players": 2,
    "contract_address": "0xtest'$(date +%s)$(shuf -i 1000-9999 -n 1)'",
    "game_type": "speed"
  }')

ARENA_ADDR=$(echo $ARENA_RESPONSE | jq -r '.address')
echo -e "${GREEN}✓ Arena created: $ARENA_ADDR${NC}\n"

# 2. Player 1 joins
echo -e "${YELLOW}2. Player 1 joining...${NC}"
curl -s -X POST "$API_URL/arenas/join" \
  -H "Content-Type: application/json" \
  -d "{
    \"arena_address\": \"$ARENA_ADDR\",
    \"player_address\": \"0xplayer1$(shuf -i 1000000-9999999 -n 1)\",
    \"tx_hash\": \"0xtx1\""
" | jq '.success'
echo -e "${GREEN}✓ Player 1 joined${NC}\n"

# 3. Player 2 joins (triggers countdown)
echo -e "${YELLOW}3. Player 2 joining (should trigger countdown)...${NC}"
PLAYER2=$(echo "0xplayer2$(shuf -i 1000000-9999999 -n 1)")
COUNTDOWN=$(curl -s -X POST "$API_URL/arenas/join" \
  -H "Content-Type: application/json" \
  -d "{
    \"arena_address\": \"$ARENA_ADDR\",
    \"player_address\": \"$PLAYER2\",
    \"tx_hash\": \"0xtx2\"
  }" | jq -r '.countdown_starts')

if [ "$COUNTDOWN" = "true" ]; then
  echo -e "${GREEN}✓ Countdown started${NC}\n"
else
  echo -e "${RED}✗ Countdown not triggered!${NC}\n"
  exit 1
fi

# 4. Wait for game to execute
echo -e "${YELLOW}4. Waiting for game execution (15 seconds)...${NC}"
for i in {1..15}; do
  STATUS=$(curl -s "$API_URL/arenas/$ARENA_ADDR" | jq -r '.game_status')
  GAME_ID=$(curl -s "$API_URL/arenas/$ARENA_ADDR" | jq -r '.game_id')
  echo -e "  [$i/15] game_status=$STATUS, game_id=${GAME_ID:0:8}..."
  sleep 1
done
echo ""

# 5. Verify results
echo -e "${YELLOW}5. Verifying game results...${NC}"
FINAL=$(curl -s "$API_URL/arenas/$ARENA_ADDR")

GAME_STATUS=$(echo $FINAL | jq -r '.game_status')
WINNERS_COUNT=$(echo $FINAL | jq '.winners | length')
PAYOUTS=$(echo $FINAL | jq -r '.payouts | join(", ")')

if [ "$GAME_STATUS" = "finished" ] && [ "$WINNERS_COUNT" -gt 0 ]; then
  echo -e "${GREEN}✓ Game completed successfully${NC}"
  echo -e "${GREEN}✓ Winners: $WINNERS_COUNT${NC}"
  echo -e "${GREEN}✓ Payouts: $PAYOUTS${NC}"
  echo -e "\n${GREEN}=== TEST PASSED ===${NC}\n"
else
  echo -e "${RED}✗ Game did not complete properly${NC}"
  echo -e "${RED}✗ Status: $GAME_STATUS, Winners: $WINNERS_COUNT${NC}"
  echo -e "\n${RED}=== TEST FAILED ===${NC}\n"
  exit 1
fi
```

Usage:
```bash
chmod +x test_game_execution.sh
./test_game_execution.sh
```

### Monitoring

**Watch Live Logs:**
```bash
# If using systemd
journalctl -u claw-arena-api -f

# If using Docker
docker-compose logs -f backend

# If running directly with output
# (already visible in terminal)
```

**Key Log Messages to Watch For:**
```
"Started game countdown for arena 0x..."
"Game started for arena 0x..., game_id: a1b2c3d4"
"Starting automatic game play for a1b2c3d4, max rounds: 10"
"Game a1b2c3d4 - Round 1/10"
"Game a1b2c3d4 advanced to round 2"
"Game a1b2c3d4 finished after round 10"
"Processed winners for arena 0x...: [...], payouts: [...]"
```

## Troubleshooting

### Issue: Game never starts
**Check:**
1. Is the timer manager running?
   ```bash
   curl http://localhost:8000/api/health
   ```

2. Are there at least 2 players?
   ```bash
   curl http://localhost:8000/api/arenas/$ARENA_ADDR | jq '.players | length'
   ```

3. Check backend logs for errors
   ```bash
   # Look for "Error triggering game start"
   ```

### Issue: game_id is null
**This shouldn't happen now** - the fix stores game_id before starting execution.
1. Verify arena document has `game_id` field
2. Check MongoDB directly:
   ```bash
   mongo
   > use claw_arena
   > db.arenas.findOne({address: "0x..."})
   ```

### Issue: Winners not determined
**Check:**
1. Is game.status actually "finished"?
2. Check GameState in game_engine:
   ```python
   game = game_engine.active_games[game_id]
   print(game.status, game.winners)
   ```

3. Check for auto-move errors in logs

### Issue: Payouts incorrect
**Verify calculation:**
```python
# If entry_fee = 1000000000000000 (0.001 MON), 2 players:
total_pool = 2000000000000000
protocol_fee_bps = 250  # 2.5%
protocol_fee = 2000000000000000 * 250 / 10000 = 50000000000000
available = 2000000000000000 - 50000000000000 = 1950000000000000
per_winner = 1950000000000000 / 2 = 975000000000000
# Each winner gets 975000000000000 (0.000975 MON)
```

## Rollback

If issues occur:
```bash
git revert fcef966
git push origin main
# Redeploy previous version
```

## Success Criteria

✓ Arena fills without manual intervention
✓ Countdown starts automatically (10 seconds)
✓ After countdown: game_id is populated
✓ Game executes automatically (no manual round advancement needed)
✓ After ~15-20 seconds: game_status = "finished"
✓ Winners are populated from game results
✓ Payouts are calculated and stored
✓ Leaderboard entries updated with wins/earnings
✓ All data persists in MongoDB
