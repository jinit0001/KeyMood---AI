import { useRef, useState } from "react";
import { KeystrokeTracker, inferMood } from "../services/keystrokeEngine";
import { useAppStore } from "../state/appStore";
import { MOOD_COLORS } from "../services/mockData";
import type { KeystrokeFeatures, MoodLabel, RiskAssessment } from "../types";
import RiskBanner from "../components/RiskBanner";

export default function LiveMood() {
  const trackerRef = useRef(new KeystrokeTracker());
  const [monitoring, setMonitoring] = useState(false);
  const [features, setFeatures] = useState<KeystrokeFeatures | null>(null);
  const [result, setResult] = useState<{ mood: MoodLabel; confidence: number } | null>(null);
  const [risk, setRisk] = useState<RiskAssessment | null>(null);
  const intervalRef = useRef<number | null>(null);
  const recordMoodReading = useAppStore((s) => s.recordMoodReading);

  const start = () => {
    trackerRef.current.reset();
    setMonitoring(true);
    setResult(null);
    setRisk(null);
    intervalRef.current = window.setInterval(() => {
      const f = trackerRef.current.getFeatures();
      setFeatures(f);
      setResult(inferMood(f));
    }, 500);
  };

  const stop = () => {
    setMonitoring(false);
    if (intervalRef.current) window.clearInterval(intervalRef.current);
    const f = trackerRef.current.getFeatures();
    const inferred = inferMood(f);
    setFeatures(f);
    setResult(inferred);
    const assessment = recordMoodReading({
      mood: inferred.mood,
      confidence: inferred.confidence,
      timestamp: new Date().toISOString(),
      features: f,
    });
    setRisk(assessment);
  };

  return (
    <div>
      <div className="page-header">
        <h1>Live Mood Detection</h1>
        <p>KeyMood is analyzing your typing patterns...</p>
      </div>

      <div className="grid grid-2">
        <div className="card">
          <label htmlFor="typing-area">Start typing here...</label>
          <textarea
            id="typing-area"
            className="typing-area"
            placeholder="Type anything — a note, a message, your thoughts..."
            onKeyDown={(e) => monitoring && trackerRef.current.onKeyDown(e.key)}
            onKeyUp={(e) => monitoring && trackerRef.current.onKeyUp(e.key)}
          />
          <p style={{ fontSize: "0.78rem", color: "var(--text-faint)", marginTop: 8 }}>
            Your actual text is not stored. KeyMood analyzes typing behavior rather than what you type.
          </p>
          <div style={{ marginTop: 14, display: "flex", gap: 8 }}>
            {!monitoring ? (
              <button className="btn btn-primary" onClick={start}>Start monitoring</button>
            ) : (
              <button className="btn btn-danger" onClick={stop}>Stop monitoring</button>
            )}
          </div>
        </div>

        <div className="card">
          <div className="card-title">Detected state</div>
          {result ? (
            <div className="mood-display">
              <span className="pulse-dot" style={{ background: MOOD_COLORS[result.mood] }} />
              <div className="label" style={{ color: MOOD_COLORS[result.mood] }}>{result.mood.toUpperCase()}</div>
              <div className="confidence">{result.confidence}% confidence</div>
            </div>
          ) : (
            <div className="empty-state">Start monitoring to see a live reading.</div>
          )}

          {features && (
            <div style={{ marginTop: 10 }}>
              <div className="feature-row"><span>Typing speed</span><span className="value">{features.typingSpeedWpm} WPM</span></div>
              <div className="feature-row"><span>Avg hold time</span><span className="value">{features.avgHoldTimeMs} ms</span></div>
              <div className="feature-row"><span>Inter-key delay</span><span className="value">{features.interKeyDelayMs} ms</span></div>
              <div className="feature-row"><span>Error rate</span><span className="value">{(features.errorRate * 100).toFixed(1)}%</span></div>
              <div className="feature-row"><span>Rhythm stability</span><span className="value">{features.rhythmStability}</span></div>
            </div>
          )}
        </div>
      </div>

      {risk && <div style={{ marginTop: 16 }}><RiskBanner risk={risk} /></div>}
    </div>
  );
}
