/**
 * ClawGame Component
 *
 * Interactive claw machine mini-game where players grab prizes.
 * Uses click/tap to position and drop the claw.
 */

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Progress } from '../ui/progress';
import { Target, Trophy, Zap } from 'lucide-react';

const PRIZE_COLORS = {
  common: 'bg-gray-400',
  uncommon: 'bg-blue-400',
  rare: 'bg-purple-500',
  golden: 'bg-yellow-400 animate-pulse',
};

const PRIZE_VALUES = {
  common: 10,
  uncommon: 25,
  rare: 50,
  golden: 100,
};

export default function ClawGame({
  arenaAddress,
  playerAddress,
  gameState,
  onSubmitMove,
  onRefresh,
}) {
  const [clawPosition, setClawPosition] = useState({ x: 50, y: 10 });
  const [isDropping, setIsDropping] = useState(false);
  const [score, setScore] = useState(0);
  const [attemptsLeft, setAttemptsLeft] = useState(5);
  const [lastResult, setLastResult] = useState(null);
  const [timeLeft, setTimeLeft] = useState(120);
  const gameAreaRef = useRef(null);

  // ✅ Memoize derived challenge + prizes so hooks deps don't change every render
  const challenge = useMemo(
    () => gameState?.current_challenge ?? {},
    [gameState?.current_challenge]
  );

  const prizes = useMemo(() => challenge.prizes ?? [], [challenge.prizes]);

  const maxAttempts = useMemo(
    () => challenge.attempts_per_player ?? 5,
    [challenge.attempts_per_player]
  );

  // Countdown timer
  useEffect(() => {
    if (timeLeft <= 0) return;

    const timer = setInterval(() => {
      setTimeLeft((prev) => Math.max(0, prev - 1));
    }, 1000);

    return () => clearInterval(timer);
  }, [timeLeft]);

  // Handle click/tap to position claw
  const handleAreaClick = (e) => {
    if (isDropping || attemptsLeft <= 0) return;
    if (!gameAreaRef.current) return;

    const rect = gameAreaRef.current.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;

    // Only allow positioning in top half
    if (y < 50) {
      setClawPosition({
        x: Math.max(5, Math.min(95, x)),
        y: Math.max(5, Math.min(45, y)),
      });
    }
  };

  // Drop the claw
  const handleDrop = useCallback(async () => {
    if (isDropping || attemptsLeft <= 0) return;

    setIsDropping(true);
    setLastResult(null);

    // Capture current X so we don't depend on any async state changes
    const dropX = clawPosition.x;
    const dropY = 80;

    // Animate claw dropping
    setClawPosition((prev) => ({ ...prev, x: dropX, y: dropY }));

    // Find nearest prize (ignoring already grabbed)
    let nearestPrize = null;
    let nearestDistance = Infinity;

    prizes.forEach((prize) => {
      if (prize.grabbed) return;
      const dx = prize.x - dropX;
      const dy = prize.y - dropY;
      const distance = Math.sqrt(dx * dx + dy * dy);
      if (distance < nearestDistance) {
        nearestDistance = distance;
        nearestPrize = prize;
      }
    });

    // Wait for animation
    await new Promise((r) => setTimeout(r, 800));

    // Submit move to backend
    try {
      const result = await onSubmitMove({
        prize_id: nearestPrize?.id,
        x: dropX,
        y: dropY,
      });

      setLastResult(result);
      if (result?.player_score !== undefined) {
        setScore(result.player_score);
      }
      setAttemptsLeft((prev) => prev - 1);
    } catch (err) {
      setLastResult({
        success: false,
        message: err?.message || 'Something went wrong',
      });
    }

    // Retract claw
    await new Promise((r) => setTimeout(r, 500));
    setClawPosition((prev) => ({ ...prev, y: 10 }));
    setIsDropping(false);

    // Refresh game state
    onRefresh();
  }, [isDropping, attemptsLeft, prizes, clawPosition.x, onSubmitMove, onRefresh]);

  // Keyboard controls
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (isDropping || attemptsLeft <= 0) return;

      switch (e.key) {
        case 'ArrowLeft':
          setClawPosition((prev) => ({ ...prev, x: Math.max(5, prev.x - 5) }));
          break;
        case 'ArrowRight':
          setClawPosition((prev) => ({ ...prev, x: Math.min(95, prev.x + 5) }));
          break;
        case ' ':
          e.preventDefault();
          handleDrop();
          break;
        default:
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isDropping, attemptsLeft, handleDrop]);

  return (
    <div className="w-full max-w-2xl mx-auto space-y-4">
      {/* Header */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <span className="text-2xl">🎮</span>
              Claw Machine Madness
            </CardTitle>
            <div className="flex items-center gap-4">
              <Badge variant="outline" className="text-lg px-3 py-1">
                <Trophy className="w-4 h-4 mr-1" />
                {score} pts
              </Badge>
              <Badge
                variant={timeLeft < 30 ? 'destructive' : 'secondary'}
                className="text-lg px-3 py-1"
              >
                {Math.floor(timeLeft / 60)}:{String(timeLeft % 60).padStart(2, '0')}
              </Badge>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between text-sm text-gray-400">
            <span>
              Attempts: {attemptsLeft} / {maxAttempts}
            </span>
            <span>Use arrow keys or click to position, SPACE to drop</span>
          </div>
          <Progress value={(attemptsLeft / maxAttempts) * 100} className="mt-2 h-2" />
        </CardContent>
      </Card>

      {/* Game Area */}
      <Card className="overflow-hidden">
        <div
          ref={gameAreaRef}
          className="relative w-full h-[400px] bg-gradient-to-b from-slate-900 to-slate-800 cursor-crosshair"
          onClick={handleAreaClick}
        >
          {/* Glass case edges */}
          <div className="absolute inset-0 border-4 border-slate-600 rounded-lg pointer-events-none" />

          {/* Claw mechanism */}
          <div
            className="absolute transition-all duration-500 ease-out"
            style={{
              left: `${clawPosition.x}%`,
              top: `${clawPosition.y}%`,
              transform: 'translate(-50%, -50%)',
            }}
          >
            {/* Claw arm */}
            <div className="w-1 bg-slate-400 h-8 mx-auto" />
            {/* Claw */}
            <div className="relative">
              <div
                className={`w-8 h-8 flex items-center justify-center transition-transform ${
                  isDropping ? 'scale-90' : 'scale-100'
                }`}
              >
                <div
                  className="absolute w-2 h-6 bg-slate-300 rounded-b transform -rotate-30 origin-top"
                  style={{ left: '2px' }}
                />
                <div
                  className="absolute w-2 h-6 bg-slate-300 rounded-b origin-top"
                  style={{ left: '12px' }}
                />
                <div
                  className="absolute w-2 h-6 bg-slate-300 rounded-b transform rotate-30 origin-top"
                  style={{ right: '2px' }}
                />
              </div>
            </div>
            {/* Target indicator */}
            <Target className="w-6 h-6 text-purple-400 mx-auto mt-2 animate-pulse" />
          </div>

          {/* Prizes */}
          {prizes.map((prize) => (
            <div
              key={prize.id}
              className={`absolute w-10 h-10 rounded-full ${PRIZE_COLORS[prize.type]} shadow-lg transform -translate-x-1/2 -translate-y-1/2 transition-all ${
                prize.grabbed ? 'opacity-30 scale-75' : 'hover:scale-110'
              }`}
              style={{
                left: `${prize.x}%`,
                top: `${prize.y}%`,
              }}
            >
              <div className="w-full h-full flex items-center justify-center text-white font-bold text-xs">
                {prize.value}
              </div>
            </div>
          ))}

          {/* Prize zone indicator */}
          <div className="absolute bottom-4 left-4 right-4 text-center">
            <div className="inline-flex gap-4 bg-black/50 rounded-lg px-4 py-2">
              {Object.entries(PRIZE_VALUES).map(([type, value]) => (
                <div key={type} className="flex items-center gap-1">
                  <div className={`w-3 h-3 rounded-full ${PRIZE_COLORS[type]}`} />
                  <span className="text-xs text-gray-300">{value}pts</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Card>

      {/* Last result */}
      {lastResult && (
        <Card
          className={`border ${
            lastResult.success
              ? 'border-green-500/50 bg-green-500/10'
              : 'border-red-500/50 bg-red-500/10'
          }`}
        >
          <CardContent className="p-4 text-center">
            <p className={lastResult.success ? 'text-green-400' : 'text-red-400'}>
              {lastResult.message}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Drop button for mobile */}
      <Button
        onClick={handleDrop}
        disabled={isDropping || attemptsLeft <= 0}
        className="w-full py-6 text-xl"
        size="lg"
      >
        {isDropping ? (
          <>
            <Zap className="w-6 h-6 mr-2 animate-bounce" />
            Grabbing...
          </>
        ) : attemptsLeft <= 0 ? (
          'No attempts left'
        ) : (
          <>
            <Target className="w-6 h-6 mr-2" />
            Drop Claw!
          </>
        )}
      </Button>
    </div>
  );
}
