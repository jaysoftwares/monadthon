import { getWalletClient, writeContract, waitForTransactionReceipt } from '@wagmi/core';
import { wagmiConfig } from '../config/wagmi';

// Minimal ABI for ArenaEscrow.join()
const ARENA_ESCROW_ABI = [
  {
    type: 'function',
    name: 'join',
    stateMutability: 'payable',
    inputs: [],
    outputs: [],
  },
];

/**
 * Send the on-chain join() transaction (moves MON from the player's wallet into the arena escrow).
 * Returns the transaction hash once mined.
 */
export async function joinArenaOnchain({ arenaAddress, entryFeeWei }) {
  if (!arenaAddress) throw new Error('Missing arena address');
  if (!entryFeeWei) throw new Error('Missing entry fee');

  // wagmi v2 uses BigInt for value
  let value;
  try {
    value = BigInt(entryFeeWei);
  } catch {
    throw new Error('Invalid entry fee value');
  }

  // Ensure we have a connected wallet client
  const walletClient = await getWalletClient(wagmiConfig);
  if (!walletClient) {
    throw new Error('Wallet not connected');
  }

  const hash = await writeContract(wagmiConfig, {
    address: arenaAddress,
    abi: ARENA_ESCROW_ABI,
    functionName: 'join',
    args: [],
    value,
  });

  const receipt = await waitForTransactionReceipt(wagmiConfig, { hash });
  if (receipt.status !== 'success') {
    throw new Error('Join transaction failed');
  }

  return hash;
}
