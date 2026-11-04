/* ============================================================================
   engine.js  —  Subtitle animation render engine
   ----------------------------------------------------------------------------
   ONE renderer, used by BOTH the live preview and the export.
   renderFrame() is a pure function of (settings, time) -> pixels, so whatever
   you see in the preview is exactly what lands in the .mov. Never render
   anything in the UI that doesn't go through here.

   Pipeline per frame:
     1. layout()        text -> lines -> per-glyph boxes (cached)
     2. glyphStates()   per-glyph alpha / scale / offset / reveal / colour at t
     3. strokeLayer     outline + drop shadow
     4. fillLayer       glyph fills  (recoloured wholesale if gradient mode)
     5. textCanvas      glow + stroke + fill composited
     6. mask            per-letter write-on wipe (destination-in)
     7. wave            per-column flag displacement + shading
     8. out             final RGBA with straight alpha
   ========================================================================== */

const Engine = (() => {
  'use strict';

  /* ---------------------------------------------------------------- utils */

  const clamp01 = x => (x < 0 ? 0 : x > 1 ? 1 : x);
  const lerp = (a, b, p) => a + (b - a) * p;

  const Ease = {
    linear: p => p,
    outCubic: p => 1 - Math.pow(1 - p, 3),
    outQuint: p => 1 - Math.pow(1 - p, 5),
    inOutCubic: p => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2),
    outBack: p => {
      const c1 = 1.70158, c3 = c1 + 1;
      return 1 + c3 * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2);
    },
    outElastic: p => {
      if (p === 0 || p === 1) return p;
      const c4 = (2 * Math.PI) / 3;
      return Math.pow(2, -10 * p) * Math.sin((p * 10 - 0.75) * c4) + 1;
    }
  };

  /* Offscreen canvas pool — reused across frames so we don't thrash memory
     during a 900-frame export. */
  const pool = new Map();
  function scratch(name, w, h) {
    let c = pool.get(name);
    if (!c) { c = document.createElement('canvas'); pool.set(name, c); }
    if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
    else c.getContext('2d').clearRect(0, 0, w, h);
    return c;
  }

  const measureCanvas = document.createElement('canvas');
  const measureCtx = measureCanvas.getContext('2d');

  function fontString(S) {
    const style = S.font.italic ? 'italic ' : '';
    return `${style}${S.font.weight} ${S.font.size}px "${S.font.family}", Impact, sans-serif`;
  }

  /* Convert a hex/rgba colour + alpha multiplier into an rgba() string. */
  function withAlpha(color, a) {
    if (a >= 1) return color;
    if (color.startsWith('#')) {
      let h = color.slice(1);
      if (h.length === 3) h = h.split('').map(c => c + c).join('');
      const n = parseInt(h, 16);
      return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
    }
    if (color.startsWith('hsl(')) return color.replace('hsl(', 'hsla(').replace(')', `,${a})`);
    if (color.startsWith('rgb(')) return color.replace('rgb(', 'rgba(').replace(')', `,${a})`);
    return color;
  }

  /* -------------------------------------------------------------- layout */

  let layoutCache = { key: null, value: null };

  function layoutKey(S) {
    return JSON.stringify([
      S.text, S.font, S.width, S.height, S.align, S.vAlign,
      S.offsetX, S.offsetY, S.maxWidthPct
    ]);
  }

  function wrapText(ctx, text, maxW) {
    const out = [];
    for (const rawLine of text.split('\n')) {
      if (!rawLine.trim()) { out.push(''); continue; }
      if (maxW <= 0) { out.push(rawLine); continue; }
      const words = rawLine.split(/\s+/);
      let cur = '';
      for (const w of words) {
        const test = cur ? cur + ' ' + w : w;
        if (ctx.measureText(test).width > maxW && cur) { out.push(cur); cur = w; }
        else cur = test;
      }
      if (cur) out.push(cur);
    }
    return out;
  }

  /**
   * Measure text into per-glyph boxes.
   * Advance widths come from cumulative measurement of the whole string, so
   * kerning between pairs is preserved even though we draw glyphs one at a
   * time (which is what per-letter animation requires).
   */
  function layout(S) {
    const key = layoutKey(S);
    if (layoutCache.key === key) return layoutCache.value;

    const ctx = measureCtx;
    ctx.font = fontString(S);
    ctx.textAlign = 'left';
    ctx.textBaseline = 'alphabetic';

    const maxW = S.maxWidthPct > 0 ? (S.width * S.maxWidthPct) / 100 : 0;
    const lines = wrapText(ctx, S.text, maxW);
    const lineH = S.font.size * S.font.lineHeight;
    const ls = S.font.letterSpacing;

    const glyphs = [];
    const lineInfo = [];
    let globalIndex = 0;
    let globalWord = 0;

    // First pass: widths, so we can align.
    const lineWidths = lines.map(line => {
      if (!line) return 0;
      let w = ctx.measureText(line).width + ls * Math.max(0, line.length - 1);
      return w;
    });

    const blockH = lines.length * lineH;
    let baseY;
    if (S.vAlign === 'top') baseY = lineH * 0.8;
    else if (S.vAlign === 'bottom') baseY = S.height - blockH + lineH * 0.8;
    else baseY = (S.height - blockH) / 2 + lineH * 0.8;
    baseY += S.offsetY;

    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;

    lines.forEach((line, li) => {
      const lw = lineWidths[li];
      let x;
      if (S.align === 'left') x = S.offsetX + S.width * 0.05;
      else if (S.align === 'right') x = S.width - lw - S.width * 0.05 + S.offsetX;
      else x = (S.width - lw) / 2 + S.offsetX;

      const y = baseY + li * lineH;
      const lineStartGlyph = glyphs.length;
      let cursor = x;
      let prevW = 0;
      let wordIndexInLine = 0;
      let atWordStart = true;

      for (let i = 0; i < line.length; i++) {
        const ch = line[i];
        const cum = ctx.measureText(line.slice(0, i + 1)).width;
        const advance = cum - prevW;
        prevW = cum;

        const isSpace = /\s/.test(ch);
        if (isSpace) { atWordStart = true; }
        else if (atWordStart) { wordIndexInLine++; globalWord++; atWordStart = false; }

        if (!isSpace) {
          const m = ctx.measureText(ch);
          const inkL = cursor - (m.actualBoundingBoxLeft || 0);
          const inkR = cursor + (m.actualBoundingBoxRight !== undefined ? m.actualBoundingBoxRight : advance);
          const inkT = y - (m.actualBoundingBoxAscent || S.font.size * 0.75);
          const inkB = y + (m.actualBoundingBoxDescent || S.font.size * 0.25);

          glyphs.push({
            ch, x: cursor, y,
            inkL, inkR, inkT, inkB,
            cx: (inkL + inkR) / 2,
            cy: (inkT + inkB) / 2,
            line: li,
            word: globalWord - 1,
            wordInLine: wordIndexInLine - 1,
            i: globalIndex++,
            iInLine: i
          });

          if (inkL < minX) minX = inkL;
          if (inkR > maxX) maxX = inkR;
          if (inkT < minY) minY = inkT;
          if (inkB > maxY) maxY = inkB;
        }

        cursor += advance + ls;
      }

      lineInfo.push({
        text: line, y, x, width: lw,
        from: lineStartGlyph, to: glyphs.length
      });
    });

    if (!isFinite(minX)) { minX = minY = 0; maxX = maxY = 1; }

    const value = {
      lines: lineInfo,
      glyphs,
      lineHeight: lineH,
      nLetters: glyphs.length,
      nWords: globalWord,
      nLines: lines.length,
      bbox: { l: minX, t: minY, r: maxX, b: maxY, w: maxX - minX, h: maxY - minY }
    };
    layoutCache = { key, value };
    return value;
  }

  /* --------------------------------------------------------- glyph states */

  function unitIndex(S, g, L, unit) {
    switch (unit) {
      case 'letter': return g.i;
      case 'word': return g.word;
      case 'line': return g.line;
      case 'random': return g._rnd !== undefined ? g._rnd : (g._rnd = hash(g.i) % Math.max(1, L.nLetters));
      default: return 0;
    }
  }
  function hash(n) { n = (n ^ 61) ^ (n >>> 16); n = n + (n << 3); n = n ^ (n >>> 4); n = n * 0x27d4eb2d; n = n ^ (n >>> 15); return Math.abs(n); }

  /**
   * Per-glyph animation state at time t.
   * Entrance (one-shot) and beat pop (looping) are computed independently and
   * multiplied together, so a word can fly in AND keep pulsing on the beat.
   */
  function glyphStates(S, L, t) {
    const E = S.entrance, P = S.pop, F = S.fill;
    const ease = Ease[E.easing] || Ease.outCubic;
    const states = new Array(L.glyphs.length);

    for (let k = 0; k < L.glyphs.length; k++) {
      const g = L.glyphs[k];

      /* ---- entrance ---- */
      const ui = unitIndex(S, g, L, E.unit);
      const start = E.delay + ui * E.stagger;
      const dur = Math.max(0.0001, E.duration);
      const rawP = clamp01((t - start) / dur);
      const p = ease(rawP);

      let alpha = 1, scale = 1, dx = 0, dy = 0, reveal = 1, rot = 0, blur = 0;

      switch (E.mode) {
        case 'none': break;
        case 'fade': alpha = rawP > 0 ? p : 0; break;
        case 'popIn': alpha = clamp01(rawP * 3); scale = Ease.outBack(rawP); break;
        case 'scaleIn': alpha = clamp01(rawP * 2); scale = 0.2 + 0.8 * p; break;
        case 'slideUp': alpha = clamp01(rawP * 2); dy = (1 - p) * E.distance; break;
        case 'slideDown': alpha = clamp01(rawP * 2); dy = -(1 - p) * E.distance; break;
        case 'slideLeft': alpha = clamp01(rawP * 2); dx = (1 - p) * E.distance; break;
        case 'dropSpin': alpha = clamp01(rawP * 2); dy = (1 - p) * E.distance; rot = (1 - p) * 0.6; break;
        case 'blurIn': alpha = clamp01(rawP * 1.5); blur = (1 - p) * E.blurAmount; scale = lerp(1.08, 1, p); break;
        case 'writeOn': reveal = rawP; alpha = rawP > 0 ? 1 : 0; break;
      }

      /* ---- exit (optional) ---- */
      if (S.exit.enabled) {
        const xStart = S.exit.time + unitIndex(S, g, L, S.exit.unit) * S.exit.stagger;
        const xp = clamp01((t - xStart) / Math.max(0.0001, S.exit.duration));
        if (xp > 0) {
          const e = Ease.outCubic(xp);
          alpha *= 1 - e;
          if (S.exit.mode === 'shrink') scale *= 1 - 0.6 * e;
          if (S.exit.mode === 'riseUp') dy -= e * S.exit.distance;
          if (S.exit.mode === 'fallDown') dy += e * S.exit.distance;
        }
      }

      /* ---- beat pop (looping, independent of entrance) ---- */
      if (P.enabled && P.bpm > 0) {
        const period = (60 / P.bpm) * Math.max(1, P.everyNBeats);
        const tau = t - P.offset - unitIndex(S, g, L, P.unit) * P.stagger;
        if (tau >= 0) {
          const since = tau - Math.floor(tau / period) * period;
          const env = Math.exp(-P.damping * since) * Math.cos(2 * Math.PI * P.bounce * since);
          scale *= 1 + P.amount * env;
          if (P.tilt) rot += P.tilt * env * 0.15;
          if (P.lift) dy -= P.lift * env;
        }
      }

      /* ---- colour ---- */
      let color = F.color;
      if (F.mode === 'rainbow') {
        const idx = F.unit === 'word' ? g.word : F.unit === 'line' ? g.line : g.i;
        const h = (F.baseHue + t * F.cycleSpeed * 360 + idx * F.hueSpread) % 360;
        color = `hsl(${(h + 360) % 360},${F.saturation}%,${F.lightness}%)`;
      } else if (F.mode === 'palette') {
        const idx = F.unit === 'word' ? g.word : F.unit === 'line' ? g.line : g.i;
        const pal = F.palette.length ? F.palette : ['#ffffff'];
        const shift = F.paletteCycle ? Math.floor(t * F.cycleSpeed * pal.length) : 0;
        color = pal[(((idx + shift) % pal.length) + pal.length) % pal.length];
      } else if (F.mode === 'gradient') {
        color = '#ffffff'; // recoloured wholesale after the fill pass
      }

      states[k] = { g, alpha: clamp01(alpha), scale, dx, dy, rot, reveal, color, blur };
    }
    return states;
  }

  /* ------------------------------------------------------- drawing passes */

  function applyGlyphTransform(ctx, st) {
    const g = st.g;
    ctx.translate(g.cx + st.dx, g.cy + st.dy);
    if (st.rot) ctx.rotate(st.rot);
    if (st.scale !== 1) ctx.scale(st.scale, st.scale);
    ctx.translate(-g.cx, -g.cy);
  }

  function drawTextPasses(S, L, states, t) {
    const W = S.width, H = S.height;
    const font = fontString(S);

    const strokeC = scratch('stroke', W, H);
    const fillC = scratch('fill', W, H);
    const sctx = strokeC.getContext('2d');
    const fctx = fillC.getContext('2d');

    for (const c of [sctx, fctx]) {
      c.font = font;
      c.textAlign = 'left';
      c.textBaseline = 'alphabetic';
      c.lineJoin = 'round';
      c.miterLimit = 2;
    }

    const hasStroke = S.stroke.enabled && S.stroke.width > 0;
    const shadowOn = S.shadow.enabled;

    /* stroke + drop shadow layer */
    if (hasStroke || shadowOn) {
      sctx.lineWidth = hasStroke ? S.stroke.width * 2 : 0.001;
      for (const st of states) {
        if (st.alpha <= 0) continue;
        sctx.save();
        applyGlyphTransform(sctx, st);
        sctx.globalAlpha = st.alpha;
        if (shadowOn) {
          sctx.shadowColor = withAlpha(S.shadow.color, S.shadow.opacity);
          sctx.shadowBlur = S.shadow.blur;
          sctx.shadowOffsetX = S.shadow.dx;
          sctx.shadowOffsetY = S.shadow.dy;
        }
        if (hasStroke) {
          sctx.strokeStyle = S.stroke.color;
          sctx.strokeText(st.g.ch, st.g.x, st.g.y);
        } else {
          // shadow only: cast it from the glyph shape itself
          sctx.fillStyle = '#000';
          sctx.fillText(st.g.ch, st.g.x, st.g.y);
        }
        sctx.restore();
      }
      // If there's no real outline, the black filler was only there to throw a
      // shadow — knock it back out, leaving just the shadow.
      if (!hasStroke && shadowOn) {
        sctx.save();
        sctx.globalCompositeOperation = 'destination-out';
        sctx.shadowColor = 'transparent'; sctx.shadowBlur = 0;
        sctx.shadowOffsetX = 0; sctx.shadowOffsetY = 0;
        for (const st of states) {
          if (st.alpha <= 0) continue;
          sctx.save(); applyGlyphTransform(sctx, st);
          sctx.fillStyle = '#000';
          sctx.fillText(st.g.ch, st.g.x, st.g.y);
          sctx.restore();
        }
        sctx.restore();
      }
    }

    /* fill layer */
    let anyBlur = false;
    for (const st of states) {
      if (st.alpha <= 0) continue;
      fctx.save();
      applyGlyphTransform(fctx, st);
      fctx.globalAlpha = st.alpha;
      if (st.blur > 0.05) { fctx.filter = `blur(${st.blur.toFixed(2)}px)`; anyBlur = true; }
      fctx.fillStyle = st.color;
      fctx.fillText(st.g.ch, st.g.x, st.g.y);
      fctx.restore();
    }
    if (anyBlur) fctx.filter = 'none';

    /* gradient recolour — keeps the gradient locked to the text block instead
       of riding along with each glyph's pop transform */
    if (S.fill.mode === 'gradient') {
      const G = S.fill;
      const bb = L.bbox;
      const ang = (G.angle * Math.PI) / 180;
      const cx = (bb.l + bb.r) / 2, cy = (bb.t + bb.b) / 2;
      const R = Math.max(bb.w, bb.h) * 0.75 + 1;
      const sweep = G.sweepSpeed ? t * G.sweepSpeed : 0;
      const ox = Math.cos(ang), oy = Math.sin(ang);
      const grad = fctx.createLinearGradient(cx - ox * R, cy - oy * R, cx + ox * R, cy + oy * R);
      const stops = G.stops.length >= 2 ? G.stops : ['#ffffff', '#888888'];
      const n = stops.length;
      // wrap the gradient so a non-zero sweep loops seamlessly
      for (let i = 0; i <= n; i++) {
        let pos = (i / n + sweep) % 1;
        if (pos < 0) pos += 1;
        grad.addColorStop(clamp01(pos), stops[i % n]);
      }
      // guarantee endpoints exist
      grad.addColorStop(0, stops[Math.floor(((sweep % 1) + 1) % 1 * n) % n]);
      fctx.save();
      fctx.globalCompositeOperation = 'source-in';
      fctx.fillStyle = grad;
      fctx.fillRect(0, 0, W, H);
      fctx.restore();
    }

    return { strokeC, fillC, hasStroke, shadowOn };
  }

  /* --------------------------------------------------------- write-on mask */

  function buildMask(S, states) {
    const W = S.width, H = S.height;
    const mask = scratch('mask', W, H);
    const mctx = mask.getContext('2d');
    const pad = (S.stroke.enabled ? S.stroke.width : 0)
      + (S.shadow.enabled ? S.shadow.blur + Math.abs(S.shadow.dy) : 0)
      + (S.glow.enabled ? S.glow.blur : 0) + 4;
    const soft = Math.max(0, S.entrance.softness);

    mctx.fillStyle = '#fff';
    for (const st of states) {
      if (st.alpha <= 0 || st.reveal <= 0) continue;
      const g = st.g;
      const w = (g.inkR - g.inkL) + pad; // include left pad in the swept width
      const x0 = g.inkL - pad;
      const y0 = g.inkT - pad;
      const h = (g.inkB - g.inkT) + pad * 2;
      const revealed = w * st.reveal;

      mctx.save();
      applyGlyphTransform(mctx, st);
      if (st.reveal >= 1) {
        mctx.fillStyle = '#fff';
        mctx.fillRect(x0, y0, w + pad, h);
      } else if (soft > 0.5) {
        const edge = x0 + revealed;
        mctx.fillStyle = '#fff';
        mctx.fillRect(x0, y0, Math.max(0, revealed - soft), h);
        const gr = mctx.createLinearGradient(edge - soft, 0, edge, 0);
        gr.addColorStop(0, 'rgba(255,255,255,1)');
        gr.addColorStop(1, 'rgba(255,255,255,0)');
        mctx.fillStyle = gr;
        mctx.fillRect(Math.max(x0, edge - soft), y0, Math.min(soft, revealed), h);
      } else {
        mctx.fillStyle = '#fff';
        mctx.fillRect(x0, y0, revealed, h);
      }
      mctx.restore();
    }
    return mask;
  }

  /* ------------------------------------------------------------ flag wave */

  /**
   * Column-by-column vertical displacement. Two summed sine waves plus an
   * amplitude ramp from the "pole" edge is what separates a flag from a
   * generic wobble — near the pole the cloth barely moves, at the free edge
   * it swings hard. Shading is driven by cos(phase) (the slope), which is
   * where a real flag catches and loses light.
   */
  function applyWave(src, dst, S, L, t, quality) {
    const W = S.width, H = S.height;
    const w = S.wave;
    const ctx = dst.getContext('2d');
    ctx.clearRect(0, 0, W, H);

    const step = quality === 'fast' ? 3 : 1;
    const amp = w.amplitude;
    const lam = Math.max(10, w.wavelength);
    const bb = L.bbox;
    const padY = amp * (1 + w.squash) + (S.glow.enabled ? S.glow.blur : 0)
      + (S.shadow.enabled ? S.shadow.blur + Math.abs(S.shadow.dy) : 0) + 20;
    const x0 = Math.max(0, Math.floor(bb.l - 60));
    const x1 = Math.min(W, Math.ceil(bb.r + 60));
    const y0 = Math.max(0, Math.floor(bb.t - padY));
    const y1 = Math.min(H, Math.ceil(bb.b + padY));
    const hgt = y1 - y0;
    const span = Math.max(1, x1 - x0);
    const cy = (bb.t + bb.b) / 2;
    const dir = w.direction === 'rtl' ? -1 : 1;

    const phaseAt = x => 2 * Math.PI * ((dir * x) / lam - t * w.speed);
    const rampAt = x => {
      if (w.pole === 'none') return 1;
      const u = w.pole === 'right' ? (x1 - x) / span : (x - x0) / span;
      return Math.pow(clamp01(u), w.poleCurve);
    };

    for (let x = x0; x < x1; x += step) {
      const ph = phaseAt(x);
      const r = rampAt(x);
      const dy = r * (amp * Math.sin(ph) + amp * w.secondary * Math.sin(ph * 0.47 + 1.3));
      const sy = 1 + w.squash * r * Math.cos(ph);
      const sw = Math.min(step + 1, x1 - x); // 1px overlap kills seams

      ctx.save();
      ctx.translate(0, dy);
      if (sy !== 1) { ctx.translate(0, cy); ctx.scale(1, sy); ctx.translate(0, -cy); }
      ctx.drawImage(src, x, y0, sw, hgt, x, y0, sw, hgt);
      ctx.restore();
    }

    if (w.shading > 0) {
      ctx.save();
      ctx.globalCompositeOperation = 'source-atop';
      for (let x = x0; x < x1; x += step) {
        const sh = Math.cos(phaseAt(x)) * rampAt(x);
        const sw = Math.min(step + 1, x1 - x);
        if (sh < 0) ctx.fillStyle = `rgba(0,0,0,${(-sh * w.shading).toFixed(3)})`;
        else ctx.fillStyle = `rgba(255,255,255,${(sh * w.shading * 0.6).toFixed(3)})`;
        ctx.fillRect(x, 0, sw, H);
      }
      ctx.restore();
    }
  }

  /* --------------------------------------------------------- renderFrame */

  /**
   * @param {HTMLCanvasElement} outCanvas  target, sized to S.width x S.height
   * @param {object} S                     settings
   * @param {number} t                     time in SECONDS
   * @param {'full'|'fast'} quality        'full' is always used for export
   */
  function renderFrame(outCanvas, S, t, quality) {
    quality = quality || 'full';
    const W = S.width, H = S.height;
    if (outCanvas.width !== W) outCanvas.width = W;
    if (outCanvas.height !== H) outCanvas.height = H;

    const octx = outCanvas.getContext('2d');
    octx.setTransform(1, 0, 0, 1, 0, 0);
    octx.globalCompositeOperation = 'source-over';
    octx.globalAlpha = 1;
    octx.clearRect(0, 0, W, H);

    if (!S.text.trim()) return;

    const L = layout(S);
    const states = glyphStates(S, L, t);

    const { strokeC, fillC, hasStroke, shadowOn } = drawTextPasses(S, L, states, t);

    /* composite glow -> stroke/shadow -> fill onto one text canvas */
    const textC = scratch('text', W, H);
    const tctx = textC.getContext('2d');

    if (S.glow.enabled && S.glow.blur > 0) {
      tctx.save();
      tctx.shadowColor = withAlpha(S.glow.color, S.glow.opacity);
      tctx.shadowBlur = S.glow.blur;
      for (let i = 0; i < Math.max(1, S.glow.intensity); i++) tctx.drawImage(fillC, 0, 0);
      tctx.restore();
      // remove the un-blurred copies we used to throw the glow
      tctx.save();
      tctx.globalCompositeOperation = 'destination-out';
      tctx.drawImage(fillC, 0, 0);
      tctx.restore();
    }
    if (hasStroke || shadowOn) tctx.drawImage(strokeC, 0, 0);
    tctx.drawImage(fillC, 0, 0);

    /* line backdrop bars (drawn beneath everything) */
    if (S.backdrop.enabled) {
      const bctx = tctx;
      bctx.save();
      bctx.globalCompositeOperation = 'destination-over';
      bctx.fillStyle = withAlpha(S.backdrop.color, S.backdrop.opacity);
      const px = S.backdrop.padX, py = S.backdrop.padY;
      for (const ln of L.lines) {
        if (ln.from >= ln.to) continue;
        let l = Infinity, r = -Infinity, tp = Infinity, bt = -Infinity, maxA = 0;
        for (let k = ln.from; k < ln.to; k++) {
          const st = states[k]; if (!st || st.alpha <= 0) continue;
          const g = st.g;
          l = Math.min(l, g.inkL); r = Math.max(r, g.inkR);
          tp = Math.min(tp, g.inkT); bt = Math.max(bt, g.inkB);
          maxA = Math.max(maxA, st.alpha * (S.entrance.mode === 'writeOn' ? st.reveal : 1));
        }
        if (!isFinite(l) || maxA <= 0) continue;
        bctx.globalAlpha = maxA;
        const rw = (r - l) + px * 2, rh = (bt - tp) + py * 2;
        if (S.backdrop.radius > 0 && bctx.roundRect) {
          bctx.beginPath();
          bctx.roundRect(l - px, tp - py, rw, rh, S.backdrop.radius);
          bctx.fill();
        } else {
          bctx.fillRect(l - px, tp - py, rw, rh);
        }
      }
      bctx.restore();
    }

    /* write-on wipe */
    if (S.entrance.mode === 'writeOn') {
      const mask = buildMask(S, states);
      tctx.save();
      tctx.globalCompositeOperation = 'destination-in';
      tctx.drawImage(mask, 0, 0);
      tctx.restore();
    }

    /* flag wave */
    if (S.wave.enabled && S.wave.amplitude > 0) {
      const waved = scratch('wave', W, H);
      applyWave(textC, waved, S, L, t, quality);
      octx.drawImage(waved, 0, 0);
    } else {
      octx.drawImage(textC, 0, 0);
    }

    /* global opacity */
    if (S.opacity < 1) {
      octx.save();
      octx.globalCompositeOperation = 'destination-in';
      octx.fillStyle = `rgba(0,0,0,${S.opacity})`;
      octx.fillRect(0, 0, W, H);
      octx.restore();
    }
  }

  function invalidate() { layoutCache = { key: null, value: null }; }

  return { renderFrame, layout, fontString, invalidate, Ease, clamp01 };
})();

if (typeof window !== 'undefined') window.Engine = Engine;
