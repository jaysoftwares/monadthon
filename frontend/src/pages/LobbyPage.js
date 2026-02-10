import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { getArenas, getLeaderboard, getAgentStatus, getNetwork, formatMON } from '../services/api';
import { useWallet } from '../context/WalletContext';
import ArenaCard from '../components/ArenaCard';
import CountdownTimer from '../components/CountdownTimer';
import { Button } from '../components/ui/button';
import { Skeleton } from '../components/ui/skeleton';
import { Trophy, Users, Coins, Zap, ArrowRight, Bot, Activity, Globe } from 'lucide-react';

const LobbyPage = () => {
  const { chainId, isConnected } = useWallet();
  const [arenas, setArenas] = useState([]);
  const [topPlayers, setTopPlayers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [agentStatus, setAgentStatus] = useState(null);
  const [currentNetworkLabel, setCurrentNetworkLabel] = useState(getNetwork());
  const [stats, setStats] = useState({
    totalArenas: 0,
    totalPlayers: 0,
    totalPrizePool: '0',
  });

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [arenasData, leaderboardData] = await Promise.all([
        getArenas(),
        getLeaderboard(3),
      ]);

      setArenas(arenasData);
      setTopPlayers(leaderboardData);
      setCurrentNetworkLabel(getNetwork());

      // Calculate stats
      const totalPlayers = arenasData.reduce((acc, arena) => acc + (arena.players?.length || 0), 0);
      const totalPrizePool = arenasData.reduce((acc, arena) => {
        const playerCount = arena.players?.length || 0;
        return acc + BigInt(arena.entry_fee || '0') * BigInt(playerCount);
      }, BigInt(0));

      setStats({
        totalArenas: arenasData.length,
        totalPlayers,
        totalPrizePool: totalPrizePool.toString(),
      });
    } catch (error) {
      console.error('Failed to fetch data:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();

    // Fetch agent status
    const fetchAgentStatus = async () => {
      try {
        const status = await getAgentStatus();
        setAgentStatus(status);
      } catch (error) {
        // Agent status is optional - don't fail if unavailable
      }
    };
    fetchAgentStatus();

    // Refresh agent status every 30 seconds
    const agentInterval = setInterval(fetchAgentStatus, 30000);

    // Listen for network changes from NetworkSwitcher
    const handleNetworkChange = () => {
      fetchData();
      fetchAgentStatus();
    };
    window.addEventListener('network-changed', handleNetworkChange);

    return () => {
      clearInterval(agentInterval);
      window.removeEventListener('network-changed', handleNetworkChange);
    };
  }, [fetchData]);

  // Re-fetch when wallet chain changes (connected user switching via wallet)
  useEffect(() => {
    if (isConnected && chainId) {
      fetchData();
    }
  }, [chainId, isConnected, fetchData]);

  const openArenas = arenas.filter(a => !a.is_closed && !a.is_finalized);
  const closedArenas = arenas.filter(a => a.is_closed || a.is_finalized);

  return (
    <div className="min-h-screen" data-testid="lobby-page">
      {/* Hero Section */}
      <section className="hero-section hero-gradient py-16 md:py-24">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            {/* Left Content */}
            <div className="animate-fade-in">
              <div className="inline-flex items-center gap-2 px-4 py-2 bg-white/80 backdrop-blur-sm rounded-full border border-purple-100 mb-6">
                <Zap className="w-4 h-4 text-[#836EF9]" />
                <span className="text-sm font-medium text-gray-700">Powered by OpenClaw</span>
              </div>
              
              <h1 className="font-heading text-4xl sm:text-5xl lg:text-6xl font-bold text-gray-900 mb-6 leading-tight">
                Compete. Win.
                <br />
                <span className="text-[#836EF9]">Earn MON.</span>
              </h1>
              
              <p className="text-lg text-gray-600 mb-8 max-w-lg">
                Join wagered tournaments on Monad. Fair brackets, instant payouts, 
                and Proof of W NFTs for champions. All powered by autonomous AI agents.
              </p>
              
              <div className="flex flex-wrap gap-4">
                {openArenas.length > 0 ? (
                  <Link to={`/arena/${openArenas[0].address}`}>
                    <Button className="btn-primary text-base px-6 py-3" data-testid="hero-join-btn">
                      Join Tournament
                      <ArrowRight className="w-5 h-5 ml-2" />
                    </Button>
                  </Link>
                ) : (
                  <Button className="btn-primary text-base px-6 py-3 opacity-75" disabled data-testid="hero-join-btn">
                    <Bot className="w-5 h-5 mr-2" />
                    Waiting for Next Tournament
                  </Button>
                )}
                <Link to="/leaderboard">
                  <Button variant="outline" className="text-base px-6 py-3 border-gray-200 hover:border-purple-200 hover:bg-purple-50" data-testid="hero-leaderboard-btn">
                    <Trophy className="w-5 h-5 mr-2 text-[#836EF9]" />
                    Leaderboard
                  </Button>
                </Link>
              </div>
            </div>

            {/* Right Stats */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white rounded-2xl p-6 border border-gray-100 shadow-card animate-fade-in" style={{ animationDelay: '0.1s' }}>
                <div className="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center mb-4">
                  <Trophy className="w-6 h-6 text-[#836EF9]" />
                </div>
                <p className="font-heading text-3xl font-bold text-gray-900">{stats.totalArenas}</p>
                <p className="text-sm text-gray-500 mt-1">Total Arenas</p>
              </div>
              
              <div className="bg-white rounded-2xl p-6 border border-gray-100 shadow-card animate-fade-in" style={{ animationDelay: '0.2s' }}>
                <div className="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center mb-4">
                  <Users className="w-6 h-6 text-green-600" />
                </div>
                <p className="font-heading text-3xl font-bold text-gray-900">{stats.totalPlayers}</p>
                <p className="text-sm text-gray-500 mt-1">Total Players</p>
              </div>
              
              <div className="col-span-2 bg-gradient-to-r from-[#836EF9] to-[#6D5ACF] rounded-2xl p-6 text-white animate-fade-in" style={{ animationDelay: '0.3s' }}>
                <div className="flex items-center gap-3 mb-2">
                  <Coins className="w-6 h-6" />
                  <span className="text-white/80">Total Prize Pool</span>
                </div>
                <p className="font-heading text-4xl font-bold">{formatMON(stats.totalPrizePool)} MON</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Agent Status Banner */}
      {agentStatus && agentStatus.agent_status === 'active' && (
        <section className="py-6 bg-gradient-to-r from-purple-50 via-white to-indigo-50 border-b border-purple-100" data-testid="agent-status-section">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-[#836EF9] rounded-xl flex items-center justify-center">
                  <Bot className="w-5 h-5 text-white" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <p className="font-heading font-semibold text-gray-900">Claw Arena Host</p>
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-100 text-green-700 text-xs font-medium">
                      <Activity className="w-3 h-3" />
                      Active
                    </span>
                  </div>
                  <p className="text-sm text-gray-500">
                    Autonomous tournament director
                    {agentStatus.tournaments_created_today > 0 && (
                      <span> &middot; {agentStatus.tournaments_created_today} created today</span>
                    )}
                  </p>
                </div>
              </div>

              {agentStatus.next_tournament_at && (
                <div className="flex items-center gap-3">
                  <span className="text-sm text-gray-500">Next tournament in</span>
                  <CountdownTimer
                    targetTime={agentStatus.next_tournament_at}
                    variant="inline"
                    onComplete={fetchData}
                  />
                </div>
              )}
            </div>
          </div>
        </section>
      )}

      {/* Next Tournament Countdown Banner - shown when no open arenas */}
      {!loading && openArenas.length === 0 && agentStatus?.next_tournament_at && (
        <section className="py-8 bg-white" data-testid="next-tournament-banner">
          <div className="max-w-xl mx-auto px-4">
            <CountdownTimer
              targetTime={agentStatus.next_tournament_at}
              label="Next Tournament Starts In"
              variant="banner"
              onComplete={fetchData}
            />
          </div>
        </section>
      )}

      {/* Mainnet Info Banner */}
      {currentNetworkLabel === 'mainnet' && (
        <section className="py-3 bg-green-50 border-b border-green-200" data-testid="mainnet-banner">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-center gap-2">
            <Globe className="w-4 h-4 text-green-600" />
            <span className="text-sm font-medium text-green-700">
              You are viewing <span className="font-semibold">Monad Mainnet</span> tournaments &mdash; real MON is at stake
            </span>
          </div>
        </section>
      )}

      {/* Open Arenas */}
      <section className="py-16 bg-white" data-testid="open-arenas-section">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h2 className="font-heading text-2xl font-bold text-gray-900">Open Tournaments</h2>
              <p className="text-gray-500 mt-1">
                {currentNetworkLabel === 'mainnet'
                  ? 'Compete for real MON prizes on Mainnet'
                  : 'Join now and compete for prizes'}
              </p>
            </div>
          </div>

          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[1, 2, 3].map((i) => (
                <div key={i} className="arena-card">
                  <Skeleton className="h-6 w-3/4 mb-2" />
                  <Skeleton className="h-4 w-1/2 mb-4" />
                  <div className="grid grid-cols-2 gap-4 mb-6">
                    <Skeleton className="h-20" />
                    <Skeleton className="h-20" />
                  </div>
                  <Skeleton className="h-10 w-full" />
                </div>
              ))}
            </div>
          ) : openArenas.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {openArenas.map((arena) => (
                <ArenaCard key={arena.address} arena={arena} />
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <div className="empty-state-icon">
                <Bot className="w-8 h-8 text-[#836EF9]" />
              </div>
              <h3 className="font-heading text-xl font-semibold text-gray-900 mb-2">No Open Tournaments</h3>
              <p className="text-gray-500 mb-6">
                {agentStatus?.agent_status === 'active'
                  ? 'The Claw Arena Host is preparing the next tournament...'
                  : 'Waiting for the autonomous agent to create tournaments'}
              </p>
              {agentStatus?.next_tournament_at && (
                <div className="flex items-center justify-center gap-2 text-[#836EF9]">
                  <span className="text-sm">Next tournament in</span>
                  <CountdownTimer
                    targetTime={agentStatus.next_tournament_at}
                    variant="inline"
                    onComplete={fetchData}
                  />
                </div>
              )}
            </div>
          )}
        </div>
      </section>

      {/* Past Arenas */}
      {closedArenas.length > 0 && (
        <section className="py-16 bg-gray-50" data-testid="past-arenas-section">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="mb-8">
              <h2 className="font-heading text-2xl font-bold text-gray-900">Past Tournaments</h2>
              <p className="text-gray-500 mt-1">View results and winners</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {closedArenas.slice(0, 6).map((arena) => (
                <ArenaCard key={arena.address} arena={arena} />
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Top Players Preview */}
      {topPlayers.length > 0 && (
        <section className="py-16 bg-white" data-testid="top-players-section">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between mb-8">
              <div>
                <h2 className="font-heading text-2xl font-bold text-gray-900">Top Champions</h2>
                <p className="text-gray-500 mt-1">Highest earning players</p>
              </div>
              <Link to="/leaderboard">
                <Button variant="ghost" className="text-[#836EF9] hover:bg-purple-50" data-testid="view-all-leaderboard-btn">
                  View All
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </Link>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {topPlayers.map((player, index) => (
                <div key={player.address} className="bg-white border border-gray-100 rounded-2xl p-6 shadow-card hover:shadow-card-hover transition-shadow">
                  <div className="flex items-center gap-4">
                    <div className={`leaderboard-rank ${index === 0 ? 'gold' : index === 1 ? 'silver' : 'bronze'}`}>
                      {index + 1}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-mono text-sm text-gray-900 truncate">{player.address}</p>
                      <p className="text-xs text-gray-500">{player.tournaments_won} wins</p>
                    </div>
                    <div className="text-right">
                      <p className="font-heading font-bold text-[#836EF9]">{formatMON(player.total_payouts)}</p>
                      <p className="text-xs text-gray-500">MON</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}
    </div>
  );
};

export default LobbyPage;
