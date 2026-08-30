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
  #speedSel {{
    width: 108px; background: #0f1214; color: var(--text); border: 1px solid var(--border);
    border-radius: 6px; padding: 9px 6px; text-align: center; font: 13px/1 -apple-system, sans-serif;
  }}
  #speedSel:disabled {{ opacity: .5; }}
  #playVideoBtn {{ width: 108px; padding: 8px 6px; font-size: 12px; }}
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
  /* Red while auto-blending — press again (same button) to stop early. */
  #plusBtn.running {{
    background: #e0554f; box-shadow: 0 4px 14px rgba(224,85,79,.4);
  }}
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
  .scrub {{
    margin-top: 16px; display: flex; flex-direction: column; align-items: center;
    gap: 6px; width: 100%;
  }}
  .scrub input[type=range] {{ width: 100%; accent-color: var(--accent2); }}
  .scrub input[type=range]:disabled {{ opacity: .35; }}
  #scrubLabel {{ font-size: 12px; color: var(--sub); }}
  #scrubLabel b {{ color: var(--text); font-variant-numeric: tabular-nums; }}
  #buildStatus {{ text-align: center; color: var(--sub); font-size: 12px; margin-top: 8px; min-height: 16px; }}
  #clipVideo {{
    display: none; margin: 16px auto 0; max-width: 100%; width: 500px;
    border-radius: 8px; border: 1px solid var(--border);
  }}
  .filmstrip {{ margin-top: 24px; display: flex; gap: 4px; flex-wrap: wrap; justify-content: center; max-width: 100%; }}
  .filmstrip div {{
    width: 46px; height: 46px; border-radius: 4px; overflow: hidden;
    border: 1px solid var(--border); background-size: cover; background-position: center;
    opacity: .85;
  }}
  .totals {{ text-align: center; margin-top: 16px; font-size: 16px; color: var(--sub); }}
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
      <div id="jumpLabel">Speed</div>
      <select id="speedSel" title="Single: + combines the current frame, then steps to the next. A speed: + auto-blends one frame after another at that rate until the last frame or until + (now red) is pressed again. Build: + skips the frame-by-frame animation entirely and asks the server to build the real mp4 directly — its own speed, not a chosen fps.">
        <option value="single" selected>Single (1 click)</option>
        <option value="4">4 fps</option>
        <option value="8">8 fps</option>
        <option value="12">12 fps</option>
        <option value="25">25 fps</option>
        <option value="build">Build (real speed)</option>
      </select>
      <button class="nav" id="playVideoBtn" disabled title="No built video yet">&#9654; Play video</button>
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
    <div class="scrub">
      <input type="range" id="scrubSlider" min="0" max="0" value="0" step="1" disabled>
      <div id="scrubLabel">No frames combined yet</div>
    </div>
  </div>

  <div class="filmstrip" id="filmstrip"></div>

  <div class="status" id="buildStatus"></div>
  <video id="clipVideo" controls></video>

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
  // instead of reading the canvas mid-draw. Takes an explicit frame number
  // rather than always reading the global `n`, so the scrub slider (below)
  // can redraw an already-combined frame for review without disturbing
  // whichever frame the nav buttons are currently sitting on.
  function drawCombinedAt(fn) {{
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
      b.src = BASE(Math.min(fn, {base_n})); o.src = OVER(Math.min(fn, {over_n}));
    }});
  }}
  const drawCombined = () => drawCombinedAt(n);

  // Combine the CURRENT frame (n) and step to the next one, leaving the
  // canvas/status showing what was just built (see showFrame()'s own
  // comment for why that is a separate call from render()). Returns false
  // once it has just combined the LAST frame — the signal both the single
  // click handler and the auto-run loop use to know there is nothing left.
  async function combineCurrentFrame() {{
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
      updateScrub();
    }}
    status.textContent = `Frame ${{n}} combined.`;
    const hadNext = n < MAXN;
    if (hadNext) {{ n++; showFrame(); }}
    return hadNext;
  }}

  // The scrub slider walks the frames that have ACTUALLY been combined so
  // far, in order — not the full 1..MAXN range, since most of that may not
  // exist yet. Its position is an index into that sorted list, not a frame
  // number itself, so it always spans exactly "first combined" to "last
  // combined" with no dead space on either end.
  const scrubSlider = document.getElementById('scrubSlider');
  const scrubLabel = document.getElementById('scrubLabel');

  function combinedSorted() {{
    return [...combined].sort((a, b) => a - b);
  }}

  function scrubTo(idx) {{
    const arr = combinedSorted();
    if (!arr.length) return;
    idx = Math.max(0, Math.min(idx, arr.length - 1));
    scrubSlider.value = idx;
    const frameNum = arr[idx];
    scrubLabel.innerHTML = `Frame <b>${{frameNum}}</b> &middot; ${{idx + 1}} / ${{arr.length}} combined`;
    canvas.style.display = 'block';
    drawCombinedAt(frameNum);
  }}

  // Called every time a new frame joins `combined` — grows the slider's
  // range and jumps it to the frame just built, so running a batch (the
  // auto-blend speeds above) tracks live, and once it stops you can drag
  // back through everything it made.
  function updateScrub() {{
    const arr = combinedSorted();
    scrubSlider.disabled = arr.length === 0;
    scrubSlider.max = Math.max(0, arr.length - 1);
    if (arr.length) scrubTo(arr.length - 1);
  }}

  scrubSlider.oninput = () => scrubTo(+scrubSlider.value);

  const buildStatus = document.getElementById('buildStatus');
  const clipVideo = document.getElementById('clipVideo');
  const playVideoBtn = document.getElementById('playVideoBtn');

  // Only ever enabled once a real, playable video exists — disabled the
  // moment a new build starts (the old file is about to be replaced) and
  // re-enabled only once the new one has actually landed.
  playVideoBtn.onclick = () => {{
    clipVideo.scrollIntoView({{behavior: 'smooth', block: 'center'}});
    clipVideo.play();
  }};

  // The one real request to the server behind the "Build" dropdown choice
  // — picture + voice together in a single ffmpeg pass. Its running time
  // is however long THAT takes, not a chosen fps: there is no per-frame
  // delay to configure here, unlike the browser-side auto-blend.
  async function buildClip(want) {{
    playVideoBtn.disabled = true;
    playVideoBtn.title = 'Building...';
    buildStatus.textContent = `Building ${{want}} frame(s) — picture and her voice, in one pass...`;
    clipVideo.style.display = 'none';
    const res = await fetch(`/build_clip?n=${{want}}`);
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    clipVideo.src = data.url + `?t=${{Date.now()}}`;   // cache-bust a rebuild at the same N
    clipVideo.style.display = 'block';
    buildStatus.textContent = `Built ${{data.frames}} frame(s) — playable above.`;
    playVideoBtn.disabled = false;
    playVideoBtn.title = 'Play the built video';
    return data;
  }}

  const plusBtn = document.getElementById('plusBtn');
  const speedSel = document.getElementById('speedSel');
  let running = false;

  function setRunning(on) {{
    running = on;
    plusBtn.classList.toggle('running', on);
    plusBtn.textContent = on ? '■' : '+';
    plusBtn.title = on ? 'Stop auto-blending' : '+';
    speedSel.disabled = on;
  }}

  // Auto-blend: combine, wait one frame-interval at the chosen fps, repeat
  // — until the last frame combines itself (hadNext comes back false) or
  // `running` goes false from the stop click below, whichever first.
  async function runAuto(fps) {{
    setRunning(true);
    const delayMs = 1000 / fps;
    while (running) {{
      const hadNext = await combineCurrentFrame();
      if (!hadNext || !running) break;
      await new Promise(r => setTimeout(r, delayMs));
    }}
    setRunning(false);
  }}

  // Build the WHOLE scene (frame 1 through MAXN) via the server, and mark
  // every one of those frames as combined here too — so the filmstrip count,
  // the totals line and the scrub slider all agree with reality afterward,
  // even though this path never drew them one at a time in the browser.
  // Not stoppable like the fps loop below: it's one request, not a series of
  // waits, so there's nothing meaningful for a second click to interrupt.
  async function runBuild() {{
    plusBtn.disabled = true;
    speedSel.disabled = true;
    try {{
      await buildClip(MAXN);
      for (let f = 1; f <= MAXN; f++) combined.add(f);
      document.getElementById('combinedCount').textContent = combined.size;
      updateScrub();
      n = MAXN;
      render();
    }} catch (e) {{
      buildStatus.textContent = `Build failed: ${{e.message}}`;
    }} finally {{
      plusBtn.disabled = false;
      speedSel.disabled = false;
    }}
  }}

  // Single mode: exactly the old one-click-one-frame behaviour, focus kept
  // on + so a run of manual clicks (or repeated Enter/Space) still works.
  // A speed selected instead turns + into a start/stop toggle for
  // runAuto() — press once to start blending at that rate, press the same
  // (now red) button again to stop early. Build skips that animation
  // entirely: its pace is the ffmpeg process, not a chosen fps.
  plusBtn.onclick = async () => {{
    if (running) {{ running = false; return; }}   // this click is the STOP
    const speed = speedSel.value;
    if (speed === 'single') {{
      await combineCurrentFrame();
      plusBtn.focus();
    }} else if (speed === 'build') {{
      runBuild();   // not awaited — button disables itself for its own duration
    }} else {{
      runAuto(+speed);   // not awaited — a stop click must reach the loop above
    }}
  }};

  document.getElementById('prevBtn').onclick = () => {{ if (!running && n > 1) {{ n--; render(); }} }};
  document.getElementById('nextBtn').onclick = () => {{ if (!running && n < MAXN) {{ n++; render(); }} }};
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
