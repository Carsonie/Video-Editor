"""
Frame Blender — step through a scene's two tracks frame by frame and combine
them by hand, to see exactly what lands in the finished video at each point.

Built 2026-08-29, out of a one-off page made to chase down ski-demo scene 1's
"not in sync" report: it turned out the BACKGROUND track has a blank stretch
at its start (no app screen visible for several seconds while Sarah is
already talking), and stepping through frames one at a time — rather than
trusting a frame-count match or a brightness average, both of which said
nothing was wrong — is what found it. Kept as its own small tool because
"is this scene's footage actually showing what it should, frame by frame"
is a real, recurring question, not a one-off.

Does not extract frames itself — serve.py hands it a base slug and an
overlay slug already extracted into cache/ (same mechanism, same cache, as
the main editor), plus their frame counts. This file only renders the page.
"""
import json

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Frame Blender — {label}</title>
<style>
  :root {{
    --bg: #0f1214; --panel: #171b1e; --border: #3a4248; --text: #dfe4e7;
    --sub: #8b949c; --accent: #2ecc40; --accent2: #7aa7ff;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--bg); color: var(--text);
    font: 14px/1.4 -apple-system, system-ui, sans-serif;
    padding: 20px;
  }}
  h1 {{ font-size: 16px; margin: 0 0 4px; }}
  .sub {{ color: var(--sub); font-size: 12px; margin-bottom: 18px; }}
  .row {{
    display: flex; align-items: flex-start; justify-content: center;
    gap: 24px; flex-wrap: wrap;
  }}
  .panel {{
    background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
    padding: 14px; width: 320px; text-align: center;
  }}
  .panel h3 {{ margin: 0 0 10px; font-size: 12px; text-transform: uppercase;
    letter-spacing: .08em; color: var(--sub); }}
  .imgwrap {{
    width: 100%; aspect-ratio: 1/1; border-radius: 6px; overflow: hidden;
    display: flex; align-items: center; justify-content: center;
    border: 1px solid var(--border);
  }}
  .imgwrap.checker {{
    background-image:
      linear-gradient(45deg, #2a2a2a 25%, transparent 25%),
      linear-gradient(-45deg, #2a2a2a 25%, transparent 25%),
      linear-gradient(45deg, transparent 75%, #2a2a2a 75%),
      linear-gradient(-45deg, transparent 75%, #2a2a2a 75%);
    background-size: 20px 20px;
    background-position: 0 0, 0 10px, 10px -10px, -10px 0px;
    background-color: #1a1a1a;
  }}
  .imgwrap img {{ max-width: 100%; max-height: 100%; object-fit: contain; }}
  .count {{ margin-top: 10px; font-size: 13px; }}
  .count b {{ color: var(--text); font-variant-numeric: tabular-nums; }}
  .mid {{
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    gap: 14px; width: 100px; padding-top: 130px;
  }}
  #jump {{
    width: 74px; background: #0f1214; color: var(--text); border: 1px solid var(--border);
    border-radius: 6px; padding: 9px 8px; text-align: center; font: 15px/1 monospace;
  }}
  #jumpLabel {{ font-size: 10px; text-transform: uppercase; letter-spacing: .08em;
    color: var(--sub); text-align: center; }}
  .navrow {{ display: flex; justify-content: center; align-items: center; gap: 14px; margin: 22px 0 6px; }}
  button.nav {{
    background: #2c3236; color: var(--text); border: 1px solid var(--border);
    border-radius: 6px; padding: 8px 16px; font-size: 13px; cursor: pointer;
  }}
  button.nav:hover {{ border-color: var(--accent2); }}
  button.nav:disabled {{ opacity: .35; cursor: default; }}
  #plusBtn {{
    width: 56px; height: 56px; border-radius: 50%; font-size: 26px;
    background: var(--accent); color: #06210a; border: none; cursor: pointer;
    box-shadow: 0 4px 14px rgba(46,204,64,.35);
  }}
  #plusBtn:active {{ transform: scale(.94); }}
  /* Focus stays on this button after every combine (see the click handler),
     so a visible ring here is what shows the run-of-frames workflow is
     ready for the next Enter/Space press. */
  #plusBtn:focus-visible, #plusBtn:focus {{
    outline: 3px solid var(--accent2); outline-offset: 3px;
  }}
  .resultWrap {{ margin-top: 26px; display: flex; flex-direction: column; align-items: center; }}
  .resultWrap h3 {{ font-size: 12px; text-transform: uppercase; letter-spacing: .08em;
    color: var(--sub); margin: 0 0 10px; }}
  #resultCanvas {{
    width: 340px; height: 340px; border-radius: 8px; border: 1px solid var(--border);
    background:
      linear-gradient(45deg, #232323 25%, transparent 25%),
      linear-gradient(-45deg, #232323 25%, transparent 25%),
      linear-gradient(45deg, transparent 75%, #232323 75%),
      linear-gradient(-45deg, transparent 75%, #232323 75%);
    background-size: 20px 20px;
    background-position: 0 0, 0 10px, 10px -10px, -10px 0px;
    background-color: #1a1a1a;
    display: none;
  }}
  .status {{ text-align: center; color: var(--sub); font-size: 12px; margin-top: 12px; min-height: 16px; }}
  .filmstrip {{ margin-top: 24px; display: flex; gap: 4px; flex-wrap: wrap; justify-content: center; max-width: 900px; }}
  .filmstrip div {{
    width: 46px; height: 46px; border-radius: 4px; overflow: hidden;
    border: 1px solid var(--border); background-size: cover; background-position: center;
    opacity: .85;
  }}
  .totals {{ text-align: center; margin-top: 16px; font-size: 12px; color: var(--sub); }}
  .totals b {{ color: var(--accent); }}
  .brightness {{ margin-top: 6px; font-size: 11px; color: var(--sub); }}
</style>
</head>
<body>
  <h1>Frame Blender — {label}</h1>
  <div class="sub">Overlay (left) + base (right) &rarr; one combined frame of the finished video.</div>

  <div class="row">
    <div class="panel">
      <h3>Overlay</h3>
      <div class="imgwrap checker"><img id="overImg" alt="overlay frame"></div>
      <div class="count">Frame <b id="overN">1</b> / <b id="overTotal">{over_n}</b></div>
    </div>

    <div class="mid">
      <div id="jumpLabel">Frame</div>
      <input id="jump" type="number" min="1" max="{max_n}" value="1">
    </div>

    <div class="panel">
      <h3>Base</h3>
      <div class="imgwrap"><img id="baseImg" alt="base frame"></div>
      <div class="count">Frame <b id="baseN">1</b> / <b id="baseTotal">{base_n}</b></div>
    </div>
  </div>

  <div class="navrow">
    <button class="nav" id="prevBtn">&#9664; prev frame</button>
    <button id="plusBtn" title="Jump to the frame above and combine it">+</button>
    <button class="nav" id="nextBtn">next frame &#9654;</button>
  </div>
  <div class="status" id="status"></div>

  <div class="totals">Combined so far: <b id="combinedCount">0</b> / {max_n} frames</div>

  <div class="resultWrap">
    <h3>Combined &mdash; this frame, as it lands in the finished mp4</h3>
    <canvas id="resultCanvas" width="700" height="700"></canvas>
  </div>

  <div class="filmstrip" id="filmstrip"></div>

<script>
  const MAXN = {max_n};
  const BASE_SLUG = {base_slug!r};
  const OVER_SLUG = {over_slug!r};
  const pad = n => String(n).padStart(5, '0');
  const BASE = n => `/${{BASE_SLUG}}/frames/frame_${{pad(n)}}{base_ext}`;
  const OVER = n => `/${{OVER_SLUG}}/frames/frame_${{pad(n)}}{over_ext}`;

  let n = 1;
  const combined = new Set();
  const baseImg = document.getElementById('baseImg');
  const overImg = document.getElementById('overImg');
  const canvas = document.getElementById('resultCanvas');
  const ctx = canvas.getContext('2d');
  const status = document.getElementById('status');

  // Just the two viewer panels and the nav state — no opinion on the
  // canvas or the status line. Split out so the post-combine auto-advance
  // (below) can move the PICKER on to the next frame without also hiding
  // the result it just drew: that used to call the combined render() below,
  // which — seeing the NEW frame was not yet combined — hid the canvas the
  // instant it appeared. Carson caught it: the big picture disappeared
  // right after every combine.
  function showFrame() {{
    baseImg.src = BASE(Math.min(n, {base_n}));
    overImg.src = OVER(Math.min(n, {over_n}));
    document.getElementById('baseN').textContent = Math.min(n, {base_n});
    document.getElementById('overN').textContent = Math.min(n, {over_n});
    document.getElementById('jump').value = n;
    document.getElementById('prevBtn').disabled = n <= 1;
    document.getElementById('nextBtn').disabled = n >= MAXN;
  }}

  // The full picture for NAVIGATING to a frame (prev/next, or landing on
  // one by typing a number then +): also syncs the canvas and status to
  // whether THIS frame has already been combined.
  function render() {{
    showFrame();
    canvas.style.display = combined.has(n) ? 'block' : 'none';
    if (combined.has(n)) drawCombined();
    status.textContent = combined.has(n) ? 'Already combined — click + again to redraw.' : '';
  }}

  // Returns once BOTH layers are actually painted, so a caller that wants
  // the finished picture (the filmstrip thumbnail, below) can wait for it
  // instead of reading the canvas mid-draw.
  function drawCombined() {{
    return new Promise(resolve => {{
      const b = new Image(), o = new Image();
      let loaded = 0;
      const done = () => {{
        loaded++;
        if (loaded < 2) return;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(b, 0, 0, canvas.width, canvas.height);
        ctx.drawImage(o, 0, 0, canvas.width, canvas.height);
        resolve();
      }};
      b.onload = done; o.onload = done;
      b.src = BASE(Math.min(n, {base_n})); o.src = OVER(Math.min(n, {over_n}));
    }});
  }}

  // One click does three jobs: land on whatever frame number is in the box,
  // combine it, THEN step to the next frame and keep the + button focused —
  // so combining a run of frames is type-once, then just press + (or Enter,
  // or Space, since focus stays put) over and over.
  const plusBtn = document.getElementById('plusBtn');
  plusBtn.onclick = async () => {{
    n = Math.max(1, Math.min(MAXN, +document.getElementById('jump').value || 1));
    render();
    canvas.style.display = 'block';
    await drawCombined();
    if (!combined.has(n)) {{
      combined.add(n);
      document.getElementById('combinedCount').textContent = combined.size;
      const strip = document.getElementById('filmstrip');
      const tile = document.createElement('div');
      // The ACTUAL combined picture — Sarah composited onto the background,
      // read straight off the canvas that was just painted — not the base
      // frame alone. A thumbnail of only the background answers a different
      // question than the one this tool exists to answer.
      tile.style.backgroundImage = `url(${{canvas.toDataURL('image/jpeg', 0.85)}})`;
      tile.title = `frame ${{n}}`;
      strip.appendChild(tile);
    }}
    const didCombine = `Frame ${{n}} combined.`;
    // showFrame(), not render(): advance the PICKER to the next frame so it
    // is ready to go, but leave the canvas and status alone — they should
    // keep showing what was just built, not flip to the new frame's
    // (not-yet-combined) empty state the instant it appears.
    if (n < MAXN) {{ n++; showFrame(); }}
    status.textContent = didCombine;
    plusBtn.focus();
  }};

  document.getElementById('prevBtn').onclick = () => {{ if (n > 1) {{ n--; render(); }} }};
  document.getElementById('nextBtn').onclick = () => {{ if (n < MAXN) {{ n++; render(); }} }};
  document.addEventListener('keydown', e => {{
    if (e.key === 'ArrowLeft') document.getElementById('prevBtn').click();
    if (e.key === 'ArrowRight') document.getElementById('nextBtn').click();
  }});

  render();
</script>
</body>
</html>
"""


def render(base_slug, over_slug, base_n, over_n, label,
           base_ext=".jpg", over_ext=".png"):
    """The Frame Blender page for one already-extracted pair.

    `base_n`/`over_n` can differ — MAXN (the nav range) is the LARGER of the
    two, and each side clamps to its own last frame past that, so a pair
    with mismatched lengths (which is itself worth seeing) does not error.
    """
    return TEMPLATE.format(
        label=label, base_n=base_n, over_n=over_n, max_n=max(base_n, over_n),
        base_slug=base_slug, over_slug=over_slug,
        base_ext=base_ext, over_ext=over_ext)
