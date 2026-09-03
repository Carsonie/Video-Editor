// Avatar Editor — the page's behaviour.
//
// Plain .js on purpose. Until 2026-08-30 all of this lived inside a Python
// string in player.py, where every brace had to be doubled for str.format()
// and a stray one broke the page at render time rather than in an editor.
// It is served as a static file now: no build step, no escaping, and the
// browser's own debugger lines up with the file.
//
// NOT wrapped in an IIFE, as of the 2026-09-01 split into two files (this
// one and gap-builder.js, loaded before it — see that file's own header).
// Both need one flat top-level scope to share SCENE, pairQS(), pad(), and
// the localStorage helpers without a formal interface between them; an
// IIFE around either file would hide its top-level bindings from the
// other. Safe here specifically because this is a single-purpose internal
// tool page, not a library — there is nothing else on the page for a
// leaked global to collide with.
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

  // ── persistence (the browser's own storage, not the server) ────────────────
  // The server is deliberately stateless (2026-08-30 restructure, so two tabs
  // can't fight over one remembered pair) — which also means it never had
  // anywhere to remember Frame Selector picks, Clip-Gap Builder frames, or a
  // Load result. Before this, a refresh silently threw all of that away; the
  // only thing that ever survived was the open pair itself, and only by
  // accident, because it happens to sit in the page's own URL.
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

  // The one thing that is NOT tied to one scene: the Clip-Gap Builder's own
  // collection. Called after every showEmpty()-driven reset (both a plain
  // refresh and an in-session scene switch go through showEmpty() first,
  // via openPair()) — NOT called by Clear, which empties storage first so
  // there is nothing left for this to bring back.
  function restoreGlobals() {
    const s = loadStore();
    if (Array.isArray(s.builderFrames) && s.builderFrames.length) {
      BUILDER_FRAMES = s.builderFrames;
      rebuildBuilderFrames(BUILDER_FRAMES.length - 1);
    }
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

  const pad = n => String(n).padStart(5, '0');
  const status = document.getElementById('status');

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
      <button class="ibtn undo" disabled title="This tool doesn't edit scenes itself yet, so there's nothing here to undo — Undo the change in the Segment and Avatar Editor (SAE) instead.">&#8630;</button>
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
    saveStore({storeScenes: STORE_SCENES, script: SCRIPT});
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
    document.getElementById('pageTitle').textContent = 'Avatar Editor — nothing loaded';
    document.title = 'Avatar Editor';
    status.textContent = '';
    libGroups.innerHTML = '';
    libStatus.textContent = 'Nothing loaded.';
    PICKED = [];
    rebuildLibFrames();
    BUILDER_FRAMES = [];
    SELECTED = new Set();
    disarmSelectMode();
    rebuildBuilderFrames();
    CLIPBOARD = [];
    // The player is frame-player.js's business, not this file's — one
    // call, rather than nine lines reaching into its internals.
    FramePlayer.reset();
  }

  async function openPair(baseRel, overRel) {
    showEmpty();
    restoreGlobals();
    status.textContent = 'Opening…';
    try {
      const q = new URLSearchParams({base: baseRel, overlay: overRel});
      const r = await fetch(`/api/open_pair?${q}`);
      const d = await r.json();
      if (d.error) { status.textContent = `Could not open: ${d.error}`; return; }
      SCENE = d;
      document.getElementById('pageTitle').textContent = `Avatar Editor — ${d.label}`;
      document.title = `Avatar Editor — ${d.label}`;
      status.textContent = '';
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
    restoreGlobals();
  }
