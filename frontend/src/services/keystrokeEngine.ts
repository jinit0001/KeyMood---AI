import type { KeystrokeFeatures, MoodLabel } from "../types";

/** Tracks raw key-timing events in memory only. No characters are ever stored. */
export class KeystrokeTracker {
  private keyDownTimes: Map<string, number> = new Map();
  private holdTimes: number[] = [];
  private interKeyDelays: number[] = [];
  private lastKeyUpAt: number | null = null;
  private startedAt: number | null = null;
  private keyCount = 0;
  private errorCount = 0; // backspace/delete presses

  onKeyDown(key: string) {
    const now = performance.now();
    if (this.startedAt === null) this.startedAt = now;
    if (!this.keyDownTimes.has(key)) {
      this.keyDownTimes.set(key, now);
    }
    if (this.lastKeyUpAt !== null) {
      const delay = now - this.lastKeyUpAt;
      if (delay > 0 && delay < 5000) this.interKeyDelays.push(delay);
    }
    this.keyCount += 1;
    if (key === "Backspace" || key === "Delete") this.errorCount += 1;
  }

  onKeyUp(key: string) {
    const now = performance.now();
    const downAt = this.keyDownTimes.get(key);
    if (downAt !== undefined) {
      const hold = now - downAt;
      if (hold > 0 && hold < 2000) this.holdTimes.push(hold);
      this.keyDownTimes.delete(key);
    }
    this.lastKeyUpAt = now;
  }

  reset() {
    this.keyDownTimes.clear();
    this.holdTimes = [];
    this.interKeyDelays = [];
    this.lastKeyUpAt = null;
    this.startedAt = null;
    this.keyCount = 0;
    this.errorCount = 0;
  }

  getFeatures(): KeystrokeFeatures {
    const avgHold = average(this.holdTimes);
    const avgDelay = average(this.interKeyDelays);
    const elapsedMinutes = this.startedAt ? (performance.now() - this.startedAt) / 60000 : 0;
    const wpm = elapsedMinutes > 0 ? this.keyCount / 5 / elapsedMinutes : 0;
    const errorRate = this.keyCount > 0 ? this.errorCount / this.keyCount : 0;
    const delayVariance = variance(this.interKeyDelays, avgDelay);
    // Stability: lower variance -> higher stability score (0-100)
    const rhythmStability = Math.max(0, 100 - Math.min(100, delayVariance / 20));

    return {
      typingSpeedWpm: round(wpm),
      avgHoldTimeMs: round(avgHold),
      interKeyDelayMs: round(avgDelay),
      errorRate: Number(errorRate.toFixed(3)),
      rhythmStability: round(rhythmStability),
    };
  }
}

export function inferMood(features: KeystrokeFeatures): { mood: MoodLabel; confidence: number } {
  const { typingSpeedWpm, interKeyDelayMs, errorRate, rhythmStability } = features;

  if (errorRate >= 0.16 || rhythmStability < 35) {
    return { mood: "Stressed", confidence: clampConfidence(70 + errorRate * 100) };
  }
  if (interKeyDelayMs >= 260 || typingSpeedWpm < 20) {
    return { mood: "Tired", confidence: clampConfidence(65 + (300 - interKeyDelayMs) / 10) };
  }
  if (typingSpeedWpm >= 55 && errorRate < 0.05 && rhythmStability >= 70) {
    return { mood: "Happy", confidence: clampConfidence(75 + rhythmStability / 5) };
  }
  if (typingSpeedWpm >= 40 && rhythmStability >= 60) {
    return { mood: "Focused", confidence: clampConfidence(70 + rhythmStability / 5) };
  }
  return { mood: "Calm", confidence: clampConfidence(60 + rhythmStability / 4) };
}

function clampConfidence(v: number): number {
  return Math.max(50, Math.min(97, Math.round(v)));
}

function average(arr: number[]): number {
  if (arr.length === 0) return 0;
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

function variance(arr: number[], mean: number): number {
  if (arr.length === 0) return 0;
  return arr.reduce((a, b) => a + (b - mean) ** 2, 0) / arr.length;
}

function round(v: number): number {
  return Math.round(v * 10) / 10;
}
