// Headless screenshots of the web page via the Chrome DevTools Protocol (no npm deps; Node >= 22).
//
//   node tools/shot.mjs <url> <out.png> [--w 1440] [--h 900] [--wait 6000] [--eval "js"] [--after 1500]
//
// --eval runs in the page after --wait ms (e.g. "window.__engine.setProgress(0.6)"), then waits --after ms.
// Prints console errors from the page. Exit code 1 if the page logged an error.
import { spawn } from 'node:child_process';
import { writeFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const args = process.argv.slice(2);
const url = args[0], out = args[1];
const opt = (k, d) => { const i = args.indexOf('--' + k); return i > 0 ? args[i + 1] : d; };
const W = +opt('w', 1440), H = +opt('h', 900), WAIT = +opt('wait', 6000), AFTER = +opt('after', 1500);
const evals = args.flatMap((a, i) => (a === '--eval' ? [args[i + 1]] : []));
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const port = 9300 + Math.floor(Math.random() * 500);

const chrome = spawn(CHROME, [
  '--headless=new', `--remote-debugging-port=${port}`, `--window-size=${W},${H}`,
  '--hide-scrollbars', '--no-first-run', '--no-default-browser-check',
  '--enable-webgl', '--ignore-gpu-blocklist', '--use-angle=metal',
  `--user-data-dir=${mkdtempSync(join(tmpdir(), 'shot-'))}`, 'about:blank',
], { stdio: 'ignore' });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let errors = 0;
try {
  let target;
  for (let i = 0; i < 50 && !target; i++) {
    await sleep(200);
    try { target = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find((t) => t.type === 'page'); } catch {}
  }
  if (!target) throw new Error('Chrome did not start');
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((r) => (ws.onopen = r));
  let id = 0; const pending = new Map();
  ws.onmessage = (m) => {
    const msg = JSON.parse(m.data);
    if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
    if (msg.method === 'Runtime.exceptionThrown') { errors++; console.log('EXCEPTION', msg.params.exceptionDetails.exception?.description || msg.params.exceptionDetails.text); }
    if (msg.method === 'Runtime.consoleAPICalled' && ['error', 'warning'].includes(msg.params.type)) {
      if (msg.params.type === 'error') errors++;
      console.log(msg.params.type.toUpperCase(), msg.params.args.map((a) => a.value ?? a.description).join(' '));
    }
  };
  const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  await send('Runtime.enable');
  await send('Page.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 1, mobile: W < 820 });
  await send('Page.navigate', { url });
  await sleep(WAIT);
  for (const e of evals) {
    const r = await send('Runtime.evaluate', { expression: e, awaitPromise: true, returnByValue: true });
    if (r.result?.exceptionDetails) { errors++; console.log('EVAL ERROR', r.result.exceptionDetails.exception?.description); }
    else if (r.result?.result?.value !== undefined) console.log('EVAL', JSON.stringify(r.result.result.value));
    await sleep(AFTER);
  }
  const shot = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync(out, Buffer.from(shot.result.data, 'base64'));
  console.log('SAVED', out);
  ws.close();
} catch (e) {
  errors++; console.log('FAIL', e.message);
} finally {
  chrome.kill('SIGKILL');
}
process.exit(errors ? 1 : 0);
