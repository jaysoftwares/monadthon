/**
 * LearningPhase Component
 *
 * Displays a 1-minute countdown with game rules before the game starts.
 * Shows how to play, tips, and a visual countdown timer.
 */

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Progress } from '../ui/progress';
import { Badge } from '../ui/badge';
import { Clock, Lightbulb, BookOpen, Gamepad2 } from 'lucide-react';

const GAME_ICONS = {
  claw: '🎮',
  prediction: '🔮',
  speed: '⚡',
  blackjack: '🃏',
};

const GAME_COLORS = {
  claw: 'from-purple-500 to-pink-500',
  prediction: 'from-blue-500 to-cyan-500',
  speed: 'from-yellow-500 to-orange-500',
  blackjack: 'from-green-500 to-emerald-500',
};

export default function LearningPhase({ gameConfig, onLearningComplete, totalSeconds = 60 }) {
  const [timeLeft, setTimeLeft] = useState(totalSeconds);
  const [currentTip, setCurrentTip] = useState(0);

  // Countdown timer
  useEffect(() => {
    if (timeLeft <= 0) {
      onLearningComplete?.();
      return;
    }

    const timer = setInterval(() => {
      setTimeLeft(prev => prev - 1);
    }, 1000);

    return () => clearInterval(timer);
  }, [timeLeft, onLearningComplete]);

  // Rotate tips
  useEffect(() => {
    if (!gameConfig?.tips?.length) return;

    const tipTimer = setInterval(() => {
      setCurrentTip(prev => (prev + 1) % gameConfig.tips.length);
    }, 5000);

    return () => clearInterval(tipTimer);
  }, [gameConfig?.tips]);

  if (!gameConfig) {
    return (
      <Card className="w-full max-w-2xl mx-auto">
        <CardContent className="p-8 text-center">
          <p className="text-gray-400">Loading game information...</p>
        </CardContent>
      </Card>
    );
  }

  const progress = ((totalSeconds - timeLeft) / totalSeconds) * 100;
  const gameType = gameConfig.type || gameConfig.game_type || 'prediction';
  const icon = GAME_ICONS[gameType] || '🎮';
  const colorGradient = GAME_COLORS[gameType] || 'from-purple-500 to-pink-500';

  return (
    <div className="w-full max-w-2xl mx-auto space-y-6">
      {/* Header with countdown */}
      <Card className="overflow-hidden">
        <div className={`bg-gradient-to-r ${colorGradient} p-6 text-white`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-4xl">{icon}</span>
              <div>
                <h2 className="text-2xl font-bold">{gameConfig.name}</h2>
                <p className="text-white/80">Learn the rules before you play!</p>
              </div>
            </div>
            <div className="text-right">
              <div className="flex items-center gap-2 text-white/90">
                <Clock className="w-5 h-5" />
                <span className="text-sm">Starting in</span>
              </div>
              <div className="text-4xl font-mono font-bold">
                {String(Math.floor(timeLeft / 60)).padStart(2, '0')}:
                {String(timeLeft % 60).padStart(2, '0')}
              </div>
            </div>
          </div>
          <Progress value={progress} className="mt-4 h-2 bg-white/30" />
        </div>

        <CardContent className="p-6">
          <p className="text-gray-300 text-lg">{gameConfig.description}</p>
        </CardContent>
      </Card>

      {/* How to Play */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-purple-400" />
            How to Play
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ol className="space-y-3">
            {gameConfig.how_to_play?.map((step, index) => (
              <li key={index} className="flex items-start gap-3">
                <span className="flex-shrink-0 w-7 h-7 rounded-full bg-purple-500/20 text-purple-400 flex items-center justify-center font-bold text-sm">
                  {index + 1}
                </span>
                <span className="text-gray-300 pt-0.5">{step}</span>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>

      {/* Tips - Rotating */}
      <Card className="border-yellow-500/30 bg-yellow-500/5">
        <CardContent className="p-6">
          <div className="flex items-start gap-4">
            <div className="flex-shrink-0 w-10 h-10 rounded-full bg-yellow-500/20 flex items-center justify-center">
              <Lightbulb className="w-5 h-5 text-yellow-400" />
            </div>
            <div>
              <h3 className="font-semibold text-yellow-400 mb-1">Pro Tip</h3>
              <p className="text-gray-300 transition-all duration-300">
                {gameConfig.tips?.[currentTip] || 'Good luck!'}
              </p>
            </div>
          </div>
          {gameConfig.tips?.length > 1 && (
            <div className="flex justify-center gap-1 mt-4">
              {gameConfig.tips.map((_, index) => (
                <div
                  key={index}
                  className={`w-2 h-2 rounded-full transition-colors ${
                    index === currentTip ? 'bg-yellow-400' : 'bg-yellow-400/30'
                  }`}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Game Info */}
      <div className="flex justify-center gap-4 flex-wrap">
        <Badge variant="outline" className="px-4 py-2">
          <Gamepad2 className="w-4 h-4 mr-2" />
          Duration: {Math.floor((gameConfig.duration_seconds || 120) / 60)} min
        </Badge>
        <Badge variant="outline" className="px-4 py-2">
          Players: {gameConfig.min_players || 2} - {gameConfig.max_players || 16}
        </Badge>
      </div>

      {/* Ready message */}
      {timeLeft <= 10 && (
        <Card className="border-green-500/50 bg-green-500/10 animate-pulse">
          <CardContent className="p-4 text-center">
            <p className="text-green-400 font-bold text-lg">
              Get Ready! Game starting in {timeLeft} seconds...
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
