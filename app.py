from flask import Flask, render_template_string

app = Flask(__name__)

HTML = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<title>Love Heart</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body {
    width: 100%;
    height: 100%;
    height: 100dvh;
    background: #060208;
    overflow: hidden;
    font-family: Arial, Helvetica, sans-serif;
    -webkit-user-select: none;
    user-select: none;
    -webkit-tap-highlight-color: transparent;
    touch-action: none;
  }
  canvas {
    display: block;
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    cursor: default;
    touch-action: none;
  }
</style>
</head>
<body>
<canvas id="c"></canvas>
<script>
const PHRASES = [
  "I love you", "Seni seviyorum", "Te amo", "Je t'aime",
  "Ich liebe dich", "Ti amo", "Eu te amo", "Я тебя люблю",
  "사랑해", "愛してる", "我爱你", "मैं तुमसे प्यार करता हूँ",
  "Σ' αγαπώ", "Ik hou van jou", "Jag älskar dig", "Kocham cię",
  "ฉันรักเธอ", "Anh yêu em", "Aku cinta kamu", "Я тебе кохаю"
];

const SC = 21;
const OY = 20;
const DURATION = 16;   // slower overall build (was 10)
const TICK = 16;
const ANIM = 68;       // slower individual phrase entrance (was 42)
const LIFT = 34;
const GAP = 7;
const SIZES = [9, 10, 11, 12];
const BG = "#060208";
const BGC = [0x06/255, 0x02/255, 0x08/255];
const FLASH = [1.0, 0.78, 0.78];

const canvas = document.getElementById("c");
const ctx = canvas.getContext("2d");
let W = 800, H = 800;

function resize() {
  // Use full available viewport; keep square so heart stays proportional
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const s = Math.min(vw, vh);
  // High-DPI support for crisp text on phones
  const dpr = Math.min(window.devicePixelRatio || 1, 2.5);
  W = H = s;
  canvas.width = Math.round(s * dpr);
  canvas.height = Math.round(s * dpr);
  canvas.style.width = s + "px";
  canvas.style.height = s + "px";
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}
window.addEventListener("resize", resize);
window.addEventListener("orientationchange", () => setTimeout(resize, 100));
resize();

// seeded PRNG (same seed as original)
function mulberry32(a) {
  return function() {
    a |= 0; a = a + 0x6D2B79F5 | 0;
    let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}
const rng = mulberry32(11);

function heart(a) {
  const x = 16 * Math.pow(Math.sin(a), 3);
  const y = 13 * Math.cos(a) - 5 * Math.cos(2*a) - 2 * Math.cos(3*a) - Math.cos(4*a);
  return [x * SC, y * SC + OY];
}

function hx(c) {
  return "#" + c.map(v => Math.round(Math.max(0, Math.min(1, v)) * 255)
    .toString(16).padStart(2, "0")).join("");
}

function mix(a, b, k) {
  return a.map((p, i) => p + (b[i] - p) * k);
}

function dim(c, k) {
  return c.map(v => v * k);
}

function clamp(v) { return Math.max(0, Math.min(1, v)); }
function mathSin(v) { return Math.sin(Math.PI * v); }

const POLY = [];
for (let i = 0; i < 720; i++) POLY.push(heart(2 * Math.PI * i / 720));
const EDGES = POLY.map((p, i) => [p, POLY[(i + 1) % 720]]);
const YMAX = Math.max(...POLY.map(p => p[1]));
const YMIN = Math.min(...POLY.map(p => p[1]));
const CY = (YMAX + YMIN) / 2;

function spans(y) {
  const xs = [];
  for (const [[x1,y1],[x2,y2]] of EDGES) {
    if ((y1 <= y && y < y2) || (y2 <= y && y < y1)) {
      xs.push(x1 + (y - y1) * (x2 - x1) / (y2 - y1));
    }
  }
  xs.sort((a,b) => a - b);
  const out = [];
  for (let i = 0; i < xs.length - 1; i += 2) out.push([xs[i], xs[i+1]]);
  return out;
}

function intersect(A, B) {
  const out = [];
  for (const a of A) {
    for (const b of B) {
      const lo = Math.max(a[0], b[0]);
      const hi = Math.min(a[1], b[1]);
      if (hi - lo > 14) out.push([lo, hi]);
    }
  }
  return out;
}

// approximate text width (Arial bold)
const measureCache = {};
function measure(text, size) {
  const key = text + "|" + size;
  if (measureCache[key] !== undefined) return measureCache[key];
  ctx.font = `bold ${size}px Arial`;
  const w = ctx.measureText(text).width;
  measureCache[key] = w;
  return w;
}

function linespace(size) {
  return size * 1.25 + 4; // approximate metrics("linespace")
}

function phraseCycle() {
  let order = [...PHRASES];
  let idx = 0;
  // shuffle once then cycle
  for (let i = order.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [order[i], order[j]] = [order[j], order[i]];
  }
  return function next() {
    if (idx >= order.length) {
      order = [...PHRASES];
      for (let i = order.length - 1; i > 0; i--) {
        const j = Math.floor(rng() * (i + 1));
        [order[i], order[j]] = [order[j], order[i]];
      }
      idx = 0;
    }
    return order[idx++];
  };
}

function mathDist(x, y) {
  return Math.hypot(x / (16 * SC), (y - CY) / (14.5 * SC));
}

function build() {
  const nextPhrase = phraseCycle();
  const rowH = Math.max(...SIZES.map(linespace));
  const half = rowH / 2;
  const placed = [];

  let y = YMAX - half;
  while (y > YMIN + half) {
    const row = intersect(spans(y + half), spans(y - half));
    for (const [lo0, hi0] of row) {
      let lo = lo0 + 4, hi = hi0 - 4;
      let cur = lo + rng() * 8;
      const line = [];

      while (true) {
        let fit = null;
        for (let tries = 0; tries < 10; tries++) {
          const text = nextPhrase();
          const size = SIZES[Math.floor(rng() * SIZES.length)];
          const w = measure(text, size);
          if (cur + w <= hi) {
            fit = { text, size, w };
            break;
          }
        }
        if (!fit) break;
        line.push({ x: cur + fit.w / 2, text: fit.text, size: fit.size, w: fit.w });
        cur += fit.w + GAP;
      }

      if (!line.length) continue;

      if (line.length > 1) {
        const left = hi - (line[line.length - 1].x + line[line.length - 1].w / 2);
        line.forEach((it, i) => { it.x += left * i / (line.length - 1); });
      } else {
        line[0].x = (lo + hi) / 2;
      }

      line.forEach((it, i) => {
        const edge = i === 0 || i === line.length - 1;
        placed.push({ x: it.x, y, text: it.text, size: it.size, edge });
      });
    }
    y -= rowH;
  }

  const wine = [0.58, 0.0, 0.09];
  const crimson = [0.90, 0.05, 0.14];
  const blood = [0.98, 0.10, 0.16];

  for (const p of placed) {
    const rad = Math.min(1.0, mathDist(p.x, p.y));
    let base = mix(wine, crimson, 0.25 + 0.75 * rad);
    base = mix(base, blood, rng() * 0.35 + (p.edge ? 0.3 : 0));
    p.color = base.map(v => Math.min(1, v));
    p.rad = rad;
  }

  const edges = placed.filter(p => p.edge)
    .sort((a, b) => (Math.atan2(a.x, a.y - CY) % (2 * Math.PI)) -
                    (Math.atan2(b.x, b.y - CY) % (2 * Math.PI)));
  const inner = placed.filter(p => !p.edge)
    .sort((a, b) => (-a.rad + rng() * 0.08) - (-b.rad + rng() * 0.08));

  return edges.concat(inner);
}

const ORDER = build();
let items = ORDER.slice();
const RATE = ORDER.length / (DURATION * 1000 / TICK);
let acc = 0;
let spawning = true;
const active = [];
const mainIds = []; // for shimmer: {x,y,text,size,color}

function spawn(p) {
  p.f = 0;
  p.dx = (rng() * 20) - 10;
  p.alive = true;
  active.push(p);
  mainIds.push({ x: p.x, y: -p.y, text: p.text, size: p.size, color: p.color });
}

function animate(p) {
  p.f += 1;
  const u = clamp(p.f / ANIM);
  const e = 1 - Math.pow(1 - u, 3);
  const c = p.color;
  const x = p.x, y = -p.y;
  const hover = (1 - e) * LIFT;
  const px = x + p.dx * (1 - e);
  const py = y - hover;

  // we draw everything each frame, so just store current state
  p.drawX = px;
  p.drawY = py;
  p.e = e;
  p.u = u;

  if (u >= 1) {
    p.drawX = x;
    p.drawY = y;
    p.e = 1;
    p.u = 1;
    p.alive = false;
    return false;
  }
  return true;
}

function drawText(text, size, x, y, color, shadow = false) {
  ctx.font = `bold ${size}px Arial`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  if (shadow) {
    ctx.fillStyle = color;
    ctx.fillText(text, x + 2, y + 3);
  } else {
    ctx.fillStyle = color;
    ctx.fillText(text, x, y);
  }
}

function render() {
  ctx.fillStyle = BG;
  ctx.fillRect(0, 0, W, H);

  // scale to fit original 800x800 coordinate space
  const scale = Math.min(W, H) / 800;
  ctx.save();
  ctx.translate(W / 2, H / 2);
  ctx.scale(scale, scale);

  // draw finished (settled) texts first
  for (const p of ORDER) {
    if (p.f === undefined || p.alive) continue;
    const x = p.x, y = -p.y;
    // shadow
    drawText(p.text, p.size, x + 2, y + 3, hx(dim(p.color, 0.30)));
    // main
    drawText(p.text, p.size, x, y, hx(p.color));
  }

  // draw active (animating) texts
  for (const p of active) {
    const e = p.e, u = p.u, c = p.color;
    const px = p.drawX, py = p.drawY;

    // shadow
    drawText(p.text, p.size, px + 2, py + 3, hx(mix(BGC, dim(c, 0.30), e)));
    // halo (slightly larger)
    ctx.font = `bold ${p.size + 1}px Arial`;
    ctx.fillStyle = hx(mix(BGC, dim(c, 0.20), e * e));
    ctx.fillText(p.text, px, py);
    // main with flash
    const flash = 0.75 * mathSin(clamp((u - 0.55) / 0.45));
    const col = mix(mix(BGC, c, Math.pow(e, 1.5)), FLASH, flash);
    drawText(p.text, p.size, px, py, hx(col));
  }

  ctx.restore();
}

let lastShimmer = 0;
function shimmer(now) {
  if (now - lastShimmer > 140) {
    lastShimmer = now;
    if (mainIds.length) {
      const i = Math.floor(rng() * mainIds.length);
      const m = mainIds[i];
      m.flashUntil = now + 260;
    }
  }
}

function step(now) {
  if (spawning) {
    acc += RATE;
    while (acc >= 1 && items.length) {
      acc -= 1;
      spawn(items.shift());
    }
    if (!items.length) spawning = false;
  }

  for (let i = active.length - 1; i >= 0; i--) {
    if (!animate(active[i])) active.splice(i, 1);
  }

  // apply temporary shimmer on settled texts
  for (const m of mainIds) {
    if (m.flashUntil && now < m.flashUntil) {
      // find corresponding settled p and temporarily brighten
      // (handled in render by checking flashUntil)
    }
  }

  render();

  // overlay shimmer flashes
  if (!spawning && active.length === 0) {
    shimmer(now);
    const scale = Math.min(W, H) / 800;
    ctx.save();
    ctx.translate(W / 2, H / 2);
    ctx.scale(scale, scale);
    for (const m of mainIds) {
      if (m.flashUntil && now < m.flashUntil) {
        drawText(m.text, m.size, m.x, m.y, hx(mix(m.color, FLASH, 0.6)));
      }
    }
    ctx.restore();
  }

  requestAnimationFrame(step);
}

// kick off
requestAnimationFrame(step);
</script>
</body>
</html>
'''

@app.route("/")
def index():
    return render_template_string(HTML)

if __name__ == "__main__":
    # Local development
    app.run(host="0.0.0.0", port=5000, debug=True)
