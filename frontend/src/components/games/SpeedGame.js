/**
 * SpeedGame Component
 *
 * Fast-paced challenges: math problems, pattern recognition, reaction time.
 * Faster correct answers = more points.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import { Progress } from '../ui/progress';
import { Zap, Brain, Timer, Trophy, AlertCircle } from 'lucide-react';

export default function SpeedGame({ arenaAddress, playerAddress, gameState, onSubmitMove, onRefresh }) {
  const [answer, setAnswer] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [startTime, setStartTime] = useState(null);
  const [reactionStart, setReactionStart] = useState(null);
  const [showReactionTarget, setShowReactionTarget] = useState(false);
  const [lastResult, setLastResult] = useState(null);
  const [roundTimeLeft, setRoundTimeLeft] = useState(10);
  const inputRef = useRef(null);

  const challenge = gameState?.current_challenge || {};
  const leaderboard = gameState?.leaderboard || [];
  const round = gameState?.round_number || 1;
  const totalRounds = 10;
  const challengeType = challenge.type || 'math';

  // Start timer when challenge loads
  useEffect(() => {
    setStartTime(Date.now());
    setSubmitted(false);
    setAnswer('');
    setLastResult(null);
    setRoundTimeLeft(challenge.time_limit || 10);
    setShowReactionTarget(false);

    // For reaction challenges, set up the delay
    if (challengeType === 'reaction' && challenge.delay_ms) {
      const delay = challenge.delay_ms;
      setTimeout(() => {
        setShowReactionTarget(true);
        setReactionStart(Date.now());
      }, delay);
    }

    // Focus input
    if (inputRef.current && challengeType !== 'reaction') {
      inputRef.current.focus();
    }
  }, [round, challengeType, challenge.delay_ms, challenge.time_limit]);

  const handleSubmit = useCallback(async (timeout = false) => {
    if (submitted) return;

    const responseTime = startTime ? Date.now() - startTime : 10000;

    let submittedAnswer = answer;
    if (challengeType === 'reaction') {
      // For reaction, the answer is the reaction time
      if (showReactionTarget && reactionStart) {
        submittedAnswer = Date.now() - reactionStart;
      } else {
        // Too early!
        submittedAnswer = -1;
      }
    } else {
      submittedAnswer = parseInt(answer) || 0;
    }

    setSubmitted(true);

    try {
      const result = await onSubmitMove({
        answer: submittedAnswer,
        response_time_ms: responseTime
      });
      setLastResult(result);
    } catch (err) {
      setLastResult({ success: false, message: err.message });
    }
  }, [submitted, startTime, answer, challengeType, showReactionTarget, reactionStart, onSubmitMove]);

  // Countdown timer
  useEffect(() => {
    if (roundTimeLeft <= 0 || submitted) return;

    const timer = setInterval(() => {
      setRoundTimeLeft(prev => {
        if (prev <= 1) {
          // Time's up - auto submit wrong answer
          if (!submitted) {
            handleSubmit(true);
          }
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [roundTimeLeft, submitted, handleSubmit]);

  const handleReactionClick = () => {
    if (submitted) return;

    if (!showReactionTarget) {
      // Clicked too early!
      setLastResult({ success: false, message: 'Too early! Wait for GREEN!' });
      setSubmitted(true);
      return;
    }

    handleSubmit();
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !submitted) {
      handleSubmit();
    }
  };

  const myScore = leaderboard.find(p => p.address === playerAddress)?.score || 0;

  // Render based on challenge type
  const renderChallenge = () => {
    switch (challengeType) {
      case 'reaction':
        return (
          <div
            className={`w-full h-64 rounded-xl flex items-center justify-center cursor-pointer transition-all ${
              showReactionTarget
                ? 'bg-green-500 text-white animate-pulse'
                : 'bg-red-500/50 text-white'
            }`}
            onClick={handleReactionClick}
          >
            {submitted ? (
              <div className="text-center">
                {lastResult?.success ? (
                  <>
                    <Zap className="w-16 h-16 mx-auto mb-2" />
                    <p className="text-2xl font-bold">{lastResult.message}</p>
                  </>
                ) : (
                  <>
                    <AlertCircle className="w-16 h-16 mx-auto mb-2" />
                    <p className="text-2xl font-bold">{lastResult?.message || 'Error'}</p>
                  </>
                )}
              </div>
            ) : showReactionTarget ? (
              <div className="text-center">
                <Zap className="w-20 h-20 mx-auto mb-2 animate-bounce" />
                <p className="text-3xl font-bold">CLICK NOW!</p>
              </div>
            ) : (
              <div className="text-center">
                <Timer className="w-16 h-16 mx-auto mb-2" />
                <p className="text-2xl font-bold">Wait for GREEN...</p>
              </div>
            )}
          </div>
        );

      case 'math':
      case 'pattern':
      default:
        return (
          <div className="space-y-6">
            <div className="text-center p-8 bg-slate-800 rounded-xl">
              <Brain className="w-12 h-12 text-yellow-400 mx-auto mb-4" />
              <p className="text-3xl font-bold text-white">
                {challenge.question || 'Loading...'}
              </p>
            </div>

            <div className="flex gap-2">
              <Input
                ref={inputRef}
                type="number"
                placeholder="Your answer..."
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                onKeyPress={handleKeyPress}
                disabled={submitted}
                className="text-2xl text-center py-6"
                autoFocus
              />
              <Button
                onClick={() => handleSubmit()}
                disabled={submitted || !answer}
                size="lg"
                className="px-8"
              >
                <Zap className="w-5 h-5 mr-1" />
                Submit
              </Button>
            </div>

            {lastResult && (
              <div className={`p-4 rounded-lg text-center ${
                lastResult.success ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
              }`}>
                <p className="font-bold">{lastResult.message}</p>
              </div>
            )}
          </div>
        );
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto space-y-4">
      {/* Header */}
      <Card className="bg-gradient-to-r from-yellow-600/20 to-orange-600/20 border-yellow-500/30">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <span className="text-2xl">⚡</span>
              Speed Challenge
            </CardTitle>
            <div className="flex items-center gap-3">
              <Badge variant="outline">
                Round {round}/{totalRounds}
              </Badge>
              <Badge variant={roundTimeLeft < 5 ? "destructive" : "secondary"} className="text-lg">
                <Timer className="w-4 h-4 mr-1" />
                {roundTimeLeft}s
              </Badge>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-400">Your Score: <span className="text-yellow-400 font-bold">{myScore} pts</span></span>
            <span className="text-gray-400">Faster = More Points!</span>
          </div>
          <Progress value={(round / totalRounds) * 100} className="mt-2 h-2" />
        </CardContent>
      </Card>

      {/* Challenge Area */}
      <Card>
        <CardContent className="p-6">
          {renderChallenge()}
        </CardContent>
      </Card>

      {/* Leaderboard */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Trophy className="w-5 h-5 text-yellow-400" />
            Live Rankings
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-2">
            {leaderboard.slice(0, 6).map((player, index) => (
              <div
                key={player.address}
                className={`flex items-center justify-between p-2 rounded ${
                  player.address === playerAddress
                    ? 'bg-yellow-500/20 border border-yellow-500/30'
                    : 'bg-slate-800/50'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold ${
                    index === 0 ? 'bg-yellow-500 text-black' :
                    index === 1 ? 'bg-gray-400 text-black' :
                    index === 2 ? 'bg-amber-600 text-white' :
                    'bg-slate-600 text-white'
                  }`}>
                    {index + 1}
                  </span>
                  <span className="font-mono text-xs">
                    {player.address.slice(0, 4)}...
                  </span>
                </div>
                <span className="font-bold text-yellow-400 text-sm">
                  {player.score}
                </span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
