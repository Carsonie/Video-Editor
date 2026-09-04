// Avatar Editor — sarah_clips/libs, the Frame Selector, and the Clip-Gap
// Builder. Split out of app.js on 2026-09-01, specifically because this is
// the one area about to grow a lot (the ten Gap Builder Menu actions all
// act on BUILDER.frames, defined here) — everything else on the
// page (the combine engine, Timeline Scenes, the Load popup, persistence)
// was staying roughly the size it already was.
//
// Neither this file nor app.js is wrapped in an IIFE — both need one flat
// top-level scope, not two separate private ones, so each can call
// straight into the other's declarations by name (this file's LIB and
// BUILDER state objects, rebuildLibFrames, rebuildBuilderFrames,
// toggleLibClip, loadLibs, savePickedForCurrentPair; app.js's SCENE,
// pairQS(), pad(), and the localStorage helpers loadStore/saveStore/
// savePair/pairKey). Loaded BEFORE app.js in index.html, because app.js's
// own bootstrap, at its very bottom, calls straight into loadLibs() and
// the two rebuild functions — they have to already exist by then.
//
// frame-player.js is the exception to that flat scope, and loads BEFORE
// both: it owns everything about the three Play buttons, keeps its own
// private scope, and is reached only through `FramePlayer`. This file
// hands it its data sources at the very bottom.
'use strict';

// ── sarah_clips/libs ─────────────────────────────────────────────────────
// The list itself is read-only, refreshed whenever a pair is opened. Each
// file also gets a checkbox: checking one pulls its frames (a still is
// one frame; a clip is every frame) into the inspector below. That
// inspector is a SEPARATE viewer, slider and frame strip from the
// scene's own — Carson's call, so browsing a library clip never disturbs
// where you are in the scene's own combined-frame review.
// ── the two rows' state, gathered ───────────────────────────────────────────
//
// These were 21 separate top-level `let`s until 2026-09-04, mutated from 25
// functions and a good many inline handlers, and that — not the line count —
// was what made this file impossible to split: every part of it reached into
// the same loose scope, so moving any part moved the state with it.
//
// They are grouped here by CONCERN, and each object is `const`: the binding
// never changes, only what is inside it. That is what lets another file hold
// a reference (working-clips.js keeps one) without it going stale — which a
// reassigned `let` did not.
//
// Two rows, plus the one thing genuinely shared between them.

const LIB = {
  picked:           [],   // checked clips' metadata, in the order checked
  frames:           [],   // every picked clip's frames, flattened into one list

  // Every file in sarah_clips/libs, by path, in the order the list DISPLAYS
  // them — top to bottom, group by group. LIB.picked is in the order boxes were
  // TICKED, which is not the same thing: OriginalAudio plays its stack in
  // the order they appear on screen, so it needs this to sort by.
  order:            [],

  // Whichever clip the Frame Selector viewer is showing RIGHT NOW — what
  // Copy/Paste act on. The Frame Selector's Play button does NOT read this:
  // it plays the whole collection, not the frame under the playhead.
  curClip:          null,
  restPosePath:     null,
  restPoseSource:   null,
  restPoseFrame:    null,

  // Which LIB.frames indices are selected for Copy Selected — the Frame
  // Selector's own equivalent of the Clip-Gap Builder's BUILDER.selected. Armed by
  // its own button, gmSelectFrames, below — while armed, a plain single
  // click on a frame here does the selecting instead of only navigating,
  // following a 3-click cycle (see gmSelectFrames.onclick and LIB.phase).
  selected:         new Set(),

  // The pending start of a click-1/click-2 range pick — null except between
  // those two clicks (LIB.phase === 1).
  rangeStart:       null,

  // 0: next click is click 1 (starts a selection). 1: next click is click 2
  // (finishes it — same frame as click 1 collapses it to one frame). 2: a
  // selection sits complete; the next click is click 3, a reset back to 0
  // that clears it rather than picking anything.
  phase:            0,

  // Whether gmSelectFrames is armed — while true, a plain click on a Frame
  // Selector thumbnail (renderLibFrameRow's onclick, above) drives the
  // 3-click start/end/reset cycle instead of only navigating. Toggled by
  // the button itself; turning it off mid-cycle only stops arming FURTHER
  // clicks — it does not clear a selection already sitting there ready for
  // Copy Selected (that only happens on click 3, or on an actual copy).
  armed:            false,

  // Whether the row and slider above are filtered down to JUST LIB.selected
  // (gmLibViewToggle, below) — a review mode, not a second selection
  // mechanism. Toggling it OFF (back to the full collection) un-stages
  // whatever was selected, same as click 3 does, since backing out of the
  // review means starting over rather than leaving a stale pick armed.
  showSelectedOnly: false,

  // Set while the Frame Selector's own stepper is driving the viewer. The
  // buttons cannot change from one frame to the next, and Players.refresh()
  // rescans the whole collection, so doing it 25 times a second was pure
  // waste. The stepper redraws once when it starts and once when it stops.
  stepping:         false,
};

const BUILDER = {
  // A second, separate strip below the Frame Selector. The Selector browses
  // whatever's checked; clicking its Frame N/Total button COPIES that one
  // frame down here, in the order copied. This is how a gap-filler gets
  // hand-assembled: pick a frame, look at it, pick the next, and scrub back
  // and forth down here to see the run of idle motion it adds up to.
  //
  // Deliberately NOT reset when a clip is un/re-checked above, or when the
  // Load picker switches to a different scene — a collection built by hand
  // is real work, and only Clear (which empties everything) should lose it.
  frames:     [],

  // Whichever clip the Clip-Gap Builder viewer is showing RIGHT NOW. Handed
  // to frame-player.js as `builderClip` (see the configure() call at the
  // bottom of this file) — its Play button plays what is on screen here.
  curClip:    null,

  // Set while the Clip-Gap Builder's own stepper is driving its viewer —
  // same reasoning as LIB.stepping above: the buttons cannot change from one
  // animation frame to the next, and Players.refresh() rescans both
  // collections.
  stepping:   false,

  // Which BUILDER.frames indices are selected FOR AN ACTION (Delete,
  // Duplicate, Copy Selected, ...) — separate from which one is merely being
  // VIEWED (that's `showBuilderFrame`'s own job, the blue .cur highlight).
  selected:   new Set(),

  // The pending start of a click-1/click-2 range pick — null except between
  // those two clicks (BUILDER.phase === 1).
  rangeStart: null,

  // 0: next click is click 1 (starts a selection). 1: next click is click 2
  // (finishes it — same frame as click 1 collapses it to one frame). 2: a
  // selection sits complete; the next click is click 3, a reset back to 0.
  phase:      0,

  // Whether gmBuilderSelectFrames is armed — the SAME 3-click start/end/
  // reset cycle gmSelectFrames runs on the Frame Selector row (LIB.armed/
  // LIB.phase), just scoped to this row instead (see renderBuilderFrameRow's
  // onclick). Toggled by the button itself; turning it off mid-cycle only
  // stops arming FURTHER clicks — it does not clear a selection already
  // sitting there.
  armed:      false,
};

const SHARED = {
  // What Copy Selected fills and Paste (not wired yet) will read from —
  // plain frame objects, the same shape LIB.frames and BUILDER.frames both
  // already use, copied by VALUE so later edits to the Frame Selector's own
  // list can never reach back and change what's on the clipboard. Not saved
  // to storage: a clipboard is working state for the rest of this session,
  // not something a refresh should be expected to bring back.
  clipboard: [],
};

const libStatus = document.getElementById('libStatus');
const libGroups = document.getElementById('libGroups');
const libSpinner = document.getElementById('libSpinner');
const libHeaderStore = document.getElementById('libHeaderStore');
const libHeaderVideo = document.getElementById('libHeaderVideo');

// Pulls the store and video name out of a scene's own base_rel — the same
// <Business>/<store>/help-videos/videos/<video>/sandbox/<scene>/segment.mp4
// shape video_root_of() in serve.py already relies on. Returns null rather
// than guessing when the shape doesn't match, same rule that function
// follows: a silently wrong label here would read as confidence about
// which store's panel this is when there wasn't any.
function storeVideoFromPath(rel) {
  const parts = (rel || '').split('/');
  const sbx = parts.indexOf('sandbox');
  if (parts.length < 2 || sbx < 1) return null;
  return {store: parts[1], video: parts[sbx - 1]};
}
// The second, duplicated panel — Sarah's COMMON library (Sarah/ at the
// repo root), beside this one. Same rendering function, a different
// source and a different pair of DOM elements — see renderLibSource().
const libStatusCommon = document.getElementById('libStatusCommon');
const libGroupsCommon = document.getElementById('libGroupsCommon');
const libSpinnerCommon = document.getElementById('libSpinnerCommon');
const humanSize = b => b < 1024 ? `${b}B` : b < 1048576 ? `${(b / 1024).toFixed(0)}KB` : `${(b / 1048576).toFixed(1)}MB`;

// ── the player ───────────────────────────────────────────────────────────
// All three Play buttons, the run queue, the audibility rule and the
// picture-follows-the-voice animation moved to frame-player.js on
// 2026-09-02 — see that file's own header for why. It is loaded BEFORE
// this one and keeps its own scope, so the only way in is FramePlayer's
// own small API. What is left here is what this file actually owns: the
// library, the two frame rows, and handing those over at the bottom of
// this file (see the Players.configure() call there). working-clips.js
// loads between the two and keeps its own scope, handing out WorkingClips.

const libInspector = document.getElementById('libInspector');
const libViewerImg = document.getElementById('libViewerImg');
const libSlider = document.getElementById('libSlider');
const libFrameRow = document.getElementById('libFrameRow');
const libNEl = document.getElementById('libN');
const libTotalEl = document.getElementById('libTotal');
const libSelectedNEl = document.getElementById('libSelectedN');

const libFrameUrl = (clip, local) => `/${clip.slug}/frames/frame_${pad(local + 1)}${clip.ext}`;

function setLibSelected(indices) {
  LIB.selected = new Set(indices);
  libSelectedNEl.textContent = LIB.selected.size;
  [...libFrameRow.children].forEach((d, j) => d.classList.toggle('selected', LIB.selected.has(j)));
  // Replace Selected needs BOTH a selection here and an active Working
  // Clip, so it has to be re-judged whenever either half moves.
  WorkingClips.refreshButtons();
}

function renderLibFrameRow() {
  libFrameRow.innerHTML = '';
  LIB.frames.forEach((f, i) => {
    const d = document.createElement('div');
    d.className = 'libframe' + (LIB.selected.has(i) ? ' selected' : '');
    d.style.backgroundImage = `url(${f.url})`;
    d.title = `${f.clip.name} — frame ${f.local + 1}/${f.clip.n}`;
    d.onclick = () => {
      if (LIB.armed) {
        if (LIB.phase === 0) {
          LIB.rangeStart = i;
          setLibSelected([i]);
          LIB.phase = 1;
        } else if (LIB.phase === 1) {
          if (i === LIB.rangeStart) {
            setLibSelected([i]);
          } else {
            const lo = Math.min(LIB.rangeStart, i), hi = Math.max(LIB.rangeStart, i);
            const range = [];
            for (let k = lo; k <= hi; k++) range.push(k);
            setLibSelected(range);
          }
          LIB.rangeStart = null;
          LIB.phase = 2;
          gmCopySelected.classList.add('ready');
          gmLibViewToggle.classList.add('ready');
        } else {
          // Click 3 — reset, and this click picks nothing on its own.
          setLibSelected([]);
          LIB.rangeStart = null;
          LIB.phase = 0;
          gmCopySelected.classList.remove('ready');
          gmLibViewToggle.classList.remove('ready');
        }
      }
      gapLog('lib_frame_click', {i, libArmed: LIB.armed, after: gapSnapshot()});
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

// The indices INTO LIB.frames that the slider/viewer currently scrub
// through — every frame normally, or just LIB.selected, sorted, while
// "Show Selected on Timeline" is on. showLibFrame's own argument is a
// POSITION into whichever of these is current, not a raw LIB.frames index.
function libViewIndices() {
  return LIB.showSelectedOnly
    ? [...LIB.selected].sort((a, b) => a - b)
    : LIB.frames.map((_, i) => i);
}

function showLibFrame(pos) {
  const indices = libViewIndices();
  const i = indices[pos];
  const f = i != null ? LIB.frames[i] : undefined;
  [...libFrameRow.children].forEach((d, j) => d.classList.toggle('cur', j === i));
  // LIB.curClip is still tracked — Copy/Paste care what is on screen. What
  // it no longer does is gate the Frame Selector's Play button: that plays
  // the whole collection now, not the one frame under the playhead.
  LIB.curClip = f ? f.clip : null;
  // Skipped while the stepper is running — see LIB.stepping above.
  if (!LIB.stepping) Players.refresh();
  if (!f) { libViewerImg.removeAttribute('src'); libNEl.textContent = '—'; return; }
  libViewerImg.src = f.url;
  libNEl.textContent = pos + 1;
  const cur = libFrameRow.children[i];
  if (cur) cur.scrollIntoView({block: 'nearest', inline: 'center'});
}

// Applies LIB.showSelectedOnly to what's actually on screen: hides every
// thumbnail not in the current view, resizes the slider to match, and
// relabels gmLibViewToggle to say what clicking it will do NEXT (the
// label names the action, not the current mode).
function applyLibViewMode() {
  const indices = libViewIndices();
  const indexSet = new Set(indices);
  [...libFrameRow.children].forEach((d, j) => {
    d.classList.toggle('hiddenByView', LIB.showSelectedOnly && !indexSet.has(j));
  });
  libSlider.max = Math.max(0, indices.length - 1);
  libSlider.disabled = indices.length === 0;
  libTotalEl.textContent = indices.length || '—';
  libSlider.value = 0;
  showLibFrame(0);
  gmLibViewToggle.textContent = LIB.showSelectedOnly ? 'Show the Collection' : 'Show Selected on Timeline';
  // "Show Selected on Timeline" narrows what the Frame Selector's own run
  // would play, so its button's count/green state is recomputed here too,
  // not only on a check/uncheck.
  Players.refresh();
}

// Rebuilds the flattened frame list from LIB.picked, in checked order —
// called after every check/uncheck, and on Clear / a scene switch.
function rebuildLibFrames() {
  LIB.frames = [];
  // A run over the OLD collection is meaningless now, and leaving it in
  // place was a real bug: check a clip, play it, pause, then change what
  // is checked, and the next press RESUMED the old paused run — the old
  // clip's voice against the new collection's pictures, which is exactly
  // what "it played the wrong clip" looked like. The collection changed,
  // so the run over it ends here; the next press starts fresh.
  // Only the Frame Selector's run: its frame row is rebuilt underneath it,
  // so every index that run held is meaningless. The Audio Menu's stack is
  // re-pointed instead, and keeps playing — see OriginalAudio.rebuild().
  FrameSelector.endRun();
  // Whatever was selected pointed at indices in the OLD list — meaningless
  // the moment the list is rebuilt, so this starts clean rather than
  // carrying a selection over onto whatever now happens to sit at the
  // same index.
  LIB.selected = new Set();
  libSelectedNEl.textContent = 0;
  LIB.rangeStart = null;
  LIB.phase = 0;
  LIB.showSelectedOnly = false;
  // Full reset of the whole selection mechanism, not just its data — a
  // Clear All that leaves Select Frames still armed (red) is only half
  // cleared.
  LIB.armed = false;
  gmSelectFrames.classList.remove('armed');
  gmCopySelected.classList.remove('ready');
  gmLibViewToggle.classList.remove('ready');
  for (const clip of LIB.picked)
    for (let i = 0; i < clip.n; i++) LIB.frames.push({url: libFrameUrl(clip, i), clip, local: i});
  renderLibFrameRow();
  applyLibViewMode();
  // Runs on every check/uncheck and on every reset, which is exactly when
  // "is there anything for these buttons to play" changes.
  Players.refresh();
  WorkingClips.refreshButtons();
}

libSlider.oninput = () => showLibFrame(+libSlider.value);

// Frame Selector picks are tied to one scene — restored once that scene's
// own pair is open, keyed the same way a save for it is: base_rel +
// over_rel, so re-opening the SAME scene later in the same session (not
// just after a refresh) brings its own picks back.
//
// Called only from an explicit check/uncheck (toggleLibClip) — never from
// rebuildLibFrames() itself, which also runs during the RESET at the
// start of loading a pair (LIB.picked = [] before restorePairProgress() gets
// a chance to read what was saved), and saving there would overwrite the
// very data a refresh is about to restore before restore can read it.
function savePickedForCurrentPair() {
  if (!SCENE) return;
  savePair(pairKey(SCENE.base_rel, SCENE.over_rel), {picked: LIB.picked});
}

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

// ── Gap Builder Menu ─────────────────────────────────────────────────────
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
const gmSaveTarget = document.getElementById('gmSaveTarget');
const gmSaveToWorking = document.getElementById('gmSaveToWorking');
const gmReplaceSelected = document.getElementById('gmReplaceSelected');
const gmAudioClearAll = document.getElementById('gmAudioClearAll');
// The three Play buttons. Their BEHAVIOUR lives in frame-player.js; what
// they are wired to here is only the route in — see the three onclicks at
// the bottom of this file.
const gmSoundBitPlayPause = document.getElementById('gmSoundBitPlayPause');
const gmLibPlayPause = document.getElementById('gmLibPlayPause');
const gmBuilderPlayPause = document.getElementById('gmBuilderPlayPause');

// The standardized "rest pose" — Sarah, settled, not speaking. Sarah/'s
// own stills/ is now the canonical source for it (Carson's own split,
// 2026-09-03; see Sarah/README.md), with a store's own sarah_clips/libs/
// stills/ copy as a fallback — see loadLibs() above, which checks common
// first. LIB.restPosePath+LIB.restPoseSource are found once per pair there;
// LIB.restPoseFrame is the actual {url, clip, local} for it, fetched lazily on
// first use and kept — it never changes mid-pair, so there is no reason to
// ask the server for it twice.
const REST_POSE_NAME = 'sarah-rest-pose-corner-300-alpha.png';

async function getRestPoseFrame() {
  if (LIB.restPoseFrame) return LIB.restPoseFrame;
  if (!LIB.restPosePath) return null;
  const r = await fetch(`/api/lib_frames?source=${LIB.restPoseSource}&path=${encodeURIComponent(LIB.restPosePath)}`);
  const d = await r.json();
  if (d.error) return null;
  const clip = {path: LIB.restPosePath, name: REST_POSE_NAME, n: d.n, slug: d.slug, ext: d.ext,
                source: LIB.restPoseSource};
  LIB.restPoseFrame = {url: libFrameUrl(clip, 0), clip, local: 0};
  return LIB.restPoseFrame;
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
    libArmed: LIB.armed, libPhase: LIB.phase, libSelected: LIB.selected.size, libRangeStart: LIB.rangeStart,
    builderArmed: BUILDER.armed, builderPhase: BUILDER.phase, builderRangeStart: BUILDER.rangeStart, selected: BUILDER.selected.size,
    clipboard: SHARED.clipboard.length, builderCur: +builderSlider.value,
    builderFrames: BUILDER.frames.length, libFrames: LIB.frames.length,
    // Working Clips: how many are saved in each section, and which one is
    // active. Both change what Save to Working Clips and Replace Selected
    // will DO, so a click log without them cannot explain either.
    wcIdle: WorkingClips.count('idle'),
    wcTransitions: WorkingClips.count('transitions'),
    wcSoundBits: WorkingClips.count('sound_bits'),
    wcActive: WorkingClips.active()?.name ?? null,
    wcActiveN: WorkingClips.active()?.n ?? 0,
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
  for (let i = 0; i < 4; i++) BUILDER.frames.push(rp);
  rebuildBuilderFrames(BUILDER.frames.length - 1);
  saveStore({builderFrames: BUILDER.frames});
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
  if (BUILDER.frames.length) {
    const last = BUILDER.frames[BUILDER.frames.length - 1];
    const blended = await fadeFrames(last.url, rp.url, 3);
    const clip = {name: 'closing transition to rest pose', n: 3};
    blended.forEach((url, i) => BUILDER.frames.push({url, clip, local: i}));
  }
  for (let i = 0; i < 4; i++) BUILDER.frames.push(rp);
  rebuildBuilderFrames(BUILDER.frames.length - 1);
  saveStore({builderFrames: BUILDER.frames});
});

// Arms/disarms the 3-click start/end/reset cycle on the Clip-Gap Builder
// row below — same mechanism gmSelectFrames uses on the Frame Selector
// row (see renderBuilderFrameRow's onclick and BUILDER.phase). Click again
// to disarm early — that only stops arming further clicks, it does not
// clear a selection already sitting there.
gmBuilderSelectFrames.onclick = withActiveFlash(gmBuilderSelectFrames, () => {
  BUILDER.armed = !BUILDER.armed;
  gmBuilderSelectFrames.classList.toggle('armed', BUILDER.armed);
});

// Copies whatever's selected in the Clip-Gap Builder's own row (BUILDER.selected,
// filled by the gmBuilderSelectFrames cycle) onto SHARED.clipboard — the SAME
// clipboard Copy Selected/Paste Selected (Frame Selector side) already
// use, so this doubles as "duplicate a range in place": select it here,
// Copy Selected, then Paste Selected picks where the copy lands.
gmBuilderCopySelected.onclick = withActiveFlash(gmBuilderCopySelected, () => {
  if (!BUILDER.selected.size) {
    libStatus.textContent = 'Select Frames, then click a frame below to start a selection '
      + '(click again to finish it) — then Copy Selected.';
    return;
  }
  const indices = [...BUILDER.selected].sort((a, b) => a - b);
  SHARED.clipboard = indices.map(i => BUILDER.frames[i]);
  libStatus.textContent = `Copied ${SHARED.clipboard.length} frame(s) — Paste Selected is ready.`;
  gmBuilderCopySelected.classList.remove('ready');
  gmPasteSelected.classList.add('ready');
  setSelected([]);
  BUILDER.rangeStart = null;
  BUILDER.phase = 0;
});

// Removes EVERY selected frame — whatever the gmBuilderSelectFrames cycle
// currently left in BUILDER.selected, one frame (click the same frame twice) or a
// whole range. One selection mechanism serves both counts, so there is no
// separate Delete a Frame any more. Indices are removed HIGHEST first, so
// splicing one out never shifts the position of another one still waiting
// to go — removing low-to-high would delete the wrong frame the moment
// the first splice moved everything after it down.
gmDeleteSelected.onclick = withActiveFlash(gmDeleteSelected, () => {
  if (!BUILDER.selected.size) {
    libStatus.textContent = 'Select Frames, then click one or more frames below, first.';
    return;
  }
  const indices = [...BUILDER.selected].sort((a, b) => b - a);
  const landOn = Math.min(...BUILDER.selected);
  for (const i of indices) BUILDER.frames.splice(i, 1);
  BUILDER.selected = new Set();
  rebuildBuilderFrames(Math.min(landOn, BUILDER.frames.length - 1));
  saveStore({builderFrames: BUILDER.frames});
});

// Empties the WHOLE collection, selected or not — no confirmation, same as
// every other action here. Only this list: the Frame Selector's own picks,
// the loaded scene, and Timeline Scenes are all untouched (that is what
// the main Clear button, in Timeline Scenes, is for).
gmClearAll.onclick = withActiveFlash(gmClearAll, () => {
  BUILDER.frames = [];
  BUILDER.selected = new Set();
  disarmSelectMode();
  rebuildBuilderFrames();
  saveStore({builderFrames: BUILDER.frames});
});

// Arms/disarms the 3-click start/end/reset cycle on the Frame Selector row
// above (see renderLibFrameRow's onclick and LIB.phase). Click again to
// disarm early — that only stops arming further clicks, it does not clear
// a selection already sitting there.
gmSelectFrames.onclick = withActiveFlash(gmSelectFrames, () => {
  LIB.armed = !LIB.armed;
  gmSelectFrames.classList.toggle('armed', LIB.armed);
});

// Copies whatever's selected in the Frame Selector's own row (LIB.selected,
// filled by the gmSelectFrames 3-click cycle) onto SHARED.clipboard, in frame
// order — not necessarily the order the two clicks happened in, since
// either end can be clicked first. Turns its own 'ready' green back off
// and resets the cycle to click 1, so the very next click on a frame
// starts a fresh pick rather than landing on click 3 by surprise.
function copySelectedLibFrames() {
  if (!LIB.selected.size) {
    libStatus.textContent = 'Select Frames, then click a frame above to start a selection '
      + '(click again to finish it) — then Copy Selected.';
    return;
  }
  const indices = [...LIB.selected].sort((a, b) => a - b);
  SHARED.clipboard = indices.map(i => LIB.frames[i]);
  libStatus.textContent = `Copied ${SHARED.clipboard.length} frame(s) — Paste Selected is ready.`;
  gmCopySelected.classList.remove('ready');
  gmLibViewToggle.classList.remove('ready');
  // The clipboard now has something in it — Paste Selected is the next
  // step, same "ready" green Copy Selected itself just had.
  gmPasteSelected.classList.add('ready');
  setLibSelected([]);
  LIB.rangeStart = null;
  LIB.phase = 0;
  // Copied — the review is over either way, so land back on the full
  // collection rather than leaving the view filtered to a selection that
  // no longer exists.
  if (LIB.showSelectedOnly) { LIB.showSelectedOnly = false; applyLibViewMode(); }
}

gmCopySelected.onclick = withActiveFlash(gmCopySelected, copySelectedLibFrames);

// Switches the row/slider above between the full collection and just
// LIB.selected, so a selection can be scrubbed through before deciding —
// Copy Selected if it looks right, or click this again to back out.
// Backing out UN-STAGES the pick (same as click 3 of the select cycle):
// this is a review step, not a second way to hold a selection.
gmLibViewToggle.onclick = withActiveFlash(gmLibViewToggle, () => {
  if (!LIB.showSelectedOnly) {
    if (!LIB.selected.size) {
      libStatus.textContent = 'Select Frames, then click a frame above to start a selection '
        + '(click again to finish it) — then Show Selected on Timeline.';
      return;
    }
    LIB.showSelectedOnly = true;
  } else {
    LIB.showSelectedOnly = false;
    setLibSelected([]);
    LIB.rangeStart = null;
    LIB.phase = 0;
    gmCopySelected.classList.remove('ready');
    gmLibViewToggle.classList.remove('ready');
  }
  applyLibViewMode();
});

// Empties the Frame Selector's OWN collection — unchecks every clip in
// sarah_clips/libs and clears LIB.picked, same idea as gmClearAll above but
// for this row instead. Does not touch the Clip-Gap Builder, CLIPBOARD: SHARED.clipboard,
// the loaded scene, or Timeline Scenes.
gmFrameSelectorClearAll.onclick = withActiveFlash(gmFrameSelectorClearAll, () => {
  LIB.picked = [];
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
  if (!SHARED.clipboard.length) {
    libStatus.textContent = 'Nothing on the clipboard — Select Frames above, then Copy Selected, first.';
    return;
  }
  doPaste(BUILDER.frames.length ? +builderSlider.value + 1 : 0);
});

// ── Working Clips: saving out, and dropping back in ──────────────────────
// Save: the whole Clip-Gap Builder collection, in its own order, filed
// under the section PICKING one names — the dropdown is the button, there
// is no second click. The popup that asks for the name is the page's own
// modal, not window.prompt; see modalPrompt() in app.js for why.
//
// The dropdown falls back to its own blank option afterwards, whether the
// save happened or was cancelled, so it never sits showing a destination
// as though it were a setting. It is an action.
gmSaveTarget.onchange = withActiveFlash(gmSaveToWorking, async () => {
  const section = gmSaveTarget.value;
  gmSaveTarget.value = '';
  if (!section) return;
  const label = (WorkingClips.sections().find(s => s.key === section) || {}).label || section;
  const r = await WorkingClips.saveBuilder(section, () => modalPrompt({
    title: 'Save to Working Clips',
    label: `${BUILDER.frames.length} frame(s) → ${label}. Name this clip:`,
    value: '',
  }));
  libStatus.textContent = r.ok
    ? `Saved "${r.entry.name}" (${r.entry.n} frames) to ${label}.`
    : r.why === 'cancelled' ? 'Save cancelled.' : r.why;
});

// Replace: the active Working Clip goes in where the Frame Selector's own
// selection is. A different frame count is allowed — the two collections
// are Carson's to line up — but never silently, because a replacement that
// changes the length changes the timing of everything after it.
gmReplaceSelected.onclick = withActiveFlash(gmReplaceSelected, async () => {
  const entry = WorkingClips.active();
  if (!entry) {
    libStatus.textContent = 'Tick a clip in Working Clips to make it active first.';
    return;
  }
  if (!LIB.selected.size) {
    libStatus.textContent = 'Select Frames above, then click a frame to start a selection '
      + '(click again to finish it) — then Replace Selected.';
    return;
  }
  const indices = [...LIB.selected].sort((a, b) => a - b);
  if (entry.n !== indices.length) {
    const go = await modalConfirm({
      title: 'Mismatch frame count',
      msg: `The selection is ${indices.length} frame(s) and "${entry.name}" is `
         + `${entry.n}. Use it anyway?`,
      yes: 'Yes', no: 'No',
    });
    if (!go) { libStatus.textContent = 'Replace cancelled.'; return; }
  }
  replaceLibSelection(indices, WorkingClips.activeFrames());
  libStatus.textContent = `Replaced ${indices.length} frame(s) with "${entry.name}" `
    + `(${entry.n} frames).`;
});

// The selection is a set of positions in the row, and Copy/Paste already
// only ever produce a CONTIGUOUS one (the 3-click cycle picks a start and
// an end). Splicing the whole span out and the new frames in keeps the
// row's order intact for any count, matching or not.
//
// This edits LIB.frames in place, and LIB.frames is REBUILT from LIB.picked
// whenever a box is ticked — so a replacement lives until the next tick,
// on purpose: it is a working edit for building something, not a change to
// the library, which is read-only from here.
function replaceLibSelection(indices, frames) {
  const at = indices[0];
  const span = indices[indices.length - 1] - at + 1;
  LIB.frames.splice(at, span, ...frames);
  setLibSelected([]);
  LIB.rangeStart = null;
  LIB.phase = 0;
  gmCopySelected.classList.remove('ready');
  gmLibViewToggle.classList.remove('ready');
  if (LIB.showSelectedOnly) { LIB.showSelectedOnly = false; }
  renderLibFrameRow();
  applyLibViewMode();
  const land = Math.min(at, Math.max(0, libViewIndices().length - 1));
  libSlider.value = land;
  showLibFrame(land);
  Players.refresh();
}

// ── the Audio Menu's own Clear All ───────────────────────────────────────
// Stops every player and unloads what is in them, so the audio side is
// back to nothing loaded. Deliberately does NOT untick anything in
// sarah_clips/libs — that empties the Frame Selector's collection too, and
// is the Frame Selector Menu's own Clear All.
gmAudioClearAll.onclick = withActiveFlash(gmAudioClearAll, () => {
  Players.reset();
  libStatus.textContent = 'Audio cleared — nothing loaded in any player.';
});

// ── the three Play buttons ───────────────────────────────────────────────
// The click lands HERE, then goes on to the one scenario that owns it in
// frame-player.js, which passes its own specifics to the shared engine:
//
//   button  →  this file  →  OriginalAudio / FrameSelector / GapBuilder
//                         →  FramePlayer's engine
//
// Each step logs on the way through, so a trace in the console shows
// exactly which route a click actually took.
gmSoundBitPlayPause.onclick = withActiveFlash(gmSoundBitPlayPause, () => {
  console.log('gap-builder: click → OriginalAudio');
  OriginalAudio.play();
});
gmLibPlayPause.onclick = withActiveFlash(gmLibPlayPause, () => {
  console.log('gap-builder: click → FrameSelector');
  FrameSelector.play();
});
gmBuilderPlayPause.onclick = withActiveFlash(gmBuilderPlayPause, () => {
  console.log('gap-builder: click → GapBuilder');
  GapBuilder.play();
});

// ── hand the player what it needs ────────────────────────────────────────
// frame-player.js owns all three Play buttons but none of the data they
// act on — the checked library, the Frame Selector's row, and the
// Clip-Gap Builder's current clip all live here and change as the user
// works. Every one is handed over as a FUNCTION, not a value: LIB.picked and
// LIB.frames are REASSIGNED on every check/uncheck, so a captured
// reference would go stale the first time a box was ticked.
//
// Last thing in this file on purpose — everything named below has to
// exist before it runs.
Players.configure({
  // showFrame and slider are the Frame Selector's OWN viewer, and only its
  // OWN Play button reaches them — see the stepper in frame-player.js.
  showFrame: pos => { LIB.stepping = true; showLibFrame(pos); LIB.stepping = false; },
  slider: () => libSlider,
  // ...and the Clip-Gap Builder's own, reached only by ITS own button.
  builderFrames: () => BUILDER.frames,
  builderShow: i => { BUILDER.stepping = true; showBuilderFrame(i); BUILDER.stepping = false; },
  builderSlider: () => builderSlider,
  picked: () => LIB.picked,
  frames: () => LIB.frames,
  viewIndices: () => libViewIndices(),
  order: () => LIB.order,
});
