// Frame Blender — sarah_clips/libs, the Frame Selector, and the Clip-Gap
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

const libInspector = document.getElementById('libInspector');
const libViewerImg = document.getElementById('libViewerImg');
const libSlider = document.getElementById('libSlider');
const libFrameRow = document.getElementById('libFrameRow');
const libNEl = document.getElementById('libN');
const libTotalEl = document.getElementById('libTotal');

let PICKED = [];        // checked clips' metadata, in the order checked
let LIB_FRAMES = [];    // every picked clip's frames, flattened into one list

const libFrameUrl = (clip, local) => `/${clip.slug}/frames/frame_${pad(local + 1)}${clip.ext}`;

function renderLibFrameRow() {
  libFrameRow.innerHTML = '';
  LIB_FRAMES.forEach((f, i) => {
    const d = document.createElement('div');
    d.className = 'libframe';
    d.style.backgroundImage = `url(${f.url})`;
    d.title = `${f.clip.name} — frame ${f.local + 1}/${f.clip.n}`;
    d.onclick = () => { libSlider.value = i; showLibFrame(i); };
    libFrameRow.appendChild(d);
  });
}

function showLibFrame(i) {
  const f = LIB_FRAMES[i];
  [...libFrameRow.children].forEach((d, j) => d.classList.toggle('cur', j === i));
  if (!f) { libViewerImg.removeAttribute('src'); libNEl.textContent = '—'; return; }
  libViewerImg.src = f.url;
  libNEl.textContent = i + 1;
  const cur = libFrameRow.children[i];
  if (cur) cur.scrollIntoView({block: 'nearest', inline: 'center'});
}

// Rebuilds the flattened frame list from PICKED, in checked order —
// called after every check/uncheck, and on Clear / a scene switch.
function rebuildLibFrames() {
  LIB_FRAMES = [];
  for (const clip of PICKED)
    for (let i = 0; i < clip.n; i++) LIB_FRAMES.push({url: libFrameUrl(clip, i), clip, local: i});
  libInspector.hidden = LIB_FRAMES.length === 0;
  libSlider.max = Math.max(0, LIB_FRAMES.length - 1);
  libSlider.disabled = LIB_FRAMES.length === 0;
  libTotalEl.textContent = LIB_FRAMES.length || '—';
  renderLibFrameRow();
  showLibFrame(0);
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
const libPickBtn = document.getElementById('libPickBtn');

function renderBuilderFrameRow() {
  builderFrameRow.innerHTML = '';
  BUILDER_FRAMES.forEach((f, i) => {
    const d = document.createElement('div');
    d.className = 'libframe';
    d.style.backgroundImage = `url(${f.url})`;
    d.title = `${f.clip.name} — frame ${f.local + 1}/${f.clip.n}`;
    d.onclick = () => { builderSlider.value = i; showBuilderFrame(i); };
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
// Only the actual mutation site (libPickBtn.onclick, below — and, soon,
// the Gap Builder Controller Menu actions) saves.
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

// The Frame N/Total button IS the copy action — clicking it takes
// whatever the Selector's slider is currently sitting on.
libPickBtn.onclick = () => {
  const f = LIB_FRAMES[+libSlider.value];
  if (!f) return;
  BUILDER_FRAMES.push(f);
  rebuildBuilderFrames(BUILDER_FRAMES.length - 1);
  saveStore({builderFrames: BUILDER_FRAMES});
};

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
    builderPanel.hidden = false;
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
        name.className = 'name'; name.title = f.name; name.textContent = f.name;
        const metaEl = document.createElement('span');
        metaEl.className = 'meta'; metaEl.textContent = meta;
        row.appendChild(cb); row.appendChild(name); row.appendChild(metaEl);
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
// The ten action buttons live in index.html (gmAddOpeningStill,
// gmAddClosingStill, gmSelectOne, gmSelectMultiple, gmPasteOne,
// gmPasteSelected, gmDeleteOne, gmDeleteSelected, gmDuplicateOne,
// gmDuplicateSelected). Two are wired below; the other eight are plain
// edits to BUILDER_FRAMES (select/copy, paste, delete, duplicate) and are
// the next piece of work, not this one.

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

// Opening: 4 IDENTICAL frames of the rest pose, no transition into them —
// Carson's own call. Scene 1 has nothing before it to jump from, and every
// other scene should already be closing out on this exact pose (see the
// Closing button below), so there is nothing to move FROM either way.
document.getElementById('gmAddOpeningStill').onclick = async () => {
  const rp = await getRestPoseFrame();
  if (!rp) {
    libStatus.textContent = `Couldn't find ${REST_POSE_NAME} in this store's sarah_clips/libs/stills/.`;
    return;
  }
  for (let i = 0; i < 4; i++) BUILDER_FRAMES.push(rp);
  rebuildBuilderFrames(BUILDER_FRAMES.length - 1);
  saveStore({builderFrames: BUILDER_FRAMES});
};

// Closing: 3 frames fading from whatever the Builder currently ends on
// into the rest pose, then 4 held frames of the pose itself — 7 frames
// total. If the Builder is empty there is nothing to fade FROM, so this
// falls back to landing on the pose directly, the same as Opening.
document.getElementById('gmAddClosingStill').onclick = async () => {
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
};
