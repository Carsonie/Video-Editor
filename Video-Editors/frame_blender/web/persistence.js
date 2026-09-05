// Frame Blender — the browser's own storage, not the server.
//
// Split out of app.js on 2026-09-04. That file was 765 lines covering four
// concerns; its own section banners already said where the seams were.
//
// ⚠ ORDER MATTERS. None of these is wrapped in an IIFE — they share ONE
// flat top-level scope, so index.html's load order reproduces the order
// the single file ran in, and a `const` used at load time must be declared
// in a file loaded earlier. Moving a <script> tag is a behaviour change.
//
// The two-space indent throughout is a leftover from when this WAS inside
// an IIFE (briefly, until 2026-09-02). It is kept rather than tidied,
// deliberately: some of these lines are inside template literals, where
// changing the indent changes the STRING, and a whitespace pass would hide
// that among hundreds of harmless lines.
//
'use strict';
  // ── persistence (the browser's own storage, not the server) ────────────────
  // The server is deliberately stateless (2026-08-30 restructure, so two tabs
  // can't fight over one remembered pair) — which also means it never had
  // anywhere to remember a Load result. Before this, a refresh silently
  // threw that away; the only thing that ever survived was the open pair
  // itself, and only by accident, because it happens to sit in the page's
  // own URL.
  //
  // localStorage survives a refresh AND closing the tab, until something
  // clears it — which here is only ever the Clear button (see showEmpty()).
  // Wrapped in try/catch because storage can be unavailable (private
  // browsing, quota) and that should degrade to "nothing persists this
  // session," never a broken page.
  const STORAGE_KEY = 'frameBlender.v1';
  const pairKey = (baseRel, overRel) => `${baseRel}::${overRel}`;

  function loadStore() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : {pairs: {}};
    } catch (e) { return {pairs: {}}; }
  }
  function saveStore(patch) {
    try {
      const cur = loadStore();
      localStorage.setItem(STORAGE_KEY, JSON.stringify({...cur, ...patch}));
    } catch (e) { /* storage unavailable — work continues, just unsaved */ }
  }
  function savePair(key, patch) {
    const cur = loadStore();
    cur.pairs = cur.pairs || {};
    cur.pairs[key] = {...(cur.pairs[key] || {}), ...patch};
    saveStore(cur);
  }
  function clearStore() {
    try { localStorage.removeItem(STORAGE_KEY); } catch (e) {}
  }

  // The one thing that is NOT tied to one scene: the last Load result.
  // Called after every showEmpty()-driven reset (both a plain refresh and an
  // in-session scene switch go through showEmpty() first, via openPair()) —
  // NOT called by Clear, which empties storage first so there is nothing
  // left for this to bring back.
  function restoreGlobals() {
    const s = loadStore();
    // Guarded on STORE_SCENES already being empty — showEmpty() does NOT
    // reset it (see showEmpty()'s own comment on what it deliberately
    // leaves alone), so loadVideo() calling this right after setting it
    // fresh must not stomp that with the same data relabeled "restored".
    if (s.storeScenes && !STORE_SCENES) {
      STORE_SCENES = s.storeScenes;
      SCRIPT = s.script || null;
      tlRender();
      tlStatus.textContent += ' (restored)';
    }
  }

  // Frame-stepping progress is tied to one scene — restored once that
  // scene's own pair is open, keyed the same way a save for it is:
  // base_rel + over_rel, so re-opening the SAME scene later in the same
  // session (not just after a refresh) brings its own work back.
  function saveProgressForCurrentPair() {
    if (!SCENE) return;
    savePair(pairKey(SCENE.base_rel, SCENE.over_rel), {n, combined: [...combined]});
  }
  async function restorePairProgress() {
    if (!SCENE) return;
    const rec = loadStore().pairs?.[pairKey(SCENE.base_rel, SCENE.over_rel)];
    if (!rec || !Array.isArray(rec.combined) || !rec.combined.length) return;
    combined.clear();
    for (const f of rec.combined) combined.add(f);
    document.getElementById('combinedCount').textContent = combined.size;
    n = Math.min(rec.n || 1, SCENE.max_n);
    render();
    // Redraw thumbnails only for a hand-stepped batch small enough that this
    // is instant. A "Build (real speed)" run marks the WHOLE scene combined
    // in one call without ever drawing a thumbnail per frame either (see
    // runBuild()'s own comment) — restoring hundreds one at a time here
    // would be the one place slower than just re-combining them.
    const arr = combinedSorted();
    if (arr.length && arr.length <= 60) {
      const strip = document.getElementById('filmstrip');
      strip.innerHTML = '';
      for (const fn of arr) {
        await drawCombinedAt(fn);
        const tile = document.createElement('div');
        tile.style.backgroundImage = `url(${canvas.toDataURL('image/jpeg', 0.85)})`;
        tile.title = `frame ${fn}`;
        strip.appendChild(tile);
      }
    }
    updateScrub();
  }

  const pad = n => String(n).padStart(5, '0');
  const BASE = n => `/${SCENE.base_slug}/frames/frame_${pad(n)}${SCENE.base_ext}`;
  const OVER = n => `/${SCENE.over_slug}/frames/frame_${pad(n)}${SCENE.over_ext}`;

  let n = 1;
  const combined = new Set();
  const baseImg = document.getElementById('baseImg');
  const overImg = document.getElementById('overImg');
  const canvas = document.getElementById('resultCanvas');
  const ctx = canvas.getContext('2d');
  const status = document.getElementById('status');

  // Which track(s) flow into the combiner canvas and, from there, into the
  // frames collection (the filmstrip / scrub range) — both on by default,
  // the same as every combine before this existed. Turning one off lets a
  // review isolate just Sarah's motion, or just the background's, instead
  // of always compositing the pair.
  let includeBase = true, includeOverlay = true;
  const overFlowBtn = document.getElementById('overFlowBtn');
  const baseFlowBtn = document.getElementById('baseFlowBtn');

  // The canvas border reads which track(s) are flowing, in the same
  // colour language --seg/--over/--accent already use everywhere else on
  // this page: blue for base alone, purple for overlay alone, green for
  // both — and the neutral border colour if neither is on, since nothing
  // is flowing at all.
  function updateFlowUI() {
    overFlowBtn.classList.toggle('on', includeOverlay);
    baseFlowBtn.classList.toggle('on', includeBase);
    overFlowBtn.title = includeOverlay
      ? 'Overlay flows into the combiner — click to leave it out'
      : 'Overlay is left out of the combiner — click to include it';
    baseFlowBtn.title = includeBase
      ? 'Base flows into the combiner — click to leave it out'
      : 'Base is left out of the combiner — click to include it';
    canvas.style.borderColor =
      includeBase && includeOverlay ? 'var(--accent)'
      : includeOverlay ? 'var(--over)'
      : includeBase ? 'var(--seg)'
      : 'var(--border)';
    // By id, not the outer `plusBtn` const below — this runs once at load,
    // before that declaration is reached, and a temporal-dead-zone
    // reference here would throw before the page ever renders.
    const btn = document.getElementById('plusBtn');
    btn.classList.remove('flow-over', 'flow-base', 'flow-none');
    if (!includeBase && !includeOverlay) btn.classList.add('flow-none');
    else if (!includeBase) btn.classList.add('flow-over');
    else if (!includeOverlay) btn.classList.add('flow-base');
  }
  overFlowBtn.onclick = () => { includeOverlay = !includeOverlay; updateFlowUI(); };
  baseFlowBtn.onclick = () => { includeBase = !includeBase; updateFlowUI(); };
  updateFlowUI();

  // Just the two viewer panels and the nav state — no opinion on the
  // canvas or the status line. Split out so the post-combine auto-advance
  // (below) can move the PICKER on to the next frame without also hiding
  // the result it just drew: that used to call the combined render() below,
  // which — seeing the NEW frame was not yet combined — hid the canvas the
  // instant it appeared. Carson caught it: the big picture disappeared
  // right after every combine.
  function showFrame() {
    if (!LOADED()) return;   // nothing to show, and nothing to repaint over a cleared page
    baseImg.src = BASE(Math.min(n, SCENE.base_n));
    overImg.src = OVER(Math.min(n, SCENE.over_n));
    document.getElementById('baseN').textContent = Math.min(n, SCENE.base_n);
    document.getElementById('overN').textContent = Math.min(n, SCENE.over_n);
    document.getElementById('prevBtn').disabled = n <= 1;
    document.getElementById('nextBtn').disabled = n >= SCENE.max_n;
  }

  // The full picture for NAVIGATING to a frame (prev/next, or landing on
  // one by typing a number then +): also syncs the canvas and status to
  // whether THIS frame has already been combined.
  function render() {
    if (!LOADED()) return;
    showFrame();
    canvas.style.display = combined.has(n) ? 'block' : 'none';
    if (combined.has(n)) drawCombined();
    status.textContent = combined.has(n) ? 'Already combined — click + again to redraw.' : '';
  }

  // Returns once every FLOWING layer is actually painted (base, overlay, or
  // both — see includeBase/includeOverlay above), so a caller that wants
  // the finished picture (the filmstrip thumbnail, below) can wait for it
  // instead of reading the canvas mid-draw. Takes an explicit frame number
  // rather than always reading the global `n`, so the scrub slider (below)
  // can redraw an already-combined frame for review without disturbing
  // whichever frame the nav buttons are currently sitting on.
  function drawCombinedAt(fn) {
    return new Promise(resolve => {
      const wantB = includeBase, wantO = includeOverlay;
      if (!wantB && !wantO) { ctx.clearRect(0, 0, canvas.width, canvas.height); resolve(); return; }
      const need = (wantB ? 1 : 0) + (wantO ? 1 : 0);
      let loaded = 0;
      const b = wantB ? new Image() : null, o = wantO ? new Image() : null;
      const done = () => {
        loaded++;
        if (loaded < need) return;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        // Base first, overlay on top — the same stacking order a full
        // combine has always drawn in, kept even when one side is off.
        if (b) ctx.drawImage(b, 0, 0, canvas.width, canvas.height);
        if (o) ctx.drawImage(o, 0, 0, canvas.width, canvas.height);
        resolve();
      };
      if (b) { b.onload = done; b.src = BASE(Math.min(fn, SCENE.base_n)); }
      if (o) { o.onload = done; o.src = OVER(Math.min(fn, SCENE.over_n)); }
    });
  }
  const drawCombined = () => drawCombinedAt(n);

  // Combine the CURRENT frame (n) and step to the next one, leaving the
  // canvas/status showing what was just built (see showFrame()'s own
  // comment for why that is a separate call from render()). Returns false
  // once it has just combined the LAST frame — the signal both the single
  // click handler and the auto-run loop use to know there is nothing left.
  async function combineCurrentFrame() {
    if (!includeBase && !includeOverlay) {
      status.textContent = 'Nothing flowing into the combiner — turn Base or Overlay back on.';
      return false;   // same "nothing left to do" signal an auto-run stops on
    }
    canvas.style.display = 'block';
    await drawCombined();
    if (!combined.has(n)) {
      combined.add(n);
      document.getElementById('combinedCount').textContent = combined.size;
      const strip = document.getElementById('filmstrip');
      const tile = document.createElement('div');
      // The ACTUAL combined picture — Sarah composited onto the background,
      // read straight off the canvas that was just painted — not the base
      // frame alone. A thumbnail of only the background answers a different
      // question than the one this tool exists to answer.
      tile.style.backgroundImage = `url(${canvas.toDataURL('image/jpeg', 0.85)})`;
      tile.title = `frame ${n}`;
      strip.appendChild(tile);
      updateScrub();
    }
    status.textContent = `Frame ${n} combined.`;
    const hadNext = n < SCENE.max_n;
    if (hadNext) { n++; showFrame(); }
    saveProgressForCurrentPair();
    return hadNext;
  }

  // The scrub slider walks the frames that have ACTUALLY been combined so
  // far, in order — not the full 1..SCENE.max_n range, since most of that may not
  // exist yet. Its position is an index into that sorted list, not a frame
  // number itself, so it always spans exactly "first combined" to "last
  // combined" with no dead space on either end.
  const scrubSlider = document.getElementById('scrubSlider');
  const scrubLabel = document.getElementById('scrubLabel');

  function combinedSorted() {
    return [...combined].sort((a, b) => a - b);
  }

  function scrubTo(idx) {
    const arr = combinedSorted();
    if (!arr.length) return;
    idx = Math.max(0, Math.min(idx, arr.length - 1));
    scrubSlider.value = idx;
    const frameNum = arr[idx];
    scrubLabel.innerHTML = `Frame <b>${frameNum}</b> &middot; ${idx + 1} / ${arr.length} combined`;
    canvas.style.display = 'block';
    drawCombinedAt(frameNum);
  }

  // Called every time a new frame joins `combined` — grows the slider's
  // range and jumps it to the frame just built, so running a batch (the
  // auto-blend speeds above) tracks live, and once it stops you can drag
  // back through everything it made.
  function updateScrub() {
    const arr = combinedSorted();
    scrubSlider.disabled = arr.length === 0;
    scrubSlider.max = Math.max(0, arr.length - 1);
    if (arr.length) scrubTo(arr.length - 1);
  }

  scrubSlider.oninput = () => scrubTo(+scrubSlider.value);

  const buildStatus = document.getElementById('buildStatus');
  const clipVideo = document.getElementById('clipVideo');
  const playVideoBtn = document.getElementById('playVideoBtn');

  // Enabled whenever a scene is loaded — it no longer waits for a build to
  // exist first. Until 2026-08-30 this button stayed disabled until the "+"
  // button (elsewhere on the page, with no visual link to Build/Play) ran
  // the build, so choosing "Build (real speed)" and clicking THIS button —
  // the obvious next step — silently did nothing. Now it builds first if
  // there's nothing built yet, then plays, so Play is the one control that
  // actually starts a build.
  playVideoBtn.onclick = async () => {
    if (!LOADED() || running) return;
    if (lastBuiltFrames == null) {
      playVideoBtn.disabled = true;
      playVideoBtn.title = 'Building...';
      try {
        await buildClip(SCENE.max_n);
      } catch (e) {
        buildStatus.textContent = `Build failed: ${e.message}`;
        playVideoBtn.disabled = false;
        playVideoBtn.title = 'No built video yet';
        return;
      }
    }
    clipVideo.scrollIntoView({behavior: 'smooth', block: 'center'});
    clipVideo.play();
  };

  // The one real request to the server behind the "Build" dropdown choice
  // — picture + voice together in a single ffmpeg pass. Its running time
  // is however long THAT takes, not a chosen fps: there is no per-frame
  // delay to configure here, unlike the browser-side auto-blend.
  let lastBuiltFrames = null;
  const tlSaveMp4Btn = document.getElementById('tlSaveMp4Btn');

  async function buildClip(want) {
    playVideoBtn.disabled = true;
    playVideoBtn.title = 'Building...';
    tlSaveMp4Btn.disabled = true;
    buildStatus.textContent = `Building ${want} frame(s) — picture and her voice, in one pass...`;
    clipVideo.style.display = 'none';
    const res = await fetch(`/build_clip?${pairQS()}&n=${want}`);
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    clipVideo.src = data.url + `?t=${Date.now()}`;   // cache-bust a rebuild at the same N
    clipVideo.style.display = 'block';
    buildStatus.textContent = `Built ${data.frames} frame(s) — playable above.`;
    playVideoBtn.disabled = false;
    playVideoBtn.title = 'Play the built video';
    lastBuiltFrames = data.frames;
    tlSaveMp4Btn.disabled = false;
    tlSaveMp4Btn.title = `Save the ${data.frames}-frame build into video/sandbox_mp4_scenes/`;
    return data;
  }
