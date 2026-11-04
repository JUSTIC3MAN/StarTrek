/* ============================================================================
   presets.js  —  font library, default settings, and one-click looks
   ========================================================================== */

/* ------------------------------------------------------------------- fonts
   All SIL Open Font License or Apache 2.0 — free for commercial use, safe to
   ship in a released music video. `w` lists the weights actually available;
   the UI locks the weight control to these so you never get a fake-bold.     */

const FONTS = [
  // --- heavy condensed: the lyric-video workhorse ---
  { name: 'Anton',               w: [400],                     cat: 'Condensed', note: 'The default lyric-video face. Tall, tight, unmissable.' },
  { name: 'Bebas Neue',          w: [400],                     cat: 'Condensed', note: 'All-caps, clean, slightly lighter than Anton.' },
  { name: 'Oswald',              w: [300,400,500,600,700],     cat: 'Condensed', note: 'Condensed with real weight range. Very legible small.' },
  { name: 'Fjalla One',          w: [400],                     cat: 'Condensed', note: 'Warmer, slightly humanist condensed.' },
  { name: 'Teko',                w: [400,500,600,700],         cat: 'Condensed', note: 'Squared-off, sporty, tall x-height.' },
  { name: 'Staatliches',         w: [400],                     cat: 'Condensed', note: 'Poster/stencil energy, punk flyer.' },
  { name: 'Big Shoulders Display', w: [400,600,700,800,900],   cat: 'Condensed', note: 'Very tall industrial condensed. Great with wide letter spacing.' },

  // --- wide + heavy: impact and hooks ---
  { name: 'Archivo Black',       w: [400],                     cat: 'Heavy',     note: 'Wide, grotesque, brutal weight. Great for a hook line.' },
  { name: 'Montserrat',          w: [700,800,900],             cat: 'Heavy',     note: 'Geometric, friendly, modern. Safe everywhere.' },
  { name: 'Inter',               w: [700,800,900],             cat: 'Heavy',     note: 'Neutral UI grotesque. Reads as clean and current.' },
  { name: 'Poppins',             w: [600,700,800,900],         cat: 'Heavy',     note: 'Perfect circles, geometric. Pop and afrobeats.' },
  { name: 'Chivo',               w: [700,800,900],             cat: 'Heavy',     note: 'Grotesque with attitude, slightly quirky.' },
  { name: 'Syne',                w: [700,800],                 cat: 'Heavy',     note: 'Weird-wide contemporary. Art-school electronic.' },
  { name: 'Unbounded',           w: [600,700,800,900],         cat: 'Heavy',     note: 'Extended geometric. Very 2020s.' },
  { name: 'Passion One',         w: [400,700,900],             cat: 'Heavy',     note: 'Tight, punchy headline face. Set it huge.' },

  // --- slab + display: character ---
  { name: 'Alfa Slab One',       w: [400],                     cat: 'Display',   note: 'Fat slab serif. Americana, rock, country.' },
  { name: 'Ultra',               w: [400],                     cat: 'Display',   note: 'Heavy slab, 70s record sleeve.' },
  { name: 'Titan One',           w: [400],                     cat: 'Display',   note: 'Rounded and chunky, cartoon energy.' },
  { name: 'Lilita One',          w: [400],                     cat: 'Display',   note: 'Soft heavy display, friendly.' },
  { name: 'Bowlby One',          w: [400],                     cat: 'Display',   note: 'Round, bubbly, very bold.' },
  { name: 'Luckiest Guy',        w: [400],                     cat: 'Display',   note: 'Comic-book bounce. Pairs great with beat pop.' },
  { name: 'Shrikhand',           w: [400],                     cat: 'Display',   note: 'High-contrast display with real personality.' },
  { name: 'Sigmar One',          w: [400],                     cat: 'Display',   note: 'Thick outlined-looking display.' },
  { name: 'Black Ops One',       w: [400],                     cat: 'Display',   note: 'Military stencil. Drill and trap.' },
  { name: 'Righteous',           w: [400],                     cat: 'Display',   note: 'Art-deco geometric, retro-modern. Lovely with write-on.' },

  // --- retro / techno ---
  { name: 'Bungee',              w: [400],                     cat: 'Retro',     note: 'Signage-inspired, urban, blocky.' },
  { name: 'Bungee Inline',       w: [400],                     cat: 'Retro',     note: 'Same but with an inline cut — reads great big.' },
  { name: 'Monoton',             w: [400],                     cat: 'Retro',     note: 'Neon-tube lines. Turn Glow on with this one.' },
  { name: 'Rubik Mono One',      w: [400],                     cat: 'Retro',     note: 'Monospaced heavy. Vaporwave, hyperpop.' }
];

/** Build the Google Fonts CSS URL for everything above. */
function googleFontsHref() {
  const parts = FONTS.map(f => {
    const fam = f.name.replace(/ /g, '+');
    const ws = f.w.slice().sort((a, b) => a - b);
    return ws.length > 1 ? `family=${fam}:wght@${ws.join(';')}` : `family=${fam}`;
  });
  return 'https://fonts.googleapis.com/css2?' + parts.join('&') + '&display=block';
}

/* ---------------------------------------------------------------- defaults */

const DEFAULTS = {
  width: 1920, height: 1080, fps: 30, duration: 4.0,

  text: "THIS IS THE\nHOOK LINE",

  font: { family: 'Anton', size: 170, weight: 400, italic: false, letterSpacing: 0, lineHeight: 1.05 },

  align: 'center', vAlign: 'middle', offsetX: 0, offsetY: 0, maxWidthPct: 80,
  opacity: 1,

  fill: {
    mode: 'solid',                 // solid | gradient | rainbow | palette
    color: '#ffffff',
    stops: ['#ff2e63', '#ffd166', '#06d6a0'],
    angle: 90, sweepSpeed: 0,
    baseHue: 0, hueSpread: 18, cycleSpeed: 0.25, saturation: 95, lightness: 60,
    palette: ['#ff2e63', '#ffd166', '#06d6a0', '#4cc9f0'],
    paletteCycle: false,
    unit: 'letter'                 // letter | word | line
  },

  stroke: { enabled: true, color: '#000000', width: 9 },
  shadow: { enabled: true, color: '#000000', opacity: 0.55, blur: 20, dx: 0, dy: 8 },
  glow: { enabled: false, color: '#00e5ff', blur: 34, opacity: 0.9, intensity: 2 },
  backdrop: { enabled: false, color: '#000000', opacity: 0.55, padX: 30, padY: 14, radius: 14 },

  entrance: {
    mode: 'popIn',                 // none|fade|popIn|scaleIn|slideUp|slideDown|slideLeft|dropSpin|blurIn|writeOn
    unit: 'word',                  // letter | word | line | none | random
    delay: 0.10, stagger: 0.07, duration: 0.45,
    easing: 'outCubic',
    distance: 70, blurAmount: 16, softness: 6,
    // write-on convenience controls; stagger/duration are derived from these
    lps: 18,                       // letters drawn per second
    overlap: 1.4                   // >1 = next letter starts before the last finishes
  },

  exit: { enabled: false, mode: 'fade', unit: 'word', time: 3.3, stagger: 0.03, duration: 0.4, distance: 400 },

  wave: {
    enabled: false,
    amplitude: 24, wavelength: 340, speed: 0.7, secondary: 0.35,
    squash: 0.12, shading: 0.28,
    pole: 'left', poleCurve: 1.0, direction: 'ltr'
  },

  pop: {
    enabled: false,
    bpm: 120, everyNBeats: 1, offset: 0,
    unit: 'none', stagger: 0,
    amount: 0.18, damping: 8, bounce: 3, tilt: 0, lift: 0
  }
};

/* ----------------------------------------------------------------- presets
   Each preset is a deep-merge patch over DEFAULTS. Your text and canvas size
   are never touched, so you can audition looks against your actual lyrics.
   A preset only changes clip length if it explicitly sets `duration`.        */

const PRESETS = {

  /* ------------------------------------------------------------ essentials */

  'Clean Caption': {
    font: { family: 'Anton', size: 150 },
    fill: { mode: 'solid', color: '#ffffff' },
    stroke: { enabled: true, color: '#000000', width: 8 },
    shadow: { enabled: true, blur: 22, dy: 10, opacity: 0.6 },
    entrance: { mode: 'fade', unit: 'word', stagger: 0.05, duration: 0.3 },
    wave: { enabled: false }, pop: { enabled: false }, exit: { enabled: false }
  },

  'Bold Impact': {
    font: { family: 'Anton', size: 190, letterSpacing: 2, lineHeight: 1.0 },
    fill: { mode: 'solid', color: '#ffffff' },
    stroke: { enabled: true, color: '#000000', width: 15 },
    shadow: { enabled: true, color: '#000000', blur: 0, dx: 0, dy: 15, opacity: 0.9 },
    entrance: { mode: 'popIn', unit: 'word', delay: 0.05, stagger: 0.07, duration: 0.4, easing: 'outBack' },
    wave: { enabled: false }, pop: { enabled: false }, exit: { enabled: false }
  },

  /* ---------------------------------------------------------------- rhythm */

  'Trap Punch': {
    font: { family: 'Archivo Black', size: 165, letterSpacing: 1 },
    fill: { mode: 'solid', color: '#ffffff' },
    stroke: { enabled: true, color: '#000000', width: 13 },
    shadow: { enabled: true, color: '#000000', blur: 28, dy: 12, opacity: 0.7 },
    entrance: { mode: 'popIn', unit: 'word', stagger: 0.05, duration: 0.32, easing: 'outBack' },
    pop: { enabled: true, bpm: 140, amount: 0.26, damping: 11, bounce: 3.6, unit: 'none', tilt: 0.25 },
    exit: { enabled: false }
  },

  'Bass Drop': {
    font: { family: 'Passion One', weight: 900, size: 235, letterSpacing: -2, lineHeight: 0.95 },
    fill: { mode: 'gradient', stops: ['#ffffff', '#c3d0e0', '#ffffff'], angle: 90, sweepSpeed: 0 },
    stroke: { enabled: true, color: '#05060a', width: 14 },
    shadow: { enabled: true, color: '#00e5ff', blur: 55, dx: 0, dy: 0, opacity: 0.6 },
    entrance: { mode: 'scaleIn', unit: 'line', stagger: 0.1, duration: 0.35, easing: 'outQuint' },
    pop: { enabled: true, bpm: 128, everyNBeats: 4, amount: 0.5, damping: 5.5, bounce: 1.8, unit: 'none', lift: 28 },
    exit: { enabled: false },
    duration: 6
  },

  'Hyperpop': {
    font: { family: 'Bungee', size: 140, letterSpacing: 4 },
    fill: { mode: 'rainbow', unit: 'letter', hueSpread: 34, cycleSpeed: 0.55, saturation: 100, lightness: 64 },
    stroke: { enabled: true, color: '#12002b', width: 11 },
    shadow: { enabled: false },
    glow: { enabled: true, color: '#ff2bd6', blur: 38, opacity: 0.85, intensity: 2 },
    entrance: { mode: 'popIn', unit: 'letter', stagger: 0.028, duration: 0.34, easing: 'outBack' },
    pop: { enabled: true, bpm: 160, amount: 0.2, damping: 12, bounce: 4.5, unit: 'letter', stagger: 0.015, tilt: 0.5 },
    exit: { enabled: false }
  },

  'Retro Bounce': {
    font: { family: 'Rubik Mono One', size: 120, letterSpacing: 2 },
    fill: { mode: 'palette', palette: ['#ff6b9d', '#c56cf0', '#4cc9f0', '#ffd166'], unit: 'letter' },
    stroke: { enabled: true, color: '#1a0033', width: 10 },
    shadow: { enabled: true, blur: 0, dx: 7, dy: 9, opacity: 1, color: '#1a0033' },
    entrance: { mode: 'dropSpin', unit: 'letter', stagger: 0.04, duration: 0.6, distance: 140, easing: 'outBack' },
    pop: { enabled: true, bpm: 140, amount: 0.14, damping: 10, bounce: 3.5, unit: 'letter', stagger: 0.02 },
    exit: { enabled: false }
  },

  'Drill Stencil': {
    font: { family: 'Black Ops One', size: 150, letterSpacing: 3 },
    fill: { mode: 'solid', color: '#f5f5f5' },
    stroke: { enabled: true, color: '#0a0a0a', width: 10 },
    shadow: { enabled: true, color: '#c1121f', blur: 0, dx: 10, dy: 10, opacity: 1 },
    entrance: { mode: 'slideLeft', unit: 'word', stagger: 0.06, duration: 0.42, distance: 260, easing: 'outQuint' },
    pop: { enabled: true, bpm: 144, everyNBeats: 2, amount: 0.12, damping: 14, bounce: 4, unit: 'none' },
    exit: { enabled: false }
  },

  /* ------------------------------------------------------------------ rise */

  'Rise & Vanish': {
    font: { family: 'Big Shoulders Display', weight: 800, size: 215, letterSpacing: 10 },
    fill: { mode: 'solid', color: '#ffffff' },
    stroke: { enabled: true, color: '#000000', width: 6 },
    shadow: { enabled: true, color: '#000000', blur: 40, dy: 8, opacity: 0.5 },
    entrance: { mode: 'slideUp', unit: 'word', delay: 0.05, stagger: 0.09, duration: 0.75, distance: 150, easing: 'outQuint' },
    exit: { enabled: true, mode: 'riseUp', unit: 'word', time: 2.1, stagger: 0.09, duration: 1.6, distance: 900 },
    wave: { enabled: false }, pop: { enabled: false },
    duration: 4.2
  },

  'Lift Off': {
    font: { family: 'Oswald', weight: 700, size: 180, letterSpacing: 5 },
    fill: { mode: 'gradient', stops: ['#ffffff', '#7dd3fc'], angle: 90, sweepSpeed: 0 },
    stroke: { enabled: true, color: '#06121f', width: 7 },
    shadow: { enabled: true, color: '#000000', blur: 32, dy: 10, opacity: 0.55 },
    entrance: { mode: 'fade', unit: 'letter', stagger: 0.03, duration: 0.4 },
    exit: { enabled: true, mode: 'riseUp', unit: 'letter', time: 2.0, stagger: 0.045, duration: 1.2, distance: 1500 },
    wave: { enabled: false }, pop: { enabled: false },
    duration: 4
  },

  /* ------------------------------------------------------------------ wave */

  'Silk Banner': {
    font: { family: 'Shrikhand', size: 150, letterSpacing: 2 },
    fill: { mode: 'gradient', stops: ['#fff3c4', '#f6c453', '#a97400', '#ffe9a8'], angle: 96, sweepSpeed: 0.12 },
    stroke: { enabled: true, color: '#2b1a00', width: 7 },
    shadow: { enabled: true, color: '#1a0f00', blur: 36, dy: 16, opacity: 0.6 },
    entrance: { mode: 'fade', unit: 'line', duration: 0.7, stagger: 0.15 },
    wave: { enabled: true, amplitude: 26, wavelength: 420, speed: 0.42, secondary: 0.45, squash: 0.14, shading: 0.42, pole: 'left', poleCurve: 1.2 },
    exit: { enabled: false },
    duration: 6
  },

  'Flag Wave': {
    font: { family: 'Archivo Black', size: 165, letterSpacing: 2 },
    fill: { mode: 'gradient', stops: ['#ff2e63', '#ff8c42', '#ffd166'], angle: 90, sweepSpeed: 0 },
    stroke: { enabled: true, color: '#1a0011', width: 7 },
    shadow: { enabled: true, blur: 26, dy: 12, opacity: 0.5 },
    entrance: { mode: 'fade', unit: 'line', duration: 0.5, stagger: 0.12 },
    wave: { enabled: true, amplitude: 30, wavelength: 380, speed: 0.55, secondary: 0.4, squash: 0.16, shading: 0.35, pole: 'left', poleCurve: 1.1 },
    exit: { enabled: false }
  },

  'Ink & Wave': {
    font: { family: 'Bebas Neue', size: 180, letterSpacing: 4 },
    fill: { mode: 'rainbow', unit: 'letter', hueSpread: 14, cycleSpeed: 0.18, saturation: 88, lightness: 62 },
    stroke: { enabled: true, color: '#101010', width: 6 },
    shadow: { enabled: true, blur: 20, dy: 8, opacity: 0.5 },
    entrance: { mode: 'writeOn', unit: 'letter', lps: 20, overlap: 1.4, softness: 6, easing: 'linear' },
    wave: { enabled: true, amplitude: 18, wavelength: 300, speed: 0.6, secondary: 0.3, squash: 0.1, shading: 0.22, pole: 'left' },
    exit: { enabled: false }
  },

  /* -------------------------------------------------------------- write-on */

  'Write On': {
    font: { family: 'Bebas Neue', size: 185, letterSpacing: 4 },
    fill: { mode: 'solid', color: '#ffffff' },
    stroke: { enabled: true, color: '#000000', width: 6 },
    shadow: { enabled: true, blur: 18, dy: 6, opacity: 0.5 },
    entrance: { mode: 'writeOn', unit: 'letter', delay: 0.05, lps: 18, overlap: 1.4, softness: 7, easing: 'linear' },
    wave: { enabled: false }, pop: { enabled: false }, exit: { enabled: false }
  },

  'Signature': {
    font: { family: 'Righteous', size: 165, letterSpacing: 3 },
    fill: { mode: 'solid', color: '#ffffff' },
    stroke: { enabled: true, color: '#000000', width: 4 },
    shadow: { enabled: true, blur: 26, dy: 8, opacity: 0.5 },
    entrance: { mode: 'writeOn', unit: 'letter', delay: 0.15, lps: 7, overlap: 2.2, softness: 14, easing: 'linear' },
    wave: { enabled: false }, pop: { enabled: false }, exit: { enabled: false },
    duration: 5
  },

  /* ---------------------------------------------------------------- colour */

  'Rainbow Cycle': {
    font: { family: 'Bungee', size: 145, letterSpacing: 3 },
    fill: { mode: 'rainbow', unit: 'letter', hueSpread: 26, cycleSpeed: 0.35, saturation: 95, lightness: 60 },
    stroke: { enabled: true, color: '#0d0221', width: 9 },
    shadow: { enabled: true, blur: 24, dy: 10, opacity: 0.5 },
    entrance: { mode: 'popIn', unit: 'letter', stagger: 0.035, duration: 0.4 },
    exit: { enabled: false }
  },

  'Chrome Sweep': {
    font: { family: 'Archivo Black', size: 160, letterSpacing: 1 },
    fill: { mode: 'gradient', stops: ['#f2f2f2', '#8a94a6', '#ffffff', '#5b6478', '#e8ecf1'], angle: 100, sweepSpeed: 0.22 },
    stroke: { enabled: true, color: '#0b0d12', width: 8 },
    shadow: { enabled: true, blur: 30, dy: 14, opacity: 0.65 },
    entrance: { mode: 'slideUp', unit: 'word', stagger: 0.07, duration: 0.55, distance: 90, easing: 'outQuint' },
    exit: { enabled: false }
  },

  'Neon Sign': {
    font: { family: 'Monoton', size: 130, letterSpacing: 6 },
    fill: { mode: 'solid', color: '#ffffff' },
    stroke: { enabled: false, color: '#00e5ff', width: 3 },
    shadow: { enabled: false },
    glow: { enabled: true, color: '#ff00e5', blur: 46, opacity: 1, intensity: 3 },
    entrance: { mode: 'blurIn', unit: 'letter', stagger: 0.05, duration: 0.6, blurAmount: 22 },
    pop: { enabled: true, bpm: 128, amount: 0.06, damping: 6, bounce: 2, unit: 'none' },
    exit: { enabled: false }
  },

  /* ------------------------------------------------------------- cinematic */

  'Cinematic Wide': {
    font: { family: 'Big Shoulders Display', weight: 400, size: 120, letterSpacing: 28, lineHeight: 1.5 },
    fill: { mode: 'solid', color: '#f2f4f7' },
    stroke: { enabled: false },
    shadow: { enabled: true, color: '#000000', blur: 46, dy: 0, opacity: 0.6 },
    entrance: { mode: 'blurIn', unit: 'letter', stagger: 0.045, duration: 1.1, blurAmount: 20, easing: 'outQuint' },
    exit: { enabled: true, mode: 'fade', unit: 'letter', time: 3.6, stagger: 0.02, duration: 0.9 },
    wave: { enabled: false }, pop: { enabled: false },
    duration: 5.5
  },

  'Ghost Fade': {
    font: { family: 'Big Shoulders Display', size: 200, weight: 700, letterSpacing: 8 },
    fill: { mode: 'solid', color: '#ffffff' },
    stroke: { enabled: false },
    shadow: { enabled: true, blur: 40, dy: 0, opacity: 0.5 },
    entrance: { mode: 'blurIn', unit: 'letter', stagger: 0.06, duration: 0.9, blurAmount: 26, easing: 'outQuint' },
    exit: { enabled: true, mode: 'riseUp', unit: 'letter', time: 3.0, stagger: 0.03, duration: 0.7, distance: 220 },
    wave: { enabled: false }, pop: { enabled: false }
  }
};

/* ------------------------------------------------------------ export sizes */

const CANVAS_SIZES = {
  '1920 x 1080  (16:9 HD)': [1920, 1080],
  '3840 x 2160  (16:9 4K)': [3840, 2160],
  '1080 x 1920  (9:16 Vertical)': [1080, 1920],
  '1080 x 1080  (1:1 Square)': [1080, 1080],
  '2048 x 858   (2.39:1 Scope)': [2048, 858],
  '1280 x 720   (16:9 Draft)': [1280, 720]
};

if (typeof window !== 'undefined') {
  window.FONTS = FONTS;
  window.DEFAULTS = DEFAULTS;
  window.PRESETS = PRESETS;
  window.CANVAS_SIZES = CANVAS_SIZES;
  window.googleFontsHref = googleFontsHref;
}
