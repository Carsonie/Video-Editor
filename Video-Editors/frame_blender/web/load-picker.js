// Frame Blender — the Load picker.
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
//
// SPLIT OUT OF app.js A SECOND TIME, same day, because of a real bug: this
// section defines pickStores(), and timeline.js does
//
//     document.getElementById('tlLoadBtn').onclick = pickStores;
//
// at LOAD TIME. In the original single file that worked, because function
// declarations hoist within one script. Across two <script> tags they do
// not: timeline.js runs first and reads an identifier that does not exist
// yet, and the page threw "pickStores is not defined" on every load.
//
// So this file must stay loaded BEFORE timeline.js. Nothing in it reads
// anything timeline.js declares at load time — checked, not assumed.
//
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
