/* ============================================================================
   ui.js  —  controls, live preview, and the export driver
   ========================================================================== */

(function () {
  'use strict';

  const $ = s => document.querySelector(s);
  const el = (tag, cls, txt) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (txt != null) n.textContent = txt;
    return n;
  };

  /* ------------------------------------------------------------ settings */

  const clone = o => JSON.parse(JSON.stringify(o));

  function deepMerge(base, patch) {
    for (const k in patch) {
      const v = patch[k];
      if (v && typeof v === 'object' && !Array.isArray(v) && typeof base[k] === 'object' && base[k] !== null) {
        deepMerge(base[k], v);
      } else {
        base[k] = Array.isArray(v) ? v.slice() : v;
      }
    }
    return base;
  }
  const getP = (o, p) => p.split('.').reduce((a, k) => (a == null ? a : a[k]), o);
  const setP = (o, p, v) => {
    const ks = p.split('.'); const last = ks.pop();
    ks.reduce((a, k) => (a[k] = a[k] || {}), o)[last] = v;
  };

  let S = clone(window.DEFAULTS);
  let ENV = { ffmpeg: false, codecs: { prores4444: 'ProRes 4444' }, outputDir: '' };

  /* Derived values: the write-on sliders are expressed in letters-per-second
     and overlap because that's how you actually think about handwriting speed;
     the engine wants stagger + duration. */
  function applyDerived() {
    const E = S.entrance;
    if (E.mode === 'writeOn') {
      E.unit = 'letter';
      E.easing = 'linear';
      E.stagger = 1 / Math.max(0.5, E.lps);
      E.duration = Math.max(0.008, E.stagger * E.overlap);
    }
  }

  /* -------------------------------------------------------------- schema */

  const EASINGS = ['linear', 'outCubic', 'outQuint', 'inOutCubic', 'outBack', 'outElastic'];
  const UNITS = [['none', 'All at once'], ['letter', 'Per letter'], ['word', 'Per word'], ['line', 'Per line'], ['random', 'Random order']];

  const isWrite = () => S.entrance.mode === 'writeOn';
  const slideMode = () => ['slideUp', 'slideDown', 'slideLeft', 'dropSpin'].includes(S.entrance.mode);

  const SCHEMA = [
    {
      title: 'Text & Layout', open: true, fields: [
        { p: 'text', t: 'textarea', label: 'Subtitle text', hint: 'One line per line. Leave a blank line between blocks if you want to batch-export them as separate files.' },
        { p: 'font.family', t: 'font', label: 'Font' },
        { p: 'font.weight', t: 'weight', label: 'Weight' },
        { p: 'font.size', t: 'range', label: 'Size', min: 20, max: 900, step: 1, unit: 'px' },
        { p: 'font.letterSpacing', t: 'range', label: 'Letter spacing', min: -30, max: 80, step: 0.5, unit: 'px' },
        { p: 'font.lineHeight', t: 'range', label: 'Line height', min: 0.7, max: 2.4, step: 0.01, unit: '×' },
        { p: 'align', t: 'select', label: 'Horizontal', opts: [['left', 'Left'], ['center', 'Center'], ['right', 'Right']] },
        { p: 'vAlign', t: 'select', label: 'Vertical', opts: [['top', 'Top'], ['middle', 'Middle'], ['bottom', 'Bottom']] },
        { p: 'maxWidthPct', t: 'range', label: 'Wrap width', min: 20, max: 100, step: 1, unit: '%' },
        { p: 'offsetX', t: 'range', label: 'Nudge X', min: -2400, max: 2400, step: 1, unit: 'px' },
        { p: 'offsetY', t: 'range', label: 'Nudge Y', min: -2400, max: 2400, step: 1, unit: 'px' },
        { p: 'opacity', t: 'range', label: 'Master opacity', min: 0, max: 1, step: 0.01 }
      ]
    },

    {
      title: 'Colour & Outline', open: true, fields: [
        {
          p: 'fill.mode', t: 'select', label: 'Fill', opts: [
            ['solid', 'Solid colour'], ['gradient', 'Gradient'],
            ['rainbow', 'Rainbow cycle'], ['palette', 'Colour palette']]
        },
        { p: 'fill.color', t: 'color', label: 'Colour', show: () => S.fill.mode === 'solid' },

        { p: 'fill.stops', t: 'colors', label: 'Gradient stops', show: () => S.fill.mode === 'gradient' },
        { p: 'fill.angle', t: 'range', label: 'Gradient angle', min: 0, max: 360, step: 1, unit: '°', show: () => S.fill.mode === 'gradient' },
        { p: 'fill.sweepSpeed', t: 'range', label: 'Gradient sweep', min: -1.5, max: 1.5, step: 0.01, unit: '/s', show: () => S.fill.mode === 'gradient', hint: 'Animates the gradient sliding through the letters. 0 holds it still.' },

        { p: 'fill.unit', t: 'select', label: 'Colour changes', opts: [['letter', 'Per letter'], ['word', 'Per word'], ['line', 'Per line']], show: () => ['rainbow', 'palette'].includes(S.fill.mode) },
        { p: 'fill.hueSpread', t: 'range', label: 'Hue spread', min: 0, max: 120, step: 1, unit: '°', show: () => S.fill.mode === 'rainbow', hint: 'How far apart neighbouring letters sit on the colour wheel.' },
        { p: 'fill.cycleSpeed', t: 'range', label: 'Cycle speed', min: -2, max: 2, step: 0.01, unit: '/s', show: () => ['rainbow', 'palette'].includes(S.fill.mode) },
        { p: 'fill.saturation', t: 'range', label: 'Saturation', min: 0, max: 100, step: 1, unit: '%', show: () => S.fill.mode === 'rainbow' },
        { p: 'fill.lightness', t: 'range', label: 'Lightness', min: 0, max: 100, step: 1, unit: '%', show: () => S.fill.mode === 'rainbow' },

        { p: 'fill.palette', t: 'colors', label: 'Palette', show: () => S.fill.mode === 'palette' },
        { p: 'fill.paletteCycle', t: 'check', label: 'Rotate palette over time', show: () => S.fill.mode === 'palette' },

        { p: 'stroke.enabled', t: 'toggle', label: 'Outline' },
        { p: 'stroke.color', t: 'color', label: 'Outline colour', show: () => S.stroke.enabled },
        { p: 'stroke.width', t: 'range', label: 'Outline thickness', min: 0, max: 80, step: 0.5, unit: 'px', show: () => S.stroke.enabled, hint: 'White text over busy footage wants 8–16px of black outline to stay readable.' }
      ]
    },

    {
      title: 'Shadow & Glow', open: false, fields: [
        { p: 'shadow.enabled', t: 'toggle', label: 'Drop shadow' },
        { p: 'shadow.color', t: 'color', label: 'Shadow colour', show: () => S.shadow.enabled },
        { p: 'shadow.opacity', t: 'range', label: 'Shadow opacity', min: 0, max: 1, step: 0.01, show: () => S.shadow.enabled },
        { p: 'shadow.blur', t: 'range', label: 'Shadow blur', min: 0, max: 120, step: 1, unit: 'px', show: () => S.shadow.enabled, hint: 'Set blur to 0 with an X/Y offset for a hard retro offset shadow.' },
        { p: 'shadow.dx', t: 'range', label: 'Shadow X', min: -80, max: 80, step: 1, unit: 'px', show: () => S.shadow.enabled },
        { p: 'shadow.dy', t: 'range', label: 'Shadow Y', min: -80, max: 80, step: 1, unit: 'px', show: () => S.shadow.enabled },

        { p: 'glow.enabled', t: 'toggle', label: 'Glow' },
        { p: 'glow.color', t: 'color', label: 'Glow colour', show: () => S.glow.enabled },
        { p: 'glow.blur', t: 'range', label: 'Glow size', min: 0, max: 150, step: 1, unit: 'px', show: () => S.glow.enabled },
        { p: 'glow.opacity', t: 'range', label: 'Glow opacity', min: 0, max: 1, step: 0.01, show: () => S.glow.enabled },
        { p: 'glow.intensity', t: 'range', label: 'Glow strength', min: 1, max: 5, step: 1, unit: '×', show: () => S.glow.enabled },

        { p: 'backdrop.enabled', t: 'toggle', label: 'Backdrop bar' },
        { p: 'backdrop.color', t: 'color', label: 'Bar colour', show: () => S.backdrop.enabled },
        { p: 'backdrop.opacity', t: 'range', label: 'Bar opacity', min: 0, max: 1, step: 0.01, show: () => S.backdrop.enabled },
        { p: 'backdrop.padX', t: 'range', label: 'Bar padding X', min: 0, max: 160, step: 1, unit: 'px', show: () => S.backdrop.enabled },
        { p: 'backdrop.padY', t: 'range', label: 'Bar padding Y', min: 0, max: 120, step: 1, unit: 'px', show: () => S.backdrop.enabled },
        { p: 'backdrop.radius', t: 'range', label: 'Bar corner radius', min: 0, max: 80, step: 1, unit: 'px', show: () => S.backdrop.enabled }
      ]
    },

    {
      title: 'Animate In', open: true, fields: [
        {
          p: 'entrance.mode', t: 'select', label: 'Entrance', opts: [
            ['none', 'None — already on screen'],
            ['fade', 'Fade in'],
            ['popIn', 'Pop in (overshoot)'],
            ['scaleIn', 'Scale up'],
            ['slideUp', 'Slide up'],
            ['slideDown', 'Slide down'],
            ['slideLeft', 'Slide in from right'],
            ['dropSpin', 'Drop + spin'],
            ['blurIn', 'Blur into focus'],
            ['writeOn', 'Write on — drawn left to right']]
        },

        { p: 'entrance.lps', t: 'range', label: 'Write speed', min: 2, max: 60, step: 0.5, unit: ' letters/sec', show: isWrite, hint: 'How fast the pen moves. 18 reads as brisk handwriting; 40+ snaps on almost instantly.' },
        { p: 'entrance.overlap', t: 'range', label: 'Stroke overlap', min: 0.3, max: 5, step: 0.05, unit: '×', show: isWrite, hint: '1 = each letter finishes exactly as the next begins. Above 1 several letters draw at once, which flows more naturally.' },
        { p: 'entrance.softness', t: 'range', label: 'Pen edge softness', min: 0, max: 40, step: 0.5, unit: 'px', show: isWrite, hint: 'Feathers the leading edge of the stroke. A little softness hides the hard wipe line.' },

        { p: 'entrance.unit', t: 'select', label: 'Reveal', opts: UNITS, show: () => S.entrance.mode !== 'none' && !isWrite() },
        { p: 'entrance.delay', t: 'range', label: 'Start delay', min: 0, max: 5, step: 0.01, unit: 's', show: () => S.entrance.mode !== 'none' },
        { p: 'entrance.stagger', t: 'range', label: 'Stagger', min: 0, max: 0.6, step: 0.005, unit: 's', show: () => S.entrance.mode !== 'none' && !isWrite(), hint: 'Gap between each letter/word starting.' },
        { p: 'entrance.duration', t: 'range', label: 'Duration', min: 0.02, max: 8, step: 0.01, unit: 's', show: () => S.entrance.mode !== 'none' && !isWrite() },
        { p: 'entrance.easing', t: 'select', label: 'Easing', opts: EASINGS.map(e => [e, e]), show: () => S.entrance.mode !== 'none' && !isWrite() },
        { p: 'entrance.distance', t: 'range', label: 'Travel distance', min: 0, max: 2600, step: 1, unit: 'px', show: slideMode, hint: 'Screen height is 1080 at HD, 2160 at 4K — so ~540 travels from the middle to the top edge, and more than that carries it off screen.' },
        { p: 'entrance.blurAmount', t: 'range', label: 'Start blur', min: 0, max: 60, step: 1, unit: 'px', show: () => S.entrance.mode === 'blurIn' }
      ]
    },

    {
      title: 'Flag Wave', open: false, badge: () => S.wave.enabled, fields: [
        { p: 'wave.enabled', t: 'toggle', label: 'Wave like a flag' },
        { p: 'wave.amplitude', t: 'range', label: 'Wave height', min: 0, max: 180, step: 1, unit: 'px', show: () => S.wave.enabled },
        { p: 'wave.wavelength', t: 'range', label: 'Wave length', min: 40, max: 1400, step: 5, unit: 'px', show: () => S.wave.enabled, hint: 'Distance between crests. Short = rippling silk, long = slow heavy banner.' },
        { p: 'wave.speed', t: 'range', label: 'Wave speed', min: -4, max: 4, step: 0.01, unit: '/s', show: () => S.wave.enabled },
        { p: 'wave.direction', t: 'select', label: 'Direction', opts: [['ltr', 'Travels right'], ['rtl', 'Travels left']], show: () => S.wave.enabled },
        { p: 'wave.pole', t: 'select', label: 'Anchored at', opts: [['left', 'Left edge (flagpole)'], ['right', 'Right edge'], ['none', 'Nowhere — waves evenly']], show: () => S.wave.enabled, hint: 'Anchoring one edge is what makes it read as cloth on a pole rather than a plain wobble.' },
        { p: 'wave.poleCurve', t: 'range', label: 'Anchor falloff', min: 0.2, max: 3, step: 0.05, show: () => S.wave.enabled && S.wave.pole !== 'none' },
        { p: 'wave.secondary', t: 'range', label: 'Second wave', min: 0, max: 1, step: 0.01, show: () => S.wave.enabled, hint: 'Mixes in a slower out-of-sync ripple so the motion never looks like a clean sine.' },
        { p: 'wave.squash', t: 'range', label: 'Perspective squash', min: 0, max: 0.6, step: 0.01, show: () => S.wave.enabled, hint: 'Stretches and compresses each column as it turns away from camera.' },
        { p: 'wave.shading', t: 'range', label: 'Light & shade', min: 0, max: 1, step: 0.01, show: () => S.wave.enabled, hint: 'Darkens the folds and highlights the crests. This is what sells the 3D.' }
      ]
    },

    {
      title: 'Beat Pop', open: false, badge: () => S.pop.enabled, fields: [
        { p: 'pop.enabled', t: 'toggle', label: 'Punch on the beat' },
        { p: 'pop.bpm', t: 'range', label: 'BPM', min: 40, max: 220, step: 1, show: () => S.pop.enabled, hint: "Your track's tempo. Match it and the text locks to the kick." },
        { p: 'pop.everyNBeats', t: 'range', label: 'Hit every', min: 1, max: 8, step: 1, unit: ' beats', show: () => S.pop.enabled },
        { p: 'pop.offset', t: 'range', label: 'Beat offset', min: -2, max: 2, step: 0.005, unit: 's', show: () => S.pop.enabled, hint: 'Nudge if the first beat lands early or late.' },
        { p: 'pop.amount', t: 'range', label: 'Punch size', min: 0, max: 0.8, step: 0.01, show: () => S.pop.enabled },
        { p: 'pop.damping', t: 'range', label: 'Settle speed', min: 1, max: 30, step: 0.5, show: () => S.pop.enabled, hint: 'High = snaps back instantly. Low = keeps wobbling into the next beat.' },
        { p: 'pop.bounce', t: 'range', label: 'Bounciness', min: 0.2, max: 9, step: 0.1, unit: ' Hz', show: () => S.pop.enabled },
        { p: 'pop.tilt', t: 'range', label: 'Tilt', min: 0, max: 3, step: 0.05, show: () => S.pop.enabled },
        { p: 'pop.lift', t: 'range', label: 'Vertical kick', min: 0, max: 120, step: 1, unit: 'px', show: () => S.pop.enabled },
        { p: 'pop.unit', t: 'select', label: 'Applies to', opts: UNITS, show: () => S.pop.enabled },
        { p: 'pop.stagger', t: 'range', label: 'Ripple delay', min: 0, max: 0.3, step: 0.005, unit: 's', show: () => S.pop.enabled && S.pop.unit !== 'none', hint: 'Offsets each letter/word so the punch rolls across the line.' }
      ]
    },

    {
      title: 'Animate Out', open: false, badge: () => S.exit.enabled, fields: [
        { p: 'exit.enabled', t: 'toggle', label: 'Animate out' },
        { p: 'exit.mode', t: 'select', label: 'Exit', opts: [['fade', 'Fade out'], ['shrink', 'Shrink away'], ['riseUp', 'Rise up'], ['fallDown', 'Fall down']], show: () => S.exit.enabled },
        { p: 'exit.time', t: 'range', label: 'Starts at', min: 0, max: 60, step: 0.05, unit: 's', show: () => S.exit.enabled },
        { p: 'exit.unit', t: 'select', label: 'Applies to', opts: UNITS, show: () => S.exit.enabled },
        { p: 'exit.stagger', t: 'range', label: 'Stagger', min: 0, max: 0.6, step: 0.005, unit: 's', show: () => S.exit.enabled },
        { p: 'exit.duration', t: 'range', label: 'Duration', min: 0.05, max: 8, step: 0.01, unit: 's', show: () => S.exit.enabled },
        { p: 'exit.distance', t: 'range', label: 'Travel distance', min: 0, max: 2600, step: 1, unit: 'px', show: () => S.exit.enabled && ['riseUp', 'fallDown'].includes(S.exit.mode), hint: 'How far it travels. ~540 lifts a centred word to the top edge at HD (1080 at 4K); go higher to carry it right off screen.' }
      ]
    },

    {
      title: 'Canvas & Timing', open: false, fields: [
        { p: '_size', t: 'size', label: 'Resolution' },
        { p: 'fps', t: 'select', label: 'Frame rate', opts: [[23.976, '23.976'], [24, '24'], [25, '25'], [29.97, '29.97'], [30, '30'], [50, '50'], [59.94, '59.94'], [60, '60']], num: true },
        { p: 'duration', t: 'range', label: 'Clip length', min: 0.3, max: 60, step: 0.1, unit: 's' }
      ]
    }
  ];

  /* ------------------------------------------------------- build controls */

  const bound = [];   // {field, node, apply()}

  function buildControls() {
    const root = $('#controls');
    root.innerHTML = '';
    bound.length = 0;

    for (const sec of SCHEMA) {
      const d = el('details', 'section');
      d.open = !!sec.open;
      const sum = el('summary');
      sum.appendChild(el('span', null, sec.title));
      if (sec.badge) {
        const b = el('span', 'badge', 'on');
        sum.appendChild(b);
        bound.push({ badge: true, node: b, fn: sec.badge });
      }
      d.appendChild(sum);
      const body = el('div', 'body');
      for (const f of sec.fields) body.appendChild(buildField(f));
      d.appendChild(body);
      root.appendChild(d);
    }
    refresh();
  }

  function buildField(f) {
    const wrap = el('div', 'field');
    wrap.dataset.path = f.p;

    const commit = () => { applyDerived(); markCustom(); refresh(); invalidateAndDraw(); };

    let input, valSpan;

    const header = (withVal) => {
      const lab = el('label', 'lbl');
      lab.appendChild(el('span', null, f.label));
      if (withVal) { valSpan = el('span', 'val'); lab.appendChild(valSpan); }
      wrap.appendChild(lab);
      return lab;
    };

    switch (f.t) {

      case 'toggle': {
        const l = el('label', 'toggle');
        input = document.createElement('input');
        input.type = 'checkbox';
        l.appendChild(input);
        l.appendChild(el('span', null, f.label));
        wrap.appendChild(l);
        input.addEventListener('change', () => { setP(S, f.p, input.checked); commit(); });
        bound.push({ f, wrap, apply: () => { input.checked = !!getP(S, f.p); } });
        break;
      }

      case 'check': {
        const l = el('label', 'inline');
        input = document.createElement('input');
        input.type = 'checkbox';
        l.appendChild(input);
        l.appendChild(el('span', null, f.label));
        wrap.appendChild(l);
        input.addEventListener('change', () => { setP(S, f.p, input.checked); commit(); });
        bound.push({ f, wrap, apply: () => { input.checked = !!getP(S, f.p); } });
        break;
      }

      case 'range': {
        header(true);
        input = document.createElement('input');
        input.type = 'range';
        input.min = f.min; input.max = f.max; input.step = f.step;
        wrap.appendChild(input);
        const show = v => {
          const dec = f.step < 0.1 ? (f.step < 0.01 ? 3 : 2) : (f.step < 1 ? 1 : 0);
          valSpan.textContent = Number(v).toFixed(dec) + (f.unit || '');
        };
        input.addEventListener('input', () => {
          const v = parseFloat(input.value);
          setP(S, f.p, v); show(v); applyDerived(); markCustom(); invalidateAndDraw();
        });
        input.addEventListener('change', () => refresh());
        bound.push({ f, wrap, apply: () => { const v = getP(S, f.p); input.value = v; show(v); } });
        break;
      }

      case 'color': {
        header(false);
        input = document.createElement('input');
        input.type = 'color';
        wrap.appendChild(input);
        input.addEventListener('input', () => { setP(S, f.p, input.value); markCustom(); invalidateAndDraw(); });
        bound.push({ f, wrap, apply: () => { input.value = toHex(getP(S, f.p)); } });
        break;
      }

      case 'select': {
        header(false);
        input = document.createElement('select');
        for (const [v, t] of (f.opts || [])) {
          const o = document.createElement('option');
          o.value = v; o.textContent = t;
          input.appendChild(o);
        }
        wrap.appendChild(input);
        input.addEventListener('change', () => {
          setP(S, f.p, f.num ? parseFloat(input.value) : input.value);
          commit();
        });
        bound.push({ f, wrap, apply: () => { input.value = getP(S, f.p); } });
        break;
      }

      case 'text': {
        header(false);
        input = document.createElement('input');
        input.type = 'text';
        wrap.appendChild(input);
        input.addEventListener('input', () => { setP(S, f.p, input.value); markCustom(); invalidateAndDraw(); });
        bound.push({ f, wrap, apply: () => { input.value = getP(S, f.p); } });
        break;
      }

      case 'textarea': {
        header(false);
        input = document.createElement('textarea');
        input.rows = 4;
        wrap.appendChild(input);
        input.addEventListener('input', () => { setP(S, f.p, input.value); markCustom(); invalidateAndDraw(); });
        bound.push({ f, wrap, apply: () => { if (document.activeElement !== input) input.value = getP(S, f.p); } });
        break;
      }

      case 'font': {
        header(false);
        input = document.createElement('select');
        const cats = [...new Set(window.FONTS.map(x => x.cat))];
        for (const c of cats) {
          const g = document.createElement('optgroup');
          g.label = c;
          for (const ft of window.FONTS.filter(x => x.cat === c)) {
            const o = document.createElement('option');
            o.value = ft.name; o.textContent = ft.name;
            g.appendChild(o);
          }
          input.appendChild(g);
        }
        wrap.appendChild(input);
        const note = el('div', 'hint');
        wrap.appendChild(note);
        input.addEventListener('change', async () => {
          const name = input.value;
          setP(S, 'font.family', name);
          const def = window.FONTS.find(x => x.name === name);
          if (def && !def.w.includes(S.font.weight)) {
            S.font.weight = def.w.includes(400) ? 400 : def.w[def.w.length - 1];
          }
          markCustom(); refresh();
          await ensureFont();
          invalidateAndDraw();
        });
        bound.push({
          f, wrap, apply: () => {
            input.value = S.font.family;
            const def = window.FONTS.find(x => x.name === S.font.family);
            note.textContent = def ? def.note : '';
          }
        });
        break;
      }

      case 'weight': {
        header(false);
        input = document.createElement('select');
        wrap.appendChild(input);
        input.addEventListener('change', async () => {
          S.font.weight = parseInt(input.value, 10);
          markCustom(); await ensureFont(); invalidateAndDraw();
        });
        bound.push({
          f, wrap, apply: () => {
            const def = window.FONTS.find(x => x.name === S.font.family) || { w: [400] };
            input.innerHTML = '';
            for (const w of def.w) {
              const o = document.createElement('option');
              o.value = w; o.textContent = w + (w === 400 ? ' (regular)' : w >= 800 ? ' (black)' : w >= 700 ? ' (bold)' : '');
              input.appendChild(o);
            }
            input.value = S.font.weight;
            wrap.classList.toggle('hidden', def.w.length < 2);
          }
        });
        break;
      }

      case 'size': {
        header(false);
        input = document.createElement('select');
        for (const [label, wh] of Object.entries(window.CANVAS_SIZES)) {
          const o = document.createElement('option');
          o.value = wh.join('x'); o.textContent = label;
          input.appendChild(o);
        }
        wrap.appendChild(input);
        input.addEventListener('change', () => {
          const [w, h] = input.value.split('x').map(Number);
          S.width = w; S.height = h;
          markCustom(); syncCanvasSize(); invalidateAndDraw();
        });
        bound.push({ f, wrap, apply: () => { input.value = `${S.width}x${S.height}`; } });
        break;
      }

      case 'colors': {
        header(false);
        const box = el('div', 'swatches');
        wrap.appendChild(box);
        const rebuild = () => {
          box.innerHTML = '';
          const arr = getP(S, f.p) || [];
          arr.forEach((c, i) => {
            const ci = document.createElement('input');
            ci.type = 'color'; ci.value = toHex(c);
            ci.addEventListener('input', () => { arr[i] = ci.value; markCustom(); invalidateAndDraw(); });
            ci.addEventListener('contextmenu', e => {
              e.preventDefault();
              if (arr.length > 2) { arr.splice(i, 1); rebuild(); markCustom(); invalidateAndDraw(); }
            });
            box.appendChild(ci);
          });
          const add = el('button', null, '+');
          add.title = 'Add colour  (right-click a swatch to remove it)';
          add.addEventListener('click', () => {
            arr.push(arr[arr.length - 1] || '#ffffff'); rebuild(); markCustom(); invalidateAndDraw();
          });
          box.appendChild(add);
          const rm = el('button', null, '−');
          rm.title = 'Remove last colour';
          rm.addEventListener('click', () => {
            if (arr.length > 2) { arr.pop(); rebuild(); markCustom(); invalidateAndDraw(); }
          });
          box.appendChild(rm);
        };
        bound.push({ f, wrap, apply: rebuild });
        break;
      }
    }

    if (f.hint) {
      const h = el('div', 'hint', f.hint);
      wrap.appendChild(h);
    }
    return wrap;
  }

  function toHex(c) {
    if (!c) return '#ffffff';
    if (c[0] === '#') return c.length === 4 ? '#' + c.slice(1).split('').map(x => x + x).join('') : c.slice(0, 7);
    const m = c.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
    if (m) return '#' + [1, 2, 3].map(i => (+m[i]).toString(16).padStart(2, '0')).join('');
    return '#ffffff';
  }

  function refresh() {
    for (const b of bound) {
      if (b.badge) {
        const on = b.fn();
        b.node.textContent = on ? 'on' : 'off';
        b.node.classList.toggle('off', !on);
        continue;
      }
      if (b.f.show) b.wrap.classList.toggle('hidden', !b.f.show());
      try { b.apply(); } catch (e) { /* field not applicable yet */ }
    }
    $('#tEnd').textContent = S.duration.toFixed(2);
    $('#scrub').max = S.duration;
  }

  /* --------------------------------------------------------------- fonts */

  const loadedFonts = new Set();
  async function ensureFont() {
    const key = `${S.font.weight} ${S.font.family}`;
    if (loadedFonts.has(key)) return;
    try {
      await document.fonts.load(`${S.font.weight} 100px "${S.font.family}"`, 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789');
      await document.fonts.ready;
      loadedFonts.add(key);
    } catch (e) { /* fall back to Impact */ }
    Engine.invalidate();
  }

  function injectFontCss() {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    if (ENV.localFonts) {
      link.href = '/fonts/fonts.css';           // offline pack, if the user ran download_fonts.py
    } else {
      link.href = window.googleFontsHref();     // straight from Google Fonts
    }
    link.addEventListener('error', () => {
      if (link.href.indexOf('/fonts/') !== -1) {
        const alt = document.createElement('link');
        alt.rel = 'stylesheet'; alt.href = window.googleFontsHref();
        document.head.appendChild(alt);
      } else {
        notice('warn', 'Could not reach Google Fonts, so only system fonts are available. Run <code>python download_fonts.py</code> once to install the font pack locally, then reload.');
      }
    });
    document.head.appendChild(link);
  }

  /* ------------------------------------------------------------- preview */

  const canvas = $('#preview');
  let playing = false, tNow = 0, lastTs = 0, dirty = true;
  let frameTimes = [];

  function invalidateAndDraw() { Engine.invalidate(); dirty = true; }

  function syncCanvasSize() {
    canvas.width = S.width; canvas.height = S.height;
    applyZoom();
  }

  /* The holder locks the aspect ratio and carries the checkerboard, so fitting
     and zooming are pure CSS — there's nothing to keep in sync by hand, and
     the background can't drift away from the canvas. */
  function applyZoom() {
    const holder = $('#canvasHolder');
    const z = $('#zoomSelect').value;
    if (z === 'fit') {
      holder.classList.remove('zoomed');
      canvas.style.width = ''; canvas.style.height = '';
    } else {
      holder.classList.add('zoomed');
      const k = parseFloat(z);
      canvas.style.width = Math.round(S.width * k) + 'px';
      canvas.style.height = Math.round(S.height * k) + 'px';
    }
  }

  function draw() {
    const t0 = performance.now();
    Engine.renderFrame(canvas, S, tNow, $('#qualitySelect').value);
    const dt = performance.now() - t0;
    frameTimes.push(dt);
    if (frameTimes.length > 20) frameTimes.shift();
    const avg = frameTimes.reduce((a, b) => a + b, 0) / frameTimes.length;
    $('#fpsReadout').textContent = `${avg.toFixed(1)} ms/f`;
    $('#tNow').textContent = tNow.toFixed(2);
    $('#scrub').value = tNow;
    dirty = false;
  }

  function tick(ts) {
    if (playing) {
      const dt = lastTs ? (ts - lastTs) / 1000 : 0;
      tNow += dt;
      if (tNow >= S.duration) {
        if ($('#loopChk').checked) tNow = 0;
        else { tNow = S.duration; setPlaying(false); }
      }
      dirty = true;
    }
    lastTs = ts;
    if (dirty) draw();
    requestAnimationFrame(tick);
  }

  function setPlaying(v) {
    playing = v; lastTs = 0;
    $('#btnPlay').textContent = v ? '❚❚' : '▶';
  }

  /* -------------------------------------------------------------- export */

  let cancelExport = false;

  function textBlocks() {
    return S.text.split(/\n\s*\n/).map(s => s.trim()).filter(Boolean);
  }

  async function doExport() {
    const codec = $('#codecSelect').value;
    if (codec !== 'png' && !ENV.ffmpeg) {
      return notice('err',
        'ffmpeg isn\'t installed, so .mov export is unavailable. Either install it with ' +
        '<code>winget install Gyan.FFmpeg</code> (then restart this app), drop <code>ffmpeg.exe</code> into the ' +
        '<code>bin</code> folder, or switch Format to <b>PNG sequence</b> — After Effects imports those natively.');
    }

    await ensureFont();

    const baseName = ($('#fileName').value || 'subtitle').trim();
    const batch = $('#batchChk').checked;
    const blocks = batch ? textBlocks() : [null];
    if (batch && blocks.length === 0) return notice('err', 'Nothing to export — the text box is empty.');

    cancelExport = false;
    setPlaying(false);
    setBusy(true);
    $('#progressWrap').hidden = false;
    $('#notice').hidden = true;

    const savedText = S.text;
    const results = [];
    const t0 = performance.now();

    try {
      for (let bi = 0; bi < blocks.length; bi++) {
        if (cancelExport) break;
        if (batch) { S.text = blocks[bi]; Engine.invalidate(); }
        const name = batch ? `${baseName}_${String(bi + 1).padStart(2, '0')}` : baseName;
        const r = await exportOne(name, codec, bi, blocks.length);
        if (!r) break;
        results.push(r);
      }
    } finally {
      S.text = savedText;
      Engine.invalidate();
      setBusy(false);
      $('#progressWrap').hidden = true;
      dirty = true;
    }

    if (cancelExport) return notice('warn', 'Export cancelled.');
    if (!results.length) return;

    const secs = ((performance.now() - t0) / 1000).toFixed(1);
    const ok = results.filter(r => r.ok);
    const bad = results.filter(r => !r.ok);

    if (bad.length) {
      notice('err', `${bad.length} of ${results.length} exports failed.<span class="path">${
        (bad[0].error || '') + (bad[0].log ? '\n' + bad[0].log : '')}</span>`);
      return;
    }

    const totalMB = ok.reduce((a, r) => a + (r.size || 0), 0) / 1048576;
    const label = ok.length === 1
      ? `Exported in ${secs}s${totalMB ? ` · ${totalMB.toFixed(1)} MB` : ''}`
      : `Exported ${ok.length} files in ${secs}s${totalMB ? ` · ${totalMB.toFixed(1)} MB` : ''}`;
    notice('ok',
      `<b>${label}</b>` +
      `<span class="path">${ok.map(r => r.path).join('<br>')}</span>` +
      `<button class="ghost small" id="btnOpenFolder">Open folder</button>` +
      `<div class="hint" style="margin-top:8px">In After Effects: File &gt; Import &gt; File, drop it on the timeline above your footage. ` +
      `Alpha is already straight/premultiplied-correct — choose <b>Straight – Unmatted</b> if AE asks.</div>`);
    const b = $('#btnOpenFolder');
    if (b) b.addEventListener('click', () => fetch('/api/open', { method: 'POST' }));
  }

  async function exportOne(name, codec, blockIdx, blockCount) {
    const total = Math.max(1, Math.round(S.duration * S.fps));

    const start = await fetch('/api/export/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, codec, fps: S.fps, frames: total, width: S.width, height: S.height })
    }).then(r => r.json());

    if (!start.ok) { notice('err', 'Could not start the encoder: ' + (start.error || 'unknown')); return null; }

    const cv = document.createElement('canvas');
    cv.width = S.width; cv.height = S.height;

    const t0 = performance.now();
    for (let f = 0; f < total; f++) {
      if (cancelExport) {
        await fetch(`/api/export/cancel?id=${start.id}`, { method: 'POST' });
        return null;
      }

      Engine.renderFrame(cv, S, f / S.fps, 'full');
      const blob = await new Promise(res => cv.toBlob(res, 'image/png'));
      const resp = await fetch(`/api/export/frame?id=${start.id}&n=${f}`, { method: 'POST', body: blob })
        .then(r => r.json());
      if (!resp.ok) { notice('err', 'Encoder stopped: ' + (resp.error || 'unknown')); return null; }

      if (f % 2 === 0 || f === total - 1) {
        const done = (f + 1) / total;
        const overall = blockCount > 1 ? (blockIdx + done) / blockCount : done;
        $('#pfill').style.width = (overall * 100).toFixed(1) + '%';
        const elapsed = (performance.now() - t0) / 1000;
        const rate = (f + 1) / elapsed;
        const left = (total - f - 1) / Math.max(0.001, rate);
        $('#pText').textContent =
          (blockCount > 1 ? `Clip ${blockIdx + 1}/${blockCount} · ` : '') +
          `frame ${f + 1}/${total} · ${rate.toFixed(1)} fps · ~${left < 1 ? '0' : Math.ceil(left)}s left`;
        await new Promise(r => setTimeout(r, 0));   // let the UI breathe
      }
    }

    return await fetch(`/api/export/finish?id=${start.id}`, { method: 'POST' }).then(r => r.json());
  }

  function setBusy(v) {
    $('#btnExport').disabled = v;
    $('#panel').style.pointerEvents = v ? 'none' : '';
    $('#panel').style.opacity = v ? '.55' : '';
  }

  function notice(kind, html) {
    const n = $('#notice');
    n.className = 'notice ' + kind;
    n.innerHTML = html;
    n.hidden = false;
  }

  /* --------------------------------------------------------------- wiring */

  function markCustom() { $('#presetSelect').value = ''; }

  function applyPreset(name) {
    const p = window.PRESETS[name];
    if (!p) return;
    const keepText = S.text, w = S.width, h = S.height, fps = S.fps, dur = S.duration;
    S = deepMerge(clone(window.DEFAULTS), p);
    S.text = keepText; S.width = w; S.height = h; S.fps = fps;
    // Only take the clip length from the preset if it deliberately sets one —
    // presets with an exit animation need room for it to play out.
    S.duration = Object.prototype.hasOwnProperty.call(p, 'duration') ? p.duration : dur;
    if (tNow > S.duration) tNow = 0;
    applyDerived();
    ensureFont().then(() => { Engine.invalidate(); dirty = true; });
    syncCanvasSize();
    refresh();
    Engine.invalidate();
    dirty = true;
  }

  async function init() {
    try { ENV = await fetch('/api/env').then(r => r.json()); } catch (e) { /* offline */ }

    injectFontCss();

    // codec dropdown
    const cs = $('#codecSelect');
    for (const [k, label] of Object.entries(ENV.codecs || { prores4444: 'ProRes 4444' })) {
      const o = document.createElement('option');
      o.value = k; o.textContent = label;
      if (!ENV.ffmpeg && k !== 'png') { o.disabled = true; o.textContent = label + '  — needs ffmpeg'; }
      cs.appendChild(o);
    }
    cs.value = ENV.ffmpeg ? 'prores4444' : 'png';

    if (!ENV.ffmpeg) {
      notice('warn',
        '<b>ffmpeg not found</b> — PNG-sequence export works right now, and After Effects imports those fine. ' +
        'For a single transparent .mov, install ffmpeg with <code>winget install Gyan.FFmpeg</code> and restart this app.');
    }

    // presets dropdown
    const ps = $('#presetSelect');
    for (const k of Object.keys(window.PRESETS)) {
      const o = document.createElement('option');
      o.value = k; o.textContent = k;
      ps.appendChild(o);
    }
    ps.addEventListener('change', () => { if (ps.value) applyPreset(ps.value); });

    buildControls();
    applyDerived();
    syncCanvasSize();
    await ensureFont();
    Engine.invalidate();
    dirty = true;
    requestAnimationFrame(tick);

    /* transport */
    $('#btnPlay').addEventListener('click', () => setPlaying(!playing));
    $('#btnStart').addEventListener('click', () => { tNow = 0; dirty = true; });
    $('#scrub').addEventListener('input', e => { tNow = parseFloat(e.target.value); setPlaying(false); dirty = true; });
    $('#qualitySelect').addEventListener('change', () => { dirty = true; });

    document.addEventListener('keydown', e => {
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) return;
      if (e.code === 'Space') { e.preventDefault(); setPlaying(!playing); }
      if (e.code === 'Home') { tNow = 0; dirty = true; }
      if (e.code === 'Tab') { e.preventDefault(); $('#btnPanel').click(); }
    });

    /* preview background */
    const setHolderBg = kind => {
      const h = $('#canvasHolder');
      h.className = 'canvasholder ' + (kind === 'checker' ? '' : kind)
        + (h.classList.contains('zoomed') ? ' zoomed' : '');
    };
    $('#bgPicker').addEventListener('click', e => {
      const b = e.target.closest('button'); if (!b) return;
      if (b.dataset.bg === 'image') return $('#fileBg').click();
      [...$('#bgPicker').children].forEach(x => x.classList.toggle('on', x === b));
      setHolderBg(b.dataset.bg);
    });
    $('#fileBg').addEventListener('change', e => {
      const f = e.target.files[0]; if (!f) return;
      const url = URL.createObjectURL(f);
      $('#canvasHolder').style.setProperty('--bgimg', `url("${url}")`);
      setHolderBg('image');
      [...$('#bgPicker').children].forEach(x => x.classList.toggle('on', x.dataset.bg === 'image'));
      e.target.value = '';
    });

    /* zoom + panel collapse */
    $('#zoomSelect').addEventListener('change', applyZoom);
    const togglePanel = () => {
      const collapsed = $('#layout').classList.toggle('collapsed');
      $('#btnPanel').title = collapsed ? 'Show the controls  (Tab)' : 'Hide the controls for a bigger preview  (Tab)';
    };
    $('#btnPanel').addEventListener('click', togglePanel);

    /* export */
    $('#btnExport').addEventListener('click', doExport);
    $('#btnCancel').addEventListener('click', () => { cancelExport = true; });

    /* save / load / reset */
    $('#btnSaveSettings').addEventListener('click', () => {
      const blob = new Blob([JSON.stringify(S, null, 2)], { type: 'application/json' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = (($('#fileName').value || 'look') + '.json');
      a.click();
    });
    $('#btnLoadSettings').addEventListener('click', () => $('#fileSettings').click());
    $('#fileSettings').addEventListener('change', async e => {
      const f = e.target.files[0]; if (!f) return;
      try {
        S = deepMerge(clone(window.DEFAULTS), JSON.parse(await f.text()));
        applyDerived(); syncCanvasSize(); await ensureFont();
        refresh(); Engine.invalidate(); dirty = true; markCustom();
      } catch (err) { notice('err', 'That file didn\'t parse as a saved look.'); }
      e.target.value = '';
    });
    $('#btnReset').addEventListener('click', () => {
      S = clone(window.DEFAULTS);
      applyDerived(); syncCanvasSize(); refresh();
      Engine.invalidate(); dirty = true; markCustom();
    });

  }

  init();
})();
