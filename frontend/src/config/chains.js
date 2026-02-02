import { defineChain } from 'viem';

/**
 * Monad Testnet chain configuration
 * Chain ID: 10143
 * RPC: https://testnet-rpc.monad.xyz
 */
export const monadTestnet = defineChain({
  id: 10143,
  name: 'Monad Testnet',
  nativeCurrency: {
    decimals: 18,
    name: 'MON',
    symbol: 'MON',
  },
  rpcUrls: {
    default: {
      http: ['https://testnet-rpc.monad.xyz'],
    },
  },
  blockExplorers: {
    default: {
      name: 'Monad Explorer',
      url: 'https://testnet.monadexplorer.com',
    },
  },
  testnet: true,
});

/**
 * Monad Mainnet chain configuration
 * Chain ID: 143
 * RPC: https://rpc.monad.xyz
 */
export const monadMainnet = defineChain({
  id: 143,
  name: 'Monad',
  nativeCurrency: {
    decimals: 18,
    name: 'MON',
    symbol: 'MON',
  },
  rpcUrls: {
    default: {
      http: ['https://rpc.monad.xyz'],
    },
  },
  blockExplorers: {
    default: {
      name: 'Monadscan',
      url: 'https://monadscan.com',
    },
  },
});

// Default to testnet for development
export const defaultChain = monadTestnet;

// Supported chains
export const supportedChains = [monadTestnet, monadMainnet];
