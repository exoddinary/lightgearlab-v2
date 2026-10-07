// Generate the site's subtle sound effects with the ElevenLabs Sound Effects API → web/sfx/*.mp3
//   export ELEVENLABS_API_KEY=...   (your key; never commit it)
//   node tools/make_sfx.mjs            # all sounds
//   node tools/make_sfx.mjs click      # just one
// Edit the prompts below and re-run to regenerate a sound.
import { writeFileSync, mkdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const SFX = {
  swoosh:    { seconds: 1.2, text: 'soft airy whoosh of a camera swinging around an object, smooth, gentle, cinematic but subtle, no impact' },
  projector: { seconds: 1.2, text: 'old film projector switching on, soft electrical click then a quiet warm hum, close, subtle' },
  hum:       { seconds: 6,   text: 'very quiet low mechanical hum of small clockwork gears turning, steady, seamless loop, no clicks' },
  click:     { seconds: 0.6, text: 'small brass latch clicking shut, soft satisfying mechanical click, close mic, dry' },
  tick:      { seconds: 0.3, text: 'single tiny gear tooth tick, very soft, short, dry, like a watch mechanism' },
  ratchet:   { seconds: 0.8, text: 'quick soft ratchet whirr, small metal gear spinning up briefly, subtle, dry' },
  unscrew:   { seconds: 0.6, text: 'tiny screw being unscrewed, two soft ratchet clicks, small metal, close, quiet' },
  clink:     { seconds: 0.7, text: 'light metal part lifting off a metal frame, soft clink, small, airy, subtle' },
  ding:      { seconds: 1.5, text: 'gentle small desk bell ding, soft and warm, short decay, pleasant, quiet' },
};

// tolerate pasted quotes / spaces / a leading label; never print the key itself
const raw = (process.env.ELEVENLABS_API_KEY || '').trim().replace(/^['"]|['"]$/g, '');
const key = (raw.match(/sk_[A-Za-z0-9]{48}/) || [raw])[0];
if (!key || /your_(real_)?key/.test(key)) {
  console.error('Set your ElevenLabs API key first:  export ELEVENLABS_API_KEY=sk_...');
  process.exit(1);
}
if (key.length !== 51 || !key.startsWith('sk_')) {
  console.error(`That key doesn't look right: ${key.length} characters${key.startsWith('sk_') ? '' : ', and it should start with sk_'}.`);
  console.error('ElevenLabs keys are 51 characters starting with sk_. Copy it again from elevenlabs.io → Profile → API Keys.');
  process.exit(1);
}
const out = join(dirname(dirname(fileURLToPath(import.meta.url))), 'web', 'sfx');
mkdirSync(out, { recursive: true });
const only = process.argv[2];

for (const [name, { text, seconds }] of Object.entries(SFX)) {
  if (only && only !== name) continue;
  process.stdout.write(`${name.padEnd(10)} … `);
  const res = await fetch('https://api.elevenlabs.io/v1/sound-generation?output_format=mp3_44100_64', {
    method: 'POST',
    headers: { 'xi-api-key': key, 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, duration_seconds: seconds, prompt_influence: 0.6, ...(name === 'hum' ? { loop: true } : {}) }),
  });
  if (!res.ok) { console.log(`failed (${res.status}) ${await res.text()}`); continue; }
  const buf = Buffer.from(await res.arrayBuffer());
  writeFileSync(join(out, `${name}.mp3`), buf);
  console.log(`saved ${(buf.length / 1024).toFixed(0)} KB`);
}
