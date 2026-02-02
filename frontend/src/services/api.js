import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Admin API key - in production, this should be handled securely
const ADMIN_API_KEY = 'claw-arena-admin-key';

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

// Public endpoints
export const getHealth = async () => {
  const response = await apiClient.get('/health');
  return response.data;
};

export const getArenas = async () => {
  const response = await apiClient.get('/arenas');
  return response.data;
};

export const getArena = async (address) => {
  const response = await apiClient.get(`/arenas/${address}`);
  return response.data;
};

export const getArenaPlayers = async (address) => {
  const response = await apiClient.get(`/arenas/${address}/players`);
  return response.data;
};

export const getArenaPayouts = async (address) => {
  const response = await apiClient.get(`/arenas/${address}/payouts`);
  return response.data;
};

export const getLeaderboard = async (limit = 50) => {
  const response = await apiClient.get(`/leaderboard?limit=${limit}`);
  return response.data;
};

// Join arena (public but requires tx hash)
export const joinArena = async (arenaAddress, playerAddress, txHash) => {
  const response = await apiClient.post('/arenas/join', {
    arena_address: arenaAddress,
    player_address: playerAddress,
    tx_hash: txHash,
  });
  return response.data;
};

// Admin endpoints
export const createArena = async (arenaData) => {
  const response = await adminClient.post('/admin/arena/create', arenaData);
  return response.data;
};

export const closeArena = async (address) => {
  const response = await adminClient.post(`/admin/arena/${address}/close`);
  return response.data;
};

export const requestFinalizeSignature = async (arenaAddress, winners, amounts) => {
  const response = await adminClient.post('/admin/arena/request-finalize-signature', {
    arena_address: arenaAddress,
    winners,
    amounts,
  });
  return response.data;
};

export const recordFinalize = async (address, txHash, winners, amounts) => {
  const response = await adminClient.post(`/admin/arena/${address}/finalize`, null, {
    params: {
      tx_hash: txHash,
      winners: winners.join(','),
      amounts: amounts.join(','),
    },
  });
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
  const baseUrl = process.env.REACT_APP_EXPLORER_BASE_URL || 'https://testnet.monadexplorer.com';
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
