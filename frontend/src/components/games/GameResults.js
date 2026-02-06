/**
 * GameResults Component
 *
 * Displays final game results with winners, scores, and prizes.
 */

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Trophy, Medal, Award, PartyPopper, ExternalLink } from 'lucide-react';
import confetti from 'canvas-confetti';

const PLACE_COLORS = {
  1: 'from-yellow-400 to-amber-500',
  2: 'from-gray-300 to-gray-400',
  3: 'from-amber-600 to-amber-700',
};

const PLACE_ICONS = {
  1: Trophy,
  2: Medal,
  3: Award,
};

export default function GameResults({ arenaAddress, gameState, arena, playerAddress, onClose }) {
  const winners = arena?.winners || gameState?.winners || [];
  const payouts = arena?.payouts || [];
  const gameResults = arena?.game_results || {};
  const playerScores = gameResults.player_scores || {};

  const isWinner = winners.includes(playerAddress);
  const myRank = winners.indexOf(playerAddress) + 1;
  const myScore = playerScores[playerAddress] || 0;

  // Trigger confetti for winners
  React.useEffect(() => {
    if (isWinner) {
      const duration = 3000;
      const end = Date.now() + duration;

      const frame = () => {
        confetti({
          particleCount: 3,
          angle: 60,
          spread: 55,
          origin: { x: 0 },
          colors: ['#FFD700', '#FFA500', '#FF6347']
        });
        confetti({
          particleCount: 3,
          angle: 120,
          spread: 55,
          origin: { x: 1 },
          colors: ['#FFD700', '#FFA500', '#FF6347']
        });

        if (Date.now() < end) {
          requestAnimationFrame(frame);
        }
      };

      frame();
    }
  }, [isWinner]);

  // Format prize amount
  const formatPrize = (weiString) => {
    if (!weiString) return '0';
    const eth = parseFloat(weiString) / 1e18;
    return eth.toFixed(4);
  };

  // Sort players by score
  const sortedPlayers = Object.entries(playerScores)
    .sort(([, a], [, b]) => b - a)
    .map(([address, score], index) => ({
      address,
      score,
      rank: index + 1,
      isWinner: winners.includes(address),
      prize: winners.indexOf(address) >= 0 ? payouts[winners.indexOf(address)] : null
    }));

  return (
    <div className="w-full max-w-2xl mx-auto space-y-6">
      {/* Winner Announcement */}
      {isWinner ? (
        <Card className="bg-gradient-to-r from-yellow-500/20 to-amber-500/20 border-yellow-500/50 overflow-hidden">
          <CardContent className="p-8 text-center relative">
            <PartyPopper className="w-16 h-16 text-yellow-400 mx-auto mb-4 animate-bounce" />
            <h1 className="text-3xl font-bold text-yellow-400 mb-2">
              Congratulations!
            </h1>
            <p className="text-xl text-white mb-4">
              You placed #{myRank}!
            </p>
            {myRank <= payouts.length && (
              <div className="inline-block bg-yellow-500/30 rounded-lg px-6 py-3">
                <p className="text-yellow-300 text-sm">Prize</p>
                <p className="text-2xl font-bold text-yellow-400">
                  {formatPrize(payouts[myRank - 1])} MON
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      ) : (
        <Card className="bg-slate-800/50">
          <CardContent className="p-8 text-center">
            <p className="text-xl text-gray-400 mb-2">Game Over</p>
            <p className="text-white">
              Your final score: <span className="font-bold text-purple-400">{myScore} points</span>
            </p>
            <p className="text-gray-500 mt-2">Better luck next time!</p>
          </CardContent>
        </Card>
      )}

      {/* Podium */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Trophy className="w-5 h-5 text-yellow-400" />
            Final Standings
          </CardTitle>
        </CardHeader>
        <CardContent>
          {/* Top 3 Podium */}
          <div className="flex justify-center items-end gap-4 mb-8">
            {/* 2nd Place */}
            {sortedPlayers[1] && (
              <div className="text-center">
                <div className={`w-20 h-20 rounded-full bg-gradient-to-b ${PLACE_COLORS[2]} flex items-center justify-center mx-auto mb-2`}>
                  <Medal className="w-10 h-10 text-white" />
                </div>
                <p className="font-mono text-sm text-gray-400">
                  {sortedPlayers[1].address.slice(0, 6)}...
                </p>
                <p className="font-bold text-white">{sortedPlayers[1].score} pts</p>
                {sortedPlayers[1].prize && (
                  <Badge variant="secondary" className="mt-1">
                    {formatPrize(sortedPlayers[1].prize)} MON
                  </Badge>
                )}
              </div>
            )}

            {/* 1st Place */}
            {sortedPlayers[0] && (
              <div className="text-center -mt-8">
                <div className={`w-24 h-24 rounded-full bg-gradient-to-b ${PLACE_COLORS[1]} flex items-center justify-center mx-auto mb-2 shadow-lg shadow-yellow-500/30`}>
                  <Trophy className="w-12 h-12 text-white" />
                </div>
                <p className="font-mono text-sm text-gray-400">
                  {sortedPlayers[0].address.slice(0, 6)}...
                </p>
                <p className="font-bold text-white text-lg">{sortedPlayers[0].score} pts</p>
                {sortedPlayers[0].prize && (
                  <Badge className="mt-1 bg-yellow-500 text-black">
                    {formatPrize(sortedPlayers[0].prize)} MON
                  </Badge>
                )}
              </div>
            )}

            {/* 3rd Place */}
            {sortedPlayers[2] && (
              <div className="text-center">
                <div className={`w-20 h-20 rounded-full bg-gradient-to-b ${PLACE_COLORS[3]} flex items-center justify-center mx-auto mb-2`}>
                  <Award className="w-10 h-10 text-white" />
                </div>
                <p className="font-mono text-sm text-gray-400">
                  {sortedPlayers[2].address.slice(0, 6)}...
                </p>
                <p className="font-bold text-white">{sortedPlayers[2].score} pts</p>
                {sortedPlayers[2].prize && (
                  <Badge variant="secondary" className="mt-1">
                    {formatPrize(sortedPlayers[2].prize)} MON
                  </Badge>
                )}
              </div>
            )}
          </div>

          {/* Full Leaderboard */}
          <div className="space-y-2">
            {sortedPlayers.slice(3).map((player) => (
              <div
                key={player.address}
                className={`flex items-center justify-between p-3 rounded-lg ${
                  player.address === playerAddress
                    ? 'bg-purple-500/20 border border-purple-500/30'
                    : 'bg-slate-800/50'
                }`}
              >
                <div className="flex items-center gap-3">
                  <span className="w-6 h-6 rounded-full bg-slate-600 flex items-center justify-center text-sm font-bold">
                    {player.rank}
                  </span>
                  <span className="font-mono text-sm text-gray-400">
                    {player.address.slice(0, 6)}...{player.address.slice(-4)}
                  </span>
                  {player.address === playerAddress && (
                    <Badge variant="secondary" className="text-xs">You</Badge>
                  )}
                </div>
                <span className="font-bold text-gray-300">
                  {player.score} pts
                </span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Game Info */}
      <Card className="bg-slate-800/50">
        <CardContent className="p-4">
          <div className="flex items-center justify-between text-sm text-gray-400">
            <span>Arena: {arenaAddress?.slice(0, 8)}...</span>
            <span>Game: {arena?.game_type || 'Unknown'}</span>
          </div>
        </CardContent>
      </Card>

      {/* Actions */}
      <div className="flex gap-4">
        <Button onClick={onClose} variant="outline" className="flex-1">
          Back to Arenas
        </Button>
        {arena?.tx_hash && (
          <Button
            variant="secondary"
            className="flex-1"
            onClick={() => window.open(`https://testnet.monadexplorer.com/tx/${arena.tx_hash}`, '_blank')}
          >
            <ExternalLink className="w-4 h-4 mr-2" />
            View Transaction
          </Button>
        )}
      </div>
    </div>
  );
}
