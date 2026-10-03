// Gear helpers shared by the service pages (SVG, no dependencies).

const NS = 'http://www.w3.org/2000/svg';

// gear outline: z teeth, one centred on +x at rotation 0 (module m: pitch radius m·z/2); optional bore
export function gearPath(z, m, hole = 0) {
  const rp = m * z / 2, ro = rp + m, rr = rp - 1.25 * m, pitch = 2 * Math.PI / z;
  let d = '';
  for (let i = 0; i < z; i++) {
    const a = i * pitch;
    [[-0.29, rr], [-0.17, ro], [0.17, ro], [0.29, rr]].forEach(([f, r], j) => {
      d += (i === 0 && j === 0 ? 'M' : 'L') + (r * Math.cos(a + f * pitch)).toFixed(2) + ' ' + (r * Math.sin(a + f * pitch)).toFixed(2);
    });
    const n = a + pitch;
    d += `A${rr.toFixed(2)} ${rr.toFixed(2)} 0 0 1 ${(rr * Math.cos(n - 0.29 * pitch)).toFixed(2)} ${(rr * Math.sin(n - 0.29 * pitch)).toFixed(2)}`;
  }
  d += 'Z';
  if (hole) d += `M${hole} 0A${hole} ${hole} 0 1 0 ${-hole} 0A${hole} ${hole} 0 1 0 ${hole} 0Z`;
  return d;
}

// centre of gear b placed against gear a at angle angDeg (same module, small backlash)
export const place = (m, a, b, angDeg) => {
  const d = m * (a.z + b.z) / 2 + 0.08 * m, t = angDeg * Math.PI / 180;
  return { x: a.x + Math.cos(t) * d, y: a.y + Math.sin(t) * d };
};

// draw a chain of meshing gears into svg; each gear meshes with the previous one (or gears[g.from])
export function makeChain(svg, gears, m, pad = 6) {
  svg.innerHTML = '';
  gears.forEach((g, i) => {
    g.ro = m * (g.z / 2 + 1);
    if (i > 0) { const p = gears[g.from ?? i - 1]; g.th = Math.atan2(g.y - p.y, g.x - p.x); g.prev = p; }
    const el = document.createElementNS(NS, 'path');
    el.setAttribute('fill', g.c); el.setAttribute('fill-rule', 'evenodd');
    el.setAttribute('d', gearPath(g.z, m, g.hole ?? m * g.z * 0.14));
    svg.append(el); g.el = el;
  });
  const minX = Math.min(...gears.map((g) => g.x - g.ro)) - pad, maxX = Math.max(...gears.map((g) => g.x + g.ro)) + pad;
  const minY = Math.min(...gears.map((g) => g.y - g.ro)) - pad, maxY = Math.max(...gears.map((g) => g.y + g.ro)) + pad;
  svg.setAttribute('viewBox', `${minX} ${minY} ${maxX - minX} ${maxY - minY}`);
  return { gears, vb: { x: minX, y: minY, w: maxX - minX, h: maxY - minY } };
}

// turn the chain: gear B (direction θ from A) turns φB = θ + π + π/zB + (zA/zB)(θ − φA), so the teeth stay meshed
export function driveChain({ gears }, phi0) {
  gears.forEach((g, i) => {
    g.phi = i === 0 ? phi0 : g.th + Math.PI + Math.PI / g.z + (g.prev.z / g.z) * (g.th - g.prev.phi);
    g.el.setAttribute('transform', `translate(${g.x.toFixed(2)} ${g.y.toFixed(2)}) rotate(${(g.phi * 180 / Math.PI).toFixed(2)})`);
  });
}

export const COG_ICON = '<svg class="cog-ic" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" fill-rule="evenodd" d="M10.3 2h3.4l.5 2.6 1.8.8 2.2-1.5 2.4 2.4-1.5 2.2.8 1.8 2.6.5v3.4l-2.6.5-.8 1.8 1.5 2.2-2.4 2.4-2.2-1.5-1.8.8-.5 2.6h-3.4l-.5-2.6-1.8-.8-2.2 1.5-2.4-2.4 1.5-2.2-.8-1.8L2 13.7v-3.4l2.6-.5.8-1.8-1.5-2.2 2.4-2.4 2.2 1.5 1.8-.8zM12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7z"/></svg>';

// header turns light over dark / turquoise sections (checked under the header itself, so pinned sections work too)
export function themeHeader() {
  const header = document.querySelector('header');
  const run = () => {
    const under = document.elementsFromPoint(Math.min(200, innerWidth / 2), 44).find((el) => !header.contains(el) && !el.closest('#menu, .menu-toggle'));
    header.classList.toggle('light', !!(under && under.closest('.dark, .on-turq')));
  };
  window.addEventListener('scroll', run, { passive: true });
  run();
}
