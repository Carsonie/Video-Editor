/*
 * Segment and Avatar Editor — the layered page's behaviour.
 *
 * A plain .js file since 2026-09-04. It used to be a <script> block inside
 * a Python string in player.py: every brace doubled, no linting, no syntax
 * highlighting, and a stray apostrophe killed the page at RENDER time
 * rather than at edit time.
 *
 * THE PAGE SHIPS EMPTY AND THE VIEW ARRIVES OVER THE API.
 * Sixteen values used to be baked into the HTML. They now come from
 * GET /api/view?slug=..., and everything below runs only once that
 * answers — which is what the async wrapper is for.
 *
 * WHY /api/view AND NOT A REBUILD FROM meta.json: base_rel, overlay_rel and the two source names are handed in
 * when the pair is opened and are not recoverable from either clip's
 * meta.json afterwards. serve.py records them in view.json at open time.
 */

/** The slug is the first path segment of /<slug>/viewer.html. */
function viewSlug() {
  const q = new URLSearchParams(location.search).get('slug');
  if (q) return q;
  const parts = location.pathname.split('/').filter(Boolean);
  return parts.length ? parts[0] : '';
}

(async function () {
  const res = await fetch('/api/view?slug=' + encodeURIComponent(viewSlug()));
  if (!res.ok) {
    document.body.textContent = 'Could not load this view: ' + res.status;
    return;
  }
  const VIEW = await res.json();
  document.documentElement.style.setProperty('--box', VIEW.box + 'px');
  document.getElementById('playerName').textContent = VIEW.player_label;
  // EDITOR — what is open. See mp4_splitter/web/app.js for the why; the
  // same line is in seq.js.
  document.title = `Segment and Avatar Editor — ${VIEW.title}`;
  document.getElementById('slider').max = VIEW.max_n;


  const SLUG = VIEW.slug;
  const BASE_REL = VIEW.base_rel;
  const OVERLAY_REL = VIEW.overlay_rel;
  const HAS_A = { base: VIEW.base_audio, overlay: VIEW.over_audio };
  const T = {
    base:    { n: VIEW.base_n, ext: VIEW.base_ext, fps: VIEW.base_fps, name: VIEW.base_name, marks: new Set() },
    overlay: { n: VIEW.over_n, ext: VIEW.over_ext, fps: VIEW.over_fps, name: VIEW.over_name, marks: new Set() }
  };
  let which = 'base';
  let ver = Date.now();
  let solo = false;

  const $ = id => document.getElementById(id);
  const pad = n => String(n).padStart(5, '0');
  const cur = () => T[which];

  function paint() {
    document.documentElement.style.setProperty('--active',
      which === 'base' ? 'var(--base)' : 'var(--over)');
    $('tBase').classList.toggle('on', which === 'base');
    $('tOver').classList.toggle('on', which === 'overlay');
    $('stage').className = !solo ? '' : (which === 'base' ? 'dimOver' : 'dimBase');
    $('soloBtn').classList.toggle('on', solo);
    $('who').innerHTML =
      `editing <b>${which === 'base' ? 'BACKGROUND' : 'OVERLAY'}</b> — ` +
      `<b>${cur().name}</b> · ${cur().n} frames · ${(cur().n / cur().fps).toFixed(2)}s` +
      (VERSTAMP ? ` &nbsp;·&nbsp; <span style="color:#8a949b">${VERSTAMP}</span>` : '');
  }

  // One playhead over BOTH clips. Each layer holds its own last frame when it
  // runs out, which is what the finished video does too — the avatar track and
  // the demo track are rarely the same length.
  function show(n) {
    const maxN = Math.max(T.base.n, T.overlay.n);
    n = Math.max(1, Math.min(maxN, n));
    $('slider').value = n;
    $('slider').max = maxN;
    const b = Math.min(n, T.base.n), o = Math.min(n, T.overlay.n);
    $('baseImg').src = `base/frames/frame_${pad(b)}${T.base.ext}?v=${ver}`;
    $('overImg').src = `overlay/frames/frame_${pad(o)}${T.overlay.ext}?v=${ver}`;
    $('pos').innerHTML =
      `frame <b>${n}</b> / ${maxN} &nbsp;·&nbsp; ${((n - 1) / cur().fps).toFixed(3)}s ` +
      `&nbsp;·&nbsp; base ${b}/${T.base.n} &nbsp;·&nbsp; overlay ${o}/${T.overlay.n}`;
    renderTicks();
  }

  function renderTicks() {
    const maxN = Math.max(T.base.n, T.overlay.n);
    const t = $('ticks'); t.innerHTML = '';
    for (const m of cur().marks) {
      const el = document.createElement('div');
      el.className = 'tick';
      el.style.left = ((m - 1) / Math.max(1, maxN - 1) * 100) + '%';
      el.title = `frame ${m} — click to jump`;
      el.addEventListener('mousedown', e => { e.preventDefault(); e.stopPropagation(); show(m); });
      t.appendChild(el);
    }
  }

  async function api(path, body) {
    const r = await fetch(path, { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(Object.assign({ slug: SLUG, which }, body)) });
    const d = await r.json();
    if (d.error) { $('status').textContent = 'Error: ' + d.error; return null; }
    return d;
  }

  async function loadMarks() {
    for (const w of ['base', 'overlay']) {
      const r = await fetch(`/api/marks?slug=${SLUG}&which=${w}`);
      const d = await r.json();
      T[w].marks = new Set(d.marks || []);
    }
    renderTicks();
  }

  // ── playback ──────────────────────────────────────────────────────────
  // Frames are individual images, so playing means swapping two <img> sources
  // at the clip's own rate. Paced against the wall
  // clock rather than setInterval(1000/fps): setInterval drifts, and a drifting
  // preview is worse than no preview when the whole point is judging timing.
  //
  // ⚠ SILENT. These are frames, not the video — nothing here plays the audio.
  let playing = false, rafId = null, playT0 = 0, playF0 = 1;
  // 2x skims; the slow rates are for judging a seam -- the join between two
  // scenes, or the moment the avatar's mouth meets the audio. At 25fps a seam
  // lands in 40ms; 0.125x stretches it to 320ms. PLAYBACK ONLY.
  //
  // Browsers refuse audio outside roughly 0.25x..4x. Below the floor the track
  // is PAUSED rather than left to drift: a stopped clock is caught by the tick,
  // a wrong one is not.
  let RATE = 1;
  const AUDIO_RATE_FLOOR = 0.25;
  const PRELOAD = 40;

  function preload(from) {
    const maxN = Math.max(T.base.n, T.overlay.n);
    for (let i = from; i < from + PRELOAD && i <= maxN; i++) {
      new Image().src = `base/frames/frame_${pad(Math.min(i, T.base.n))}${T.base.ext}?v=${ver}`;
      new Image().src = `overlay/frames/frame_${pad(Math.min(i, T.overlay.n))}${T.overlay.ext}?v=${ver}`;
    }
  }

  // Whichever track actually carries sound is the clock. In a help video that
  // is the AVATAR, not the screen capture — the demo footage is silent. Two
  // clocks drift, and sync is the thing this playback exists to judge.
  function clockAud() {
    if (HAS_A.overlay && !$('audOver').paused) return $('audOver');
    if (HAS_A.base && !$('audBase').paused) return $('audBase');
    return null;
  }
  function tick() {
    if (!playing) return;
    const maxN = Math.max(T.base.n, T.overlay.n);
    const fps = cur().fps || 25;
    const a = clockAud();
    let n;
    if (a) {
      n = Math.floor(a.currentTime * fps) + 1;
      if (n > maxN) { for (const e of [$('audBase'), $('audOver')]) e.currentTime = 0; n = 1; }
    } else {
      n = playF0 + Math.floor((performance.now() - playT0) / 1000 * fps * RATE);
    }
    if (n > maxN) {
      if ($('loopChk').checked) { playT0 = performance.now(); playF0 = 1; n = 1; }
      else { stop(); show(maxN); return; }
    }
    show(n);
    if (n % 20 === 0) preload(n + 1);
  }
  function play() {
    const maxN = Math.max(T.base.n, T.overlay.n);
    playing = true;
    playF0 = (+$('slider').value >= maxN) ? 1 : +$('slider').value;
    playT0 = performance.now();
    $('playBtn').textContent = '❚❚ Pause';
    $('playBtn').classList.add('on');
    preload(playF0);
    // Both tracks start from the same frame, so the mix matches the picture.
    for (const [k, id] of [['base','audBase'], ['overlay','audOver']]) {
      if (!HAS_A[k]) continue;
      const e = $(id);
      e.currentTime = Math.min((playF0 - 1) / (cur().fps || 25), Math.max(0, (T[k].n - 1) / T[k].fps));
      // Whichever track carries sound is the frame clock, so slowing the
      // audio slows the picture with it — one clock still, at either rate.
      e.playbackRate = Math.max(AUDIO_RATE_FLOOR, RATE);
      if (RATE >= AUDIO_RATE_FLOOR) e.play().catch(() => {});
    }
    rafId = setInterval(tick, Math.max(8, 1000 / ((cur().fps || 25) * RATE) / 2));
  }
  function stop() {
    playing = false;
    if (rafId) clearInterval(rafId);
    rafId = null;
    for (const id of ['audBase','audOver']) $(id).pause();
    $('playBtn').textContent = '▶ Play';
    $('playBtn').classList.remove('on');
  }
  $('playBtn').onclick = () => playing ? stop() : play();
  $('rateSel').onchange = () => {
    RATE = parseFloat($('rateSel').value);
    $('rateSel').classList.toggle('off1', RATE !== 1);
    $('status').textContent = (RATE < AUDIO_RATE_FLOOR && (HAS_A.base || HAS_A.overlay))
      ? `Audio is off below ${AUDIO_RATE_FLOOR}x - the browser will not play a track that slow. The picture is still exact.` : '';
    if (!playing) return;
    for (const [k, id] of [['base','audBase'], ['overlay','audOver']]) {
      if (!HAS_A[k]) continue;
      const e = $(id);
      if (RATE < AUDIO_RATE_FLOOR) { e.pause(); continue; }
      e.playbackRate = RATE;
      if (e.paused) { e.currentTime = (+$('slider').value - 1) / (cur().fps || 25); e.play().catch(() => {}); }
    }
    // Rebase the elapsed-time origin onto the frame showing now, or the
    // playhead jumps the moment the rate changes.
    playF0 = +$('slider').value;
    playT0 = performance.now();
    clearInterval(rafId);
    rafId = setInterval(tick, Math.max(8, 1000 / ((cur().fps || 25) * RATE) / 2));
  };
  $('muteBtn').onclick = () => {
    const m = !$('audOver').muted;
    for (const id of ['audBase','audOver']) $(id).muted = m;
    $('muteBtn').textContent = m ? '🔇' : '🔊';
  };
  if (!HAS_A.base && !HAS_A.overlay) {
    $('muteBtn').disabled = true; $('muteBtn').textContent = '🔇';
    $('muteBtn').title = 'neither clip has an audio track';
  }

  $('tBase').onclick = () => { which = 'base'; refreshEditGate(); paint(); show(+$('slider').value); };
  $('tOver').onclick = () => { which = 'overlay'; refreshEditGate(); paint(); show(+$('slider').value); };
  $('soloBtn').onclick = () => { solo = !solo; paint(); };
  ['p1','n1','p10','n10','prevMark','nextMark'].forEach(id =>
    $(id).addEventListener('click', stop, true));
  $('slider').addEventListener('mousedown', stop);
  $('p1').onclick = () => show(+$('slider').value - 1);
  $('n1').onclick = () => show(+$('slider').value + 1);
  $('p10').onclick = () => show(+$('slider').value - 10);
  $('n10').onclick = () => show(+$('slider').value + 10);
  $('slider').oninput = () => show(+$('slider').value);

  $('markBtn').onclick = async () => {
    const n = +$('slider').value, on = !cur().marks.has(n);
    const d = await api('/api/mark', { frame: n, on });
    if (!d) return;
    on ? cur().marks.add(n) : cur().marks.delete(n);
    $('status').textContent = `${on ? 'Marked' : 'Unmarked'} frame ${n} on ${which}.`;
    renderTicks();
  };
  function jump(dir) {
    const s = [...cur().marks].sort((a, b) => a - b), n = +$('slider').value;
    const t = dir > 0 ? s.find(m => m > n) : [...s].reverse().find(m => m < n);
    if (t !== undefined) show(t);
  }
  $('prevMark').onclick = () => jump(-1);
  $('nextMark').onclick = () => jump(1);

  async function edit(path, side) {
    const d = await api(path, { at: Math.min(+$('slider').value, cur().n), count: 1, side });
    if (!d) return;
    cur().n = d.nb_frames;
    cur().marks = new Set(d.marks || []);
    ver++;                       // frames moved on disk — every cached URL is suspect
    $('status').textContent =
      `${path.includes('dup') ? 'Added' : 'Deleted'} 1 frame ${side} on ${which} — now ${d.nb_frames} frames.`;
    show(d.current || +$('slider').value);
  }
  $('addL').onclick = () => edit('/api/frames/dup', 'left');
  $('addR').onclick = () => edit('/api/frames/dup', 'right');
  $('delL').onclick = () => edit('/api/frames/del', 'left');
  $('delR').onclick = () => edit('/api/frames/del', 'right');

  $('cutBtn').onclick = async () => {
    if (!cur().marks.size) { $('status').textContent = `No break points on ${which}.`; return; }
    if (!confirm(`Cut ${cur().name} at ${cur().marks.size} break point(s)?`)) return;
    const d = await api('/api/cut', {});
    if (!d) return;
    $('status').textContent = `Wrote ${d.count} segment(s) to:\n${d.outdir}`;
  };
  $('saveBtn').onclick = async () => {
    if (!confirm(`Overwrite ${cur().name} with its edited length (${cur().n} frames)?\n\n` +
                 `The current file is archived to z_History/ first.`)) return;
    const d = await api('/api/save', {});
    if (!d) return;
    ver++;
    $('status').textContent = `Saved ${d.duration_s}s to:\n${d.path}`;
  };

  document.addEventListener('keydown', e => {
    if (e.key === 'ArrowLeft')  { e.altKey ? jump(-1) : show(+$('slider').value - (e.shiftKey ? 10 : 1)); e.preventDefault(); }
    if (e.key === 'ArrowRight') { e.altKey ? jump(1)  : show(+$('slider').value + (e.shiftKey ? 10 : 1)); e.preventDefault(); }
    if (e.key === ' ') { $('playBtn').click(); e.preventDefault(); }
    if (e.key === 'm' || e.key === 'M') { $('markBtn').click(); e.preventDefault(); }
    if (e.key === 'b' || e.key === 'B') { $('tBase').click(); e.preventDefault(); }
    if (e.key === 'o' || e.key === 'O') { $('tOver').click(); e.preventDefault(); }
  });

  // ── the scene list ────────────────────────────────────────────────────
  // Selecting a scene RELOADS the page against a new base, because a pair is
  // keyed on both files and its cache is per-pair. The overlay is carried
  // across unchanged, which is the point: step scene by scene with the same
  // avatar clip laid over each one.
  let SIB = null, VERSTAMP = '';
  async function loadScenes() {
    try {
      const r = await fetch(`/api/siblings?path=${encodeURIComponent(BASE_REL)}`);
      SIB = await r.json();
      if (SIB.error) { $('sceneNote').textContent = SIB.error; return; }
    } catch (e) { $('sceneNote').textContent = String(e); return; }
    const sel = $('verSel');
    sel.innerHTML = '';
    for (const v of SIB.versions) {
      const o = document.createElement('option');
      o.value = v; o.textContent = `v${v}  (${SIB.by_version[v].length} scenes)`;
      if (v === SIB.current_version) o.selected = true;
      sel.appendChild(o);
    }
    VERSTAMP = `segment v${SIB.current_version ?? '?'}` +
               (SIB.overlay_version ? ` · avatar v${SIB.overlay_version}` : ' · no avatar set');

    // WHERE, on its own and first. This is the fact that changes what an edit
    // DOES, so it does not belong in a row of version numbers — which is how it
    // was, and why the panel read as five chips of one kind when it was two.
    $('scopeBar').innerHTML = SIB.editor_scope === 'sandbox'
      ? `Editing <b>sandbox</b> — your working copy.` +
        `<br><span class="sub">Reads and writes here only. dev/ is the safe copy, never touched.</span>`
      : `Editing <b>${SIB.layout || 'files'}</b> directly.` +
        `<br><span class="sub">There is no safe copy in front of these files.</span>`;

    // WHICH VERSION, one row per part, tied to the LAYER it feeds. The dot and
    // colour match the Background/Overlay toggles above the stage, so a version
    // number attaches to something already understood instead of floating free.
    // "scenes v1" also went: the list is called scenes, so that chip read as the
    // version OF the list. It is the avatar set.
    const _cv = String(SIB.current_version ?? '');
    const nmiss = (SIB.by_version[_cv] || []).filter(i => i.missing).length;
    const rows = [
      `<div class="vrow base"><span class="dot">&#9679;</span>` +
        `<span class="who">background</span><span class="what">segment</span>` +
        `<span class="ver">v${SIB.current_version ?? '?'}</span></div>`,
      `<div class="vrow over"><span class="dot">&#9679;</span>` +
        `<span class="who">overlay</span><span class="what">avatar + audio</span>` +
        (SIB.overlay_version
          ? `<span class="ver">v${SIB.overlay_version}</span>`
          : `<span class="ver" style="color:#e05555">none</span>`) + `</div>`,
    ];
    if (SIB.script_version)
      rows.push(`<div class="vrow meta"><span class="dot">&middot;</span>` +
                `<span class="who">words</span><span class="what">script</span>` +
                `<span class="ver">v${SIB.script_version}</span></div>`);
    if (nmiss)
      rows.push(`<div class="vrow meta"><span class="dot">!</span>` +
                `<span class="who" style="color:#e05555">missing</span>` +
                `<span class="what">no sandbox copy</span>` +
                `<span class="ver" style="color:#e05555">${nmiss}</span></div>`);
    $('verStamp').innerHTML = rows.join('');
    paint();
    sel.onchange = () => renderScenes(+sel.value);
    renderScenes(SIB.current_version ?? SIB.versions[0]);
  }
  // Scenes whose edits are blocked. A SET OF LOCKS, not of permissions, so the
  // empty default means everything stays editable exactly as before — the lock
  // changes nothing until you deliberately turn one on. Per page load: it is a
  // guard while you work, not a property of the file.
  // Keyed "<scene>:<layer>", because a scene has TWO editable things and they
  // are locked independently: you routinely finish the footage while the avatar
  // is still being retimed. A set of LOCKS, not permissions, so empty means
  // everything stays editable exactly as before.
  const LOCKED = new Set();
  const lockKey = (n, layer) => `${n}:${layer}`;
  const isLocked = (n, layer) => LOCKED.has(lockKey(n, layer));

  // Gate the controls that CHANGE something, against the scene they would act
  // on. Cut and Save are included: they write files, which is the thing a lock
  // most needs to stop.
  function refreshEditGate() {
    const n = currentSceneN();
    // Gate against the layer that is LIT, because that is the one every edit
    // acts on. Locking the segment must not stop you retiming the avatar.
    const blocked = n != null && isLocked(n, which);
    for (const id of ['addL', 'addR', 'delL', 'delR', 'cutBtn', 'saveBtn']) {
      const el = $(id);
      if (el) {
        el.disabled = blocked;
        el.title = blocked
          ? `The ${which === 'base' ? 'segment' : 'overlay'} of scene ${n} is locked — untick its lock in the list to edit it`
          : '';
      }
    }
  }
  // Row styling reflects BOTH locks: one layer locked is dimmed, both locked is
  // struck through. A single "locked" class could not tell those apart.
  function paintLockState() {
    for (const el of document.querySelectorAll('.scene')) {
      const n = +el.dataset.n;
      const b = isLocked(n, 'base'), o = isLocked(n, 'overlay');
      el.classList.toggle('lk-base', (b || o) && !(b && o));
      el.classList.toggle('lk-both', b && o);
      el.classList.remove('locked');
    }
  }

  let CUR_N = null;
  const currentSceneN = () => CUR_N;

  // Totals, footing the list: how many scenes, how long they run, and how many
  // frames each LAYER holds. The two frame totals stay SEPARATE -- they are
  // different files of different lengths, and one combined number would mean
  // nothing. Spacers keep each total under the column it sums.
  function renderTotals(rows) {
    const usable = rows.filter(r => !r.missing);
    const secs = usable.reduce((a, r) => a + (r.dur || 0), 0);
    const segF = usable.reduce((a, r) => a + (r.frames || 0), 0);
    const ovF  = usable.reduce((a, r) => a + (r.overlay_frames || 0), 0);

    const d = document.createElement('div');
    d.className = 'scene totals';
    d.title = `${usable.length} scenes, ${secs.toFixed(2)}s, `
            + `${segF} segment frames, ${ovF} overlay frames`;
    const pad = kind => {
      const x = document.createElement('span');
      x.className = 'cbpad ' + kind;
      return x;
    };
    d.appendChild(pad('pk'));

    const body = document.createElement('span');
    body.style.cssText = 'display:flex;gap:8px;align-items:baseline;flex:1;min-width:0';
    body.innerHTML = `<span class="lab">${usable.length} scenes</span>`
                   + `<span class="dur">${secs.toFixed(2)}s</span>`;
    d.appendChild(body);

    for (const [layer, total] of [['base', segF], ['overlay', ovF]]) {
      d.appendChild(pad('ed'));
      const f = document.createElement('span');
      f.className = 'frames' + (layer === 'overlay' ? ' ov' : '');
      f.textContent = total;
      f.title = `${total} ${layer === 'base' ? 'segment' : 'overlay'} frames in total`;
      d.appendChild(f);
    }
    $('sceneList').appendChild(d);
  }

  function renderScenes(v) {
    const list = $('sceneList'); list.innerHTML = '';
    for (const it of (SIB.by_version[v] || [])) {
      const d = document.createElement('div');
      d.className = 'scene' + (it.current ? ' cur' : '');
      if (it.current) CUR_N = it.n;
      d.dataset.n = it.n;   // the timeline view has always set this; this one did not
      // No left bar: that gutter is the checkbox column now. A row's kind is
      // still readable from its tag on the right.
      if (it.missing) d.style.opacity = '.55';
      // Each row carries the version of the avatar clip it will load, because
      // "which scenes am I looking at" is a per-row question once more than one
      // set exists — and a row with no clip must look different, not just quiet.
      // A sandbox override has to be VISIBLE in the list. Finding out from the
      // finished video that a scene used an edit you forgot about is exactly
      // the failure the sandbox layer makes possible.
      // In sandbox scope EVERY row is sandbox, so the per-row tag would be
      // noise. Flag the opposite instead: a scene with NO sandbox copy.
      // A bookend is not a script scene. Mark it so, or "00-opening" reads as
      // a scene that has somehow gone missing from the script.
      const ovTag = it.extra
        ? `<span class="ovv" style="color:#7ec8e3;border-color:#2f5f72">bookend</span>`
        : it.missing
        ? `<span class="ovv" style="color:#e05555;border-color:#7a3a3a">missing</span>`
        : it.overlay
          ? `<span class="ovv">v${SIB.overlay_version}</span>`
          : `<span class="ovv" style="color:#e05555;border-color:#7a3a3a">none</span>`;
      const cb = document.createElement('input');
      cb.type = 'checkbox'; cb.className = 'pick'; cb.dataset.n = it.n;
      cb.checked = it.current;          // start with what is already open
      cb.disabled = !!it.missing;
      cb.onclick = ev => { ev.stopPropagation(); updatePick(); };
      d.appendChild(cb);
      const body = document.createElement('span');
      body.style.cssText = 'display:flex;gap:8px;align-items:baseline;flex:1';
      body.innerHTML = `<span class="num">${it.n}</span>` +
                    `<span class="lab">${it.label || it.name}</span>` +
                    ovTag +
                    `<span class="dur">${it.dur ?? '?'}s</span>`;
      d.appendChild(body);
      d.title = it.name;
      body.onclick = () => {
        if (it.current) return;
        // THIS scene's own overlay when one exists, so picture, avatar and audio
        // are the same scene. Falling back to the current overlay would put the
        // wrong voice under the right footage, which is the fault this replaced.
        const ov = it.overlay || OVERLAY_REL;
        $('status').textContent = it.overlay
          ? `Loading scene ${it.n} with its own narration…`
          : `Scene ${it.n} has no overlay of its own — keeping the current one.`;
        location.href = `/api/open-pair-go?base=${encodeURIComponent(it.path)}`
                      + `&overlay=${encodeURIComponent(ov)}`;
      };
      // Two locks and two counts: the SEGMENT (the footage) and the OVERLAY
      // (the avatar). They are separate controls because they are separate
      // files with separate lengths, edited one layer at a time.
      const addPair = (layer, count, exact, present) => {
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.className = 'edcb' + (layer === 'overlay' ? ' ov' : '');
        cb.dataset.n = it.n; cb.dataset.layer = layer;
        cb.checked = !isLocked(it.n, layer);
        cb.disabled = !present;
        cb.title = present
          ? `Editing allowed for this scene's ${layer === 'base' ? 'segment' : 'overlay'}`
          : `this scene has no ${layer === 'base' ? 'segment' : 'overlay'}`;
        cb.onclick = ev => {
          ev.stopPropagation();
          if (cb.checked) LOCKED.delete(lockKey(it.n, layer));
          else LOCKED.add(lockKey(it.n, layer));
          paintLockState();
          refreshEditGate();
        };
        d.appendChild(cb);

        const fr = document.createElement('span');
        fr.className = 'frames' + (layer === 'overlay' ? ' ov' : '') + (exact ? '' : ' est');
        fr.dataset.n = it.n; fr.dataset.layer = layer;
        fr.textContent = count == null ? '—' : (exact ? String(count) : '~' + count);
        fr.title = count == null
          ? `no ${layer === 'base' ? 'segment' : 'overlay'} frame count available`
          : (exact ? `${count} frames, counted from the extraction`
                   : `about ${count} frames, read without extracting — it can be out by one until the scene has been opened`);
        d.appendChild(fr);
      };
      addPair('base', it.frames, it.frames_exact, !it.missing);
      addPair('overlay', it.overlay_frames, it.overlay_frames_exact, !!it.overlay);
      list.appendChild(d);
    }
    const anyOv = (SIB.by_version[v] || []).some(i => i.overlay);
    renderTotals(SIB.by_version[v] || []);
    paintLockState();
    refreshEditGate();
    updatePick();
    $('sceneNote').innerHTML =
      (SIB.overlay_version
        ? `Each scene loads its own avatar clip and audio.`
        : `<b>No per-scene overlays.</b> Build them with make_scene_overlays.py, or every scene ` +
          `shows the same avatar clip.`) +
      (SIB.versions.length > 1
        ? `<br>${SIB.versions.length} segment cuts on disk; switching version keeps the pairing.`
        : '') +
      (SIB.overlay_version && !anyOv ? `<br>⚠ none matched this cut's scene numbers.` : '');
  }

  // Several scenes on ONE timeline. A scene alone cannot show how it JOINS the
  // next, and a join is where the faults are — a pose that jumps, a voice that
  // starts before the picture settles.
  function updatePick() {
    const picked = [...document.querySelectorAll('.pick')].filter(c => c.checked);
    $('seqBtn').disabled = picked.length < 1;
    $('seqBtn').innerHTML = picked.length
      ? `&#9654; Timeline of ${picked.length} scene${picked.length === 1 ? '' : 's'}`
      : '&#9654; Timeline of 0 scenes';
  }
  $('seqBtn').onclick = () => {
    const ns = [...document.querySelectorAll('.pick')].filter(c => c.checked)
                 .map(c => +c.dataset.n).sort((a, b) => a - b);
    if (!ns.length) return;
    $('status').textContent = `Building a timeline of ${ns.length} scene(s)…`;
    location.href = `/api/open-seq-go?root=${encodeURIComponent(SIB.folder)}`
                  + `&ns=${ns.join(',')}`;
  };

  paint(); show(1); loadMarks(); loadScenes();
})();
