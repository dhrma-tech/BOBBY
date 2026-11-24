// Settings dialog: coach persona + voice, LLM provider/key (on-device only), board look, play options, data.
import { useEffect, useRef, useState } from "react";
import { Dialog } from "./Dialog";
import { useSettings } from "../lib/useSettings";
import { DEFAULT_MODELS, exportAll, importAll, resetAll, settings, type BoardTheme, type PieceSet, type Provider, type Theme } from "../bridge/storage";
import { BOARD_THEMES } from "../components/Board";
import { toast } from "../components/Toast";
import { useBridgeStatus } from "../bridge/py";
import { usePersonas } from "../components/CoachDrawer";
import { PROVIDERS, complete } from "../lib/coach";
import { speak, ttsAvailable, voicePrefsFor, voices } from "../lib/tts";

type Toggle = "coordinates" | "sounds" | "legalHighlights" | "takebacks" | "hints" | "showEval" | "focusMode";

export function SettingsDialog({ onClose }: { onClose: () => void }) {
  const s = useSettings();
  const bs = useBridgeStatus();
  const personas = usePersonas();
  const file = useRef<HTMLInputElement>(null);
  const [vlist, setVlist] = useState<SpeechSynthesisVoice[]>(voices());
  const [showKey, setShowKey] = useState(false);
  const [testing, setTesting] = useState("");
  useEffect(() => {
    if (!ttsAvailable()) return;
    const f = () => setVlist(voices());
    speechSynthesis.addEventListener?.("voiceschanged", f);
    return () => speechSynthesis.removeEventListener?.("voiceschanged", f);
  }, []);

  const toggle = (k: Toggle, label: string) => (
    <label className="check"><input type="checkbox" checked={s[k]} onChange={(e) => settings.set({ [k]: e.target.checked })} /> {label}</label>
  );
  const persona = personas.find((p) => p.id === s.persona);
  const vp = voicePrefsFor(s.persona, persona);
  const setVoice = (patch: Partial<typeof vp>) => settings.set({ voice: { ...s.voice, per: { ...s.voice.per, [s.persona]: { ...vp, ...patch } } } });
  const setLlm = (patch: Partial<typeof s.llm>) => settings.set({ llm: { ...s.llm, ...patch } });

  const doExport = async () => {
    try {
      const blob = new Blob([await exportAll()], { type: "application/json" });
      const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: `bobby-export-${new Date().toISOString().slice(0, 10)}.json` });
      a.click(); URL.revokeObjectURL(a.href); toast("Exported (API key not included)");
    } catch (e) { toast("Export failed: " + (e as Error).message); }
  };
  const doImport = async (f: File) => {
    try { await importAll(await f.text()); toast("Imported. Reloading"); setTimeout(() => location.reload(), 600); }
    catch (e) { toast("Import failed: " + (e as Error).message.slice(0, 120)); }
  };
  const testLlm = async () => {
    setTesting("Testing…");
    try { const t = await complete(s.llm, "Reply with the single word: ready", "ping", 10); setTesting(`OK: ${t.slice(0, 40)}`); }
    catch (e) { setTesting((e as Error).message); }
  };
  const prov = PROVIDERS.find((p) => p.id === s.llm.provider)!;

  return (
    <Dialog title="Settings" onClose={onClose} wide>
      <div className="set-grid">
        <fieldset className="set">
          <legend>Coach</legend>
          <div className="personas" role="radiogroup" aria-label="Coach persona">
            {[...personas, { id: "custom", name: "Custom coach", tagline: "Describe any tone you like." }].map((p) => (
              <label key={p.id} className={"persona" + (s.persona === p.id ? " on" : "")}>
                <input type="radio" name="persona" value={p.id} checked={s.persona === p.id} onChange={() => settings.set({ persona: p.id })} />
                <span className={"pglyph pg-" + p.id} aria-hidden="true">{p.name.replace(/^The /, "")[0]}</span>
                <span><strong>{p.name}</strong><small className="muted block">{p.tagline}</small></span>
              </label>
            ))}
          </div>
          {s.persona === "custom" ? (
            <label className="stack">Custom coach tone <textarea rows={3} maxLength={400} value={s.customCoach} onChange={(e) => settings.set({ customCoach: e.target.value })} placeholder="e.g. Calm and patient, uses football metaphors" />
              <small className="muted">Tone only. Bobby still explains engine facts and nothing else.</small></label>
          ) : null}
          <p className="muted small">Personas change how Bobby talks, never how it plays or what it says is true.</p>
        </fieldset>

        <fieldset className="set">
          <legend>Voice</legend>
          {ttsAvailable() ? <>
            <label className="check"><input type="checkbox" checked={s.voice.enabled} onChange={(e) => settings.set({ voice: { ...s.voice, enabled: e.target.checked } })} /> Speak coach answers aloud</label>
            <p className="muted small">Settings below are saved for {s.persona === "custom" ? "the custom coach" : persona?.name ?? s.persona}.</p>
            <label>Voice <select value={vp.voiceURI} onChange={(e) => setVoice({ voiceURI: e.target.value })} aria-label="System voice">
              <option value="">Automatic</option>{vlist.map((v) => <option key={v.voiceURI} value={v.voiceURI}>{v.name} ({v.lang})</option>)}</select></label>
            <label>Rate <input type="range" min={0.5} max={2} step={0.05} value={vp.rate} onChange={(e) => setVoice({ rate: +e.target.value })} aria-label="Speech rate" /> <output>{vp.rate.toFixed(2)}</output></label>
            <label>Pitch <input type="range" min={0} max={2} step={0.05} value={vp.pitch} onChange={(e) => setVoice({ pitch: +e.target.value })} aria-label="Speech pitch" /> <output>{vp.pitch.toFixed(2)}</output></label>
            <div className="btnrow"><button className="btn" onClick={() => speak("Knight to f3. Develop a piece and control the centre.", s.persona, persona, true)}>Test voice</button></div>
          </> : <p className="muted small">This browser has no speech synthesis.</p>}
        </fieldset>

        <fieldset className="set">
          <legend>AI provider (optional)</legend>
          <p className="warnbox small" role="note">Your API key is stored only in this browser (localStorage) and is sent only to the provider you choose. It is not included in exports. Anyone with access to this browser profile can read it. Use a key with a spending limit.</p>
          <label>Provider <select value={s.llm.provider} onChange={(e) => { const p = e.target.value as Provider; setLlm({ provider: p, model: s.llm.model && s.llm.provider === p ? s.llm.model : DEFAULT_MODELS[p] }); }} aria-label="Provider">
            {PROVIDERS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}</select></label>
          {s.llm.provider === "custom" ? <label>Base URL <input type="text" value={s.llm.baseUrl} onChange={(e) => setLlm({ baseUrl: e.target.value })} placeholder="https://host/v1" aria-label="Base URL" spellCheck={false} /></label> : null}
          <label>Model <input type="text" value={s.llm.model} onChange={(e) => setLlm({ model: e.target.value })} placeholder="model id" aria-label="Model" spellCheck={false} /></label>
          <label>API key <input type={showKey ? "text" : "password"} value={s.llm.key} onChange={(e) => setLlm({ key: e.target.value })} placeholder={s.llm.provider === "custom" ? "optional" : "paste your key"} aria-label="API key" autoComplete="off" spellCheck={false} />
            <button className="chip" type="button" onClick={() => setShowKey(!showKey)}>{showKey ? "Hide" : "Show"}</button></label>
          {prov.note ? <p className="muted small">{prov.note}</p> : null}
          <div className="btnrow">
            <button className="btn" onClick={() => void testLlm()} disabled={!s.llm.model || (!s.llm.key && s.llm.provider !== "custom")}>Test connection</button>
            {s.llm.key ? <button className="btn btn-danger" onClick={() => setLlm({ key: "" })}>Forget key</button> : null}
          </div>
          {testing ? <p className="small muted" role="status">{testing}</p> : null}
          <p className="muted small">Without a key Bobby uses built-in explanations from the engine facts.</p>
        </fieldset>

        <fieldset className="set">
          <legend>Look</legend>
          <label>Theme <select value={s.theme} onChange={(e) => settings.set({ theme: e.target.value as Theme })} aria-label="Theme">
            <option value="auto">Match system</option><option value="light">Light</option><option value="dark">Dark</option></select></label>
          <label>Board <select value={s.boardTheme} onChange={(e) => settings.set({ boardTheme: e.target.value as BoardTheme })} aria-label="Board theme">
            {Object.entries(BOARD_THEMES).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}</select></label>
          <label>Pieces <select value={s.pieceSet} onChange={(e) => settings.set({ pieceSet: e.target.value as PieceSet })} aria-label="Piece set">
            <option value="classic">Classic</option><option value="glyph">Glyphs</option><option value="letters">Letters</option></select></label>
          {toggle("coordinates", "Coordinates")}
          {toggle("legalHighlights", "Show legal moves")}
          {toggle("showEval", "Eval bar")}
        </fieldset>

        <fieldset className="set">
          <legend>Play</legend>
          {toggle("focusMode", "Focus mode: hide eval and coach until the game ends")}
          {toggle("sounds", "Sounds")}
          {toggle("takebacks", "Allow takebacks")}
          {toggle("hints", "Allow hints")}
          <label>Bobby strength offset <input type="range" min={-200} max={200} step={25} value={s.strengthOffset} onChange={(e) => settings.set({ strengthOffset: +e.target.value })} aria-label="Strength offset" /> <output>{s.strengthOffset > 0 ? "+" : ""}{s.strengthOffset}</output></label>
          <p className="muted small">Bobby aims at your estimated rating plus this offset. Applies from the next game.</p>
        </fieldset>

        <fieldset className="set">
          <legend>Your data</legend>
          <p className="muted small">Everything stays on this device. Export to back up or move it.</p>
          <div className="btnrow">
            <button className="btn" onClick={doExport}>Export</button>
            <button className="btn" onClick={() => file.current?.click()}>Import</button>
            <button className="btn btn-danger" onClick={() => { if (confirm("Delete all Bobby data on this device?")) void resetAll(); }}>Reset</button>
            <input ref={file} type="file" accept="application/json" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) void doImport(f); }} />
          </div>
        </fieldset>
        <p className="muted small">Python core: {bs.mode}{bs.fallbackUsed.length ? ` (dev fallback: ${bs.fallbackUsed.join(", ")})` : ""}.</p>
      </div>
    </Dialog>
  );
}
