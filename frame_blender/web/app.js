// Frame Blender — the page's behaviour.
//
// Plain .js on purpose. Until 2026-08-30 all of this lived inside a Python
// string in player.py, where every brace had to be doubled for str.format()
// and a stray one broke the page at render time rather than in an editor.
// It is served as a static file now: no build step, no escaping, and the
// browser's own debugger lines up with the file.
(function () {
  'use strict';

// THE one piece of state that says what this page is looking at.
  // null means nothing is loaded, and that is a real, first-class state —
  // the page can start there, Clear can return to it, and every action
  // below checks it. Before the 2026-08-30 restructure this was four
  // separate values baked into the HTML by the server at render time,
  // which is why the page could never truly be cleared: the scene WAS the
  // page. Now the page is empty furniture and the scene arrives over the
  // API, so unloading is just setting this back to null.
  let SCENE = null;
  const LOADED = () => SCENE !== null;
  // The narration script for the loaded VIDEO (all scenes), not for the
  // one open scene — which is why it lives beside SCENE, not inside it.
  let SCRIPT = null;
  // Every request that acts on a scene says WHICH scene, rather than
  // relying on the server to remember. That is what lets two tabs work on
  // two different scenes at once, and what makes Clear real.
  const pairQS = () => new URLSearchParams(
      {base: SCENE.base_rel, overlay: SCENE.over_rel}).toString();

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

  // Returns once BOTH layers are actually painted, so a caller that wants
  // the finished picture (the filmstrip thumbnail, below) can wait for it
  // instead of reading the canvas mid-draw. Takes an explicit frame number
  // rather than always reading the global `n`, so the scrub slider (below)
  // can redraw an already-combined frame for review without disturbing
  // whichever frame the nav buttons are currently sitting on.
  function drawCombinedAt(fn) {
    return new Promise(resolve => {
      const b = new Image(), o = new Image();
      let loaded = 0;
      const done = () => {
        loaded++;
        if (loaded < 2) return;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(b, 0, 0, canvas.width, canvas.height);
        ctx.drawImage(o, 0, 0, canvas.width, canvas.height);
        resolve();
      };
      b.onload = done; o.onload = done;
      b.src = BASE(Math.min(fn, SCENE.base_n)); o.src = OVER(Math.min(fn, SCENE.over_n));
    });
  }
  const drawCombined = () => drawCombinedAt(n);

  // Combine the CURRENT frame (n) and step to the next one, leaving the
  // canvas/status showing what was just built (see showFrame()'s own
  // comment for why that is a separate call from render()). Returns false
  // once it has just combined the LAST frame — the signal both the single
  // click handler and the auto-run loop use to know there is nothing left.
  async function combineCurrentFrame() {
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

  // ── Timeline Scenes ──────────────────────────────────────────────────────
  // A read-mostly companion to the Segment and Avatar Editor's own panel of
  // the same name, sharing its actual data rather than a copy of it: Load
  // asks the main editor for this store's real scene list, and every dirty
  // dot comes from the SAME per-scene cache flag the editor's own icons
  // read — so the two tools cannot show two different answers for the same
  // scene. Save writes through the editor's own save path too, for the
  // same reason.
  //
  // Undo has no such source here: it needs a snapshot of what a scene
  // looked like one step ago, and this tool has never taken one, because it
  // has no edit action of its own yet that would need undoing. The icon is
  // shown, disabled, rather than left out, so the row layout already
  // matches the editor's and only needs its behaviour turned on later.
  let STORE_SCENES = null;
  const tlStatus = document.getElementById('tlStatus');
  const tlRows = document.getElementById('tlRows');

  // The narration line for a scene, from the script.json loaded alongside
  // it. Matched on scene NUMBER, which is what script.json keys on — a
  // label can differ between the script and the folder name, the number
  // cannot.
  function lineOf(n) {
    const sc = (SCRIPT && SCRIPT.scenes) || [];
    const node = sc.find(x => Number(x.n) === Number(n));
    return node && node.line ? node.line : null;
  }

  function tlRow(it) {
    const d = document.createElement('div');
    d.className = 'tlrow' + (it.current ? ' cur' : '');
    const dirty = !!(it.base_edited || it.over_edited);
    const durTxt = it.dur == null ? '—' : `${it.dur}s`;
    d.innerHTML = `
      <span class="n">${it.n}</span>
      <span class="lab" title="${it.label || ''}">${it.label || '(scene ' + it.n + ')'}</span>
      <span class="dur">${durTxt}</span>
      <span class="dot${dirty ? ' dirty' : ''}" title="${dirty ? 'Has unsaved changes in its cache' : 'Pristine — file matches its cache'}"></span>
      <button class="ibtn undo" disabled title="Frame Blender doesn't edit scenes itself yet, so there's nothing here to undo — Undo the change in the Segment and Avatar Editor instead.">&#8630;</button>
      <button class="ibtn save${dirty ? ' dirty' : ''}" ${dirty ? '' : 'disabled'}
        title="${dirty ? 'Save this scene\'s cache to sandbox/ (same as the editor\'s own Save)' : 'No unsaved changes to save'}">&#8593;</button>`;
    d.querySelector('.save').onclick = ev => { ev.stopPropagation(); tlSaveScene(it); };
    // Clicking the row LOADS that scene. This is what "Load" always implied
    // and never did: before the restructure the page could not change scene
    // at all, because the scene was baked into the page at render time.
    // What she SAYS over this scene, when a script was loaded with it.
    // Shown on hover rather than as another column: the row is already
    // dense, and the line is usually a full sentence.
    const line = lineOf(it.n);
    const openable = it.path && it.overlay;
    const tip = openable ? `Open scene ${it.n} in the viewer`
                          : `Scene ${it.n} has no segment/overlay pair to open`;
    d.title = line ? `${tip}\n\n\u201c${line}\u201d` : tip;
    if (openable) {
      d.style.cursor = 'pointer';
      d.onclick = () => openPair(it.path, it.overlay);
    }
    return d;
  }

  function tlRender() {
    tlRows.innerHTML = '';
    if (!STORE_SCENES) return;
    for (const it of STORE_SCENES) tlRows.appendChild(tlRow(it));
    const dirtyCount = STORE_SCENES.filter(it => it.base_edited || it.over_edited).length;
    const scripted = ((SCRIPT && SCRIPT.scenes) || []).length;
    tlStatus.textContent = `${STORE_SCENES.length} scene(s) loaded`
      + (dirtyCount ? ` — ${dirtyCount} with unsaved changes` : ' — all pristine')
      + (scripted ? ` · script.json: ${scripted} line(s)` : ' · no script.json');
  }

  async function tlSaveOne(slug, force) {
    const r = await fetch('/api/save_scene', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slug, force }) });
    return r.json();
  }

  // Same stale/confirm/retry shape as the editor's own saveScene() — asks
  // once, retries with force, because the file changing since this list was
  // loaded means some OTHER save already landed here first.
  async function tlSaveScene(it) {
    const layers = [];
    if (it.base_edited && it.base_slug) layers.push(['segment', it.base_slug]);
    if (it.over_edited && it.over_slug) layers.push(['overlay', it.over_slug]);
    if (!layers.length) return;
    const names = layers.map(l => l[0]).join(' and ');
    if (!confirm(`Save scene ${it.n} (${names}) to sandbox/? This overwrites the current file there — the previous version is archived to its own z_History/ first.`)) return;
    for (const [name, slug] of layers) {
      let d = await tlSaveOne(slug, false);
      if (d.error === 'stale') {
        if (!confirm(`${d.message}\n\nOverwrite it anyway?`)) {
          tlStatus.textContent = `Save stopped on scene ${it.n} ${name} — ${d.message}`;
          return;
        }
        d = await tlSaveOne(slug, true);
      }
      if (d.error) { tlStatus.textContent = `Save failed on scene ${it.n} ${name}: ${d.error}`; return; }
    }
    tlStatus.textContent = `Saved scene ${it.n}.`;
    tlLoad();   // re-pull the real state rather than guess it locally
  }

  async function tlLoad() {
    if (!LOADED()) { tlStatus.textContent = 'Nothing loaded — open a pair first.'; return; }
    tlStatus.textContent = 'Loading…';
    try {
      const r = await fetch(`/api/load_store?path=${encodeURIComponent(SCENE.base_rel)}`);
      const d = await r.json();
      if (d.error) { tlStatus.textContent = `Load failed: ${d.error}`; return; }
      const ver = d.current_version;
      STORE_SCENES = (d.by_version && d.by_version[ver]) || d.by_version?.[Object.keys(d.by_version)[0]] || [];
      tlRender();
    } catch (e) {
      tlStatus.textContent = `Load failed: ${e.message} — is the main editor running (shared/serve.py, port 8842)?`;
    }
  }

  document.getElementById('tlLoadBtn').onclick = pickStores;

  // A REAL unload, not a repaint. Three separate places hold this scene and
  // all three have to let go, or the page looks empty while every tool
  // still quietly acts on the scene that was supposedly cleared:
  //
  //   1. the DOM            — the pictures, counts, filmstrip, panels
  //   2. this page's JS     — one `SCENE = null`, because SCENE is the only
  //                           thing that holds it (see SCENE's own comment)
  //
  // The server used to be a third place, holding the open pair in module
  // globals — so a cleared page still had Build building the old scene, and
  // two browser tabs silently fought over one slot. The API takes the pair
  // explicitly now, so there is no server-side copy left to clear.
  document.getElementById('tlClearBtn').onclick = () => {
    if (running) running = false;
    showEmpty();                 // the scene itself
    STORE_SCENES = null;         // and the store listing beside it
    SCRIPT = null;
    tlRows.innerHTML = '';
    tlStatus.textContent = 'Nothing loaded — click Load.';
    history.replaceState(null, '', location.pathname);
  };

  tlSaveMp4Btn.onclick = async () => {
    if (lastBuiltFrames == null) return;
    tlSaveMp4Btn.disabled = true;
    try {
      const r = await fetch(`/api/save_mp4?${pairQS()}&n=${lastBuiltFrames}`);
      const d = await r.json();
      tlStatus.textContent = d.error ? `Save MP4 failed: ${d.error}` : `Saved: ${d.saved}`;
    } catch (e) {
      tlStatus.textContent = `Save MP4 failed: ${e.message}`;
    } finally {
      tlSaveMp4Btn.disabled = false;
    }
  };

  const plusBtn = document.getElementById('plusBtn');
  const speedSel = document.getElementById('speedSel');
  let running = false;

  function setRunning(on) {
    running = on;
    plusBtn.classList.toggle('running', on);
    plusBtn.textContent = on ? '■' : '+';
    plusBtn.title = on ? 'Stop auto-blending' : '+';
    speedSel.disabled = on;
  }

  // Auto-blend: combine, wait one frame-interval at the chosen fps, repeat
  // — until the last frame combines itself (hadNext comes back false) or
  // `running` goes false from the stop click below, whichever first.
  async function runAuto(fps) {
    setRunning(true);
    const delayMs = 1000 / fps;
    while (running) {
      const hadNext = await combineCurrentFrame();
      if (!hadNext || !running) break;
      await new Promise(r => setTimeout(r, delayMs));
    }
    setRunning(false);
  }

  // Build the WHOLE scene (frame 1 through SCENE.max_n) via the server, and mark
  // every one of those frames as combined here too — so the filmstrip count,
  // the totals line and the scrub slider all agree with reality afterward,
  // even though this path never drew them one at a time in the browser.
  // Not stoppable like the fps loop below: it's one request, not a series of
  // waits, so there's nothing meaningful for a second click to interrupt.
  async function runBuild() {
    plusBtn.disabled = true;
    speedSel.disabled = true;
    try {
      await buildClip(SCENE.max_n);
      for (let f = 1; f <= SCENE.max_n; f++) combined.add(f);
      document.getElementById('combinedCount').textContent = combined.size;
      updateScrub();
      n = SCENE.max_n;
      render();
    } catch (e) {
      buildStatus.textContent = `Build failed: ${e.message}`;
    } finally {
      plusBtn.disabled = false;
      speedSel.disabled = false;
    }
  }

  // Single mode: exactly the old one-click-one-frame behaviour, focus kept
  // on + so a run of manual clicks (or repeated Enter/Space) still works.
  // A speed selected instead turns + into a start/stop toggle for
  // runAuto() — press once to start blending at that rate, press the same
  // (now red) button again to stop early. Build skips that animation
  // entirely: its pace is the ffmpeg process, not a chosen fps.
  plusBtn.onclick = async () => {
    if (running) { running = false; return; }   // this click is the STOP
    if (!LOADED()) { status.textContent = 'Nothing loaded — open a pair, or click Load.'; return; }
    const speed = speedSel.value;
    if (speed === 'single') {
      await combineCurrentFrame();
      plusBtn.focus();
    } else if (speed === 'build') {
      runBuild();   // not awaited — button disables itself for its own duration
    } else {
      runAuto(+speed);   // not awaited — a stop click must reach the loop above
    }
  };

  document.getElementById('prevBtn').onclick = () => { if (LOADED() && !running && n > 1) { n--; render(); } };
  document.getElementById('nextBtn').onclick = () => { if (LOADED() && !running && n < SCENE.max_n) { n++; render(); } };
  document.addEventListener('keydown', e => {
    if (e.key === 'ArrowLeft') document.getElementById('prevBtn').click();
    if (e.key === 'ArrowRight') document.getElementById('nextBtn').click();
  });

  // ── sarah_clips/libs ─────────────────────────────────────────────────────
  // The list itself is read-only, refreshed whenever a pair is opened. Each
  // file also gets a checkbox: checking one pulls its frames (a still is
  // one frame; a clip is every frame) into the inspector below. That
  // inspector is a SEPARATE viewer, slider and frame strip from the
  // scene's own — Carson's call, so browsing a library clip never disturbs
  // where you are in the scene's own combined-frame review.
  const libStatus = document.getElementById('libStatus');
  const libGroups = document.getElementById('libGroups');
  const humanSize = b => b < 1024 ? `${b}B` : b < 1048576 ? `${(b / 1024).toFixed(0)}KB` : `${(b / 1048576).toFixed(1)}MB`;

  const libInspector = document.getElementById('libInspector');
  const libViewerImg = document.getElementById('libViewerImg');
  const libSlider = document.getElementById('libSlider');
  const libFrameRow = document.getElementById('libFrameRow');
  const libNEl = document.getElementById('libN');
  const libTotalEl = document.getElementById('libTotal');

  let PICKED = [];        // checked clips' metadata, in the order checked
  let LIB_FRAMES = [];    // every picked clip's frames, flattened into one list

  const libFrameUrl = (clip, local) => `/${clip.slug}/frames/frame_${pad(local + 1)}${clip.ext}`;

  function renderLibFrameRow() {
    libFrameRow.innerHTML = '';
    LIB_FRAMES.forEach((f, i) => {
      const d = document.createElement('div');
      d.className = 'libframe';
      d.style.backgroundImage = `url(${f.url})`;
      d.title = `${f.clip.name} — frame ${f.local + 1}/${f.clip.n}`;
      d.onclick = () => { libSlider.value = i; showLibFrame(i); };
      libFrameRow.appendChild(d);
    });
  }

  function showLibFrame(i) {
    const f = LIB_FRAMES[i];
    [...libFrameRow.children].forEach((d, j) => d.classList.toggle('cur', j === i));
    if (!f) { libViewerImg.removeAttribute('src'); libNEl.textContent = '—'; return; }
    libViewerImg.src = f.url;
    libNEl.textContent = i + 1;
    const cur = libFrameRow.children[i];
    if (cur) cur.scrollIntoView({block: 'nearest', inline: 'center'});
  }

  // Rebuilds the flattened frame list from PICKED, in checked order —
  // called after every check/uncheck, and on Clear / a scene switch.
  function rebuildLibFrames() {
    LIB_FRAMES = [];
    for (const clip of PICKED)
      for (let i = 0; i < clip.n; i++) LIB_FRAMES.push({url: libFrameUrl(clip, i), clip, local: i});
    libInspector.hidden = LIB_FRAMES.length === 0;
    libSlider.max = Math.max(0, LIB_FRAMES.length - 1);
    libSlider.disabled = LIB_FRAMES.length === 0;
    libTotalEl.textContent = LIB_FRAMES.length || '—';
    renderLibFrameRow();
    showLibFrame(0);
  }

  libSlider.oninput = () => showLibFrame(+libSlider.value);

  // ── Clip-Gap Builder ─────────────────────────────────────────────────────
  // A second, separate strip below the Frame Selector. The Selector browses
  // whatever's checked; clicking its Frame N/Total button COPIES that one
  // frame down here, in the order copied. This is how a gap-filler gets
  // hand-assembled: pick a frame, look at it, pick the next, and scrub back
  // and forth down here to see the run of idle motion it adds up to.
  //
  // Deliberately NOT reset when a clip is un/re-checked above, or when the
  // Load picker switches to a different scene — a collection built by hand
  // is real work, and only Clear (which empties everything) should lose it.
  let BUILDER_FRAMES = [];
  const builderPanel = document.getElementById('builderPanel');
  const builderViewerImg = document.getElementById('builderViewerImg');
  const builderSlider = document.getElementById('builderSlider');
  const builderFrameRow = document.getElementById('builderFrameRow');
  const builderNEl = document.getElementById('builderN');
  const builderTotalEl = document.getElementById('builderTotal');
  const libPickBtn = document.getElementById('libPickBtn');

  function renderBuilderFrameRow() {
    builderFrameRow.innerHTML = '';
    BUILDER_FRAMES.forEach((f, i) => {
      const d = document.createElement('div');
      d.className = 'libframe';
      d.style.backgroundImage = `url(${f.url})`;
      d.title = `${f.clip.name} — frame ${f.local + 1}/${f.clip.n}`;
      d.onclick = () => { builderSlider.value = i; showBuilderFrame(i); };
      builderFrameRow.appendChild(d);
    });
  }

  function showBuilderFrame(i) {
    const f = BUILDER_FRAMES[i];
    [...builderFrameRow.children].forEach((d, j) => d.classList.toggle('cur', j === i));
    if (!f) { builderViewerImg.removeAttribute('src'); builderNEl.textContent = '—'; return; }
    builderViewerImg.src = f.url;
    builderNEl.textContent = i + 1;
    const cur = builderFrameRow.children[i];
    if (cur) cur.scrollIntoView({block: 'nearest', inline: 'center'});
  }

  function rebuildBuilderFrames(landOn) {
    builderSlider.max = Math.max(0, BUILDER_FRAMES.length - 1);
    builderSlider.disabled = BUILDER_FRAMES.length === 0;
    builderTotalEl.textContent = BUILDER_FRAMES.length || '—';
    renderBuilderFrameRow();
    const i = landOn != null ? landOn : 0;
    builderSlider.value = i;
    showBuilderFrame(i);
  }

  builderSlider.oninput = () => showBuilderFrame(+builderSlider.value);

  // The Frame N/Total button IS the copy action — clicking it takes
  // whatever the Selector's slider is currently sitting on.
  libPickBtn.onclick = () => {
    const f = LIB_FRAMES[+libSlider.value];
    if (!f) return;
    BUILDER_FRAMES.push(f);
    rebuildBuilderFrames(BUILDER_FRAMES.length - 1);
  };

  async function toggleLibClip(f, checked) {
    if (!checked) {
      PICKED = PICKED.filter(c => c.path !== f.path);
      rebuildLibFrames();
      return;
    }
    try {
      const r = await fetch(`/api/lib_frames?path=${encodeURIComponent(f.path)}`);
      const d = await r.json();
      if (d.error) { libStatus.textContent = `${f.name}: ${d.error}`; return; }
      PICKED.push({path: f.path, name: f.name, n: d.n, slug: d.slug, ext: d.ext});
      rebuildLibFrames();
    } catch (e) {
      libStatus.textContent = `${f.name}: ${e.message}`;
    }
  }

  async function loadLibs() {
    PICKED = [];
    rebuildLibFrames();
    try {
      const r = await fetch(`/api/libs_list?${pairQS()}`);
      const d = await r.json();
      if (d.error) { libStatus.textContent = d.error; return; }
      if (!d.root) { libStatus.textContent = 'No sarah_clips/libs/ folder for this store yet.'; return; }
      const total = d.groups.reduce((s, g) => s + g.files.length, 0);
      libStatus.textContent = `${d.root} — ${total} file(s)`;
      builderPanel.hidden = false;
      libGroups.innerHTML = '';
      for (const g of d.groups) {
        const box = document.createElement('div');
        box.className = 'libgroup';
        const head = document.createElement('h4');
        head.textContent = `${g.folder} (${g.files.length})`;
        box.appendChild(head);
        if (!g.files.length) {
          const e = document.createElement('div');
          e.className = 'libempty';
          e.textContent = 'empty';
          box.appendChild(e);
        }
        for (const f of g.files) {
          const row = document.createElement('div');
          row.className = 'libfile';
          const meta = f.dur != null ? `${f.dur}s` : humanSize(f.size);
          const cb = document.createElement('input');
          cb.type = 'checkbox';
          cb.title = `Inspect ${f.name}'s frames below`;
          cb.onchange = () => toggleLibClip(f, cb.checked);
          const name = document.createElement('span');
          name.className = 'name'; name.title = f.name; name.textContent = f.name;
          const metaEl = document.createElement('span');
          metaEl.className = 'meta'; metaEl.textContent = meta;
          row.appendChild(cb); row.appendChild(name); row.appendChild(metaEl);
          box.appendChild(row);
        }
        libGroups.appendChild(box);
      }
    } catch (e) {
      libStatus.textContent = `Couldn't load: ${e.message}`;
    }
  }
  // ── the Load picker ──────────────────────────────────────────────────────
  // Two steps in one modal: a store, then one of that store's video folders.
  // Before this, "Load" needed the scene's own path to already be known —
  // which meant you could only load the store you were already in. There was
  // no way to get from one store to another without hand-editing the URL.
  const pickBack = document.getElementById('pickBack');
  const pickBody = document.getElementById('pickBody');
  const pickCrumb = document.getElementById('pickCrumb');
  const pickBackBtn = document.getElementById('pickBackBtn');

  function pickClose() { pickBack.hidden = true; pickBody.innerHTML = ''; }
  document.getElementById('pickCancel').onclick = pickClose;
  pickBack.onclick = e => { if (e.target === pickBack) pickClose(); };
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !pickBack.hidden) pickClose();
  });

  function pickShow(msg) {
    pickBack.hidden = false;
    pickBody.innerHTML = `<div class="modalmsg">${msg}</div>`;
  }

  async function pickStores() {
    pickCrumb.textContent = 'step 1 of 2 — store';
    pickBackBtn.hidden = true;
    pickShow('Loading stores…');
    let d;
    try {
      d = await (await fetch('/api/stores')).json();
    } catch (e) { return pickShow(`Could not list stores: ${e.message}`); }
    if (d.error) return pickShow(`Could not list stores: ${d.error}`);
    const stores = (d.stores || []).filter(s => (s.videos || []).length);
    if (!stores.length) return pickShow('No stores with a video folder were found.');

    pickBody.innerHTML = '';
    for (const st of stores) {
      const b = document.createElement('button');
      b.className = 'pickitem';
      const n = st.videos.length;
      b.innerHTML = `<span><span class="biz">${st.business} / </span>${st.store}</span>` +
                    `<span class="meta">${n} video${n === 1 ? '' : 's'}</span>`;
      b.onclick = () => pickVideos(st);
      pickBody.appendChild(b);
    }
  }

  function pickVideos(st) {
    pickCrumb.textContent = `step 2 of 2 — ${st.store}`;
    pickBackBtn.hidden = false;
    pickBackBtn.onclick = pickStores;
    pickBody.innerHTML = '';
    for (const v of st.videos) {
      const b = document.createElement('button');
      b.className = 'pickitem';
      const n = (v.scenes || []).length;
      b.disabled = !v.has_sandbox;
      b.innerHTML = `<span>${v.name}</span><span class="meta">` +
        (v.has_sandbox ? `${n} scene${n === 1 ? '' : 's'}` : 'no sandbox yet') + `</span>`;
      if (v.has_sandbox) b.onclick = () => loadVideo(v.root);
      else b.title = 'This video has no sandbox/ folder, so there is nothing to work on yet.';
      pickBody.appendChild(b);
    }
  }

  // Load a whole video folder: every scene in its sandbox, plus the
  // narration script that belongs to them. Opens the first scene so the
  // viewer is showing something real rather than an empty frame.
  async function loadVideo(root) {
    pickShow('Loading scenes…');
    let d;
    try {
      d = await (await fetch(`/api/load_video?root=${encodeURIComponent(root)}`)).json();
    } catch (e) { return pickShow(`Load failed: ${e.message}`); }
    if (d.error) return pickShow(`Load failed: ${d.error}`);

    STORE_SCENES = (d.by_version && (d.by_version[d.current_version] ||
                    d.by_version[Object.keys(d.by_version)[0]])) || [];
    SCRIPT = d.script || null;
    tlRender();
    pickClose();

    const first = STORE_SCENES.find(it => it.path && it.overlay);
    if (first) await openPair(first.path, first.overlay);
    else tlStatus.textContent =
      `${STORE_SCENES.length} scene(s) — none has both a segment and an overlay to open.`;
  }

  // ── loading and unloading a scene ────────────────────────────────────────
  // These two are exact opposites, and that symmetry is the whole point of
  // the restructure: showEmpty() is what the page looks like with SCENE
  // null, openPair() is what it looks like with SCENE set. Clear just calls
  // showEmpty(). Nothing else has to be "undone".

  function showEmpty() {
    SCENE = null;
    n = 1;
    combined.clear();
    document.getElementById('pageTitle').textContent = 'Frame Blender — nothing loaded';
    document.title = 'Frame Blender';
    document.getElementById('combinedCount').textContent = '0';
    document.getElementById('filmstrip').innerHTML = '';
    status.textContent = '';
    baseImg.removeAttribute('src');
    overImg.removeAttribute('src');
    for (const id of ['baseN', 'overN', 'baseTotal', 'overTotal', 'totalFrames'])
      document.getElementById(id).textContent = '—';
    document.getElementById('prevBtn').disabled = true;
    document.getElementById('nextBtn').disabled = true;
    canvas.style.display = 'none';
    scrubSlider.value = 0; scrubSlider.max = 0; scrubSlider.disabled = true;
    scrubLabel.textContent = 'No frames combined yet';
    clipVideo.removeAttribute('src');
    clipVideo.style.display = 'none';
    buildStatus.textContent = '';
    playVideoBtn.disabled = true;
    playVideoBtn.title = 'No built video yet';
    lastBuiltFrames = null;
    tlSaveMp4Btn.disabled = true;
    tlSaveMp4Btn.title = 'Build a clip first';
    libGroups.innerHTML = '';
    libStatus.textContent = 'Nothing loaded.';
    PICKED = [];
    rebuildLibFrames();
    builderPanel.hidden = true;
    BUILDER_FRAMES = [];
    rebuildBuilderFrames();
  }

  async function openPair(baseRel, overRel) {
    showEmpty();
    status.textContent = 'Opening…';
    try {
      const q = new URLSearchParams({base: baseRel, overlay: overRel});
      const r = await fetch(`/api/open_pair?${q}`);
      const d = await r.json();
      if (d.error) { status.textContent = `Could not open: ${d.error}`; return; }
      SCENE = d;
      document.getElementById('pageTitle').textContent = `Frame Blender — ${d.label}`;
      document.title = `Frame Blender — ${d.label}`;
      document.getElementById('baseTotal').textContent = d.base_n;
      document.getElementById('overTotal').textContent = d.over_n;
      document.getElementById('totalFrames').textContent = d.max_n;
      status.textContent = '';
      playVideoBtn.disabled = false;
      playVideoBtn.title = 'Build the whole scene, then play it';
      render();
      loadLibs();
      // Keep the URL honest, so a reload or a copied link reopens THIS pair
      // rather than whatever the server would have defaulted to.
      const u = new URL(location);
      u.search = q.toString();
      history.replaceState(null, '', u);
    } catch (e) {
      status.textContent = `Could not open: ${e.message}`;
    }
  }

  // ── bootstrap ────────────────────────────────────────────────────────────
  // The page ships empty. A scene arrives one of three ways, all the same
  // code path: a ?base=&overlay= in the URL (so an old bookmark still
  // works), clicking a row in Timeline Scenes, or nothing at all — which is
  // a perfectly good state to sit in, not an error to recover from.
  const qs = new URLSearchParams(location.search);
  if (qs.get('base') && qs.get('overlay')) {
    openPair(qs.get('base'), qs.get('overlay'));
  } else {
    showEmpty();
  }
})();
