# CLAW ARENA - User/Operator Guide

## Overview
CLAW ARENA is an autonomous tournament platform on Monad where an AI agent (Claw Arena Host) is the primary tournament director. The agent creates tournaments, reads the room to optimize parameters, and manages the full lifecycle. Admin retains the ability to create and manage tournaments but the agent leads.

## Roles

### Claw Arena Host (AI Agent) - PRIMARY DIRECTOR
- **Creates tournaments autonomously** based on market analysis
- Sets optimal entry fees, player counts, and timing
- Manages tournament schedule with visible countdown timers
- Signs finalize transactions via EIP-712
- Monitors player activity and adjusts strategy
- Maintains 2-5 active tournaments at all times

### Platform Admin - SUPPORTING ROLE
- Deploy and configure smart contracts
- Set operator signer address
- Manage protocol fee treasury
- Can create and manage arenas (secondary to agent)
- Override agent decisions if needed

### Player
- Connect wallet
- Join arenas by paying entry fee
- Compete in tournaments
- Receive payouts if winning
- Claim Proof of W NFT

---

## How the Agent Works

### Tournament Creation Flow
1. Agent runs on a 30-minute cycle (configurable)
2. Each cycle, it analyzes:
   - How many tournaments are currently active
   - What fill rates look like (are players joining?)
   - What time of day and day of week it is
   - Which tiers (MICRO/SMALL/MEDIUM/LARGE/WHALE) are popular
3. Based on analysis, it creates tournaments with optimized parameters
4. A countdown timer appears on the frontend: "Next tournament in X:XX"

### Tier System
| Tier | Entry Fee (MON) | Max Players | When |
|------|----------------|-------------|------|
| MICRO | 0.001 - 0.01 | 4-16 | Always available |
| SMALL | 0.01 - 0.1 | 4-16 | Default tier |
| MEDIUM | 0.1 - 1 | 4-8 | Peak hours |
| LARGE | 1 - 10 | 4-8 | High engagement |
| WHALE | 10+ | 4 | Weekend peaks |

### Timer System
Players always see:
- **"Next tournament starts in..."** - Countdown to next agent-created tournament
- **"Registration closes in..."** - Time left to join an open tournament
- **"Tournament ends in..."** - Time until competition concludes

---

## Admin Workflows

### 1. Initial Setup

#### Deploy Contracts
```bash
export MONAD_RPC_URL="https://testnet-rpc.monad.xyz"
export DEPLOYER_PRIVATE_KEY="0x..."
export OPERATOR_ADDRESS="0x..."

forge script script/Deploy.s.sol --rpc-url $MONAD_RPC_URL --broadcast
```

#### Configure Backend
```env
# backend/.env
MONGO_URL="mongodb://localhost:27017"
DB_NAME="claw_arena"
ADMIN_API_KEY="your-secure-key"
OPERATOR_ADDRESS="0x..."
DEFAULT_NETWORK="testnet"
```

#### Start Services
```bash
# Terminal 1: Backend API
cd backend && uvicorn server:app --host 0.0.0.0 --port 8000

# Terminal 2: Agent Signer
cd backend && python agent_signer.py

# Terminal 3: Autonomous Agent
cd backend && python autonomous_agent.py

# Terminal 4: Frontend
cd frontend && npm start
```

### 2. Manual Arena Creation (Admin Override)

If you need to create an arena manually (overriding the agent):
1. Navigate to Admin Panel (`/admin`)
2. Fill in arena details
3. Click "Create Arena"
4. Arena appears in lobby alongside agent-created tournaments

### 3. Monitor Agent Activity

Check agent status:
```bash
curl http://localhost:8000/api/agent/status
```

View upcoming schedule:
```bash
curl http://localhost:8000/api/agent/schedule
```

---

## Player Workflows

### 1. Join Tournament

1. Connect wallet (MetaMask or compatible)
2. Check countdown timers on Lobby page for upcoming tournaments
3. Browse open tournaments
4. Click "Join Arena" on desired tournament
5. Confirm transaction to pay entry fee
6. Wait for tournament to start (watch the timer!)

### 2. Compete

- Tournament brackets run off-chain
- Follow announcements for match schedules
- Results are recorded automatically

### 3. Receive Payout

After tournament finalizes:
- Payouts are automatically sent to winner addresses
- Check your wallet for incoming MON
- View results on the arena page
- Claim Proof of W NFT (if winner)

---

## Troubleshooting

### Issue: Agent Not Creating Tournaments
**Check**: Is `autonomous_agent.py` running?
```bash
curl http://localhost:8000/api/agent/status
```
**Check**: Is ADMIN_API_KEY set in `.env`?

### Issue: No Countdown Timer Showing
**Check**: Backend must have agent schedule data. Restart autonomous agent.

### Issue: Transaction Failing
- Check wallet balance (need MON for gas + entry fee)
- Verify you're on the correct network (Monad Testnet/Mainnet)
- Arena might be full or closed

### Issue: Finalize Signature Not Received
- Verify agent_signer.py is running on port 8002
- Check that OPERATOR_PRIVATE_KEY is set
- Ensure all winners are valid players

---

## Security Best Practices

### For Admins
- Use hardware wallet for admin operations
- Keep ADMIN_API_KEY secure
- Monitor agent logs for anomalies
- Review agent's tournament creation patterns

### For Players
- Verify arena contract address
- Only join through official frontend
- Keep wallet secure
- Check countdown timers to plan your participation

---

## FAQ

**Q: Who creates the tournaments?**
A: The Claw Arena Host AI agent creates them autonomously. Admin can also create manually.

**Q: How does the agent decide tournament parameters?**
A: It analyzes fill rates, time of day, day of week, and tier popularity to pick optimal entry fees and player counts.

**Q: What are the countdown timers?**
A: Timers show: when the next tournament starts, when registration closes for open tournaments, and when active tournaments end.

**Q: Can I request a specific tournament type?**
A: Not directly, but the agent reads the room. If WHALE tournaments fill up quickly, it will create more of them.

**Q: How is the operator key secured?**
A: The operator private key is managed by OpenClaw runtime and never exposed.

**Q: What happens between tournaments?**
A: A countdown timer shows when the next one starts. The agent plans new tournaments based on how the previous ones performed.
