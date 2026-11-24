// Headless smoke test against the production build (vite preview).
// Usage: npm run build && npm run smoke   (CHROME=/path/to/chrome to override the browser)
// Covers: board + focus mode, a game vs Bobby + pipeline, stats after a game, a lesson completing, a puzzle solving,
// settings persisting after reload, persona swap changing only the prompt's tone (mocked LLM), TTS being called (mocked).
import { chromium } from "playwright-core";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const site = join(dirname(fileURLToPath(import.meta.url)), "..");
const PORT = 4179;
const BASE = `http://127.0.0.1:${PORT}/`;
const CHROME = process.env.CHROME || ["/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser"].find(existsSync);
const results = [];
const check = (name, ok, extra = "") => { results.push({ name, ok }); console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? "  " + extra : ""}`); };

const server = spawn(process.execPath, [join(site, "node_modules/vite/bin/vite.js"), "preview", "--host", "127.0.0.1", "--port", String(PORT), "--strictPort"], { cwd: site, stdio: "pipe" });
await new Promise((res, rej) => {
  const t = setTimeout(() => rej(new Error("preview did not start")), 20000);
  server.stdout.on("data", (d) => { if (String(d).includes(String(PORT))) { clearTimeout(t); res(); } });
  server.on("exit", (c) => rej(new Error("preview exited " + c)));
});

const browser = await chromium.launch({ executablePath: CHROME, args: ["--no-sandbox"] });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
// Mock speechSynthesis so TTS calls can be observed in a headless browser.
await ctx.addInitScript(() => {
  window.__spoken = [];
  const synth = {
    speak: (u) => window.__spoken.push({ text: u.text, rate: u.rate, pitch: u.pitch }), cancel: () => {}, pause: () => {}, resume: () => {},
    getVoices: () => [], addEventListener: () => {}, removeEventListener: () => {}, speaking: false, pending: false, paused: false,
  };
  Object.defineProperty(window, "speechSynthesis", { value: synth, configurable: true });
  if (!window.SpeechSynthesisUtterance) window.SpeechSynthesisUtterance = function (t) { this.text = t; };
});
// Mock LLM endpoint (custom OpenAI-compatible provider); records each request body.
const llmBodies = [];
await ctx.route("https://mock-llm.test/**", async (route) => {
  const req = route.request();
  const cors = { "access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "POST, OPTIONS" };
  if (req.method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
  llmBodies.push(JSON.parse(req.postData() || "{}"));
  return route.fulfill({ status: 200, headers: { ...cors, "content-type": "application/json" }, body: JSON.stringify({ choices: [{ message: { content: `Mock coach answer ${llmBodies.length}.` } }] }) });
});

const p = await ctx.newPage();
const errors = [];
p.on("pageerror", (e) => errors.push(e.message));
p.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
const step = async (name, fn) => { try { await fn(); } catch (e) { check(name, false, String(e.message).split("\n")[0].slice(0, 200)); } };
const clickSq = async (sq) => { await p.click(`[data-square="${sq}"]`); await p.waitForTimeout(80); };

let gameId = null;

await step("play: board, focus mode default on, game vs Bobby, pipeline", async () => {
  await p.goto(BASE + "#/");
  await p.waitForSelector('[data-square="e2"]', { timeout: 30000 });
  const lvl = p.locator(".level", { hasText: "Know the moves" });
  if (await lvl.count()) await lvl.click();
  await p.waitForFunction(() => document.querySelector(".top-r")?.textContent?.includes("Loading core") === false, null, { timeout: 90000 });
  await p.waitForTimeout(600);
  await clickSq("e2"); await clickSq("e4");
  await p.waitForFunction(() => document.querySelectorAll(".moves .mv").length >= 2, null, { timeout: 30000 });
  const focusNote = await p.locator('[data-testid="focus-note"]').count();
  const evalbars = await p.locator(".evalbar").count();
  const askDisabled = await p.getByRole("button", { name: "Ask Bobby" }).isDisabled();
  check("focus mode on by default: eval + coach hidden during game", focusNote === 1 && evalbars === 0 && askDisabled, `note=${focusNote} evalbar=${evalbars} askDisabled=${askDisabled}`);
  await clickSq("d2"); await clickSq("d4");
  await p.waitForFunction(() => document.querySelectorAll(".moves .mv").length >= 4, null, { timeout: 30000 });
  await p.getByRole("button", { name: "Resign" }).click();
  await p.getByRole("button", { name: "Open review" }).waitFor({ timeout: 120000 });
  check("eval returns after game ends", (await p.locator(".evalbar").count()) === 1);
  await p.getByRole("button", { name: "Open review" }).click();
  await p.waitForURL(/#\/review\//);
  gameId = p.url().split("#/review/")[1];
  await p.waitForSelector(".acc", { timeout: 60000 });
  check("game played and analysed", !!gameId);
});

await step("review: explain uses template without key", async () => {
  await p.locator(".moves .mv").first().click();
  await p.locator('[data-testid="explain-btn"]').click();
  const t = p.locator('[data-testid="explain-text"]');
  await t.waitFor({ timeout: 30000 });
  check("per-move explain (template)", (await t.getAttribute("data-source")) === "template" && (await t.textContent()).length > 10, (await t.textContent()).slice(0, 80));
});

await step("stats renders after a game", async () => {
  await p.goto(BASE + "#/stats");
  await p.waitForSelector('[data-testid="history"] tbody tr', { timeout: 30000 });
  await p.waitForSelector('[data-testid="benchmarks"] tbody tr', { timeout: 30000 }).catch(() => {});
  const rows = await p.locator('[data-testid="history"] tbody tr').count();
  const ratingPts = await p.locator('[data-testid="chart-rating"] circle').count();
  const accPts = await p.locator('[data-testid="chart-accuracy"] circle').count();
  const bench = await p.locator('[data-testid="benchmarks"] tbody tr').count();
  check("stats: history, rating + accuracy charts, benchmarks", rows >= 1 && ratingPts >= 1 && accPts >= 1 && bench >= 1, `rows=${rows} rating=${ratingPts} acc=${accPts} bench=${bench}`);
});

await step("lesson completes", async () => {
  const id = "pawn-moves";
  await p.goto(BASE + `#/learn?l=${id}`);
  await p.waitForSelector(`[data-lesson-id="${id}"]`, { timeout: 30000 });
  const lesson = await p.evaluate(async (i) => (await fetch(`./data/lessons/${i}.json`)).json(), id);
  for (let i = 0; i < lesson.steps.length; i++) {
    const st = lesson.steps[i];
    await p.waitForSelector(`[data-lesson-id="${id}"][data-step="${i}"]`, { timeout: 10000 });
    if (st.type === "info") await p.locator(".panel").getByRole("button", { name: "Continue", exact: true }).click();
    else if (st.type === "move") { await clickSq(st.correct[0].slice(0, 2)); await clickSq(st.correct[0].slice(2, 4)); }
    else if (st.type === "square") await clickSq(st.correct[0]);
    else if (st.type === "quiz") await p.locator(".qopt", { hasText: st.correct[0] }).first().click();
    await p.locator('[data-testid="lesson-continue"]').click({ timeout: 10000 });
  }
  await p.locator('[data-testid="lesson-complete"]').waitFor({ timeout: 10000 });
  await p.goto(BASE + "#/learn");
  await p.waitForSelector(`[data-lesson="${id}"]`);
  check("lesson completes and shows as done", await p.locator(`[data-lesson="${id}"].done`).count() === 1);
});

await step("puzzle solves", async () => {
  await p.goto(BASE + "#/train?tab=puzzles&set=themed&theme=mateIn2");
  const el = p.locator("[data-puzzle-id]");
  await el.waitFor({ timeout: 60000 });
  const pid = await el.getAttribute("data-puzzle-id");
  const sol = await p.evaluate(async (i) => (await (await fetch("./data/puzzles.json")).json()).find((x) => x.id === i).solution, pid);
  for (let i = 0; i < sol.length; i += 2) {
    await clickSq(sol[i].slice(0, 2)); await clickSq(sol[i].slice(2, 4));
    if (i + 1 < sol.length) await p.waitForTimeout(700);
  }
  await p.waitForSelector('[data-puzzle-id][data-state="solved"]', { timeout: 10000 });
  check("themed puzzle solved", true, `${pid} ${sol.join(" ")}`);
});

await step("settings persist after reload", async () => {
  await p.goto(BASE + "#/");
  await p.waitForSelector('[data-square="e2"]');
  await p.getByRole("button", { name: "Settings" }).click();
  await p.selectOption('select[aria-label="Board theme"]', "brown");
  await p.selectOption('select[aria-label="Piece set"]', "glyph");
  await p.locator('.persona', { hasText: "The Closer" }).click();
  await p.locator('input[aria-label="Strength offset"]').fill("100");
  await p.reload();
  await p.waitForSelector('[data-square="e2"]');
  await p.getByRole("button", { name: "Settings" }).click();
  const board = await p.inputValue('select[aria-label="Board theme"]');
  const pieces = await p.inputValue('select[aria-label="Piece set"]');
  const persona = await p.locator('input[name="persona"]:checked').getAttribute("value");
  const off = await p.inputValue('input[aria-label="Strength offset"]');
  check("settings persisted", board === "brown" && pieces === "glyph" && persona === "closer" && off === "100", `${board} ${pieces} ${persona} ${off}`);
  // Configure the mocked LLM + voice for the next step.
  await p.selectOption('select[aria-label="Provider"]', "custom");
  await p.fill('input[aria-label="Base URL"]', "https://mock-llm.test/v1");
  await p.fill('input[aria-label="Model"]', "mock-model");
  await p.getByLabel("Speak coach answers aloud").check();
  await p.keyboard.press("Escape");
});

await step("persona swap changes prompt tone only (mock LLM) + TTS", async () => {
  await p.goto(BASE + `#/review/${gameId}`);
  await p.waitForSelector(".acc", { timeout: 30000 });
  const ask = async () => {
    await p.locator(".panel").getByRole("button", { name: "Ask Bobby" }).click();
    const n = await p.locator(".msg.bobby").count();
    await p.locator(".drawer .quick .chip").first().click();
    await p.waitForFunction((k) => document.querySelectorAll(".msg.bobby").length > k, n, { timeout: 30000 });
    await p.locator('.drawer [aria-label="Close coach"]').click();
  };
  await ask();
  await p.getByRole("button", { name: "Settings" }).click();
  await p.locator('.persona', { hasText: "The Visionary" }).click();
  await p.keyboard.press("Escape");
  await ask();
  const [a, b] = llmBodies;
  const ok2 = llmBodies.length === 2;
  const sysA = a?.messages?.[0]?.content ?? "", sysB = b?.messages?.[0]?.content ?? "";
  const userSame = a?.messages?.[1]?.content === b?.messages?.[1]?.content;
  const strip = (x) => x.replace(/Persona '.*?' \(tone only\):.*\n/, "");
  const onlyTone = sysA !== sysB && strip(sysA) === strip(sysB) && sysA.includes("The Closer") && sysB.includes("The Visionary");
  check("persona swap: same facts, only tone block differs", ok2 && userSame && onlyTone, `requests=${llmBodies.length} userSame=${userSame} onlyTone=${onlyTone}`);
  const spoken = await p.evaluate(() => window.__spoken);
  check("TTS speak() called for coach answers", spoken.length >= 2 && spoken.some((x) => x.text.includes("Mock coach answer")), `calls=${spoken.length} rates=${spoken.map((x) => x.rate).join(",")}`);
});

await step("other pages render", async () => {
  for (const t of ["endgames", "openings", "tricks", "challenges"]) {
    await p.goto(BASE + `#/train?tab=${t}`);
    await p.waitForTimeout(1500);
  }
  await p.goto(BASE + "#/train?tab=openings");
  await p.waitForSelector('[data-testid="opening-name"]');
  await clickSq("e2"); await clickSq("e4"); await clickSq("c7"); await clickSq("c5");
  await p.waitForFunction(() => /Sicilian/.test(document.querySelector('[data-testid="opening-name"]')?.textContent ?? ""), null, { timeout: 15000 });
  check("opening explorer names 1.e4 c5 live", true);
  await p.goto(BASE + "#/train?tab=challenges");
  await p.waitForSelector(".plan li", { timeout: 20000 });
  const streak = Number(await p.textContent('[data-testid="streak"]'));
  check("challenges: plan + streak after training today", streak >= 1, `streak=${streak}`);
});

const bad = errors.filter((e) => !/favicon|ERR_FILE_NOT_FOUND|benchmarks\.json/.test(e));
check("no page errors", bad.length === 0, bad.slice(0, 3).join(" | ").slice(0, 300));
await p.screenshot({ path: join(site, "test-results", "smoke.png") }).catch(() => {});
await browser.close();
server.kill();
const failed = results.filter((r) => !r.ok).length;
console.log(`\n${results.length - failed}/${results.length} checks passed`);
process.exit(failed ? 1 : 0);
