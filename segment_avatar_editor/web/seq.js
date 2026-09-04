/*
 * Segment and Avatar Editor — the timeline page's behaviour.
 *
 * A plain .js file since 2026-09-04. It used to be a <script> block inside
 * a Python string in player.py: every brace doubled, no linting, no syntax
 * highlighting, and a stray apostrophe killed the page at RENDER time
 * rather than at edit time.
 *
 * THE PAGE SHIPS EMPTY AND THE VIEW ARRIVES OVER THE API.
 * Five values used to be baked into the HTML. They now come from
 * GET /api/view?slug=..., and everything below runs only once that
 * answers — which is what the async wrapper is for.
 *
 * WHY /api/view AND NOT A REBUILD FROM meta.json: the manifest maps every global frame to (scene, local frame) and
 * is built when the timeline is opened. Nothing on disk holds it but the
 * view.json serve.py writes at open time.
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
  document.title = VIEW.title;
  document.getElementById('slider').max = VIEW.total;


  const SEQ = VIEW.manifest;
  const ROOT_REL = VIEW.root_rel;
  const $ = id => document.getElementById(id);
  const pad = n => String(n).padStart(5, '0');
  const status = m => { $('status').textContent = m; };

  // ── the timeline index ────────────────────────────────────────────────
  // Global frame -> which scene, and how far into it. The timeline's length is
  // the sum of every scene's BASE length, because that is what is on screen.
  //
  // Rebuilt, not computed once: adding or deleting a frame changes a scene's
  // length, and every start after it moves. Editing on a stale index would put
  // the NEXT edit into the wrong scene, which is the one failure here that
  // writes to a file.
  let starts = [], total = 0, ver = Date.now();
  function reindex() {
    starts = []; total = 0;
    for (const s of SEQ) { starts.push(total); total += s.base_n; }
    $('slider').max = Math.max(1, total);
  }
  function at(g) {
    let i = 0;
    while (i + 1 < SEQ.length && g > starts[i + 1]) i++;
    return { i, local: g - starts[i] };      // local is 1-based
  }
  const curI = () => at(+$('slider').value).i;

  // ── which layer an edit acts on ───────────────────────────────────────
  // Same meaning as the single-scene view: `which` is the layer being EDITED,
  // and Solo dims the other so there is no doubt which one that is. Every edit
  // endpoint takes a cache slug, and each scene here keeps its own top-level
  // cache — so an edit on the timeline is the same call the single-scene view
  // makes, with this scene's slug and the frame number local to it.
  // `solo` is gone with its button — both layers are always shown. `which`
  // survives because marks, Cut and Save each act on ONE layer; it is derived
  // from the scene rows' ticks now, in syncWhich().
  let which = 'base';
  const slugOf = (i, w) => (w || which) === 'base' ? SEQ[i].base_slug : SEQ[i].over_slug;
  const lenOf  = (i, w) => (w || which) === 'base' ? SEQ[i].base_n    : SEQ[i].over_n;

  // ── solo ────────────────────────────────────────────────────────────────
  // Both -> Avatar -> Footage -> Both. A VIEW control: it changes nothing on
  // disk, does not touch the per-scene edit ticks, and is not remembered
  // anywhere. It is what you are LOOKING at, not what you are working on.
  //
  // Avatar-only puts a checkerboard behind her, because the fault this exists
  // to find is a bad ALPHA EDGE — a black fringe, or a matte flattened
  // somewhere upstream — and that is invisible against the footage.
  const SOLO_STEPS = [
    { key: 'both',    cls: '',          label: '&#9673; Both' },
    { key: 'overlay', cls: 'solo-ov',   label: '&#9673; Avatar' },
    { key: 'base',    cls: 'solo-base', label: '&#9673; Footage' },
  ];
  let SOLO = 0;
  function paintSolo() {
    const st = $('stage'), b = $('soloBtn');
    if (!st || !b) return;
    for (const s of SOLO_STEPS) if (s.cls) st.classList.remove(s.cls);
    const cur = SOLO_STEPS[SOLO];
    if (cur.cls) st.classList.add(cur.cls);
    b.innerHTML = cur.label;
    b.classList.toggle('on', SOLO !== 0);
  }
  // Guarded. A bare .onclick on a missing element throws, and a throw at load
  // kills every line after it — this exact button did that: the scene list
  // never rendered and the stage never got a frame, from one absent control.
  if ($('soloBtn')) $('soloBtn').onclick = () =>
    { SOLO = (SOLO + 1) % SOLO_STEPS.length; paintSolo(); };
  paintSolo();
  function paint() {
    // The Background/Overlay/Solo row is gone: the scene rows' ticks say which
    // layer an edit touches, so a second control saying it again was one more
    // thing to keep in step. What is left of paint() is the accent colour, so
    // the frame border still shows which layer is being worked on. Both layers
    // are always shown now -- there is no control left to un-solo with, and a
    // view stuck dimmed with no way back is worse than no solo at all.
    // Four states, not two: `which` only ever names ONE layer, so it cannot
    // tell "both ticked" from "segment only" -- and those mean different things
    // for + and -. Read the ticks directly.
    const ci = curI(), cn = (SEQ[ci] || {}).n;
    const tb = cn != null && !isLocked(cn, 'base')    && !!slugOf(ci, 'base');
    const to = cn != null && !isLocked(cn, 'overlay') && !!slugOf(ci, 'overlay');
    const varName = (tb && to) ? '--both' : tb ? '--seg' : to ? '--over' : '--none';
    // Resolve the palette entry to a literal and set both the variable (other
    // rules read it) and the border itself.
    //
    // A note for anyone measuring this: #stage carries `transition:
    // border-color .12s`, and a running transition outranks an inline style, so
    // getComputedStyle during those 120ms returns the colour it is coming FROM,
    // not the one just set. That is correct behaviour and invisible to a human;
    // it only misleads a script. To assert on the settled colour, set
    // `transition:none` on #stage first.
    const lit = getComputedStyle(document.documentElement)
                  .getPropertyValue(varName).trim();
    document.documentElement.style.setProperty('--active', lit);
    $('stage').style.borderColor = lit;
    // The border is the only thing this function owns, so it must not clear
    // classes it did not set. `className = ''` wiped SOLO on every scene
    // change: the button still read "Avatar" while the footage came back,
    // which is worse than not having the control — it lied about the view.
    //
    // Nothing puts a class on #stage for the border any more; it is an inline
    // style two lines up. So there is nothing here to clear.
    paintSolo();
  }

  function show(g) {
    g = Math.max(1, Math.min(total, g));
    $('slider').value = g;
    const { i, local } = at(g);
    const s = SEQ[i];
    $('baseImg').src = `../${s.base_slug}/frames/frame_${pad(Math.min(local, s.base_n))}${s.base_ext}?v=${ver}`;
    if (s.over_slug) {
      $('overImg').style.display = '';
      // A scene's avatar is usually SHORTER than its footage; hold her last
      // frame rather than blanking her, which is what the finished video does.
      $('overImg').src = `../${s.over_slug}/frames/frame_${pad(Math.min(local, s.over_n))}${s.over_ext}?v=${ver}`;
    } else {
      $('overImg').style.display = 'none';
    }
    $('pos').innerHTML = `timeline <b>${g}</b> / ${total} &middot; ` +
      `${((g - 1) / (s.fps || 25)).toFixed(2)}s of ${(total / (s.fps || 25)).toFixed(2)}s`;
    if (i !== curScene) { curScene = i; onSceneChange(i, local); loadMarks(i); }
    // EVERY frame, not only at a boundary. The highlighted word moves WITHIN a
    // scene, and this call used to sit inside the branch above — so the word lit
    // up as a scene started and then sat on the first word until the next one.
    // Cheap to run: paintVtt() returns early per row whose state has not
    // changed, and only re-centres when the scene actually moved.
    paintVtt();
    renderReport();
    paintBar();
  }
  let curScene = -1;

  function paintBar() {
    const { i } = at(+$('slider').value);
    const n = SEQ[i].n;
    [...$('segbar').children].forEach((el, k) => el.classList.toggle('cur', k === i));
    // Matched on the scene NUMBER, not the row's position: the list holds every
    // scene now, so position and scene are no longer the same thing.
    [...$('sceneList').children].forEach(el => el.classList.toggle('cur', +el.dataset.n === n));
  }

  function rebuildBar() {
    $('segbar').innerHTML = '';
    for (let i = 0; i < SEQ.length; i++) {
      const s = SEQ[i];
      const b = document.createElement('div');
      b.className = 'segblk'; b.style.flex = String(s.base_n); b.dataset.n = s.n;
      b.textContent = s.n; b.title = `${s.n} ${s.label} — ${(s.base_n / (s.fps || 25)).toFixed(2)}s`;
      b.onclick = () => { stop(); show(starts[i] + 1); };
      $('segbar').appendChild(b);
    }
    paintBar();
  }

  // ── break points ──────────────────────────────────────────────────────
  // Kept per CACHE SLUG, which is per scene per layer — the same unit the
  // server stores them in. Drawn at their GLOBAL position so a mark stays under
  // the frame it belongs to as the bar rescales.
  const MARKS = {};
  const marksOf = (i, w) => MARKS[slugOf(i, w)] || new Set();

  async function loadMarks(i) {
    for (const w of ['base', 'overlay']) {
      const slug = slugOf(i, w);
      if (!slug || MARKS[slug]) continue;
      try {
        const r = await fetch(`/api/marks?slug=${slug}`);
        const d = await r.json();
        MARKS[slug] = new Set(d.marks || []);
      } catch (e) { MARKS[slug] = new Set(); }
    }
    renderTicks();
    // The marks arrive AFTER the first paint, and the zone is derived from
    // them, so row 4 and the loop label were still reporting "no marks — zone
    // is the whole scene" on a scene that had four. Anything derived from
    // marks has to be redrawn once they land, not only when the playhead moves.
    renderReport();
  }

  // Every mark on the active layer, as timeline positions, in order.
  function globalMarks() {
    const out = [];
    for (let i = 0; i < SEQ.length; i++) {
      for (const m of marksOf(i)) {
        // A mark past the end of the scene's FOOTAGE has no place on a timeline
        // measured in footage. It is still stored, and still shown when that
        // scene is opened on its own.
        if (m <= SEQ[i].base_n) out.push(starts[i] + m);
      }
    }
    return out.sort((a, b) => a - b);
  }

  function renderTicks() {
    const t = $('ticks'); t.innerHTML = '';
    for (const g of globalMarks()) {
      const { i, local } = at(g);
      const el = document.createElement('div');
      el.className = 'tick';
      el.style.left = ((g - 1) / Math.max(1, total - 1) * 100) + '%';
      el.title = `scene ${SEQ[i].n} frame ${local} — click to jump`;
      el.addEventListener('mousedown', e => { e.preventDefault(); e.stopPropagation(); stop(); show(g); });
      t.appendChild(el);
    }
  }

  // ── editing ───────────────────────────────────────────────────────────
  // Every call carries THIS scene's slug and a frame number local to it. The
  // server never sees a timeline frame, which is what keeps a cut on the
  // timeline identical to the same cut made scene by scene.
  async function api(path, body) {
    const i = curI(), slug = slugOf(i);
    if (!slug) { status(`Scene ${SEQ[i].n} has no ${which} layer to edit.`); return null; }
    try {
      const r = await fetch(path, { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(Object.assign({ slug }, body)) });
      const d = await r.json();
      if (d.error) { status('Error: ' + d.error); return null; }
      return d;
    } catch (e) { status('Error: ' + e); return null; }
  }

  $('markBtn').onclick = async () => {
    const i = curI(), { local } = at(+$('slider').value), slug = slugOf(i);
    if (!slug) { status(`Scene ${SEQ[i].n} has no ${which} layer.`); return; }
    if (local > lenOf(i)) {
      status(`Frame ${local} is past the end of this scene's ${which} layer (${lenOf(i)}).`);
      return;
    }
    const set = MARKS[slug] || (MARKS[slug] = new Set());
    const on = !set.has(local);
    const d = await api('/api/mark', { frame: local, on });
    if (!d) return;
    on ? set.add(local) : set.delete(local);
    status(`${on ? 'Marked' : 'Unmarked'} frame ${local} of scene ${SEQ[i].n} (${which}).`);
    renderTicks();
  };

  // Mark-to-mark runs across the WHOLE timeline, not just this scene — the
  // marks either side of a join are exactly the pair worth stepping between.
  function jumpMark(dir) {
    const s = globalMarks(), g = +$('slider').value;
    const t = dir > 0 ? s.find(m => m > g) : [...s].reverse().find(m => m < g);
    if (t !== undefined) { stop(); show(t); }
    else status(dir > 0 ? 'No mark after here.' : 'No mark before here.');
  }
  $('prevMark').onclick = () => jumpMark(-1);
  $('nextMark').onclick = () => jumpMark(1);

  // ── per-row add / remove ────────────────────────────────────────────────
  // The two ticks on a row choose the target, so one pair of buttons covers all
  // three cases without a mode anywhere:
  //
  //   segment + overlay  ->  both layers change, both counts grow
  //   segment only       ->  only the segment changes
  //   overlay only       ->  only the overlay changes
  //
  // Only the scene under the PLAYHEAD can be edited: it is the only one with a
  // current frame to duplicate. Every other row's buttons are disabled rather
  // than guessing a frame.
  // ── tooltips ────────────────────────────────────────────────────────────
  // Reads the element's own `title`, so every control is covered — including
  // the per-row ones whose text changes with state ("scene 4 is not under the
  // playhead", "2 changes pending"). The title is REMOVED while hovering and
  // put back on leave, otherwise the browser's own tooltip appears underneath
  // this one at its own timing.
  (function tooltips() {
    const tip = document.getElementById('tip');
    let timer = null, held = null;

    function hide() {
      clearTimeout(timer); timer = null;
      tip.classList.remove('on');
      if (held) { held.el.title = held.text; held = null; }
    }
    function show(el, text) {
      tip.textContent = text;
      tip.classList.add('on');
      // Placed after it is measurable, and kept on screen: a tip that runs off
      // the edge is no more use than no tip.
      const r = el.getBoundingClientRect(), t = tip.getBoundingClientRect();
      let x = r.left + r.width / 2 - t.width / 2;
      let y = r.top - t.height - 8;
      if (y < 6) y = r.bottom + 8;                       // flip under when tight above
      x = Math.max(6, Math.min(x, window.innerWidth - t.width - 6));
      tip.style.left = Math.round(x) + 'px';
      tip.style.top = Math.round(y) + 'px';
    }

    document.addEventListener('mouseover', e => {
      const el = e.target.closest('[title]');
      if (!el || el === (held && held.el)) return;
      hide();
      const text = el.getAttribute('title');
      if (!text) return;
      held = { el, text };
      el.removeAttribute('title');                       // suppress the native one
      // 3 seconds. Long enough that a tip does not chase the pointer across a
      // row of eight buttons on the way to the one you meant.
      timer = setTimeout(() => show(el, text), 3000);
    });
    document.addEventListener('mouseout', e => {
      if (held && !held.el.contains(e.relatedTarget)) hide();
    });
    // A tip that outlives what it describes is a lie, so anything that moves
    // or changes the page takes it down.
    for (const ev of ['mousedown', 'wheel', 'keydown']) document.addEventListener(ev, hide, true);
    window.addEventListener('blur', hide);
  })();

  // ── naming modal ────────────────────────────────────────────────────────
  // Anything that CREATES a scene has to be named and confirmed before it
  // happens, because it changes the store's own structure rather than a
  // preview. Join uses it now; split will use the same one.
  function askName(opts) {
    return new Promise(resolve => {
      const box = $('modal'), name = $('mName'), err = $('mErr');
      $('mTitle').textContent = opts.title;
      $('mBody').innerHTML = opts.body;
      $('mOk').textContent = opts.ok || 'Confirm';
      name.value = opts.value || '';
      err.textContent = '';
      box.classList.add('on');
      name.focus(); name.select();

      const close = v => {
        box.classList.remove('on');
        document.removeEventListener('keydown', key, true);
        $('mOk').onclick = $('mCancel').onclick = box.onmousedown = null;
        resolve(v);
      };
      const submit = () => {
        const v = name.value.trim().toLowerCase();
        // Checked HERE as well as on the server: the name becomes a folder
        // name, and a bad one should be refused before anything is archived.
        if (!/^[a-z0-9][a-z0-9-]{0,48}$/.test(v)) {
          err.textContent = 'Lower-case letters, digits and hyphens only — this becomes a folder name.';
          name.focus(); return;
        }
        if ((opts.taken || []).includes(v)) {
          err.textContent = `There is already a scene called "${v}".`;
          name.focus(); return;
        }
        close(v);
      };
      const key = e => {
        if (e.key === 'Escape') { e.stopPropagation(); close(null); }
        if (e.key === 'Enter')  { e.stopPropagation(); submit(); }
      };
      document.addEventListener('keydown', key, true);
      $('mOk').onclick = submit;
      $('mCancel').onclick = () => close(null);
      box.onmousedown = e => { if (e.target === box) close(null); };
    });
  }

  // ── which tracks an action acts on ──────────────────────────────────────
  // One place turns the dropdown into the server's vocabulary, and one place
  // paints the border, so the colour can never disagree with what will happen.
  function tracksOf(selId) {
    const v = $(selId).value;
    return v === 'both' ? ['segment', 'avatar'] : v === 'base' ? ['segment'] : ['avatar'];
  }
  function paintAct(selId, wrapId) {
    $(wrapId).dataset.trk = $(selId).value;
  }
  for (const [sel, wrap] of [['joinTrk', 'joinAct'], ['splitTrk', 'splitAct']]) {
    $(sel).onchange = () => paintAct(sel, wrap);
    paintAct(sel, wrap);
  }

  // ── split ───────────────────────────────────────────────────────────────
  // Splits the scene under the pointer at the frame on screen. The frame on
  // screen becomes the FIRST frame of the second half, so what you are looking
  // at is what the new scene opens on.
  async function splitScene() {
    const i = curI();
    if (i < 0 || !SEQ[i]) return;
    const s = SEQ[i], n = s.n;
    if (s.in_script === false) {
      alert(`${String(n).padStart(2, '0')}-${s.label} is a bookend.\n\n`
          + `It is a folder with no row in script.json — the fixed opening or `
          + `closing. A split rewrites the scene list, so it cannot take one.\n\n`
          + `Move the pointer to a script scene and split that.`);
      return;
    }
    const { local } = at(+$('slider').value);
    const trk = tracksOf('splitTrk');

    // Same rule as the join, and for the same reason: a split renumbers every
    // scene after the one it cuts, and it reads the files.
    const dirty = SEQ.filter(x => histOf(x.n).length);
    if (dirty.length) {
      alert(`Save these scenes before splitting.\n\n`
          + dirty.map(x => `  ${x.n} ${x.label} — ${histOf(x.n).length} change(s)`).join('\n')
          + `\n\nA split renumbers every scene after the one it cuts, and reads `
          + `the files on disk. These edits are not on disk yet.\n\n`
          + `Use each scene's save icon, or "Save all scenes".`);
      return;
    }
    const dropped = ['segment', 'avatar'].filter(t => !trk.includes(t))
                      .map(t => t === 'segment' ? 'segment' : 'overlay');
    const lens = { segment: s.base_n, avatar: s.over_n || 0 };
    const bad = trk.filter(t => !(local > 1 && local <= (lens[t] || 0)));
    if (bad.length) {
      status(`Frame ${local} is not inside the ${bad.join(' and ')} of scene ${n}`
           + ` — move the pointer to a frame both halves can exist either side of.`);
      return;
    }
    const taken = ALL.map(a => (a.label || '').toLowerCase());
    const base = (s.label || 'scene').slice(0, 40);

    const first = await askName({
      title: `Split scene ${n} at frame ${local}`,
      ok: 'Next: name the second half',
      value: `${base}-a`.slice(0, 49), taken,
      body:
        `<b>${n} ${s.label || ''}</b> becomes two scenes, cut so that frame`
        + ` <b>${local}</b> is the FIRST frame of the second half.`
        + `<ul>`
        + trk.map(t => `<li>${t === 'segment' ? 'segment' : 'overlay'}:`
                     + ` <b>${local - 1}</b> + <b>${lens[t] - local + 1}</b> frames</li>`).join('')
        + (dropped.length ? `<li class="warn">the <b>${dropped.join(' and ')}</b> is NOT carried into`
                          + ` either half &mdash; recoverable from z_History/ only</li>` : '')
        + `<li class="warn">the narration line stays whole with the FIRST half;`
        + ` the second is left empty for you to write</li>`
        + `<li>every scene in the script is renumbered <b>1..N</b></li>`
        + `<li>the folder replaced, and script.json, are copied to <b>z_History/</b> first</li></ul>`
        + `<p class="warn">This changes the store, not just the preview, and cannot be undone from here.</p>`
        + `<p>Name the FIRST half:</p>`
    });
    if (!first) return;
    const second = await askName({
      title: `Split scene ${n} — second half`,
      ok: 'Split and renumber', value: `${base}-b`.slice(0, 49),
      taken: taken.concat([first]),
      body: `First half: <b>${first}</b> (${local - 1} frames, keeps the narration line).`
          + `<p>Name the SECOND half — the one that opens on frame ${local}:</p>`
    });
    if (!second) return;

    stop();
    status(`Splitting scene ${n} at frame ${local}…`);
    let d;
    try {
      const r = await fetch('/api/split', { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ root: ROOT_REL, n, at: local,
                               labels: [first, second], tracks: trk }) });
      d = await r.json();
    } catch (e) { status(`Split failed: ${e}`); return; }
    if (d.error) { status(`Split failed: ${d.error}`); return; }

    RENUMBERED = true;
    paintSaveBtn();
    const moved = (d.renumbered || []).map(r => `${r.from}→${r.to}`).join(', ');
    alert(`Split scene ${d.split} at frame ${d.at} into "${d.labels[0]}" and "${d.labels[1]}".

`
        + `The narration line stayed with "${d.line_stayed_with}" — the second half needs one writing.

`
        + (moved ? `Renumbered: ${moved}

` : '')
        + `Previous state archived to:
${d.archived_to}

`
        + `The timeline will reload against the new numbering.`);
    location.href = `/api/open-seq-go?root=${encodeURIComponent(ROOT_REL)}`
                  + `&ns=${encodeURIComponent(String(d.split))}`;
  }
  $('splitBtn').onclick = splitScene;

  // ── join ────────────────────────────────────────────────────────────────
  // Renumbering is the part with consequences: `n` is what the rest of the
  // pipeline indexes by, so once the numbers move, saving one scene on its own
  // would write it under a number the others do not agree with yet.
  let RENUMBERED = false;

  // Asked of the STORE, not remembered in the page. A join or a split reloads
  // the timeline, so a flag held here would die at the moment it starts to
  // matter. script.json carries `_was_n` on every scene whose number moved,
  // and that is what this reads.
  async function loadRenumberState() {
    try {
      const r = await fetch(`/api/renumber-state?root=${encodeURIComponent(ROOT_REL)}`);
      const d = await r.json();
      RENUMBERED = !!d.renumbered;
      paintSaveBtn();
      paintBackupBtn();
      // Said, not enforced. Knowing a join moved the numbers is useful; being
      // stopped from saving one scene because of it was not — every edit made
      // after a join is made under the new numbering, since a join reloads the
      // page. Save each scene when you want to.
      if (RENUMBERED) {
        const moved = (d.moved || []).map(m => `${m.from}→${m.to}`).join(', ');
        status(`A join or split renumbered these scenes${moved ? ` (${moved})` : ''}. `
             + `Each scene still saves on its own.`);
      }
      renderScenes();
    } catch (e) { /* leave it false: refusing to save on a guess is worse */ }
  }

  // A bookend — 00-opening, 99-closing — is a real folder with no row in
  // script.json. Join and Split both rewrite the scene list, so neither can
  // touch one. Caught HERE rather than at the server, because the server sees
  // it only after the naming dialog has been filled in and confirmed: the
  // refusal read as "not scenes in the script: [0]" at the end of the job.
  function bookendsOn(list) {
    return list.filter(s => s.in_script === false)
               .map(s => `${String(s.n).padStart(2, '0')}-${s.label}`);
  }

  async function joinTimeline() {
    if (SEQ.length < 2) { status('A join needs at least two scenes on the timeline.'); return; }
    const bk = bookendsOn(SEQ);
    if (bk.length) {
      alert(`This timeline includes ${bk.length === 1 ? 'a bookend' : 'bookends'}: `
          + `${bk.join(', ')}.

`
          + `A bookend is a folder with no row in script.json — the fixed opening `
          + `and closing. A join rewrites the scene list, so it cannot take one.

`
          + `Rebuild the timeline from script scenes only, then join.`);
      return;
    }
    const list = SEQ.map(s => s.n);
    const taken = ALL.map(a => (a.label || '').toLowerCase());
    const segF = SEQ.reduce((a, s) => a + s.base_n, 0);
    const ovlF = SEQ.reduce((a, s) => a + (s.over_n || 0), 0);
    const pending = SEQ.filter(s => histOf(s.n).length).map(s => s.n);

    // A join RENUMBERS every scene, and it reads the FILES. An edit still sitting
    // in a scene's history has not reached a file, and after the renumber its
    // scene no longer has the number that history was recorded against — so it
    // could not be saved even if you wanted to. Refused rather than warned: the
    // warning let you agree to lose them, which is not a choice anyone means to
    // make while naming a new scene.
    if (pending.length) {
      const rows = pending.map(n => {
        const s = SEQ.find(x => x.n === n);
        const c = histOf(n).length;
        return `  ${n} ${s ? s.label : ''} — ${c} change${c === 1 ? '' : 's'}`;
      }).join('\n');
      alert(`Save these scenes before joining.\n\n${rows}\n\n`
          + `A join renumbers every scene and reads the files on disk. These `
          + `edits are not on disk yet, and once the numbers move they cannot `
          + `be saved under the number they were made against.\n\n`
          + `Use each scene's save icon, or "Save all scenes".`);
      return;
    }
    const trk = tracksOf('joinTrk');
    // A scene with no narration, joined to scenes that have one. The opening is
    // the case: it is built from two HeyGen clips plus the morph, so no single
    // raw render sits behind it. Concatenating as-is would start the NEXT
    // scene's narration at frame 1 — Sarah saying the login line over the
    // intro. Filling holds that time open instead.
    const noNar = SEQ.filter(s => s.has_narration === false);
    const fillNar = noNar.length > 0 && noNar.length < SEQ.length && trk.includes('avatar');
    const dropped = ['segment', 'avatar'].filter(t => !trk.includes(t))
                      .map(t => t === 'segment' ? 'segment track' : 'overlay track');

    const name = await askName({
      title: `Join ${SEQ.length} scenes into one`,
      ok: 'Join and renumber',
      value: (SEQ[0].label || 'joined').slice(0, 40),
      taken,
      body:
        `In script order: <b>${SEQ.map(s => `${s.n} ${s.label || ''}`).join('</b>, <b>')}</b>.`
        + `<ul>`
        + (trk.includes('segment') ? `<li>segments joined end to end &mdash; <b>${segF}</b> frames</li>` : '')
        + (trk.includes('avatar')  ? `<li>avatars joined the same way &mdash; <b>${ovlF}</b> frames</li>` : '')
        + (fillNar
           ? `<li><b>${noNar.map(s => s.label).join(', ')}</b> has no narration &mdash; `
             + `its time is held open with a transparent silent clip, `
             + `<b>${noNar.reduce((a, s) => a + s.base_n, 0)}</b> frames, so the narration `
             + `after it stays where it belongs</li>`
           : '')
        + (dropped.length ? `<li class="warn">the <b>${dropped.join(' and ')}</b> of these scenes is NOT carried`
                          + ` into the joined scene &mdash; recoverable from z_History/ only</li>` : '')
        + `<li>their narration lines are joined in order into one line</li>`
        + `<li>every scene in the script is renumbered <b>1..N</b>, since a join leaves a gap</li>`
        + `<li>the folders replaced, and script.json, are copied to <b>z_History/</b> first</li></ul>`
        + `<p class="warn">This changes the store, not just the preview, and cannot be undone from here.</p>`
    });
    if (!name) return;

    stop();
    status(`Joining ${list.length} scenes into "${name}"…`);
    let d;
    try {
      const r = await fetch('/api/join', { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ root: ROOT_REL, ns: list, label: name, tracks: trk, fill_gaps: fillNar }) });
      d = await r.json();
    } catch (e) { status(`Join failed: ${e}`); return; }
    if (d.error) { status(`Join failed: ${d.error}`); return; }

    RENUMBERED = true;
    paintSaveBtn();
    const moved = (d.renumbered || []).map(r => `${r.from}→${r.to}`).join(', ');
    alert(`Joined ${d.joined.join(', ')} into "${d.label}" as scene ${d.new_n}.

`
        + (moved ? `Renumbered: ${moved}

` : '')
        + `Previous state archived to:
${d.archived_to}

`
        + `The timeline will reload against the new numbering.`);
    location.href = `/api/open-seq-go?root=${encodeURIComponent(ROOT_REL)}`
                  + `&ns=${encodeURIComponent(String(d.new_n))}`;
  }
  $('joinBtn').onclick = joinTimeline;

  // ── Backup Scenes ─────────────────────────────────────────────────────
  // Redefined 2026-08-29 (moved here from the scene list panel, and absorbed
  // what used to be the force branch of Save All): archive the sandbox
  // GENERATION about to be replaced, then write the CURRENT editor state —
  // every scene, every layer, whether or not it was tracked as edited, LOCKED
  // tracks included, plus every narrative line — back over sandbox/,
  // unconditionally. This is the one button that never asks whether
  // something changed; it always makes sandbox/ match this timeline exactly,
  // and always keeps a full copy of what it just replaced.
  //
  // WHY THE ARCHIVE STEP EXISTS: none of this is in git. The video is
  // hundreds of megabytes and git keeps every version of every file forever,
  // so the whole Customers/ tree is ignored — which leaves no revert at all.
  // A per-file z_History (api_save's own) covers "undo that one save"; this
  // covers "put the whole generation back". A COPY into 1000_archive, not a
  // move — api_save's rebuild reads each scene straight off its sandbox
  // path, so the file has to still be there when the write below runs.
  //
  // The renumber note: a join or split leaves a `_was_n` marker on every
  // scene whose number moved. The files themselves were already written —
  // atomically, by the join — so the marker is the ONLY thing left
  // outstanding, and clearing it is what "I accept this reorder" means. The
  // button turns green while one is pending.
  async function backupScenes() {
    let plan = null;
    try {
      const r = await fetch('/api/save-archive', { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ root: ROOT_REL, dry: true }) });
      plan = await r.json();
    } catch (e) { /* fall through — the message says so rather than guessing */ }
    if (!plan || plan.error) { status(`Could not read the sandbox: ${plan && plan.error}`); return; }

    const withWork = SEQ.map((s, i) => ({ i, n: s.n,
        layers: ['base', 'overlay'].filter(w => slugOf(i, w)) }))
        .filter(x => x.layers.length);
    const scriptTargets = SEQ.filter(s => VTT && VTT.byN[s.n]);
    if (plan.empty && !withWork.length && !scriptTargets.length) {
      status(`Nothing on the timeline to write, and the sandbox is already empty.`);
      return;
    }
    if (!confirm(`Back up and refill the sandbox?

`
               + (plan.empty
                  ? `The sandbox is currently empty — nothing to archive first.

`
                  : `COPYING ${plan.would_archive.length} scene folder(s) TO
`
                    + `${plan.into}

`)
               + `Then every scene on this timeline (${withWork.length}) is `
               + `written to sandbox/ exactly as configured here right now, `
               + `whether or not it was marked as edited — LOCKED tracks `
               + `included — and every narrative line is written to `
               + `script.json, unconditionally.

`
               + (RENUMBERED
                  ? `A join or split renumbered the scenes. That note is cleared `
                    + `too — it is the only thing left outstanding after one.`
                  : `No renumber note is outstanding.`))) return;
    stop();
    let archivedTo = null;
    try {
      const r = await fetch('/api/save-archive', { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ root: ROOT_REL }) });
      const d = await r.json();
      if (d.error) { status(`Backup Scenes stopped — could not archive the ` +
        `current sandbox first: ${d.error}`); return; }
      archivedTo = d.archived_to;
    } catch (e) {
      status(`Backup Scenes stopped — could not archive the current sandbox ` +
        `first: ${e}`);
      return;
    }

    const btn = $('backupBtn');
    const total_ = withWork.reduce((n, x) => n + x.layers.length, 0);
    let wrote = 0;
    const busy = () => { if (btn) { btn.classList.add('working'); btn.disabled = true;
      btn.innerHTML = `Saving ${wrote} / ${total_}…`; } };
    const rest = () => { if (btn) { btn.classList.remove('working'); btn.disabled = false;
      btn.innerHTML = '&#9707; Backup Scenes'; } };
    busy();

    const done = [], failed = [], warn = [];
    for (const x of withWork) {
      let ok = true;
      for (const w of x.layers) {
        let d;
        try {
          const r = await fetch('/api/save', { method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ slug: slugOf(x.i, w) }) });
          d = await r.json();
        } catch (e) { failed.push(`scene ${x.n} ${w}: ${e}`); ok = false; continue; }
        if (d.error) { failed.push(`scene ${x.n} ${w}: ${d.error}`); ok = false; continue; }
        if (d.warning) warn.push(`scene ${x.n} ${w}: ${d.warning}`);
        setEditedOf(x.i, w, false);
        wrote++;
        busy();
      }
      if (ok) { histOf(x.n).length = 0; done.push(x.n); }
    }

    const lineDone = [], lineFailed = [];
    for (const s of scriptTargets) {
      const text = vLine[s.n] !== undefined ? vLine[s.n] : VTT.byN[s.n].line;
      try {
        const r = await fetch('/api/line', { method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ root: ROOT_REL, n: s.n, line: text }) });
        const d = await r.json();
        if (d.error) { lineFailed.push(`scene ${s.n}: ${d.error}`); continue; }
        VTT.byN[s.n].line = d.line;
        VTT.byN[s.n].words = d.words;
        vLine[s.n] = d.line;
        vDirty.delete(s.n);
        lineDone.push(s.n);
      } catch (e) { lineFailed.push(`scene ${s.n}: ${e}`); }
    }
    if (scriptTargets.length) paintVttSum();

    // Only AFTER the writes landed. Clearing the marker first would leave the
    // note gone and nothing actually written if a save below then failed.
    let cleared = '';
    if (RENUMBERED) {
      try {
        await fetch('/api/renumber-clear', { method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ root: ROOT_REL }) });
        RENUMBERED = false;
        cleared = ' The renumber note is cleared.';
      } catch (e) { cleared = ' ⚠ The renumber note could not be cleared.'; }
    }
    rest();
    paintBackupBtn();
    renderScenes();
    status(`Archived to:
${archivedTo || '(sandbox was already empty)'}
`
         + `Saved ${done.length} of ${withWork.length} scene(s)`
         + (done.length ? `: ${done.join(', ')}` : '') + '.'
         + ` Lines saved for ${lineDone.length} of ${scriptTargets.length} scene(s).`
         + cleared
         + (failed.length ? `\n⚠ ${failed.join('; ')}` : '')
         + (warn.length ? `\n⚠ ${warn.join('; ')}` : '')
         + (lineFailed.length ? `\n⚠ line: ${lineFailed.join('; ')}` : ''));
  }

  // GREEN while a join or split has left a note outstanding — the one moment
  // this button has a second job, and the moment it is easiest to walk away
  // from. Enabled the rest of the time: a backup is worth taking whenever, and
  // putting the only revert this data has behind a rare event would be worse
  // than the confusion that gating it would avoid.
  function paintBackupBtn() {
    const b = $('backupBtn');
    if (b) b.classList.toggle('pending', RENUMBERED);
  }

  // ── Clear All ────────────────────────────────────────────────────────
  // Added 2026-08-29. Empties this BROWSER TAB's session — SEQ and every
  // other piece of state this page has accumulated — so Load can put a
  // different video into a genuinely clean editor rather than one still
  // carrying another video's marks, locks and undo history underneath it.
  //
  // Touches NOTHING on disk. sandbox/ is exactly as it was before this ran;
  // this is memory only, the same memory a page reload already empties —
  // Clear All just does it without leaving the page and losing ROOT_REL.
  //
  // Direct DOM resets below rather than routing through paint()/show()/
  // renderScenes() — every one of those assumes at least one scene exists
  // (SEQ[0], curI(), at(g) all dereference it), and making the zero-scene
  // case safe through all of them is a bigger audit than this button is
  // worth. Simplest correct thing: blank exactly what those functions would
  // have painted, directly.
  function clearAllScenes() {
    if (!confirm(`Clear this editor session?

`
               + `Removes every scene, the narrative table, every mark, `
               + `lock and undo step this tab is holding.

`
               + `Nothing on sandbox/ is touched — this only clears what `
               + `THIS BROWSER TAB has in memory.`)) return;
    stop();
    SEQ.length = 0;
    starts = []; total = 0; which = 'base'; SOLO = 0; vttCentred = -1;
    Object.keys(MARKS).forEach(k => delete MARKS[k]);
    Object.keys(HIST).forEach(k => delete HIST[k]);
    Object.keys(vLine).forEach(k => delete vLine[k]);
    LOCKED.clear();
    vDirty.clear();
    ON.clear();
    RENUMBERED = false;
    VTT = null;

    $('sceneList').innerHTML = '';
    $('baseImg').removeAttribute('src');
    $('overImg').removeAttribute('src');
    $('segbar').innerHTML = '';
    $('ticks').innerHTML = '';
    $('slider').max = 1;
    $('slider').value = 1;
    $('pos').textContent = '';
    $('vttRows').innerHTML = '';
    $('vttSum').textContent = '';
    $('rep').textContent = '';
    $('rebuildBtn').disabled = true;
    $('rebuildBtn').innerHTML = 'Tick at least one scene';
    paintBackupBtn();
    status('Editor cleared — nothing loaded. Use Load to open a video.');
  }
  $('clearAllBtn').onclick = clearAllScenes;

  // ── Load ─────────────────────────────────────────────────────────────
  // Added 2026-08-29: open a different video without leaving the page or
  // hand-building a URL. Two picks — store, then which of its videos — then
  // straight to /api/open-seq-go, the same redirect Rebuild already uses.
  //
  // Re-fetches /api/stores every time the modal opens rather than caching
  // it for the session: a store list is cheap to compute and a stale one
  // — missing a video someone just built — is the one failure mode worth
  // avoiding here.
  async function openLoadModal() {
    const box = $('loadModal'), list = $('loadList'), err = $('loadErr');
    box.classList.add('on');
    err.textContent = '';
    $('loadBack').classList.remove('on');
    $('loadTitle').textContent = 'Load a video — choose a store';
    list.innerHTML = '<div class="empty">Loading stores…</div>';
    let stores;
    try {
      const r = await fetch('/api/stores');
      const d = await r.json();
      stores = d.stores || [];
    } catch (e) { list.innerHTML = ''; err.textContent = `Could not list stores: ${e}`; return; }
    renderStoreList(stores);

    const close = () => {
      box.classList.remove('on');
      document.removeEventListener('keydown', key, true);
      box.onmousedown = null;
    };
    const key = e => { if (e.key === 'Escape') { e.stopPropagation(); close(); } };
    document.addEventListener('keydown', key, true);
    box.onmousedown = e => { if (e.target === box) close(); };
    $('loadCancel').onclick = close;

    function renderStoreList(stores) {
      $('loadTitle').textContent = 'Load a video — choose a store';
      $('loadBack').classList.remove('on');
      err.textContent = '';
      list.innerHTML = '';
      if (!stores.length) {
        list.innerHTML = '<div class="empty">No store with a ready video was found under Customers/.</div>';
        return;
      }
      for (const s of stores) {
        const b = document.createElement('button');
        b.innerHTML = `${s.store}<span class="sub">${s.business} — `
          + `${s.videos.length} video${s.videos.length === 1 ? '' : 's'}</span>`;
        b.onclick = () => renderVideoList(s);
        list.appendChild(b);
      }
    }
    function renderVideoList(s) {
      $('loadTitle').textContent = `Load a video — ${s.store}`;
      $('loadBack').classList.add('on');
      $('loadBack').onclick = () => renderStoreList(stores);
      err.textContent = '';
      list.innerHTML = '';
      for (const v of s.videos) {
        const b = document.createElement('button');
        const reason = !v.scenes.length ? 'its script has no scenes'
          : !v.has_sandbox ? 'no sandbox/ built yet' : null;
        b.innerHTML = `${v.name}<span class="sub">${v.scenes.length} `
          + `scene${v.scenes.length === 1 ? '' : 's'}`
          + (reason ? ` — ${reason}` : ``) + `</span>`;
        b.disabled = !!reason;
        b.onclick = () => confirmLoad(s, v);
        list.appendChild(b);
      }
    }
    function confirmLoad(s, v) {
      if (!confirm(`Load ${s.store} — ${v.name}?

${v.scenes.length} scene(s).

`
                 + `Anything unsaved in the current session is lost — Save `
                 + `Timeline or Save all first if you want it kept.`)) return;
      close();
      status(`Loading ${s.store} — ${v.name}…`);
      location.href = `/api/open-seq-go?root=${encodeURIComponent(v.root)}&ns=${v.scenes.join(',')}`;
    }
  }
  $('loadBtn').onclick = openLoadModal;

  // ── Save Timeline / Save all ────────────────────────────────────────────
  // Both DIRTY-only — the unconditional, everything-regardless-of-state job
  // lives on Backup Scenes now, not here. The only difference between these
  // two is reach: Save Timeline writes video layers pendingOf(i) tracks as
  // edited; Save all does that AND every narrative line vDirty tracks as
  // edited. Neither touches a line or a layer that isn't flagged dirty, and
  // neither archives anything first — Backup Scenes is the one button with
  // a "put the whole generation back" answer.
  async function saveScenes(includeNarrative) {
    const withWork = SEQ.map((s, i) => ({ i, n: s.n, layers: pendingOf(i) }))
        .filter(x => x.layers.length);
    const lineWork = includeNarrative ? SEQ.filter(s => vDirty.has(s.n)) : [];
    if (!withWork.length && !lineWork.length) {
      const held = SEQ.flatMap((s, i) => heldBackOf(i).map(w =>
        `  scene ${s.n}: ${w === 'base' ? 'segment' : 'overlay'} is unticked`));
      status(held.length
        ? `Nothing to save — every edit is on a track you have unticked:
`
          + held.join(`
`)
        : RENUMBERED
          ? `No scene has unsaved edits. A join or split left a renumber note; `
            + `Backup Scenes is what clears it.`
          : `No scene has unsaved edits.`);
      return;
    }
    const lines = withWork.map(x => {
      const names = x.layers.map(w => w === 'base' ? 'segment' : 'overlay');
      const sizes = x.layers.map(w => `${lenOf(x.i, w)}f`);
      return `  scene ${x.n}: ${names.join(' and ')} (${sizes.join(', ')})`;
    }).join(`
`);
    const lineList = lineWork.map(s => `  scene ${s.n}: narrative line`).join(`
`);
    if (!confirm(`Save ${withWork.length} scene(s)`
               + (lineWork.length ? ` and ${lineWork.length} line(s)` : ``)
               + `?

${lines}`
               + (lineWork.length ? `
${lineList}` : ``)
               + `

WRITING TO
${ROOT_REL}/sandbox/

`
               + `Each file keeps its previous version in its own scene's `
               + `z_History/.

`
               + `No whole-set backup is taken and no renumber note is cleared. `
               + `Backup Scenes does both of those.`)) return;
    stop();
    const btn = $(includeNarrative ? 'saveAllBtn' : 'saveTimelineBtn');
    const label = includeNarrative ? '&#128221; Save all' : '&#128190; Save Timeline';
    const total_ = withWork.reduce((n, x) => n + x.layers.length, 0);
    let wrote = 0;
    const busy = () => { if (btn) { btn.classList.add('working'); btn.disabled = true;
      btn.innerHTML = `Saving ${wrote} / ${total_}…`; } };
    const rest = () => { if (btn) { btn.classList.remove('working'); btn.disabled = false;
      btn.innerHTML = label; } };
    busy();

    const done = [], failed = [], warn = [], stale = [];
    const saveOne = (i, w, force) => fetch('/api/save', { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slug: slugOf(i, w), force }) }).then(r => r.json());
    for (const x of withWork) {
      let ok = true;
      for (const w of x.layers) {
        let d;
        try {
          d = await saveOne(x.i, w, false);
        } catch (e) { failed.push(`scene ${x.n} ${w}: ${e}`); ok = false; continue; }
        // STALE scenes are set aside rather than asked about one at a time —
        // a confirm() per scene would mean a wall of popups on a big batch.
        // They get ONE combined question after this loop finishes.
        if (d.error === 'stale') { stale.push({i: x.i, n: x.n, w, message: d.message}); ok = false; continue; }
        if (d.error) { failed.push(`scene ${x.n} ${w}: ${d.error}`); ok = false; continue; }
        if (d.warning) warn.push(`scene ${x.n} ${w}: ${d.warning}`);
        // This track's file now matches its cache. Marked per TRACK, so a
        // scene whose overlay wrote and whose segment failed still shows the
        // segment as outstanding.
        setEditedOf(x.i, w, false);
        wrote++;
        busy();
      }
      // The undo snapshots go only when the whole scene wrote — one that
      // failed keeps them, so it can be retried or walked back.
      if (ok) { histOf(x.n).length = 0; done.push(x.n); }
    }

    if (stale.length) {
      const list = stale.map(s => `  scene ${s.n}: ${s.w === 'base' ? 'segment' : 'overlay'}`).join(`
`);
      const overwrite = confirm(
        `${stale.length} track(s) changed on disk since this page loaded them — `
        + `probably saved from another tab or Frame Blender:

${list}

`
        + `Overwrite them with THIS page's version anyway?`);
      for (const s of stale) {
        if (!overwrite) { failed.push(`scene ${s.n} ${s.w}: ${s.message}`); continue; }
        let d;
        try { d = await saveOne(s.i, s.w, true); }
        catch (e) { failed.push(`scene ${s.n} ${s.w}: ${e}`); continue; }
        if (d.error) { failed.push(`scene ${s.n} ${s.w}: ${d.error}`); continue; }
        if (d.warning) warn.push(`scene ${s.n} ${s.w}: ${d.warning}`);
        setEditedOf(s.i, s.w, false);
        wrote++; busy();
        if (!pendingOf(s.i).length) { histOf(s.n).length = 0; done.push(s.n); }
      }
    }

    const lineDone = [], lineFailed = [];
    for (const s of lineWork) {
      const text = vLine[s.n];
      try {
        const r = await fetch('/api/line', { method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ root: ROOT_REL, n: s.n, line: text }) });
        const d = await r.json();
        if (d.error) { lineFailed.push(`scene ${s.n}: ${d.error}`); continue; }
        VTT.byN[s.n].line = d.line;
        VTT.byN[s.n].words = d.words;
        vLine[s.n] = d.line;
        vDirty.delete(s.n);
        lineDone.push(s.n);
      } catch (e) { lineFailed.push(`scene ${s.n}: ${e}`); }
    }
    if (lineWork.length) paintVttSum();

    // Put the labels back BEFORE anything else, so a failure below cannot
    // leave the button spinning over a run that has stopped.
    rest();
    renderScenes();
    status(`Saved ${done.length} of ${withWork.length} scene(s)`
         + (done.length ? `: ${done.join(', ')}` : '') + '.'
         + (includeNarrative ? ` Lines saved for ${lineDone.length} of ${lineWork.length} scene(s).` : '')
         + (failed.length ? `\n⚠ ${failed.join('; ')}` : '')
         + (warn.length ? `\n⚠ ${warn.join('; ')}` : '')
         + (lineFailed.length ? `\n⚠ line: ${lineFailed.join('; ')}` : ''));
  }
  $('backupBtn').onclick = backupScenes;

  // ── list-level actions ──────────────────────────────────────────────────
  const setAllPicks = on => {
    for (const c of document.querySelectorAll('.pick')) if (!c.disabled) c.checked = on;
    updatePick();
  };
  $('selAll').onclick  = () => setAllPicks(true);
  $('selNone').onclick = () => setAllPicks(false);

  // Which scenes a list-level action applies to: ticked AND already on the
  // timeline. A ticked scene that has not been rebuilt in yet has no cache
  // loaded and no frame counts to compare, so it is reported rather than
  // silently treated as done.
  function targets() {
    const ticked = new Set(picked());
    const on = [], pending = [];
    for (const n of ticked) {
      const i = SEQ.findIndex(s => s.n === n);
      if (i >= 0) on.push(i); else pending.push(n);
    }
    return { on, pending };
  }

  function balanceReport() {
    const { on, pending } = targets();
    let rows = 0, frames = 0;
    for (const i of on) {
      if (!slugOf(i, 'base') || !slugOf(i, 'overlay')) continue;
      const d = Math.abs(SEQ[i].base_n - SEQ[i].over_n);
      if (d) { rows++; frames += d; }
    }
    $('balanceBtn').disabled = rows === 0;
    $('balNote').innerHTML = rows === 0
      ? (on.length
          ? `<span class="ok">&#10003;</span> the ticked scenes already match, track for track.`
          : `Tick a scene to compare its two tracks.`)
        + (pending.length ? ` <span class="skip">${pending.length} ticked scene(s) are not on the timeline yet — rebuild first.</span>` : '')
      : `<b>${rows}</b> ticked scene${rows === 1 ? '' : 's'} differ${rows === 1 ? 's' : ''} by <b>${frames}</b> frame${frames === 1 ? '' : 's'} in total.`
        + (pending.length ? ` <span class="skip">${pending.length} not on the timeline yet.</span>` : '');
  }

  // ── update frame imbalance ──────────────────────────────────────────────
  // The two tracks of a scene are different files and drift apart as each is
  // edited. This pads the SHORTER one by repeating its LAST frame until both
  // hold the same count — the last frame because that is the settled end of
  // the shot, where a repeat is invisible; anywhere else it would show as a
  // stutter mid-motion.
  //
  // Each scene's change goes through its own history, so this is undoable one
  // scene at a time exactly like a hand edit.
  async function balanceScenes() {
    const { on, pending } = targets();
    const work = [];
    for (const i of on) {
      if (!slugOf(i, 'base') || !slugOf(i, 'overlay')) continue;
      const diff = SEQ[i].base_n - SEQ[i].over_n;
      if (!diff) continue;
      const short = diff > 0 ? 'overlay' : 'base';
      if (isLocked(SEQ[i].n, short)) { work.push({ i, short, skipped: true }); continue; }
      work.push({ i, short, count: Math.abs(diff) });
    }
    const doable = work.filter(w => !w.skipped);
    if (!doable.length) {
      status(work.length
        ? `Nothing done — the track needing frames is locked on every scene that differs.`
        : `Nothing to do — the ticked scenes already match.`);
      return;
    }
    if (!confirm(`Balance ${doable.length} scene(s)?

`
               + doable.map(w => `  scene ${SEQ[w.i].n}: +${w.count} to the `
                                + `${w.short === 'base' ? 'segment' : 'overlay'}`).join('\n')
               + `

Each repeats that track's LAST frame. Undoable per scene.`)) return;
    stop();
    const done = [], failed = [];
    for (const w of doable) {
      const { i, short, count } = w;
      const before = await snapshot(i, [short]);
      const len = lenOf(i, short);
      let d;
      try {
        const r = await fetch('/api/frames/dup', { method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ slug: slugOf(i, short), at: len, count, side: 'right' }) });
        d = await r.json();
      } catch (e) { failed.push(`scene ${SEQ[i].n}: ${e}`); continue; }
      if (d.error) { failed.push(`scene ${SEQ[i].n}: ${d.error}`); continue; }
      if (short === 'base') SEQ[i].base_n = d.nb_frames; else SEQ[i].over_n = d.nb_frames;
      MARKS[slugOf(i, short)] = new Set(d.marks || []);
      const row = ALL.find(x => x.n === SEQ[i].n);
      if (row) {
        if (short === 'base') { row.frames = d.nb_frames; row.frames_exact = true; }
        else { row.overlay_frames = d.nb_frames; row.overlay_frames_exact = true; }
      }
      pushHist(i, before);
      done.push(`${SEQ[i].n} +${count} ${short === 'base' ? 'seg' : 'ovl'}`);
    }
    ver++;
    reindex(); rebuildBar(); renderNote(); renderScenes();
    show(+$('slider').value); renderTicks(); renderReport();
    const skipped = work.filter(w => w.skipped).map(w => SEQ[w.i].n);
    status(`Balanced ${done.length} scene(s): ${done.join(', ')}. `
         + `Timeline is ${(total / (SEQ[0].fps || 25)).toFixed(2)}s.`
         + (skipped.length ? `
⚠ skipped ${skipped.join(', ')} — the track needing frames is locked.` : '')
         + (pending.length ? `
⚠ ${pending.length} ticked scene(s) are not on the timeline.` : '')
         + (failed.length ? `
⚠ ${failed.join('; ')}` : ''));
  }
  $('balanceBtn').onclick = balanceScenes;

  // ── per-scene change history ────────────────────────────────────────────
  // One stack per SCENE, because a scene is what gets saved. An entry is the
  // frame map of each layer BEFORE an edit, so undo is "put this layer back to
  // that map" — no need to keep the JPEGs themselves, since a map plus the
  // source rebuilds any past state exactly.
  //
  // Cleared on a successful save: at that moment the file on disk IS the
  // current state, so there is nothing left to undo back to.
  // WHICH TRACKS OF A SCENE HAVE EDITS THAT ITS FILE HAS NOT GOT.
  //
  // Read from the CACHE — carried on the manifest as base_edited/over_edited,
  // kept in step here as edits land — and NOT from the undo history below.
  //
  // The history is this page's memory, and a reload empties it. That is what
  // it cost: ten scenes padded by Update Frame Imbalance, the page reloaded
  // while something unrelated was being fixed, and every save icon came back
  // pristine over a cache still holding all ten. Save All then answered "no
  // scene has unsaved edits" and meant it, because it was asking the wrong
  // thing.
  //
  // A LOCKED track is left out. The tick is a deliberate "do not touch this
  // one", and a save is exactly the touch it is protecting against — but the
  // caller is told, so a lock can never quietly hold work back.
  function pendingOf(i) {
    const s = SEQ[i];
    if (!s) return [];
    return ['base', 'overlay'].filter(w =>
      slugOf(i, w) && !isLocked(s.n, w) && editedOf(i, w));
  }
  function editedOf(i, w) {
    const s = SEQ[i];
    return !!(s && (w === 'base' ? s.base_edited : s.over_edited));
  }
  function setEditedOf(i, w, on) {
    const s = SEQ[i];
    if (!s) return;
    if (w === 'base') s.base_edited = on; else s.over_edited = on;
  }
  // Locked tracks that DO have unsaved edits, so a save can name what it is
  // leaving behind instead of silently skipping it.
  function heldBackOf(i) {
    const s = SEQ[i];
    if (!s) return [];
    return ['base', 'overlay'].filter(w =>
      slugOf(i, w) && isLocked(s.n, w) && editedOf(i, w));
  }

  const HIST = {};                       // scene number -> [{base, overlay}, ...]
  const histOf = n => (HIST[n] = HIST[n] || []);

  // Fetched, not cached: a map is only wanted at the moment an edit is about
  // to happen, and holding one per clip for a 14-scene timeline would be a lot
  // of integers kept alive for scenes nobody touches.
  async function snapshot(i, layers) {
    const e = {};
    for (const w of layers) {
      const slug = slugOf(i, w);
      if (!slug) continue;
      try {
        const r = await fetch(`/api/frames/map?slug=${encodeURIComponent(slug)}`);
        const d = await r.json();
        if (d.frame_map) e[w] = d.frame_map;
      } catch (err) { /* a snapshot we could not take is one we do not offer */ }
    }
    return e;
  }
  // Every write to a cache marks that track as ahead of its file. Called
  // beside pushHist rather than inside each edit, for the same reason the lock
  // and the session log are taken in one place: one of them WILL be forgotten,
  // and the one forgotten is the edit that never gets saved.
  function markEdited(i, layers) {
    for (const w of layers) setEditedOf(i, w, true);
  }
  function pushHist(i, entry) {
    markEdited(i, Object.keys(entry || {}));
    if (!entry || (!entry.base && !entry.overlay)) return;
    histOf(SEQ[i].n).push(entry);
    renderScenes();
  }

  // ── undo ────────────────────────────────────────────────────────────────
  // One click, one step back, until the stack is empty and the scene matches
  // the file it was last saved to. Each entry names only the layers that
  // actually changed, so undoing a segment-only edit leaves the overlay alone.
  async function undoScene(n) {
    const i = SEQ.findIndex(s => s.n === n);
    const hist = histOf(n);
    if (i < 0 || !hist.length) return;
    stop();
    const entry = hist[hist.length - 1];
    status(`Undoing the last change to scene ${n}…`);
    const done = [];
    for (const [w, map] of Object.entries(entry)) {
      const slug = slugOf(i, w);
      if (!slug || !map) continue;
      let d;
      try {
        const r = await fetch('/api/frames/restore', { method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ slug, frame_map: map }) });
        d = await r.json();
      } catch (e) { status(`Undo failed on ${w}: ${e}`); return; }
      if (d.error) { status(`Undo failed on ${w} of scene ${n}: ${d.error}`); return; }
      if (w === 'base') SEQ[i].base_n = d.nb_frames; else SEQ[i].over_n = d.nb_frames;
      MARKS[slug] = new Set(d.marks || []);
      const row = ALL.find(x => x.n === n);
      if (row) {
        if (w === 'base') { row.frames = d.nb_frames; row.frames_exact = true; }
        else { row.overlay_frames = d.nb_frames; row.overlay_frames_exact = true; }
      }
      // Whether the clip is still edited AFTER the undo, from the server —
      // it is not derivable from the frame count, and a page that assumes
      // "still edited" leaves Save armed with nothing to save.
      if (d.edited !== undefined) setEditedOf(i, w, !!d.edited);
      done.push(`${w === 'base' ? 'segment' : 'overlay'} ${d.nb_frames}`);
    }
    // Popped only after every layer in the entry is back, or a half-applied
    // undo would leave the stack claiming work that was never reversed.
    hist.pop();
    ver++;
    reindex(); rebuildBar(); renderNote(); renderScenes();
    show(Math.min(total, starts[i] + 1));
    renderTicks(); renderReport();
    status(`Undid one change on scene ${n} — ${done.join(', ')}. `
         + `${hist.length} left. Timeline is ${(total / (SEQ[0].fps || 25)).toFixed(2)}s.`);
  }

  // ── save ────────────────────────────────────────────────────────────────
  // Writes the edited clip back over the file in sandbox/, archiving the
  // current one to z_History/ first, then empties this scene's history —
  // the file now IS the current state, so there is nothing to undo back to.
  // ONE refusal, used by BOTH save paths. There are two ways to save a single
  // The toolbar's Save is always Save scene. It briefly became "Save all
  // scenes" while a renumber lock was set; the lock is gone. A join reloads the
  // page, so every edit made after one was made under the NEW numbering —
  // saving a single scene on its own was never unsafe.
  // Save All's tip is written in the markup and does not change, so nothing
  // rewrites it here any more. This used to set a PER-SCENE wording on every
  // renumber-state load, which would now describe the wrong job.
  function paintSaveBtn() {}



  async function saveScene(n) {
    const i = SEQ.findIndex(s => s.n === n);
    if (i < 0) return;
    // WHICH TRACKS ARE BEHIND THEIR CACHE — asked of the cache, not of this
    // page's undo history. The history empties on a reload, and the edits do
    // not: a scene padded before a reload came back with a pristine icon and
    // this function returned without doing anything.
    const layers = pendingOf(i);
    if (!layers.length) return;
    const names = layers.map(w => w === 'base' ? 'segment' : 'overlay').join(' and ');
    if (!confirm(`Save scene ${n} (${SEQ[i].label})?

`
               + `WRITING TO
${ROOT_REL}/sandbox/`
               + `${String(n).padStart(2, '0')}-${SEQ[i].label}/

`
               + `Writes the ${names} over the current file. That file is `
               + `archived to this scene's own z_History/ first.

`
               + `A snapshot of the WHOLE sandbox is taken by "Save all scenes", `
               + `not by this.

`
               + `This scene's ${histOf(n).length} undo step(s) are cleared.`)) return;
    stop();
    const done = [], warn = [];
    for (const w of layers) {
      let d;
      const attempt = force => fetch('/api/save', { method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ slug: slugOf(i, w), force }) }).then(r => r.json());
      try {
        d = await attempt(false);
        // STALE: this file changed on disk since this page loaded it — most
        // likely another tab or Frame Blender already saved something here.
        // One extra confirm, then retry with force, rather than silently
        // overwriting whatever that other save just wrote.
        if (d.error === 'stale') {
          if (!confirm(`${d.message}

Overwrite it anyway?`)) {
            status(`Save stopped on ${w} of scene ${n} — ${d.message}`);
            return;
          }
          d = await attempt(true);
        }
      } catch (e) { status(`Save failed on ${w}: ${e}`); return; }
      if (d.error) { status(`Save failed on ${w} of scene ${n}: ${d.error}`); return; }
      done.push(`${w === 'base' ? 'segment' : 'overlay'} ${d.duration_s}s`);
      // The server counts the frames it actually wrote. Surface a mismatch
      // loudly: a save that quietly writes a different length than the one you
      // edited is the worst kind of wrong.
      if (d.warning) warn.push(`${w === 'base' ? 'segment' : 'overlay'}: ${d.warning}`);
      // This track's file now matches its cache.
      setEditedOf(i, w, false);
    }
    // Cleared only after EVERY layer wrote. A partial save that emptied the
    // history would strand the unwritten layer with no way back.
    histOf(n).length = 0;
    renderScenes();
    status(`Saved scene ${n} — ${done.join(', ')}. History cleared.`
         + (warn.length ? `
⚠ ${warn.join(' | ')}` : ''));
  }

  // ── the marked zone ─────────────────────────────────────────────────────
  // Marks divide a scene into zones. The zone is the one the playhead is
  // INSIDE: from the mark at or before it, to the next mark (or the scene's
  // end). With no marks the zone is the whole scene, which is why loop still
  // does something sensible before anything is marked.
  //
  // Returned in LOCAL frames, because every edit endpoint speaks local frames
  // and converting once here keeps that conversion in one place.
  function zoneOf(i, local) {
    const n = lenOf(i);
    const ms = [...(MARKS[slugOf(i)] || [])].sort((x, y) => x - y);
    let a = 1, b = n;
    for (const m of ms) {
      if (m <= local) a = m;
      else { b = m - 1; break; }
    }
    return { a, b: Math.max(a, Math.min(b, n)), marked: ms.length > 0 };
  }

  // ── row 3: edits ────────────────────────────────────────────────────────
  // One path for all four buttons. `span` decides frame vs zone, `kind`
  // decides add vs remove; the ticked layers decide what is touched, exactly
  // as the per-row +/- do. Sequential per layer: both writes touch the same
  // cache tree.
  // Ask the SERVER how long each layer of a scene really is, and correct the
  // page. The page keeps its own count and updates it after every edit — which
  // works until one edit fails, a cache is rebuilt, or two tabs touch the same
  // clip. Then it drifts silently and every later edit is aimed at the wrong
  // frame. Measured: the page said 478 where the cache held 476, so deleting
  // frame 477 clamped to the end and took the last frame instead.
  async function resync(i) {
    const fixed = [];
    for (const w of ['base', 'overlay']) {
      const slug = slugOf(i, w);
      if (!slug) continue;
      try {
        const r = await fetch(`/api/frames/map?slug=${encodeURIComponent(slug)}`);
        const d = await r.json();
        if (d.error || typeof d.nb_frames !== 'number') continue;
        const was = lenOf(i, w);
        if (was !== d.nb_frames) {
          if (w === 'base') SEQ[i].base_n = d.nb_frames; else SEQ[i].over_n = d.nb_frames;
          fixed.push(`${w === 'base' ? 'segment' : 'overlay'} ${was}→${d.nb_frames}`);
        }
      } catch (e) { /* keep the page's number; the next edit refuses loudly */ }
    }
    if (fixed.length) { reindex(); rebuildBar(); renderScenes(); }
    return fixed;
  }


  // ── copy and paste a frame ──────────────────────────────────────────────
  // CLIP holds a POSITION, not a picture: which scene, which frame, on which
  // tracks. Pasting re-inserts that very frame — the map records the same
  // source frame the original showed, so nothing is decoded, re-encoded or
  // guessed at. A trip out to the system clipboard and back would cost a PNG
  // round trip and leave the map describing a frame it no longer knows.
  let CLIP = null;

  function paintPaste() {
    const b = $('pasteFrame');
    if (!b) return;
    b.disabled = !CLIP;
    const tip = CLIP
      ? `Paste a copy of scene ${CLIP.n}'s frame ${CLIP.local} in after the `
        + `frame on screen, on the ticked tracks. Copied from `
        + `${CLIP.layers.map(w => w === 'base' ? 'segment' : 'overlay').join(' + ')}.`
      : 'Nothing copied yet — press Copy first.';
    b.dataset.tip = tip;
    b.title = tip;
  }

  // The picture, for pasting into something else on the Mac. Separate from the
  // internal copy on purpose: this one IS a picture, and is no use for putting
  // a frame back into a clip.
  async function toMacClipboard(i, local) {
    const s = SEQ[i];
    const url = `../${s.base_slug}/frames/frame_${pad(Math.min(local, s.base_n))}${s.base_ext}?v=${ver}`;
    try {
      const img = new Image();
      img.src = url;
      await img.decode();
      const c = document.createElement('canvas');
      c.width = img.naturalWidth; c.height = img.naturalHeight;
      c.getContext('2d').drawImage(img, 0, 0);
      // PNG because that is the only image type browsers reliably write to a
      // clipboard; the frame itself is untouched either way.
      const blob = await new Promise(r => c.toBlob(r, 'image/png'));
      await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
      return `${img.naturalWidth}×${img.naturalHeight}`;
    } catch (e) {
      return null;
    }
  }

  async function copyFrame(alsoMac) {
    const i = curI();
    if (i < 0 || !SEQ[i]) return;
    const n = SEQ[i].n;
    const layers = ['base', 'overlay'].filter(w => !isLocked(n, w) && slugOf(i, w));
    if (!layers.length) {
      status(`Scene ${n}: tick the segment or the overlay first — nothing to copy.`);
      return;
    }
    const { local } = at(+$('slider').value);
    CLIP = { i, n, local, layers, label: SEQ[i].label };
    paintPaste();
    let extra = '';
    if (alsoMac) {
      const size = await toMacClipboard(i, local);
      extra = size ? ` The picture is on the Mac clipboard too (${size}).`
                   : ' The Mac clipboard refused it — the browser only allows that '
                     + 'from a real click on a focused page.';
    }
    status(`Copied scene ${n} frame ${local} `
         + `(${layers.map(w => w === 'base' ? 'segment' : 'overlay').join(' + ')}).`
         + ` Move to where you want it and press Paste.${extra}`);
  }

  async function pasteFrame() {
    if (!CLIP) return;
    const i = curI();
    if (i < 0 || !SEQ[i]) return;
    const n = SEQ[i].n;
    if (i !== CLIP.i) {
      status(`The copied frame is from scene ${CLIP.n}, and the playhead is on `
           + `scene ${n}. A paste stays inside one scene — the two clips are `
           + `different files.`);
      return;
    }
    const layers = ['base', 'overlay'].filter(w => !isLocked(n, w) && slugOf(i, w)
                                                   && CLIP.layers.includes(w));
    if (!layers.length) {
      status(`Nothing to paste onto: the copy came from `
           + `${CLIP.layers.join(' + ')}, and those tracks are not ticked now.`);
      return;
    }
    stop();
    const fixed = await resync(i);
    if (fixed.length) {
      status(`Scene ${n}: this page was out of step with the clip `
           + `(${fixed.join(', ')}). Corrected — try the paste again.`);
      return;
    }
    const before = await snapshot(i, layers);
    const { local } = at(+$('slider').value);

    // CHECK EVERY TRACK BEFORE WRITING ANY. The two tracks are routinely
    // different lengths — 480 segment against 442 avatar is normal — so a frame
    // that exists in one can be past the end of the other. Writing them in turn
    // and stopping at the first error left the segment pasted and the avatar
    // refused: a half-done edit, reported as a failure. It happened four times
    // in a row, each adding a frame to one track only.
    const tooShort = layers.filter(w => local > lenOf(i, w) || CLIP.local > lenOf(i, w));
    if (tooShort.length) {
      const names = tooShort.map(w => w === 'base' ? 'segment' : 'overlay');
      alert(`Frame ${local} is past the end of the `
          + `${names.join(' and ')} on scene ${n}.

`
          + layers.map(w => `  ${w === 'base' ? 'segment' : 'overlay'}: `
                          + `${lenOf(i, w)} frames`).join('\n')
          + `

Nothing was pasted. The two tracks are different lengths, so a `
          + `frame that exists in one can be past the end of the other — untick `
          + `the shorter track, or move to a frame both of them have.`);
      return;
    }

    const done = [];
    for (const w of layers) {
      try {
        const r = await fetch('/api/frames/paste', { method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ slug: slugOf(i, w),
                                 from: CLIP.local, at: local }) });
        const d = await r.json();
        if (d.error) {
          // Past the pre-flight and still refused: something changed under us.
          // Say what DID happen, because a track already written is not nothing.
          alert(`Paste failed on the ${w === 'base' ? 'segment' : 'overlay'}: ${d.error}

`
              + (done.length ? `The ${done.join(', ')} was already written. Use Undo `
                             + `to take it back.` : 'Nothing was written.'));
          if (done.length) pushHist(i, before);
          reindex(); rebuildBar(); renderScenes();
          return;
        }
        if (w === 'base') SEQ[i].base_n = d.nb_frames; else SEQ[i].over_n = d.nb_frames;
        done.push(`${w === 'base' ? 'segment' : 'overlay'} ${d.nb_frames}`);
      } catch (e) { status(`Paste failed: ${e}`); return; }
    }
    pushHist(i, before);
    ver++;
    reindex(); rebuildBar(); renderScenes();
    const g = starts[i] + Math.min(local + 1, lenOf(i, 'base'));
    $('slider').value = g; show(g);
    status(`Pasted scene ${CLIP.n}'s frame ${CLIP.local} after frame ${local} — `
         + `${done.join(', ')}. Timeline is ${(total / (SEQ[0].fps || 25)).toFixed(2)}s.`);
  }

  async function doEdit(kind, span) {
    const i = curI();
    if (i < 0 || !SEQ[i]) return;
    const n = SEQ[i].n;
    const layers = ['base', 'overlay'].filter(w => !isLocked(n, w) && slugOf(i, w));
    if (!layers.length) {
      status(`Scene ${n}: tick the segment or the overlay first — nothing to act on.`);
      return;
    }
    stop();
    // Straighten the page's counts BEFORE aiming an edit at a frame number.
    const fixed = await resync(i);
    if (fixed.length) {
      status(`Scene ${n}: this page was out of step with the clip `
           + `(${fixed.join(', ')}). Corrected — try that edit again.`);
      return;
    }
    // Snapshot BEFORE the write, and of exactly the layers about to change.
    const before = await snapshot(i, layers);
    const { local } = at(+$('slider').value);
    // CHECK EVERY TICKED TRACK BEFORE WRITING ANY. The two are routinely
    // different lengths — 480 segment against 442 avatar is normal — so the
    // frame on screen can exist in one and be past the end of the other. This
    // loop used to `continue` past a refusal, which changed the tracks that
    // worked and skipped the rest: a half-done edit that reads as an error.
    if (!span) {
      const short = layers.filter(w => local > lenOf(i, w));
      if (short.length) {
        alert(`Frame ${local} is past the end of the `
            + `${short.map(w => w === 'base' ? 'segment' : 'overlay').join(' and ')} `
            + `on scene ${n}.

`
            + layers.map(w => `  ${w === 'base' ? 'segment' : 'overlay'}: `
                            + `${lenOf(i, w)} frames`).join('\n')
            + `

Nothing was changed. Untick the shorter track, or move to a `
            + `frame both of them have.`);
        return;
      }
    }

    // ONE zone, decided BEFORE anything is written. Editing the first layer
    // shifts its marks, so recomputing the zone for the second layer read the
    // ALREADY-MOVED marks and gave a different, larger span: a 35-frame zone
    // grew the segment by 35 and the overlay by 70. The zone the user is
    // looking at is the zone both layers get.
    const zone = span ? zoneOf(i, local) : null;
    const changed = [];
    for (const w of layers) {
      const len = lenOf(i, w);
      let path, body;
      if (span) {
        const z = zone;
        path = kind === 'dup' ? '/api/frames/dup-span' : '/api/frames/del-span';
        body = { slug: slugOf(i, w), a: Math.min(z.a, len), b: Math.min(z.b, len) };
      // NOTE: neither branch clamps with lenOf(). That clamp read this page's
      // OWN idea of the length, and when it had drifted below the cache's real
      // one — 478 here against 476 there — every frame past its number silently
      // became the LAST frame, so deleting frame 477 took one off the END
      // instead of the frame on screen. The server validates a span against the
      // real length and refuses outside it, so sending the frame unclamped
      // turns a drift into a visible refusal instead of a wrong deletion.
      } else if (kind === 'dup') {
        // Insert the copy immediately AFTER the frame on screen, so the new
        // frame is the one the playhead lands on below.
        path = '/api/frames/dup';
        body = { slug: slugOf(i, w), at: local, count: 1, side: 'right' };
      } else {
        // Delete the frame ON SCREEN. The single-frame endpoint deletes to one
        // SIDE of the current frame and so could never remove the frame you are
        // looking at; a one-frame span is exactly that frame.
        path = '/api/frames/del-span';
        body = { slug: slugOf(i, w), a: local, b: local };
      }
      let d;
      try {
        const r = await fetch(path, { method: 'POST',
          headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        d = await r.json();
      } catch (e) { status(`Error on ${w}: ${e}`); continue; }
      if (d.error) { status(`Error on ${w} of scene ${n}: ${d.error}`); continue; }
      if (!span && kind === 'del' && d.actual === 0) continue;
      if (w === 'base') SEQ[i].base_n = d.nb_frames; else SEQ[i].over_n = d.nb_frames;
      MARKS[slugOf(i, w)] = new Set(d.marks || []);
      const row = ALL.find(x => x.n === n);
      if (row) {
        if (w === 'base') { row.frames = d.nb_frames; row.frames_exact = true; }
        else { row.overlay_frames = d.nb_frames; row.overlay_frames_exact = true; }
      }
      changed.push(`${w === 'base' ? 'segment' : 'overlay'} ${d.nb_frames}`);
    }
    if (!changed.length) { status('Nothing changed.'); return; }
    // Only record layers that actually moved: a failed or no-op layer must not
    // leave an undo step that would put a different layer back.
    pushHist(i, Object.fromEntries(
      Object.entries(before).filter(([w]) => changed.some(c => c.startsWith(w === 'base' ? 'segment' : 'overlay')))));
    ver++;
    const start = starts[i];
    reindex(); rebuildBar(); renderNote(); renderScenes();
    // Where the playhead lands, in scene-local frames:
    //   add     -> local + 1, the copy just made, so you see what you added
    //   delete  -> local, which is now the NEXT frame shifted into that slot,
    //              so the timeline appears to move on rather than back
    //   zone    -> local, clamped, since the span it was in may be gone
    const after = lenOf(i);
    let landing = (!span && kind === 'dup') ? local + 1 : local;
    landing = Math.max(1, Math.min(landing, after));
    show(Math.min(total, start + landing));
    renderTicks(); renderReport();
    status(`${kind === 'dup' ? 'Added' : 'Removed'} ${span ? 'the marked zone' : '1 frame'} `
         + `on scene ${n} — ${changed.join(', ')}. `
         + `Timeline is ${(total / (SEQ[0].fps || 25)).toFixed(2)}s.`);
  }

  // ── row 4: what is selected ─────────────────────────────────────────────
  // Reports the two ticks, the frame or span on EACH track, and how long the
  // selection runs. The two tracks are different lengths, so one number could
  // not stand for both.
  // Row 4 is a FIXED GRID, not a sentence. It used to be flowing text that
  // wrapped to one or two lines depending on how wide the numbers happened to
  // be, so the row changed height as you scrubbed and shoved the whole control
  // block up and down. Now every cell has a fixed width, the row has a fixed
  // height, and nothing here can move anything else.
  //
  // Numbers are right-aligned tabular figures for the same reason: 9 and 88
  // and 461 have to occupy the same space or the columns dance.
  // ONE element per cell. Emitting the label and the value as two siblings
  // made each of them its own grid item, so a two-column grid laid the four
  // cells out as four ROWS of label/value and the fixed height clipped half of
  // it away.
  function repCell(label, value, cls) {
    return `<span class="rc"><span class="rk">${label}</span>`
         + `<span class="rv ${cls || ''}">${value}</span></span>`;
  }
  function renderReport() {
    const i = curI();
    const g = $('rep');
    if (i < 0 || !SEQ[i]) {
      g.innerHTML = repCell('scene', '—') + repCell('segment', '—')
                  + repCell('selection', '—') + repCell('overlay', '—');
      return;
    }
    const s = SEQ[i], fps = s.fps || 25;
    const { local } = at(+$('slider').value);
    const z = zoneOf(i, Math.min(local, lenOf(i)));
    const zoneLen = z.b - z.a + 1;

    const track = w => {
      const len = lenOf(i, w), slug = slugOf(i, w);
      if (!slug) return `<i class="off">no ${w === 'base' ? 'segment' : 'overlay'}</i>`;
      if (isLocked(s.n, w)) return `<i class="off">unticked</i>`;
      const f = Math.min(local, len);
      const a = Math.min(z.a, len), b = Math.min(z.b, len);
      return `<b>${f}</b>/${len}<span class="sep">zone</span>`
           + `<b>${a}–${b}</b> (${b - a + 1}f)`;
    };

    // The grid fills left-to-right, so this ORDER is the layout. SEGMENT and
    // OVERLAY now sit in the same column, one above the other, because the
    // thing you read them for is comparing the two frame counts — 483 over 439
    // is a glance; 483 beside a duration and 439 under a scene name is not.
    g.innerHTML =
        repCell('scene', `<b>${s.n}</b> <span class="nm">${s.label || ''}</span>`)
      + repCell('segment', track('base'), 'seg')
      + repCell('selection', `<b>${(zoneLen / fps).toFixed(2)}s</b>`
                           + `<span class="sep">timeline</span>`
                           + `<b>${(total / fps).toFixed(2)}s</b>`)
      + repCell('overlay', track('overlay'), 'ovl');
  }

  $('copyFrame').onclick = ev => copyFrame(ev.shiftKey);
  $('pasteFrame').onclick = () => pasteFrame();
  $('addFrame').onclick = () => doEdit('dup', false);
  $('delFrame').onclick = () => doEdit('del', false);
  $('addZone').onclick  = () => doEdit('dup', true);
  $('delZone').onclick  = () => doEdit('del', true);

  // The per-row + / - is the SAME operation as row 3's + / - Frame, so it is
  // the same code. Two paths for one action drift apart, and one of them then
  // deletes a different frame than the other.
  async function rowEdit(n, kind) {
    const i = SEQ.findIndex(s => s.n === n);
    if (i < 0 || i !== curI()) return;
    return doEdit(kind, false);
  }


  // ── Save Timeline / Save all ────────────────────────────────────────────
  // Renamed and moved to row 4 2026-08-29 (was Save Scenes / Save All, in
  // row 3). Same saveScenes() function, called with different reach —
  // Save Timeline is video only, Save all also covers dirty narrative lines.
  // See saveScenes()'s own comment for why the unconditional job moved out
  // to Backup Scenes instead of staying a third mode of this call.
  $('saveTimelineBtn').onclick = () => saveScenes(false);
  $('saveAllBtn').onclick = () => saveScenes(true);

  // ── audio ────────────────────────────────────────────────────────────
  // ONE element, re-pointed at each boundary. Two alternating elements would
  // hide the first-play load stall, but every clip is a few seconds of AAC and
  // the browser caches it after one pass, so the second loop is already
  // seamless — the extra element was buying almost nothing.
  const aud = $('audA');
  function audioFor(i) {
    const s = SEQ[i];
    // Sarah's voice rides on the AVATAR clip. The footage is normally silent,
    // so falling through to it gives silence rather than the wrong voice.
    if (s.over_audio) return `../${s.over_slug}/audio.m4a`;
    if (s.base_audio) return `../${s.base_slug}/audio.m4a`;
    return null;
  }
  // ── VTT ─────────────────────────────────────────────────────────────────
  // Video Timing Table, not WebVTT. Per scene: how long the footage runs, how
  // long the line takes to say, and the gap between them.
  //
  // The clip length comes from the TIMELINE, not from the file on disk, so it
  // moves as frames are added or cut. vtt.py reads the file, which is right for
  // a report and wrong here -- a gap that does not budge while you edit frames
  // is a lie with a decimal point on it.
  let VTT = null;                       // {wps, scenes:[...]} from the server
  const vLine = {};                   // n -> the text currently in the box
  const vDirty = new Set();             // n -> edited but not written yet

  const clipS = i => lenOf(i, 'base') / (SEQ[i].fps || 25);
  const wordsOf = t => t.split(/\s+/).filter(w => /[A-Za-z0-9]/.test(w)).length;
  function speechS(n, text) {
    const r = VTT && VTT.byN[n];
    if (!r) return null;
    return wordsOf(text) / VTT.wps + (r.pause || 0);
  }

  async function loadVtt() {
    try {
      const res = await fetch(`/api/vtt?root=${encodeURIComponent(ROOT_REL)}`);
      const d = await res.json();
      if (d.error) return;
      d.byN = {};
      for (const r of d.scenes) d.byN[r.n] = r;
      VTT = d;
    } catch (e) { return; }
    renderVtt();
    paintVtt();
  }

  function renderVtt() {
    const box = $('vttRows');
    box.innerHTML = '';
    if (!VTT) return;
    SEQ.forEach((sc, i) => {
      const r = VTT.byN[sc.n];
      const row = document.createElement('div');
      row.className = 'vt';
      row.dataset.i = i;
      if (vLine[sc.n] === undefined) vLine[sc.n] = r ? r.line : '';
      // A bookend (00-opening, 99-closing) is on the timeline but is not a
      // script scene, so it has no line to edit. Shown anyway, greyed: a table
      // that silently skips rows does not match what is playing.
      row.innerHTML =
        `<span class="vn">${sc.n}</span>` +
        `<span class="vl"></span>` +
        `<span class="vt3"></span>` +
        (r ? '' : `<span class="vtodo">not a script scene — no line</span>`);
      if (r) {
        const ta = document.createElement('textarea');
        ta.rows = 2;
        ta.value = vLine[sc.n];
        ta.dataset.n = sc.n;
        ta.title = 'The line for this scene. Editing it here writes '
                 + 'script.json, which is what HeyGen is paid to say. '
                 + 'Saved when you click away; Esc puts it back.';
        ta.addEventListener('input', () => {
          vLine[sc.n] = ta.value;
          vDirty.add(sc.n);
          row.classList.add('dirty');
          paintVttRow(row, i);           // the gap moves as you type
          paintVttSum();
        });
        ta.addEventListener('keydown', ev => {
          if (ev.key === 'Escape') {
            ta.value = VTT.byN[sc.n].line; ta.dispatchEvent(new Event('input'));
            vDirty.delete(sc.n); row.classList.remove('dirty'); ta.blur();
          }
          if (ev.key === 'Enter' && (ev.metaKey || ev.ctrlKey)) ta.blur();
        });
        ta.addEventListener('blur', () => {
          // Closing the box hands the row back to the highlighter.
          row.classList.remove('editing');
          saveLine(sc.n);
        });
        row.appendChild(ta);
      }
      row.addEventListener('click', () => {
        if (+$('slider').value < 1) return;
        const g = starts[i] + 1;
        if (at(+$('slider').value).i !== i) { $('slider').value = g; show(g); }
        const ta = row.querySelector('textarea');
        // Shown BEFORE focusing: a display:none element cannot take focus, so
        // focusing first would silently do nothing and the box would stay shut.
        if (ta) { row.classList.add('editing'); ta.focus(); }
      });
      box.appendChild(row);
      paintVttRow(row, i);
    });
    paintVttSum();
  }

  function paintVttRow(row, i) {
    const sc = SEQ[i], r = VTT && VTT.byN[sc.n];
    const c = clipS(i);
    const lab = row.querySelector('.vl');
    const txt = vLine[sc.n] || '';
    // Per-WORD spans, so the one being spoken can be picked out. Escaped by
    // hand rather than trusted: this is the store's own narration copy, and an
    // ampersand or an angle bracket in it is ordinary text, not markup.
    if (r && txt) {
      lab.innerHTML = txt.split(/\s+/).filter(Boolean).map(w =>
        `<span class="w">${w.replace(/&/g, '&amp;').replace(/</g, '&lt;')
                            .replace(/>/g, '&gt;')}</span>`).join(' ');
    } else {
      lab.textContent = r ? '— no line yet —' : sc.label;
    }
    lab.title = txt;
    const cell = row.querySelector('.vt3');
    if (!r) { cell.textContent = `${c.toFixed(1)}s`; return; }
    const sp = speechS(sc.n, txt), gap = c - sp;
    // Negative is the defect that ships silently: the line is still being said
    // when the footage has already moved on.
    const cls = gap < 0 ? 'gapNeg' : (gap > 2.5 ? 'gapBad' : 'gapOk');
    cell.innerHTML = `${c.toFixed(1)}s clip &middot; ${sp.toFixed(1)}s said &middot; `
                   + `<span class="${cls}">${gap >= 0 ? '' : '−'}${Math.abs(gap).toFixed(1)}s gap</span>`;
  }

  function paintVttSum() {
    if (!VTT) return;
    let c = 0, sp = 0, bad = 0, neg = 0;
    SEQ.forEach((sc, i) => {
      c += clipS(i);
      const r = VTT.byN[sc.n];
      if (!r) return;
      const t = speechS(sc.n, vLine[sc.n] || '');
      sp += t;
      const g = clipS(i) - t;
      if (g < 0) neg++; else if (g > 2.5) bad++;
    });
    const dead = c > 0 ? Math.round((c - sp) / c * 100) : 0;
    $('vttSum').textContent =
      `${c.toFixed(1)}s clip · ${sp.toFixed(1)}s said · ${dead}% dead air`
      + (neg ? ` · ${neg} overrun` : '') + (bad ? ` · ${bad} over 2.5s` : '')
      + (vDirty.size ? ` · ${vDirty.size} unsaved` : '');
  }

  // The row for whatever is on screen, opened for editing and scrolled to.
  // The row the playhead is inside, held in the MIDDLE of the panel, with the
  // scenes ahead of it coming down from the top and the ones behind leaving out
  // the bottom.
  //
  // Centred by setting scrollTop outright rather than with scrollIntoView.
  // `block:'nearest'` scrolls the least it can get away with, so a row that was
  // already just-visible never moved and one that was not jumped to the edge:
  // the list twitched at every boundary and never settled anywhere you could
  // read ahead from.
  // WHICH WORD IS BEING SAID.
  //
  // The words are spread across the RUNS OF SPEECH, not across the scene and
  // not across one outer span. Both of those were tried and both drifted:
  //
  //   From frame 1 at the voice's average rate — seconds ahead. Sarah settles
  //   into shot before she talks, and on ski-demo's opening that is 1.64s of
  //   nothing while the highlight was already a third of the way down.
  //
  //   Evenly across first-word-to-last-word — ahead, then waiting, then ahead
  //   again. She pauses between sentences and speaks faster in between. That
  //   opening is 13.88s of talking inside a 19.28s scene: five and a half
  //   seconds of silence that an even spread hands words to.
  //
  // So each run gets a share of the line in proportion to how long it lasts,
  // and inside a run the words are even. Through a pause the highlight HOLDS
  // on the last word said, which is what she is doing.
  //
  // Still an approximation inside a run: there are no per-word timings
  // anywhere in this pipeline and HeyGen returns none, so a long word and a
  // short one get the same slice. It is an aid for lining the picture up
  // against the line, not a measurement — nothing that writes a file reads it.
  function paintSpokenWord(row, i) {
    if (!row || !VTT) return;
    const words = row.querySelectorAll('.vl .w');
    if (!words.length) return;
    const s = SEQ[i], W = words.length;
    const t = (at(+$('slider').value).local - 1) / (s.fps || 25);
    const runs = s.speech_runs || [];
    let k = -1;

    if (runs.length) {
      const D = runs.reduce((sum, r) => sum + (r[1] - r[0]), 0);
      if (D > 0 && t < runs[0][0]) {
        // She has not started. Nothing is lit — that is the honest picture,
        // and it is also the clearest way to see how long the lead-in is.
        k = -1;
      } else if (D > 0) {
        let acc = 0;
        for (const r of runs) {
          const share = ((r[1] - r[0]) / D) * W;
          // Between sentences: HOLD where the last run ended.
          //
          // `acc` here is the shares of every run already passed, and the last
          // word of that run was floor(acc + share) — which is floor(acc)
          // exactly. Holding anything else moves the highlight while she is
          // silent. This said `floor(acc) - 1`, so at every pause the tracer
          // stepped BACK a word and then forward again when she resumed.
          if (t < r[0]) { k = Math.floor(acc); break; }
          if (t <= r[1]) { k = Math.floor(acc + ((t - r[0]) / (r[1] - r[0])) * share); break; }
          acc += share;
        }
        // Past the last run: she has finished, so the line ends lit on its
        // last word rather than going dark while the footage plays on.
        if (k === -1) k = W - 1;
        k = Math.max(0, Math.min(W - 1, k));
      }
    } else {
      // No measurement for this clip — a scene with no avatar, or one whose
      // audio could not be read. Fall back to the voice's average rate from
      // the scene's own start, and say nothing more confident than that.
      k = Math.max(-1, Math.min(W - 1, Math.floor(t * VTT.wps)));
    }

    for (let j = 0; j < W; j++) words[j].classList.toggle('wnow', j === k);
  }

  let vttCentred = -1;
  function centreVtt(row) {
    const box = $('vttRows');
    if (!box || !row) return;
    box.scrollTop = row.offsetTop + row.offsetHeight / 2 - box.clientHeight / 2;
  }

  function paintVtt() {
    const rows = [...document.querySelectorAll('#vttRows .vt')];
    if (!rows.length) return;
    const cur = at(+$('slider').value).i;
    rows.forEach(row => {
      const on = +row.dataset.i === cur;
      if (on === row.classList.contains('on')) return;
      // Leaving a scene closes its editor. Blur alone was not enough to save it:
      // the box is hidden by the same class change, and a hidden field that
      // never fired blur takes the edit with it. Written here instead, where the
      // decision to leave is actually made.
      if (!on && row.classList.contains('dirty')) saveLine(SEQ[+row.dataset.i].n);
      row.classList.toggle('on', on);
    });
    // AFTER the classes are set, so the open row has its real height — and only
    // when the scene actually changed. Re-centring every frame would fight the
    // scrollbar while someone is reading, and would pull the panel out from
    // under a line being typed.
    const active = rows.find(r => +r.dataset.i === cur);
    if (cur !== vttCentred) {
      vttCentred = cur;
      centreVtt(active);
      // The row just left goes back to plain text. A word left lit on a scene
      // that is no longer playing points at nothing.
      rows.forEach(r => r.querySelectorAll('.vl .wnow')
                         .forEach(w => w.classList.remove('wnow')));
    }
    // Every frame, not only at a boundary: this is the thing that moves. Not
    // while the box is open — the highlight lives in the label, which is
    // hidden then, and there is nothing to light.
    if (active && !active.classList.contains('editing')) paintSpokenWord(active, cur);
  }

  // Closing the tab with an edit still in the box. fetch() with keepalive
  // survives the page going away; a normal one is cancelled mid-flight.
  window.addEventListener('beforeunload', () => {
    for (const n of vDirty) {
      navigator.sendBeacon('/api/line', new Blob(
        [JSON.stringify({ root: ROOT_REL, n, line: vLine[n] })],
        { type: 'application/json' }));
    }
  });

  async function saveLine(n) {
    if (!vDirty.has(n)) return;
    const text = vLine[n];
    try {
      const res = await fetch('/api/line', { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ root: ROOT_REL, n, line: text }) });
      const d = await res.json();
      if (d.error) { status(`Line ${n} not saved: ${d.error}`); return; }
      VTT.byN[n].line = d.line;
      VTT.byN[n].words = d.words;
      vLine[n] = d.line;
      vDirty.delete(n);
      const row = [...document.querySelectorAll('#vttRows .vt')]
        .find(x => SEQ[+x.dataset.i].n === n);
      if (row) {
        row.classList.remove('dirty');
        const ta = row.querySelector('textarea');
        if (ta && ta.value !== d.line) ta.value = d.line;   // whitespace tidied
      }
      paintVttSum();
      if (!d.unchanged) status(`Scene ${n}'s line saved to script.json.`);
    } catch (e) { status(`Line ${n} not saved: ${e}`); }
  }

  function onSceneChange(i, local) {
    // The lock applies to the scene under the PLAYHEAD, so crossing a boundary
    // can hand you a locked scene or take you off one. Re-gate on every change,
    // or the buttons keep describing the scene you just left.
    refreshEditGate();
    const src = audioFor(i);
    if (!src) { aud.pause(); aud.removeAttribute('src'); return; }
    if (aud.dataset.key !== src) { aud.dataset.key = src; aud.src = src; }
    aud.currentTime = Math.max(0, (local - 1) / (SEQ[i].fps || 25));
    // One element re-pointed per scene, so the rate is set again at every
    // boundary — assigning a new src resets playbackRate to 1, and the sound
    // would race the picture from the next scene on.
    if (RATE < AUDIO_RATE_FLOOR) { aud.pause(); }
    else {
      aud.playbackRate = RATE;
      if (playing) aud.play().catch(() => {});
    }
  }

  // ── playback ──────────────────────────────────────────────────────────
  let playing = false, timer = null, t0 = 0, g0 = 1;
  // 2x skims; the slow rates are for judging a seam -- the join between two
  // scenes, or the moment the avatar's mouth meets the audio. At 25fps a seam
  // lands in 40ms; 0.125x stretches it to 320ms. PLAYBACK ONLY.
  //
  // Browsers refuse audio outside roughly 0.25x..4x. Below the floor the track
  // is PAUSED rather than left to drift: a stopped clock is caught by the tick,
  // a wrong one is not.
  let RATE = 1;
  const AUDIO_RATE_FLOOR = 0.25;
  // Loop bounds in GLOBAL frames: the marked zone of the scene the playhead
  // was in when play started. Computed once per loop pass rather than per tick,
  // and only while looping — an unmarked scene gives the whole scene, and with
  // loop off the run is the whole timeline as before.
  function loopBounds() {
    if (!$('loopChk').checked) return { lo: 1, hi: total };
    const i = at(g0).i;
    if (i < 0 || !SEQ[i]) return { lo: 1, hi: total };
    const z = zoneOf(i, at(g0).local);
    const start = starts[i];
    return { lo: start + z.a, hi: Math.min(total, start + z.b) };
  }
  function tick() {
    if (!playing) return;
    const fps = SEQ[at(+$('slider').value).i].fps || 25;
    let g = g0 + Math.floor((performance.now() - t0) / 1000 * fps * RATE);
    const { lo, hi } = loopBounds();
    if (g > hi) {
      if ($('loopChk').checked) {
        t0 = performance.now(); g0 = lo; g = lo;
        // Take the SOUND back too. show() only re-points the audio when the
        // SCENE changes, and a loop inside one scene never changes it -- so the
        // narration carried on past the zone and was finished and silent after
        // one pass while the picture kept looping. That is what "the loop does
        // not work" sounds like even when every frame is right.
        const p = at(lo);
        if (aud.dataset.key) {
          aud.currentTime = Math.max(0, (p.local - 1) / (SEQ[p.i].fps || 25));
          if (aud.paused && RATE >= AUDIO_RATE_FLOOR) aud.play().catch(() => {});
        }
      }
      else { stop(); show(total); return; }
    }
    show(g);
    if (g % 20 === 0) preload(g + 1);
  }
  function preload(from) {
    for (let k = from; k < from + 40 && k <= total; k++) {
      const { i, local } = at(k); const s = SEQ[i];
      new Image().src = `../${s.base_slug}/frames/frame_${pad(Math.min(local, s.base_n))}${s.base_ext}?v=${ver}`;
      if (s.over_slug)
        new Image().src = `../${s.over_slug}/frames/frame_${pad(Math.min(local, s.over_n))}${s.over_ext}?v=${ver}`;
    }
  }
  function play() {
    playing = true; g0 = (+$('slider').value >= total) ? 1 : +$('slider').value;
    t0 = performance.now(); $('playBtn').innerHTML = '&#10074;&#10074; Pause';
    $('playBtn').classList.add('on'); preload(g0);
    // Put the sound where the PICTURE is before starting it. onSceneChange
    // only re-points the audio when the scene changes, so scrubbing WITHIN a
    // scene left the track wherever it had got to — press Play after dragging
    // back and the voice ran seconds ahead of the frame. The layered view has
    // always done this; the timeline never did.
    {
      const { i, local } = at(g0);
      if (aud.dataset.key) aud.currentTime = Math.max(0, (local - 1) / (SEQ[i].fps || 25));
    }
    if (RATE >= AUDIO_RATE_FLOOR) {
      aud.playbackRate = RATE;
      if (aud.dataset.key) aud.play().catch(() => {});
    } else { aud.pause(); }
    timer = setInterval(tick, 12);
  }
  function stop() {
    playing = false; if (timer) clearInterval(timer); timer = null;
    aud.pause();
    $('playBtn').innerHTML = '&#9654; Play'; $('playBtn').classList.remove('on');
  }
  $('playBtn').onclick = () => playing ? stop() : play();
  $('rateSel').onchange = () => {
    RATE = parseFloat($('rateSel').value);
    $('rateSel').classList.toggle('off1', RATE !== 1);
    $('status').textContent = RATE < AUDIO_RATE_FLOOR ? `Audio is off below ${AUDIO_RATE_FLOOR}x - the browser will not play a track that slow. The picture is still exact.` : '';
    if (RATE < AUDIO_RATE_FLOOR) aud.pause();
    else { aud.playbackRate = RATE; if (playing && aud.dataset.key) aud.play().catch(() => {}); }
    if (!playing) return;
    g0 = +$('slider').value;
    t0 = performance.now();
  };
  $('muteBtn').onclick = () => {
    aud.muted = !aud.muted;
    $('muteBtn').innerHTML = aud.muted ? '&#128263;' : '&#128266;';
  };
  // `which` still exists, because marks, Cut and Save each act on ONE layer.
  // It is now read off the ticks instead of a button: the single ticked layer
  // wins, and when both are ticked the SEGMENT is the target -- the confirms on
  // Cut and Save name it out loud, so it is never a silent choice.
  function syncWhich() {
    const i = curI();
    if (i < 0 || !SEQ[i]) return;
    const n = SEQ[i].n;
    const b = !isLocked(n, 'base')    && slugOf(i, 'base');
    const o = !isLocked(n, 'overlay') && slugOf(i, 'overlay');
    const next = b ? 'base' : (o ? 'overlay' : 'base');
    // paint() unconditionally: going from both-ticked to segment-only does not
    // change `which` (base still wins) but it DOES change the border, so a
    // repaint gated on `which` would miss exactly that case.
    paint();
    if (next === which) return;
    which = next;
    renderTicks();
  }

  const jump = d => { stop(); show(+$('slider').value + d); };
  $('p1').onclick = () => jump(-1);
  $('n1').onclick = () => jump(1);
  $('p10').onclick = () => jump(-10);
  $('n10').onclick = () => jump(10);
  $('prevScene').onclick = () => { stop(); const { i } = at(+$('slider').value); show(starts[Math.max(0, i - 1)] + 1); };
  $('nextScene').onclick = () => { stop(); const { i } = at(+$('slider').value); show(starts[Math.min(SEQ.length - 1, i + 1)] + 1); };
  $('slider').addEventListener('mousedown', stop);
  $('slider').oninput = () => show(+$('slider').value);


  document.addEventListener('keydown', e => {
    // A textarea is open whenever the VTT row under the pointer is, so every
    // one of these letters is a letter someone means to type. Space was the
    // loud one: it played the timeline instead of putting a space in the line.
    const t = e.target;
    if (t && (t.tagName === 'TEXTAREA' || t.tagName === 'INPUT'
              || t.isContentEditable) && t.type !== 'range') return;
    if (e.key === ' ') { $('playBtn').click(); e.preventDefault(); }
    if (e.key === 'ArrowLeft')  { e.altKey ? jumpMark(-1) : jump(e.shiftKey ? -10 : -1); e.preventDefault(); }
    if (e.key === 'ArrowRight') { e.altKey ? jumpMark(1)  : jump(e.shiftKey ?  10 :  1); e.preventDefault(); }
    if (e.key === 'm' || e.key === 'M') { $('markBtn').click(); e.preventDefault(); }
    if (e.key === 's' || e.key === 'S') { $('soloBtn').click(); e.preventDefault(); }
    if (e.key === '[') { $('prevScene').click(); e.preventDefault(); }
    if (e.key === ']') { $('nextScene').click(); e.preventDefault(); }
  });

  // ── the list: EVERY scene, the ticked ones active ─────────────────────
  // Listing only what was on the timeline made every other scene LOOK deleted,
  // and left no way back to them without going out to the single-scene view.
  // The list is the store's full set; the ticks say which are on the timeline.
  const ON = new Set(SEQ.map(s => s.n));
  let ALL = null;

  async function loadScenes() {
    try {
      const r = await fetch(`/api/siblings?path=${encodeURIComponent(SEQ[0].base_rel)}`);
      const j = await r.json();
      if (j.error) throw new Error(j.error);
      ALL = j.by_version[String(j.current_version ?? 0)] || [];
    } catch (e) {
      // The list is a convenience; the timeline plays without it. Falling back
      // to SEQ keeps the panel honest rather than blank — it simply cannot
      // offer the scenes that are OFF the timeline.
      ALL = SEQ.map(s => ({ n: s.n, label: s.label, missing: false,
                            dur: +(s.base_n / (s.fps || 25)).toFixed(2) }));
      status('scene list unavailable — ' + e.message);
    }
    renderScenes();
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
    syncWhich();
    const n = currentSceneN();
    // Gate against the layer that is LIT, because that is the one every edit
    // acts on. Locking the segment must not stop you retiming the avatar.
    const blocked = n != null && isLocked(n, which);
    // The row buttons are enabled only on the scene under the playhead, and
    // only when that row has at least one layer ticked.
    for (const b of document.querySelectorAll('.rowbtn')) {
      const rn = +b.dataset.n;
      const isCur = rn === n;
      const any = !isLocked(rn, 'base') || !isLocked(rn, 'overlay');
      b.disabled = !isCur || !any;
      b.title = !isCur
          ? `Scene ${rn} is not under the pointer. Only the scene the pointer is inside can be`
            + ` edited, because that is the only one with a current frame — click this row's name to go there.`
        : !any
          ? `Tick this row's segment or overlay box first. Those ticks choose which track an edit touches,`
            + ` and with neither ticked there is nothing to act on.`
        : (b.dataset.kind === 'dup'
            ? `Duplicate the frame on screen, on scene ${rn}'s ticked track(s). Same as + Frame below.`
            : `Delete the frame on screen, from scene ${rn}'s ticked track(s). Same as - Frame below.`);
    }
    // Save Scenes and Save All are NOT in this list. The gate is about the
    // track under the pointer being locked, and those two act on every scene on
    // the timeline — greying out the only way to save, because of one scene the
    // pointer happens to be sitting in, would be a trap.
    for (const id of ['addFrame', 'delFrame', 'addZone', 'delZone',
                      'addL', 'addR', 'delL', 'delR']) {
      const el = $(id);
      if (el) {
        el.disabled = blocked;
        // Keep the control's OWN tip and add the reason on top of it, rather
        // than replacing it. This used to assign '' when not blocked, which
        // silently erased the help text written into the markup — the six
        // controls listed here were the six on the page with an empty title.
        if (el.dataset.tip === undefined) el.dataset.tip = el.getAttribute('title') || '';
        el.title = blocked
          ? `Unavailable: the ${which === 'base' ? 'segment' : 'overlay'} of scene ${n} is locked.`
            + ` Tick that track's box in the list to edit it.`
            + (el.dataset.tip ? `

${el.dataset.tip}` : '')
          : el.dataset.tip;
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

  const currentSceneN = () => (SEQ[curI()] || {}).n ?? null;

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
    body.style.cssText = 'display:flex;gap:8px;align-items:baseline;flex:1 1 0;min-width:0;overflow:hidden';
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
    for (let k = 0; k < 2; k++) {
      const x = document.createElement('span');
      x.className = 'cbpad btn';   // stands in for a +/- so the totals still line up
      d.appendChild(x);
    }
    $('sceneList').appendChild(d);
  }

  function renderScenes() {
    $('sceneList').innerHTML = '';
    for (const it of ALL) {
      const on = ON.has(it.n);
      const d = document.createElement('div');
      d.className = 'scene' + (on ? ' inseq' : ' offseq');
      d.dataset.n = it.n;

      const cb = document.createElement('input');
      cb.type = 'checkbox'; cb.className = 'pick'; cb.dataset.n = it.n;
      cb.checked = on; cb.disabled = !!it.missing;
      // Its own tip: without one it inherits the ROW's, which on a scene
      // already on the timeline reads "jump to this scene" — the wrong control.
      cb.title = it.missing
        ? `Scene ${it.n} has no footage, so it cannot go on the timeline.`
        : `Put scene ${it.n} on the timeline, or take it off. Ticking does not rebuild by`
          + ` itself — press Rebuild underneath once the set is the one you want.`;
      cb.onclick = ev => { ev.stopPropagation(); updatePick(); };
      d.appendChild(cb);

      const body = document.createElement('span');
      body.style.cssText = 'display:flex;gap:8px;align-items:baseline;flex:1 1 0;min-width:0;overflow:hidden';
      body.innerHTML = `<span class="num">${it.n}</span>` +
        `<span class="lab">${it.label || it.n}</span>` +
        (it.missing ? `<span class="ovv" style="color:#e05555;border-color:#7a3a3a">missing</span>` : '') +
        `<span class="dur">${it.dur ?? '?'}s</span>`;
      // Only a scene ON the timeline has anywhere to jump to. For the rest the
      // checkbox is the whole interaction, so the name is not dressed up as
      // clickable when clicking it can do nothing.
      if (on) {
        const i = SEQ.findIndex(s => s.n === it.n);
        body.style.cursor = 'pointer';
        body.onclick = () => { stop(); show(starts[i] + 1); };
        d.title = `${it.n} ${it.label || ''} — jump to this scene`;
      } else {
        d.title = `${it.n} ${it.label || ''} — tick to put it on the timeline`;
      }
      d.appendChild(body);
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
          ? `Include this scene's ${layer === 'base' ? 'SEGMENT (the footage)' : 'OVERLAY (the avatar)'}`
            + ` in edits. Untick it to protect this track while you work on the other one —`
            + ` + / - Frame, + / - Zone, Cut and Save all skip an unticked track.`
          : `This scene has no ${layer === 'base' ? 'segment' : 'overlay'}, so there is nothing to edit.`;
        cb.onclick = ev => {
          ev.stopPropagation();
          if (cb.checked) LOCKED.delete(lockKey(it.n, layer));
          else LOCKED.add(lockKey(it.n, layer));
          paintLockState();
          refreshEditGate();
          renderReport();
        };
        d.appendChild(cb);

        const fr = document.createElement('span');
        fr.className = 'frames' + (layer === 'overlay' ? ' ov' : '') + (exact ? '' : ' est');
        fr.dataset.n = it.n; fr.dataset.layer = layer;
        fr.textContent = count == null ? '—' : (exact ? String(count) : '~' + count);
        fr.title = count == null
          ? `No ${layer === 'base' ? 'segment' : 'overlay'} on this scene, so there is nothing to count.`
          : (exact
              ? `${count} frames in this scene's ${layer === 'base' ? 'segment' : 'overlay'}, counted frame by frame.`
                + ` The two tracks are separate files and drift apart as you edit — Update Frame Imbalance evens them up.`
              : `About ${count} frames, read from the file header without extracting it.`
                + ` It can be out by one until the scene has been opened.`);
        d.appendChild(fr);
      };
      addPair('base', it.frames, it.frames_exact, !it.missing);
      addPair('overlay', it.overlay_frames, it.overlay_frames_exact, !!it.overlay);

      // +/- act on whichever layers THIS ROW has ticked. The ticks already say
      // what may be edited, so they choose the target too rather than a
      // separate control saying it a second way.
      for (const [kind, glyph, cls] of [['dup', '+', 'plus'], ['del', '−', 'minus']]) {
        const b = document.createElement('button');
        b.className = `rowbtn ${cls}`;
        b.dataset.n = it.n; b.dataset.kind = kind;
        b.textContent = glyph;
        b.onclick = ev => { ev.stopPropagation(); rowEdit(it.n, kind); };
        d.appendChild(b);
      }
      // Undo and Save for THIS scene. Both are lit only while the scene has
      // unsaved changes -- the same condition, because a save is what empties
      // the history and an undo is what walks back through it.
      // Two different questions, and they were the same one until it cost ten
      // scenes. UNDO walks this page's own snapshots, so it needs the history.
      // SAVE asks whether the FILE is behind its cache — which survives a
      // reload, and is the only honest answer.
      const hist = histOf(it.n);
      const iSeq = SEQ.findIndex(x => x.n === it.n);
      const needsSave = iSeq >= 0 && pendingOf(iSeq).length > 0;
      for (const [act, glyph, cls, tip] of [
            ['undo', '↶', 'undo', 'Undo the last change to this scene'],
            ['save', '⤓', 'save', 'Save this scene to sandbox and clear its history']]) {
        const hb = document.createElement('button');
        hb.className = `histbtn ${cls}`;
        hb.dataset.n = it.n; hb.dataset.act = act;
        hb.textContent = glyph;
        // Save is also unavailable while the set is mid-renumber — the refusal
        // is explained on click, but a live-looking button that always refuses
        // is worse than one that shows it cannot act.
        // One thing decides both icons: does THIS scene have unsaved changes.
        // Nothing about any other scene, and nothing about a renumber. A join
        // reloads the page, so every edit made after one was made under the new
        // numbering — saving a single scene was never unsafe, and the lock that
        // used to sit here only got in the way.
        hb.disabled = act === 'undo' ? hist.length === 0 : !needsSave;
        // Dirty the moment this scene has an unsaved change; pristine again
        // when it is saved OR when every change has been undone — both end with
        // an empty history, which is the one thing that decides it.
        hb.classList.toggle('dirty', act === 'save' && needsSave);
        hb.title = hist.length === 0
          ? `Scene ${it.n} has no unsaved changes, so there is nothing to ${act}.`
            + ` These two light up as soon as you edit this scene.`
          : `${tip}. ${hist.length} change${hist.length === 1 ? '' : 's'} pending on scene ${it.n};`
            + ` undo walks back one per click, and save clears them all.`;
        hb.onclick = ev => { ev.stopPropagation(); act === 'undo' ? undoScene(it.n) : saveScene(it.n); };
        d.appendChild(hb);
      }

      $('sceneList').appendChild(d);
    }
    renderTotals(ALL);
    paintLockState();
    refreshEditGate();
    updatePick();
    paintBar();
  }

  // Rebuilding is a NAVIGATION, not a live edit: a different set of scenes is a
  // different timeline with different frame numbers, and pretending otherwise
  // would leave the slider pointing at a frame that no longer exists.
  const picked = () => [...document.querySelectorAll('.pick')]
    .filter(c => c.checked).map(c => +c.dataset.n).sort((a, b) => a - b);
  function updatePick() {
    const ns = picked();
    const same = ns.length === ON.size && ns.every(n => ON.has(n));
    $('rebuildBtn').disabled = same || ns.length === 0;
    balanceReport();
    $('rebuildBtn').innerHTML = ns.length === 0
      ? 'Tick at least one scene'
      : same ? `&#10003; These ${ns.length} are on the timeline`
             : `&#8635; Rebuild with ${ns.length} scene${ns.length === 1 ? '' : 's'}`;
  }
  $('rebuildBtn').onclick = () => {
    const ns = picked();
    if (!ns.length) return;
    status(`Rebuilding with ${ns.length} scene(s)…`);
    location.href = `/api/open-seq-go?root=${encodeURIComponent(ROOT_REL)}&ns=${ns.join(',')}`;
  };

  // A function, not a one-off: `total` is only known after reindex(), and an
  // edit changes it. Written once at load it read "0.0s" — a number that looked
  // like a measurement and was really just the order the lines ran in.
  // The note this wrote is gone from the page. Kept as a no-op rather than
  // chased through its three callers, all of which fire after a length change.
  function renderNote() {}

  reindex(); rebuildBar(); paint(); renderNote(); loadScenes(); show(1);
  paintPaste();
  loadRenumberState();
  loadVtt();
  renderReport();   // row 4 must say something before the first click
})();
