import { getAccount, readContract, simulateContract, writeContract, waitForTransactionReceipt } from '@wagmi/core';
import { wagmiConfig } from '../config/wagmi';

// ABI for reading the current state of the Arena
const ARENA_ESCROW_READ_ABI = [
  { type: 'function', name: 'entryFee', stateMutability: 'view', inputs: [], outputs: [{ type: 'uint256' }] },
  { type: 'function', name: 'isClosed', stateMutability: 'view', inputs: [], outputs: [{ type: 'bool' }] },
  { type: 'function', name: 'isFinalized', stateMutability: 'view', inputs: [], outputs: [{ type: 'bool' }] },
  { type: 'function', name: 'registrationDeadline', stateMutability: 'view', inputs: [], outputs: [{ type: 'uint64' }] },
  { type: 'function', name: 'getPlayerCount', stateMutability: 'view', inputs: [], outputs: [{ type: 'uint256' }] },
  { type: 'function', name: 'maxPlayers', stateMutability: 'view', inputs: [], outputs: [{ type: 'uint32' }] },
];

// ABI for the join action
const ARENA_ESCROW_JOIN_ABI = [
  { type: 'function', name: 'join', stateMutability: 'payable', inputs: [], outputs: [] },
];

/**
 * Main function to join an arena on-chain
 */
export async function joinArenaOnchain({ arenaAddress }) {
  if (!arenaAddress) throw new Error('Missing arena address');

  // 1. Get current account context
  const { address, isConnected } = getAccount(wagmiConfig);
  if (!isConnected || !address) throw new Error('Wallet not connected');

  console.log("--- DEBUG START: ON-CHAIN JOIN ---");
  console.log("Target Arena:", arenaAddress);
  console.log("Your Wallet:", address);

  // 2. Fetch Source of Truth from the blockchain
  const [entryFee, isClosed, isFinalized, deadline, count, maxPlayers] = await Promise.all([
    readContract(wagmiConfig, { address: arenaAddress, abi: ARENA_ESCROW_READ_ABI, functionName: 'entryFee' }),
    readContract(wagmiConfig, { address: arenaAddress, abi: ARENA_ESCROW_READ_ABI, functionName: 'isClosed' }),
    readContract(wagmiConfig, { address: arenaAddress, abi: ARENA_ESCROW_READ_ABI, functionName: 'isFinalized' }),
    readContract(wagmiConfig, { address: arenaAddress, abi: ARENA_ESCROW_READ_ABI, functionName: 'registrationDeadline' }),
    readContract(wagmiConfig, { address: arenaAddress, abi: ARENA_ESCROW_READ_ABI, functionName: 'getPlayerCount' }),
    readContract(wagmiConfig, { address: arenaAddress, abi: ARENA_ESCROW_READ_ABI, functionName: 'maxPlayers' }),
  ]);

  // Logging values to find why the wallet is reverting
  const now = Math.floor(Date.now() / 1000);
  console.log("CONTRACT STATE:", {
    entryFee: entryFee.toString(),
    isClosed,
    isFinalized,
    deadline: Number(deadline),
    currentTime: now,
    playerCount: count.toString(),
    maxPlayers: maxPlayers.toString()
  });

  // 3. Logic Checks before attempting transaction
  if (isClosed) throw new Error('Registration is officially closed.');
  if (isFinalized) throw new Error('Arena is already finalized.');
  if (BigInt(count) >= BigInt(maxPlayers)) throw new Error('Arena is full.');
  
  if (Number(deadline) > 0 && now > Number(deadline)) {
    throw new Error(`Registration deadline has passed. (Now: ${now}, Deadline: ${deadline})`);
  }

  // 4. Pre-flight simulation
  // Including 'account' ensures the simulation knows WHO is calling (important for "Already Joined" check)
  try {
    console.log("Simulating contract call...");
    await simulateContract(wagmiConfig, {
      address: arenaAddress,
      abi: ARENA_ESCROW_JOIN_ABI,
      functionName: 'join',
      value: entryFee,
      account: address, 
    });
  } catch (error) {
    console.error("Simulation failed before writing:", error); // Fixed syntax error
    const revertReason = error.shortMessage || error.message || 'Contract reverted during simulation.';
    throw new Error(`Revert Reason: ${revertReason}`);
  }

  // 5. Execute Transaction
  try {
    console.log("Sending transaction to wallet...");
    const hash = await writeContract(wagmiConfig, {
      address: arenaAddress,
      abi: ARENA_ESCROW_JOIN_ABI,
      functionName: 'join',
      value: entryFee,
    });

    console.log("Transaction Hash:", hash);

    // 6. Wait for block confirmation
    console.log("Waiting for network confirmation...");
    const receipt = await waitForTransactionReceipt(wagmiConfig, { hash });
    
    if (receipt.status !== 'success') {
      throw new Error('Transaction was included in block but failed execution.');
    }

    console.log("Successfully joined the arena!");
    return hash;
  } catch (err) {
    console.error("Wallet/Write Error:", err);
    throw err;
  }
}