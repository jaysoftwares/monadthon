import React from 'react';
import { Link } from 'react-router-dom';
import { ExternalLink } from 'lucide-react';

const Footer = () => {
  return (
    <footer className="footer py-8" data-testid="footer">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2">
            <div className="claw-logo-mark" style={{ width: 28, height: 28 }} />
            <span className="font-heading font-bold text-lg text-gray-900">
              CLAW <span className="text-[#836EF9]">ARENA</span>
            </span>
          </Link>

          {/* Built on Monad Badge */}
          <div className="monad-badge" data-testid="monad-badge">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="12" cy="12" r="10" fill="#836EF9"/>
              <path d="M12 6L8 10L12 14L16 10L12 6Z" fill="white"/>
              <path d="M12 14L8 18H16L12 14Z" fill="white" fillOpacity="0.6"/>
            </svg>
            Built on Monad
          </div>

          {/* Links */}
          <div className="flex items-center gap-6 text-sm text-gray-500">
            <a 
              href="https://docs.monad.xyz" 
              target="_blank" 
              rel="noopener noreferrer"
              className="hover:text-[#836EF9] transition-colors flex items-center gap-1"
              data-testid="docs-link"
            >
              Docs <ExternalLink className="w-3 h-3" />
            </a>
            <a 
              href="https://testnet.monadexplorer.com" 
              target="_blank" 
              rel="noopener noreferrer"
              className="hover:text-[#836EF9] transition-colors flex items-center gap-1"
              data-testid="explorer-link"
            >
              Explorer <ExternalLink className="w-3 h-3" />
            </a>
            <a 
              href="https://github.com" 
              target="_blank" 
              rel="noopener noreferrer"
              className="hover:text-[#836EF9] transition-colors flex items-center gap-1"
              data-testid="github-link"
            >
              GitHub <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>

        <div className="mt-8 pt-6 border-t border-gray-100 text-center text-sm text-gray-400">
          © {new Date().getFullYear()} CLAW ARENA. Powered by OpenClaw on Monad.
        </div>
      </div>
    </footer>
  );
};

export default Footer;
