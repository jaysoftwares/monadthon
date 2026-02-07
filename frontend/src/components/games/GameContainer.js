/**
 * GameContainer Component
 *
 * Main container that manages game state and switches between:
 * 1. Waiting state
 * 2. Learning phase (1 minute)
 * 3. Active game (Claw, Prediction, Speed, or Blackjack)
 * 4. Results
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import LearningPhase from './LearningPhase';
import ClawGame from './ClawGame';
import PredictionGame from './PredictionGame';
import SpeedGame from './SpeedGame';
import BlackjackGame from './BlackjackGame';
import GameResults from './GameResults';
import { Loader2, Users, Trophy } from 'lucide-react';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export default function GameContainer({ arenaAddress, playerAddress, onGameEnd }) {
  const [gameState, setGameState] = useState(null);
  const [arena, setArena] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch arena and game state
  const fetchState = useCallback(async () => {
    try {
      const [arenaRes, gameRes] = await Promise.all([
        fetch(`${API_URL}/api/arenas/${arenaAddress}`),
        fetch(`${API_URL}/api/arenas/${arenaAddress}/game`)
      ]);

      if (arenaRes.ok) {
        setArena(await arenaRes.json());
      }

      if (gameRes.ok) {
        setGameState(await gameRes.json());
      }

      setLoading(false);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  }, [arenaAddress]);

  // Poll for updates
  useEffect(() => {
    fetchState();
    const interval = setInterval(fetchState, 3000);
    return () => clearInterval(interval);
  }, [fetchState]);

  // Submit a move to the game
  const submitMove = async (moveData) => {
    try {
      const response = await fetch(`${API_URL}/api/arenas/${arenaAddress}/game/move`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          arena_address: arenaAddress,
          player_address: playerAddress,
          move_data: moveData
        })
      });

      if (response.ok) {
        const result = await response.json();
        // Update local game state
        await fetchState();
        return result;
      } else {
        const err = await response.json();
        throw new Error(err.detail || 'Move failed');
      }
    } catch (err) {
      console.error('Move error:', err);
      throw err;
    }
  };

  if (loading) {
    return (
      <Card className="w-full max-w-2xl mx-auto">
        <CardContent className="p-12 flex flex-col items-center justify-center">
          <Loader2 className="w-12 h-12 animate-spin text-purple-400 mb-4" />
          <p className="text-gray-400">Loading game...</p>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="w-full max-w-2xl mx-auto border-red-500/50">
        <CardContent className="p-8 text-center">
          <p className="text-red-400 mb-4">Error: {error}</p>
          <Button onClick={fetchState} variant="outline">
            Try Again
          </Button>
        </CardContent>
      </Card>
    );
  }

  const status = gameState?.status || arena?.game_status || 'waiting';
  const gameType = gameState?.game_type || arena?.game_type || 'prediction';
  const gameConfig = arena?.game_config || {};

  // Render based on game status
  switch (status) {
    case 'waiting':
      return (
        <Card className="w-full max-w-2xl mx-auto">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="w-5 h-5" />
              Waiting for Players
            </CardTitle>
          </CardHeader>
          <CardContent className="text-center py-8">
            <p className="text-gray-400 mb-4">
              {arena?.players?.length || 0} / {arena?.max_players || 8} players joined
            </p>
            <p className="text-sm text-gray-500">
              Game will start once registration closes
            </p>
            {gameConfig.name && (
              <div className="mt-6 p-4 bg-purple-500/10 rounded-lg">
                <p className="text-purple-400 font-semibold">
                  This tournament features: {gameConfig.name}
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      );

    case 'learning':
      return (
        <LearningPhase
          gameConfig={gameConfig}
          totalSeconds={arena?.learning_phase_seconds || 60}
          onLearningComplete={() => {
            // Learning complete - game will activate
            fetchState();
          }}
        />
      );

    case 'active':
      // Render the appropriate game component
      const GameComponent = {
        claw: ClawGame,
        prediction: PredictionGame,
        speed: SpeedGame,
        blackjack: BlackjackGame
      }[gameType] || PredictionGame;

      return (
        <GameComponent
          arenaAddress={arenaAddress}
          playerAddress={playerAddress}
          gameState={gameState}
          onSubmitMove={submitMove}
          onRefresh={fetchState}
        />
      );

    case 'finished':
      return (
        <GameResults
          arenaAddress={arenaAddress}
          gameState={gameState}
          arena={arena}
          playerAddress={playerAddress}
          onClose={onGameEnd}
        />
      );

    default:
      return (
        <Card className="w-full max-w-2xl mx-auto">
          <CardContent className="p-8 text-center">
            <p className="text-gray-400">Unknown game status: {status}</p>
          </CardContent>
        </Card>
      );
  }
}
