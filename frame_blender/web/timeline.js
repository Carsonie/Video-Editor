// Frame Blender — Timeline Scenes.
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
    clearStore();                // the ONE point that erases what's persisted —
                                  // otherwise the NEXT refresh or Load would
                                  // just bring the Builder and picks right back
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
      saveProgressForCurrentPair();
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

  document.getElementById('prevBtn').onclick = () => { if (LOADED() && !running && n > 1) { n--; render(); saveProgressForCurrentPair(); } };
  document.getElementById('nextBtn').onclick = () => { if (LOADED() && !running && n < SCENE.max_n) { n++; render(); saveProgressForCurrentPair(); } };
  document.addEventListener('keydown', e => {
    if (e.key === 'ArrowLeft') document.getElementById('prevBtn').click();
    if (e.key === 'ArrowRight') document.getElementById('nextBtn').click();
  });
