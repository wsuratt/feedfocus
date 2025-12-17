/**
 * Dwell time service - batches and sends dwell events to backend
 *
 * Batching strategy:
 * - Buffer events for up to 2 seconds
 * - Send batch when buffer reaches 10 events or 2s elapsed
 * - Use sendBeacon on unload for reliability
 */

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const BATCH_INTERVAL_MS = 2000;
const MAX_BATCH_SIZE = 10;

interface DwellEvent {
  insightId: string;
  dwellMs: number;
}

let dwellBuffer: DwellEvent[] = [];
let flushTimeout: NodeJS.Timeout | null = null;

/**
 * Add dwell event to buffer and flush if needed
 */
export function flushDwellEvent(insightId: string, dwellMs: number) {
  dwellBuffer.push({ insightId, dwellMs });

  // Flush immediately if buffer is full
  if (dwellBuffer.length >= MAX_BATCH_SIZE) {
    flushDwellBuffer();
  } else {
    // Schedule flush if not already scheduled
    if (!flushTimeout) {
      flushTimeout = setTimeout(flushDwellBuffer, BATCH_INTERVAL_MS);
    }
  }
}

/**
 * Send buffered dwell events to backend
 */
async function flushDwellBuffer() {
  if (dwellBuffer.length === 0) return;

  const eventsToSend = [...dwellBuffer];
  dwellBuffer = [];

  // Clear timeout if exists
  if (flushTimeout) {
    clearTimeout(flushTimeout);
    flushTimeout = null;
  }

  try {
    // Get JWT token from localStorage
    const token = localStorage.getItem('authToken');

    await fetch(`${API_URL}/api/feed/dwell-batch`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ events: eventsToSend }),
    });
  } catch (error) {
    console.error('Failed to send dwell batch:', error);
    // Don't retry - dwell time is best-effort
  }
}

/**
 * Flush on page unload using sendBeacon for reliability
 * Note: sendBeacon doesn't support custom headers, so auth relies on cookies
 */
function flushOnUnload() {
  if (dwellBuffer.length === 0) return;

  const blob = new Blob(
    [JSON.stringify({ events: dwellBuffer })],
    { type: 'application/json' }
  );

  navigator.sendBeacon(`${API_URL}/api/feed/dwell-batch`, blob);
  dwellBuffer = [];
}

// Register unload handlers
if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', flushOnUnload);
  window.addEventListener('pagehide', flushOnUnload);
}
