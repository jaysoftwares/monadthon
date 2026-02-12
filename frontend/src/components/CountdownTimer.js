import React, { useState, useEffect, useRef } from 'react';
import { Clock, Timer } from 'lucide-react';

/**
 * CountdownTimer - Displays a live countdown to a target timestamp
 *
 * Props:
 * - targetTime: ISO timestamp string to count down to
 * - label: Text label above the timer (e.g., "Next Tournament In")
 * - onComplete: Callback when countdown reaches zero
 * - variant: "banner" | "inline" | "card" (styling variant)
 * - showIcon: Whether to show the clock icon (default true)
 * - completedText: Text to show when countdown reaches zero
 */
const CountdownTimer = ({
  targetTime,
  label = 'Countdown',
  onComplete,
  variant = 'inline',
  showIcon = true,
  completedText = 'Now',
}) => {
  const [timeLeft, setTimeLeft] = useState(null);
  const completedRef = useRef(false);
  const targetRef = useRef(null);

  useEffect(() => {
    if (!targetTime) {
      setTimeLeft(null);
      completedRef.current = false;
      targetRef.current = null;
      return;
    }

    if (targetRef.current !== targetTime) {
      targetRef.current = targetTime;
      completedRef.current = false;
    }

    const calculateTimeLeft = () => {
      const target = new Date(targetTime).getTime();
      const now = Date.now();
      const diff = Math.max(0, Math.floor((target - now) / 1000));
      return diff;
    };

    const notifyCompleteOnce = () => {
      if (!completedRef.current) {
        completedRef.current = true;
        if (onComplete) onComplete();
      }
    };

    const initialRemaining = calculateTimeLeft();
    setTimeLeft(initialRemaining);
    if (initialRemaining <= 0) {
      notifyCompleteOnce();
    }

    const interval = setInterval(() => {
      const remaining = calculateTimeLeft();
      setTimeLeft(remaining);

      if (remaining <= 0) {
        clearInterval(interval);
        notifyCompleteOnce();
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [targetTime, onComplete]);

  if (timeLeft === null || timeLeft === undefined) return null;

  const hours = Math.floor(timeLeft / 3600);
  const minutes = Math.floor((timeLeft % 3600) / 60);
  const seconds = timeLeft % 60;

  const formatDigit = (n) => String(n).padStart(2, '0');

  const timeDisplay = hours > 0
    ? `${formatDigit(hours)}:${formatDigit(minutes)}:${formatDigit(seconds)}`
    : `${formatDigit(minutes)}:${formatDigit(seconds)}`;

  const isUrgent = timeLeft < 300; // Less than 5 minutes

  if (variant === 'banner') {
    return (
      <div
        className={`rounded-xl p-4 border ${
          isUrgent
            ? 'bg-orange-50 border-orange-200'
            : 'bg-gradient-to-r from-purple-50 to-indigo-50 border-purple-200'
        }`}
        data-testid="countdown-banner"
      >
        <div className="flex items-center justify-center gap-3">
          {showIcon && (
            <Timer className={`w-5 h-5 ${isUrgent ? 'text-orange-500' : 'text-[#836EF9]'}`} />
          )}
          <div className="text-center">
            <p className={`text-sm font-medium ${isUrgent ? 'text-orange-600' : 'text-gray-600'}`}>
              {label}
            </p>
            <p
              className={`font-heading text-3xl font-bold tabular-nums ${
                isUrgent ? 'text-orange-600' : 'text-[#836EF9]'
              }`}
            >
              {timeLeft <= 0 ? completedText : timeDisplay}
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (variant === 'card') {
    return (
      <div
        className={`bg-white rounded-xl p-5 border shadow-card ${
          isUrgent ? 'border-orange-200' : 'border-gray-100'
        }`}
        data-testid="countdown-card"
      >
        <div className={`flex items-center gap-2 text-sm mb-2 ${isUrgent ? 'text-orange-500' : 'text-gray-500'}`}>
          {showIcon && <Clock className="w-4 h-4" />}
          {label}
        </div>
        <p
          className={`font-heading text-2xl font-bold tabular-nums ${
            isUrgent ? 'text-orange-600' : 'text-gray-900'
          }`}
        >
          {timeLeft <= 0 ? completedText : timeDisplay}
        </p>
      </div>
    );
  }

  // inline variant (default)
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-sm font-medium tabular-nums ${
        isUrgent ? 'text-orange-600' : 'text-[#836EF9]'
      }`}
      data-testid="countdown-inline"
    >
      {showIcon && <Clock className="w-3.5 h-3.5" />}
      {timeLeft <= 0 ? completedText : timeDisplay}
    </span>
  );
};

export default CountdownTimer;
