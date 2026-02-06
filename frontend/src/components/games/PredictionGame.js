/**
 * PredictionGame Component
 *
 * Players predict outcomes (numbers, prices, etc.)
 * Closest prediction wins each round.
 */

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import { Progress } from '../ui/progress';
import { Eye, EyeOff, Send, Trophy, Clock, Target } from 'lucide-react';

export default function PredictionGame({ arenaAddress, playerAddress, gameState, onSubmitMove, onRefresh }) {
  const [prediction, setPrediction] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState(null);
  const [roundTimeLeft, setRoundTimeLeft] = useState(45);

  const challenge = gameState?.current_challenge || {};
  const leaderboard = gameState?.leaderboard || [];
  const round = gameState?.round_number || 1;
  const totalRounds = 3;

  // Countdown timer for round
  useEffect(() => {
    if (roundTimeLeft <= 0 || submitted) return;

    const timer = setInterval(() => {
      setRoundTimeLeft(prev => Math.max(0, prev - 1));
    }, 1000);

    return () => clearInterval(timer);
  }, [roundTimeLeft, submitted]);

  // Reset on new round
  useEffect(() => {
    setSubmitted(false);
    setPrediction('');
    setRoundTimeLeft(challenge.time_limit || 45);
  }, [round, challenge.time_limit]);

  const handleSubmit = async () => {
    if (!prediction || submitted) return;

    const numValue = parseFloat(prediction);
    if (isNaN(numValue)) {
      setError('Please enter a valid number');
      return;
    }

    if (challenge.min !== undefined && numValue < challenge.min) {
      setError(`Minimum value is ${challenge.min}`);
      return;
    }

    if (challenge.max !== undefined && numValue > challenge.max) {
      setError(`Maximum value is ${challenge.max}`);
      return;
    }

    setError(null);

    try {
      await onSubmitMove({ prediction: numValue });
      setSubmitted(true);
    } catch (err) {
      setError(err.message);
    }
  };

  const myRank = leaderboard.findIndex(p => p.address === playerAddress) + 1;
  const myScore = leaderboard.find(p => p.address === playerAddress)?.score || 0;

  return (
    <div className="w-full max-w-2xl mx-auto space-y-4">
      {/* Header */}
      <Card className="bg-gradient-to-r from-blue-600/20 to-cyan-600/20 border-blue-500/30">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <span className="text-2xl">🔮</span>
              Prediction Arena
            </CardTitle>
            <div className="flex items-center gap-3">
              <Badge variant="outline">
                Round {round}/{totalRounds}
              </Badge>
              <Badge variant={roundTimeLeft < 10 ? "destructive" : "secondary"} className="text-lg">
                <Clock className="w-4 h-4 mr-1" />
                {roundTimeLeft}s
              </Badge>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Progress value={(round / totalRounds) * 100} className="h-2" />
        </CardContent>
      </Card>

      {/* Question */}
      <Card>
        <CardHeader>
          <CardTitle className="text-center text-xl">
            {challenge.question || 'Loading question...'}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Range hint */}
          {(challenge.min !== undefined || challenge.max !== undefined) && (
            <p className="text-center text-gray-400 text-sm">
              Enter a number between {challenge.min ?? '?'} and {challenge.max ?? '?'}
            </p>
          )}

          {/* Input */}
          <div className="flex gap-2">
            <Input
              type="number"
              placeholder="Enter your prediction..."
              value={prediction}
              onChange={(e) => setPrediction(e.target.value)}
              disabled={submitted || roundTimeLeft <= 0}
              className="text-lg text-center"
              min={challenge.min}
              max={challenge.max}
            />
            <Button
              onClick={handleSubmit}
              disabled={submitted || !prediction || roundTimeLeft <= 0}
              size="lg"
            >
              {submitted ? (
                <>
                  <EyeOff className="w-5 h-5 mr-1" />
                  Locked
                </>
              ) : (
                <>
                  <Send className="w-5 h-5 mr-1" />
                  Submit
                </>
              )}
            </Button>
          </div>

          {/* Error message */}
          {error && (
            <p className="text-red-400 text-center text-sm">{error}</p>
          )}

          {/* Submitted confirmation */}
          {submitted && (
            <div className="text-center p-4 bg-green-500/10 rounded-lg border border-green-500/30">
              <Eye className="w-8 h-8 text-green-400 mx-auto mb-2" />
              <p className="text-green-400 font-semibold">
                Prediction locked: {prediction}
              </p>
              <p className="text-gray-400 text-sm">
                Waiting for other players...
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Leaderboard */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Trophy className="w-5 h-5 text-yellow-400" />
            Leaderboard
          </CardTitle>
        </CardHeader>
        <CardContent>
          {leaderboard.length > 0 ? (
            <div className="space-y-2">
              {leaderboard.slice(0, 5).map((player, index) => (
                <div
                  key={player.address}
                  className={`flex items-center justify-between p-3 rounded-lg ${
                    player.address === playerAddress
                      ? 'bg-purple-500/20 border border-purple-500/30'
                      : 'bg-slate-800/50'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <span className={`w-6 h-6 rounded-full flex items-center justify-center text-sm font-bold ${
                      index === 0 ? 'bg-yellow-500 text-black' :
                      index === 1 ? 'bg-gray-400 text-black' :
                      index === 2 ? 'bg-amber-600 text-white' :
                      'bg-slate-600 text-white'
                    }`}>
                      {index + 1}
                    </span>
                    <span className="font-mono text-sm">
                      {player.address.slice(0, 6)}...{player.address.slice(-4)}
                    </span>
                    {player.address === playerAddress && (
                      <Badge variant="secondary" className="text-xs">You</Badge>
                    )}
                  </div>
                  <span className="font-bold text-purple-400">
                    {player.score} pts
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center text-gray-400">No scores yet</p>
          )}

          {/* Your position if not in top 5 */}
          {myRank > 5 && (
            <div className="mt-4 pt-4 border-t border-slate-700">
              <div className="flex items-center justify-between p-3 rounded-lg bg-purple-500/20 border border-purple-500/30">
                <div className="flex items-center gap-3">
                  <span className="w-6 h-6 rounded-full bg-slate-600 flex items-center justify-center text-sm font-bold">
                    {myRank}
                  </span>
                  <span>You</span>
                </div>
                <span className="font-bold text-purple-400">{myScore} pts</span>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Round info */}
      <Card className="bg-slate-800/50">
        <CardContent className="p-4">
          <div className="flex items-center justify-center gap-2 text-gray-400">
            <Target className="w-4 h-4" />
            <span className="text-sm">
              Closest prediction wins the round! Total of 3 rounds.
            </span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
