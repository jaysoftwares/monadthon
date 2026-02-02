import React, { useState, useRef, useEffect } from 'react';
import { useWallet } from '../context/WalletContext';
import { ChevronDown, Check, Loader2, Globe } from 'lucide-react';

/**
 * NetworkSwitcher - Dropdown to switch between Monad Testnet and Mainnet
 */
const NetworkSwitcher = () => {
  const {
    isConnected,
    chainId,
    isSwitching,
    isTestnet,
    isMainnet,
    isOnMonad,
    monadTestnet,
    monadMainnet,
    switchNetwork,
    getChainName,
  } = useWallet();

  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Don't show if wallet not connected
  if (!isConnected) {
    return null;
  }

  const networks = [
    {
      id: monadTestnet.id,
      name: 'Testnet',
      fullName: 'Monad Testnet',
      isActive: isTestnet,
      color: 'bg-yellow-500',
    },
    {
      id: monadMainnet.id,
      name: 'Mainnet',
      fullName: 'Monad Mainnet',
      isActive: isMainnet,
      color: 'bg-green-500',
    },
  ];

  const currentNetwork = networks.find(n => n.isActive) || {
    name: 'Unknown',
    fullName: 'Unknown Network',
    color: 'bg-gray-500',
  };

  const handleNetworkSwitch = async (networkId) => {
    if (networkId === chainId) {
      setIsOpen(false);
      return;
    }

    await switchNetwork(networkId);
    setIsOpen(false);
  };

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Current Network Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        disabled={isSwitching}
        className="flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-200 hover:border-gray-300 bg-white hover:bg-gray-50 transition-colors text-sm font-medium"
        data-testid="network-switcher-btn"
      >
        {isSwitching ? (
          <Loader2 className="w-4 h-4 animate-spin text-gray-500" />
        ) : (
          <>
            <span className={`w-2 h-2 rounded-full ${currentNetwork.color}`} />
            <span className="text-gray-700">{currentNetwork.name}</span>
          </>
        )}
        <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-48 bg-white rounded-xl shadow-lg border border-gray-100 py-2 z-50">
          <div className="px-3 py-2 border-b border-gray-100">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Select Network</p>
          </div>

          {networks.map((network) => (
            <button
              key={network.id}
              onClick={() => handleNetworkSwitch(network.id)}
              disabled={isSwitching}
              className={`w-full flex items-center justify-between px-3 py-2.5 hover:bg-gray-50 transition-colors ${
                network.isActive ? 'bg-purple-50' : ''
              }`}
              data-testid={`network-option-${network.id}`}
            >
              <div className="flex items-center gap-2">
                <span className={`w-2.5 h-2.5 rounded-full ${network.color}`} />
                <div className="text-left">
                  <p className={`text-sm font-medium ${network.isActive ? 'text-purple-700' : 'text-gray-700'}`}>
                    {network.fullName}
                  </p>
                  <p className="text-xs text-gray-400">Chain ID: {network.id}</p>
                </div>
              </div>
              {network.isActive && (
                <Check className="w-4 h-4 text-purple-600" />
              )}
            </button>
          ))}

          {!isOnMonad && (
            <div className="px-3 py-2 border-t border-gray-100 mt-1">
              <p className="text-xs text-orange-600">
                Currently on unsupported network
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default NetworkSwitcher;
