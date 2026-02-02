import { http } from 'wagmi';
import { WagmiAdapter } from '@reown/appkit-adapter-wagmi';
import { monadTestnet, monadMainnet } from './chains';

// Reown Project ID - Get yours at https://cloud.reown.com
// For development, we use a placeholder. In production, use environment variable.
export const projectId = process.env.REACT_APP_REOWN_PROJECT_ID || 'claw-arena-dev';

// Metadata for the dApp
export const metadata = {
  name: 'CLAW ARENA',
  description: 'OpenClaw-powered autonomous tournament host on Monad',
  url: typeof window !== 'undefined' ? window.location.origin : 'https://clawarena.xyz',
  icons: ['/logo192.png'],
};

// Networks to support - prioritize testnet for development
export const networks = [monadTestnet, monadMainnet];

// Create the Wagmi Adapter for Reown AppKit
export const wagmiAdapter = new WagmiAdapter({
  projectId,
  networks,
  transports: {
    [monadTestnet.id]: http('https://testnet-rpc.monad.xyz'),
    [monadMainnet.id]: http('https://rpc.monad.xyz'),
  },
});

// Export the wagmi config
export const wagmiConfig = wagmiAdapter.wagmiConfig;
