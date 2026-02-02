import React, { createContext, useContext, useState, useCallback } from 'react';

const WalletContext = createContext(null);

// Mock wallet provider - in production, use wagmi
export const WalletProvider = ({ children }) => {
  const [address, setAddress] = useState(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const [chainId, setChainId] = useState(parseInt(process.env.REACT_APP_CHAIN_ID || '10143'));

  const connect = useCallback(async () => {
    setIsConnecting(true);
    try {
      // Mock connection - in production, use wagmi's useConnect
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Check if window.ethereum exists
      if (typeof window !== 'undefined' && window.ethereum) {
        try {
          const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
          if (accounts[0]) {
            setAddress(accounts[0]);
            return;
          }
        } catch (e) {
          console.log('MetaMask not available, using mock address');
        }
      }
      
      // Fallback to mock address
      const mockAddress = '0x' + Array(40).fill(0).map(() => Math.floor(Math.random() * 16).toString(16)).join('');
      setAddress(mockAddress);
    } finally {
      setIsConnecting(false);
    }
  }, []);

  const disconnect = useCallback(() => {
    setAddress(null);
  }, []);

  const truncateAddress = useCallback((addr) => {
    if (!addr) return '';
    return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
  }, []);

  return (
    <WalletContext.Provider value={{
      address,
      isConnected: !!address,
      isConnecting,
      chainId,
      connect,
      disconnect,
      truncateAddress,
    }}>
      {children}
    </WalletContext.Provider>
  );
};

export const useWallet = () => {
  const context = useContext(WalletContext);
  if (!context) {
    throw new Error('useWallet must be used within a WalletProvider');
  }
  return context;
};

export default WalletContext;
