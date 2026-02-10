import React, { useState, useCallback } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useWallet } from '../context/WalletContext';
import { Button } from '../components/ui/button';
import NetworkSwitcher from './NetworkSwitcher';
import { Wallet, Menu, X, AlertTriangle, Loader2 } from 'lucide-react';

const Header = () => {
  const {
    isConnected,
    isConnecting,
    address,
    connect,
    disconnect,
    truncateAddress,
    wrongNetwork,
    isSwitching,
    switchToMonad,
  } = useWallet();
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Global network change counter – bumped so pages can subscribe and refetch
  const [networkChangeKey, setNetworkChangeKey] = useState(0);

  const handleNetworkChange = useCallback(() => {
    setNetworkChangeKey((k) => k + 1);
    // Dispatch a custom event so any page component can listen
    window.dispatchEvent(new CustomEvent('network-changed'));
  }, []);

  const navLinks = [
    { path: '/', label: 'Lobby' },
    { path: '/leaderboard', label: 'Leaderboard' },
    { path: '/agents', label: 'My Agents' },
    // Admin route exists at /admin but hidden from nav - only accessible via direct URL
  ];

  const isActive = (path) => location.pathname === path;

  const handleSwitchNetwork = async () => {
    await switchToMonad();
  };

  return (
    <>
      <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-gray-100" data-testid="header">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <Link to="/" className="flex items-center gap-3" data-testid="logo-link">
              <div className="claw-logo-mark" />
              <span className="claw-logo-text">
                CLAW <span>ARENA</span>
              </span>
            </Link>

            {/* Desktop Navigation */}
            <nav className="hidden md:flex items-center gap-8" data-testid="desktop-nav">
              {navLinks.map((link) => (
                <Link
                  key={link.path}
                  to={link.path}
                  className={`nav-link ${isActive(link.path) ? 'active' : ''}`}
                  data-testid={`nav-${link.label.toLowerCase()}`}
                >
                  {link.label}
                </Link>
              ))}
            </nav>

            {/* Network Switcher & Wallet Button */}
            <div className="flex items-center gap-3">
              {/* Network Switcher - always visible (works in browse mode when disconnected) */}
              {(!isConnected || (isConnected && !wrongNetwork)) && (
                <div className="hidden sm:block">
                  <NetworkSwitcher onNetworkChange={handleNetworkChange} />
                </div>
              )}

              {isConnected ? (
                wrongNetwork ? (
                  // Wrong network - show switch button
                  <Button
                    onClick={handleSwitchNetwork}
                    disabled={isSwitching}
                    className="bg-orange-500 hover:bg-orange-600 text-white"
                    data-testid="switch-network-btn"
                  >
                    {isSwitching ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Switching...
                      </>
                    ) : (
                      <>
                        <AlertTriangle className="w-4 h-4 mr-2" />
                        Switch to Monad
                      </>
                    )}
                  </Button>
                ) : (
                  // Connected to correct network
                  <button
                    onClick={disconnect}
                    className="wallet-btn connected"
                    data-testid="wallet-connected-btn"
                  >
                    <Wallet className="w-4 h-4" />
                    <span className="font-mono text-sm">{truncateAddress(address)}</span>
                  </button>
                )
              ) : (
                <Button
                  onClick={connect}
                  disabled={isConnecting}
                  className="btn-primary"
                  data-testid="connect-wallet-btn"
                >
                  <Wallet className="w-4 h-4 mr-2" />
                  {isConnecting ? 'Connecting...' : 'Connect Wallet'}
                </Button>
              )}

              {/* Mobile menu button */}
              <button
                className="md:hidden p-2"
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                data-testid="mobile-menu-btn"
              >
                {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
              </button>
            </div>
          </div>

          {/* Mobile Navigation */}
          {mobileMenuOpen && (
            <nav className="md:hidden py-4 border-t border-gray-100" data-testid="mobile-nav">
              {/* Network Switcher in mobile menu */}
              <div className="pb-3 mb-3 border-b border-gray-100">
                <NetworkSwitcher onNetworkChange={handleNetworkChange} />
              </div>

              {navLinks.map((link) => (
                <Link
                  key={link.path}
                  to={link.path}
                  className={`block py-2 nav-link ${isActive(link.path) ? 'active' : ''}`}
                  onClick={() => setMobileMenuOpen(false)}
                  data-testid={`mobile-nav-${link.label.toLowerCase()}`}
                >
                  {link.label}
                </Link>
              ))}
            </nav>
          )}
        </div>
      </header>

      {/* Wrong Network Banner */}
      {isConnected && wrongNetwork && (
        <div className="bg-orange-50 border-b border-orange-200 px-4 py-3" data-testid="wrong-network-banner">
          <div className="max-w-7xl mx-auto flex items-center justify-center gap-3">
            <AlertTriangle className="w-5 h-5 text-orange-500" />
            <span className="text-orange-700 text-sm font-medium">
              You're connected to the wrong network. Please switch to Monad to use CLAW ARENA.
            </span>
            <Button
              onClick={handleSwitchNetwork}
              disabled={isSwitching}
              size="sm"
              className="bg-orange-500 hover:bg-orange-600 text-white text-xs px-3 py-1 h-7"
            >
              {isSwitching ? 'Switching...' : 'Switch Network'}
            </Button>
          </div>
        </div>
      )}
    </>
  );
};

export default Header;
