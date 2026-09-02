// Avatar Editor — sarah_clips/libs, the Frame Selector, and the Clip-Gap
// Builder. Split out of app.js on 2026-09-01, specifically because this is
// the one area about to grow a lot (the ten Gap Builder Controller Menu
// actions all act on BUILDER_FRAMES, defined here) — everything else on the
// page (the combine engine, Timeline Scenes, the Load popup, persistence)
// was staying roughly the size it already was.
//
// Neither this file nor app.js is wrapped in an IIFE — both need one flat
// top-level scope, not two separate private ones, so each can call
// straight into the other's declarations by name (this file's PICKED,
// LIB_FRAMES, BUILDER_FRAMES, rebuildLibFrames, rebuildBuilderFrames,
// toggleLibClip, loadLibs, savePickedForCurrentPair; app.js's SCENE,
// pairQS(), pad(), and the localStorage helpers loadStore/saveStore/
// savePair/pairKey). Loaded BEFORE app.js in index.html, because app.js's
// own bootstrap, at its very bottom, calls straight into loadLibs() and
// the two rebuild functions — they have to already exist by then.
'use strict';

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

// ── Sound Bits ───────────────────────────────────────────────────────────
// One shared player every Sound Bits row's own ▶ button loads into (see
// renderLibGroups' sound_bits branch, below) — same "one viewer, many
// things to pick" shape as the Frame Selector/Clip-Gap Builder already
// use, rather than a <video> per row. Plays straight off /api/lib_media
// (the raw file, audio intact — see that route's own comment in
// serve.py for why /api/lib_frames can't be reused for this).
const soundBitPlayer = document.getElementById('soundBitPlayer');
const soundBitVideo = document.getElementById('soundBitVideo');
const soundBitName = document.getElementById('soundBitName');
const soundBitRate = document.getElementById('soundBitRate');
// Lives in the Controller Menu's own "Audio Menu" section, not next to the
// video — one button, wherever the rest of the menu's buttons are, rather
// than a second set of transport controls bolted onto the player itself.
const gmSoundBitPlayPause = document.getElementById('gmSoundBitPlayPause');

function playSoundBit(f, label) {
  soundBitPlayer.hidden = false;
  soundBitName.textContent = label;
  soundBitVideo.src = `/api/lib_media?path=${encodeURIComponent(f.path)}`;
  soundBitVideo.playbackRate = +soundBitRate.value;
  soundBitVideo.play();
  soundBitPlayer.scrollIntoView({block: 'nearest'});
  gmSoundBitPlayPause.disabled = false;
}

soundBitRate.onchange = () => { soundBitVideo.playbackRate = +soundBitRate.value; };

// Keeps its own label in sync with whatever's actually happening to the
// video — including when a clip just runs out on its own, not only when
// this button is what paused it.
soundBitVideo.onplay = () => { gmSoundBitPlayPause.textContent = 'Pause'; };
soundBitVideo.onpause = () => { gmSoundBitPlayPause.textContent = 'Play'; };
gmSoundBitPlayPause.onclick = withActiveFlash(gmSoundBitPlayPause, () => {
  if (soundBitVideo.paused) soundBitVideo.play();
  else soundBitVideo.pause();
});

const libInspector = document.getElementById('libInspector');
const libViewerImg = document.getElementById('libViewerImg');
const libSlider = document.getElementById('libSlider');
const libFrameRow = document.getElementById('libFrameRow');
const libNEl = document.getElementById('libN');
const libTotalEl = document.getElementById('libTotal');
const libSelectedNEl = document.getElementById('libSelectedN');

let PICKED = [];        // checked clips' metadata, in the order checked
let LIB_FRAMES = [];    // every picked clip's frames, flattened into one list

// Which LIB_FRAMES indices are selected for Copy Selected — the Frame
// Selector's own equivalent of the Clip-Gap Builder's SELECTED. Armed by
// its own button, gmSelectFrames, below — while armed, a plain single
// click on a frame here does the selecting instead of only navigating,
// following a 3-click cycle (see gmSelectFrames.onclick and libPhase).
let LIB_SELECTED = new Set();
// The pending start of a click-1/click-2 range pick — null except between
// those two clicks (libPhase === 1).
let libRangeStart = null;
// 0: next click is click 1 (starts a selection). 1: next click is click 2
// (finishes it — same frame as click 1 collapses it to one frame). 2: a
// selection sits complete; the next click is click 3, a reset back to 0
// that clears it rather than picking anything.
let libPhase = 0;

// Whether the row and slider above are filtered down to JUST LIB_SELECTED
// (gmLibViewToggle, below) — a review mode, not a second selection
// mechanism. Toggling it OFF (back to the full collection) un-stages
// whatever was selected, same as click 3 does, since backing out of the
// review means starting over rather than leaving a stale pick armed.
let libShowSelectedOnly = false;

const libFrameUrl = (clip, local) => `/${clip.slug}/frames/frame_${pad(local + 1)}${clip.ext}`;

function setLibSelected(indices) {
  LIB_SELECTED = new Set(indices);
  libSelectedNEl.textContent = LIB_SELECTED.size;
  [...libFrameRow.children].forEach((d, j) => d.classList.toggle('selected', LIB_SELECTED.has(j)));
}

function renderLibFrameRow() {
  libFrameRow.innerHTML = '';
  LIB_FRAMES.forEach((f, i) => {
    const d = document.createElement('div');
    d.className = 'libframe' + (LIB_SELECTED.has(i) ? ' selected' : '');
    d.style.backgroundImage = `url(${f.url})`;
    d.title = `${f.clip.name} — frame ${f.local + 1}/${f.clip.n}`;
    d.onclick = () => {
      if (libArmed) {
        if (libPhase === 0) {
          libRangeStart = i;
          setLibSelected([i]);
          libPhase = 1;
        } else if (libPhase === 1) {
          if (i === libRangeStart) {
            setLibSelected([i]);
          } else {
            const lo = Math.min(libRangeStart, i), hi = Math.max(libRangeStart, i);
            const range = [];
            for (let k = lo; k <= hi; k++) range.push(k);
            setLibSelected(range);
          }
          libRangeStart = null;
          libPhase = 2;
          gmCopySelected.classList.add('ready');
          gmLibViewToggle.classList.add('ready');
        } else {
          // Click 3 — reset, and this click picks nothing on its own.
          setLibSelected([]);
          libRangeStart = null;
          libPhase = 0;
          gmCopySelected.classList.remove('ready');
          gmLibViewToggle.classList.remove('ready');
        }
      }
      gapLog('lib_frame_click', {i, libArmed, after: gapSnapshot()});
      // Still moves the viewer here too, armed or not, same as before — as
      // a POSITION in the current view, not necessarily this thumbnail's
      // raw index (the two differ once "Show Selected on Timeline" has
      // filtered the view down).
      const pos = libViewIndices().indexOf(i);
      libSlider.value = pos; showLibFrame(pos);
    };
    libFrameRow.appendChild(d);
  });
}

// The indices INTO LIB_FRAMES that the slider/viewer currently scrub
// through — every frame normally, or just LIB_SELECTED, sorted, while
// "Show Selected on Timeline" is on. showLibFrame's own argument is a
// POSITION into whichever of these is current, not a raw LIB_FRAMES index.
function libViewIndices() {
  return libShowSelectedOnly
    ? [...LIB_SELECTED].sort((a, b) => a - b)
    : LIB_FRAMES.map((_, i) => i);
}

function showLibFrame(pos) {
  const indices = libViewIndices();
  const i = indices[pos];
  const f = i != null ? LIB_FRAMES[i] : undefined;
  [...libFrameRow.children].forEach((d, j) => d.classList.toggle('cur', j === i));
  if (!f) { libViewerImg.removeAttribute('src'); libNEl.textContent = '—'; return; }
  libViewerImg.src = f.url;
  libNEl.textContent = pos + 1;
  const cur = libFrameRow.children[i];
  if (cur) cur.scrollIntoView({block: 'nearest', inline: 'center'});
}

// Applies libShowSelectedOnly to what's actually on screen: hides every
// thumbnail not in the current view, resizes the slider to match, and
// relabels gmLibViewToggle to say what clicking it will do NEXT (the
// label names the action, not the current mode).
function applyLibViewMode() {
  const indices = libViewIndices();
  const indexSet = new Set(indices);
  [...libFrameRow.children].forEach((d, j) => {
    d.classList.toggle('hiddenByView', libShowSelectedOnly && !indexSet.has(j));
  });
  libSlider.max = Math.max(0, indices.length - 1);
  libSlider.disabled = indices.length === 0;
  libTotalEl.textContent = indices.length || '—';
  libSlider.value = 0;
  showLibFrame(0);
  gmLibViewToggle.textContent = libShowSelectedOnly ? 'Show the Collection' : 'Show Selected on Timeline';
}

// Rebuilds the flattened frame list from PICKED, in checked order —
// called after every check/uncheck, and on Clear / a scene switch.
function rebuildLibFrames() {
  LIB_FRAMES = [];
  // Whatever was selected pointed at indices in the OLD list — meaningless
  // the moment the list is rebuilt, so this starts clean rather than
  // carrying a selection over onto whatever now happens to sit at the
  // same index.
  LIB_SELECTED = new Set();
  libSelectedNEl.textContent = 0;
  libRangeStart = null;
  libPhase = 0;
  libShowSelectedOnly = false;
  // Full reset of the whole selection mechanism, not just its data — a
  // Clear All that leaves Select Frames still armed (red) is only half
  // cleared.
  libArmed = false;
  gmSelectFrames.classList.remove('armed');
  gmCopySelected.classList.remove('ready');
  gmLibViewToggle.classList.remove('ready');
  for (const clip of PICKED)
    for (let i = 0; i < clip.n; i++) LIB_FRAMES.push({url: libFrameUrl(clip, i), clip, local: i});
  renderLibFrameRow();
  applyLibViewMode();
}

libSlider.oninput = () => showLibFrame(+libSlider.value);

// Frame Selector picks are tied to one scene — restored once that scene's
// own pair is open, keyed the same way a save for it is: base_rel +
// over_rel, so re-opening the SAME scene later in the same session (not
// just after a refresh) brings its own picks back.
//
// Called only from an explicit check/uncheck (toggleLibClip) — never from
// rebuildLibFrames() itself, which also runs during the RESET at the
// start of loading a pair (PICKED = [] before restorePairProgress() gets
// a chance to read what was saved), and saving there would overwrite the
// very data a refresh is about to restore before restore can read it.
function savePickedForCurrentPair() {
  if (!SCENE) return;
  savePair(pairKey(SCENE.base_rel, SCENE.over_rel), {picked: PICKED});
}

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

// Which BUILDER_FRAMES indices are selected FOR AN ACTION (Delete,
// Duplicate, Copy Selected, ...) — separate from which one is merely being
// VIEWED (that's `showBuilderFrame`'s own job, the blue .cur highlight).
let SELECTED = new Set();
// Whether gmBuilderSelectFrames is armed — the SAME 3-click start/end/
// reset cycle gmSelectFrames runs on the Frame Selector row (libArmed/
// libPhase), just scoped to this row instead (see renderBuilderFrameRow's
// onclick). Toggled by the button itself; turning it off mid-cycle only
// stops arming FURTHER clicks — it does not clear a selection already
// sitting there.
let builderArmed = false;
// 0: next click is click 1 (starts a selection). 1: next click is click 2
// (finishes it — same frame as click 1 collapses it to one frame). 2: a
// selection sits complete; the next click is click 3, a reset back to 0.
let builderPhase = 0;
// The pending start of a click-1/click-2 range pick — null except between
// those two clicks (builderPhase === 1).
let builderRangeStart = null;

// A full reset of the Builder's own select/copy mechanism — called at hard
// reset points (a scene switch/Clear in app.js's showEmpty(), and
// gmClearAll below), never from inside the 3-click cycle itself (which
// only ever clears what its OWN click needs cleared).
function disarmSelectMode() {
  builderArmed = false;
  builderPhase = 0;
  builderRangeStart = null;
  gmBuilderSelectFrames.classList.remove('armed');
  gmBuilderCopySelected.classList.remove('ready');
}

function setSelected(indices) {
  SELECTED = new Set(indices);
  [...builderFrameRow.children].forEach((d, j) => d.classList.toggle('selected', SELECTED.has(j)));
}

function renderBuilderFrameRow() {
  builderFrameRow.innerHTML = '';
  BUILDER_FRAMES.forEach((f, i) => {
    const d = document.createElement('div');
    d.className = 'libframe' + (SELECTED.has(i) ? ' selected' : '');
    d.style.backgroundImage = `url(${f.url})`;
    d.title = `${f.clip.name} — frame ${f.local + 1}/${f.clip.n}`;
    d.onclick = () => {
      // Same 3-click cycle as the Frame Selector's own row (see
      // copySelectDblClick's old comment, now libPhase's) — click 1: start.
      // Click 2: end (or the same frame again for a one-frame selection).
      // Click 3: reset, and this click picks nothing on its own.
      if (builderArmed) {
        if (builderPhase === 0) {
          builderRangeStart = i;
          setSelected([i]);
          builderPhase = 1;
        } else if (builderPhase === 1) {
          if (i === builderRangeStart) {
            setSelected([i]);
          } else {
            const lo = Math.min(builderRangeStart, i), hi = Math.max(builderRangeStart, i);
            const range = [];
            for (let k = lo; k <= hi; k++) range.push(k);
            setSelected(range);
          }
          builderRangeStart = null;
          builderPhase = 2;
          gmBuilderCopySelected.classList.add('ready');
        } else {
          setSelected([]);
          builderRangeStart = null;
          builderPhase = 0;
          gmBuilderCopySelected.classList.remove('ready');
        }
      }
      gapLog('builder_frame_click', {i, builderArmed, after: gapSnapshot()});
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
  const f = BUILDER_FRAMES[i];
  [...builderFrameRow.children].forEach((d, j) => d.classList.toggle('cur', j === i));
  if (!f) { builderViewerImg.removeAttribute('src'); builderNEl.textContent = '—'; return; }
  builderViewerImg.src = f.url;
  builderNEl.textContent = i + 1;
  const cur = builderFrameRow.children[i];
  if (cur) cur.scrollIntoView({block: 'nearest', inline: 'center'});
}

// Deliberately does NOT save to storage — it also runs during the RESET
// at the start of showEmpty() (BUILDER_FRAMES = [] before restoreGlobals()
// gets a chance to read what was saved), and saving there would overwrite
// the very collection a refresh is about to bring back before it can.
// Only the actual mutation sites (doPaste, and the Gap Builder Controller
// Menu actions) save.
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

// Runs the actual paste: Carson picks where with a PLAIN click on a frame
// in the row below first (same click that always moves the viewer there —
// no separate arming step), then clicks Paste Selected, which just reads
// wherever that left builderSlider sitting. An empty Builder has no frame
// to have clicked, so it always inserts at the very start (0) instead.
function doPaste(insertAt) {
  const builderLenBefore = BUILDER_FRAMES.length;
  BUILDER_FRAMES.splice(insertAt, 0, ...CLIPBOARD);
  const landOn = insertAt + CLIPBOARD.length - 1;
  const n = CLIPBOARD.length;
  gapLog('do_paste', {insertAt, n, builderLenBefore, builderLenAfter: BUILDER_FRAMES.length});
  CLIPBOARD = [];
  gmPasteSelected.classList.remove('ready');
  // The whole select → copy → paste cycle is done — every button that was
  // part of it goes back to plain white, both Select Frames buttons
  // included (the clipboard could have come from either row), exactly
  // like finishing a copy already resets its own Copy Selected's green.
  libArmed = false;
  gmSelectFrames.classList.remove('armed');
  builderArmed = false;
  gmBuilderSelectFrames.classList.remove('armed');
  rebuildBuilderFrames(landOn);
  saveStore({builderFrames: BUILDER_FRAMES});
  libStatus.textContent = insertAt > 0
    ? `Pasted ${n} frame(s) after frame ${insertAt}.`
    : `Pasted ${n} frame(s).`;
}

async function toggleLibClip(f, checked) {
  if (!checked) {
    PICKED = PICKED.filter(c => c.path !== f.path);
    rebuildLibFrames();
    savePickedForCurrentPair();
    return;
  }
  try {
    const r = await fetch(`/api/lib_frames?path=${encodeURIComponent(f.path)}`);
    const d = await r.json();
    if (d.error) { libStatus.textContent = `${f.name}: ${d.error}`; return; }
    PICKED.push({path: f.path, name: f.name, n: d.n, slug: d.slug, ext: d.ext});
    rebuildLibFrames();
    savePickedForCurrentPair();
  } catch (e) {
    libStatus.textContent = `${f.name}: ${e.message}`;
  }
}

async function loadLibs() {
  PICKED = [];
  rebuildLibFrames();
  // A fresh pair may be a different STORE, so both are re-resolved below,
  // never carried over from whatever pair was open before.
  restPosePath = null;
  restPoseFrame = null;
  try {
    const r = await fetch(`/api/libs_list?${pairQS()}`);
    const d = await r.json();
    if (d.error) { libStatus.textContent = d.error; return; }
    if (!d.root) { libStatus.textContent = 'No sarah_clips/libs/ folder for this store yet.'; return; }
    const total = d.groups.reduce((s, g) => s + g.files.length, 0);
    libStatus.textContent = `${d.root} — ${total} file(s)`;
    libGroups.innerHTML = '';
    // The one file every store's library carries under this exact name —
    // see Sarah/README.md's "rest pose" section. Found here, once per
    // pair, rather than re-searched on every Controller Menu click.
    for (const g of d.groups)
      for (const f of g.files)
        if (f.name === REST_POSE_NAME) restPosePath = f.path;
    // What was checked for THIS pair last time — a refresh, or coming
    // back to a scene already visited this session, both restore it.
    const rec = SCENE && loadStore().pairs?.[pairKey(SCENE.base_rel, SCENE.over_rel)];
    const savedPaths = new Set((rec?.picked || []).map(c => c.path));
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
          playBtn.onclick = () => playSoundBit(f, name.textContent);
          row.appendChild(playBtn);
        }
        box.appendChild(row);
        if (savedPaths.has(f.path)) {
          cb.checked = true;
          toggleLibClip(f, true);
        }
      }
      libGroups.appendChild(box);
    }
  } catch (e) {
    libStatus.textContent = `Couldn't load: ${e.message}`;
  }
}

// ── Gap Builder Controller Menu ──────────────────────────────────────────
// All ten of the original placeholder buttons are gone or folded in now.
// Select One Frame / Select Multiple Frames combined into
// gmBuilderSelectFrames + gmBuilderCopySelected — the SAME 3-click cycle
// and Copy Selected pairing gmSelectFrames/gmCopySelected already use on
// the Frame Selector's row, just aimed at this one instead. Paste One
// Frame dropped since Paste Selected already covers a single frame (Copy
// Selected with just one frame picked). Duplicate One Frame / Duplicate
// Selected dropped too, for the same reason as Paste One: select a range
// here, Copy Selected, Paste Selected — that pastes a COPY back into this
// same row, which already IS "duplicate a range in place." Delete a Frame
// dropped for the identical reason: select just one frame with the same
// 3-click cycle (click the same frame twice), then Delete Selected — one
// selection mechanism serves every count instead of a redundant pair.
//
// What's left: gmAddOpeningStill, gmAddClosingStill, gmBuilderSelectFrames
// + gmBuilderCopySelected, gmPasteSelected, gmDeleteSelected, gmClearAll —
// all wired — plus, below a divider + "Frame Selector" title,
// gmSelectFrames + gmCopySelected for that OTHER row.
const gmAddOpeningStill = document.getElementById('gmAddOpeningStill');
const gmAddClosingStill = document.getElementById('gmAddClosingStill');
const gmBuilderSelectFrames = document.getElementById('gmBuilderSelectFrames');
const gmBuilderCopySelected = document.getElementById('gmBuilderCopySelected');
const gmDeleteSelected = document.getElementById('gmDeleteSelected');
const gmClearAll = document.getElementById('gmClearAll');
const gmSelectFrames = document.getElementById('gmSelectFrames');
const gmCopySelected = document.getElementById('gmCopySelected');
const gmLibViewToggle = document.getElementById('gmLibViewToggle');
const gmFrameSelectorClearAll = document.getElementById('gmFrameSelectorClearAll');
const gmPasteSelected = document.getElementById('gmPasteSelected');

// Whether gmSelectFrames is armed — while true, a plain click on a Frame
// Selector thumbnail (renderLibFrameRow's onclick, above) drives the
// 3-click start/end/reset cycle instead of only navigating. Toggled by
// the button itself; turning it off mid-cycle only stops arming FURTHER
// clicks — it does not clear a selection already sitting there ready for
// Copy Selected (that only happens on click 3, or on an actual copy).
let libArmed = false;

// What Copy Selected fills and Paste (not wired yet) will read from —
// plain frame objects, the same shape LIB_FRAMES and BUILDER_FRAMES both
// already use, copied by VALUE so later edits to the Frame Selector's own
// list can never reach back and change what's on the clipboard. Not saved
// to storage: a clipboard is working state for the rest of this session,
// not something a refresh should be expected to bring back.
let CLIPBOARD = [];

// The standardized "rest pose" — Sarah, settled, not speaking. Every
// store's sarah_clips/libs/stills/ carries it under this exact name (see
// Sarah/README.md). restPosePath is found once per pair inside loadLibs()
// above; restPoseFrame is the actual {url, clip, local} for it, fetched
// lazily on first use and kept — it never changes mid-pair, so there is
// no reason to ask the server for it twice.
const REST_POSE_NAME = 'sarah-rest-pose-corner-300-alpha.png';
let restPosePath = null;
let restPoseFrame = null;

async function getRestPoseFrame() {
  if (restPoseFrame) return restPoseFrame;
  if (!restPosePath) return null;
  const r = await fetch(`/api/lib_frames?path=${encodeURIComponent(restPosePath)}`);
  const d = await r.json();
  if (d.error) return null;
  const clip = {path: restPosePath, name: REST_POSE_NAME, n: d.n, slug: d.slug, ext: d.ext};
  restPoseFrame = {url: libFrameUrl(clip, 0), clip, local: 0};
  return restPoseFrame;
}

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`could not load ${src}`));
    img.src = src;
  });
}

// Same easing morph_avatar_corner.py's own lerp uses, and the same spacing
// sarah_transitions.py's _fixed_fade() uses (n frames strictly BETWEEN a
// and b, never including either endpoint) — so a transition built here in
// the browser reads as the same motion as one built there in Python.
//
// The blend itself is simpler than build/fade_frames.py's premultiplied
// version: plain canvas globalAlpha compositing, A first then B on top at
// rising opacity. Good enough for a same-kind corner-to-corner fade, where
// there is no fully-transparent-to-opaque edge for the simpler math to get
// wrong — see fade_frames.py's own docstring for where premultiplied
// blending actually matters.
const smoothstep = u => 3 * u * u - 2 * u * u * u;

async function fadeFrames(urlA, urlB, n) {
  const [a, b] = await Promise.all([loadImage(urlA), loadImage(urlB)]);
  const w = a.naturalWidth, h = a.naturalHeight;
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  const cctx = c.getContext('2d');
  const out = [];
  for (let i = 0; i < n; i++) {
    const t = smoothstep((i + 1) / (n + 1));
    cctx.clearRect(0, 0, w, h);
    cctx.globalAlpha = 1;
    cctx.drawImage(a, 0, 0, w, h);
    cctx.globalAlpha = t;
    cctx.drawImage(b, 0, 0, w, h);
    out.push(c.toDataURL('image/png'));
  }
  return out;
}

// A snapshot of every bit of Gap Builder state a click can change — logged
// before and after, so a log line shows not just WHAT was clicked but what
// it actually did. Cheap enough to call on every click; nothing here is
// more than reading a variable or a Set's size.
function gapSnapshot() {
  return {
    libArmed, libPhase, libSelected: LIB_SELECTED.size, libRangeStart,
    builderArmed, builderPhase, builderRangeStart, selected: SELECTED.size,
    clipboard: CLIPBOARD.length, builderCur: +builderSlider.value,
    builderFrames: BUILDER_FRAMES.length, libFrames: LIB_FRAMES.length,
  };
}

// Sends one line to the server's own logs/gap_builder_<date>.log (see
// client_log() in serve.py) — added specifically because Carson tests
// this through his own real browser tab, which this process can never see
// into on its own. Fire-and-forget: a log that could break a click is
// worse than no log, so failures are swallowed, never awaited, never
// thrown into the caller.
function gapLog(event, extra) {
  try {
    fetch('/api/gap_log', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({event, ...extra}),
      keepalive: true,
    }).catch(() => {});
  } catch (e) { /* never let logging break a click */ }
}

// Green flash while a Gap Menu button's click is actually being handled —
// see .gapMenuBtn.active in app.css. Held for a minimum visible time even
// when the handler finishes instantly (most of these do), so the flash is
// something you can actually see, not a colour set and unset within the
// same frame. For an async handler (the two Still buttons, which fetch
// and blend), the green naturally lasts the whole real wait instead.
//
// Also the one place that logs every Controller Menu button click (see
// gapLog above) — wrapping every button here means every one of them gets
// logged for free, with the state before the click and the state after,
// rather than repeating a log call in each handler.
function withActiveFlash(btn, handler) {
  return async (...args) => {
    const before = gapSnapshot();
    btn.classList.add('active');
    const start = performance.now();
    try {
      await handler(...args);
    } finally {
      const remaining = 150 - (performance.now() - start);
      if (remaining > 0) await new Promise(r => setTimeout(r, remaining));
      btn.classList.remove('active');
      gapLog('button_click', {id: btn.id, before, after: gapSnapshot()});
    }
  };
}

// Opening: 4 IDENTICAL frames of the rest pose, no transition into them —
// Carson's own call. Scene 1 has nothing before it to jump from, and every
// other scene should already be closing out on this exact pose (see the
// Closing button below), so there is nothing to move FROM either way.
gmAddOpeningStill.onclick = withActiveFlash(gmAddOpeningStill, async () => {
  const rp = await getRestPoseFrame();
  if (!rp) {
    libStatus.textContent = `Couldn't find ${REST_POSE_NAME} in this store's sarah_clips/libs/stills/.`;
    return;
  }
  for (let i = 0; i < 4; i++) BUILDER_FRAMES.push(rp);
  rebuildBuilderFrames(BUILDER_FRAMES.length - 1);
  saveStore({builderFrames: BUILDER_FRAMES});
});

// Closing: 3 frames fading from whatever the Builder currently ends on
// into the rest pose, then 4 held frames of the pose itself — 7 frames
// total. If the Builder is empty there is nothing to fade FROM, so this
// falls back to landing on the pose directly, the same as Opening.
gmAddClosingStill.onclick = withActiveFlash(gmAddClosingStill, async () => {
  const rp = await getRestPoseFrame();
  if (!rp) {
    libStatus.textContent = `Couldn't find ${REST_POSE_NAME} in this store's sarah_clips/libs/stills/.`;
    return;
  }
  if (BUILDER_FRAMES.length) {
    const last = BUILDER_FRAMES[BUILDER_FRAMES.length - 1];
    const blended = await fadeFrames(last.url, rp.url, 3);
    const clip = {name: 'closing transition to rest pose', n: 3};
    blended.forEach((url, i) => BUILDER_FRAMES.push({url, clip, local: i}));
  }
  for (let i = 0; i < 4; i++) BUILDER_FRAMES.push(rp);
  rebuildBuilderFrames(BUILDER_FRAMES.length - 1);
  saveStore({builderFrames: BUILDER_FRAMES});
});

// Arms/disarms the 3-click start/end/reset cycle on the Clip-Gap Builder
// row below — same mechanism gmSelectFrames uses on the Frame Selector
// row (see renderBuilderFrameRow's onclick and builderPhase). Click again
// to disarm early — that only stops arming further clicks, it does not
// clear a selection already sitting there.
gmBuilderSelectFrames.onclick = withActiveFlash(gmBuilderSelectFrames, () => {
  builderArmed = !builderArmed;
  gmBuilderSelectFrames.classList.toggle('armed', builderArmed);
});

// Copies whatever's selected in the Clip-Gap Builder's own row (SELECTED,
// filled by the gmBuilderSelectFrames cycle) onto CLIPBOARD — the SAME
// clipboard Copy Selected/Paste Selected (Frame Selector side) already
// use, so this doubles as "duplicate a range in place": select it here,
// Copy Selected, then Paste Selected picks where the copy lands.
gmBuilderCopySelected.onclick = withActiveFlash(gmBuilderCopySelected, () => {
  if (!SELECTED.size) {
    libStatus.textContent = 'Select Frames, then click a frame below to start a selection '
      + '(click again to finish it) — then Copy Selected.';
    return;
  }
  const indices = [...SELECTED].sort((a, b) => a - b);
  CLIPBOARD = indices.map(i => BUILDER_FRAMES[i]);
  libStatus.textContent = `Copied ${CLIPBOARD.length} frame(s) — Paste Selected is ready.`;
  gmBuilderCopySelected.classList.remove('ready');
  gmPasteSelected.classList.add('ready');
  setSelected([]);
  builderRangeStart = null;
  builderPhase = 0;
});

// Removes EVERY selected frame — whatever the gmBuilderSelectFrames cycle
// currently left in SELECTED, one frame (click the same frame twice) or a
// whole range. One selection mechanism serves both counts, so there is no
// separate Delete a Frame any more. Indices are removed HIGHEST first, so
// splicing one out never shifts the position of another one still waiting
// to go — removing low-to-high would delete the wrong frame the moment
// the first splice moved everything after it down.
gmDeleteSelected.onclick = withActiveFlash(gmDeleteSelected, () => {
  if (!SELECTED.size) {
    libStatus.textContent = 'Select Frames, then click one or more frames below, first.';
    return;
  }
  const indices = [...SELECTED].sort((a, b) => b - a);
  const landOn = Math.min(...SELECTED);
  for (const i of indices) BUILDER_FRAMES.splice(i, 1);
  SELECTED = new Set();
  rebuildBuilderFrames(Math.min(landOn, BUILDER_FRAMES.length - 1));
  saveStore({builderFrames: BUILDER_FRAMES});
});

// Empties the WHOLE collection, selected or not — no confirmation, same as
// every other action here. Only this list: the Frame Selector's own picks,
// the loaded scene, and Timeline Scenes are all untouched (that is what
// the main Clear button, in Timeline Scenes, is for).
gmClearAll.onclick = withActiveFlash(gmClearAll, () => {
  BUILDER_FRAMES = [];
  SELECTED = new Set();
  disarmSelectMode();
  rebuildBuilderFrames();
  saveStore({builderFrames: BUILDER_FRAMES});
});

// Arms/disarms the 3-click start/end/reset cycle on the Frame Selector row
// above (see renderLibFrameRow's onclick and libPhase). Click again to
// disarm early — that only stops arming further clicks, it does not clear
// a selection already sitting there.
gmSelectFrames.onclick = withActiveFlash(gmSelectFrames, () => {
  libArmed = !libArmed;
  gmSelectFrames.classList.toggle('armed', libArmed);
});

// Copies whatever's selected in the Frame Selector's own row (LIB_SELECTED,
// filled by the gmSelectFrames 3-click cycle) onto CLIPBOARD, in frame
// order — not necessarily the order the two clicks happened in, since
// either end can be clicked first. Turns its own 'ready' green back off
// and resets the cycle to click 1, so the very next click on a frame
// starts a fresh pick rather than landing on click 3 by surprise.
function copySelectedLibFrames() {
  if (!LIB_SELECTED.size) {
    libStatus.textContent = 'Select Frames, then click a frame above to start a selection '
      + '(click again to finish it) — then Copy Selected.';
    return;
  }
  const indices = [...LIB_SELECTED].sort((a, b) => a - b);
  CLIPBOARD = indices.map(i => LIB_FRAMES[i]);
  libStatus.textContent = `Copied ${CLIPBOARD.length} frame(s) — Paste Selected is ready.`;
  gmCopySelected.classList.remove('ready');
  gmLibViewToggle.classList.remove('ready');
  // The clipboard now has something in it — Paste Selected is the next
  // step, same "ready" green Copy Selected itself just had.
  gmPasteSelected.classList.add('ready');
  setLibSelected([]);
  libRangeStart = null;
  libPhase = 0;
  // Copied — the review is over either way, so land back on the full
  // collection rather than leaving the view filtered to a selection that
  // no longer exists.
  if (libShowSelectedOnly) { libShowSelectedOnly = false; applyLibViewMode(); }
}

gmCopySelected.onclick = withActiveFlash(gmCopySelected, copySelectedLibFrames);

// Switches the row/slider above between the full collection and just
// LIB_SELECTED, so a selection can be scrubbed through before deciding —
// Copy Selected if it looks right, or click this again to back out.
// Backing out UN-STAGES the pick (same as click 3 of the select cycle):
// this is a review step, not a second way to hold a selection.
gmLibViewToggle.onclick = withActiveFlash(gmLibViewToggle, () => {
  if (!libShowSelectedOnly) {
    if (!LIB_SELECTED.size) {
      libStatus.textContent = 'Select Frames, then click a frame above to start a selection '
        + '(click again to finish it) — then Show Selected on Timeline.';
      return;
    }
    libShowSelectedOnly = true;
  } else {
    libShowSelectedOnly = false;
    setLibSelected([]);
    libRangeStart = null;
    libPhase = 0;
    gmCopySelected.classList.remove('ready');
    gmLibViewToggle.classList.remove('ready');
  }
  applyLibViewMode();
});

// Empties the Frame Selector's OWN collection — unchecks every clip in
// sarah_clips/libs and clears PICKED, same idea as gmClearAll above but
// for this row instead. Does not touch the Clip-Gap Builder, CLIPBOARD,
// the loaded scene, or Timeline Scenes.
gmFrameSelectorClearAll.onclick = withActiveFlash(gmFrameSelectorClearAll, () => {
  PICKED = [];
  [...libGroups.querySelectorAll('input[type=checkbox]')].forEach(cb => { cb.checked = false; });
  rebuildLibFrames();
  savePickedForCurrentPair();
});

// Pastes right away — no arming step. The destination is wherever a plain
// click already left the Builder row sitting (builderSlider.value, set by
// renderBuilderFrameRow's onclick on every click, armed or not): click a
// frame there first, THEN click this. An empty Builder has no frame to
// have clicked, so it always inserts at the very start instead.
gmPasteSelected.onclick = withActiveFlash(gmPasteSelected, () => {
  if (!CLIPBOARD.length) {
    libStatus.textContent = 'Nothing on the clipboard — Select Frames above, then Copy Selected, first.';
    return;
  }
  doPaste(BUILDER_FRAMES.length ? +builderSlider.value + 1 : 0);
});
