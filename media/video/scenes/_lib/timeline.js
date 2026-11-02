// Deterministic scene timeline for the Ezhuthu launch video.
// Every scene defines window.SCENE = { duration, render(t) } where render is a pure function of
// scene-local time t (seconds). Capture tools call `await window.__seek(t)`; previews autoplay.
// URL params: ?t=3.2 freezes at 3.2 s; ?play=0 disables autoplay.
(function () {
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const lerp = (a, b, k) => a + (b - a) * k;
  function bezier(x1, y1, x2, y2) {
    // cubic-bezier solver (same curve as CSS)
    const cx = 3 * x1, bx = 3 * (x2 - x1) - cx, ax = 1 - cx - bx;
    const cy = 3 * y1, by = 3 * (y2 - y1) - cy, ay = 1 - cy - by;
    const sx = (t) => ((ax * t + bx) * t + cx) * t;
    const sy = (t) => ((ay * t + by) * t + cy) * t;
    const dx = (t) => (3 * ax * t + 2 * bx) * t + cx;
    return function (x) {
      if (x <= 0) return 0; if (x >= 1) return 1;
      let t = x;
      for (let i = 0; i < 8; i++) { const e = sx(t) - x; const d = dx(t); if (Math.abs(e) < 1e-6 || !d) break; t -= e / d; }
      return sy(clamp(t));
    };
  }
  const E = {
    linear: (x) => x,
    standard: bezier(0.2, 0, 0, 1),
    enter: bezier(0, 0, 0.2, 1),
    exit: bezier(0.4, 0, 1, 1),
    chisel: bezier(0.65, 0, 0.35, 1),
    outCubic: (x) => 1 - Math.pow(1 - x, 3),
    outQuart: (x) => 1 - Math.pow(1 - x, 4),
    outExpo: (x) => (x >= 1 ? 1 : 1 - Math.pow(2, -10 * x)),
    inOut: (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2),
    outBack: (x) => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); },
    outElastic: (x) => (x <= 0 ? 0 : x >= 1 ? 1 : Math.pow(2, -10 * x) * Math.sin((x * 10 - 0.75) * ((2 * Math.PI) / 3)) + 1),
  };
  // progress of t through [start, start+dur] with easing
  const p = (t, start, dur, ease = E.standard) => ease(clamp((t - start) / (dur || 1e-6)));
  // fade in at a, out at b (each `f` seconds)
  const win = (t, a, b, f = 0.4) => Math.min(p(t, a, f, E.standard), 1 - p(t, b - f, f, E.exit));
  // seeded PRNG (mulberry32) so particles are identical every render
  function rng(seed) {
    let a = seed >>> 0;
    return function () { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  }
  const fmt = (n, d = 0) => n.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
  // count-up that never overshoots the final value and lands exactly on it
  const count = (t, start, dur, to, d = 0, from = 0, ease = E.outCubic) => {
    const k = p(t, start, dur, ease);
    const v = k >= 1 ? to : from + (to - from) * k;
    const f = Math.pow(10, d);
    return fmt(Math.floor(v * f + 1e-9) / f, d);
  };
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const css = (el, o) => { if (!el) return; for (const k in o) el.style[k] = o[k]; };

  // split text into spans for kinetic type. Tamil is split by grapheme cluster (never by code point).
  function split(el, mode = 'char') {
    const text = el.textContent;
    el.textContent = '';
    let parts;
    if (mode === 'word') parts = text.split(/(\s+)/);
    else if (typeof Intl !== 'undefined' && Intl.Segmenter) parts = [...new Intl.Segmenter('ta', { granularity: 'grapheme' }).segment(text)].map((s) => s.segment);
    else parts = [...text];
    const spans = [];
    for (const ch of parts) {
      const s = document.createElement('span');
      s.textContent = ch;
      if (/^\s+$/.test(ch)) { s.style.whiteSpace = 'pre'; el.appendChild(s); continue; }
      s.style.display = 'inline-block';
      s.style.willChange = 'transform, opacity';
      el.appendChild(s); spans.push(s);
    }
    return spans;
  }

  async function ready() {
    try { await document.fonts.ready; } catch (e) {}
    const imgs = $$('img');
    await Promise.all(imgs.map((i) => (i.complete ? Promise.resolve() : new Promise((r) => { i.onload = i.onerror = r; }))));
    const vids = $$('video');
    await Promise.all(vids.map((v) => (v.readyState >= 2 ? Promise.resolve() : new Promise((r) => { v.addEventListener('loadeddata', r, { once: true }); v.addEventListener('error', r, { once: true }); setTimeout(r, 8000); }))));
    if (window.SCENE && window.SCENE.prepare) await window.SCENE.prepare();
  }

  // seek videos frame-accurately (resolves after 'seeked')
  function seekVideo(v, time) {
    return new Promise((res) => {
      const target = Math.max(0, Math.min(time, (v.duration || 1e9) - 0.001));
      if (Math.abs(v.currentTime - target) < 1e-4 && v.readyState >= 2) return res();
      const done = () => { v.removeEventListener('seeked', done); requestAnimationFrame(() => res()); };
      v.addEventListener('seeked', done);
      v.currentTime = target;
      setTimeout(done, 3000);
    });
  }

  let readyP = null;
  window.__ready = () => (readyP ||= ready());
  window.__seek = async (t) => {
    await window.__ready();
    const S = window.SCENE;
    const r = S.render(Math.max(0, Math.min(t, S.duration)));
    if (r && r.then) await r;
    // two RAFs so layout + paint have happened before the screenshot
    await new Promise((res) => requestAnimationFrame(() => requestAnimationFrame(res)));
    return true;
  };

  window.EZ = { clamp, lerp, bezier, E, p, win, rng, fmt, count, $, $$, css, split, seekVideo };

  window.addEventListener('load', async () => {
    const q = new URLSearchParams(location.search);
    await window.__ready();
    if (q.has('t')) { window.__seek(parseFloat(q.get('t')) || 0); return; }
    if (q.get('play') === '0' || navigator.webdriver) { window.__seek(0); return; }
    // preview autoplay (loops). Not used for capture.
    const S = window.SCENE; let t0 = performance.now(); let busy = false;
    const tick = async () => {
      if (!busy) { busy = true; const t = ((performance.now() - t0) / 1000) % (S.duration + 1); await window.__seek(Math.min(t, S.duration)); busy = false; }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
})();
