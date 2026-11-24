// "Ask Bobby" side drawer: chat about the current position. Facts come from the engine; the LLM (or template) explains.
import { useEffect, useRef, useState } from "react";
import { explain, loadPersonas, positionFacts, type CoachAnswer } from "../lib/coach";
import { speak, stopSpeaking } from "../lib/tts";
import { useSettings } from "../lib/useSettings";
import type { Persona } from "../bridge/types";

interface Msg { role: "you" | "bobby"; text: string; source?: CoachAnswer["source"]; error?: string }

const QUICK = ["What is the plan here?", "What is the engine's best move and why?", "Who is better?"];

export function usePersonas() {
  const [list, setList] = useState<Persona[]>([]);
  useEffect(() => { let live = true; loadPersonas().then((l) => live && setList(l)).catch(() => {}); return () => { live = false; }; }, []);
  return list;
}

export function PersonaBadge() {
  const s = useSettings();
  const list = usePersonas();
  const p = list.find((x) => x.id === s.persona);
  const name = s.persona === "custom" ? "Custom coach" : p?.name ?? s.persona;
  return <span className="persona-badge" title={p?.tagline ?? ""}><span className={"pglyph pg-" + s.persona} aria-hidden="true">{name.replace(/^The /, "")[0]}</span>{name}</span>;
}

export function CoachDrawer({ fen, context, onClose }: { fen: string; context?: Record<string, unknown>; onClose: () => void }) {
  const s = useSettings();
  const personas = usePersonas();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const list = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => { input.current?.focus(); const k = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); }; addEventListener("keydown", k); return () => { removeEventListener("keydown", k); stopSpeaking(); }; }, [onClose]);
  useEffect(() => { list.current?.scrollTo({ top: list.current.scrollHeight }); }, [msgs, busy]);
  const hasLlm = s.llm.provider === "custom" ? !!s.llm.baseUrl.trim() : !!s.llm.key.trim();

  const ask = async (question: string) => {
    const text = question.trim();
    if (!text || busy) return;
    setMsgs((m) => [...m, { role: "you", text }]); setQ(""); setBusy(true);
    try {
      const facts = await positionFacts(fen, text, context);
      const a = await explain(facts, "chat");
      setMsgs((m) => [...m, { role: "bobby", text: a.text, source: a.source, error: a.error }]);
    } catch (e) {
      setMsgs((m) => [...m, { role: "bobby", text: "", error: (e as Error).message }]);
    } finally { setBusy(false); }
  };

  return (
    <aside className="drawer" role="dialog" aria-label="Ask Bobby" aria-modal="false">
      <div className="drawer-h">
        <h2>Ask Bobby</h2>
        <PersonaBadge />
        <button className="icon-btn" onClick={onClose} aria-label="Close coach">×</button>
      </div>
      <p className="muted small">{hasLlm ? `Answers from ${s.llm.provider} (${s.llm.model}), grounded in engine facts only.` : "No API key: answers are templates built from engine facts. Add a key in Settings for free-form answers."}</p>
      <div className="chat" ref={list} aria-live="polite">
        {!msgs.length ? <p className="muted small">Ask about the position on the board. Bobby only explains what the engine reports.</p> : null}
        {msgs.map((m, i) => (
          <div key={i} className={"msg " + m.role} data-source={m.source}>
            {m.text ? <p>{m.text}</p> : null}
            {m.error ? <p className="err small">{m.error}{m.text ? " (showing the template answer instead)" : ""}</p> : null}
            {m.role === "bobby" && m.text ? (
              <div className="msg-f"><small className="muted">{m.source === "llm" ? "LLM" : m.source === "cache" ? "LLM (cached)" : "template"}</small>
                <button className="textlink" onClick={() => speak(m.text, s.persona, personas.find((p) => p.id === s.persona), true)}>Speak</button></div>
            ) : null}
          </div>
        ))}
        {busy ? <p className="muted small think">Bobby is looking at the position…</p> : null}
      </div>
      <div className="quick">{QUICK.map((x) => <button key={x} className="chip" disabled={busy} onClick={() => void ask(x)}>{x}</button>)}</div>
      <form className="typed" onSubmit={(e) => { e.preventDefault(); void ask(q); }}>
        <label className="sr-only" htmlFor="coach-q">Question</label>
        <input id="coach-q" ref={input} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask about this position" autoComplete="off" />
      </form>
    </aside>
  );
}
