import React, { useState, useEffect } from 'react';
import { getLeaderboard, formatMON, getExplorerUrl } from '../services/api';
import { Skeleton } from '../components/ui/skeleton';
import { Trophy, Medal, ExternalLink, Users, Coins, Target } from 'lucide-react';

const LeaderboardPage = () => {
  const [leaderboard, setLeaderboard] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchLeaderboard = async () => {
      try {
        const data = await getLeaderboard(50);
        setLeaderboard(data);
      } catch (error) {
        console.error('Failed to fetch leaderboard:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchLeaderboard();
  }, []);

  const getRankStyle = (index) => {
    switch (index) {
      case 0:
        return { bg: 'bg-gradient-to-r from-yellow-50 to-amber-50', border: 'border-yellow-200', rank: 'gold' };
      case 1:
        return { bg: 'bg-gradient-to-r from-gray-50 to-slate-50', border: 'border-gray-300', rank: 'silver' };
      case 2:
        return { bg: 'bg-gradient-to-r from-orange-50 to-amber-50', border: 'border-orange-200', rank: 'bronze' };
      default:
        return { bg: 'bg-white', border: 'border-gray-100', rank: 'default' };
    }
  };

  // Calculate total stats
  const totalPayouts = leaderboard.reduce((acc, p) => acc + BigInt(p.total_payouts || '0'), BigInt(0));
  const totalWins = leaderboard.reduce((acc, p) => acc + (p.total_wins || 0), 0);
  const totalPlayers = leaderboard.length;

  return (
    <div className="min-h-screen bg-gray-50" data-testid="leaderboard-page">
      {/* Hero */}
      <div className="bg-gradient-to-br from-white via-purple-50 to-white py-12 border-b border-gray-100">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-[#836EF9] rounded-2xl mb-4">
              <Trophy className="w-8 h-8 text-white" />
            </div>
            <h1 className="font-heading text-4xl font-bold text-gray-900">Leaderboard</h1>
            <p className="text-gray-500 mt-2">Top performers in CLAW ARENA</p>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-card text-center">
              <Users className="w-6 h-6 text-[#836EF9] mx-auto mb-2" />
              <p className="font-heading text-2xl font-bold text-gray-900">{totalPlayers}</p>
              <p className="text-sm text-gray-500">Champions</p>
            </div>
            <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-card text-center">
              <Target className="w-6 h-6 text-green-500 mx-auto mb-2" />
              <p className="font-heading text-2xl font-bold text-gray-900">{totalWins}</p>
              <p className="text-sm text-gray-500">Total Wins</p>
            </div>
            <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-card text-center">
              <Coins className="w-6 h-6 text-[#836EF9] mx-auto mb-2" />
              <p className="font-heading text-2xl font-bold text-[#836EF9]">{formatMON(totalPayouts.toString())}</p>
              <p className="text-sm text-gray-500">MON Distributed</p>
            </div>
          </div>
        </div>
      </div>

      {/* Leaderboard Table */}
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {loading ? (
          <div className="space-y-4">
            {[1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="h-20 rounded-xl" />
            ))}
          </div>
        ) : leaderboard.length > 0 ? (
          <div className="space-y-3">
            {leaderboard.map((player, index) => {
              const style = getRankStyle(index);
              return (
                <div
                  key={player.address}
                  className={`${style.bg} border ${style.border} rounded-xl p-4 sm:p-5 transition-all hover:shadow-md`}
                  data-testid={`leaderboard-row-${index}`}
                >
                  <div className="flex items-center gap-4">
                    {/* Rank */}
                    <div className={`leaderboard-rank ${style.rank} shrink-0`}>
                      {index < 3 ? (
                        <Medal className="w-4 h-4" />
                      ) : (
                        index + 1
                      )}
                    </div>

                    {/* Player Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="font-mono text-sm sm:text-base text-gray-900 truncate">
                          {player.address}
                        </p>
                        <a
                          href={getExplorerUrl('address', player.address)}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-gray-400 hover:text-[#836EF9] shrink-0"
                        >
                          <ExternalLink className="w-4 h-4" />
                        </a>
                      </div>
                      <div className="flex items-center gap-4 mt-1 text-sm text-gray-500">
                        <span>{player.tournaments_won || 0} wins</span>
                        <span>•</span>
                        <span>{player.tournaments_played || 0} played</span>
                      </div>
                    </div>

                    {/* Earnings */}
                    <div className="text-right shrink-0">
                      <p className="font-heading text-xl sm:text-2xl font-bold text-[#836EF9]">
                        {formatMON(player.total_payouts)}
                      </p>
                      <p className="text-sm text-gray-500">MON earned</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="text-center py-16">
            <div className="w-16 h-16 bg-purple-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <Trophy className="w-8 h-8 text-[#836EF9]" />
            </div>
            <h3 className="font-heading text-xl font-semibold text-gray-900 mb-2">No Champions Yet</h3>
            <p className="text-gray-500">Be the first to claim victory in CLAW ARENA!</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default LeaderboardPage;
