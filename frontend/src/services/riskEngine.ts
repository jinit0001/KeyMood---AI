import type { MoodLabel, RiskAssessment } from "../types";

const NEGATIVE_MOODS: MoodLabel[] = ["Stressed", "Tired"];

// Pattern-level only, general phrases — used to trigger a supportive
// response and route to real help, not to make a clinical judgement.
const CRISIS_PATTERNS: RegExp[] = [
  /\bkill(ing)? myself\b/i,
  /\bend(ing)? my life\b/i,
  /\bwant(ed)? to die\b/i,
  /\bsuicid(e|al)\b/i,
  /\bhurt(ing)? myself\b/i,
  /\bself[\s-]?harm\b/i,
  /\bno reason to (live|go on)\b/i,
  /\bcan'?t (go on|do this anymore)\b/i,
];

export function textIndicatesCrisis(text: string): boolean {
  if (!text) return false;
  return CRISIS_PATTERNS.some((rx) => rx.test(text));
}

export function assessRisk(recentMoods: MoodLabel[], text?: string): RiskAssessment {
  const reasons: string[] = [];
  let level: RiskAssessment["level"] = "low";

  if (text && textIndicatesCrisis(text)) {
    level = "high";
    reasons.push("Language used suggests significant distress.");
  }

  let streak = 0;
  for (let i = recentMoods.length - 1; i >= 0; i--) {
    if (NEGATIVE_MOODS.includes(recentMoods[i])) streak++;
    else break;
  }
  if (streak >= 4) {
    level = "high";
    reasons.push(`${streak} consecutive low-wellbeing readings in a row.`);
  } else if (streak >= 2) {
    if (level === "low") level = "medium";
    reasons.push(`${streak} consecutive low-wellbeing readings in a row.`);
  }

  if (reasons.length === 0) {
    reasons.push("No significant risk indicators detected.");
  }

  return { level, reasons };
}

export type CountryCode = "IN" | "US" | "UK" | "INTL";

export const COUNTRY_OPTIONS: { code: CountryCode; label: string }[] = [
  { code: "IN", label: "India" },
  { code: "US", label: "United States" },
  { code: "UK", label: "United Kingdom" },
  { code: "INTL", label: "Other / International" },
];

export const CRISIS_RESOURCES_BY_COUNTRY: Record<CountryCode, { label: string; value: string }[]> = {
  IN: [
    { label: "KIRAN Mental Health Helpline (Govt. of India)", value: "1800-599-0019, 24/7" },
    { label: "iCall (TISS)", value: "9152987821, Mon\u2013Sat 8am\u20138pm" },
    { label: "AASRA", value: "+91 98204 66726, 24/7" },
  ],
  US: [
    { label: "988 Suicide & Crisis Lifeline", value: "Call or text 988, 24/7" },
  ],
  UK: [
    { label: "Samaritans", value: "116 123, 24/7" },
  ],
  INTL: [
    { label: "Find A Helpline (international directory)", value: "findahelpline.com" },
  ],
};

export function crisisResourcesFor(country: CountryCode) {
  return CRISIS_RESOURCES_BY_COUNTRY[country];
}

// Kept for any code still importing the old flat list — defaults to India.
export const CRISIS_RESOURCES = CRISIS_RESOURCES_BY_COUNTRY.IN;
