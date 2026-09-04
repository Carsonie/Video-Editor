// sarah_clips/libs — the two library panels and the Frame Selector.
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

// ── sarah_clips/libs ─────────────────────────────────────────────────────
// The list itself is read-only, refreshed whenever a pair is opened. Each
// file also gets a checkbox: checking one pulls its frames (a still is
// one frame; a clip is every frame) into the inspector below. That
// inspector is a SEPARATE viewer, slider and frame strip from the
// scene's own — Carson's call, so browsing a library clip never disturbs
// where you are in the scene's own combined-frame review.
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
