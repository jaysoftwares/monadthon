/**
 * BlackjackGame Component
 *
 * Classic Blackjack tournament - beat the dealer and outscore other players.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Progress } from '../ui/progress';
import { Trophy, Clock, Plus, Hand } from 'lucide-react';

// Card rendering component
const PlayingCard = ({ card, hidden = false }) => {
  if (!card) return null;

  const suitSymbols = {
    hearts: '♥️',
    diamonds: '♦️',
    clubs: '♣️',
    spades: '♠️',
  };

  const suitColors = {
    hearts: 'text-red-500',
    diamonds: 'text-red-500',
    clubs: 'text-white',
    spades: 'text-white',
  };

  if (hidden) {
    return (
      <div className="w-16 h-24 bg-gradient-to-br from-blue-600 to-blue-800 rounded-lg border-2 border-white/20 flex items-center justify-center shadow-lg">
        <span className="text-2xl">🎴</span>
      </div>
    );
  }

  return (
    <div className="w-16 h-24 bg-white rounded-lg border-2 border-gray-300 flex flex-col items-center justify-between p-1 shadow-lg">
      <div className={`text-left w-full ${suitColors[card.suit]}`}>
        <span className="font-bold text-sm">{card.rank}</span>
        <span className="text-xs">{suitSymbols[card.suit]}</span>
      </div>
      <span className="text-3xl">{suitSymbols[card.suit]}</span>
      <div className={`text-right w-full rotate-180 ${suitColors[card.suit]}`}>
        <span className="font-bold text-sm">{card.rank}</span>
        <span className="text-xs">{suitSymbols[card.suit]}</span>
      </div>
    </div>
  );
};

// Calculate hand value
const calculateHandValue = (cards) => {
  if (!cards || cards.length === 0) return 0;

  let total = 0;
  let aces = 0;

  cards.forEach(card => {
    if (['J', 'Q', 'K'].includes(card.rank)) {
      total += 10;
    } else if (card.rank === 'A') {
      aces += 1;
      total += 11;
    } else {
      total += parseInt(card.rank);
    }
  });

  // Adjust aces
  while (total > 21 && aces > 0) {
    total -= 10;
    aces -= 1;
  }

  return total;
};

export default function BlackjackGame({ arenaAddress, playerAddress, gameState, onSubmitMove, onRefresh }) {
  const [actionTaken, setActionTaken] = useState(false);
  const [roundTimeLeft, setRoundTimeLeft] = useState(30);
  const [lastResult, setLastResult] = useState(null);

  const challenge = gameState?.current_challenge || {};
  const leaderboard = gameState?.leaderboard || [];
  const round = gameState?.round_number || 1;
  const totalRounds = 5;

  const playerHands = challenge.player_hands || {};
  const dealerHand = challenge.dealer_hand || { cards: [] };
  const myHand = playerHands[playerAddress] || { cards: [], status: 'waiting' };
  const myCards = myHand.cards || [];
  const myTotal = calculateHandValue(myCards);
  const myStatus = myHand.status || 'playing';

  // Reset on new round
  useEffect(() => {
    setActionTaken(false);
    setLastResult(null);
    setRoundTimeLeft(challenge.time_limit || 30);
  }, [round, challenge.time_limit]);

  const handleAction = useCallback(async (action) => {
    if (actionTaken || myStatus !== 'playing') return;

    try {
      const result = await onSubmitMove({ action });
      setLastResult(result);

      if (action === 'stand' || result.game_state?.total > 21) {
        setActionTaken(true);
      }

      onRefresh();
    } catch (err) {
      setLastResult({ success: false, message: err.message });
    }
  }, [actionTaken, myStatus, onSubmitMove, onRefresh]);

  // Countdown timer
  useEffect(() => {
    if (roundTimeLeft <= 0 || myStatus !== 'playing') return;

    const timer = setInterval(() => {
      setRoundTimeLeft(prev => {
        if (prev <= 1 && !actionTaken) {
          // Auto stand on timeout
          handleAction('stand');
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [roundTimeLeft, myStatus, actionTaken, handleAction]);

  const myScore = leaderboard.find(p => p.address === playerAddress)?.score || 0;
  const canAct = myStatus === 'playing' && !actionTaken;

  return (
    <div className="w-full max-w-2xl mx-auto space-y-4">
      {/* Header */}
      <Card className="bg-gradient-to-r from-green-600/20 to-emerald-600/20 border-green-500/30">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <span className="text-2xl">🃏</span>
              Blackjack Showdown
            </CardTitle>
            <div className="flex items-center gap-3">
              <Badge variant="outline">
                Hand {round}/{totalRounds}
              </Badge>
              <Badge variant={roundTimeLeft < 10 ? "destructive" : "secondary"} className="text-lg">
                <Clock className="w-4 h-4 mr-1" />
                {roundTimeLeft}s
              </Badge>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-400">Your Chips: <span className="text-green-400 font-bold">{myScore}</span></span>
            <span className="text-gray-400">Beat the dealer to win chips!</span>
          </div>
          <Progress value={(round / totalRounds) * 100} className="mt-2 h-2" />
        </CardContent>
      </Card>

      {/* Game Table */}
      <Card className="bg-gradient-to-b from-green-900 to-green-800 border-green-700">
        <CardContent className="p-6 space-y-8">
          {/* Dealer */}
          <div className="text-center">
            <p className="text-white/70 mb-3">Dealer</p>
            <div className="flex justify-center gap-2">
              {dealerHand.cards?.map((card, index) => (
                <PlayingCard
                  key={index}
                  card={card}
                  hidden={dealerHand.hidden && index === 1}
                />
              ))}
            </div>
            {!dealerHand.hidden && (
              <p className="text-white mt-2 font-bold">
                {calculateHandValue(dealerHand.cards)}
              </p>
            )}
          </div>

          {/* Divider */}
          <div className="border-t border-white/20" />

          {/* Player */}
          <div className="text-center">
            <p className="text-white/70 mb-3">Your Hand</p>
            <div className="flex justify-center gap-2">
              {myCards.map((card, index) => (
                <PlayingCard key={index} card={card} />
              ))}
            </div>
            <p className={`mt-2 font-bold text-xl ${
              myTotal > 21 ? 'text-red-400' :
              myTotal === 21 ? 'text-yellow-400' :
              'text-white'
            }`}>
              {myTotal}
              {myTotal > 21 && ' - BUST!'}
              {myTotal === 21 && ' - BLACKJACK!'}
            </p>
          </div>

          {/* Status */}
          {myStatus !== 'playing' && (
            <div className={`text-center p-3 rounded-lg ${
              myStatus === 'bust' ? 'bg-red-500/30 text-red-400' :
              myStatus === 'stand' ? 'bg-blue-500/30 text-blue-400' :
              'bg-gray-500/30 text-gray-400'
            }`}>
              <p className="font-bold uppercase">{myStatus}</p>
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-center gap-4">
            <Button
              onClick={() => handleAction('hit')}
              disabled={!canAct || myTotal >= 21}
              size="lg"
              variant="outline"
              className="bg-blue-500/20 border-blue-400 hover:bg-blue-500/40"
            >
              <Plus className="w-5 h-5 mr-2" />
              Hit
            </Button>
            <Button
              onClick={() => handleAction('stand')}
              disabled={!canAct}
              size="lg"
              variant="outline"
              className="bg-yellow-500/20 border-yellow-400 hover:bg-yellow-500/40"
            >
              <Hand className="w-5 h-5 mr-2" />
              Stand
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Result */}
      {lastResult && (
        <Card className={`border ${
          lastResult.success ? 'border-green-500/50 bg-green-500/10' : 'border-red-500/50 bg-red-500/10'
        }`}>
          <CardContent className="p-4 text-center">
            <p className={lastResult.success ? 'text-green-400' : 'text-red-400'}>
              {lastResult.message}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Other Players */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Trophy className="w-5 h-5 text-yellow-400" />
            All Players
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(playerHands).map(([addr, hand], index) => {
              const handCards = hand.cards || [];
              const total = calculateHandValue(handCards);
              const isMe = addr === playerAddress;

              return (
                <div
                  key={addr}
                  className={`flex items-center justify-between p-2 rounded ${
                    isMe ? 'bg-green-500/20 border border-green-500/30' : 'bg-slate-800/50'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs">
                      {addr.slice(0, 4)}...
                    </span>
                    {isMe && <Badge variant="secondary" className="text-xs">You</Badge>}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-gray-400 text-sm">{hand.status}</span>
                    <span className={`font-bold ${
                      total > 21 ? 'text-red-400' : 'text-green-400'
                    }`}>
                      {total}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
