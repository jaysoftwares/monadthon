import React, { createContext, useContext, useCallback, useEffect, useState } from 'react';
import { useAccount, useConnect, useDisconnect, useSwitchChain, useChainId } from 'wagmi';
import { useAppKit } from '@reown/appkit/react';
import { monadTestnet, monadMainnet } from '../config/chains';

const WalletContext = createContext(null);

// Target chain - default to testnet
const TARGET_CHAIN_ID = parseInt(process.env.REACT_APP_CHAIN_ID || '10143');

/**
 * WalletProvider - Real wallet integration using wagmi and Reown AppKit
 *
 * Features:
 * - Real wallet connection via Reown AppKit (WalletConnect, MetaMask, etc.)
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

  // Check if user is on the correct network
  useEffect(() => {
    if (isConnected && chainId) {
      const isCorrectChain = chainId === monadTestnet.id || chainId === monadMainnet.id;
      setWrongNetwork(!isCorrectChain);
    } else {
      setWrongNetwork(false);
    }
  }, [isConnected, chainId]);

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
      console.error('Failed to disconnect:', error);
    }
  }, [disconnectAsync]);

  // Switch to Monad network
  const switchToMonad = useCallback(async () => {
    if (!switchChainAsync) return false;

    try {
      await switchChainAsync({ chainId: TARGET_CHAIN_ID });
      return true;
    } catch (error) {
      console.error('Failed to switch network:', error);

      // If switch fails, try to add the network first
      if (error.code === 4902 || error.message?.includes('Unrecognized chain')) {
        try {
          const targetChain = TARGET_CHAIN_ID === monadTestnet.id ? monadTestnet : monadMainnet;

          // Request to add the chain
          if (window.ethereum) {
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
          }
        } catch (addError) {
          console.error('Failed to add network:', addError);
        }
      }
      return false;
    }
  }, [switchChainAsync]);

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
      targetChainId: TARGET_CHAIN_ID,

      // Actions
      connect,
      disconnect,
      switchToMonad,

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
 * - wrongNetwork: Whether user is on wrong network
 * - isSwitching: Whether network switch is in progress
 * - connect(): Open wallet connection modal
 * - disconnect(): Disconnect wallet
 * - switchToMonad(): Switch to Monad network
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
