import { getAccount, readContract, simulateContract, writeContract, waitForTransactionReceipt } from '@wagmi/core';
import { wagmiConfig } from '../config/wagmi';

const ARENA_ESCROW_READ_ABI = [
  { type: 'function', name: 'entryFee', stateMutability: 'view', inputs: [], outputs: [{ type: 'uint256' }] },
  { type: 'function', name: 'isClosed', stateMutability: 'view', inputs: [], outputs: [{ type: 'bool' }] },
  { type: 'function', name: 'isFinalized', stateMutability: 'view', inputs: [], outputs: [{ type: 'bool' }] },
  { type: 'function', name: 'registrationDeadline', stateMutability: 'view', inputs: [], outputs: [{ type: 'uint64' }] },
  { type: 'function', name: 'getPlayerCount', stateMutability: 'view', inputs: [], outputs: [{ type: 'uint256' }] },
  { type: 'function', name: 'maxPlayers', stateMutability: 'view', inputs: [], outputs: [{ type: 'uint32' }] },
];

const ARENA_ESCROW_JOIN_ABI = [
  { type: 'function', name: 'join', stateMutability: 'payable', inputs: [], outputs: [] },
];

export async function joinArenaOnchain({ arenaAddress }) {
  if (!arenaAddress) throw new Error('Missing arena address');

  // 1. Check if user is actually connected
  const { address, isConnected } = getAccount(wagmiConfig);
  if (!isConnected || !address) throw new Error('Wallet not connected');

  // 2. Fetch Source of Truth from chain
  const entryFee = await readContract(wagmiConfig, {
    address: arenaAddress,
    abi: ARENA_ESCROW_READ_ABI,
    functionName: 'entryFee',
  });

  const [isClosed, isFinalized, deadline, count, maxPlayers] = await Promise.all([
    readContract(wagmiConfig, { address: arenaAddress, abi: ARENA_ESCROW_READ_ABI, functionName: 'isClosed' }),
    readContract(wagmiConfig, { address: arenaAddress, abi: ARENA_ESCROW_READ_ABI, functionName: 'isFinalized' }),
    readContract(wagmiConfig, { address: arenaAddress, abi: ARENA_ESCROW_READ_ABI, functionName: 'registrationDeadline' }),
    readContract(wagmiConfig, { address: arenaAddress, abi: ARENA_ESCROW_READ_ABI, functionName: 'getPlayerCount' }),
    readContract(wagmiConfig, { address: arenaAddress, abi: ARENA_ESCROW_READ_ABI, functionName: 'maxPlayers' }),
  ]);

  // 3. Logic Checks
  if (isClosed) throw new Error('Registration closed');
  if (isFinalized) throw new Error('Already finalized');
  if (BigInt(count) >= BigInt(maxPlayers)) throw new Error('Arena full');
  
  if (Number(deadline) > 0) {
    const now = Math.floor(Date.now() / 1000);
    if (now > Number(deadline)) throw new Error('Deadline passed');
  }

  // 4. Pre-flight simulation
  // This helps avoid wasting gas if the contract would revert anyway
  try {
    await simulateContract(wagmiConfig, {
      address: arenaAddress,
      abi: ARENA_ESCROW_JOIN_ABI,
      functionName: 'join',
      value: entryFee,
      account: address, // Added account for better simulation accuracy
    });
  } catch (error) {
    console.error("Simulation failed before writing:", error); // Fixed missing quotes
    const revertReason = error.shortMessage || error.message || 'Unknown contract error during simulation.';
    throw new Error(`Pre-check failed: ${revertReason}`);
  }

  // 5. Execute Transaction
  const hash = await writeContract(wagmiConfig, {
    address: arenaAddress,
    abi: ARENA_ESCROW_JOIN_ABI,
    functionName: 'join',
    value: entryFee,
  });

  // 6. Wait for block confirmation
  const receipt = await waitForTransactionReceipt(wagmiConfig, { hash });
  if (receipt.status !== 'success') throw new Error('Join transaction failed on-chain');

  return hash;
}