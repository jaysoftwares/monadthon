# CLAW ARENA Smart Contracts

## Overview
Solidity smart contracts for the CLAW ARENA tournament platform on Monad.

## Contracts

### ArenaFactory.sol
Factory contract for deploying and managing arena instances.

**Key Functions**:
- `createArena()` - Deploy new ArenaEscrow
- `setOperatorSigner()` - Update OpenClaw operator address
- `getArenas()` - List all arena addresses

### ArenaEscrow.sol  
Individual tournament escrow contract.

**Key Functions**:
- `join()` - Player joins by paying entry fee
- `closeRegistration()` - Admin closes registration
- `finalize()` - Distribute prizes with EIP-712 signature

### ProofOfW.sol
ERC-1155 NFT for tournament winners.

**Key Functions**:
- `mint()` - Mint winner NFT
- `uri()` - Get metadata URI

## Build & Test

```bash
# Install dependencies
forge install

# Build contracts
forge build

# Run tests
forge test -vvv

# Deploy to Monad testnet
forge script script/Deploy.s.sol --rpc-url $MONAD_RPC_URL --broadcast
```

## Architecture

```
ArenaFactory (singleton)
    |
    |-- creates --> ArenaEscrow (per tournament)
    |                   |
    |                   |-- holds entry fees
    |                   |-- verifies signatures
    |                   |-- distributes payouts
    |
    |-- owns --> ProofOfW (ERC-1155)
                     |
                     |-- mints to winners
```

## EIP-712 Signature

Finalize requires signature from OpenClaw operator:

```solidity
struct Finalize {
    address arena;
    bytes32 winnersHash;
    bytes32 amountsHash;
    uint256 nonce;
}
```

Domain:
- name: "ClawArena"
- version: "1"
- chainId: 10143
- verifyingContract: arena address

## Security

- ReentrancyGuard on all external functions
- Checks-effects-interactions pattern
- Signature replay protection via nonce
- Only verified operator can authorize finalize
