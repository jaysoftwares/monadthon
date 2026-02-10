import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Toaster } from 'sonner';
import { WagmiProvider } from 'wagmi';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createAppKit } from '@reown/appkit/react';
import { wagmiAdapter, projectId, metadata, networks } from './config/wagmi';
import { WalletProvider } from './context/WalletContext';
import ErrorBoundary from './components/ErrorBoundary';
import Header from './components/Header';
import Footer from './components/Footer';
import LobbyPage from './pages/LobbyPage';
import ArenaPage from './pages/ArenaPage';
import LeaderboardPage from './pages/LeaderboardPage';
import AdminPage from './pages/AdminPage';
import AgentsPage from './pages/AgentsPage';
import './App.css';

// Create a React Query client
const queryClient = new QueryClient();

// Initialize Reown AppKit
createAppKit({
  adapters: [wagmiAdapter],
  projectId,
  networks,
  metadata,
  themeMode: 'light',
  themeVariables: {
    '--w3m-color-mix': '#836EF9',
    '--w3m-color-mix-strength': 20,
    '--w3m-accent': '#836EF9',
    '--w3m-border-radius-master': '12px',
  },
  features: {
    analytics: false, // Disable for development
    email: false,
    socials: false,
  },
});

function App() {
  return (
    <ErrorBoundary>
      <WagmiProvider config={wagmiAdapter.wagmiConfig}>
        <QueryClientProvider client={queryClient}>
          <WalletProvider>
            <BrowserRouter>
              <div className="flex flex-col min-h-screen bg-white">
                <Header />
                <main className="flex-1">
                  <Routes>
                    <Route path="/" element={<LobbyPage />} />
                    <Route path="/arena/:address" element={<ArenaPage />} />
                    <Route path="/leaderboard" element={<LeaderboardPage />} />
                    <Route path="/agents" element={<AgentsPage />} />
                    <Route path="/admin" element={<AdminPage />} />
                  </Routes>
                </main>
                <Footer />
              </div>
              <Toaster
                position="bottom-right"
                toastOptions={{
                  style: {
                    background: 'white',
                    border: '1px solid #E5E7EB',
                    borderRadius: '12px',
                  },
                  className: 'font-body',
                }}
              />
            </BrowserRouter>
          </WalletProvider>
        </QueryClientProvider>
      </WagmiProvider>
    </ErrorBoundary>
  );
}

export default App;
