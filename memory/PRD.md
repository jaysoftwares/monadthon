# CLAW ARENA - Product Requirements Document

## Original Problem Statement
Build a production-ready, deployable monorepo for a hackathon project called CLAW ARENA - an OpenClaw-powered autonomous tournament host agent on Monad (EVM). Users join wagered tournaments by paying native MON entry fees. The agent runs brackets offchain, and then finalizes results onchain by signing EIP-712 typed data using the OpenClaw runtime's signing tool.

## User Personas
1. **Tournament Players**: Web3 gamers who want to compete in wagered tournaments for MON prizes
2. **Tournament Admins**: Operators who create, manage, and finalize tournaments
3. **Spectators**: Users who view leaderboards and tournament results

## Core Requirements (Static)
- Real onchain escrow and payouts in native MON
- Real wallet join flow
- Real event indexing + leaderboard
- Real OpenClaw Gateway integration via Tools Invoke HTTP API (MOCKED for MVP)
- Real deployment scripts + tests
- Monad purple (#836EF9) + white theme

## What's Been Implemented (2026-02-02)

### Backend (FastAPI)
- [x] GET /api/health - Health check endpoint
- [x] GET /api/arenas - List all arenas
- [x] GET /api/arenas/:address - Get arena by address
- [x] GET /api/arenas/:address/players - Get arena players
- [x] GET /api/arenas/:address/payouts - Get arena payouts
- [x] GET /api/leaderboard - Get leaderboard
- [x] POST /api/arenas/join - Record player joining
- [x] POST /api/admin/arena/create - Create new arena
- [x] POST /api/admin/arena/:address/close - Close registration
- [x] POST /api/admin/arena/request-finalize-signature - Get EIP-712 signature (MOCKED)
- [x] POST /api/admin/arena/:address/finalize - Record finalization

### Frontend (React)
- [x] Lobby page with hero section and arena grid
- [x] Arena detail page with players, stats, join flow
- [x] Leaderboard page with rankings
- [x] Admin panel for create/close/finalize
- [x] CLAW ARENA logo and branding
- [x] Monad purple theme (#836EF9)
- [x] Mock wallet connection
- [x] Navigation between pages

### Smart Contracts (Documentation/Stubs)
- [x] ArenaFactory.sol - Factory contract
- [x] ArenaEscrow.sol - Tournament escrow
- [x] ProofOfW.sol - ERC-1155 winner NFT
- [x] Deploy script for Monad testnet
- [x] Foundry test suite

### OpenClaw Integration
- [x] IDENTITY.md - Agent identity
- [x] SOUL.md - Agent values and ethics
- [x] AGENTS.md - Operational runbook
- [x] TOOLS.md - Tool documentation
- [x] USER.md - Operator guide
- [x] Arena host skill stub

## Prioritized Backlog

### P0 (Critical for Production)
- [ ] Real wagmi/viem wallet integration
- [ ] Deploy smart contracts to Monad testnet
- [ ] Connect frontend to real smart contracts
- [ ] Integrate real OpenClaw Gateway API

### P1 (Important)
- [ ] PostgreSQL migration from MongoDB
- [ ] Event indexer service
- [ ] Real-time WebSocket updates
- [ ] Transaction status tracking

### P2 (Nice to Have)
- [ ] Tournament bracket visualization
- [ ] Player profile pages
- [ ] Tournament history
- [ ] Email notifications

## Next Tasks
1. Deploy ArenaFactory to Monad testnet
2. Configure real wagmi providers
3. Obtain OpenClaw Gateway credentials
4. Connect frontend to deployed contracts
5. Add event indexer for Monad events
