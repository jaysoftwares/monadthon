import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useWallet } from '../context/WalletContext';
import { Button } from '../components/ui/button';
import { Wallet, Menu, X } from 'lucide-react';

const Header = () => {
  const { isConnected, isConnecting, address, connect, disconnect, truncateAddress } = useWallet();
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = React.useState(false);

  const navLinks = [
    { path: '/', label: 'Lobby' },
    { path: '/leaderboard', label: 'Leaderboard' },
    { path: '/admin', label: 'Admin' },
  ];

  const isActive = (path) => location.pathname === path;

  return (
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

          {/* Wallet Button */}
          <div className="flex items-center gap-4">
            {isConnected ? (
              <button
                onClick={disconnect}
                className="wallet-btn connected"
                data-testid="wallet-connected-btn"
              >
                <Wallet className="w-4 h-4" />
                <span className="font-mono text-sm">{truncateAddress(address)}</span>
              </button>
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
  );
};

export default Header;
