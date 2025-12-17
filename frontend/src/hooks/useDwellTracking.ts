/**
 * Weighted dwell time tracking using IntersectionObserver
 *
 * Tracks actual view time weighted by:
 * - Visibility ratio (0-1)
 * - Position in viewport (center = higher weight)
 */

import { useEffect, useRef, useCallback, useMemo } from 'react';
import { flushDwellEvent } from '../services/dwellService';

interface DwellState {
  startTime: number;
  accumulatedMs: number;
  currentWeight: number;
}

export function useDwellTracking() {
  const dwellStates = useRef<Map<string, DwellState>>(new Map());
  const rafId = useRef<number>();

  const calculateWeight = useCallback((entry: IntersectionObserverEntry): number => {
    const ratio = entry.intersectionRatio;
    const rect = entry.boundingClientRect;
    const viewportHeight = window.innerHeight;

    // Center of element
    const elementCenter = rect.top + rect.height / 2;
    const viewportCenter = viewportHeight / 2;

    // Distance from center (0 at center, 1 at edges)
    const distanceFromCenter = Math.abs(elementCenter - viewportCenter) / (viewportHeight / 2);

    // Position weight: 1.0 at center, 0.5 at edges
    const positionWeight = Math.max(0.5, 1.0 - (distanceFromCenter * 0.5));

    // Combined weight
    return ratio * positionWeight;
  }, []);

  const updateDwellTime = useCallback(() => {
    const now = Date.now();

    dwellStates.current.forEach((state, insightId) => {
      const elapsed = now - state.startTime;
      state.accumulatedMs += elapsed * state.currentWeight;
      state.startTime = now;

      // Flush if accumulated > 2s
      if (state.accumulatedMs >= 2000) {
        flushDwell(insightId);
      }
    });

    rafId.current = requestAnimationFrame(updateDwellTime);
  }, []);

  const flushDwell = useCallback((insightId: string) => {
    const state = dwellStates.current.get(insightId);
    if (!state || state.accumulatedMs < 100) return; // Ignore < 100ms

    flushDwellEvent(insightId, Math.round(state.accumulatedMs));
    dwellStates.current.delete(insightId);
  }, []);

  const observer = useMemo(() => {
    return new IntersectionObserver(
      (entries) => {
        const now = Date.now();

        entries.forEach((entry) => {
          const insightId = entry.target.getAttribute('data-insight-id');
          if (!insightId) return;

          const currentState = dwellStates.current.get(insightId);

          if (entry.isIntersecting) {
            const weight = calculateWeight(entry);

            if (currentState) {
              // Update existing state
              const elapsed = now - currentState.startTime;
              currentState.accumulatedMs += elapsed * currentState.currentWeight;
              currentState.startTime = now;
              currentState.currentWeight = weight;
            } else {
              // Create new state
              dwellStates.current.set(insightId, {
                startTime: now,
                accumulatedMs: 0,
                currentWeight: weight,
              });
            }
          } else {
            // Element left viewport
            if (currentState) {
              const elapsed = now - currentState.startTime;
              currentState.accumulatedMs += elapsed * currentState.currentWeight;
              currentState.currentWeight = 0;

              // Flush if we have meaningful dwell time
              if (currentState.accumulatedMs >= 500) {
                flushDwell(insightId);
              } else {
                // Keep tracking but with 0 weight
                currentState.startTime = now;
              }
            }
          }
        });
      },
      {
        threshold: [0, 0.25, 0.5, 0.75, 1.0], // Multiple thresholds for better tracking
        rootMargin: '0px',
      }
    );
  }, [calculateWeight, flushDwell]);

  // Start RAF loop
  useEffect(() => {
    rafId.current = requestAnimationFrame(updateDwellTime);
    return () => {
      if (rafId.current) {
        cancelAnimationFrame(rafId.current);
      }
    };
  }, [updateDwellTime]);

  // Flush on page hide
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden) {
        dwellStates.current.forEach((_, insightId) => flushDwell(insightId));
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [flushDwell]);

  const trackRef = useCallback((element: HTMLElement | null) => {
    if (element) {
      observer.observe(element);
    }
  }, [observer]);

  // Cleanup: disconnect observer and flush any remaining dwell states
  useEffect(() => {
    return () => {
      observer.disconnect();
      // Flush all remaining tracked insights
      const now = Date.now();
      dwellStates.current.forEach((state, insightId) => {
        const elapsed = now - state.startTime;
        state.accumulatedMs += elapsed * state.currentWeight;
        flushDwell(insightId);
      });
    };
  }, [observer, flushDwell]);

  return { trackRef };
}
