import { getWalletClient, readContract, simulateContract, writeContract, waitForTransactionReceipt } from '@wagmi/core';
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

  const walletClient = await getWalletClient(wagmiConfig);
  if (!walletClient) throw new Error('Wallet not connected');

  // Source of truth: chain
  const entryFee = await readContract(wagmiConfig, {
    address: arenaAddress,
    abi: ARENA_ESCROW_READ_ABI,
    functionName: 'entryFee',
  });

  // Optional: better pre-checks (gives you a human error before tx)
  const [isClosed, isFinalized, deadline, count, maxPlayers] = await Promise.all([
    readContract(wagmiConfig, { address: arenaAddress, abi: ARENA_ESCROW_READ_ABI, functionName: 'isClosed' }),
    readContract(wagmiConfig, { address: arenaAddress, abi: ARENA_ESCROW_READ_ABI, functionName: 'isFinalized' }),
    readContract(wagmiConfig, { address: arenaAddress, abi: ARENA_ESCROW_READ_ABI, functionName: 'registrationDeadline' }),
    readContract(wagmiConfig, { address: arenaAddress, abi: ARENA_ESCROW_READ_ABI, functionName: 'getPlayerCount' }),
    readContract(wagmiConfig, { address: arenaAddress, abi: ARENA_ESCROW_READ_ABI, functionName: 'maxPlayers' }),
  ]);

  if (isClosed) throw new Error('Registration closed');
  if (isFinalized) throw new Error('Already finalized');
  if (Number(count) >= Number(maxPlayers)) throw new Error('Arena full');
  if (Number(deadline) > 0) {
    const now = Math.floor(Date.now() / 1000);
    if (now > Number(deadline)) throw new Error('Deadline passed');
  }

  // Pre-flight simulation (this is where you’ll get the REAL revert reason)
  await simulateContract(wagmiConfig, {
    address: arenaAddress,
    abi: ARENA_ESCROW_JOIN_ABI,
    functionName: 'join',
    value: entryFee,
  });

  const hash = await writeContract(wagmiConfig, {
    address: arenaAddress,
    abi: ARENA_ESCROW_JOIN_ABI,
    functionName: 'join',
    value: entryFee,
  });

  const receipt = await waitForTransactionReceipt(wagmiConfig, { hash });
  if (receipt.status !== 'success') throw new Error('Join transaction failed');

  return hash;
}
