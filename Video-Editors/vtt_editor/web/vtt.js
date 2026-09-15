/*
  VTT EDITOR — the page's behaviour.

  ⚠ THE SERVER OWNS THE TRUTH, THIS PAGE OWNS THE VIEW.
  Every number on screen came from /api/state, which reads it off disk on every
  request. Nothing is remembered here between refreshes, so a table cannot offer
  a job that no longer makes sense — the exact failure that had a Stretch button
  pointing at screens a previous stretch had already fixed.

  ⚠ NO confirm(). The two-click arm instead.
  Carried over from the artifact page, where a sandboxed frame blocked confirm()
  and it returned FALSE SILENTLY — no dialog, no error, a completely dead
  button. This page is not sandboxed, so confirm() would work here; the arm is
  kept anyway because it is better: it names what is about to happen, in the
  button, with the real numbers.
*/
'use strict';

const $ = (id) => document.getElementById(id);
const esc = (t) => String(t).replace(/[&<>"]/g,
  (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

let FOLDER = '';
let STATE = null;
let RINGS = { header: null, rings: [] };
let SEL = 1;                       // the selected scene, the page's one anchor

// ── the one status line ────────────────────────────────────────────────────
function say(text, cls) {
  const el = $('status');
  el.textContent = text || '';
  el.className = 'status' + (cls ? ' ' + cls : '');
}

async function api(path, opts) {
  const r = await fetch(path, opts);
  const d = await r.json().catch(() => ({ ok: false, err: 'bad JSON from the server' }));
  if (!r.ok && d.err === undefined) d.err = `HTTP ${r.status}`;
  return d;
}

// ── beats: a {0.3} marker is silence, never a word ─────────────────────────
// Same rule as pause_marks.py and as the server's own copy. Counting a marker
// both ways pays for the same pause twice.
const BEAT = /\{\s*(\d*\.?\d+)\s*\}/g;
const beats = (t) => {
  let s = 0, m; BEAT.lastIndex = 0;
  while ((m = BEAT.exec(t)) !== null) s += parseFloat(m[1]);
  return Math.round(s * 1000) / 1000;
};
const bare = (t) => t.replace(BEAT, ' ').replace(/\s{2,}/g, ' ').trim();
const wordsIn = (t) => (bare(t) ? bare(t).split(/\s+/).length : 0);

// ── the five job rows ──────────────────────────────────────────────────────
/*
  Each row renders from the server's own numbers, and each decides its own
  class: ok (done), owed (there is work), stuck (it cannot run and says why).
  ⚠ A ROW THAT CANNOT ACT IS DISABLED WITH ITS REASON VISIBLE. Never hidden —
  a missing row reads as a missing feature, and a live row that does nothing is
  worse than both.
*/
function jobRow(j) {
  const wps = 3.44;
  let state = '', why = j.blocked || '', action = null, cls = 'owed';

  if (j.job === 'rings') {
    cls = 'rings';
    state = j.n
      ? `${j.n} rings · ${j.clicks} click, ${j.typing} typing · ${j.fill}`
      : 'no log';
    if (j.trimmed) why = `log rebased by −${j.trimmed}s for the lead-in trim`;
    action = j.n ? { label: `Show ${j.n} on the frame`, id: 'rings' } : null;
    if (!j.n) cls = 'stuck';
  }

  if (j.job === 'segments') {
    state = `${j.n} of ${j.of} scenes cut`
      + (j.files > j.n ? ` · ${j.files} cached cuts` : '');
    cls = j.n >= j.of && j.of ? 'ok' : (j.blocked ? 'stuck' : 'owed');
  }

  if (j.job === 'scenes') {
    state = `${j.n} of ${j.of} in sandbox/`;
    cls = j.of && j.n >= j.of ? 'ok' : (j.blocked ? 'stuck' : 'owed');
    if (!j.blocked && j.n < j.of) {
      action = { label: j.n ? 'Re-promote' : 'Promote to sandbox/', id: 'promote' };
    } else if (!j.blocked) {
      action = { label: 'Re-promote', id: 'promote' };
    }
  }

  if (j.job === 'narrative') {
    state = `${j.n} lines · ${j.words} words · `
      + (j.short ? `${j.short} screen${j.short === 1 ? '' : 's'} too short`
                 : 'every screen fits');
    cls = j.blocked ? 'stuck' : (j.short ? 'owed' : 'ok');
    if (j.short) {
      why = j.short_rows
        .map((r) => `${r.label} +${r.short_by.toFixed(1)}s`).join(', ');
    }
  }

  if (j.job === 'voice') {
    state = (j.seconds ? `${j.seconds.toFixed(2)}s` : 'not built')
      + (j.rushed ? ` · ${j.rushed} rushed` : j.seconds ? ' · nothing rushed' : '');
    cls = j.blocked ? 'stuck' : (j.stale || !j.seconds ? 'owed' : 'ok');
    if (j.rushed && !why) {
      why = j.rushed_rows.map((r) => `${r.label} ${r.rate} wpm`).join(', ');
    }
    if (j.stale && !why) why = 'the words are newer than the soundtrack';
    if (!j.blocked) {
      // ⚠ HEAVY. It stretches and re-narrates: minutes, and a new file.
      action = { label: j.seconds ? 'Rebuild' : 'Build', id: 'voice', heavy: true };
    }
  }

  const btn = action
    ? `<button data-act="${action.id}"${action.heavy ? ' class="heavy"' : ''}>`
      + `<span class="spin"></span><span class="lbl">${esc(action.label)}</span></button>`
    : (j.blocked
        ? '<button disabled>unavailable</button>'
        : '');

  return `<li class="job ${cls}">
    <div class="jname">${esc(j.job)}</div>
    <div class="jstate">${esc(state)}</div>
    ${why ? `<div class="jwhy">${esc(why)}</div>` : ''}
    ${btn}
  </li>`;
}

// ── the scene strip and the table ──────────────────────────────────────────
/*
  ⚠ THE DWELL COMES FROM THE SCRIPT, AND IT IS AT BOTH ENDS.
  0.5 in and 0.8 out were hardcoded here — two numbers in the page that the
  script also carried, so raising the dwell would have moved the table and left
  the audio alone. Carson set it to 0.75 both ways on 2026-09-15; the server
  sends `lead` once and each scene's own `exit`, and narrate_mac.py reads the
  same field, so the table and the soundtrack cannot disagree.

  ⚠ FRAMES ARE DERIVED FROM THE MEASURED fps, NOT FROM 25.
  one-day-rental is 30fps and special-skis is 25. A fixed 25 is the same bug
  that put stretch_scenes' candidate edges past the end of a 66-second file.
*/
function calc(sc) {
  const w = wordsIn(sc.line);
  const b = beats(sc.line);
  const speech = Math.round((w / 3.44) * 10) / 10;
  const fps = (STATE && STATE.fps) || 25;
  const frames = Math.round((sc.clip || 0) * fps);
  // ⚠ A SILENT SCENE IS AS LONG AS ITS FOOTAGE, NOT AS LONG AS ITS WORDS, and
  // it carries NO dwell at either end — a close-out on nothing would be counted
  // as room the voice never uses. Costed the ordinary way, special-skis scene 18
  // came out at 1.3s against 156.2s of picture and reported 154.9s of dead air.
  if (!w) {
    return { w: 0, b: 0, speech: 0, lead: 0, exit: 0, frames,
             scene: sc.clip, gap: 0, silent: true };
  }
  const lead = (STATE && typeof STATE.lead === 'number') ? STATE.lead : 0.75;
  const exit = (typeof sc.exit === 'number' && sc.exit) ? sc.exit : lead;
  const scene = Math.round((lead + speech + b + exit) * 10) / 10;
  let gap = Math.round((sc.clip - scene) * 10) / 10;
  if (gap === 0) gap = 0;                   // clears a "-0.0"
  return { w, b, speech, lead, exit, frames, scene, gap, silent: false };
}

function render() {
  if (!STATE) return;
  // ⚠ NEVER REBUILD THE TABLE WHILE A LINE IS BEING TYPED INTO.
  // render() replaces the whole tbody, caret and all. A job finishing mid-edit
  // would have thrown the words away — and it is exactly when a long job ends
  // that a refresh fires. The rail and the header still update; only the rows
  // wait, and the next save's own refresh brings them in step.
  const live = document.activeElement;
  const editing = live && live.classList && live.classList.contains('linebox');

  const rows = STATE.scenes.map((sc) => ({ sc, ...calc(sc) }));

  $('jobs').innerHTML = STATE.jobs.map(jobRow).join('');
  $('headmeta').innerHTML =
    `<span>${esc(STATE.store)}</span>`
    + `<span><b>${esc(STATE.recipe)}</b></span>`
    + (STATE.footage ? `<span>${STATE.footage.toFixed(1)}s</span>` : '')
    + `<span>${STATE.scenes.length} scenes</span>`
    + `<span>${(STATE.lead ?? 0.75).toFixed(2)}s dwell</span>`
    + `<span>${STATE.fps ? (+STATE.fps).toFixed(0) : '?'} fps</span>`;

  $('strip').innerHTML = rows.map((r) => {
    const cls = [r.gap < 0 ? 'short' : '', r.silent ? 'silent' : ''].filter(Boolean).join(' ');
    return `<button role="tab" class="${cls}" data-n="${r.sc.n}"
              aria-selected="${r.sc.n === SEL}">
      <span class="sn">${String(r.sc.n).padStart(2, '0')}</span>
      <span class="sl">${esc(r.sc.label)}</span>
    </button>`;
  }).join('');

  if (editing) { paintSelection(); drawRings(); return; }

  $('tbody').innerHTML = rows.map((r) => `
    <tr class="${r.sc.n === SEL ? 'sel' : ''}" data-n="${r.sc.n}">
      <td class="n">${r.sc.n}</td>
      <td class="lab">${esc(r.sc.label)}</td>
      <td>${r.sc.clip.toFixed(1)}s</td>
      <td class="${r.silent ? 'dim' : ''}">${r.lead.toFixed(2)}s</td>
      <td class="${r.silent ? 'dim' : ''}">${r.speech.toFixed(1)}s</td>
      <td class="${r.b ? '' : 'dim'}">${r.b.toFixed(1)}s</td>
      <td class="${r.silent ? 'dim' : ''}">${r.exit.toFixed(2)}s</td>
      <td>${r.scene.toFixed(1)}s</td>
      <td class="${r.gap < 0 ? 'gapbad' : 'dim'}">${r.gap >= 0 ? '+' : ''}${r.gap.toFixed(1)}s</td>
      <td class="dim">${r.frames.toLocaleString()}</td>
      <td class="line l"><div class="linebox${r.silent ? ' empty' : ''}"
        contenteditable="true" spellcheck="true" data-n="${r.sc.n}"
        data-ph="Silent on purpose — type to give it a line"
        >${esc(r.sc.line)}</div></td>
    </tr>`).join('');

  wireLines();
  drawRings();
}

// ── editing a line ────────────────────────────────────────────────────────
/*
  ⚠ SAVED ON BLUR, ONE SCENE AT A TIME, AND THE CELL SAYS WHICH STATE IT IS IN.
  An editor that saves everything on one button loses an edit the moment the
  page reloads; one that saves silently gives no way to tell a written line from
  a lost one. The border carries it: accent while saving, green when saved, red
  when refused.

  ⚠ AN EMPTIED LINE IS A REAL EDIT. A guard of the shape `if (next && changed)`
  refuses a cleared line, so a scene can be given words and never handed back to
  silence. Both directions go through.
*/
let lineTimer = null;

function wireLines() {
  document.querySelectorAll('.linebox').forEach((el) => {
    el.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter') { ev.preventDefault(); el.blur(); saveLine(el); }
      if (ev.key === 'Escape') { render(); }
    });
    el.addEventListener('focus', () => { SEL = Number(el.dataset.n); paintSelection(); });
    // ⚠ SAVED ON INPUT (DEBOUNCED) AS WELL AS ON BLUR, AND NOT ONLY ON BLUR.
    // Two reasons, one found by testing and one worse:
    //   1. `blur` did not fire at all when the page was driven from a browser
    //      pane that lacked window focus — the edit sat in the DOM, unsaved,
    //      with no error. An interaction whose ONLY trigger can be suppressed
    //      is an interaction that silently loses work.
    //   2. A finished job calls refresh(), which re-renders the table. Anything
    //      half-typed went with it. A debounce means the words are already on
    //      disk before that can happen.
    el.addEventListener('input', () => {
      clearTimeout(lineTimer);
      lineTimer = setTimeout(() => saveLine(el), 900);
    });
    el.addEventListener('blur', () => saveLine(el));
  });
}

/*
  One scene's words to disk. Safe to call repeatedly — it returns immediately
  when nothing changed, so the debounce and the blur cannot double-save.
*/
async function saveLine(el) {
  {
      clearTimeout(lineTimer);
      const n = Number(el.dataset.n);
      const sc = STATE && STATE.scenes.find((x) => x.n === n);
      const next = el.innerText.replace(/\s+/g, ' ').trim();
      if (!sc || next === sc.line) return;
      sc.line = next;                      // claim it, so a second call is a no-op

      el.classList.remove('saved', 'failed');
      el.classList.add('saving');
      say(`saving scene ${n}…`, 'work');
      const d = await api('/api/save_line', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder: FOLDER, n, line: next }),
      });
      el.classList.remove('saving');
      if (!d.ok) {
        el.classList.add('failed');
        say(`scene ${n} NOT saved: ${d.err || 'unknown'}`, 'bad');
        return;
      }
      el.classList.add('saved');
      // The verify step runs vtt_build, which REFUSES on a mismatch. Report it
      // rather than swallowing it — that drift is what the tool exists to stop.
      const v = d.verify;
      if (v && !v.ok) {
        say(`scene ${n} saved, but the .vtt does not agree — ${(v.err || '').trim().slice(0, 120)}`, 'bad');
      } else {
        say(`scene ${n} saved · both files agree`, 'ok');
      }
      await refresh();                 // the numbers moved; re-read them
  }
}

function paintSelection() {
  document.querySelectorAll('.strip button').forEach((b) => {
    b.setAttribute('aria-selected', String(Number(b.dataset.n) === SEL));
  });
  document.querySelectorAll('#tbody tr').forEach((tr) => {
    tr.classList.toggle('sel', Number(tr.dataset.n) === SEL);
  });
}

// ── the frame, and the rings over it ──────────────────────────────────────
/*
  ⚠ THE FRAME IS ASKED FOR BY TIME, AND THE SERVER CACHES IT.
  Scrubbing asks for the same frames repeatedly and each one is an ffmpeg seek
  into a gigabyte. The cache is on the server side, so this page just asks.
*/
/*
  ⚠ THE SERVER'S `start` IS THE TRUTH. Summing the clips before a scene was
  wrong by exactly the dead lead-in — this capture opens on 2.43s of blank
  browser, so Play began 2.43s early and showed the end of the PREVIOUS screen.
  Found 2026-09-15 by pressing Play on scene 8 and landing at 25.14s when the
  scene starts at 27.57s. Falling back to the sum only when a folder has no
  report at all, and that case has no edges anyway.
*/
function sceneStart(n) {
  const sc = STATE.scenes.find((x) => x.n === n);
  if (sc && typeof sc.start === 'number') return sc.start;
  let t = 0;
  for (const s of STATE.scenes) {
    if (s.n === n) break;
    t += s.clip || 0;
  }
  return Math.round(t * 100) / 100;
}

let frameAt = -1;
let loadedFolder = '';
let SRC = 'raw';                    // 'raw' or 'narrated' — see the note below
let stopAt = null;                  // where the current scene ends, while playing

/*
  ⚠ ONE <video>, SEEKED — NOT A NEW REQUEST PER FRAME.
  The frame endpoint is still there and still useful from the command line, but
  the page uses the real file: the server answers byte ranges, so a seek costs
  one small request instead of an ffmpeg pass, and the same element can play.
  `src` is set ONCE per capture — resetting it on every seek restarts the
  download and makes scrubbing crawl.
*/
function showFrame(t) {
  if (!FOLDER || !STATE || !STATE.capture) return;
  const v = $('vid');
  const key = FOLDER + '|' + SRC;
  if (loadedFolder !== key) {
    loadedFolder = key;
    v.src = `/api/video?folder=${encodeURIComponent(FOLDER)}&src=${SRC}`;
    v.onloadeddata = () => { $('framewrap').classList.add('has-frame'); drawRings(); };
    v.onerror = () => { $('framewrap').classList.remove('has-frame'); };
  }
  t = Math.max(0, Math.round(t * 100) / 100);
  frameAt = t;
  $('scrubat').textContent = t.toFixed(2) + 's';
  $('scrub').value = String(t);
  try { v.currentTime = t; } catch (_) { /* not seekable yet; loadeddata retries */ }
  drawRings();
}

/*
  ⚠ PLAY RUNS THE SELECTED SCENE AND STOPS AT ITS END.
  Carson, 2026-09-15: "I need a play button to run the scenes." The scene is the
  unit being judged — whether its line fits, whether the ring lands, whether the
  screen holds long enough — so running past its end just makes you find the
  boundary again by hand. `all` plays on to the end of the capture for the times
  you want the join between two scenes.
*/
function sceneEnd(n) {
  const sc = STATE.scenes.find((x) => x.n === n);
  return Math.round((sceneStart(n) + (sc ? sc.clip : 0)) * 100) / 100;
}

function setPlayIcon(playing) {
  const b = $('play');
  b.textContent = playing ? '❚❚' : '▶';
  b.classList.toggle('playing', playing);
  b.setAttribute('aria-label', playing ? 'pause' : 'play this scene');
}

function playScene(toEnd) {
  const v = $('vid');
  if (!v.src) return;
  if (!v.paused) { v.pause(); return; }          // the same button pauses
  const from = sceneStart(SEL);
  stopAt = toEnd ? null : sceneEnd(SEL);
  // Restart the scene when the head is already past its end, so a second press
  // replays rather than doing nothing.
  if (stopAt !== null && (v.currentTime < from - 0.05 || v.currentTime >= stopAt - 0.05)) {
    try { v.currentTime = from; } catch (_) {}
  }
  v.play().then(() => setPlayIcon(true)).catch((e) => {
    say('could not play: ' + e.message, 'bad');
  });
}

/*
  ⚠ A LOGGED RECT IS IN CSS PIXELS OF THE PAGE, NOT PIXELS OF THE VIDEO.
  The capture is a cropped window region on a scaled monitor, so the two are
  different coordinate systems. The log's header carries the window region and
  the chrome crop, and the transform happens HERE, where the rendered frame's
  own size is also known. Multiplying by a guessed ratio is how a ring ends up
  near the right place and never on it.

  Drawn only for rings whose time is within half a second of the frame on
  screen, because a ring is a moment, not a property of the scene.
*/
function drawRings() {
  const ov = $('overlay');
  if (!ov) return;
  ov.innerHTML = '';
  const h = RINGS.header;
  if (!h || !RINGS.rings.length || frameAt < 0) return;
  const win = h.window || {};
  if (!win.width || !win.height) return;

  const near = RINGS.rings.filter((r) => typeof r.t === 'number'
    && Math.abs(r.t - frameAt) <= 0.5);
  const crop = Number(h.chrome_crop_top || 0);
  for (const r of near) {
    if (typeof r.x !== 'number') continue;
    // page px -> the captured region: the window's own top-left is the origin,
    // and the chrome the recorder cropped off comes out of the y.
    const left = (r.x / win.width) * 100;
    const top = ((r.y + crop) / win.height) * 100;
    const w = (r.w / win.width) * 100;
    const hh = (r.h / win.height) * 100;
    const box = document.createElement('div');
    box.className = 'ringbox';
    box.style.left = left + '%';
    box.style.top = top + '%';
    box.style.width = w + '%';
    box.style.height = hh + '%';
    ov.appendChild(box);
  }
}

// ── the long jobs: arm, then commit ───────────────────────────────────────
let armed = null, armTimer = null;

function disarm() {
  document.querySelectorAll('.job button').forEach((b) => {
    b.classList.remove('armed');
    const lbl = b.querySelector('.lbl');
    if (lbl && b.dataset.idle) lbl.textContent = b.dataset.idle;
  });
  armed = null;
  clearTimeout(armTimer);
}

const PROMPTS = {
  promote: () => 'copies every cached scene into sandbox/. Click again to go ahead.',
  voice: () => 'stretches the short screens and re-narrates — minutes, and a new '
    + 'file beside the master. Click again to go ahead.',
};

async function onJobClick(btn) {
  const act = btn.dataset.act;

  if (act === 'rings') {
    RINGS = await api(`/api/rings?folder=${encodeURIComponent(FOLDER)}`);
    say(RINGS.rings && RINGS.rings.length
      ? `${RINGS.rings.length} rings loaded — they appear on the frame at their own moment`
      : (RINGS.why || 'no rings'), RINGS.rings && RINGS.rings.length ? 'ok' : 'bad');
    drawRings();
    return;
  }

  if (armed !== act) {
    disarm();
    armed = act;
    btn.dataset.idle = btn.dataset.idle || btn.querySelector('.lbl').textContent;
    btn.classList.add('armed');
    btn.querySelector('.lbl').textContent = 'Click again';
    say(PROMPTS[act] ? PROMPTS[act]() : 'click again to go ahead', 'work');
    armTimer = setTimeout(() => { disarm(); say(''); }, 6000);
    return;
  }

  disarm();
  // ⚠ EVERY JOB BUTTON LOCKS WHILE ONE RUNS. They write the same folder, so two
  // at once is two ffmpeg passes over one output.
  const all = [...document.querySelectorAll('.job button')];
  all.forEach((b) => { b.disabled = true; });
  btn.classList.add('busy');
  btn.querySelector('.lbl').textContent = act === 'voice' ? 'Building' : 'Working';
  say(act === 'voice' ? 'stretching and re-narrating — this takes minutes…'
                      : 'promoting the scenes…', 'work');

  const d = await api(act === 'voice' ? '/api/voice' : '/api/promote', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ folder: FOLDER }),
  });

  btn.classList.remove('busy');
  all.forEach((b) => { b.disabled = false; });

  if (!d.ok) {
    say(`${act} failed: ${(d.err || d.out || 'unknown').trim().slice(0, 200)}`, 'bad');
  } else if (act === 'promote') {
    say(`promoted ${d.promoted.length} scene(s) into sandbox/`, 'ok');
  } else {
    // stretch_request prints its own summary; show its last meaningful line.
    const line = (d.out || '').trim().split('\n').filter(Boolean).slice(-6)
      .find((l) => /WATCH|narration|encoded|nothing to do/.test(l)) || 'done';
    say(`${line.trim()}  (${d.seconds}s)`, 'ok');
  }
  await refresh();
}

// ── loading ───────────────────────────────────────────────────────────────
async function refresh() {
  if (!FOLDER) return;
  const d = await api(`/api/state?folder=${encodeURIComponent(FOLDER)}`);
  if (!d.ok) { say(d.err || 'could not read that folder', 'bad'); return; }
  STATE = d.state;

  // ⚠ THE WRONG TOOL, SAID PLAINLY. A BUILT video's lengths live in its
  // sandbox clips, not in its script, so this editor would show 11 scenes of
  // 0.0s — indistinguishable from a bug. The Segment and Avatar Editor owns
  // that stage, and build/vtt_html.py draws its table.
  if (STATE.kind === 'built') {
    $('jobs').innerHTML = '';
    $('strip').innerHTML = '';
    $('tbody').innerHTML = '';
    $('framewrap').classList.remove('has-frame');
    $('silentbadge').hidden = true;
    $('headmeta').innerHTML = `<span>${esc(STATE.store)}</span>`
      + `<span><b>${esc(STATE.recipe)}</b></span><span>built video</span>`;
    $('railnote').textContent = 'this is a BUILT video — vtt_editor covers raw '
      + 'captures. Open it in the Segment and Avatar Editor, or draw its table '
      + 'with build/vtt_html.py.';
    say(`${STATE.recipe} is a BUILT video — its scene lengths come from its `
      + 'sandbox clips, not its script. Use the Segment and Avatar Editor.', 'bad');
    return;
  }

  if (!STATE.scenes.some((s) => s.n === SEL)) SEL = STATE.scenes.length ? STATE.scenes[0].n : 1;
  const span = STATE.footage || STATE.scenes.reduce((a, s) => a + (s.clip || 0), 0);
  $('scrub').max = String(Math.max(1, Math.round(span)));
  render();
  RINGS = await api(`/api/rings?folder=${encodeURIComponent(FOLDER)}`);
  // ⚠ DEFAULT TO THE CUT YOU CAN HEAR. If a narrated file exists it is almost
  // always the one worth watching, and defaulting to the silent raw is how
  // "there is no sound" becomes the first thing anyone says.
  if (STATE.narrated && SRC === 'raw') { SRC = 'narrated'; loadedFolder = ''; }
  if (!STATE.narrated && SRC === 'narrated') { SRC = 'raw'; loadedFolder = ''; }
  showFrame(sceneStart(SEL));
  paintSource();
  // A message from a previous folder is not about this one.
  if ($('status').classList.contains('bad')) say('');
}

/*
  ⚠ FOUR DROPDOWNS THAT NARROW EACH OTHER, LEFT TO RIGHT.
  Carson, 2026-09-15: "add some breadcrumb filters… Dropdown to select a biz…
  a store from that biz… a help-video folder from that store… a working folder
  from the help-video folder."

  The whole tree arrives once from /api/tree and the narrowing happens here, so
  changing a business does not cost four round trips. Selection is remembered by
  NAME rather than index — rebuilding a list and keeping index 0 is how a picker
  silently jumps to a different store.

  ⚠ A FOLDER WITH NO SCRIPT IS STILL LISTED, marked "· no script". Hiding them
  made three of the four stores look empty, because their only scripted folder
  is a BUILT video whose script sits in sandbox/. Seeing it and being told why
  beats not seeing it at all.
*/
let TREE = [];
const CRUMB = { biz: '', store: '', stage: '', work: '' };

function opt(value, label, cls) {
  const o = document.createElement('option');
  o.value = value;
  o.textContent = label;
  if (cls) o.className = cls;
  return o;
}

/*
  ⚠ WHEN A SELECTION IS RESET, PREFER SOMETHING THAT ACTUALLY OPENS.
  `items[0]` looked like the obvious default and was wrong: every store's first
  stage alphabetically is `development/`, which is EMPTY in all four of them. So
  switching business landed on "nothing to open here" and the editor read as
  broken. Each list can name a preferred value — the first stage that holds a
  script, the first folder that has one — and falls back to items[0] only when
  nothing qualifies.
*/
function fill(sel, items, chosen, preferred) {
  sel.innerHTML = '';
  for (const it of items) sel.appendChild(opt(it.value, it.label, it.cls));
  sel.disabled = items.length === 0;
  if (!items.length) { sel.appendChild(opt('', '—')); return ''; }
  let keep = items.some((i) => i.value === chosen) ? chosen : '';
  if (!keep && preferred && items.some((i) => i.value === preferred)) keep = preferred;
  if (!keep) keep = items[0].value;
  sel.value = keep;
  return keep;
}

const scripted = (folders) => folders.filter((f) => f.has_script);

function bizNode()   { return TREE.find((b) => b.name === CRUMB.biz); }
function storeNode() { const b = bizNode(); return b && b.stores.find((s) => s.name === CRUMB.store); }
function stageNode() { const s = storeNode(); return s && s.stages.find((x) => x.name === CRUMB.stage); }

function paintCrumbs() {
  CRUMB.biz = fill($('c-biz'),
    TREE.map((b) => ({ value: b.name, label: b.name })), CRUMB.biz);

  const b = bizNode();
  const stores = b ? b.stores : [];
  const bestStore = (stores.find((s) => s.stages.some((sg) => scripted(sg.folders).length))
                     || stores[0] || {}).name;
  CRUMB.store = fill($('c-store'),
    stores.map((s) => ({ value: s.name, label: s.name })), CRUMB.store, bestStore);

  const st = storeNode();
  const stages = st ? st.stages : [];
  // The first stage that has a script in it — that is where the work is.
  const bestStage = (stages.find((sg) => scripted(sg.folders).length)
                     || stages.find((sg) => sg.folders.length) || {}).name;
  CRUMB.stage = fill($('c-stage'),
    stages.map((sg) => ({
      value: sg.name,
      label: `${sg.name} (${scripted(sg.folders).length}/${sg.folders.length})`,
    })), CRUMB.stage, bestStage);

  const sg = stageNode();
  const folders = sg ? sg.folders : [];
  const bestWork = (scripted(folders)[0] || {}).path;
  CRUMB.work = fill($('c-work'),
    folders.map((f) => ({
      value: f.path,
      label: f.name + (f.has_script ? '' : '  · no script'),
      cls: f.has_script ? '' : 'noscript',
    })), CRUMB.work, bestWork);

  $('railnote').textContent = sg
    ? `${sg.folders.filter((f) => f.has_script).length} of ${sg.folders.length} `
      + `folders here have a script · the master is never written to`
    : 'nothing in this folder';
}

async function openCrumb() {
  paintCrumbs();
  const sg = stageNode();
  const hit = sg && sg.folders.find((f) => f.path === CRUMB.work);
  if (!hit) { say('nothing to open here', 'bad'); return; }
  if (!hit.has_script) {
    STATE = null;
    $('framewrap').classList.remove('has-frame');
    $('jobs').innerHTML = '';
    $('strip').innerHTML = '';
    $('tbody').innerHTML = '';
    say(`${hit.name} has no script.json — the words are the input, and there is `
      + 'nothing to build a table from', 'bad');
    return;
  }
  FOLDER = hit.path;
  SEL = 1; frameAt = -1; stopAt = null; loadedFolder = '';
  $('vid').pause();
  await refresh();
}

async function boot() {
  const d = await api('/api/tree');
  TREE = d.tree || [];
  if (!TREE.length) {
    say('no customers found under Video-Editor/Customers', 'bad');
    return;
  }
  // ⚠ OPEN ON SOMETHING THAT WORKS. Landing on an empty `development/` folder
  // makes a working editor look broken on first load, so the first selection is
  // the first folder in the tree that actually has a script.
  outer:
  for (const b of TREE) for (const st of b.stores) for (const sg of st.stages) {
    for (const f of sg.folders) {
      if (f.has_script) {
        CRUMB.biz = b.name; CRUMB.store = st.name;
        CRUMB.stage = sg.name; CRUMB.work = f.path;
        break outer;
      }
    }
  }
  for (const [id, key] of [['c-biz', 'biz'], ['c-store', 'store'],
                           ['c-stage', 'stage'], ['c-work', 'work']]) {
    $(id).addEventListener('change', (ev) => {
      CRUMB[key] = ev.target.value;
      // Anything to the right of what changed is no longer valid.
      if (key === 'biz')   { CRUMB.store = ''; CRUMB.stage = ''; CRUMB.work = ''; }
      if (key === 'store') { CRUMB.stage = ''; CRUMB.work = ''; }
      if (key === 'stage') { CRUMB.work = ''; }
      openCrumb();
    });
  }
  await openCrumb();
}

// ── wiring ────────────────────────────────────────────────────────────────
$('jobs').addEventListener('click', (ev) => {
  const b = ev.target.closest('button');
  if (b && !b.disabled && b.dataset.act) onJobClick(b);
});
$('strip').addEventListener('click', (ev) => {
  const b = ev.target.closest('button');
  if (!b) return;
  SEL = Number(b.dataset.n);
  paintSelection();
  $('vid').pause();
  stopAt = null;                  // a new scene: the old end no longer applies
  showFrame(sceneStart(SEL));
});
$('scrub').addEventListener('input', (ev) => {
  $('vid').pause();                    // scrubbing means you are looking, not watching
  showFrame(Number(ev.target.value));
});

/*
  ⚠ THE RAW CAPTURE IS SILENT, AND THE PAGE HAS TO SAY SO.
  Carson, 2026-09-15: "I can not here it?" Two causes at once — the player
  carried `muted` (mine), and the raw capture is digital silence at -91 dB,
  which is what the recorder writes: a silent AAC track, because the voice does
  not exist until narrate_mac.py lays it down. Unmuting alone would have
  changed nothing, and "I unmuted it" would have been a wrong answer.
  So: the source is a choice, and the mute control says when the current one
  has nothing to hear.
*/
function paintSource() {
  const hasNarrated = !!(STATE && STATE.narrated);
  const nar = $('src-nar');
  nar.disabled = !hasNarrated;
  nar.title = hasNarrated
    ? `play ${STATE.narrated}`
    : 'no narrated cut yet — build the voice first';
  $('src-raw').classList.toggle('on', SRC === 'raw');
  nar.classList.toggle('on', SRC === 'narrated');
  // The raw cut is always silent; the narrated one is the only one with a voice.
  const silent = SRC === 'raw';
  // ⚠ SAY IT ON THE PICTURE. See the note on .silentbadge in index.html.
  const badge = $('silentbadge');
  badge.hidden = !silent;
  badge.innerHTML = silent
    ? (hasNarrated
        ? '<b>SILENT</b> — this is the raw capture.<br>Press <b>narrated</b> to hear the voice.'
        : '<b>SILENT</b> — raw capture, no voice yet.<br>Build the voice to hear it.')
    : '';
  const m = $('mute');
  m.classList.toggle('silent', silent);
  m.textContent = $('vid').muted ? '🔇' : '🔊';
  m.title = silent
    ? 'the RAW capture is silent by design — switch to narrated to hear the voice'
    : ($('vid').muted ? 'unmute' : 'mute');
}

function setSource(next) {
  if (next === SRC) return;
  if (next === 'narrated' && !(STATE && STATE.narrated)) return;
  SRC = next;
  const at = frameAt >= 0 ? frameAt : sceneStart(SEL);
  $('vid').pause();
  stopAt = null;
  frameAt = -1;
  showFrame(at);
  paintSource();
  say(SRC === 'raw'
    ? 'raw capture — silent by design, the voice is only in the narrated cut'
    : `narrated cut — ${STATE.narrated}`, SRC === 'raw' ? '' : 'ok');
}

$('src-raw').addEventListener('click', () => setSource('raw'));
$('src-nar').addEventListener('click', () => setSource('narrated'));
$('mute').addEventListener('click', () => {
  const v = $('vid');
  v.muted = !v.muted;
  paintSource();
});

$('play').addEventListener('click', (ev) => playScene(ev.shiftKey));
$('playall').addEventListener('click', () => {
  const v = $('vid');
  if (!v.paused) { v.pause(); return; }
  playScene(true);
});

/*
  ⚠ THE PLAYHEAD DRIVES THE SCRUB, THE TIME AND THE RINGS WHILE IT PLAYS,
  and it is also what stops the scene at its own end. `timeupdate` fires about
  four times a second, which is close enough for the readout and exact enough
  for the stop once the check is a >= on the scene's end.
*/
$('vid').addEventListener('timeupdate', () => {
  const v = $('vid');
  const t = Math.round(v.currentTime * 100) / 100;
  frameAt = t;
  $('scrubat').textContent = t.toFixed(2) + 's';
  $('scrub').value = String(t);
  drawRings();
  if (stopAt !== null && t >= stopAt - 0.02) {
    v.pause();
    try { v.currentTime = stopAt; } catch (_) {}
  }
});
$('vid').addEventListener('play', () => setPlayIcon(true));
$('vid').addEventListener('pause', () => setPlayIcon(false));
$('vid').addEventListener('ended', () => { setPlayIcon(false); stopAt = null; });

// Space plays, but never while a line is being typed into.
document.addEventListener('keydown', (ev) => {
  if (ev.code !== 'Space') return;
  const a = document.activeElement;
  if (a && a.classList && a.classList.contains('linebox')) return;
  if (a && a.tagName === 'SELECT') return;
  ev.preventDefault();
  playScene(ev.shiftKey);
});

/*
  ⚠ A FAILED FIRST FETCH RETRIES, ONCE, RATHER THAN LEAVING A DEAD PAGE.
  The server is often restarted while this tab is open; the page then loads
  against a socket that is half a second from being ready and shows "Failed to
  fetch" forever, which looks exactly like a broken editor.
*/
boot().catch(async (e) => {
  say('starting… (' + e.message + ')', 'work');
  await new Promise((r) => setTimeout(r, 1200));
  boot().catch((e2) => say('could not start: ' + e2.message
    + ' — is the server running on 8848?', 'bad'));
});
