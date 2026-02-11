import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getArena, joinArena, formatMON, getExplorerUrl, getGameState, getGameRules } from '../services/api';
import { useWallet } from '../context/WalletContext';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
import CountdownTimer from '../components/CountdownTimer';
import {
  ArrowLeft, Users, Coins, Trophy, Clock, ExternalLink,
  CheckCircle, XCircle, Loader2, Copy, Check, Bot, Timer, Globe, AlertTriangle, Zap
} from 'lucide-react';
import { toast } from 'sonner';

const ArenaPage = () => {
  const { address } = useParams();
  const { isConnected, address: walletAddress, connect } = useWallet();
  const [arena, setArena] = useState(null);
  const [loading, setLoading] = useState(true);
  const [joining, setJoining] = useState(false);
  const [copied, setCopied] = useState(false);
  const [gameState, setGameState] = useState(null);
  const [gameRules, setGameRules] = useState(null);
  const [showHowToPlay, setShowHowToPlay] = useState(false);
  const [gameCountdown, setGameCountdown] = useState(null);
  const [gameStartTime, setGameStartTime] = useState(null);

  // Fetch arena and game state
  useEffect(() => {
    const fetchData = async () => {
      try {
        const data = await getArena(address);
        setArena(data);

        // If game is active, fetch game state and rules
        if (data.game_id && (data.game_status === 'active' || data.game_status === 'learning')) {
          try {
            const gs = await getGameState(address);
            setGameState(gs);

            // Fetch game rules if we don't have them
            if (data.game_type && !gameRules) {
              try {
                const rules = await getGameRules(data.game_type);
                setGameRules(rules);
              } catch (e) {
                console.error('Failed to fetch game rules:', e);
              }
            }
          } catch (e) {
            console.error('Failed to fetch game state:', e);
          }
        }
      } catch (error) {
        console.error('Failed to fetch arena:', error);
        toast.error('Failed to load arena');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    // Refresh more frequently when game is active or countdown is running
    const interval = setInterval(fetchData, 2000); // Refresh every 2s
    return () => clearInterval(interval);
  }, [address, gameRules]);

  // Handle game countdown
  useEffect(() => {
    if (!arena?.is_closed || arena?.game_status !== 'waiting') {
      return;
    }

    // Calculate time until game starts (10 seconds after arena closes)
    const closedTime = new Date(arena.closed_at);
    const gameStartEstimate = new Date(closedTime.getTime() + 10000); // 10 seconds
    
    const updateCountdown = () => {
      const now = new Date();
      const remaining = Math.max(0, Math.floor((gameStartEstimate - now) / 1000));
      setGameCountdown(remaining);

      if (remaining === 0) {
        // Game should be starting
        setShowHowToPlay(true);
      }
    };

    updateCountdown();
    const timer = setInterval(updateCountdown, 100);
    return () => clearInterval(timer);
  }, [arena?.is_closed, arena?.game_status, arena?.closed_at]);

  const handleJoin = async () => {
    if (!isConnected) {
      await connect();
      return;
    }

    setJoining(true);
    try {
      // In production, this would:
      // 1. Call the smart contract join() function with entry fee
      // 2. Wait for transaction confirmation
      // 3. Then call the API to record the join
      
      // Mock transaction hash for demo
      const mockTxHash = '0x' + Array(64).fill(0).map(() => Math.floor(Math.random() * 16).toString(16)).join('');
      
      await joinArena(address, walletAddress, mockTxHash);
      toast.success('Successfully joined the arena!');
      
      // Refresh arena data
      const data = await getArena(address);
      setArena(data);
    } catch (error) {
      console.error('Failed to join arena:', error);
      toast.error(error.response?.data?.detail || 'Failed to join arena');
    } finally {
      setJoining(false);
    }
  };

  const copyAddress = () => {
    navigator.clipboard.writeText(address);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getStatusBadge = () => {
    if (arena?.is_finalized) {
      return <Badge className="badge-finalized text-base px-4 py-1">Finalized</Badge>;
    }
    if (arena?.is_closed) {
      return <Badge className="badge-closed text-base px-4 py-1">Registration Closed</Badge>;
    }
    if (arena?.players?.length >= arena?.max_players) {
      return <Badge className="badge-live text-base px-4 py-1">Full</Badge>;
    }
    return <Badge className="badge-open text-base px-4 py-1">Open for Registration</Badge>;
  };

  const canJoin = arena && 
    !arena.is_closed && 
    !arena.is_finalized && 
    arena.players?.length < arena.max_players &&
    !arena.players?.includes(walletAddress);

  const hasJoined = arena?.players?.includes(walletAddress);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 py-8">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <Skeleton className="h-8 w-32 mb-8" />
          <div className="bg-white rounded-2xl p-8 border border-gray-100">
            <Skeleton className="h-10 w-3/4 mb-4" />
            <Skeleton className="h-6 w-1/2 mb-8" />
            <div className="grid grid-cols-3 gap-6 mb-8">
              <Skeleton className="h-24" />
              <Skeleton className="h-24" />
              <Skeleton className="h-24" />
            </div>
            <Skeleton className="h-40" />
          </div>
        </div>
      </div>
    );
  }

  if (!arena) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <XCircle className="w-16 h-16 text-red-400 mx-auto mb-4" />
          <h2 className="font-heading text-2xl font-bold text-gray-900 mb-2">Arena Not Found</h2>
          <p className="text-gray-500 mb-6">The arena you're looking for doesn't exist.</p>
          <Link to="/">
            <Button className="btn-primary">Back to Lobby</Button>
          </Link>
        </div>
      </div>
    );
  }

  const playerCount = arena.players?.length || 0;
  const prizePool = BigInt(arena.entry_fee || '0') * BigInt(playerCount);
  const protocolFee = (prizePool * BigInt(arena.protocol_fee_bps || 250)) / BigInt(10000);
  const netPrizePool = prizePool - protocolFee;

  return (
    <div className="min-h-screen bg-gray-50" data-testid="arena-page">
      {/* Header */}
      <div className="bg-white border-b border-gray-100">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <Link to="/" className="inline-flex items-center gap-2 text-gray-500 hover:text-[#836EF9] transition-colors mb-4" data-testid="back-to-lobby">
            <ArrowLeft className="w-4 h-4" />
            Back to Lobby
          </Link>
          
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <div className="flex items-center gap-3">
                <h1 className="font-heading text-3xl font-bold text-gray-900" data-testid="arena-name">{arena.name}</h1>
                <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium ${
                  arena.network === 'mainnet'
                    ? 'bg-green-100 text-green-700'
                    : 'bg-yellow-100 text-yellow-700'
                }`}>
                  <Globe className="w-3 h-3" />
                  {arena.network === 'mainnet' ? 'Mainnet' : 'Testnet'}
                </span>
              </div>
              <div className="flex items-center gap-2 mt-2">
                <span className="font-mono text-sm text-gray-500">{address}</span>
                <button onClick={copyAddress} className="text-gray-400 hover:text-[#836EF9]" data-testid="copy-address-btn">
                  {copied ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
                </button>
                <a 
                  href={getExplorerUrl('address', address)} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-gray-400 hover:text-[#836EF9]"
                  data-testid="explorer-link"
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
              </div>
            </div>
            {getStatusBadge()}
          </div>
        </div>
      </div>

      {/* Mainnet Warning */}
      {arena.network === 'mainnet' && !arena.is_finalized && (
        <div className="bg-green-50 border-b border-green-200 px-4 py-3">
          <div className="max-w-4xl mx-auto flex items-center justify-center gap-2">
            <AlertTriangle className="w-4 h-4 text-green-600" />
            <span className="text-sm font-medium text-green-700">
              This tournament is on <span className="font-semibold">Monad Mainnet</span> &mdash; real MON is required to join
            </span>
          </div>
        </div>
      )}

      {/* How to Play Modal */}
      {showHowToPlay && gameRules && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-xl">
            <div className="sticky top-0 p-6 border-b border-gray-100 bg-gradient-to-r from-purple-50 to-white flex items-center justify-between">
              <h2 className="font-heading text-2xl font-bold text-gray-900">How to Play</h2>
              <button
                onClick={() => setShowHowToPlay(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            </div>
            
            <div className="p-6">
              <div className="mb-6">
                <h3 className="font-heading text-xl font-bold text-gray-900 mb-2">{gameRules.name}</h3>
                <p className="text-gray-600 mb-4">{gameRules.description}</p>
                <Badge className="mb-4">
                  {gameRules.duration_seconds} seconds • {gameRules.min_players}-{gameRules.max_players} players
                </Badge>
              </div>

              <div className="mb-6">
                <h4 className="font-heading text-lg font-semibold text-gray-900 mb-3">How to Play</h4>
                <ol className="list-decimal list-inside space-y-2">
                  {gameRules.how_to_play.map((step, idx) => (
                    <li key={idx} className="text-gray-700">{step}</li>
                  ))}
                </ol>
              </div>

              <div className="mb-6">
                <h4 className="font-heading text-lg font-semibold text-gray-900 mb-3">Tips & Tricks</h4>
                <ul className="list-disc list-inside space-y-2">
                  {gameRules.tips.map((tip, idx) => (
                    <li key={idx} className="text-gray-700">{tip}</li>
                  ))}
                </ul>
              </div>

              <Button
                onClick={() => setShowHowToPlay(false)}
                className="btn-primary w-full"
              >
                Got It! Let's Play
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Content */}
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Game Countdown Banner */}
        {arena?.is_closed && gameCountdown !== null && gameCountdown > 0 && arena?.game_status === 'waiting' && (
          <div className="mb-8 bg-gradient-to-r from-purple-500 to-purple-600 rounded-2xl p-6 text-white shadow-lg">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-purple-100 text-sm font-semibold">GAME STARTING IN</p>
                <p className="font-heading text-4xl font-bold">{gameCountdown}s</p>
              </div>
              <div className="text-right">
                <Zap className="w-12 h-12 inline-block mb-2" />
                <p className="text-purple-100 text-sm">Get ready!</p>
              </div>
            </div>
          </div>
        )}

        {/* Game Active Display */}
        {arena?.game_status === 'active' && gameState && (
          <div className="mb-8 bg-white rounded-2xl border-2 border-green-400 shadow-lg overflow-hidden">
            <div className="p-6 bg-gradient-to-r from-green-50 to-emerald-50 border-b border-green-200">
              <h3 className="font-heading text-2xl font-bold text-gray-900 flex items-center gap-2">
                <Zap className="w-6 h-6 text-green-600" />
                Game in Progress
              </h3>
              <p className="text-gray-600 mt-1">
                Round {gameState.round_number} • {gameState.time_remaining_seconds}s remaining
              </p>
            </div>
            
            {gameState.leaderboard && gameState.leaderboard.length > 0 && (
              <div className="p-6">
                <h4 className="font-heading font-semibold text-gray-900 mb-4">Current Scores</h4>
                <div className="space-y-3">
                  {gameState.leaderboard.slice(0, 5).map((player, idx) => (
                    <div key={player.address} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                      <div className="flex items-center gap-3">
                        <div className="font-heading font-bold text-lg text-gray-600 w-6">{idx + 1}</div>
                        <div>
                          <p className="font-mono text-sm text-gray-900">{player.address}</p>
                          {player.address === walletAddress && (
                            <span className="text-xs text-[#836EF9] font-medium">You</span>
                          )}
                        </div>
                      </div>
                      <span className="font-heading font-bold text-gray-900">{player.score}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Game Finished Display */}
        {arena?.game_status === 'finished' && (
          <div className="mb-8 bg-white rounded-2xl border-2 border-blue-400 shadow-lg overflow-hidden">
            <div className="p-6 bg-gradient-to-r from-blue-50 to-cyan-50 border-b border-blue-200">
              <h3 className="font-heading text-2xl font-bold text-gray-900 flex items-center gap-2">
                <CheckCircle className="w-6 h-6 text-blue-600" />
                Game Complete
              </h3>
              <p className="text-gray-600 mt-1">Waiting for winner processing...</p>
            </div>
          </div>
        )}

        {/* Stats Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-card">
            <div className="flex items-center gap-2 text-gray-500 text-sm mb-2">
              <Coins className="w-4 h-4" />
              Entry Fee
            </div>
            <p className="font-heading text-2xl font-bold text-gray-900">{formatMON(arena.entry_fee)} MON</p>
          </div>
          
          <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-card">
            <div className="flex items-center gap-2 text-gray-500 text-sm mb-2">
              <Users className="w-4 h-4" />
              Players
            </div>
            <p className="font-heading text-2xl font-bold text-gray-900">{playerCount} / {arena.max_players}</p>
          </div>
          
          <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-card">
            <div className="flex items-center gap-2 text-gray-500 text-sm mb-2">
              <Trophy className="w-4 h-4" />
              Prize Pool
            </div>
            <p className="font-heading text-2xl font-bold text-[#836EF9]">{formatMON(prizePool.toString())} MON</p>
          </div>
          
          <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-card">
            <div className="flex items-center gap-2 text-gray-500 text-sm mb-2">
              <Clock className="w-4 h-4" />
              Created
            </div>
            <p className="font-heading text-lg font-bold text-gray-900">{new Date(arena.created_at).toLocaleDateString()}</p>
            {arena.created_by === 'agent' && (
              <div className="flex items-center gap-1 mt-1 text-xs text-[#836EF9]">
                <Bot className="w-3 h-3" />
                <span>By Agent</span>
              </div>
            )}
          </div>
        </div>

        {/* Countdown Timer Banner */}
        {!arena.is_finalized && arena.registration_deadline && !arena.is_closed && (
          <div className="mb-8">
            <CountdownTimer
              targetTime={arena.registration_deadline}
              label="Registration Closes In"
              variant="banner"
            />
          </div>
        )}
        {arena.is_closed && !arena.is_finalized && arena.tournament_end_estimate && (
          <div className="mb-8">
            <CountdownTimer
              targetTime={arena.tournament_end_estimate}
              label="Tournament Ends In"
              variant="banner"
            />
          </div>
        )}

        {/* Join Button */}
        {canJoin && (
          <div className="bg-gradient-to-r from-purple-50 to-white rounded-2xl p-6 border border-purple-100 mb-8">
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
              <div>
                <h3 className="font-heading text-xl font-semibold text-gray-900">Join This Tournament</h3>
                <p className="text-gray-500 mt-1">Pay {formatMON(arena.entry_fee)} MON to enter</p>
              </div>
              <Button 
                onClick={handleJoin} 
                disabled={joining}
                className="btn-primary px-8 py-3 text-lg"
                data-testid="join-arena-btn"
              >
                {joining ? (
                  <>
                    <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                    Joining...
                  </>
                ) : !isConnected ? (
                  'Connect Wallet to Join'
                ) : (
                  `Join for ${formatMON(arena.entry_fee)} MON`
                )}
              </Button>
            </div>
          </div>
        )}

        {hasJoined && !arena.is_finalized && (
          <div className="bg-green-50 border border-green-200 rounded-xl p-4 mb-8 flex items-center gap-3">
            <CheckCircle className="w-5 h-5 text-green-500" />
            <span className="text-green-700 font-medium">You have joined this tournament!</span>
          </div>
        )}

        {/* Players List */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-card overflow-hidden mb-8" data-testid="players-section">
          <div className="p-6 border-b border-gray-100">
            <h3 className="font-heading text-xl font-semibold text-gray-900">Players ({playerCount})</h3>
          </div>
          
          {playerCount > 0 ? (
            <div className="divide-y divide-gray-50">
              {arena.players.map((player, index) => (
                <div key={player} className="px-6 py-4 flex items-center justify-between table-row-hover" data-testid={`player-${index}`}>
                  <div className="flex items-center gap-4">
                    <div className="player-avatar">
                      {player.slice(2, 4).toUpperCase()}
                    </div>
                    <div>
                      <p className="font-mono text-sm text-gray-900">{player}</p>
                      {player === walletAddress && (
                        <span className="text-xs text-[#836EF9] font-medium">You</span>
                      )}
                    </div>
                  </div>
                  <a 
                    href={getExplorerUrl('address', player)} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="text-gray-400 hover:text-[#836EF9]"
                  >
                    <ExternalLink className="w-4 h-4" />
                  </a>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-12 text-center">
              <Users className="w-12 h-12 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500">No players have joined yet. Be the first!</p>
            </div>
          )}
        </div>

        {/* Finalized Results */}
        {arena.is_finalized && arena.winners?.length > 0 && (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-card overflow-hidden" data-testid="results-section">
            <div className="p-6 border-b border-gray-100 bg-gradient-to-r from-purple-50 to-white">
              <h3 className="font-heading text-xl font-semibold text-gray-900 flex items-center gap-2">
                <Trophy className="w-5 h-5 text-[#836EF9]" />
                Tournament Results
              </h3>
            </div>
            
            <div className="divide-y divide-gray-50">
              {arena.winners.map((winner, index) => (
                <div key={winner} className="px-6 py-4 flex items-center justify-between" data-testid={`winner-${index}`}>
                  <div className="flex items-center gap-4">
                    <div className={`leaderboard-rank ${index === 0 ? 'gold' : index === 1 ? 'silver' : index === 2 ? 'bronze' : 'default'}`}>
                      {index + 1}
                    </div>
                    <div>
                      <p className="font-mono text-sm text-gray-900">{winner}</p>
                      {winner === walletAddress && (
                        <span className="text-xs text-[#836EF9] font-medium">You</span>
                      )}
                    </div>
                  </div>
                  <span className="font-heading font-bold text-[#836EF9]">
                    {formatMON(arena.payouts[index])} MON
                  </span>
                </div>
              ))}
            </div>

            {arena.tx_hash && (
              <div className="p-6 border-t border-gray-100 bg-gray-50">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-500">Finalize Transaction</span>
                  <a 
                    href={getExplorerUrl('tx', arena.tx_hash)} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="tx-hash flex items-center gap-1"
                    data-testid="finalize-tx-link"
                  >
                    {arena.tx_hash.slice(0, 10)}...{arena.tx_hash.slice(-8)}
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default ArenaPage;
