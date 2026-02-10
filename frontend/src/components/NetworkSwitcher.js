import React, { useState, useRef, useEffect } from 'react';
import { useWallet } from '../context/WalletContext';
import { setNetwork, getNetwork } from '../services/api';
import { ChevronDown, Check, Loader2, AlertTriangle } from 'lucide-react';

/**
 * NetworkSwitcher - Dropdown to switch between Monad Testnet and Mainnet.
 *
 * Works in two modes:
 * 1. Connected wallet: switches the wallet chain and syncs the API network.
 * 2. Disconnected: switches only the API browse-network so users can view
 *    arenas on either network before connecting.
 */
const NetworkSwitcher = ({ onNetworkChange }) => {
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
  } = useWallet();

  const [isOpen, setIsOpen] = useState(false);
  const [showMainnetWarning, setShowMainnetWarning] = useState(false);
  const [pendingNetworkId, setPendingNetworkId] = useState(null);
  // For disconnected browsing – track which network the user is viewing
  const [browseNetwork, setBrowseNetwork] = useState(getNetwork());
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

  const networks = [
    {
      id: monadTestnet.id,
      key: 'testnet',
      name: 'Testnet',
      fullName: 'Monad Testnet',
      isActive: isConnected ? isTestnet : browseNetwork === 'testnet',
      color: 'bg-yellow-500',
      dotColor: 'bg-yellow-400',
    },
    {
      id: monadMainnet.id,
      key: 'mainnet',
      name: 'Mainnet',
      fullName: 'Monad Mainnet',
      isActive: isConnected ? isMainnet : browseNetwork === 'mainnet',
      color: 'bg-green-500',
      dotColor: 'bg-green-400',
    },
  ];

  const currentNetwork = networks.find(n => n.isActive) || networks[0];

  const handleNetworkSwitch = async (network) => {
    if (isConnected && network.id === chainId) {
      setIsOpen(false);
      return;
    }
    if (!isConnected && network.key === browseNetwork) {
      setIsOpen(false);
      return;
    }

    // Show mainnet warning when switching TO mainnet
    if (network.key === 'mainnet') {
      setPendingNetworkId(network);
      setShowMainnetWarning(true);
      setIsOpen(false);
      return;
    }

    await performSwitch(network);
  };

  const performSwitch = async (network) => {
    setShowMainnetWarning(false);
    setPendingNetworkId(null);

    if (isConnected) {
      // Switch the wallet chain – this also triggers WalletContext to call setNetwork()
      try {
        await switchNetwork(network.id);
      } catch (error) {
        console.debug('Network switch cancelled or failed:', error?.message || error);
      }
    } else {
      // Disconnected browsing – only update the API network
      setNetwork(network.key);
      setBrowseNetwork(network.key);
    }

    setIsOpen(false);
    // Notify parent so pages can refetch
    if (onNetworkChange) {
      onNetworkChange(network.key);
    }
  };

  const confirmMainnetSwitch = () => {
    if (pendingNetworkId) {
      performSwitch(pendingNetworkId);
    }
  };

  const cancelMainnetSwitch = () => {
    setShowMainnetWarning(false);
    setPendingNetworkId(null);
  };

  return (
    <>
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
          <div className="absolute right-0 mt-2 w-52 bg-white rounded-xl shadow-lg border border-gray-100 py-2 z-50">
            <div className="px-3 py-2 border-b border-gray-100">
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Select Network</p>
            </div>

            {networks.map((network) => (
              <button
                key={network.id}
                onClick={() => handleNetworkSwitch(network)}
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

            {isConnected && !isOnMonad && (
              <div className="px-3 py-2 border-t border-gray-100 mt-1">
                <p className="text-xs text-orange-600">
                  Currently on unsupported network
                </p>
              </div>
            )}

            {!isConnected && (
              <div className="px-3 py-2 border-t border-gray-100 mt-1">
                <p className="text-xs text-gray-400">
                  Browsing mode &mdash; connect wallet to play
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Mainnet Warning Modal */}
      {showMainnetWarning && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full mx-4 p-6 animate-fade-in">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-orange-100 rounded-xl flex items-center justify-center">
                <AlertTriangle className="w-5 h-5 text-orange-500" />
              </div>
              <h3 className="font-heading text-lg font-semibold text-gray-900">Switch to Mainnet?</h3>
            </div>
            <p className="text-gray-600 text-sm mb-2">
              You are about to switch to <span className="font-semibold text-gray-900">Monad Mainnet</span>.
            </p>
            <ul className="text-sm text-gray-500 space-y-1 mb-6 ml-4 list-disc">
              <li>Mainnet uses <span className="font-semibold text-gray-700">real MON tokens</span></li>
              <li>Entry fees and gas costs are paid with real funds</li>
              <li>Transactions are irreversible on mainnet</li>
            </ul>
            <div className="flex gap-3">
              <button
                onClick={cancelMainnetSwitch}
                className="flex-1 px-4 py-2.5 rounded-lg border border-gray-200 text-gray-700 text-sm font-medium hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={confirmMainnetSwitch}
                className="flex-1 px-4 py-2.5 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700 transition-colors"
              >
                Switch to Mainnet
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default NetworkSwitcher;
