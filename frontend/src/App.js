import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Toaster } from 'sonner';
import { WalletProvider } from './context/WalletContext';
import Header from './components/Header';
import Footer from './components/Footer';
import LobbyPage from './pages/LobbyPage';
import ArenaPage from './pages/ArenaPage';
import LeaderboardPage from './pages/LeaderboardPage';
import AdminPage from './pages/AdminPage';
import './App.css';

function App() {
  return (
    <WalletProvider>
      <BrowserRouter>
        <div className="flex flex-col min-h-screen bg-white">
          <Header />
          <main className="flex-1">
            <Routes>
              <Route path="/" element={<LobbyPage />} />
              <Route path="/arena/:address" element={<ArenaPage />} />
              <Route path="/leaderboard" element={<LeaderboardPage />} />
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
  );
}

export default App;
