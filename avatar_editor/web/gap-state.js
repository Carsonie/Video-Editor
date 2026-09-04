// The two rows' state — LIB, BUILDER and the one thing they share.
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
