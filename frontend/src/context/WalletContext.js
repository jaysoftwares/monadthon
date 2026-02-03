import React, { createContext, useContext, useCallback, useEffect, useState } from 'react';
import { useAccount, useConnect, useDisconnect, useSwitchChain, useChainId } from 'wagmi';
import { useAppKit } from '@reown/appkit/react';
import { monadTestnet, monadMainnet, supportedChains } from '../config/chains';

const WalletContext = createContext(null);

// Default chain - can be overridden by env var
const DEFAULT_CHAIN_ID = parseInt(process.env.REACT_APP_CHAIN_ID || '10143');

/**
 * WalletProvider - Real wallet integration using wagmi and Reown AppKit
 *
 * Features:
 * - Real wallet connection via Reown AppKit (WalletConnect, MetaMask, etc.)
 * - Switch between Monad Testnet and Mainnet
 * - Automatic chain switching to Monad if user is on wrong network
 * - Maintains same API as mock provider for backward compatibility
 */
export const WalletProvider = ({ children }) => {
  const { open } = useAppKit();
  const { address, isConnected, isConnecting: wagmiConnecting } = useAccount();
  const { connectAsync, connectors } = useConnect();
  const { disconnectAsync } = useDisconnect();
  const { switchChainAsync, isPending: isSwitching } = useSwitchChain();
  const chainId = useChainId();

  const [isConnecting, setIsConnecting] = useState(false);
  const [wrongNetwork, setWrongNetwork] = useState(false);

  // Check if user is on a supported Monad network
  const isOnMonad = chainId === monadTestnet.id || chainId === monadMainnet.id;
  const isTestnet = chainId === monadTestnet.id;
  const isMainnet = chainId === monadMainnet.id;

  // Check if user is on the correct network
  useEffect(() => {
    if (isConnected && chainId) {
      setWrongNetwork(!isOnMonad);
    } else {
      setWrongNetwork(false);
    }
  }, [isConnected, chainId, isOnMonad]);

  // Connect wallet using Reown AppKit modal
  const connect = useCallback(async () => {
    setIsConnecting(true);
    try {
      // Open the Reown AppKit modal for wallet selection
      await open({ view: 'Connect' });
    } catch (error) {
      console.error('Failed to open wallet modal:', error);
    } finally {
      setIsConnecting(false);
    }
  }, [open]);

  // Disconnect wallet
  const disconnect = useCallback(async () => {
    try {
      await disconnectAsync();
    } catch (error) {
      // Silently handle disconnect errors - user may have rejected or wallet disconnected
      if (error?.code !== 4001 && !error?.message?.includes('User rejected')) {
        console.error('Failed to disconnect:', error);
      }
    }
  }, [disconnectAsync]);

  // Helper to check if error is user rejection
  const isUserRejection = (error) => {
    return (
      error?.code === 4001 ||
      error?.message?.includes('User rejected') ||
      error?.message?.includes('user rejected') ||
      error?.message?.includes('User denied') ||
      error?.name === 'UserRejectedRequestError'
    );
  };

  // Helper to add network to wallet
  const addNetworkToWallet = useCallback(async (targetChain) => {
    if (!window.ethereum) return false;

    try {
      await window.ethereum.request({
        method: 'wallet_addEthereumChain',
        params: [{
          chainId: `0x${targetChain.id.toString(16)}`,
          chainName: targetChain.name,
          nativeCurrency: targetChain.nativeCurrency,
          rpcUrls: [targetChain.rpcUrls.default.http[0]],
          blockExplorerUrls: [targetChain.blockExplorers.default.url],
        }],
      });
      return true;
    } catch (addError) {
      // Silently handle user rejection
      if (!isUserRejection(addError)) {
        console.error('Failed to add network:', addError);
      }
      return false;
    }
  }, []);

  // Switch to a specific network by chain ID
  const switchNetwork = useCallback(async (targetChainId) => {
    if (!switchChainAsync) return false;

    const targetChain = supportedChains.find(c => c.id === targetChainId);
    if (!targetChain) {
      console.error('Unsupported chain ID:', targetChainId);
      return false;
    }

    try {
      await switchChainAsync({ chainId: targetChainId });
      return true;
    } catch (error) {
      // Silently handle user rejection - this is expected behavior
      if (isUserRejection(error)) {
        return false;
      }

      console.error('Failed to switch network:', error);

      // If switch fails, try to add the network first
      if (error?.code === 4902 || error?.message?.includes('Unrecognized chain')) {
        const added = await addNetworkToWallet(targetChain);
        if (added) {
          // Try switching again after adding
          try {
            await switchChainAsync({ chainId: targetChainId });
            return true;
          } catch (retryError) {
            if (!isUserRejection(retryError)) {
              console.error('Failed to switch after adding network:', retryError);
            }
          }
        }
      }
      return false;
    }
  }, [switchChainAsync, addNetworkToWallet]);

  // Switch to Monad network (default or first supported)
  const switchToMonad = useCallback(async () => {
    return switchNetwork(DEFAULT_CHAIN_ID);
  }, [switchNetwork]);

  // Switch to testnet
  const switchToTestnet = useCallback(async () => {
    return switchNetwork(monadTestnet.id);
  }, [switchNetwork]);

  // Switch to mainnet
  const switchToMainnet = useCallback(async () => {
    return switchNetwork(monadMainnet.id);
  }, [switchNetwork]);

  // Truncate address for display
  const truncateAddress = useCallback((addr) => {
    if (!addr) return '';
    return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
  }, []);

  // Get current chain name
  const getChainName = useCallback(() => {
    if (chainId === monadTestnet.id) return 'Monad Testnet';
    if (chainId === monadMainnet.id) return 'Monad';
    return 'Unknown Network';
  }, [chainId]);

  return (
    <WalletContext.Provider value={{
      // Core state
      address,
      isConnected,
      isConnecting: isConnecting || wagmiConnecting,
      chainId,

      // Network state
      wrongNetwork,
      isSwitching,
      isOnMonad,
      isTestnet,
      isMainnet,

      // Chain info
      supportedChains,
      monadTestnet,
      monadMainnet,

      // Actions
      connect,
      disconnect,
      switchToMonad,
      switchToTestnet,
      switchToMainnet,
      switchNetwork,

      // Helpers
      truncateAddress,
      getChainName,
    }}>
      {children}
    </WalletContext.Provider>
  );
};

/**
 * useWallet hook - provides wallet state and actions
 *
 * Returns:
 * - address: Connected wallet address
 * - isConnected: Whether wallet is connected
 * - isConnecting: Whether connection is in progress
 * - chainId: Current chain ID
 * - wrongNetwork: Whether user is on unsupported network
 * - isSwitching: Whether network switch is in progress
 * - isOnMonad: Whether user is on any Monad network
 * - isTestnet: Whether user is on Monad Testnet
 * - isMainnet: Whether user is on Monad Mainnet
 * - supportedChains: Array of supported chain configs
 * - monadTestnet: Testnet chain config
 * - monadMainnet: Mainnet chain config
 * - connect(): Open wallet connection modal
 * - disconnect(): Disconnect wallet
 * - switchToMonad(): Switch to default Monad network
 * - switchToTestnet(): Switch to Monad Testnet
 * - switchToMainnet(): Switch to Monad Mainnet
 * - switchNetwork(chainId): Switch to specific chain
 * - truncateAddress(addr): Shorten address for display
 * - getChainName(): Get current chain name
 */
export const useWallet = () => {
  const context = useContext(WalletContext);
  if (!context) {
    throw new Error('useWallet must be used within a WalletProvider');
  }
  return context;
};

export default WalletContext;
