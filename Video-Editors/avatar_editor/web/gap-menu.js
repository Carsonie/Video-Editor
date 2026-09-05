// The Gap Builder Menu, the Audio Menu's Clear All, and the three Play buttons.
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
