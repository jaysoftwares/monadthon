import { useState, useEffect } from 'react';

/**
 * Custom hook to manage arena countdown timers
 * Handles game start countdown and idle timers
 */
export const useArenaTimer = (arena) => {
  const [countdown, setCountdown] = useState(null);
  const [timerType, setTimerType] = useState(null);

  useEffect(() => {
    if (!arena) {
      setCountdown(null);
      setTimerType(null);
      return;
    }

    // Check if game start countdown should be active
    if (arena.is_closed && arena.game_status === 'waiting' && arena.closed_at && !arena.game_id) {
      setTimerType('game_start');
      
      const updateCountdown = () => {
        const closedTime = new Date(arena.closed_at);
        const gameStartTime = new Date(closedTime.getTime() + 10000); // 10 seconds
        const now = new Date();
        const remaining = Math.max(0, Math.floor((gameStartTime - now) / 1000));
        
        setCountdown(remaining);
        
        if (remaining === 0) {
          setTimerType(null);
        }
      };

      updateCountdown();
      const timer = setInterval(updateCountdown, 100);
      return () => clearInterval(timer);
    }

    // Check if idle timer should be active (arena will auto-delete if empty/1 player)
    if (!arena.is_closed && arena.players?.length <= 1) {
      setTimerType('idle');
      
      const updateCountdown = () => {
        // Idle timers usually expire after 20 seconds of inactivity
        // This would be tracked on the backend
        // For now, we show a visual indicator
        setCountdown(20);
      };

      updateCountdown();
    }

    return () => {
      setCountdown(null);
      setTimerType(null);
    };
  }, [arena?.id, arena?.is_closed, arena?.game_status, arena?.closed_at, arena?.players?.length]);

  return { countdown, timerType };
};

export default useArenaTimer;
