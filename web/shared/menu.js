// Shared gear menu: a white pill with a turning gear (top right) that opens into a turquoise-framed panel, spreading out
// from the gear. Used by every page:  import { initMenu } from './shared/menu.js';  initMenu({ onGo })
// - onGo(key): the page handles in-story links itself (index.html scrolls to the section). Without it, those links go to
//   index.html#key, which index.html scrolls to on arrival.
// Needs GSAP (global) and shared/menu.css.

const COG = '<path d="M10.3 2h3.4l.5 2.6 1.8.8 2.2-1.5 2.4 2.4-1.5 2.2.8 1.8 2.6.5v3.4l-2.6.5-.8 1.8 1.5 2.2-2.4 2.4-2.2-1.5-1.8.8-.5 2.6h-3.4l-.5-2.6-1.8-.8-2.2 1.5-2.4-2.4 1.5-2.2-.8-1.8L2 13.7v-3.4l2.6-.5.8-1.8-1.5-2.2 2.4-2.4 2.2 1.5 1.8-.8zM12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7z" fill="currentColor" fill-rule="evenodd"/>';
const BULB = 'M161.92 139.77 154.19 141.44C153.7 144.03 153.03 146.55 152.18 148.99L158.03 154.28C159.4 155.52 159.77 157.84 158.84 159.44L154.36 167.21C153.44 168.81 151.25 169.65 149.49 169.09L141.96 166.67C140.26 168.64 138.42 170.48 136.45 172.19L138.88 179.71C139.44 181.47 138.6 183.66 137 184.59L129.22 189.08C127.63 190 125.31 189.63 124.07 188.27L118.77 182.42C116.33 183.27 113.82 183.94 111.23 184.43L109.56 192.16C109.18 193.96 107.35 195.44 105.51 195.44H96.53C94.68 195.44 92.86 193.97 92.47 192.16L90.8 184.44C88.22 183.95 85.7 183.27 83.26 182.42L77.96 188.28C76.73 189.65 74.41 190.01 72.81 189.09L65.04 184.61C63.44 183.68 62.6 181.49 63.16 179.73L65.59 172.21C63.61 170.5 61.77 168.66 60.07 166.69L52.54 169.12C50.78 169.68 48.59 168.83 47.67 167.24L43.18 159.47C42.26 157.87 42.62 155.55 43.99 154.31L49.84 149.01C48.99 146.57 48.32 144.06 47.82 141.47L40.1 139.8C38.3 139.42 36.82 137.59 36.82 135.75V126.78C36.82 124.93 38.29 123.11 40.09 122.72L47.82 121.05C48.31 118.46 48.98 115.95 49.83 113.5L43.98 108.2C42.61 106.97 42.25 104.66 43.17 103.06L47.65 95.28C48.57 93.68 50.76 92.84 52.52 93.4L60.05 95.82C64.41 90.78 69.67 86.57 75.59 83.41 75.56 83.09 75.59 82.76 75.68 82.41L84.86 46.2C85.31 44.41 87.18 42.95 89.03 42.95H112.93C114.77 42.94 116.65 44.4 117.11 46.19L126.31 82.4C126.39 82.75 126.42 83.08 126.39 83.4 132.31 86.55 137.58 90.77 141.94 95.8L149.47 93.38C151.23 92.81 153.42 93.65 154.34 95.25L158.83 103.03C159.75 104.63 159.39 106.94 158.02 108.17L152.17 113.48C153.02 115.92 153.69 118.43 154.19 121.02L161.91 122.69C163.72 123.07 165.19 124.9 165.19 126.75L165.2 135.72C165.2 137.56 163.72 139.38 161.92 139.77ZM104.48 48.6 101.01 48.22C96.01 47.67 91.29 47.22 90.52 47.22 89.75 47.22 89.05 47.27 89.02 47.3 88.99 47.32 88.83 47.89 88.66 48.56 88.49 49.23 92.44 50.23 97.44 50.78L105.25 51.64C110.25 52.2 114.17 51.96 113.96 51.12 113.74 50.29 109.48 49.16 104.48 48.6ZM106.92 58.2 95.87 56.98C90.87 56.43 86.61 56.63 86.41 57.42 86.21 58.21 90.14 59.31 95.14 59.86L107.69 61.24C112.69 61.79 116.61 61.56 116.39 60.72 116.18 59.89 111.92 58.75 106.92 58.2ZM109.36 67.79 93.56 66.05C88.57 65.5 84.31 65.7 84.12 66.49 83.91 67.28 87.83 68.38 92.84 68.93L110.13 70.83C115.13 71.39 119.05 71.15 118.83 70.32 118.62 69.48 114.36 68.34 109.36 67.79ZM111.8 77.39 91.26 75.13C86.27 74.57 82.02 74.77 81.81 75.57 81.61 76.35 85.54 77.46 90.54 78L112.57 80.43C117.58 80.98 121.49 80.75 121.28 79.91 121.06 79.08 116.8 77.94 111.8 77.39ZM123.46 122.37 120.66 92.37C114.75 89.38 108.07 87.69 100.99 87.69 93.91 87.69 87.23 89.39 81.33 92.38L78.59 121.32C78.49 123.16 78.58 124.08 78.81 123.37 79.04 122.66 79.8 120.86 79.91 120.86 80.01 120.86 80.78 120.86 81.63 120.86 82.48 120.86 83.25 120.86 83.36 120.86 83.45 120.86 84.02 122.28 84.6 124.03L85.69 127.89C86.1 129.68 86.77 129.68 87.19 127.89L88.28 124.03C88.86 122.28 89.42 120.86 89.52 120.86 89.62 120.86 90.4 120.86 91.25 120.86 92.1 120.86 92.87 120.86 92.97 120.86 93.07 120.86 93.63 122.28 94.22 124.03L95.31 127.89C95.72 129.69 96.4 129.69 96.81 127.89L97.9 124.03C98.48 122.28 99.04 120.85 99.14 120.85 99.24 120.85 100.02 120.85 100.87 120.85 101.72 120.85 102.49 120.85 102.59 120.85 102.69 120.85 103.25 122.28 103.84 124.03L104.93 127.89C105.34 129.68 106.02 129.68 106.43 127.89L107.52 124.03C108.1 122.28 108.66 120.85 108.76 120.85 108.87 120.85 109.64 120.85 110.49 120.85 111.34 120.85 112.11 120.85 112.21 120.85 112.32 120.85 112.88 122.28 113.46 124.02L114.55 127.89C114.96 129.68 115.64 129.68 116.05 127.88L117.13 124.02C117.72 122.28 118.29 120.85 118.38 120.85 118.48 120.85 119.26 120.85 120.11 120.85 120.96 120.85 121.73 120.85 121.83 120.85 121.94 120.85 122.28 121.56 122.6 122.43 122.92 123.31 123.57 124.21 123.46 122.37ZM123.55 93.98 126.32 141.14C126.36 142.99 126.35 144.49 126.27 144.49 126.19 144.5 126.15 144.53 126.15 144.6 126.15 144.66 125.59 144.81 124.92 144.81 124.26 144.81 123.58 143.31 123.43 141.47L120.98 127.37C120.51 125.59 119.72 125.59 119.24 127.37L116.79 141.47C116.65 143.31 115.98 144.81 115.3 144.81 114.63 144.81 113.96 143.31 113.81 141.47L111.37 127.37C110.88 125.59 110.09 125.59 109.62 127.37L107.18 141.48C107.03 143.31 106.36 144.82 105.69 144.82 105.01 144.82 104.34 143.31 104.19 141.48L101.75 127.37C101.26 125.59 100.48 125.59 100 127.37L97.55 141.48C97.4 143.32 96.74 144.82 96.07 144.82 95.39 144.82 94.72 143.32 94.57 141.48L92.12 127.38C91.64 125.59 90.86 125.59 90.38 127.38L87.94 141.48C87.78 143.32 87.11 144.82 86.44 144.82 85.77 144.82 85.11 143.32 84.96 141.48L82.5 127.38C82.02 125.6 81.24 125.6 80.76 127.38 80.76 127.38 78.06 137.34 78.05 144.69 78.05 144.72 78.05 144.74 78.05 144.73 78.05 144.79 78.05 144.82 78.05 144.82 78.05 144.82 77.5 144.82 76.83 144.82 76.16 144.82 75.6 144.82 75.6 144.82 75.6 144.82 75.65 143.32 75.7 141.47L78.46 93.98C65.87 101.62 57.46 115.45 57.46 131.26 57.47 155.31 76.96 174.8 101.01 174.79 125.07 174.79 144.56 155.28 144.55 131.24 144.55 115.44 136.14 101.62 123.55 93.98Z';
const BADGE = 'M181.4 89.7L196.7 92.2L196.7 107.8L181.4 110.3L177.8 126.0L190.5 134.9L183.7 149.0L168.8 144.6L158.8 157.2L166.4 170.7L154.2 180.5L142.7 170.0L128.1 177.0L129.1 192.5L113.9 196.0L108.1 181.6L91.9 181.6L86.1 196.0L70.9 192.5L71.9 177.0L57.3 170.0L45.8 180.5L33.6 170.7L41.2 157.2L31.2 144.6L16.3 149.0L9.5 134.9L22.2 126.0L18.6 110.3L3.3 107.8L3.3 92.2L18.6 89.7L22.2 74.0L9.5 65.1L16.3 51.0L31.2 55.4L41.2 42.8L33.6 29.3L45.8 19.5L57.3 30.0L71.9 23.0L70.9 7.5L86.1 4.0L91.9 18.4L108.1 18.4L113.9 4.0L129.1 7.5L128.1 23.0L142.7 30.0L154.2 19.5L166.4 29.3L158.8 42.8L168.8 55.4L183.7 51.0L190.5 65.1L177.8 74.0Z';
const BG_GEAR = 'M179.6 92.2L197.8 93.8L197.8 106.2L179.6 107.8L177.5 119.9L194.0 127.7L189.8 139.2L172.1 134.6L166.0 145.2L178.9 158.2L171.0 167.6L156.0 157.2L146.6 165.0L154.2 181.6L143.6 187.8L133.0 172.9L121.5 177.1L123.0 195.3L110.9 197.4L106.1 179.8L93.9 179.8L89.1 197.4L77.0 195.3L78.5 177.1L67.0 172.9L56.4 187.8L45.8 181.6L53.4 165.0L44.0 157.2L29.0 167.6L21.1 158.2L34.0 145.2L27.9 134.6L10.2 139.2L6.0 127.7L22.5 119.9L20.4 107.8L2.2 106.2L2.2 93.8L20.4 92.2L22.5 80.1L6.0 72.3L10.2 60.8L27.9 65.4L34.0 54.8L21.1 41.8L29.0 32.4L44.0 42.8L53.4 35.0L45.8 18.4L56.4 12.2L67.0 27.1L78.5 22.9L77.0 4.7L89.1 2.6L93.9 20.2L106.1 20.2L110.9 2.6L123.0 4.7L121.5 22.9L133.0 27.1L143.6 12.2L154.2 18.4L146.6 35.0L156.0 42.8L171.0 32.4L178.9 41.8L166.0 54.8L172.1 65.4L189.8 60.8L194.0 72.3L177.5 80.1Z M100 64a36 36 0 1 0 0.01 0Z';

// [label, href (a page) or null, in-story key]
const SERVICES = [
  ['Web development', 'web-development.html', null],
  ['Mobile apps', null, 'stack'],
  ['Interactive design', null, 'design'],
  ['Product strategy', null, 'process'],
  ['Support &amp; care', null, 'support'],
];
const LINKS = [['Home', 'home'], ['About', 'about'], ['Process', 'process'], ['Any stack', 'stack'], ['Selected works', null], ['Contact', 'contact']];
// URLs still to be added (each button stays inert until it has one)
const SOCIALS = [
  ['LinkedIn', '<rect x="3" y="3" width="18" height="18" rx="4"/><path d="M8 10.5v6M8 7.5v.01M11.5 16.5v-3.5a2.5 2.5 0 0 1 5 0v3.5M11.5 10.5v6"/>'],
  ['Instagram', '<rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><path d="M17.3 6.7v.01"/>'],
  ['GitHub', '<path d="M9 19c-4.3 1.4-4.3-2.5-6-3M15 21v-3.5c0-1 .1-1.4-.5-2 2.8-.3 5.5-1.4 5.5-6a4.6 4.6 0 0 0-1.3-3.2 4.2 4.2 0 0 0-.1-3.2s-1.1-.3-3.5 1.3a12.3 12.3 0 0 0-6.2 0C6.5 2.8 5.4 3.1 5.4 3.1a4.2 4.2 0 0 0-.1 3.2A4.6 4.6 0 0 0 4 9.5c0 4.6 2.7 5.7 5.5 6-.6.6-.6 1.2-.5 2V21"/>'],
  ['Email', '<rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="M3.5 6.5l8.5 6.5 8.5-6.5"/>'],
];

function markup() {
  const here = location.pathname.split('/').pop() || 'index.html';
  const tooth = `<span class="tooth" aria-hidden="true"><svg viewBox="0 0 24 24">${COG}</svg></span>`;
  const svc = SERVICES.map(([t, href, go]) => {
    const cur = href && href === here ? ' aria-current="page"' : '';
    return `<li><a href="${href || '#'}"${go ? ` data-go="${go}"` : ''}${cur}>${tooth}<span>${t}</span></a></li>`;
  }).join('');
  const links = LINKS.map(([t, go]) => (go ? `<a href="#" data-go="${go}">${t}</a>`
    : `<span class="soon" aria-disabled="true">${t}<small>soon</small></span>`)).join('');
  const soc = SOCIALS.map(([k, svg]) => `<a href="#" aria-label="${k}"><svg viewBox="0 0 24 24">${svg}</svg></a>`).join('');
  return `
<button class="menu-toggle" id="menuToggle" aria-expanded="false" aria-controls="menu" aria-label="Open menu">
  <span class="bars" aria-hidden="true"><i></i><i></i></span>
  <span class="gearball" aria-hidden="true"><svg viewBox="0 0 24 24">${COG}</svg></span>
</button>
<nav id="menu" aria-label="Main menu" aria-hidden="true">
  <div class="panel">
    <svg class="bg-gear" viewBox="0 0 200 200" aria-hidden="true"><path d="${BG_GEAR}" fill-rule="evenodd"/></svg>
    <ul class="svc">${svc}</ul>
    <a href="#" class="badge" data-go="contact">
      <svg class="gear" viewBox="0 0 200 200" aria-hidden="true"><path d="${BADGE}"/></svg>
      <span class="label"><b>Start a project<br>with us</b><svg class="bulb" viewBox="36 34 130 154" aria-hidden="true"><path transform="matrix(1,0,0,-1,0,230)" d="${BULB}"/></svg></span>
    </a>
    <div class="menu-links">${links}</div>
    <div class="socials">${soc}</div>
  </div>
</nav>`;
}

export function initMenu({ onGo } = {}) {
  document.body.insertAdjacentHTML('beforeend', markup());
  const menuEl = document.getElementById('menu'), toggle = document.getElementById('menuToggle');
  const toggleCog = toggle.querySelector('.gearball svg');
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let open = false, tl = null;

  // the toggle's gear always turns slowly; faster on hover, a burst when the menu opens or closes
  const cog = { speed: 0.12, rot: 0 };               // turns per second
  gsap.ticker.add((time, dt) => {
    if (reduce) return;
    cog.rot += cog.speed * 360 * dt / 1000;
    toggleCog.style.transform = `rotate(${cog.rot.toFixed(1)}deg)`;
  });
  const spin = (to, d = 0.6) => gsap.to(cog, { speed: to, duration: d, ease: 'power2.out', overwrite: true });
  toggle.addEventListener('pointerenter', () => !open && spin(0.7));
  toggle.addEventListener('pointerleave', () => !open && spin(0.12));
  const burst = (dir) => { cog.speed = 3 * dir; spin(open ? -0.12 : 0.12, 1.2); };

  const origin = () => {
    const r = toggleCog.getBoundingClientRect();
    const x = r.left + r.width / 2, y = r.top + r.height / 2;
    return { x, y, R: Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y)) + 20 };
  };
  const PARTS = '#menu .svc li, #menu .badge, #menu .menu-links > *, #menu .socials a';

  function openMenu() {
    if (open) return;
    open = true;
    document.body.classList.add('menu-open');
    toggle.setAttribute('aria-expanded', 'true'); toggle.setAttribute('aria-label', 'Close menu');
    menuEl.setAttribute('aria-hidden', 'false');
    document.documentElement.style.overflow = 'hidden';
    burst(1);
    const { x, y, R } = origin();
    if (tl) tl.kill();
    gsap.set(PARTS, { clearProps: 'all' });
    tl = gsap.timeline()
      .set(menuEl, { visibility: 'visible' })
      .fromTo(menuEl, { clipPath: `circle(0px at ${x}px ${y}px)` }, { clipPath: `circle(${R}px at ${x}px ${y}px)`, duration: 0.8, ease: 'power3.inOut' })
      .from('#menu .svc li', { y: 50, autoAlpha: 0, stagger: 0.06, duration: 0.7, ease: 'power3.out' }, 0.32)
      .from('#menu .badge', { scale: 0.5, rotate: -120, autoAlpha: 0, duration: 1, ease: 'back.out(1.5)' }, 0.4)
      .from('#menu .menu-links > *, #menu .socials a', { y: 16, autoAlpha: 0, stagger: 0.035, duration: 0.5, ease: 'power2.out' }, 0.55)
      .add(() => menuEl.querySelector('.svc a').focus({ preventScroll: true }), 0.5);
  }
  function closeMenu(then) {
    if (!open) return;
    open = false;
    document.body.classList.remove('menu-open');
    toggle.setAttribute('aria-expanded', 'false'); toggle.setAttribute('aria-label', 'Open menu');
    menuEl.setAttribute('aria-hidden', 'true');
    burst(-1);
    const { x, y } = origin();
    if (tl) tl.kill();
    tl = gsap.timeline({ onComplete: () => {
      gsap.set(menuEl, { visibility: 'hidden' });
      document.documentElement.style.overflow = '';
      if (then) then(); else toggle.focus({ preventScroll: true });
    } })
      .to(PARTS, { autoAlpha: 0, duration: 0.2 }, 0)
      .to(menuEl, { clipPath: `circle(0px at ${x}px ${y}px)`, duration: 0.6, ease: 'power3.inOut' }, 0.05);
  }

  toggle.addEventListener('click', () => (open ? closeMenu() : openMenu()));
  window.addEventListener('keydown', (e) => { if (e.key === 'Escape' && open) closeMenu(); });
  menuEl.addEventListener('click', (e) => {
    const a = e.target.closest('a');
    if (!a) return;
    e.preventDefault();
    const go = a.dataset.go, href = a.getAttribute('href');
    if (go) closeMenu(() => (onGo ? onGo(go) : (location.href = go === 'home' ? 'index.html' : `index.html#${go}`)));
    else if (href && href !== '#') closeMenu(() => (location.href = href));
  });
  return { isOpen: () => open, open: openMenu, close: closeMenu };
}
