// Frame Blender — the page's behaviour.
//
// Plain .js on purpose. Until 2026-08-30 all of this lived inside a Python
// string in player.py, where every brace had to be doubled for str.format()
// and a stray one broke the page at render time rather than in an editor.
// It is served as a static file now: no build step, no escaping, and the
// browser's own debugger lines up with the file.
//
// Was briefly split into this file plus a second, gap-builder.js (added
// 2026-09-01, removed 2026-09-02 when the Clip-Gap Builder moved to the
// Avatar Editor's own scope). Not wrapped in an IIFE, a leftover of that
// split kept on purpose: nothing else on this single-purpose page needs
// its own scope, and there is no leaked-global risk to guard against.
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
