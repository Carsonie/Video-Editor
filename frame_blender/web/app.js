// Frame Blender — loading and unloading a scene, and the bootstrap.
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
  // ── loading and unloading a scene ────────────────────────────────────────
  // These two are exact opposites, and that symmetry is the whole point of
  // the restructure: showEmpty() is what the page looks like with SCENE
  // null, openPair() is what it looks like with SCENE set. Clear just calls
  // showEmpty(). Nothing else has to be "undone".

  function showEmpty() {
    SCENE = null;
    n = 1;
    combined.clear();
    document.getElementById('pageTitle').textContent = 'Frame Blender — nothing loaded';
    document.title = 'Frame Blender';
    document.getElementById('combinedCount').textContent = '0';
    document.getElementById('filmstrip').innerHTML = '';
    status.textContent = '';
    baseImg.removeAttribute('src');
    overImg.removeAttribute('src');
    for (const id of ['baseN', 'overN', 'baseTotal', 'overTotal', 'totalFrames'])
      document.getElementById(id).textContent = '—';
    document.getElementById('prevBtn').disabled = true;
    document.getElementById('nextBtn').disabled = true;
    canvas.style.display = 'none';
    scrubSlider.value = 0; scrubSlider.max = 0; scrubSlider.disabled = true;
    scrubLabel.textContent = 'No frames combined yet';
    clipVideo.removeAttribute('src');
    clipVideo.style.display = 'none';
    buildStatus.textContent = '';
    playVideoBtn.disabled = true;
    playVideoBtn.title = 'No built video yet';
    lastBuiltFrames = null;
    tlSaveMp4Btn.disabled = true;
    tlSaveMp4Btn.title = 'Build a clip first';
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
      document.getElementById('pageTitle').textContent = `Frame Blender — ${d.label}`;
      document.title = `Frame Blender — ${d.label}`;
      document.getElementById('baseTotal').textContent = d.base_n;
      document.getElementById('overTotal').textContent = d.over_n;
      document.getElementById('totalFrames').textContent = d.max_n;
      status.textContent = '';
      playVideoBtn.disabled = false;
      playVideoBtn.title = 'Build the whole scene, then play it';
      render();
      restorePairProgress();
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
