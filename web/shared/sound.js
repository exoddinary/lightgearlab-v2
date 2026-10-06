// Subtle sound effects (files in web/sfx/, made by tools/make_sfx.mjs). Off until the visitor turns them on with the
// small toggle; the choice is remembered. Quiet, never stacked, silent when the tab is hidden or reduced motion is set.
//   import { sfx } from './shared/sound.js';  sfx.play('click');  sfx.hum(level 0..1)
const BASE = new URL('../sfx/', import.meta.url).href;
const VOL = { swoosh: 0.28, projector: 0.25, click: 0.3, tick: 0.12, ratchet: 0.18, unscrew: 0.14, clink: 0.16, ding: 0.25 };
const HUM_MAX = 0.08;
const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
let ctx = null, master = null, buffers = {}, humNode = null, humGain = null, on = false, last = {};
try { on = localStorage.getItem('lgl-sound') === 'on'; } catch {}

// Built-in stand-ins, synthesised here, so the site has sound even before the ElevenLabs clips exist (sfx/*.mp3 win).
function synth(name) {
  const sr = ctx.sampleRate, len = { swoosh: 1.2, hum: 4, projector: 1.1, ding: 1.4, ratchet: 0.45, clink: 0.5, click: 0.18, unscrew: 0.3, tick: 0.06 }[name] || 0.2;
  const b = ctx.createBuffer(1, Math.floor(sr * len), sr), d = b.getChannelData(0);
  let seed = 1; const noise = () => ((seed = (seed * 16807) % 2147483647) / 1073741823.5 - 1);
  const tick = (t0, f, decay, amp) => { for (let i = Math.floor(t0 * sr); i < d.length; i++) { const t = i / sr - t0;
    d[i] += amp * Math.exp(-t / decay) * (0.6 * Math.sin(2 * Math.PI * f * t) + 0.4 * noise()); } };
  if (name === 'swoosh') {                                // air sweeping past: noise through a rising-then-falling band
    let lp = 0, bp = 0;
    for (let i = 0; i < d.length; i++) { const t = i / sr, u = t / len, env = Math.sin(Math.PI * Math.min(1, u)) ** 2;
      const f = 0.02 + 0.18 * Math.sin(Math.PI * u); lp += f * (noise() - lp); bp += f * (lp - bp); d[i] = 1.6 * env * (lp - bp); } }
  else if (name === 'tick') tick(0, 3200, 0.006, 0.5);
  else if (name === 'click') { tick(0, 1800, 0.01, 0.7); tick(0.035, 900, 0.03, 0.5); }
  else if (name === 'unscrew') { tick(0, 2600, 0.008, 0.4); tick(0.12, 2400, 0.008, 0.35); }
  else if (name === 'ratchet') { for (let k = 0; k < 9; k++) tick(k * 0.045 * (1 - k * 0.04), 2800, 0.005, 0.3 * (1 - k / 11)); }
  else if (name === 'clink') { for (let i = 0; i < d.length; i++) { const t = i / sr;
    d[i] += 0.35 * Math.exp(-t / 0.12) * (Math.sin(2 * Math.PI * 2350 * t) + 0.5 * Math.sin(2 * Math.PI * 3890 * t)); } }
  else if (name === 'ding') { for (let i = 0; i < d.length; i++) { const t = i / sr;
    d[i] += 0.35 * Math.exp(-t / 0.45) * (Math.sin(2 * Math.PI * 1318 * t) + 0.35 * Math.sin(2 * Math.PI * 2637 * t)); } }
  else if (name === 'projector') { tick(0, 1200, 0.015, 0.6);
    for (let i = Math.floor(0.05 * sr); i < d.length; i++) { const t = i / sr;
      d[i] += 0.12 * Math.min(1, (t - 0.05) * 8) * Math.exp(-(t - 0.05) / 0.6) * (Math.sin(2 * Math.PI * 100 * t) + 0.5 * Math.sin(2 * Math.PI * 200 * t)); } }
  else if (name === 'hum') { for (let i = 0; i < d.length; i++) { const t = i / sr;   // whole cycles in 4 s, so it loops cleanly
    d[i] = 0.25 * Math.sin(2 * Math.PI * 55 * t) + 0.12 * Math.sin(2 * Math.PI * 110 * t) + 0.04 * noise()
      + 0.15 * Math.max(0, Math.sin(2 * Math.PI * 6 * t)) ** 24 * noise(); } }
  return b;
}
async function load(name) {
  if (buffers[name] !== undefined) return buffers[name];
  buffers[name] = null;
  try {
    const r = await fetch(BASE + name + '.mp3');
    if (r.ok) buffers[name] = await ctx.decodeAudioData(await r.arrayBuffer());
  } catch {}
  if (!buffers[name]) buffers[name] = synth(name);       // no generated clip yet: use the built-in stand-in
  return buffers[name];
}
async function start() {
  if (!ctx) {
    ctx = new (window.AudioContext || window.webkitAudioContext)();
    master = ctx.createGain(); master.gain.value = 1; master.connect(ctx.destination);
    await Promise.all(['hum', ...Object.keys(VOL)].map(load));
    if (buffers.hum) {
      humGain = ctx.createGain(); humGain.gain.value = 0; humGain.connect(master);
      humNode = ctx.createBufferSource(); humNode.buffer = buffers.hum; humNode.loop = true; humNode.connect(humGain); humNode.start();
    }
  }
  if (ctx.state === 'suspended') await ctx.resume();
}
function setOn(v) {
  on = v;
  try { localStorage.setItem('lgl-sound', v ? 'on' : 'off'); } catch {}
  document.documentElement.classList.toggle('sound-on', v);
  if (v) start().then(() => sfx.play('tick')); else if (humGain) humGain.gain.setTargetAtTime(0, ctx.currentTime, 0.1);
}
document.addEventListener('visibilitychange', () => { if (ctx) (document.hidden ? ctx.suspend() : on && ctx.resume()); });

export const sfx = {
  get on() { return on; },
  toggle() { setOn(!on); },
  play(name, gain = 1) {
    if (!on || reduce || !ctx || !buffers[name]) return;
    const now = ctx.currentTime;
    if (last[name] && now - last[name] < 0.09) return;  // never machine-gun the same sound
    last[name] = now;
    const s = ctx.createBufferSource(), g = ctx.createGain();
    s.buffer = buffers[name]; s.playbackRate.value = 0.96 + Math.random() * 0.08;   // tiny variation, so repeats don't feel canned
    g.gain.value = (VOL[name] ?? 0.2) * gain;
    s.connect(g).connect(master); s.start();
  },
  hum(level) {                                           // 0..1, eased; follows scroll speed
    if (!humGain || !on || reduce) return;
    humGain.gain.setTargetAtTime(HUM_MAX * Math.max(0, Math.min(1, level)), ctx.currentTime, 0.4);
  },
};

// the toggle: a small speaker-gear button beside the menu button (built here so every page gets it)
const btn = document.createElement('button');
btn.className = 'sound-toggle'; btn.type = 'button';
btn.setAttribute('aria-label', 'Sound');
btn.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z" fill="currentColor"/>
  <path class="w" d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
  <path class="x" d="M16 9.5l5 5M21 9.5l-5 5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>`;
const style = document.createElement('style');
style.textContent = `.sound-toggle { position: fixed; top: 22px; right: 168px; z-index: 60; width: 54px; height: 54px; border: 0; border-radius: 50%;
  background: #fff; color: #1d1c1a; cursor: pointer; display: grid; place-items: center; box-shadow: 0 6px 22px rgba(0,0,0,0.1); }
.sound-toggle svg { width: 22px; height: 22px; } .sound-toggle .w { display: none; }
.sound-on .sound-toggle .w { display: block; } .sound-on .sound-toggle .x { display: none; }
.sound-toggle:focus-visible { outline: 2px solid #f2c14e; outline-offset: 3px; }
@media (max-width: 820px) { .sound-toggle { top: 14px; right: 128px; width: 46px; height: 46px; } }`;
document.head.append(style);
document.body.append(btn);
document.documentElement.classList.toggle('sound-on', on);
btn.addEventListener('click', () => { btn.setAttribute('aria-pressed', String(!on)); sfx.toggle(); });
// browsers only allow audio after a gesture: if sound was left on, start on the first interaction
if (on) { const go = () => { start(); removeEventListener('pointerdown', go); removeEventListener('keydown', go); };
  addEventListener('pointerdown', go); addEventListener('keydown', go); }
// a soft tick on hover for buttons and cards everywhere
document.addEventListener('pointerover', (e) => {
  const t = e.target.closest('a, button, .card, .chip');
  if (t && !t.contains(e.relatedTarget)) sfx.play('tick');
});
