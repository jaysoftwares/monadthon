/**
 * Per-network contract addresses and configuration.
 *
 * Addresses can be set via environment variables or fetched from the backend.
 * The backend /api/config endpoint returns the canonical addresses for each network.
 */
import { monadTestnet, monadMainnet } from './chains';

// Contract addresses per network
// Set via REACT_APP_<NETWORK>_ARENA_FACTORY_ADDRESS env vars or updated at runtime
const contracts = {
  [monadTestnet.id]: {
    chainId: monadTestnet.id,
    network: 'testnet',
    name: 'Monad Testnet',
    arenaFactory: process.env.REACT_APP_TESTNET_ARENA_FACTORY_ADDRESS || '',
    treasury: process.env.REACT_APP_TESTNET_TREASURY_ADDRESS || '',
  },
  [monadMainnet.id]: {
    chainId: monadMainnet.id,
    network: 'mainnet',
    name: 'Monad',
    arenaFactory: process.env.REACT_APP_MAINNET_ARENA_FACTORY_ADDRESS || '',
    treasury: process.env.REACT_APP_MAINNET_TREASURY_ADDRESS || '',
  },
};

/**
 * Get contract config for a specific chain ID.
 * Returns null if the chain is not supported.
 */
export const getContractConfig = (chainId) => {
  return contracts[chainId] || null;
};

/**
 * Update contract addresses at runtime (e.g. after fetching from backend /api/config).
 */
export const updateContractConfig = (chainId, { arenaFactory, treasury }) => {
  if (contracts[chainId]) {
    if (arenaFactory) contracts[chainId].arenaFactory = arenaFactory;
    if (treasury) contracts[chainId].treasury = treasury;
  }
};

/**
 * Check if a network has contracts deployed (factory address is set).
 */
export const isNetworkDeployed = (chainId) => {
  const config = contracts[chainId];
  return config && config.arenaFactory && config.arenaFactory.length === 42;
};

export default contracts;
