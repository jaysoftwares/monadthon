import React from 'react';
import { Link } from 'react-router-dom';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import CountdownTimer from './CountdownTimer';
import { Users, Coins, ArrowRight, Clock, Bot, Globe, AlertCircle, RefreshCcw } from 'lucide-react';
import { formatMON } from '../services/api';

const ArenaCard = ({ arena }) => {
  const isMainnet = arena.network === 'mainnet';
  const playerCount = arena.players?.length || 0;
  const spotsLeft = arena.max_players - playerCount;

  // 1. Logic for showing the 1-minute refund timer
  const isWaitingForPlayers = playerCount === 1 && !arena.is_closed && !arena.is_finalized;
  const hasIdleTimeout = !!arena.idle_ends_at;

  const getStatusBadge = () => {
    if (arena.is_finalized) {
      return <Badge className="bg-gray-100 text-gray-600" data-testid={`arena-status-${arena.address}`}>Finalized</Badge>;
    }
    if (arena.is_closed) {
      return <Badge className="bg-red-100 text-red-600" data-testid={`arena-status-${arena.address}`}>Closed</Badge>;
    }
    if (playerCount >= arena.max_players) {
      return <Badge className="bg-orange-100 text-orange-600" data-testid={`arena-status-${arena.address}`}>Full</Badge>;
    }
    // New status for when a lobby has just been reset
    if (playerCount === 0 && arena.last_refund_tx) {
        return <Badge className="bg-blue-100 text-blue-600 animate-pulse"><RefreshCcw className="w-3 h-3 mr-1" /> Reset & Refunded</Badge>;
    }
    return <Badge className="bg-green-100 text-green-600" data-testid={`arena-status-${arena.address}`}>Open</Badge>;
  };

  return (
    <div className="arena-card group border border-gray-100 hover:border-[#836EF9]/30 transition-all bg-white rounded-xl p-5 shadow-sm hover:shadow-md" data-testid={`arena-card-${arena.address}`}>
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="font-heading font-semibold text-lg text-gray-900 group-hover:text-[#836EF9] transition-colors">
            {arena.name}
          </h3>
          <div className="flex items-center gap-2 mt-1">
            <p className="font-mono text-xs text-gray-400">
              {arena.address?.slice(0, 10)}...{arena.address?.slice(-8)}
            </p>
            <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${
              isMainnet ? 'bg-green-50 text-green-700' : 'bg-yellow-50 text-yellow-700'
            }`}>
              <Globe className="w-2.5 h-2.5" />
              {isMainnet ? 'Mainnet' : 'Testnet'}
            </span>
          </div>
        </div>
        {getStatusBadge()}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="bg-gray-50 rounded-lg p-2.5">
          <div className="flex items-center gap-2 text-gray-500 text-[10px] uppercase tracking-wider mb-1">
            <Coins className="w-3 h-3" />
            Entry Fee
          </div>
          <p className="font-heading font-bold text-gray-900">
            {formatMON(arena.entry_fee)} MON
          </p>
        </div>
        <div className="bg-gray-50 rounded-lg p-2.5">
          <div className="flex items-center gap-2 text-gray-500 text-[10px] uppercase tracking-wider mb-1">
            <Users className="w-3 h-3" />
            Players
          </div>
          <p className="font-heading font-bold text-gray-900">
            {playerCount} / {arena.max_players}
          </p>
        </div>
      </div>

      {/* 1-Minute Timeout Warning */}
      {isWaitingForPlayers && hasIdleTimeout && (
        <div className="flex items-center gap-2 bg-orange-50 border border-orange-100 rounded-lg p-3 mb-4 animate-in fade-in slide-in-from-top-1">
          <AlertCircle className="w-4 h-4 text-orange-500 shrink-0" />
          <div className="flex-1">
            <p className="text-[10px] text-orange-700 font-medium uppercase tracking-tight">Refund Countdown</p>
            <div className="flex items-center justify-between">
              <span className="text-xs text-orange-600">Resetting in:</span>
              <CountdownTimer targetTime={arena.idle_ends_at} variant="inline" className="text-orange-700 font-bold" />
            </div>
          </div>
        </div>
      )}

      {/* Players Preview */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex -space-x-2">
          {playerCount > 0 ? (
            arena.players?.slice(0, 5).map((player) => (
              <div 
                key={player} 
                className="w-8 h-8 rounded-full bg-gradient-to-br from-[#836EF9] to-[#A192FA] border-2 border-white flex items-center justify-center text-[10px] text-white font-bold"
                title={player}
              >
                {player.slice(2, 4).toUpperCase()}
              </div>
            ))
          ) : (
            <span className="text-xs text-gray-400 italic">No players yet</span>
          )}
          {playerCount > 5 && (
            <div className="w-8 h-8 rounded-full bg-gray-100 border-2 border-white flex items-center justify-center text-[10px] text-gray-600 font-bold">
              +{playerCount - 5}
            </div>
          )}
        </div>
        {!arena.is_finalized && !arena.is_closed && spotsLeft > 0 && (
          <span className="text-xs text-[#836EF9] font-medium">
            {spotsLeft} spots left
          </span>
        )}
      </div>

      {/* Prize Pool */}
      <div className="bg-gradient-to-r from-purple-50 to-indigo-50 rounded-lg p-3 mb-4">
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500">Total Prize Pool</span>
          <span className="font-heading font-bold text-[#836EF9]">
            {formatMON((BigInt(arena.entry_fee || '0') * BigInt(playerCount)).toString())} MON
          </span>
        </div>
      </div>

      {/* Registration Countdown (Only if not waiting for idle refund) */}
      {!arena.is_finalized && arena.registration_deadline && !arena.is_closed && !isWaitingForPlayers && (
        <div className="flex items-center justify-between mb-4 px-1">
          <span className="text-xs text-gray-500 italic">Registration ends in</span>
          <CountdownTimer targetTime={arena.registration_deadline} variant="inline" />
        </div>
      )}

      {/* Action */}
      <Link to={`/arena/${arena.address}`}>
        <Button
          className={`w-full transition-all flex items-center justify-center gap-2 ${
            arena.is_finalized 
            ? 'bg-gray-900 hover:bg-black text-white' 
            : 'bg-[#836EF9] hover:bg-[#6e56f8] text-white'
          }`}
          data-testid={`view-arena-btn-${arena.address}`}
        >
          {arena.is_finalized ? 'View Results' : arena.is_closed ? 'In Progress' : 'Join Arena'}
          <ArrowRight className="w-4 h-4" />
        </Button>
      </Link>

      {/* Footer */}
      <div className="mt-4 pt-4 border-t border-gray-50 flex items-center justify-between text-[10px] text-gray-400">
        <div className="flex items-center gap-1">
          <Clock className="w-3 h-3" />
          Created {new Date(arena.created_at).toLocaleDateString()}
        </div>
        {arena.created_by === 'agent' && (
          <div className="flex items-center gap-1 text-[#836EF9] font-medium">
            <Bot className="w-3 h-3" />
            <span>AI AGENT</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default ArenaCard;