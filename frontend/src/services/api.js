import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const API = `${BACKEND_URL}/api`;

// Admin API key - in production, this should be handled securely
const ADMIN_API_KEY = 'claw-arena-admin-key';

// Network configuration
const NETWORK_CONFIG = {
  testnet: {
    chainId: 10143,
    name: 'Monad Testnet',
    explorerUrl: 'https://testnet.monadexplorer.com',
  },
  mainnet: {
    chainId: 143,
    name: 'Monad',
    explorerUrl: 'https://monadscan.com',
  },
};

// Current network - can be updated by the app
let currentNetwork = 'testnet';

// Set the current network
export const setNetwork = (network) => {
  if (NETWORK_CONFIG[network]) {
    currentNetwork = network;
  }
};

// Get current network
export const getNetwork = () => currentNetwork;

// Get network config
export const getNetworkConfig = () => NETWORK_CONFIG[currentNetwork];

// Get network from chain ID
export const getNetworkFromChainId = (chainId) => {
  if (chainId === NETWORK_CONFIG.testnet.chainId) return 'testnet';
  if (chainId === NETWORK_CONFIG.mainnet.chainId) return 'mainnet';
  return null;
};

const apiClient = axios.create({
  baseURL: API,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add admin key to requests when needed
const adminClient = axios.create({
  baseURL: API,
  headers: {
    'Content-Type': 'application/json',
    'X-Admin-Key': ADMIN_API_KEY,
  },
});

// Add network param to requests
const withNetwork = (params = {}) => ({
  ...params,
  network: currentNetwork,
});

// Public endpoints
export const getHealth = async () => {
  const response = await apiClient.get('/health');
  return response.data;
};

export const getConfig = async () => {
  const response = await apiClient.get('/config', { params: withNetwork() });
  return response.data;
};

export const getArenas = async () => {
  const response = await apiClient.get('/arenas', { params: withNetwork() });
  return response.data;
};

export const getArena = async (address) => {
  const response = await apiClient.get(`/arenas/${address}`, { params: withNetwork() });
  return response.data;
};

export const getArenaPlayers = async (address) => {
  const response = await apiClient.get(`/arenas/${address}/players`, { params: withNetwork() });
  return response.data;
};

export const getArenaPayouts = async (address) => {
  const response = await apiClient.get(`/arenas/${address}/payouts`, { params: withNetwork() });
  return response.data;
};

export const getLeaderboard = async (limit = 50) => {
  const response = await apiClient.get('/leaderboard', { params: withNetwork({ limit }) });
  return response.data;
};

// Join arena (public but requires tx hash)
export const joinArena = async (arenaAddress, playerAddress, txHash) => {
  const response = await apiClient.post('/arenas/join', {
    arena_address: arenaAddress,
    player_address: playerAddress,
    tx_hash: txHash,
    network: currentNetwork,
  });
  return response.data;
};

// Admin endpoints
export const createArena = async (arenaData) => {
  const response = await adminClient.post('/admin/arena/create', arenaData, {
    params: withNetwork(),
  });
  return response.data;
};

export const closeArena = async (address) => {
  const response = await adminClient.post(`/admin/arena/${address}/close`, null, {
    params: withNetwork(),
  });
  return response.data;
};

export const requestFinalizeSignature = async (arenaAddress, winners, amounts) => {
  const response = await adminClient.post('/admin/arena/request-finalize-signature', {
    arena_address: arenaAddress,
    winners,
    amounts,
    network: currentNetwork,
  });
  return response.data;
};

export const recordFinalize = async (address, txHash, winners, amounts) => {
  const response = await adminClient.post(`/admin/arena/${address}/finalize`, null, {
    params: withNetwork({
      tx_hash: txHash,
      winners: winners.join(','),
      amounts: amounts.join(','),
    }),
  });
  return response.data;
};

// Agent endpoints
export const getAgentStatus = async () => {
  const response = await apiClient.get('/agent/status', { params: withNetwork() });
  return response.data;
};

export const getAgentSchedule = async () => {
  const response = await apiClient.get('/agent/schedule', { params: withNetwork() });
  return response.data;
};

// Helper functions
export const formatMON = (weiString) => {
  if (!weiString) return '0';
  const wei = BigInt(weiString);
  const mon = Number(wei) / 1e18;
  return mon.toLocaleString(undefined, { maximumFractionDigits: 4 });
};

export const parseMON = (monString) => {
  const mon = parseFloat(monString);
  return (BigInt(Math.floor(mon * 1e18))).toString();
};

export const getExplorerUrl = (type, hash) => {
  const config = getNetworkConfig();
  const baseUrl = config.explorerUrl;
  switch (type) {
    case 'tx':
      return `${baseUrl}/tx/${hash}`;
    case 'address':
      return `${baseUrl}/address/${hash}`;
    default:
      return baseUrl;
  }
};

export default apiClient;
