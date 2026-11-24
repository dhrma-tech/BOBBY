// Spoken coach output via the Web Speech API (speechSynthesis). Output only; no speech recognition.
import { settings, type VoicePrefs } from "../bridge/storage";
import type { Persona } from "../bridge/types";

export const ttsAvailable = () => typeof window !== "undefined" && "speechSynthesis" in window && typeof SpeechSynthesisUtterance !== "undefined";

export function voices(): SpeechSynthesisVoice[] {
  if (!ttsAvailable()) return [];
  try { return speechSynthesis.getVoices(); } catch { return []; }
}

const FEMALE = /female|woman|samantha|victoria|karen|zira|susan|serena|tessa|moira|fiona|allison|ava|joanna|salli|kimberly|google uk english female/i;
const MALE = /\bmale\b|man\b|daniel|alex|fred|david|mark|george|james|oliver|thomas|google uk english male/i;

function pickVoice(prefs: VoicePrefs | undefined, persona: Persona | undefined): SpeechSynthesisVoice | null {
  const vs = voices();
  if (!vs.length) return null;
  if (prefs?.voiceURI) { const v = vs.find((x) => x.voiceURI === prefs.voiceURI); if (v) return v; }
  const lang = (navigator.language || "en").slice(0, 2);
  const local = vs.filter((v) => v.lang.toLowerCase().startsWith(lang));
  const pool = local.length ? local : vs;
  const g = persona?.voice.preferGender;
  const re = g === "female" ? FEMALE : g === "male" ? MALE : null;
  return (re && pool.find((v) => re.test(v.name) && !(g === "male" && FEMALE.test(v.name)))) || pool.find((v) => v.default) || pool[0];
}

export function voicePrefsFor(personaId: string, persona?: Persona): VoicePrefs {
  const saved = settings.get().voice.per[personaId];
  return { rate: saved?.rate ?? persona?.voice.rate ?? 1, pitch: saved?.pitch ?? persona?.voice.pitch ?? 1, voiceURI: saved?.voiceURI ?? "" };
}

/** Speak text in the persona's voice when voice output is on (or when forced, for the Settings "test" button). */
export function speak(text: string, personaId: string, persona?: Persona, force = false): boolean {
  if (!ttsAvailable() || !text.trim()) return false;
  if (!force && !settings.get().voice.enabled) return false;
  const p = voicePrefsFor(personaId, persona);
  try {
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text.slice(0, 1200));
    u.rate = Math.max(0.5, Math.min(2, p.rate));
    u.pitch = Math.max(0, Math.min(2, p.pitch));
    const v = pickVoice(p, persona);
    if (v) { u.voice = v; u.lang = v.lang; }
    speechSynthesis.speak(u);
    return true;
  } catch { return false; }
}

export function stopSpeaking() { if (ttsAvailable()) try { speechSynthesis.cancel(); } catch { /* ignore */ } }
