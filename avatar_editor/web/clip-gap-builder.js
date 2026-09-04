// The Clip-Gap Builder — the second frame row, and its selection.
// ---------------------------------------------------------------------------
// Split out of gap-builder.js on 2026-09-04. That file was 1,184 lines doing
// eight jobs; its own section banners already said where the seams were, and
// these are those seams.
//
// ⚠ ORDER MATTERS. None of these files is wrapped in an IIFE — they share
// ONE flat top-level scope, deliberately, the way ordered <script> tags
// always have. So index.html's load order reproduces the order the single
// file ran in, and a `const` used at load time must be declared in a file
// loaded earlier. Moving a <script> tag is a behaviour change.
// ---------------------------------------------------------------------------

'use strict';

// ── Clip-Gap Builder ─────────────────────────────────────────────────────
const builderPanel = document.getElementById('builderPanel');
const builderViewerImg = document.getElementById('builderViewerImg');
const builderSlider = document.getElementById('builderSlider');
const builderFrameRow = document.getElementById('builderFrameRow');
const builderNEl = document.getElementById('builderN');
const builderTotalEl = document.getElementById('builderTotal');

// A full reset of the Builder's own select/copy mechanism — called at hard
// reset points (a scene switch/Clear in app.js's showEmpty(), and
// gmClearAll below), never from inside the 3-click cycle itself (which
// only ever clears what its OWN click needs cleared).
function disarmSelectMode() {
  BUILDER.armed = false;
  BUILDER.phase = 0;
  BUILDER.rangeStart = null;
  gmBuilderSelectFrames.classList.remove('armed');
  gmBuilderCopySelected.classList.remove('ready');
}

function setSelected(indices) {
  BUILDER.selected = new Set(indices);
  [...builderFrameRow.children].forEach((d, j) => d.classList.toggle('selected', BUILDER.selected.has(j)));
}

function renderBuilderFrameRow() {
  builderFrameRow.innerHTML = '';
  BUILDER.frames.forEach((f, i) => {
    const d = document.createElement('div');
    d.className = 'libframe' + (BUILDER.selected.has(i) ? ' selected' : '');
    d.style.backgroundImage = `url(${f.url})`;
    d.title = `${f.clip.name} — frame ${f.local + 1}/${f.clip.n}`;
    d.onclick = () => {
      // Same 3-click cycle as the Frame Selector's own row (see
      // copySelectDblClick's old comment, now LIB.phase's) — click 1: start.
      // Click 2: end (or the same frame again for a one-frame selection).
      // Click 3: reset, and this click picks nothing on its own.
      if (BUILDER.armed) {
        if (BUILDER.phase === 0) {
          BUILDER.rangeStart = i;
          setSelected([i]);
          BUILDER.phase = 1;
        } else if (BUILDER.phase === 1) {
          if (i === BUILDER.rangeStart) {
            setSelected([i]);
          } else {
            const lo = Math.min(BUILDER.rangeStart, i), hi = Math.max(BUILDER.rangeStart, i);
            const range = [];
            for (let k = lo; k <= hi; k++) range.push(k);
            setSelected(range);
          }
          BUILDER.rangeStart = null;
          BUILDER.phase = 2;
          gmBuilderCopySelected.classList.add('ready');
        } else {
          setSelected([]);
          BUILDER.rangeStart = null;
          BUILDER.phase = 0;
          gmBuilderCopySelected.classList.remove('ready');
        }
      }
      gapLog('builder_frame_click', {i, builderArmed: BUILDER.armed, after: gapSnapshot()});
      // Still moves the viewer here too, armed or not, same as before —
      // and THIS is what tells Paste Selected where "here" is: a plain
      // click on a frame here, then Paste Selected, no arming step of its
      // own (see gmPasteSelected.onclick, which just reads
      // builderSlider.value).
      builderSlider.value = i; showBuilderFrame(i);
    };
    builderFrameRow.appendChild(d);
  });
}

function showBuilderFrame(i) {
  const f = BUILDER.frames[i];
  [...builderFrameRow.children].forEach((d, j) => d.classList.toggle('cur', j === i));
  BUILDER.curClip = f ? f.clip : null;
  if (!BUILDER.stepping) Players.refresh();
  if (!f) { builderViewerImg.removeAttribute('src'); builderNEl.textContent = '—'; return; }
  builderViewerImg.src = f.url;
  builderNEl.textContent = i + 1;
  const cur = builderFrameRow.children[i];
  if (cur) cur.scrollIntoView({block: 'nearest', inline: 'center'});
}

// Deliberately does NOT save to storage — it also runs during the RESET
// at the start of showEmpty() (BUILDER.frames = [] before restoreGlobals()
// gets a chance to read what was saved), and saving there would overwrite
// the very collection a refresh is about to bring back before it can.
// Only the actual mutation sites (doPaste, and the Gap Builder Menu
// actions) save.
function rebuildBuilderFrames(landOn) {
  // Save to Working Clips is only offered when there is something to save.
  WorkingClips.refreshButtons();
  // The collection this run was walking has been rebuilt, so every
  // position it held is meaningless — same rule the Frame Selector's row
  // follows in rebuildLibFrames().
  GapBuilder.endRun();
  builderSlider.max = Math.max(0, BUILDER.frames.length - 1);
  builderSlider.disabled = BUILDER.frames.length === 0;
  builderTotalEl.textContent = BUILDER.frames.length || '—';
  renderBuilderFrameRow();
  const i = landOn != null ? landOn : 0;
  builderSlider.value = i;
  showBuilderFrame(i);
}

builderSlider.oninput = () => showBuilderFrame(+builderSlider.value);

// Runs the actual paste: Carson picks where with a PLAIN click on a frame
// in the row below first (same click that always moves the viewer there —
// no separate arming step), then clicks Paste Selected, which just reads
// wherever that left builderSlider sitting. An empty Builder has no frame
// to have clicked, so it always inserts at the very start (0) instead.
function doPaste(insertAt) {
  const builderLenBefore = BUILDER.frames.length;
  BUILDER.frames.splice(insertAt, 0, ...SHARED.clipboard);
  const landOn = insertAt + SHARED.clipboard.length - 1;
  const n = SHARED.clipboard.length;
  gapLog('do_paste', {insertAt, n, builderLenBefore, builderLenAfter: BUILDER.frames.length});
  SHARED.clipboard = [];
  gmPasteSelected.classList.remove('ready');
  // The whole select → copy → paste cycle is done — every button that was
  // part of it goes back to plain white, both Select Frames buttons
  // included (the clipboard could have come from either row), exactly
  // like finishing a copy already resets its own Copy Selected's green.
  LIB.armed = false;
  gmSelectFrames.classList.remove('armed');
  BUILDER.armed = false;
  gmBuilderSelectFrames.classList.remove('armed');
  rebuildBuilderFrames(landOn);
  saveStore({builderFrames: BUILDER.frames});
  libStatus.textContent = insertAt > 0
    ? `Pasted ${n} frame(s) after frame ${insertAt}.`
    : `Pasted ${n} frame(s).`;
}

// `f.source` ('store' | 'common') says which library the clip came from,
// and travels on every LIB.picked/LIB.frames entry from here on — the server
// needs it on every later /api/lib_frames or /api/lib_media call, since
// Sarah/ and a store's own sarah_clips/libs/ are siblings, not one nested
// in the other, so a bare path is ambiguous between them. `path` itself
// stays the identity key for lookups (LIB.picked.filter(c => c.path !== ...)
// below): the two sources' paths can never collide, because a store path
// always carries that store's own long Customers/-relative prefix and a
// common path never does.
async function toggleLibClip(f, checked) {
  if (!checked) {
    LIB.picked = LIB.picked.filter(c => c.path !== f.path);
    rebuildLibFrames();
    OriginalAudio.rebuild();   // the stack follows every checkbox
    savePickedForCurrentPair();
    return;
  }
  try {
    const r = await fetch(`/api/lib_frames?source=${f.source}&path=${encodeURIComponent(f.path)}`);
    const d = await r.json();
    if (d.error) { libStatus.textContent = `${f.name}: ${d.error}`; return; }
    // has_audio is MEASURED server-side (see has_audible() in serve.py) —
    // every .webm in this library carries an Opus stream, including the
    // silent idle loops, so "has a stream" was never the right question.
    LIB.picked.push({path: f.path, name: f.name, n: d.n, slug: d.slug, ext: d.ext,
                 has_audio: !!f.has_audio, source: f.source});
    rebuildLibFrames();
    OriginalAudio.rebuild();   // the stack follows every checkbox
    savePickedForCurrentPair();
  } catch (e) {
    libStatus.textContent = `${f.name}: ${e.message}`;
  }
}

// Renders one library's groups into its own panel — the exact same DOM
// shape whichever of the two panels this is. `source` ('store'|'common')
// is what makes it possible to tell the two apart afterwards: it rides on
// every clip object this builds, and every later fetch (toggleLibClip,
// the Play buttons, Working Clips) reads it straight off the clip rather
// than asking which panel it came from.
//
// LIB.order — the FLAT, combined display order both panels' checked
// clips share, for OriginalAudio's stack (Carson's rule: it plays down
// the list the way you read it) — is appended to, not reset, so calling
// this once per panel in the same pass builds one continuous order:
// whatever the COMMON panel shows, top to bottom, then the STORE panel's,
// top to bottom — left to right, the same order the two panels sit in on
// screen.
function renderLibSource(d, groupsEl, statusEl, source, savedPaths) {
  const total = d.groups.reduce((s, g) => s + g.files.length, 0);
  statusEl.textContent = `${d.root} — ${total} file(s)`;
  groupsEl.innerHTML = '';
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
      LIB.order.push(f.path);   // display order, for OriginalAudio's stack
      const row = document.createElement('div');
      row.className = 'libfile';
      const meta = f.dur != null ? `${f.dur}s` : humanSize(f.size);
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.title = `Inspect ${f.name}'s frames below`;
      cb.onchange = () => toggleLibClip(f, cb.checked);
      const name = document.createElement('span');
      name.className = 'name';
      // Sound Bits: a short label (the scene name a "01-" prefix and the
      // extension stripped off) with the FULL spoken line as its tooltip
      // — f.line comes from that scene's own script.json (see
      // libs_list()'s server-side comment), so the words shown here are
      // never retyped from anywhere. Every other group keeps the plain
      // filename it always has.
      if (g.folder === 'sound_bits') {
        const label = f.name.replace(/\.[^.]+$/, '').replace(/^\d+-/, '');
        name.title = f.line || f.name;
        name.textContent = label;
      } else {
        name.title = f.name; name.textContent = f.name;
      }
      const metaEl = document.createElement('span');
      metaEl.className = 'meta'; metaEl.textContent = meta;
      row.appendChild(cb); row.appendChild(name); row.appendChild(metaEl);
      if (g.folder === 'sound_bits') {
        const playBtn = document.createElement('button');
        playBtn.type = 'button';
        playBtn.className = 'soundBitPlay';
        playBtn.textContent = '▶';
        playBtn.title = f.line ? `Play: "${f.line}"` : 'Play this clip';
        playBtn.onclick = () => OriginalAudio.playClip(f, name.textContent);
        row.appendChild(playBtn);
      }
      box.appendChild(row);
      if (savedPaths.has(f.path)) {
        cb.checked = true;
        toggleLibClip(f, true);
      }
    }
    groupsEl.appendChild(box);
  }
}

async function loadLibs() {
  LIB.picked = [];
  rebuildLibFrames();
  // The store panel's own header — the store, then the video, replacing
  // "sarah_clips/libs" (Carson's own call, 2026-09-03): which folder it
  // reads is an implementation detail; which STORE and VIDEO you're
  // looking at is what actually matters here. Set from SCENE.base_rel
  // rather than waiting on the /api/libs_list response below, so it's
  // right even when that store's own library is empty or archived.
  const sv = SCENE && storeVideoFromPath(SCENE.base_rel);
  libHeaderStore.textContent = sv ? sv.store : '—';
  libHeaderVideo.textContent = sv ? sv.video : '—';
  // A fresh pair may be a different STORE, so both are re-resolved below,
  // never carried over from whatever pair was open before.
  LIB.restPosePath = null;
  LIB.restPoseSource = null;
  LIB.restPoseFrame = null;
  LIB.order = [];

  // What was checked for THIS pair last time — a refresh, or coming back
  // to a scene already visited this session, both restore it. Shared by
  // both panels: LIB.picked can hold entries from either source, and their
  // paths never collide (a store path always carries that store's own
  // long Customers/-relative prefix; a common path never does), so one
  // Set correctly re-ticks the right box in whichever panel it belongs to.
  const rec = SCENE && loadStore().pairs?.[pairKey(SCENE.base_rel, SCENE.over_rel)];
  const savedPaths = new Set((rec?.picked || []).map(c => c.path));

  // COMMON first, so its clips sort ahead of the store's own in LIB.order
  // — matching the two panels' left-to-right order on screen. Independent
  // try/catch: a broken store fetch should not also blank the common
  // panel, and Sarah/ not existing yet on a fresh checkout shouldn't block
  // the store's own library from loading. The spinner's own hide sits in a
  // `finally`, not after the try block, because two of the branches below
  // `return` early (the store one) — only `finally` is guaranteed to run
  // on every one of those paths.
  libSpinnerCommon.hidden = false;
  try {
    const r = await fetch('/api/libs_list?source=common');
    const d = await r.json();
    if (d.error) { libStatusCommon.textContent = d.error; }
    else if (!d.root) { libStatusCommon.textContent = 'No Sarah/ folder found.'; }
    else {
      // The one file every library carries under this exact name — see
      // Sarah/README.md's "rest pose" section. Checked here FIRST: Sarah/
      // is the canonical, single source for it now (Carson's own split,
      // 2026-09-03) — a store's own copy under the store branch below is
      // only used as a fallback for a pair whose common library hasn't
      // been checked yet.
      for (const g of d.groups)
        for (const f of g.files)
          if (f.name === REST_POSE_NAME) { LIB.restPosePath = f.path; LIB.restPoseSource = 'common'; }
      renderLibSource(d, libGroupsCommon, libStatusCommon, 'common', savedPaths);
    }
  } catch (e) {
    libStatusCommon.textContent = `Couldn't load: ${e.message}`;
  } finally {
    libSpinnerCommon.hidden = true;
  }

  libSpinner.hidden = false;
  try {
    const r = await fetch(`/api/libs_list?${pairQS()}`);
    const d = await r.json();
    if (d.error) { libStatus.textContent = d.error; return; }
    if (!d.root) { libStatus.textContent = 'No sarah_clips/libs/ folder for this store yet.'; return; }
    if (LIB.restPosePath === null)
      for (const g of d.groups)
        for (const f of g.files)
          if (f.name === REST_POSE_NAME) { LIB.restPosePath = f.path; LIB.restPoseSource = 'store'; }
    renderLibSource(d, libGroups, libStatus, 'store', savedPaths);
  } catch (e) {
    libStatus.textContent = `Couldn't load: ${e.message}`;
  } finally {
    libSpinner.hidden = true;
  }
}
