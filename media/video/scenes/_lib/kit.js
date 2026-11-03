// Shared building blocks for the v2 launch-film scenes (load after timeline.js).
//   KIT.photo(parent, id)        a 4096 px stock plate (/__stock/web/<id>.jpg) with the warm grade; .at(rect) frames it
//   KIT.kb(ph, A, B, k)          Ken Burns: frame the normalised source rect lerp(A, B, k) to cover 1920x1080
//   KIT.clip(parent, name)       an all-intra clip (/__clips/<name>.mp4); await KIT.seek(v, t)
//   KIT.grain(stage)             deterministic film grain; call g(t) every frame
// Rects are [x, y, w, h] as fractions of the source image (the storyboard's notation). A rect that is not 16:9 is
// covered (the larger scale wins) around its centre, and the result is clamped so the plate always fills the frame.
(function () {
  const { clamp, lerp, rng, seekVideo } = EZ;
  const W = 1920, H = 1080;

  function photo(parent, id, opt = {}) {
    const box = document.createElement('div');
    box.className = 'ph' + (opt.cls ? ' ' + opt.cls : '');
    const img = document.createElement('img');
    img.src = opt.src || `/__stock/web/${id}.jpg`;
    img.alt = '';
    img.decoding = 'sync';
    box.appendChild(img);
    if (opt.grade !== false) { const w = document.createElement('div'); w.className = 'ph-warm'; box.appendChild(w); }
    (parent || document.getElementById('stage')).appendChild(box);
    const ph = { box, img, id, at: (r, extra = 1) => frame(ph, r, extra),
      // source fraction (u, v) -> screen px, valid after the last at()/kb() call
      pt: (u, v) => [ph.tx + u * ph.iw * ph.s, ph.ty + v * ph.ih * ph.s] };
    return ph;
  }
  function frame(ph, r, extra = 1) {
    const iw = ph.img.naturalWidth || 4096, ih = ph.img.naturalHeight || 2304;
    const s = Math.max(W / (r[2] * iw), H / (r[3] * ih)) * extra;
    const cx = (r[0] + r[2] / 2) * iw, cy = (r[1] + r[3] / 2) * ih;
    let tx = W / 2 - cx * s, ty = H / 2 - cy * s;
    tx = clamp(tx, W - iw * s, 0); ty = clamp(ty, H - ih * s, 0);
    ph.s = s; ph.tx = tx; ph.ty = ty; ph.iw = iw; ph.ih = ih;
    ph.img.style.transform = `translate3d(${tx.toFixed(2)}px, ${ty.toFixed(2)}px, 0) scale(${s.toFixed(5)})`;
  }
  const lr = (A, B, k) => A.map((a, i) => lerp(a, B[i], k));
  const kb = (ph, A, B, k, extra = 1) => frame(ph, lr(A, B, clamp(k)), extra);

  function clip(parent, name, cls) {
    const v = document.createElement('video');
    v.src = `/__clips/${name}.mp4`; v.muted = true; v.preload = 'auto'; v.playsInline = true;
    if (cls) v.className = cls;
    (parent || document.getElementById('stage')).appendChild(v);
    return v;
  }
  const seek = (v, t) => seekVideo(v, Math.max(0, t));

  // film grain: a 480x270 noise canvas, re-seeded per frame (30 fps), scaled up and overlaid
  function grain(stage, opacity = 0.11) {
    const c = document.createElement('canvas');
    c.width = 480; c.height = 270; c.className = 'grain-c';
    c.style.opacity = opacity;
    (stage || document.getElementById('stage')).appendChild(c);
    const ctx = c.getContext('2d');
    const id = ctx.createImageData(480, 270);
    let last = -1;
    return (t) => {
      const f = Math.round(t * 30);
      if (f === last) return; last = f;
      const r = rng(1000 + f * 7919);
      const d = id.data;
      for (let i = 0; i < d.length; i += 4) { const v = 96 + r() * 64; d[i] = d[i + 1] = d[i + 2] = v; d[i + 3] = 255; }
      ctx.putImageData(id, 0, 0);
    };
  }

  // full-frame stone / temple flash (1-2 s B-roll between motion-graphics beats).
  //   const f = KIT.flash('p11', A, B, 'caption', 'Photo: ..., CC BY-SA 4.0'); f(t, a, b) shows it from a to b (scene s)
  function flash(id, A, B, cap, credit, opt = {}) {
    const layer = document.createElement('div');
    layer.style.cssText = 'position:absolute;inset:0;z-index:' + (opt.z || 80) + ';overflow:hidden;background:#13100D;opacity:0';
    document.getElementById('stage').appendChild(layer);
    const ph = photo(layer, id);
    const v = document.createElement('div'); v.className = 'vignette'; layer.appendChild(v);
    if (cap) { const c = document.createElement('div'); c.className = 'tag'; c.textContent = cap; layer.appendChild(c); }
    if (credit) { const c = document.createElement('div'); c.className = 'src src-r'; c.textContent = credit; layer.appendChild(c); }
    const fin = opt.fin ?? 0.12, fout = opt.fout ?? 0.25;
    return (t, a, b) => {
      if (t < a - 0.01 || t > b + 0.01) { layer.style.display = 'none'; return 0; }
      layer.style.display = '';
      const k = Math.min(clamp((t - a) / fin), 1 - clamp((t - (b - fout)) / fout));
      layer.style.opacity = k;
      kb(ph, A, B, clamp((t - a) / (b - a)));
      return k;
    };
  }

  window.KIT = { photo, frame, kb, lr, clip, seek, grain, flash };
})();
