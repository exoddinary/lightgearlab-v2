// Shared contact overlay. Any link to "#contact" (or with data-contact="topic") opens it; the topic comes from
// data-contact, else <body data-topic>, else "general". Sending opens the visitor's mail app with an email to
// hello@lightgearlab.com, subject and details filled in for that topic (a static site has no mail server; see README).
// Loaded by shared/menu.js, so every page that has the menu has the overlay.

const TO = 'hello@lightgearlab.com';
const TOPICS = {
  general: {
    title: 'Start a <em>project.</em>', intro: "Tell us what you're making. We'll get back to you within two working days.",
    subject: 'Project enquiry', placeholder: 'What are you building, and where are you with it?',
    groups: [['What do you need?', ['Web app / system', 'Mobile app', 'Games tech', 'AR, VR or MR', 'Development partnership', 'Support & care']]],
  },
  'web-apps': {
    title: "Let's build your <em>platform.</em>", intro: 'A few details help us come back with a useful first answer.',
    subject: 'Web apps & systems enquiry', placeholder: 'What should it do, and who will use it?',
    groups: [['Stage', ['New build', 'Redesign / rebuild', 'Add features']], ['Timeline', ['ASAP', '1–3 months', '3–6 months', 'Flexible']]],
  },
  mobile: {
    title: "Let's put it in their <em>pocket.</em>", intro: 'Tell us about the app you have in mind.',
    subject: 'Mobile app enquiry', placeholder: 'What should the app do? Any apps you like the feel of?',
    groups: [['Platform', ['iOS', 'Android', 'Both']], ['Stage', ['Just an idea', 'Designs ready', 'Existing app']]],
  },
  partnership: {
    title: "Bidding on something? Let's <em>mesh.</em>", intro: "Share what you can about the tender; we're happy to sign an NDA first.",
    subject: 'Development partnership / tender enquiry', placeholder: 'What is the tender for, and what would you need from us?',
    groups: [['Partnership model', ['Technical partner', 'Joint bid', 'White-label', 'Not sure yet']]],
    fields: [['deadline', 'Tender deadline', 'date']],
  },
  support: {
    title: "Let's keep it <em>running.</em>", intro: "Tell us about your system, whether we built it or not.",
    subject: 'Support & care enquiry', placeholder: "What's the system, and what kind of help do you need?",
    groups: [['I need', ['A support plan', 'Project rescue', 'A one-off fix']], ['Built by', ['LightGearLab', 'Another team', 'Our in-house team']]],
    fields: [['link', 'Link to the site / app (optional)', 'url']],
  },
};
TOPICS.rescue = { ...TOPICS.support, title: "Let's take a <em>look.</em>", intro: "Tell us what's stuck or broken. We start with an honest health check.",
  subject: 'Project rescue / health check request', placeholder: "What's happening, and how long has it been stuck?", preselect: { 'I need': 'Project rescue' } };

const css = document.createElement('link');
css.rel = 'stylesheet'; css.href = new URL('./contact.css', import.meta.url).href;
document.head.append(css);

const COG = '<path fill="currentColor" fill-rule="evenodd" d="M10.3 2h3.4l.5 2.6 1.8.8 2.2-1.5 2.4 2.4-1.5 2.2.8 1.8 2.6.5v3.4l-2.6.5-.8 1.8 1.5 2.2-2.4 2.4-2.2-1.5-1.8.8-.5 2.6h-3.4l-.5-2.6-1.8-.8-2.2 1.5-2.4-2.4 1.5-2.2-.8-1.8L2 13.7v-3.4l2.6-.5.8-1.8-1.5-2.2 2.4-2.4 2.2 1.5 1.8-.8zM12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7z"/>';
const esc = (s) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

const root = document.createElement('div');
root.id = 'contact';
root.setAttribute('role', 'dialog'); root.setAttribute('aria-modal', 'true'); root.setAttribute('aria-labelledby', 'contactTitle'); root.hidden = true;
root.innerHTML = `
  <div class="ct-panel">
    <button class="ct-close" type="button" aria-label="Close"><span></span><span></span></button>
    <svg class="ct-gear" viewBox="0 0 24 24" aria-hidden="true">${COG}</svg>
    <div class="ct-head"><h2 id="contactTitle"></h2><p class="ct-intro"></p></div>
    <form class="ct-form" novalidate>
      <div class="ct-row">
        <label><span>Name</span><input name="name" autocomplete="name" required></label>
        <label><span>Email</span><input name="email" type="email" autocomplete="email" required></label>
      </div>
      <label><span>Company <i>(optional)</i></span><input name="company" autocomplete="organization"></label>
      <div class="ct-groups"></div>
      <div class="ct-fields"></div>
      <label><span>Message</span><textarea name="message" rows="4" required></textarea></label>
      <p class="ct-error" role="alert"></p>
      <div class="ct-actions">
        <button class="ct-send" type="submit">Send to ${TO} <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M13 6l6 6-6 6"/></svg></button>
        <span class="ct-alt">or email <a href="mailto:${TO}">${TO}</a></span>
      </div>
    </form>
    <div class="ct-done" hidden>
      <svg class="ct-done-gear" viewBox="0 0 24 24" aria-hidden="true">${COG}</svg>
      <h2>Almost <em>there.</em></h2>
      <p>Your email app should have opened with the message ready. Just press send. If it didn't open, copy the message and
        email it to <a href="mailto:${TO}">${TO}</a>.</p>
      <div class="ct-actions"><button class="ct-copy" type="button">Copy message</button><button class="ct-again" type="button">Back</button></div>
    </div>
  </div>`;

let topicKey = 'general', lastFocus = null, tl = null, lastMail = '';
const $ = (sel) => root.querySelector(sel);
const form = $('.ct-form');

function fill(key) {
  topicKey = TOPICS[key] ? key : 'general';
  const t = TOPICS[topicKey];
  $('#contactTitle').innerHTML = t.title;
  $('.ct-intro').textContent = t.intro;
  form.message.placeholder = t.placeholder;
  $('.ct-groups').innerHTML = (t.groups || []).map(([label, opts]) => `
    <fieldset class="ct-chips"><legend>${label}</legend>${opts.map((o) => `
      <label><input type="radio" name="g:${esc(label)}" value="${esc(o)}"${t.preselect?.[label] === o ? ' checked' : ''}><span>${esc(o)}</span></label>`).join('')}
    </fieldset>`).join('');
  $('.ct-fields').innerHTML = (t.fields || []).map(([name, label, type]) =>
    `<label><span>${label}</span><input name="f:${name}" type="${type}" data-label="${esc(label)}"></label>`).join('');
}

function compose() {
  const t = TOPICS[topicKey], d = new FormData(form);
  const name = (d.get('name') || '').trim(), company = (d.get('company') || '').trim();
  const lines = [];
  for (const [label] of t.groups || []) { const v = d.get('g:' + label); if (v) lines.push(`${label}: ${v}`); }
  form.querySelectorAll('.ct-fields input').forEach((i) => { if (i.value) lines.push(`${i.dataset.label.replace(/ \(optional\)/, '')}: ${i.value}`); });
  const body = [`Hi LightGearLab,`, '', (d.get('message') || '').trim(), '', '—',
    `Name: ${name}`, `Email: ${(d.get('email') || '').trim()}`, company ? `Company: ${company}` : null, ...lines,
    `Sent from: ${document.title}`].filter((l) => l !== null).join('\n');
  const subject = `${t.subject}${company ? ' — ' + company : name ? ' — ' + name : ''}`;
  return { subject, body };
}

form.addEventListener('submit', (e) => {
  e.preventDefault();
  const err = $('.ct-error');
  const bad = [...form.querySelectorAll('[required]')].find((i) => !i.value.trim() || (i.type === 'email' && !/^\S+@\S+\.\S+$/.test(i.value)));
  if (bad) { err.textContent = bad.type === 'email' ? 'Please enter a valid email address.' : 'Please fill in your name, email and a message.'; bad.focus(); return; }
  err.textContent = '';
  const { subject, body } = compose();
  lastMail = `To: ${TO}\nSubject: ${subject}\n\n${body}`;
  window.__contactLast = lastMail;                       // (for testing)
  window.location.href = `mailto:${TO}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  form.hidden = true; $('.ct-head').hidden = true; $('.ct-done').hidden = false;
  $('.ct-copy').focus();
});
$('.ct-copy').addEventListener('click', async (e) => {
  try { await navigator.clipboard.writeText(lastMail); e.target.textContent = 'Copied'; } catch { e.target.textContent = 'Copy failed: select the text manually'; }
});
$('.ct-again').addEventListener('click', () => { form.hidden = false; $('.ct-head').hidden = false; $('.ct-done').hidden = true; $('.ct-copy').textContent = 'Copy message'; });

export function openContact(key, from) {
  if (!root.isConnected) document.body.append(root);
  fill(key || document.body.dataset.topic || 'general');
  form.hidden = false; $('.ct-head').hidden = false; $('.ct-done').hidden = true;
  lastFocus = document.activeElement;
  root.hidden = false;
  document.documentElement.style.overflow = 'hidden';
  const r = from?.getBoundingClientRect?.(), x = r ? r.left + r.width / 2 : innerWidth / 2, y = r ? r.top + r.height / 2 : innerHeight / 2;
  const R = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y)) + 20;
  if (tl) tl.kill();
  if (window.gsap) {
    tl = gsap.timeline()
      .fromTo(root, { clipPath: `circle(0px at ${x}px ${y}px)` }, { clipPath: `circle(${R}px at ${x}px ${y}px)`, duration: 0.7, ease: 'power3.inOut' })
      .from(root.querySelectorAll('.ct-head > *, .ct-form > *'), { y: 18, autoAlpha: 0, stagger: 0.04, duration: 0.5, ease: 'power2.out' }, 0.3);
  }
  setTimeout(() => form.name.focus({ preventScroll: true }), 350);
}
export function closeContact() {
  if (root.hidden) return;
  const done = () => { root.hidden = true; document.documentElement.style.overflow = ''; lastFocus?.focus?.({ preventScroll: true }); };
  if (tl) tl.kill();
  if (window.gsap) tl = gsap.to(root, { clipPath: `circle(0px at ${innerWidth - 60}px 50px)`, duration: 0.5, ease: 'power3.inOut', onComplete: done });
  else done();
}

$('.ct-close').addEventListener('click', closeContact);
root.addEventListener('click', (e) => { if (e.target === root) closeContact(); });
window.addEventListener('keydown', (e) => {
  if (root.hidden) return;
  if (e.key === 'Escape') { e.stopImmediatePropagation(); closeContact(); }
  if (e.key === 'Tab') {                                 // keep focus inside the dialog
    const f = [...root.querySelectorAll('button, input, textarea, a[href]')].filter((el) => el.offsetParent);
    if (!f.length) return;
    if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
    else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
  }
}, true);
// every "#contact" link or [data-contact] element on the page opens it (capture: before page handlers)
document.addEventListener('click', (e) => {
  const a = e.target.closest('[data-contact], a[href="#contact"], a[href$="index.html#contact"]');
  if (!a || a.closest('#contact')) return;
  e.preventDefault(); e.stopPropagation();
  openContact(a.dataset.contact, a);
}, true);
if (location.hash === '#contact') setTimeout(() => openContact(), 600);
