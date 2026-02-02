# CLAW ARENA - User/Operator Guide

## Overview
This document provides guidance for operators and administrators of CLAW ARENA.

## Roles

### Platform Admin
- Deploy and configure smart contracts
- Set operator signer address
- Manage protocol fee treasury
- Create and manage arenas

### Tournament Operator
- Create new arenas
- Monitor registrations
- Close registration when ready
- Request finalize signatures
- Submit finalize transactions

### Player
- Connect wallet
- Join arenas by paying entry fee
- Compete in tournaments
- Receive payouts if winning
- Claim Proof of W NFT

---

## Admin Workflows

### 1. Initial Setup

#### Deploy Contracts
```bash
# Set environment variables
export MONAD_RPC_URL="https://testnet-rpc.monad.xyz"
export DEPLOYER_PRIVATE_KEY="0x..."
export OPERATOR_ADDRESS="0x..." # OpenClaw operator

# Deploy factory
forge script script/Deploy.s.sol --rpc-url $MONAD_RPC_URL --broadcast
```

#### Configure Backend
```env
# backend/.env
MONGO_URL="mongodb://localhost:27017"
DB_NAME="claw_arena"
ADMIN_API_KEY="your-secure-key"
OPERATOR_ADDRESS="0x..."
CHAIN_ID="10143"
```

#### Configure Frontend
```env
# frontend/.env
REACT_APP_BACKEND_URL="https://api.clawarena.xyz"
REACT_APP_CHAIN_ID="10143"
REACT_APP_MONAD_RPC_URL="https://testnet-rpc.monad.xyz"
```

### 2. Create Arena

1. Navigate to Admin Panel (`/admin`)
2. Fill in arena details:
   - Name (e.g., "Weekend Showdown #1")
   - Entry Fee (in MON)
   - Max Players (4, 8, 16, 32)
   - Protocol Fee (1%, 2.5%, 5%)
3. Click "Create Arena"
4. Arena is now open for registration

### 3. Close Registration

When ready to start the tournament:
1. Go to Admin Panel
2. Find arena in "Close Registration" section
3. Click "Close" button
4. Registration is now closed, no more players can join

### 4. Finalize Tournament

After competition completes:

1. Select arena in "Finalize Tournament" section
2. Enter winners and their payout amounts
   - Winners must be from the player list
   - Amounts must not exceed prize pool minus fees
3. Click "Request Finalize Signature"
4. Wait for OpenClaw agent to return signature
5. Click "Finalize & Distribute Prizes"
6. Transaction will be submitted from your wallet
7. Winners receive payouts automatically

---

## Player Workflows

### 1. Join Tournament

1. Connect wallet (MetaMask or compatible)
2. Browse open tournaments on Lobby page
3. Click "Join Arena" on desired tournament
4. Confirm transaction to pay entry fee
5. Wait for transaction confirmation
6. You're now registered!

### 2. Compete

- Tournament brackets run off-chain
- Follow announcements for match schedules
- Results are recorded by tournament admin

### 3. Receive Payout

After tournament finalizes:
- Payouts are automatically sent to winner addresses
- Check your wallet for incoming MON
- View payout in arena results page
- Claim Proof of W NFT (if winner)

---

## Troubleshooting

### Issue: Transaction Failing

**Possible Causes**:
- Insufficient MON balance
- Wrong network (ensure Monad Testnet)
- Arena is full or closed

**Solutions**:
1. Check wallet balance
2. Verify network in wallet
3. Refresh arena page

### Issue: Finalize Signature Not Received

**Possible Causes**:
- OpenClaw Gateway unavailable
- Invalid winner addresses
- Payout amounts exceed escrow

**Solutions**:
1. Verify all winners are valid players
2. Check payout sum <= prize pool - fees
3. Contact support if persists

### Issue: Arena Not Showing

**Possible Causes**:
- Indexer delay
- Backend service down

**Solutions**:
1. Wait 30 seconds and refresh
2. Check backend health endpoint
3. Contact support

---

## Security Best Practices

### For Admins
- Use hardware wallet for admin operations
- Keep ADMIN_API_KEY secure
- Review winner/payout data before finalizing
- Monitor for suspicious activity

### For Players
- Verify arena contract address
- Only join through official frontend
- Keep wallet secure
- Don't share private keys

---

## Support

- Discord: [CLAW ARENA Discord]
- Twitter: @ClawArena
- Email: support@clawarena.xyz

---

## FAQ

**Q: How are brackets determined?**
A: Brackets can be randomized or seeded by the tournament operator.

**Q: What happens if finalize fails?**
A: Funds remain in escrow. Admin can retry with corrected data.

**Q: Can I withdraw after joining?**
A: No, entry fees are locked once joined.

**Q: How is the operator key secured?**
A: The operator private key is managed by OpenClaw runtime and never exposed.
