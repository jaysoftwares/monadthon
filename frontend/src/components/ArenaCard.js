import React from 'react';
import { Link } from 'react-router-dom';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import CountdownTimer from './CountdownTimer';
import { Users, Coins, ArrowRight, Clock, Bot } from 'lucide-react';
import { formatMON, getExplorerUrl } from '../services/api';

const ArenaCard = ({ arena }) => {
  const getStatusBadge = () => {
    if (arena.is_finalized) {
      return <Badge className="badge-finalized" data-testid={`arena-status-${arena.address}`}>Finalized</Badge>;
    }
    if (arena.is_closed) {
      return <Badge className="badge-closed" data-testid={`arena-status-${arena.address}`}>Closed</Badge>;
    }
    if (arena.players?.length >= arena.max_players) {
      return <Badge className="badge-live" data-testid={`arena-status-${arena.address}`}>Full</Badge>;
    }
    return <Badge className="badge-open" data-testid={`arena-status-${arena.address}`}>Open</Badge>;
  };

  const playerCount = arena.players?.length || 0;
  const spotsLeft = arena.max_players - playerCount;

  return (
    <div className="arena-card group" data-testid={`arena-card-${arena.address}`}>
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="font-heading font-semibold text-lg text-gray-900 group-hover:text-[#836EF9] transition-colors">
            {arena.name}
          </h3>
          <p className="font-mono text-xs text-gray-400 mt-1">
            {arena.address?.slice(0, 10)}...{arena.address?.slice(-8)}
          </p>
        </div>
        {getStatusBadge()}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="stats-card">
          <div className="flex items-center gap-2 text-gray-500 text-xs mb-1">
            <Coins className="w-3 h-3" />
            Entry Fee
          </div>
          <p className="font-heading font-semibold text-gray-900">
            {formatMON(arena.entry_fee)} MON
          </p>
        </div>
        <div className="stats-card">
          <div className="flex items-center gap-2 text-gray-500 text-xs mb-1">
            <Users className="w-3 h-3" />
            Players
          </div>
          <p className="font-heading font-semibold text-gray-900">
            {playerCount} / {arena.max_players}
          </p>
        </div>
      </div>

      {/* Players Preview */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex -space-x-2">
          {arena.players?.slice(0, 5).map((player, i) => (
            <div 
              key={player} 
              className="player-avatar border-2 border-white"
              title={player}
            >
              {player.slice(2, 4).toUpperCase()}
            </div>
          ))}
          {playerCount > 5 && (
            <div className="player-avatar border-2 border-white bg-gray-200 text-gray-600">
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
      <div className="bg-gradient-to-r from-purple-50 to-white rounded-lg p-3 mb-4">
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500">Prize Pool</span>
          <span className="font-heading font-bold text-[#836EF9]">
            {formatMON((BigInt(arena.entry_fee || '0') * BigInt(playerCount)).toString())} MON
          </span>
        </div>
      </div>

      {/* Countdown Timer */}
      {!arena.is_finalized && arena.registration_deadline && !arena.is_closed && (
        <div className="flex items-center justify-between mb-4 px-1">
          <span className="text-xs text-gray-500">Registration closes in</span>
          <CountdownTimer targetTime={arena.registration_deadline} variant="inline" />
        </div>
      )}
      {arena.is_closed && !arena.is_finalized && arena.tournament_end_estimate && (
        <div className="flex items-center justify-between mb-4 px-1">
          <span className="text-xs text-gray-500">Tournament ends in</span>
          <CountdownTimer targetTime={arena.tournament_end_estimate} variant="inline" />
        </div>
      )}

      {/* Action */}
      <Link to={`/arena/${arena.address}`}>
        <Button
          className="w-full btn-primary group-hover:shadow-lg transition-shadow"
          data-testid={`view-arena-btn-${arena.address}`}
        >
          {arena.is_finalized ? 'View Results' : arena.is_closed ? 'View Arena' : 'Join Arena'}
          <ArrowRight className="w-4 h-4 ml-2" />
        </Button>
      </Link>

      {/* Footer: Timestamp + Agent Badge */}
      <div className="mt-4 flex items-center justify-between text-xs text-gray-400">
        <div className="flex items-center gap-1">
          <Clock className="w-3 h-3" />
          Created {new Date(arena.created_at).toLocaleDateString()}
        </div>
        {arena.created_by === 'agent' && (
          <div className="flex items-center gap-1 text-[#836EF9]">
            <Bot className="w-3 h-3" />
            <span>Agent</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default ArenaCard;
