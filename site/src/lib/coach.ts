// Coach layer (PLAN section 7). Engine facts -> Python coach_prompt -> chosen LLM provider (bring your own key).
// No key: Python template_explanation. Answers are cached per position + persona + mode + question.
// The LLM never sees anything but the facts; the persona changes tone only.
import { Chess } from "chess.js";
import { analysisEngine, toWhite } from "../bridge/engine";
import { py } from "../bridge/py";
import { db, settings, store, type LlmSettings, type Provider, type Settings } from "../bridge/storage";
import type { CoachMode, Eval, MoveClass, Persona } from "../bridge/types";
import { data } from "./data";
import { tryMove } from "./chess";
import { speak } from "./tts";

export const PROVIDERS: { id: Provider; label: string; url: string; note: string }[] = [
  { id: "anthropic", label: "Anthropic", url: "https://api.anthropic.com/v1/messages", note: "Sent with the anthropic-dangerous-direct-browser-access header so the browser may call it directly." },
  { id: "openai", label: "OpenAI", url: "https://api.openai.com/v1/chat/completions", note: "" },
  { id: "google", label: "Google (Gemini)", url: "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", note: "" },
  { id: "openrouter", label: "OpenRouter", url: "https://openrouter.ai/api/v1/chat/completions", note: "" },
  { id: "custom", label: "Custom (OpenAI-compatible)", url: "", note: "Base URL ending before /chat/completions, e.g. http://localhost:11434/v1. The server must allow browser (CORS) requests." },
];

// ---------- personas ----------
let personaList: Promise<Persona[]> | null = null;
export const loadPersonas = () => (personaList ??= py.personas().catch((e) => { personaList = null; throw e; }));
export function personaArg(s: Settings = settings.get()): string | { custom: string } {
  return s.persona === "custom" ? { custom: s.customCoach.trim() || "Friendly and clear." } : s.persona;
}

// ---------- facts ----------
const sanLine = (fen: string, pv: string[], n = 6) => {
  const c = new Chess(fen); const out: string[] = [];
  for (const u of pv.slice(0, n)) { const m = tryMove(c, u.slice(0, 2), u.slice(2, 4), u[4]); if (!m) break; out.push(m.san); }
  return out;
};

async function topTags(n = 3): Promise<string[]> {
  const w = (await store.getWeakness()) as { tags?: Record<string, { score?: number }> } | null;
  return Object.entries(w?.tags ?? {}).filter(([t]) => !t.startsWith("phase_")).sort((a, b) => (b[1].score ?? 0) - (a[1].score ?? 0)).slice(0, n).map(([t]) => t);
}

async function cardsFor(tags: string[], n = 2) {
  if (!tags.length) return [];
  const cards = await data.cards().catch(() => []);
  return cards.filter((c) => c.tags.some((t) => tags.includes(t))).slice(0, n).map((c) => ({ title: c.title, text: c.text }));
}

const factsMemo = new Map<string, Promise<Record<string, unknown>>>();
/** Facts about a position for chat ("ask Bobby"). Memoised per position + question, so a persona swap reuses identical facts. */
export function positionFacts(fen: string, question: string, extra: Record<string, unknown> = {}): Promise<Record<string, unknown>> {
  const k = JSON.stringify([fen, question, extra]);
  let p = factsMemo.get(k);
  if (!p) {
    p = computePositionFacts(fen, question, extra);
    p.catch(() => factsMemo.delete(k));
    factsMemo.set(k, p);
    if (factsMemo.size > 200) factsMemo.delete(factsMemo.keys().next().value as string);
  }
  return p;
}
async function computePositionFacts(fen: string, question: string, extra: Record<string, unknown>): Promise<Record<string, unknown>> {
  const r = await analysisEngine().analyse(fen, { depth: 14, multipv: 2, movetimeMs: 1500, channel: "coach" });
  const lines = r.lines.map((l) => ({ eval: toWhite(l, fen), line: sanLine(fen, l.pv) }));
  const tags = await topTags();
  return {
    fen, side_to_move: fen.split(" ")[1] === "b" ? "Black" : "White", question,
    eval: lines[0]?.eval ?? null, best_line: lines[0]?.line ?? [], other_lines: lines.slice(1),
    weakness_tags: tags, knowledge_cards: await cardsFor(tags), ...extra,
  };
}

/** Facts about one played move (Review "explain"). */
export async function moveFacts(m: { fen_before: string; san: string; eval_before: Eval; eval_after: Eval; best_pv?: string[]; best_uci: string | null }, cls: MoveClass | undefined, tags: string[] = []) {
  const best = m.best_pv?.length ? m.best_pv : m.best_uci ? [m.best_uci] : [];
  const t = tags.length ? tags : await topTags();
  return {
    fen: m.fen_before, move: m.san, class: cls ?? null, eval_before: m.eval_before, eval_after: m.eval_after,
    best_line: sanLine(m.fen_before, best), tags: t, knowledge_cards: await cardsFor(t),
  };
}

// ---------- providers ----------
export class CoachError extends Error { constructor(msg: string, public kind: "network" | "http" | "config" | "empty") { super(msg); } }

async function post(url: string, headers: Record<string, string>, body: unknown): Promise<unknown> {
  let res: Response;
  try {
    res = await fetch(url, { method: "POST", headers: { "content-type": "application/json", ...headers }, body: JSON.stringify(body) });
  } catch (e) {
    throw new CoachError(`Could not reach the provider (network or CORS blocked the browser request): ${(e as Error).message}`, "network");
  }
  const text = await res.text();
  let json: unknown = null;
  try { json = JSON.parse(text); } catch { /* not JSON */ }
  if (!res.ok) {
    const j = json as { error?: { message?: string } | string; message?: string } | null;
    const msg = typeof j?.error === "string" ? j.error : j?.error?.message ?? j?.message ?? text.slice(0, 200);
    throw new CoachError(`Provider error ${res.status}: ${msg}`, "http");
  }
  return json;
}

export async function complete(llm: LlmSettings, system: string, user: string, maxTokens = 400): Promise<string> {
  const model = llm.model.trim();
  if (!model) throw new CoachError("Choose a model in Settings.", "config");
  if (llm.provider !== "custom" && !llm.key.trim()) throw new CoachError("Add an API key in Settings.", "config");
  let out = "";
  if (llm.provider === "anthropic") {
    const j = (await post("https://api.anthropic.com/v1/messages", {
      "x-api-key": llm.key.trim(), "anthropic-version": "2023-06-01", "anthropic-dangerous-direct-browser-access": "true",
    }, { model, max_tokens: maxTokens, system, messages: [{ role: "user", content: user }] })) as { content?: { type: string; text?: string }[] };
    out = (j.content ?? []).filter((c) => c.type === "text").map((c) => c.text ?? "").join("");
  } else if (llm.provider === "google") {
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`;
    const j = (await post(url, { "x-goog-api-key": llm.key.trim() }, {
      systemInstruction: { parts: [{ text: system }] }, contents: [{ role: "user", parts: [{ text: user }] }], generationConfig: { maxOutputTokens: maxTokens },
    })) as { candidates?: { content?: { parts?: { text?: string }[] } }[] };
    out = (j.candidates?.[0]?.content?.parts ?? []).map((p) => p.text ?? "").join("");
  } else {
    const url = llm.provider === "openai" ? "https://api.openai.com/v1/chat/completions"
      : llm.provider === "openrouter" ? "https://openrouter.ai/api/v1/chat/completions"
      : llm.baseUrl.trim().replace(/\/+$/, "") + "/chat/completions";
    if (llm.provider === "custom" && !/^https?:\/\//.test(llm.baseUrl.trim())) throw new CoachError("Set a base URL (http or https) for the custom provider.", "config");
    const headers: Record<string, string> = llm.key.trim() ? { authorization: `Bearer ${llm.key.trim()}` } : {};
    if (llm.provider === "openrouter") headers["x-title"] = "Bobby chess coach";
    const j = (await post(url, headers, { model, max_tokens: maxTokens, messages: [{ role: "system", content: system }, { role: "user", content: user }] })) as { choices?: { message?: { content?: string } }[] };
    out = j.choices?.[0]?.message?.content ?? "";
  }
  out = out.trim();
  if (!out) throw new CoachError("The provider returned an empty answer.", "empty");
  return out;
}

// ---------- explain ----------
export interface CoachAnswer { text: string; source: "llm" | "template" | "cache"; error?: string; prompt?: { system: string; user: string } }

async function hash(s: string): Promise<string> {
  if (!globalThis.crypto?.subtle) { let h = 5381; for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0; return "d" + (h >>> 0).toString(16) + s.length; }
  const b = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(b)].slice(0, 16).map((x) => x.toString(16).padStart(2, "0")).join("");
}

/** Explain facts in the current persona. Speaks the answer when voice output is on. */
export async function explain(facts: Record<string, unknown>, mode: CoachMode, opts: { speakIt?: boolean } = {}): Promise<CoachAnswer> {
  const s = settings.get();
  const persona = personaArg(s);
  const hasLlm = s.llm.provider === "custom" ? !!s.llm.baseUrl.trim() : !!s.llm.key.trim();
  let ans: CoachAnswer;
  if (!hasLlm) {
    ans = { text: await py.template_explanation(facts, mode), source: "template" };
  } else {
    const prompt = await py.coach_prompt(persona, facts, mode);
    const key = await hash(JSON.stringify([s.llm.provider, s.llm.model, prompt.system, prompt.user]));
    const hit = await db.coachCache.get(key).catch(() => undefined);
    if (hit) ans = { text: hit.text, source: "cache", prompt };
    else {
      try {
        const text = await complete(s.llm, prompt.system, prompt.user);
        await db.coachCache.put({ key, text, at: new Date().toISOString() }).catch(() => {});
        ans = { text, source: "llm", prompt };
      } catch (e) {
        const fallbackText = await py.template_explanation(facts, mode).catch(() => "");
        ans = { text: fallbackText, source: "template", error: (e as Error).message, prompt };
      }
    }
  }
  if (opts.speakIt !== false && ans.text) {
    const list = await loadPersonas().catch(() => [] as Persona[]);
    speak(ans.text, s.persona, list.find((p) => p.id === s.persona));
  }
  return ans;
}
