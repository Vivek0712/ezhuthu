// Shared pieces for the 30 s social cuts (load after /media/video/scenes/_lib/timeline.js).
//   SOC.load()                 fetch /media/social/vo.json (word times on the 30 s clock) -> SOC.vo, SOC.chunks
//   SOC.captions(el, t)        burned-in, word-synced captions: short chunks, active word lit in lamp-300
//   SOC.line(n)                {start_s, end_s} of narration line n (1-based): beats key off the voice
//   SOC.photo(parent, src, W, H) / SOC.frame(ph, rect)   a stock plate framed by a normalised source rect for any W x H
(function () {
  const { clamp, lerp } = EZ;
  const S = { vo: null, chunks: [] };

  S.load = async function (maxWords = 4, maxChars = 26) {
    S.vo = await (await fetch('/media/social/vo.json', { cache: 'no-store' })).json();
    const chunks = [];
    for (const ln of S.vo.lines) {
      // speech marks drop punctuation: take the display form of each word from the script when counts match
      const toks = ln.text.split(/\s+/);
      if (toks.length === ln.words.length) ln.words.forEach((w, i) => { w.w = toks[i]; });
      let cur = [];
      const flush = () => { if (cur.length) chunks.push({ words: cur, line: ln.n }); cur = []; };
      for (const w of ln.words) {
        const txt = cur.map((x) => x.w).join(' ');
        if (cur.length && (cur.length >= maxWords || (txt + ' ' + w.w).length > maxChars)) flush();
        cur.push(w);
        if (/[,.:;!?]$/.test(w.w) && cur.length >= 2) flush();
      }
      flush();
    }
    chunks.forEach((c) => { c.s = c.words[0].s - 0.06; });
    chunks.forEach((c, i) => {
      const next = chunks[i + 1];
      const end = c.words[c.words.length - 1].e + 0.35;
      c.e = next && next.line === c.line ? next.s : end;
      if (next) c.e = Math.min(c.e, next.words[0].s - 0.06);
    });
    S.chunks = chunks;
    return S.vo;
  };
  S.line = (n) => S.vo.lines[n - 1];

  // caption element: one chunk at a time, each word a span; dangling punctuation trimmed except ? and '
  let lastKey = null;
  S.captions = function (el, t, opts = {}) {
    const c = S.chunks.find((x) => t >= x.s && t < x.e);
    if (!c) { el.style.opacity = 0; lastKey = null; return null; }
    const key = c.s;
    if (key !== lastKey) {
      el.innerHTML = '';
      for (const w of c.words) {
        const s = document.createElement('span');
        s.className = 'cw';
        s.textContent = w.w.replace(/[,.;:]$/, '');
        el.appendChild(s);
        el.appendChild(document.createTextNode(' '));
      }
      lastKey = key;
    }
    const spans = el.querySelectorAll('.cw');
    c.words.forEach((w, i) => { spans[i].classList.toggle('on', t >= w.s - 0.03); spans[i].classList.toggle('now', t >= w.s - 0.03 && t < w.e); });
    const k = clamp((t - c.s) / 0.12);
    el.style.opacity = 1;
    el.style.transform = `${opts.base || ''} translateY(${(1 - k) * 10}px)`;
    return c;
  };

  S.photo = function (parent, src, W, H, cls) {
    const box = document.createElement('div');
    box.className = 'ph' + (cls ? ' ' + cls : '');
    box.style.width = W + 'px'; box.style.height = H + 'px';
    const img = document.createElement('img');
    img.src = src; img.alt = ''; img.decoding = 'sync';
    box.appendChild(img);
    const w = document.createElement('div'); w.className = 'ph-warm'; box.appendChild(w);
    parent.appendChild(box);
    return { box, img, W, H };
  };
  // rect = [x, y, w, h] fractions of the source; covered (larger scale wins) and clamped to fill W x H
  S.frame = function (ph, r) {
    const iw = ph.img.naturalWidth || 4096, ih = ph.img.naturalHeight || 2304;
    const s = Math.max(ph.W / (r[2] * iw), ph.H / (r[3] * ih));
    const cx = (r[0] + r[2] / 2) * iw, cy = (r[1] + r[3] / 2) * ih;
    let tx = ph.W / 2 - cx * s, ty = ph.H / 2 - cy * s;
    tx = clamp(tx, ph.W - iw * s, 0); ty = clamp(ty, ph.H - ih * s, 0);
    ph.img.style.transform = `translate3d(${tx.toFixed(2)}px, ${ty.toFixed(2)}px, 0) scale(${s.toFixed(5)})`;
    ph.s = s; ph.tx = tx; ph.ty = ty; ph.iw = iw; ph.ih = ih;
  };
  S.kb = (ph, A, B, k) => S.frame(ph, A.map((a, i) => lerp(a, B[i], clamp(k))));

  // film grain at any size (seeded per frame)
  S.grain = function (stage, W, H, opacity = 0.08) {
    const c = document.createElement('canvas');
    c.width = Math.round(W / 4); c.height = Math.round(H / 4);
    c.style.cssText = `position:absolute;left:0;top:0;width:${W}px;height:${H}px;pointer-events:none;mix-blend-mode:overlay;z-index:60;opacity:${opacity}`;
    stage.appendChild(c);
    const ctx = c.getContext('2d');
    const id = ctx.createImageData(c.width, c.height);
    let last = -1;
    return (t) => {
      const f = Math.round(t * 30);
      if (f === last) return; last = f;
      const r = EZ.rng(1000 + f * 7919);
      const d = id.data;
      for (let i = 0; i < d.length; i += 4) { const v = 96 + r() * 64; d[i] = d[i + 1] = d[i + 2] = v; d[i + 3] = 255; }
      ctx.putImageData(id, 0, 0);
    };
  };

  // ---- the Restore beat (real gallery sample: Tiruvalisvaram district name, filled -k at 72%, matches the edition)
  // L = layout in page px: {head:{x,y,w}, line:{x,y,w,fs}, src:[{x,y,w,h}x4], node:{x,y,w,h}, verdict:{x,y,w}, foot:{x,y,w}}
  S.restoreBeat = function (parent, L) {
    const root = document.createElement('div'); root.className = 'rb'; parent.appendChild(root);
    const el = (cls, html, st) => { const d = document.createElement('div'); d.className = cls; d.innerHTML = html; Object.assign(d.style, st); root.appendChild(d); return d; };
    const head = el('rb-head', '<span class="eb">Restorer</span> a Strands agent with tools', { left: L.head.x + 'px', top: L.head.y + 'px', width: L.head.w + 'px' });
    const line = el('rb-line', (L.line.pre || 'நாட்டுப் பாம்புணி') + '<span class="gap"><b class="q">?</b><b class="k">க்</b></span>' + (L.line.post || 'கூற்றத்து'),
      { left: L.line.x + 'px', top: L.line.y + 'px', width: L.line.w + 'px', fontSize: L.line.fs + 'px' });
    const SRC = [['14,355 parallel lines', 'from other inscriptions'], ['Custom Tamil ontology', '1,958 kings, places, temples, formulas'],
      ['Fine-tuned Strands decision models', 'trained on Tamil inscriptions'], ['Claude on Amazon Bedrock', 'proposes the letters']];
    const srcs = SRC.map(([a, b], i) => el('rb-src', `<div class="a">${a}</div><div class="b">${b}</div>`,
      { left: L.src[i].x + 'px', top: L.src[i].y + 'px', width: L.src[i].w + 'px', height: L.src[i].h + 'px' }));
    const node = el('rb-node', '<div class="a">Confidence check</div><div class="b">fill only when sure</div>',
      { left: L.node.x + 'px', top: L.node.y + 'px', width: L.node.w + 'px', height: L.node.h + 'px' });
    const verdict = el('rb-verdict', '<span class="pct">72% sure</span> <span class="fill">FILL</span>', { left: L.verdict.x + 'px', top: L.verdict.y + 'px', width: L.verdict.w + 'px' });
    const match = el('rb-match', '✓ matches the editors’ restoration', { left: L.verdict.x + 'px', top: (L.verdict.y + L.verdict.dy) + 'px', width: L.verdict.w + 'px' });
    const foot = el('rb-foot', 'Gallery sample: a district name, Tiruvalisvaram inscription. Text: DHARMA, CC BY-SA 4.0', { left: L.foot.x + 'px', top: L.foot.y + 'px', width: L.foot.w + 'px' });
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); svg.setAttribute('class', 'rb-svg');
    svg.setAttribute('width', L.W); svg.setAttribute('height', L.H); root.insertBefore(svg, root.firstChild);
    const nx = L.node.x + L.node.w / 2, ny = L.node.y;
    const paths = L.src.map((r) => { const pth = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      const sx = r.x + r.w / 2, sy = r.y + r.h; const ex = L.horizontal ? L.node.x : nx, ey = L.horizontal ? L.node.y + L.node.h / 2 : ny;
      const x0 = L.horizontal ? r.x + r.w : sx, y0 = L.horizontal ? r.y + r.h / 2 : sy;
      pth.setAttribute('d', L.horizontal ? `M${x0} ${y0} C ${x0 + 80} ${y0}, ${ex - 80} ${ey}, ${ex} ${ey}` : `M${x0} ${y0} C ${x0} ${y0 + 60}, ${ex} ${ey - 60}, ${ex} ${ey}`);
      pth.setAttribute('class', 'edge'); svg.appendChild(pth); return pth; });
    const pk = paths.map(() => { const c = document.createElementNS('http://www.w3.org/2000/svg', 'circle'); c.setAttribute('r', 9); c.setAttribute('class', 'pkt'); svg.appendChild(c); return c; });
    let PL = null;
    const gap = line.querySelector('.gap'), q = line.querySelector('.q'), k = line.querySelector('.k');
    return {
      root,
      render(t, T) { // T = {in, src0, srcStep, fill, sure, match, out}
        const { p, E } = EZ;
        if (!PL) PL = paths.map((x) => x.getTotalLength());
        root.style.opacity = Math.min(p(t, T.in - 0.15, 0.3), 1 - p(t, T.out - 0.15, 0.3));
        head.style.opacity = p(t, T.in, 0.3);
        line.style.opacity = p(t, T.in + 0.05, 0.3);
        const pulse = 0.5 + 0.5 * Math.sin(t * 7);
        gap.style.boxShadow = t < T.fill ? `0 0 ${18 + 22 * pulse}px rgba(174,184,236,${0.5 + 0.4 * pulse})` : '0 0 34px rgba(245,196,104,.9)';
        gap.classList.toggle('filled', t >= T.fill);
        q.style.opacity = 1 - p(t, T.fill - 0.1, 0.2); k.style.opacity = p(t, T.fill, 0.25);
        k.style.transform = `translateY(${(1 - p(t, T.fill, 0.35, E.outBack)) * -60}px)`;
        srcs.forEach((d, i) => { const a = T.src0 + i * T.srcStep; d.style.opacity = p(t, a, 0.25); d.classList.toggle('hot', t >= a && t < a + 0.9);
          d.style.transform = `translateY(${(1 - p(t, a, 0.35, E.outCubic)) * 18}px)`;
          paths[i].style.strokeDasharray = PL[i]; paths[i].style.strokeDashoffset = PL[i] * (1 - p(t, a + 0.15, 0.4));
          const f = ((t - a - 0.3) / 0.7); const on = f > 0 && t < T.sure;
          const pt = paths[i].getPointAtLength(PL[i] * (f % 1 + 1) % 1 * 1); pk[i].setAttribute('cx', pt.x); pk[i].setAttribute('cy', pt.y); pk[i].style.opacity = on ? 1 : 0; });
        node.style.opacity = p(t, T.src0 + 0.3, 0.3);
        node.classList.toggle('hot', t >= T.src0 + 3 * T.srcStep && t < T.sure + 0.6);
        verdict.style.opacity = p(t, T.sure - 0.25, 0.3);
        verdict.style.transform = `scale(${0.85 + 0.15 * p(t, T.sure - 0.25, 0.4, E.outBack)})`;
        match.style.opacity = p(t, T.match, 0.3);
        foot.style.opacity = 0.9 * p(t, T.in + 0.3, 0.4);
      },
    };
  };

  window.SOC = S;
})();
