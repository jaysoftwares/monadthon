# CLAW ARENA 🏆

> OpenClaw-powered autonomous tournament host on Monad

CLAW ARENA is a wagered tournament platform where users compete for native MON prizes. The system uses an AI agent (powered by OpenClaw) to authorize prize distributions via EIP-712 signatures, ensuring trustless and verifiable payouts without storing private keys on the backend.

![Built on Monad](https://img.shields.io/badge/Built%20on-Monad-836EF9?style=for-the-badge)

## Features

- **Wagered Tournaments**: Join tournaments by paying MON entry fees
- **Trustless Escrow**: Funds held in smart contracts, not custodial wallets  
- **AI-Powered Finalization**: OpenClaw agent signs finalize transactions
- **Proof of W NFT**: ERC-1155 NFT for tournament winners
- **Real-time Leaderboard**: Track top performers across all arenas

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Frontend      │────▶│   Backend API   │────▶│ Agent           │
│   (React)       │     │   (FastAPI)     │     │ Orchestrator    │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Smart         │     │   MongoDB       │     │   OpenClaw      │
│   Contracts     │     │   Database      │     │   Gateway       │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## Quick Start

### Prerequisites
- Node.js >= 20
- Python >= 3.10
- Docker Desktop (optional)
- Foundry (for contracts)

### Installation

```bash
# Install frontend dependencies
cd frontend && yarn install

# Install backend dependencies  
cd backend && pip install -r requirements.txt

# Start development
# Backend runs on :8001, Frontend on :3000
```

### Environment Variables

See `.env.example` for all configuration options.

## Project Structure

```
claw-arena/
├── README.md
├── .env.example
├── contracts/                    # Foundry smart contracts
│   ├── src/
│   │   ├── ArenaFactory.sol
│   │   ├── ArenaEscrow.sol
│   │   └── ProofOfW.sol
│   ├── script/
│   ├── test/
│   └── foundry.toml
├── frontend/                     # React frontend
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   └── services/
│   └── package.json
├── backend/                      # FastAPI backend
│   ├── server.py
│   └── requirements.txt
└── openclaw/
    ├── workspace/
    │   ├── AGENTS.md
    │   ├── SOUL.md
    │   ├── TOOLS.md
    │   ├── IDENTITY.md
    │   └── USER.md
    └── skills/arena-host/
```

## Smart Contracts

### Deploy to Monad Testnet

```bash
# Set environment
export MONAD_RPC_URL="https://testnet-rpc.monad.xyz"
export DEPLOYER_PRIVATE_KEY="0x..."
export OPERATOR_ADDRESS="0x..."
export TREASURY_ADDRESS="0x..."

# Deploy
cd contracts
forge script script/Deploy.s.sol --rpc-url $MONAD_RPC_URL --broadcast
```

### Run Tests

```bash
cd contracts
forge test -vvv
```

## API Endpoints

### Public
- `GET /api/health` - Health check
- `GET /api/arenas` - List all arenas
- `GET /api/arenas/:address` - Get arena details
- `GET /api/leaderboard` - Get leaderboard

### Admin (requires `X-Admin-Key` header)
- `POST /api/admin/arena/create` - Create new arena
- `POST /api/admin/arena/:address/close` - Close registration
- `POST /api/admin/arena/request-finalize-signature` - Get OpenClaw signature
- `POST /api/admin/arena/:address/finalize` - Record finalization

## OpenClaw Integration

The backend includes MOCK MODE for the OpenClaw agent signing flow. In production, configure:

```env
OPENCLAW_GATEWAY_URL=https://gateway.openclaw.xyz
OPENCLAW_BEARER_TOKEN=your-token
OPENCLAW_SESSION_KEY=your-session-key
```

## Frontend Pages

| Route | Description |
|-------|-------------|
| `/` | Lobby - View open and past tournaments |
| `/arena/:address` | Arena details, players, join, results |
| `/leaderboard` | Top winners by earnings |
| `/admin` | Create arenas, close, finalize |

## Finalize Flow

1. Admin clicks "Request Finalize Signature" in admin panel
2. Frontend calls backend → backend generates EIP-712 signature (mock/OpenClaw)
3. Signature returned to frontend
4. Admin submits `finalize(winners, amounts, signature)` transaction
5. Smart contract verifies signature matches operator
6. Payouts distributed to winners
7. Proof of W NFTs minted

## Security

- **No Backend Private Keys**: Signing happens in OpenClaw runtime
- **EIP-712 Signatures**: Typed data prevents signature reuse
- **Nonce Protection**: Each arena finalize requires unique nonce
- **Admin API Key**: Protected endpoints require authentication

---

**Built with 💜 on Monad**
