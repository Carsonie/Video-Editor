// Hand frame-player.js its data sources. Loaded LAST of the gap files.
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
