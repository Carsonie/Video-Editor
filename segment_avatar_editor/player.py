#!/usr/bin/env python3
"""
The Segment and Avatar Editor — one scene's footage with its alpha avatar laid
over it, in two shapes:

  layered   (PAIR_TEMPLATE)  one scene, mp4 underneath and WebM on top
  timeline  (SEQ_TEMPLATE)   several scenes joined, to judge how they JOIN

They are one player because they edit the same two layers with the same tools;
only the span differs. Frame extraction and the edit maths live in shared/.
"""
import json
import os

from shared import frames

probe = frames.probe
get_frame_map = frames.get_frame_map

# The player's name and version, shown at the foot of its page. The version
# lives in a VERSION file beside this module rather than in the source, so a
# bump is a one-line diff that a commit hook can see and a reader can trust.
NAME = "Segment and Avatar Editor"

def _version():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERSION")
    try:
        return open(p).read().strip() or "?"
    except OSError:
        return "?"

def label():
    return f"{NAME} v{_version()}"


PAIR_TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>
  :root {{
    --box: {box}px;
    --base: #2ecc40;          /* BACKGROUND (mp4) is green  */
    --over: #a56cff;          /* OVERLAY   (webm) is purple */
    --active: var(--base);
  }}
  body {{ margin:0; background:#141414; color:#eee;
         font:14px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
  .wrap {{ padding:14px; display:flex; gap:16px; align-items:flex-start;
           justify-content:center; }}
  .left {{ display:flex; flex-direction:column; gap:10px; align-items:center; }}
  /* The scene list is the reason a cut is reviewable at all: a folder holds
     several versions of the same recording, and lexical order puts Num_10
     before Num_2. Here they are in SCENE order, named, one click to load. */
  /* 270 -> 360: the row carries six columns now (tick, number, name,
     duration, then a lock+count for EACH layer). At 270 the name was
     ellipsed down to one or two letters, which made the list useless. */
  .right {{ width:360px; flex:none; background:#1b1f22; border:1px solid #3a4248;
            border-radius:8px; padding:10px; max-height:88vh; overflow:auto; }}
  .right h4 {{ margin:0 0 8px; font-size:12px; color:#9aa; font-weight:600;
               text-transform:uppercase; letter-spacing:.04em; }}
  #verSel {{ width:100%; background:#2c3236; color:#eee; border:1px solid #4a5259;
             border-radius:6px; padding:6px; margin-bottom:8px; font-size:13px; }}
  .vlab {{ display:block; font-size:11px; color:#6d757b; margin:2px 0 3px; }}
  /* The three versions that must agree, stated before anything is clicked.
     A cut, an avatar set and a script can each move independently, and a
     mismatch is invisible in the picture until the wrong voice plays. */
  /* Two kinds of information were shown as one pile of chips: WHERE the files
     come from, and WHICH VERSION each part is. Separated now, and each version
     sits against the LAYER it feeds — same dot and colour as the
     Background/Overlay toggles above the stage, so a number attaches to
     something already understood instead of floating free. */
  #scopeBar {{ font-size:11.5px; line-height:1.45; padding:6px 8px; margin-bottom:9px;
               border-radius:6px; border:1px solid #7a5c2a; background:#2a2114;
               color:#ffd9a0; }}
  #scopeBar b {{ color:#ffb74d; }}
  #scopeBar .sub {{ color:#9c8a6d; }}
  #verStamp {{ margin-bottom:9px; }}
  .vrow {{ display:flex; align-items:baseline; gap:7px; font-size:12px; padding:2px 0; }}
  .vrow .dot {{ font-size:10px; width:10px; text-align:center; }}
  .vrow .who {{ color:#9aa; width:74px; }}
  .vrow .what {{ color:#cfd6da; flex:1; }}
  .vrow .ver {{ color:#fff; font-weight:600; }}
  .vrow.base .dot {{ color:#2ecc40; }}
  .vrow.over .dot {{ color:#a56cff; }}
  .vrow.meta .dot {{ color:#5a636a; }}
  .scene .pick {{ accent-color:#2ecc40; margin:0 2px 0 0; cursor:pointer; flex:none; }}
  #seqBtn {{ width:100%; margin-top:8px; }}
  #seqBtn:not(:disabled) {{ background:#1f5c2e; border-color:#2ecc40; }}
  .scene .ovv {{ font-size:10px; color:#a56cff; border:1px solid #4a3a68;
                 border-radius:8px; padding:0 5px; }}
  .scene.cur .ovv {{ color:#e6d9ff; border-color:#7a5fb0; }}
  .scene {{ display:flex; gap:8px; align-items:baseline; padding:6px 8px;
            border-radius:6px; cursor:pointer; font-size:13px; line-height:1.3; }}
  .scene:hover {{ background:#252b2f; }}
  .scene .num {{ color:#8a949b; min-width:18px; text-align:right; }}
  .scene .lab {{ flex:1; min-width:88px; color:#dfe4e7; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
  .scene .dur {{ color:#8a949b; font-size:12px; }}
  .scene.cur {{ background:#1f5c2e; }}
  .scene.cur .lab, .scene.cur .num, .scene.cur .dur {{ color:#eaffef; }}
  #stage {{ position:relative; width:var(--box); height:var(--box);
            background:#232323; border:2px solid var(--active); border-radius:8px;
            overflow:hidden; transition:border-color .12s; }}
  #baseImg {{ position:absolute; left:0; width:var(--box); top:50%;
              transform:translateY(-50%); image-rendering:auto; }}
  #overImg {{ position:absolute; left:0; top:0; width:var(--box); height:var(--box); }}
  /* Dim whichever layer is NOT being edited, so the active one is unmistakable. */
  .dimBase #baseImg {{ opacity:.35; }}
  .dimOver #overImg {{ opacity:.35; }}
  .row {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap;
          justify-content:center; }}
  .bar {{ width:var(--box); }}
  input[type=range] {{ width:100%; accent-color:var(--active); }}
  button {{ background:#2c3236; color:#eee; border:1px solid #4a5259;
            border-radius:6px; padding:7px 11px; font-size:14px; cursor:pointer; }}
  button:hover {{ border-color:var(--active); }}
  button:disabled {{ opacity:.4; cursor:default; }}
  button.on {{ background:var(--active); border-color:var(--active); color:#111;
               font-weight:600; }}
  .tgl {{ display:flex; gap:0; border:1px solid #4a5259; border-radius:8px;
          overflow:hidden; }}
  .tgl button {{ border:0; border-radius:0; padding:8px 16px; }}
  #tBase.on {{ background:var(--base); color:#111; }}
  #tOver.on {{ background:var(--over); color:#111; }}
  .meta {{ font-size:12px; color:#9aa; }}
  .meta b {{ color:#eee; }}
  #ticks {{ position:relative; height:12px; }}
  .tick {{ position:absolute; top:0; width:3px; height:12px;
           background:var(--active); transform:translateX(-50%);
           border-radius:1px; cursor:pointer; }}
  .tick:hover {{ filter:brightness(1.4); }}
  .tick::before {{ content:''; position:absolute; left:-6px; right:-6px;
                   top:-4px; bottom:-4px; }}
  #status {{ font-size:12px; color:#e0c060; min-height:16px; white-space:pre-line;
             text-align:center; max-width:var(--box); }}
  /* The player's own name, at the foot of the page. Three players share this
     server and look alike at a glance; this is what says which one you are in
     before you touch a control. */
  .playerName {{ margin:22px auto 4px; text-align:center; font-size:12px;
                letter-spacing:.16em; text-transform:uppercase; color:#6d757b; }}
  /* Matched to the row's buttons so the transport reads as one control set.
     Lit whenever the rate is not 1x, so an odd speed cannot pass for normal. */
  #rateSel {{ background:#2c3236; color:#eee; border:1px solid #4a5259; border-radius:6px;
             height:30px; font-size:12px; font-family:inherit; padding:0 4px; cursor:pointer; }}
  #rateSel:hover {{ background:#373e43; }}
  #rateSel.off1 {{ background:#1f5c2e; border-color:#2ecc40; color:#fff; }}
  /* Right-hand pair on every scene row: an edit lock, then that segment's
     frame count. The lock is a SEPARATE control from the tick on the left —
     that one says "show me this scene", this one says "let me change it". */
  .edcb {{ margin:0 0 0 6px; accent-color:#e0a93f; flex-shrink:0; cursor:pointer; }}
  /* FIXED width, not min-width: the totals row carries four digits where a
     scene carries three, and a column that grows to fit its widest cell shunts
     everything after it out of line. Wide enough for "~2827". */
  .frames {{ font-variant-numeric:tabular-nums; font-size:11px; color:#8b949c;
            width:44px; flex:none; text-align:right; }}
  /* A count read from the file header rather than a real extraction can be one
     out, so it shows a ~ and is never passed off as exact. */
  .frames.est {{ color:#6d757b; font-style:italic; }}
  .scene.locked .lab {{ opacity:.5; text-decoration:line-through; }}
  /* The overlay pair is tinted to match the purple the overlay layer uses
     everywhere else, so which lock belongs to which layer is readable without
     hovering. */
  .edcb.ov {{ accent-color:#a06cd5; }}
  .frames.ov {{ color:#9d86bd; }}
  .frames.ov.est {{ color:#6f5f87; }}
  .scene.lk-base .lab {{ opacity:.6; }}
  .scene.lk-both .lab {{ opacity:.45; text-decoration:line-through; }}
  /* Totals foot the list. Spacers stand in for the three checkbox columns so
     each total sits under the column it adds up -- a totals row that does not
     line up with its column is just another number on the page. */
  .scene.totals {{ border-top:1px solid #3a4248; margin-top:4px; padding-top:7px;
                  font-weight:600; color:#cfd6dc; cursor:default; background:none; }}
  .scene.totals .lab {{ color:#8b949c; font-weight:500; }}
  .scene.totals .frames {{ color:#e6d3a8; }}
  .scene.totals .frames.ov {{ color:#c3a9e0; }}
  /* A spacer must reproduce its checkbox's MARGINS as well as its width.
     Without them the flexible middle column swallowed the 14px difference
     and every total sat 6px right of the column it was summing. */
  .cbpad {{ width:13px; flex:none; }}
  .cbpad.pk {{ margin-right:2px; }}   /* mirrors .pick  */
  .cbpad.ed {{ margin-left:6px; }}    /* mirrors .edcb  */
</style></head><body>
<div class="wrap">
 <div class="left">
  <div class="row">
    <div class="tgl">
      <button id="tBase" class="on">● Background &nbsp;<small>mp4</small></button>
      <button id="tOver">● Overlay &nbsp;<small>webm</small></button>
    </div>
    <button id="soloBtn" title="Dim the layer that is not being edited">Solo active</button>
  </div>
  <div class="meta" id="who"></div>

  <div id="stage"><img id="baseImg"><img id="overImg"></div>
  <audio id="audBase" src="base/audio.m4a" preload="auto"></audio>
  <audio id="audOver" src="overlay/audio.m4a" preload="auto"></audio>

  <div class="bar"><div id="ticks"></div>
    <input id="slider" type="range" min="1" max="{max_n}" value="1" step="1"></div>
  <div class="meta" id="pos"></div>

  <div class="row">
    <button id="playBtn" title="Play / pause  (space)">▶ Play</button>
    <button id="muteBtn" title="Mute / unmute">🔊</button>
    <select id="rateSel" title="Playback speed. Slow to judge a seam; 2x to skim.">
      <option value="2">2x</option>
      <option value="1" selected>1x</option>
      <option value="0.5">0.5x</option>
      <option value="0.25">0.25x</option>
      <option value="0.125">0.125x</option>
    </select>
    <button id="p10">◀◀</button><button id="p1">◀</button>
    <button id="n1">▶</button><button id="n10">▶▶</button>
    <label class="meta" style="margin-left:4px">
      <input id="loopChk" type="checkbox" checked> loop</label>
    <button id="markBtn">◆ Mark / unmark</button>
    <button id="prevMark">[ prev mark</button><button id="nextMark">next mark ]</button>
  </div>
  <div class="row">
    <button id="addL">+1 ◀ add</button><button id="addR">add ▶ +1</button>
    <button id="delL">−1 ◀ del</button><button id="delR">del ▶ −1</button>
    <button id="cutBtn">✂ Cut active</button>
    <button id="saveBtn">💾 Save active</button>
  </div>
  <div id="status"></div>
 </div>
 <div class="right">
   <h4>Scenes</h4>
   <div id="scopeBar"></div>
   <div id="verStamp"></div>
   <label class="vlab" for="verSel">cut</label>
   <select id="verSel"></select>
   <div id="sceneList"></div>
   <button id="seqBtn" disabled>&#9654; Timeline of 0 scenes</button>
   <div class="vlab" style="margin:4px 0 8px">Tick several to watch how they join.</div>
   <div id="sceneNote" style="font-size:11px;color:#6d757b;margin-top:8px;line-height:1.5"></div>
 </div>
</div>
  <div class="playerName">{player_label}</div>
<script>
  const SLUG = {slug!r};
  const BASE_REL = {base_rel!r};
  const OVERLAY_REL = {overlay_rel!r};
  const HAS_A = {{ base: {base_audio}, overlay: {over_audio} }};
  const T = {{
    base:    {{ n: {base_n}, ext: {base_ext!r}, fps: {base_fps}, name: {base_name!r}, marks: new Set() }},
    overlay: {{ n: {over_n}, ext: {over_ext!r}, fps: {over_fps}, name: {over_name!r}, marks: new Set() }}
  }};
  let which = 'base';
  let ver = Date.now();
  let solo = false;

  const $ = id => document.getElementById(id);
  const pad = n => String(n).padStart(5, '0');
  const cur = () => T[which];

  function paint() {{
    document.documentElement.style.setProperty('--active',
      which === 'base' ? 'var(--base)' : 'var(--over)');
    $('tBase').classList.toggle('on', which === 'base');
    $('tOver').classList.toggle('on', which === 'overlay');
    $('stage').className = !solo ? '' : (which === 'base' ? 'dimOver' : 'dimBase');
    $('soloBtn').classList.toggle('on', solo);
    $('who').innerHTML =
      `editing <b>${{which === 'base' ? 'BACKGROUND' : 'OVERLAY'}}</b> — ` +
      `<b>${{cur().name}}</b> · ${{cur().n}} frames · ${{(cur().n / cur().fps).toFixed(2)}}s` +
      (VERSTAMP ? ` &nbsp;·&nbsp; <span style="color:#8a949b">${{VERSTAMP}}</span>` : '');
  }}

  // One playhead over BOTH clips. Each layer holds its own last frame when it
  // runs out, which is what the finished video does too — the avatar track and
  // the demo track are rarely the same length.
  function show(n) {{
    const maxN = Math.max(T.base.n, T.overlay.n);
    n = Math.max(1, Math.min(maxN, n));
    $('slider').value = n;
    $('slider').max = maxN;
    const b = Math.min(n, T.base.n), o = Math.min(n, T.overlay.n);
    $('baseImg').src = `base/frames/frame_${{pad(b)}}${{T.base.ext}}?v=${{ver}}`;
    $('overImg').src = `overlay/frames/frame_${{pad(o)}}${{T.overlay.ext}}?v=${{ver}}`;
    $('pos').innerHTML =
      `frame <b>${{n}}</b> / ${{maxN}} &nbsp;·&nbsp; ${{((n - 1) / cur().fps).toFixed(3)}}s ` +
      `&nbsp;·&nbsp; base ${{b}}/${{T.base.n}} &nbsp;·&nbsp; overlay ${{o}}/${{T.overlay.n}}`;
    renderTicks();
  }}

  function renderTicks() {{
    const maxN = Math.max(T.base.n, T.overlay.n);
    const t = $('ticks'); t.innerHTML = '';
    for (const m of cur().marks) {{
      const el = document.createElement('div');
      el.className = 'tick';
      el.style.left = ((m - 1) / Math.max(1, maxN - 1) * 100) + '%';
      el.title = `frame ${{m}} — click to jump`;
      el.addEventListener('mousedown', e => {{ e.preventDefault(); e.stopPropagation(); show(m); }});
      t.appendChild(el);
    }}
  }}

  async function api(path, body) {{
    const r = await fetch(path, {{ method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify(Object.assign({{ slug: SLUG, which }}, body)) }});
    const d = await r.json();
    if (d.error) {{ $('status').textContent = 'Error: ' + d.error; return null; }}
    return d;
  }}

  async function loadMarks() {{
    for (const w of ['base', 'overlay']) {{
      const r = await fetch(`/api/marks?slug=${{SLUG}}&which=${{w}}`);
      const d = await r.json();
      T[w].marks = new Set(d.marks || []);
    }}
    renderTicks();
  }}

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

  function preload(from) {{
    const maxN = Math.max(T.base.n, T.overlay.n);
    for (let i = from; i < from + PRELOAD && i <= maxN; i++) {{
      new Image().src = `base/frames/frame_${{pad(Math.min(i, T.base.n))}}${{T.base.ext}}?v=${{ver}}`;
      new Image().src = `overlay/frames/frame_${{pad(Math.min(i, T.overlay.n))}}${{T.overlay.ext}}?v=${{ver}}`;
    }}
  }}

  // Whichever track actually carries sound is the clock. In a help video that
  // is the AVATAR, not the screen capture — the demo footage is silent. Two
  // clocks drift, and sync is the thing this playback exists to judge.
  function clockAud() {{
    if (HAS_A.overlay && !$('audOver').paused) return $('audOver');
    if (HAS_A.base && !$('audBase').paused) return $('audBase');
    return null;
  }}
  function tick() {{
    if (!playing) return;
    const maxN = Math.max(T.base.n, T.overlay.n);
    const fps = cur().fps || 25;
    const a = clockAud();
    let n;
    if (a) {{
      n = Math.floor(a.currentTime * fps) + 1;
      if (n > maxN) {{ for (const e of [$('audBase'), $('audOver')]) e.currentTime = 0; n = 1; }}
    }} else {{
      n = playF0 + Math.floor((performance.now() - playT0) / 1000 * fps * RATE);
    }}
    if (n > maxN) {{
      if ($('loopChk').checked) {{ playT0 = performance.now(); playF0 = 1; n = 1; }}
      else {{ stop(); show(maxN); return; }}
    }}
    show(n);
    if (n % 20 === 0) preload(n + 1);
  }}
  function play() {{
    const maxN = Math.max(T.base.n, T.overlay.n);
    playing = true;
    playF0 = (+$('slider').value >= maxN) ? 1 : +$('slider').value;
    playT0 = performance.now();
    $('playBtn').textContent = '❚❚ Pause';
    $('playBtn').classList.add('on');
    preload(playF0);
    // Both tracks start from the same frame, so the mix matches the picture.
    for (const [k, id] of [['base','audBase'], ['overlay','audOver']]) {{
      if (!HAS_A[k]) continue;
      const e = $(id);
      e.currentTime = Math.min((playF0 - 1) / (cur().fps || 25), Math.max(0, (T[k].n - 1) / T[k].fps));
      // Whichever track carries sound is the frame clock, so slowing the
      // audio slows the picture with it — one clock still, at either rate.
      e.playbackRate = Math.max(AUDIO_RATE_FLOOR, RATE);
      if (RATE >= AUDIO_RATE_FLOOR) e.play().catch(() => {{}});
    }}
    rafId = setInterval(tick, Math.max(8, 1000 / ((cur().fps || 25) * RATE) / 2));
  }}
  function stop() {{
    playing = false;
    if (rafId) clearInterval(rafId);
    rafId = null;
    for (const id of ['audBase','audOver']) $(id).pause();
    $('playBtn').textContent = '▶ Play';
    $('playBtn').classList.remove('on');
  }}
  $('playBtn').onclick = () => playing ? stop() : play();
  $('rateSel').onchange = () => {{
    RATE = parseFloat($('rateSel').value);
    $('rateSel').classList.toggle('off1', RATE !== 1);
    $('status').textContent = (RATE < AUDIO_RATE_FLOOR && (HAS_A.base || HAS_A.overlay))
      ? `Audio is off below ${{AUDIO_RATE_FLOOR}}x - the browser will not play a track that slow. The picture is still exact.` : '';
    if (!playing) return;
    for (const [k, id] of [['base','audBase'], ['overlay','audOver']]) {{
      if (!HAS_A[k]) continue;
      const e = $(id);
      if (RATE < AUDIO_RATE_FLOOR) {{ e.pause(); continue; }}
      e.playbackRate = RATE;
      if (e.paused) {{ e.currentTime = (+$('slider').value - 1) / (cur().fps || 25); e.play().catch(() => {{}}); }}
    }}
    // Rebase the elapsed-time origin onto the frame showing now, or the
    // playhead jumps the moment the rate changes.
    playF0 = +$('slider').value;
    playT0 = performance.now();
    clearInterval(rafId);
    rafId = setInterval(tick, Math.max(8, 1000 / ((cur().fps || 25) * RATE) / 2));
  }};
  $('muteBtn').onclick = () => {{
    const m = !$('audOver').muted;
    for (const id of ['audBase','audOver']) $(id).muted = m;
    $('muteBtn').textContent = m ? '🔇' : '🔊';
  }};
  if (!HAS_A.base && !HAS_A.overlay) {{
    $('muteBtn').disabled = true; $('muteBtn').textContent = '🔇';
    $('muteBtn').title = 'neither clip has an audio track';
  }}

  $('tBase').onclick = () => {{ which = 'base'; refreshEditGate(); paint(); show(+$('slider').value); }};
  $('tOver').onclick = () => {{ which = 'overlay'; refreshEditGate(); paint(); show(+$('slider').value); }};
  $('soloBtn').onclick = () => {{ solo = !solo; paint(); }};
  ['p1','n1','p10','n10','prevMark','nextMark'].forEach(id =>
    $(id).addEventListener('click', stop, true));
  $('slider').addEventListener('mousedown', stop);
  $('p1').onclick = () => show(+$('slider').value - 1);
  $('n1').onclick = () => show(+$('slider').value + 1);
  $('p10').onclick = () => show(+$('slider').value - 10);
  $('n10').onclick = () => show(+$('slider').value + 10);
  $('slider').oninput = () => show(+$('slider').value);

  $('markBtn').onclick = async () => {{
    const n = +$('slider').value, on = !cur().marks.has(n);
    const d = await api('/api/mark', {{ frame: n, on }});
    if (!d) return;
    on ? cur().marks.add(n) : cur().marks.delete(n);
    $('status').textContent = `${{on ? 'Marked' : 'Unmarked'}} frame ${{n}} on ${{which}}.`;
    renderTicks();
  }};
  function jump(dir) {{
    const s = [...cur().marks].sort((a, b) => a - b), n = +$('slider').value;
    const t = dir > 0 ? s.find(m => m > n) : [...s].reverse().find(m => m < n);
    if (t !== undefined) show(t);
  }}
  $('prevMark').onclick = () => jump(-1);
  $('nextMark').onclick = () => jump(1);

  async function edit(path, side) {{
    const d = await api(path, {{ at: Math.min(+$('slider').value, cur().n), count: 1, side }});
    if (!d) return;
    cur().n = d.nb_frames;
    cur().marks = new Set(d.marks || []);
    ver++;                       // frames moved on disk — every cached URL is suspect
    $('status').textContent =
      `${{path.includes('dup') ? 'Added' : 'Deleted'}} 1 frame ${{side}} on ${{which}} — now ${{d.nb_frames}} frames.`;
    show(d.current || +$('slider').value);
  }}
  $('addL').onclick = () => edit('/api/frames/dup', 'left');
  $('addR').onclick = () => edit('/api/frames/dup', 'right');
  $('delL').onclick = () => edit('/api/frames/del', 'left');
  $('delR').onclick = () => edit('/api/frames/del', 'right');

  $('cutBtn').onclick = async () => {{
    if (!cur().marks.size) {{ $('status').textContent = `No break points on ${{which}}.`; return; }}
    if (!confirm(`Cut ${{cur().name}} at ${{cur().marks.size}} break point(s)?`)) return;
    const d = await api('/api/cut', {{}});
    if (!d) return;
    $('status').textContent = `Wrote ${{d.count}} segment(s) to:\\n${{d.outdir}}`;
  }};
  $('saveBtn').onclick = async () => {{
    if (!confirm(`Overwrite ${{cur().name}} with its edited length (${{cur().n}} frames)?\\n\\n` +
                 `The current file is archived to z_History/ first.`)) return;
    const d = await api('/api/save', {{}});
    if (!d) return;
    ver++;
    $('status').textContent = `Saved ${{d.duration_s}}s to:\\n${{d.path}}`;
  }};

  document.addEventListener('keydown', e => {{
    if (e.key === 'ArrowLeft')  {{ e.altKey ? jump(-1) : show(+$('slider').value - (e.shiftKey ? 10 : 1)); e.preventDefault(); }}
    if (e.key === 'ArrowRight') {{ e.altKey ? jump(1)  : show(+$('slider').value + (e.shiftKey ? 10 : 1)); e.preventDefault(); }}
    if (e.key === ' ') {{ $('playBtn').click(); e.preventDefault(); }}
    if (e.key === 'm' || e.key === 'M') {{ $('markBtn').click(); e.preventDefault(); }}
    if (e.key === 'b' || e.key === 'B') {{ $('tBase').click(); e.preventDefault(); }}
    if (e.key === 'o' || e.key === 'O') {{ $('tOver').click(); e.preventDefault(); }}
  }});

  // ── the scene list ────────────────────────────────────────────────────
  // Selecting a scene RELOADS the page against a new base, because a pair is
  // keyed on both files and its cache is per-pair. The overlay is carried
  // across unchanged, which is the point: step scene by scene with the same
  // avatar clip laid over each one.
  let SIB = null, VERSTAMP = '';
  async function loadScenes() {{
    try {{
      const r = await fetch(`/api/siblings?path=${{encodeURIComponent(BASE_REL)}}`);
      SIB = await r.json();
      if (SIB.error) {{ $('sceneNote').textContent = SIB.error; return; }}
    }} catch (e) {{ $('sceneNote').textContent = String(e); return; }}
    const sel = $('verSel');
    sel.innerHTML = '';
    for (const v of SIB.versions) {{
      const o = document.createElement('option');
      o.value = v; o.textContent = `v${{v}}  (${{SIB.by_version[v].length}} scenes)`;
      if (v === SIB.current_version) o.selected = true;
      sel.appendChild(o);
    }}
    VERSTAMP = `segment v${{SIB.current_version ?? '?'}}` +
               (SIB.overlay_version ? ` · avatar v${{SIB.overlay_version}}` : ' · no avatar set');

    // WHERE, on its own and first. This is the fact that changes what an edit
    // DOES, so it does not belong in a row of version numbers — which is how it
    // was, and why the panel read as five chips of one kind when it was two.
    $('scopeBar').innerHTML = SIB.editor_scope === 'sandbox'
      ? `Editing <b>sandbox</b> — your working copy.` +
        `<br><span class="sub">Reads and writes here only. dev/ is the safe copy, never touched.</span>`
      : `Editing <b>${{SIB.layout || 'files'}}</b> directly.` +
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
        `<span class="ver">v${{SIB.current_version ?? '?'}}</span></div>`,
      `<div class="vrow over"><span class="dot">&#9679;</span>` +
        `<span class="who">overlay</span><span class="what">avatar + audio</span>` +
        (SIB.overlay_version
          ? `<span class="ver">v${{SIB.overlay_version}}</span>`
          : `<span class="ver" style="color:#e05555">none</span>`) + `</div>`,
    ];
    if (SIB.script_version)
      rows.push(`<div class="vrow meta"><span class="dot">&middot;</span>` +
                `<span class="who">words</span><span class="what">script</span>` +
                `<span class="ver">v${{SIB.script_version}}</span></div>`);
    if (nmiss)
      rows.push(`<div class="vrow meta"><span class="dot">!</span>` +
                `<span class="who" style="color:#e05555">missing</span>` +
                `<span class="what">no sandbox copy</span>` +
                `<span class="ver" style="color:#e05555">${{nmiss}}</span></div>`);
    $('verStamp').innerHTML = rows.join('');
    paint();
    sel.onchange = () => renderScenes(+sel.value);
    renderScenes(SIB.current_version ?? SIB.versions[0]);
  }}
  // Scenes whose edits are blocked. A SET OF LOCKS, not of permissions, so the
  // empty default means everything stays editable exactly as before — the lock
  // changes nothing until you deliberately turn one on. Per page load: it is a
  // guard while you work, not a property of the file.
  // Keyed "<scene>:<layer>", because a scene has TWO editable things and they
  // are locked independently: you routinely finish the footage while the avatar
  // is still being retimed. A set of LOCKS, not permissions, so empty means
  // everything stays editable exactly as before.
  const LOCKED = new Set();
  const lockKey = (n, layer) => `${{n}}:${{layer}}`;
  const isLocked = (n, layer) => LOCKED.has(lockKey(n, layer));

  // Gate the controls that CHANGE something, against the scene they would act
  // on. Cut and Save are included: they write files, which is the thing a lock
  // most needs to stop.
  function refreshEditGate() {{
    const n = currentSceneN();
    // Gate against the layer that is LIT, because that is the one every edit
    // acts on. Locking the segment must not stop you retiming the avatar.
    const blocked = n != null && isLocked(n, which);
    for (const id of ['addL', 'addR', 'delL', 'delR', 'cutBtn', 'saveBtn']) {{
      const el = $(id);
      if (el) {{
        el.disabled = blocked;
        el.title = blocked
          ? `The ${{which === 'base' ? 'segment' : 'overlay'}} of scene ${{n}} is locked — untick its lock in the list to edit it`
          : '';
      }}
    }}
  }}
  // Row styling reflects BOTH locks: one layer locked is dimmed, both locked is
  // struck through. A single "locked" class could not tell those apart.
  function paintLockState() {{
    for (const el of document.querySelectorAll('.scene')) {{
      const n = +el.dataset.n;
      const b = isLocked(n, 'base'), o = isLocked(n, 'overlay');
      el.classList.toggle('lk-base', (b || o) && !(b && o));
      el.classList.toggle('lk-both', b && o);
      el.classList.remove('locked');
    }}
  }}

  let CUR_N = null;
  const currentSceneN = () => CUR_N;

  // Totals, footing the list: how many scenes, how long they run, and how many
  // frames each LAYER holds. The two frame totals stay SEPARATE -- they are
  // different files of different lengths, and one combined number would mean
  // nothing. Spacers keep each total under the column it sums.
  function renderTotals(rows) {{
    const usable = rows.filter(r => !r.missing);
    const secs = usable.reduce((a, r) => a + (r.dur || 0), 0);
    const segF = usable.reduce((a, r) => a + (r.frames || 0), 0);
    const ovF  = usable.reduce((a, r) => a + (r.overlay_frames || 0), 0);

    const d = document.createElement('div');
    d.className = 'scene totals';
    d.title = `${{usable.length}} scenes, ${{secs.toFixed(2)}}s, `
            + `${{segF}} segment frames, ${{ovF}} overlay frames`;
    const pad = kind => {{
      const x = document.createElement('span');
      x.className = 'cbpad ' + kind;
      return x;
    }};
    d.appendChild(pad('pk'));

    const body = document.createElement('span');
    body.style.cssText = 'display:flex;gap:8px;align-items:baseline;flex:1;min-width:0';
    body.innerHTML = `<span class="lab">${{usable.length}} scenes</span>`
                   + `<span class="dur">${{secs.toFixed(2)}}s</span>`;
    d.appendChild(body);

    for (const [layer, total] of [['base', segF], ['overlay', ovF]]) {{
      d.appendChild(pad('ed'));
      const f = document.createElement('span');
      f.className = 'frames' + (layer === 'overlay' ? ' ov' : '');
      f.textContent = total;
      f.title = `${{total}} ${{layer === 'base' ? 'segment' : 'overlay'}} frames in total`;
      d.appendChild(f);
    }}
    $('sceneList').appendChild(d);
  }}

  function renderScenes(v) {{
    const list = $('sceneList'); list.innerHTML = '';
    for (const it of (SIB.by_version[v] || [])) {{
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
          ? `<span class="ovv">v${{SIB.overlay_version}}</span>`
          : `<span class="ovv" style="color:#e05555;border-color:#7a3a3a">none</span>`;
      const cb = document.createElement('input');
      cb.type = 'checkbox'; cb.className = 'pick'; cb.dataset.n = it.n;
      cb.checked = it.current;          // start with what is already open
      cb.disabled = !!it.missing;
      cb.onclick = ev => {{ ev.stopPropagation(); updatePick(); }};
      d.appendChild(cb);
      const body = document.createElement('span');
      body.style.cssText = 'display:flex;gap:8px;align-items:baseline;flex:1';
      body.innerHTML = `<span class="num">${{it.n}}</span>` +
                    `<span class="lab">${{it.label || it.name}}</span>` +
                    ovTag +
                    `<span class="dur">${{it.dur ?? '?'}}s</span>`;
      d.appendChild(body);
      d.title = it.name;
      body.onclick = () => {{
        if (it.current) return;
        // THIS scene's own overlay when one exists, so picture, avatar and audio
        // are the same scene. Falling back to the current overlay would put the
        // wrong voice under the right footage, which is the fault this replaced.
        const ov = it.overlay || OVERLAY_REL;
        $('status').textContent = it.overlay
          ? `Loading scene ${{it.n}} with its own narration…`
          : `Scene ${{it.n}} has no overlay of its own — keeping the current one.`;
        location.href = `/api/open-pair-go?base=${{encodeURIComponent(it.path)}}`
                      + `&overlay=${{encodeURIComponent(ov)}}`;
      }};
      // Two locks and two counts: the SEGMENT (the footage) and the OVERLAY
      // (the avatar). They are separate controls because they are separate
      // files with separate lengths, edited one layer at a time.
      const addPair = (layer, count, exact, present) => {{
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.className = 'edcb' + (layer === 'overlay' ? ' ov' : '');
        cb.dataset.n = it.n; cb.dataset.layer = layer;
        cb.checked = !isLocked(it.n, layer);
        cb.disabled = !present;
        cb.title = present
          ? `Editing allowed for this scene's ${{layer === 'base' ? 'segment' : 'overlay'}}`
          : `this scene has no ${{layer === 'base' ? 'segment' : 'overlay'}}`;
        cb.onclick = ev => {{
          ev.stopPropagation();
          if (cb.checked) LOCKED.delete(lockKey(it.n, layer));
          else LOCKED.add(lockKey(it.n, layer));
          paintLockState();
          refreshEditGate();
        }};
        d.appendChild(cb);

        const fr = document.createElement('span');
        fr.className = 'frames' + (layer === 'overlay' ? ' ov' : '') + (exact ? '' : ' est');
        fr.dataset.n = it.n; fr.dataset.layer = layer;
        fr.textContent = count == null ? '—' : (exact ? String(count) : '~' + count);
        fr.title = count == null
          ? `no ${{layer === 'base' ? 'segment' : 'overlay'}} frame count available`
          : (exact ? `${{count}} frames, counted from the extraction`
                   : `about ${{count}} frames, read without extracting — it can be out by one until the scene has been opened`);
        d.appendChild(fr);
      }};
      addPair('base', it.frames, it.frames_exact, !it.missing);
      addPair('overlay', it.overlay_frames, it.overlay_frames_exact, !!it.overlay);
      list.appendChild(d);
    }}
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
        ? `<br>${{SIB.versions.length}} segment cuts on disk; switching version keeps the pairing.`
        : '') +
      (SIB.overlay_version && !anyOv ? `<br>⚠ none matched this cut's scene numbers.` : '');
  }}

  // Several scenes on ONE timeline. A scene alone cannot show how it JOINS the
  // next, and a join is where the faults are — a pose that jumps, a voice that
  // starts before the picture settles.
  function updatePick() {{
    const picked = [...document.querySelectorAll('.pick')].filter(c => c.checked);
    $('seqBtn').disabled = picked.length < 1;
    $('seqBtn').innerHTML = picked.length
      ? `&#9654; Timeline of ${{picked.length}} scene${{picked.length === 1 ? '' : 's'}}`
      : '&#9654; Timeline of 0 scenes';
  }}
  $('seqBtn').onclick = () => {{
    const ns = [...document.querySelectorAll('.pick')].filter(c => c.checked)
                 .map(c => +c.dataset.n).sort((a, b) => a - b);
    if (!ns.length) return;
    $('status').textContent = `Building a timeline of ${{ns.length}} scene(s)…`;
    location.href = `/api/open-seq-go?root=${{encodeURIComponent(SIB.folder)}}`
                  + `&ns=${{ns.join(',')}}`;
  }};

  paint(); show(1); loadMarks(); loadScenes();
</script></body></html>
"""


def write_pair(outdir, base_meta, over_meta, box=750, base_rel="", overlay_rel=""):
    """
    Write the layered viewer for a base/overlay pair.

    `base_rel`/`overlay_rel` are the two sources' paths relative to Customers/.
    The viewer needs them to list the base's sibling scenes and to reload itself
    against a different one while carrying the same overlay across.
    """
    html = PAIR_TEMPLATE.format(
        player_label=label(),
        title=f"{base_meta.get('source_name','base')} + {over_meta.get('source_name','overlay')}",
        box=box, slug=os.path.basename(outdir.rstrip("/")),
        base_rel=base_rel, overlay_rel=overlay_rel,
        max_n=max(base_meta["nb_frames"], over_meta["nb_frames"]),
        base_n=base_meta["nb_frames"], over_n=over_meta["nb_frames"],
        base_ext=base_meta.get("ext", ".jpg"), over_ext=over_meta.get("ext", ".png"),
        base_fps=base_meta["fps"], over_fps=over_meta["fps"],
        base_name=base_meta.get("source_name", "base"),
        over_name=over_meta.get("source_name", "overlay"),
        base_audio="true" if base_meta.get("has_audio") else "false",
        over_audio="true" if over_meta.get("has_audio") else "false")
    with open(os.path.join(outdir, "viewer.html"), "w") as fh:
        fh.write(html)


# ---------------------------------------------------------------------------
# SEQUENCE VIEWER — several scenes on ONE timeline
# ---------------------------------------------------------------------------
#
# A scene on its own cannot show the thing that most often goes wrong: how one
# scene JOINS the next. A hard cut, a pose that jumps, a voice that starts
# before the picture settles — all of them live at a boundary, and a
# single-clip viewer has no boundaries in it.
#
# Each scene keeps its OWN extraction and its own cache; the manifest maps a
# global frame to (scene, local frame). Concatenating frames into one new cache
# would have been simpler and would have cost both the reuse and the ability to
# say WHICH scene is on screen.
#
# Frames are addressed as `../<slug>/frames/…`. Each clip keeps the SAME
# standalone cache it would get on its own, so opening a scene by itself and
# opening it in a timeline share one extraction instead of doubling it.

SEQ_TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>
  /* The viewer's border reports WHICH LAYERS ARE TICKED, so it answers "what
     will + and - touch here" without reading down the list:
         both ticked    green   --both
         segment only   blue    --seg
         overlay only   purple  --over
         neither        yellow  --none    (nothing will happen)
     Blue is also the segment tick's own colour, so the border and the checkbox
     that caused it are never two different colours for the same thing. */
  :root {{ --box: {box}px; --base:#2ecc40; --over:#a06cff; --active:var(--base);
          --both:#2ecc40; --seg:#4fc3f7; --none:#e8c249; }}
  body {{ margin:0; background:#141414; color:#eee;
         font:14px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
  .wrap {{ padding:14px; display:flex; gap:16px; align-items:flex-start;
           justify-content:center; }}
  .left {{ display:flex; flex-direction:column; gap:10px; align-items:center; }}
  #stage {{ position:relative; width:var(--box); height:var(--box);
            background:#232323; border:2px solid var(--active); border-radius:8px;
            overflow:hidden; transition:border-color .12s; }}
  #baseImg {{ position:absolute; left:0; width:var(--box); top:50%;
              transform:translateY(-50%); }}
  #overImg {{ position:absolute; left:0; top:0; width:var(--box); height:var(--box); }}
  /* Dim whichever layer is NOT being edited, so the active one is unmistakable. */
  .dimBase #baseImg {{ opacity:.35; }}
  .dimOver #overImg {{ opacity:.35; }}
  .row {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap;
          justify-content:center; }}
  .bar {{ width:var(--box); }}
  /* ONE coordinate space for the bar. A native range thumb's CENTRE travels
     from half-a-thumb in to half-a-thumb short of the end, but the ticks and
     the scene blocks were laid out across the FULL width -- so a mark and the
     pointer could only ever agree at the exact middle, and drifted by up to
     half a thumb at the ends. Clicking a mark left the pointer visibly beside
     it, and a loop looked out of step with its own boundary.
     The thumb is given an explicit size here so the inset is a known number
     rather than whatever the browser picked, and the tick layer and the scene
     bar are inset by half of it. */
  :root {{ --thumb:14px; --halfthumb:7px; }}
  /* margin:0 matters as much as the inset. Chrome gives a range input a
     default 2px margin, so the slider box sat 2px right of the tick layer and
     every mark was out by a constant 2px even once the scaling was right. */
  input[type=range] {{ -webkit-appearance:none; appearance:none; margin:0;
                      width:100%; height:var(--thumb); background:transparent;
                      accent-color:var(--active); }}
  input[type=range]::-webkit-slider-runnable-track {{
      height:6px; border-radius:3px; background:#39424a; }}
  input[type=range]::-webkit-slider-thumb {{ -webkit-appearance:none; appearance:none;
      width:var(--thumb); height:var(--thumb); border-radius:50%;
      background:var(--active); border:none; margin-top:-4px; }}
  input[type=range]::-moz-range-track {{ height:6px; border-radius:3px; background:#39424a; }}
  input[type=range]::-moz-range-thumb {{ width:var(--thumb); height:var(--thumb);
      border-radius:50%; background:var(--active); border:none; }}
  button {{ background:#2c3236; color:#eee; border:1px solid #4a5259;
            border-radius:6px; padding:7px 11px; font-size:14px; cursor:pointer; }}
  button:hover {{ border-color:var(--active); }}
  button:disabled {{ opacity:.4; cursor:default; }}
  button.on {{ background:var(--active); border-color:var(--active); color:#111;
               font-weight:600; }}
  .tgl {{ display:flex; gap:0; border:1px solid #4a5259; border-radius:8px;
          overflow:hidden; }}
  .tgl button {{ border:0; border-radius:0; padding:8px 16px; }}
  #tBase.on {{ background:var(--base); color:#111; }}
  #tOver.on {{ background:var(--over); color:#111; }}
  .meta {{ font-size:12px; color:#9aa; }}
  .meta b {{ color:#eee; }}
  #ticks {{ position:relative; height:12px; margin:0 var(--halfthumb); }}
  .tick {{ position:absolute; top:0; width:3px; height:12px;
           background:var(--active); transform:translateX(-50%);
           border-radius:1px; cursor:pointer; }}
  .tick:hover {{ filter:brightness(1.4); }}
  .tick::before {{ content:''; position:absolute; left:-6px; right:-6px;
                   top:-4px; bottom:-4px; }}
  /* The scene boundaries, drawn ON the timeline. Seeing where a join falls is
     most of the point of putting several scenes on one bar. */
  #segbar {{ position:relative; height:16px; display:flex; gap:1px;
             margin:0 var(--halfthumb) 2px; }}
  .segblk {{ height:100%; background:#2a3136; border-radius:2px; font-size:9px;
             color:#8a949b; overflow:hidden; white-space:nowrap; text-align:center;
             line-height:16px; cursor:pointer; }}
  .segblk:hover {{ background:#39434a; color:#dfe4e7; }}
  .segblk.cur {{ background:#1f5c2e; color:#eaffef; }}
  /* 270 -> 360: the row carries six columns now (tick, number, name,
     duration, then a lock+count for EACH layer). At 270 the name was
     ellipsed down to one or two letters, which made the list useless. */
  /* 360 -> 412: the +/- pair added two more columns (16px each plus a 6px
     gutter), and at 360 the duration ran into the first lock. */
  /* Wide enough to hold the control block at the width it already had (666px,
     widest row 644px). The controls moved here from under the viewer, and the
     point of moving them was to stop the page growing downwards -- so the
     column is sized to fit them on one line each, not the other way round.
     Fixed on purpose: this is a tool for one monitor, not a responsive page. */
  .right {{ width:700px; flex:none; background:#1b1f22; border:1px solid #3a4248;
            border-radius:8px; padding:10px; max-height:94vh;
            display:flex; flex-direction:column; }}
  /* Only the scene list scrolls. The controls sit under it and must stay put --
     a Save button that scrolls out of reach is worse than a shorter list. */
  #sceneList {{ overflow:auto; flex:1 1 auto; min-height:0; }}
  .right h4 {{ margin:0 0 8px; font-size:12px; color:#9aa; font-weight:600;
               text-transform:uppercase; letter-spacing:.04em; text-align:center; }}
  .scene {{ display:flex; gap:7px; align-items:baseline; padding:5px 6px; overflow:hidden;
            border-radius:6px; font-size:13px; }}
  .scene .num {{ color:#8a949b; min-width:18px; text-align:right; }}
  /* min-width:0, not 88px. An 88px floor on the one flexible cell meant that
     below a certain panel width the row could not shrink at all -- so instead
     of the name getting shorter, the whole row overflowed and the duration
     slid under the first checkbox. The name is the only thing here that can
     lose characters harmlessly, so it is the only thing allowed to. */
  .scene .lab {{ flex:1 1 0; min-width:0; color:#dfe4e7; overflow:hidden;
                text-overflow:ellipsis; white-space:nowrap; }}
  /* Everything after the name holds its size: a number cut in half is worse
     than a name cut short. */
  .scene .num, .scene .dur {{ flex:none; }}
  .scene .dur {{ color:#8a949b; font-size:12px; }}
  .scene.inseq {{ background:#1d2a20; }}
  /* Off the timeline, still on the list. Dimmed rather than hidden: the scene
     exists, it is simply not in this join. */
  .scene.offseq {{ opacity:.5; }}
  .scene.offseq:hover {{ opacity:.85; }}
  .scene.cur {{ background:#1f5c2e; opacity:1; }}
  .scene .pick {{ accent-color:#2ecc40; margin:0 2px 0 0; cursor:pointer; flex:none; }}
  .scene .ovv {{ font-size:10px; padding:0 4px; border:1px solid #444; border-radius:3px; }}
  #rebuildBtn {{ width:100%; margin-top:8px; font-size:12px; }}
  #rebuildBtn:not(:disabled) {{ background:#1f5c2e; border-color:#2ecc40; }}
  /* A FIXED height, not a max. It used to be `max-height:300px`, so the panel
     was as tall as its contents until they passed 300 — and the active row
     swaps a one-line label for a textarea, which is more than twice as tall.
     Every scene boundary therefore changed the panel's own height and shoved
     the page up and down under the playhead. Now the box never moves and the
     rows scroll inside it.

     Sized for about SEVEN rows: six collapsed at ~29px plus the open one at
     ~66px, under a 30px heading. */
  #vtt {{ width:var(--box); border:1px solid #3a4248; border-radius:8px;
          background:#1b1f22; height:270px; overflow:hidden;
          display:flex; flex-direction:column; }}
  #vttHead {{ flex:none; background:#1b1f22;
              padding:7px 10px; border-bottom:1px solid #3a4248;
              font-size:11px; letter-spacing:.05em; text-transform:uppercase;
              color:#9aa; font-weight:600; }}
  /* `position:relative` so a row's offsetTop is measured against THIS box —
     the centring maths reads it, and against any other offsetParent it would
     scroll to the wrong place.

     The padding is three rows deep at each end, which is what lets scene 1 and
     the last scene sit in the middle like every other one instead of being
     stuck against an edge. */
  #vttRows {{ flex:1 1 auto; overflow-y:auto; position:relative;
              padding-block:87px; scroll-behavior:smooth; }}
  #vttSum {{ float:right; text-transform:none; letter-spacing:0; color:#7d868d;
             font-weight:400; }}
  .vt {{ display:grid; grid-template-columns:22px 1fr auto; gap:2px 8px;
         padding:6px 10px; border-bottom:1px solid #262c31; cursor:text;
         text-align:left; align-items:center; min-height:29px; }}
  .vt:last-child {{ border-bottom:none; }}
  .vt .vn {{ color:#8a949b; font-size:12px; text-align:right; }}
  .vt .vl {{ color:#cfd6da; font-size:14px; overflow:hidden;
             text-overflow:ellipsis; white-space:nowrap; }}
  /* The ACTIVE line wraps. One-line-with-an-ellipsis is right for the rows you
     are skimming, and useless for the one being spoken: most of the line is
     off the end, so the word being highlighted would be hidden more often
     than not. The panel is a fixed height now, so a taller row scrolls
     instead of moving the page. */
  .vt.on .vl {{ white-space:normal; overflow:visible; line-height:1.45; }}
  /* The word being spoken, near enough. Its position is ESTIMATED from the
     scene's elapsed time and the voice's measured words-per-second — there are
     no per-word timings anywhere in this pipeline, and HeyGen does not return
     any. It is an aid for lining the picture up against the line, not a
     measurement: a long word and a short one get the same slice. */
  .vt .wnow {{ background:#f5e08a; color:#1b1f22; border-radius:3px;
               padding:0 2px; }}
  .vt .vt3 {{ font-size:11px; font-variant-numeric:tabular-nums; color:#8b949c;
              white-space:nowrap; }}
  /* The gap is the number the table exists for: how long she sits frozen with
     nothing to say. Past the 2.5s threshold vtt.py flags, it turns. */
  .vt .gapOk {{ color:#6f9c6f; }}
  .vt .gapBad {{ color:#e08c60; }}
  .vt .gapNeg {{ color:#e05c5c; font-weight:600; }}
  .vt textarea {{ grid-column:2 / span 2; background:#151a1d; color:#dfe4e7;
                  border:1px solid #333b41; border-radius:5px; padding:5px 7px;
                  font:inherit; font-size:14px; line-height:1.35; resize:vertical;
                  width:100%; box-sizing:border-box; display:none; }}
  /* Only the scene under the pointer opens its editor. Every line as a textarea
     at once is a wall of boxes, and only one of them is the line being watched. */
  .vt.on {{ background:#1f262b; }}
  /* Being the scene under the playhead no longer means "being edited". The
     active row now shows its LINE, so the spoken word can be highlighted in
     it; the box opens when you click the row, and closes when you click away.
     A textarea cannot carry a highlight inside it. */
  .vt.editing .vl {{ display:none; }}
  .vt.editing textarea {{ display:block; }}
  .vt.on .vn {{ color:#dfe4e7; font-weight:600; }}
  .vt textarea:focus {{ outline:none; border-color:#2ecc40; }}
  .vt.dirty textarea {{ border-color:#e0c060; }}
  .vt .vtodo {{ grid-column:2 / span 2; font-size:11px; color:#e08c60; }}
  #status {{ font-size:12px; color:#e0c060; min-height:16px; white-space:pre-line;
             text-align:center; max-width:100%; margin-top:8px; }}
  /* The player's own name, at the foot of the page. Three players share this
     server and look alike at a glance; this is what says which one you are in
     before you touch a control. */
  .playerName {{ margin:22px auto 4px; text-align:center; font-size:12px;
                letter-spacing:.16em; text-transform:uppercase; color:#6d757b; }}
  /* Matched to the row's buttons so the transport reads as one control set.
     Lit whenever the rate is not 1x, so an odd speed cannot pass for normal. */
  /* 34px, not 30: it sits in a row of 34px buttons, and a control four pixels
     shorter than its neighbours reads as a different kind of thing. */
  #rateSel {{ background:#2c3236; color:#eee; border:1px solid #4a5259; border-radius:6px;
             height:34px; font-size:13px; font-family:inherit; padding:0 6px; cursor:pointer; }}
  #rateSel:hover {{ background:#373e43; }}
  #rateSel.off1 {{ background:#1f5c2e; border-color:#2ecc40; color:#fff; }}
  /* Right-hand pair on every scene row: an edit lock, then that segment's
     frame count. The lock is a SEPARATE control from the tick on the left —
     that one says "show me this scene", this one says "let me change it". */
  .edcb {{ margin:0 0 0 6px; accent-color:var(--seg); flex-shrink:0; cursor:pointer; }}
  /* FIXED width, not min-width: the totals row carries four digits where a
     scene carries three, and a column that grows to fit its widest cell shunts
     everything after it out of line. Wide enough for "~2827". */
  .frames {{ font-variant-numeric:tabular-nums; font-size:11px; color:#8b949c;
            width:44px; flex:none; text-align:right; }}
  /* A count read from the file header rather than a real extraction can be one
     out, so it shows a ~ and is never passed off as exact. */
  .frames.est {{ color:#6d757b; font-style:italic; }}
  .scene.locked .lab {{ opacity:.5; text-decoration:line-through; }}
  /* The overlay pair is tinted to match the purple the overlay layer uses
     everywhere else, so which lock belongs to which layer is readable without
     hovering. */
  .edcb.ov {{ accent-color:#a06cd5; }}
  .frames.ov {{ color:#9d86bd; }}
  .frames.ov.est {{ color:#6f5f87; }}
  .scene.lk-base .lab {{ opacity:.6; }}
  .scene.lk-both .lab {{ opacity:.45; text-decoration:line-through; }}
  /* Totals foot the list. Spacers stand in for the three checkbox columns so
     each total sits under the column it adds up -- a totals row that does not
     line up with its column is just another number on the page. */
  .scene.totals {{ border-top:1px solid #3a4248; margin-top:4px; padding-top:7px;
                  font-weight:600; color:#cfd6dc; cursor:default; background:none; }}
  .scene.totals .lab {{ color:#8b949c; font-weight:500; }}
  .scene.totals .frames {{ color:#a9d8ee; }}
  .scene.totals .frames.ov {{ color:#c3a9e0; }}
  /* A spacer must reproduce its checkbox's MARGINS as well as its width.
     Without them the flexible middle column swallowed the 14px difference
     and every total sat 6px right of the column it was summing. */
  .cbpad {{ width:13px; flex:none; }}
  .cbpad.pk {{ margin-right:2px; }}   /* mirrors .pick  */
  .cbpad.ed {{ margin-left:6px; }}    /* mirrors .edcb  */
  .cbpad.btn {{ width:16px; margin-left:6px; }}  /* mirrors .rowbtn */
  /* Row +/- : square, checkbox-sized, sitting in the same rhythm as the two
     locks they act on. Enabled only on the scene under the playhead, because
     that is the only scene with a current frame to duplicate. */
  .rowbtn {{ width:16px; height:16px; flex:none; margin-left:6px; padding:0;
            border:1px solid #55606a; border-radius:3px; background:#2c3236;
            color:#cfd6dc; font:600 12px/1 -apple-system,sans-serif;
            display:inline-flex; align-items:center; justify-content:center;
            cursor:pointer; }}
  .rowbtn:hover:not(:disabled) {{ background:#3a4248; }}
  .rowbtn.plus:not(:disabled)  {{ border-color:#2ecc40; color:#8ee89b; }}
  .rowbtn.minus:not(:disabled) {{ border-color:#e05555; color:#f0a0a0; }}
  .rowbtn:disabled {{ opacity:.25; cursor:default; }}
  /* Four labelled rows. The label is a fixed column so the controls start on
     the same x in every row and the rows read as a stack, not a pile. */
  .ctlrow[data-r="3"] button {{ border-color:#4a5259; }}
  .vsep {{ width:1px; height:22px; background:#3a4248; margin:0 4px; flex:none; }}
  /* Row 4 states what is selected, so it is read, not clicked. */
  .ctlrow.report {{ align-items:flex-start; }}
  /* The player's name, centred and given some weight — it is the page's title. */
  .playerName {{ text-align:center; font-size:15px; font-weight:700;
                letter-spacing:.14em; color:#8b949c; margin:22px auto 6px; }}
  /* One box around the controls, and a box around each row inside it. The
     rows are four different KINDS of action, and an outline each is what stops
     "step a frame" and "overwrite a file" reading as one continuous strip. */
  /* Contrast measured, not eyeballed. The first attempt used #3a4248 and
     #2f373d, which are 1.69:1 and 1.37:1 against their own fills -- below the
     ~1.5:1 where an edge stops being visible at all, so the boxes were there
     in the DOM and invisible on screen. A border needs roughly 3:1 to read. */
  #ctls {{ border:1px solid #66727c; border-radius:9px; padding:10px;   /* 3.52:1 */
          margin-top:10px; background:#171b1e; }}
  .ctlrow {{ display:flex; align-items:center; gap:7px;
            border:1px solid #66737d; border-radius:7px;                /* 3.41:1 */
            padding:7px 9px; background:#1b1f22; }}
  .ctlrow + .ctlrow {{ margin-top:8px; }}
  /* Pin the line box so a control's HEIGHT comes from the rule, not from
     whichever glyph it happens to contain: the button holding a diamond was a
     pixel taller than its plain-text neighbours. */
  .ctlrow button, .ctlrow #loopLbl, .ctlrow select {{ line-height:18px; }}
  /* Row 3 writes files, so its box is the one that stands out. */
  .ctlrow[data-r="3"] {{ border-color:#8b98a3; }}                        /* 5.62:1 */
  /* The loop control is a toggle in a row of buttons, so it is shaped like
     one. The checkbox itself still does the work and still takes focus; it is
     just no longer a bare tick sitting between two buttons. */
  /* Same box as `button` — padding 7px 11px, 14px text, 1px border, 6px
     radius — rather than a hand-picked height. A fixed height guessed at 30px
     against the buttons' 33px, which is exactly the kind of 3px that makes a
     row look assembled from spare parts. */
  #loopLbl {{ display:inline-flex; align-items:center; gap:6px; cursor:pointer;
             padding:7px 11px; font-size:14px;
             background:#2c3236; color:#eee;
             border:1px solid #4a5259; border-radius:6px; }}
  #loopLbl:hover {{ background:#373e43; }}
  #loopLbl:has(#loopChk:checked) {{ background:#1f5c2e; border-color:#2ecc40; color:#fff; }}
  #loopLbl:has(#loopChk:focus-visible) {{ outline:2px solid #7aa7ff; outline-offset:1px; }}
  #loopChk {{ margin:0; accent-color:#2ecc40; }}
  /* Undo and Save sit at the end of a row, after the two +/- buttons. Same
     16px box so the row keeps one rhythm. Greyed when the scene has nothing
     to undo or nothing to save -- which is the same condition. */
  .histbtn {{ width:16px; height:16px; flex:none; margin-left:6px; padding:0;
             border:1px solid #55606a; border-radius:3px; background:#2c3236;
             color:#cfd6dc; font:600 10px/1 -apple-system,sans-serif;
             display:inline-flex; align-items:center; justify-content:center;
             cursor:pointer; }}
  .histbtn:hover:not(:disabled) {{ background:#3a4248; }}
  .histbtn.undo:not(:disabled) {{ border-color:#e0a93f; color:#e8c98a; }}
  .histbtn.save:not(:disabled) {{ border-color:#2e8ecc; color:#8fc9ee; }}
  .histbtn:disabled {{ opacity:.25; cursor:default; }}
  /* EXCEPT when it is dirty. A scene held by the renumber lock still HAS unsaved
     work, and fading it to a quarter says the opposite — it looks exactly like a
     scene with nothing pending. Dimmed enough to read as "not this button", lit
     enough to read as "there is work here". */
  .histbtn.save.dirty:disabled {{ opacity:.7; cursor:not-allowed; }}
  /* PRISTINE vs DIRTY, said in colour rather than only in opacity. A greyed
     icon reads as "not available"; it does not read as "this scene has three
     unsaved changes". The amber is the same amber the segment checkboxes use
     for work in progress, so the two mean one thing across the page. */
  .histbtn.save {{ position:relative; }}
  .histbtn.save.dirty {{ background:#4a3a18; border-color:#e0a93f; color:#ffdc9a;
                        font-weight:700; }}
  .histbtn.save.dirty:hover {{ background:#5c4820; }}
  .histbtn.save.dirty::after {{ content:''; position:absolute; top:-3px; right:-3px;
                        width:5px; height:5px; border-radius:50%;
                        background:#e0a93f; }}
  /* Actions that apply to the LIST rather than to one row, kept below the
     rebuild button and boxed so they read as list-level, not row-level. */
  #bulk {{ margin-top:8px; padding-top:8px; border-top:1px solid #3a4248;
          display:flex; flex-direction:column; gap:6px; }}
  .bulkrow {{ display:flex; gap:6px; }}
  .bulkrow button {{ flex:1; }}
  #balanceBtn, #backupBtn {{ width:100%; }}
  #backupBtn {{ margin-top:6px; }}
  /* GREEN when a join or split has left a renumber note outstanding — the one
     moment this button has a second job to do, and the moment it is easiest to
     walk away from. It stays enabled the rest of the time: a backup is worth
     taking whenever, and gating it behind a rare event would put the only
     revert this data has behind a door. */
  #backupBtn.pending {{ border-color:#2ecc40; color:#dff5e2;
                        box-shadow:0 0 0 1px rgba(46,204,64,.35); }}
  #balanceBtn:not(:disabled) {{ border-color:#4a8fbf; color:#cfe6f5; }}
  #balNote {{ font-size:11px; line-height:1.5; color:#8b949c; }}
  #balNote b {{ color:#dfe4e7; }}
  #balNote .ok {{ color:#8ee89b; }}
  #balNote .skip {{ color:#e0a93f; }}
  /* Row 4: two fixed rows of two fixed columns. Its height is pinned so the
     control block above it cannot move while you scrub. */
  .ctlrow.report {{ background:#161a1d; height:52px; align-items:stretch; overflow:hidden; }}
  #rep {{ display:grid; grid-template-columns:1fr 1fr; grid-auto-rows:22px;
         align-items:center; column-gap:18px; width:100%;
         font-size:11px; color:#9aa4ae; font-variant-numeric:tabular-nums; }}
  #rep .rc {{ display:flex; align-items:baseline; gap:8px; min-width:0; overflow:hidden; }}
  #rep .rk {{ flex:none; width:58px; color:#6d757b;
             text-transform:uppercase; letter-spacing:.1em; font-size:9px; }}
  #rep .rv {{ min-width:0; overflow:hidden; white-space:nowrap; text-overflow:ellipsis; }}
  #rep .rv.seg b {{ color:#a9d8ee; }}
  #rep .rv.ovl b {{ color:#c3a9e0; }}
  #rep .sep {{ color:#6d757b; margin:0 6px; }}
  #rep .off {{ color:#6d757b; font-style:normal; }}
  /* The scene name is the one thing here that can be any length, so it is the
     one thing that truncates. */
  #rep .nm {{ display:inline-block; max-width:190px; overflow:hidden;
             text-overflow:ellipsis; white-space:nowrap; vertical-align:bottom; }}
  /* Delayed tooltip. Two seconds is long enough that it never interrupts
     someone who knows the control, and short enough to answer someone who is
     hesitating over it. */
  #tip {{ position:fixed; z-index:99; max-width:320px; padding:7px 10px;
         background:#0f1214; color:#dfe4e7; border:1px solid #66727c;
         border-radius:6px; font-size:12px; line-height:1.45;
         box-shadow:0 6px 20px rgba(0,0,0,.55); pointer-events:none;
         opacity:0; transition:opacity .12s ease; }}
  #tip.on {{ opacity:1; }}
  #tip b {{ color:#8ee89b; }}
  /* One modal, used for anything that has to be NAMED and confirmed before it
     happens — join today, split when it lands. */
  #modal {{ position:fixed; inset:0; z-index:200; display:none;
           background:rgba(8,10,12,.72); align-items:center; justify-content:center; }}
  #modal.on {{ display:flex; }}
  .mbox {{ width:520px; max-width:92vw; background:#171b1e; color:#dfe4e7;
          border:1px solid #66727c; border-radius:10px; padding:18px 20px;
          box-shadow:0 18px 50px rgba(0,0,0,.6); }}
  .mbox h5 {{ margin:0 0 10px; font-size:15px; font-weight:700; letter-spacing:.02em; }}
  #mBody {{ font-size:12px; line-height:1.6; color:#9aa4ae; margin-bottom:14px; }}
  #mBody b {{ color:#dfe4e7; }}
  #mBody .warn {{ color:#e0a93f; }}
  #mBody ul {{ margin:8px 0 0; padding-left:18px; }}
  .mlab {{ display:block; font-size:10px; letter-spacing:.12em; text-transform:uppercase;
          color:#6d757b; margin-bottom:5px; }}
  #mName {{ width:100%; box-sizing:border-box; background:#0f1214; color:#dfe4e7;
           border:1px solid #4a5259; border-radius:6px; padding:8px 10px;
           font:14px/1.2 ui-monospace,Menlo,monospace; }}
  #mName:focus {{ outline:2px solid #7aa7ff; outline-offset:1px; }}
  #mErr {{ min-height:16px; font-size:11px; color:#e05555; margin-top:6px; }}
  .mrow {{ display:flex; gap:8px; justify-content:flex-end; margin-top:12px; }}
  #mOk {{ border-color:#2ecc40; color:#cdf3d4; }}
  /* An action and the tracks it acts on, joined into one control. The border
     colour is the SAME language the viewer frame and the row ticks already
     use: green for both tracks, blue for the segment, purple for the overlay.
     One idea, said the same way everywhere. */
  /* ONE control, not a button welded to a dropdown. The border belongs to the
     wrapper and is the only thing that reports which tracks are chosen —
     there is no state word on the face of it, because the colour already says
     it in the same language the viewer frame and the row ticks use.
     The select is invisible over a caret: it still opens the native list with
     its full labels, it just does not print the current value on the button. */
  .act {{ display:inline-flex; align-items:center; background:#2c3236;
         border:1px solid #4a5259; border-radius:6px; overflow:hidden; }}
  .act > button {{ border:0; border-radius:0; background:none; color:inherit; }}
  .act .caret {{ position:relative; display:inline-flex; align-items:center;
                align-self:stretch; padding:0 8px 0 4px;
                color:inherit; opacity:.7; cursor:pointer; }}
  /* Drawn, not a text triangle: a glyph renders at whatever weight the font
     feels like and sits off the optical centre. This one inherits the state
     colour through currentColor, so it changes with the border for free. */
  .act .chev {{ width:10px; height:6px; display:block; }}
  .act .caret:hover .chev {{ transform:translateY(1px); }}
  @media (prefers-reduced-motion:no-preference) {{
    .act .chev {{ transition:transform .12s ease; }}
  }}
  .act .caret:hover {{ opacity:1; }}
  .act .caret select {{ position:absolute; inset:0; width:100%; height:100%;
                       opacity:0; cursor:pointer; border:0; }}
  .act[data-trk="both"]    {{ border-color:var(--both); color:#cdf3d4; }}
  .act[data-trk="base"]    {{ border-color:var(--seg);  color:#cfe8f7; }}
  .act[data-trk="overlay"] {{ border-color:var(--over); color:#e4d3f5; }}
</style></head><body>
<div class="wrap">
 <div class="left">
  <div id="stage"><img id="baseImg"><img id="overImg"></div>
  <div class="bar">
    <div id="segbar"></div>
    <div id="ticks"></div>
    <input id="slider" type="range" min="1" max="{total}" value="1" step="1" title="The whole timeline, every scene end to end. Drag to scrub, or click anywhere to jump there. The arrow keys step one frame from wherever you land, which is how you find the exact frame something happens on.">
  </div>
  <div class="meta" id="pos"></div>

  <!-- The VTT — Video Timing Table, NOT WebVTT subtitles. Sarah's line per
       scene, what it costs to say, and the gap left over. It sits here because
       this is the space the controls vacated, and because a line is easiest to
       judge while looking at the footage it plays over. -->
  <div id="vtt">
    <div id="vttHead">VTT <span id="vttSum"></span></div>
    <div id="vttRows"></div>
  </div>

  
 </div>
 <div class="right">
   <h4>Time Line Scenes</h4>
   <div id="sceneList"></div>
   <button id="rebuildBtn" disabled title="Rebuild the timeline from the ticked scenes. The timeline is a different set of frames afterwards, so this is a navigation, not an edit — nothing you have changed is lost.">Tick at least one scene</button>
   <div id="bulk">
     <div class="bulkrow">
       <button id="selAll" title="Tick every scene in the list. Pair it with Rebuild to put the whole video on one timeline.">Select all</button>
       <button id="selNone" title="Untick every scene. Then tick just the few you want to compare, and rebuild.">Unselect all</button>
     </div>
     <button id="balanceBtn" title="Make each ticked scene's two tracks the same length, by repeating the LAST frame of whichever is shorter. The last frame is the settled end of the shot, so the repeat is invisible. Undoable per scene.">&#8646; Update Frame Imbalance</button>
     <button id="backupBtn" title="Copy every scene folder in sandbox/ into sandbox/z_History/26-8-27_v1 &mdash; a whole-set backup, because none of this is in git. A COPY: your scenes stay where they are. If a join or split has renumbered the scenes, it also clears that note, which is the only thing left outstanding after one.">&#9707; Backup Scenes</button>
     <div id="balNote"></div>
   </div>

   <!-- Four rows, each answering one question, in the order the work happens:
        1. where am I    2. what is marked    3. change it    4. what is selected
        They were one undifferentiated pile before, so "play a bit" and
        "overwrite a file" sat side by side. Under the viewer until the block
        moved here, which is why the page used to run off the bottom. -->
   <div id="ctls">
  <div class="ctlrow" data-r="1"><button id="playBtn" title="Play or pause the timeline. Space does the same. Playback starts from wherever the pointer is, so drag it first to watch a particular moment.">&#9654; Play</button>
    <button id="muteBtn" title="Mute the narration. The picture is unaffected — useful when you are judging motion and the voice is a distraction.">&#128266;</button>
    <select id="rateSel" title="Playback speed. Slow right down to judge a seam: at 25fps a cut is over in 40ms, and 0.125x stretches that to 320ms. Below 0.25x the browser will not play audio, so those speeds are silent.">
      <option value="2">2x</option>
      <option value="1" selected>1x</option>
      <option value="0.5">0.5x</option>
      <option value="0.25">0.25x</option>
      <option value="0.125">0.125x</option>
    </select>
    <button id="p10" title="Back 10 frames. Hold to scan backwards quickly without losing your place.">&#9664;&#9664;</button>
    <button id="p1" title="Back one frame. This is the control for finding the exact frame a change happens on.">&#9664;</button>
    <button id="n1" title="Forward one frame. Step through a transition one frame at a time to see where it really begins.">&#9654;</button>
    <button id="n10" title="Forward 10 frames. Quicker than dragging when you are a little way from what you want.">&#9654;&#9654;</button>
    <button id="prevScene" title="Jump to the start of the previous scene. Keyboard: [">&#124;&#9664; scene</button>
    <button id="nextScene" title="Jump to the start of the next scene. Keyboard: ]">scene &#9654;&#124;</button>
  </div>

  <div class="ctlrow" data-r="2"><button id="markBtn" title="Mark or unmark this frame (keyboard: m). Marks divide a scene into ZONES — the span between two marks — which is what Loop Zone plays and what + Zone and - Zone act on.">&#9670; Mark / Unmark</button>
    <button id="prevMark" title="Jump back to the previous mark. Marks show as green ticks on the bar; you can also click a tick directly.">&#91; prev mark</button>
    <button id="nextMark" title="Jump forward to the next mark. Marks show as green ticks on the bar; you can also click a tick directly.">next mark &#93;</button>
    <!-- Off by default: opening a timeline and pressing Play should play the
         timeline once at 1x, not start looping a zone the user has not asked
         for yet. Loop Zone is a thing you turn ON to study a seam. -->
    <label id="loopLbl" title="Loop the zone the pointer is inside — the span between the marks either side of it. With no marks it loops the whole scene. Turn this on to watch one seam over and over while you trim it.">
      <input id="loopChk" type="checkbox" title="Loop the zone the pointer is inside — the span between the marks either side of it. With no marks it loops the whole scene."><span>&#8635; Loop Zone</span></label>
    <span class="act" id="joinAct">
      <button id="joinBtn" title="Join every scene on the timeline into ONE new scene. You are asked to name it first and shown exactly what will be merged. Scene numbers are rewritten 1..N afterwards, so from then on scenes must be saved as a set.">Join</button>
      <span class="caret"><svg class="chev" viewBox="0 0 10 6" aria-hidden="true"><path d="M1 1l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg><select id="joinTrk" title="Which tracks the join acts on. Both is the normal case and the button turns green for it; pick one track alone and the button takes that track's colour. A track you do not pick is NOT carried into the joined scene.">
          <option value="both" selected>both</option>
          <option value="base">segment</option>
          <option value="overlay">overlay</option>
        </select></span>
    </span>
    <span class="act" id="splitAct">
      <button id="splitBtn" title="Split the scene under the pointer in two, at the frame on screen. You are asked to name both halves. Every scene is renumbered afterwards, so from then on scenes must be saved as a set.">Split</button>
      <span class="caret"><svg class="chev" viewBox="0 0 10 6" aria-hidden="true"><path d="M1 1l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg><select id="splitTrk" title="Which tracks the split acts on. Both is the normal case and the button turns green for it; pick one track alone and the button takes that track's colour. A track you do not pick stays whole and is not carried into either half.">
          <option value="both" selected>both</option>
          <option value="base">segment</option>
          <option value="overlay">overlay</option>
        </select></span>
    </span>
  </div>

  <div class="ctlrow" data-r="3"><button id="addFrame" title="Duplicate the frame on screen, on whichever tracks this scene has ticked. The copy becomes the frame you are looking at. Use it to hold a still moment for longer.">&#65291; Frame</button>
    <button id="delFrame" title="Delete the frame on screen, on whichever tracks this scene has ticked. The next frame moves into its place, so the timeline appears to step forward.">&#65293; Frame</button>
    <button id="addZone" title="Repeat the whole marked zone once more, on the ticked tracks. Useful for stretching a settled stretch to fit a longer line of narration.">&#65291; Zone</button>
    <button id="delZone" title="Remove the whole marked zone from the ticked tracks. Mark either side of what you want gone, then press this.">&#65293; Zone</button>
    <span class="vsep"></span>
    <button id="copyFrame" title="Copy the frame on screen. It is remembered by POSITION, not as a picture — pasting it later inserts the very same frame, with no re-encoding. Hold Shift as you click to put the picture on the Mac clipboard as well, for pasting into another app.">⧉ Copy</button>
    <button id="pasteFrame" disabled title="Paste the copied frame in after the frame on screen, on the ticked tracks. Nothing is copied yet — press Copy first.">⧉ Paste</button>
    <span class="vsep"></span>
    <button id="cutBtn" title="Write every scene ON THIS TIMELINE that has unsaved edits back over its file in sandbox/. Each file keeps its previous version in its own scene's z_History/. No whole-set backup is taken and no renumber note is cleared &mdash; Backup Scenes does both of those.">&#128190; Save Scenes</button>
    <button id="saveBtn" title="Write every scene with unsaved edits back over its file in sandbox/. Same set as Save Scenes: a rebuild reloads the page, so a scene taken off the timeline takes its pending edits with it and there is no third set to reach.">&#10515; Save All</button>
  </div>

  <div class="ctlrow report" data-r="4"><span id="rep"></span>
  </div>
  </div>

  <div id="status"></div>
 </div>
</div>
<audio id="audA" preload="auto"></audio>
<div id="tip"></div>
<div id="modal"><div class="mbox">
  <h5 id="mTitle">Name it</h5>
  <div id="mBody"></div>
  <label class="mlab" for="mName" title="Lower-case letters, digits and hyphens. This becomes the scene's FOLDER name in sandbox/ and its label in script.json, so it is what every later tool will call this scene.">New scene name</label>
  <input id="mName" type="text" autocomplete="off" spellcheck="false" title="Lower-case letters, digits and hyphens — no spaces or capitals. It becomes the folder name in sandbox/ and the label in script.json. Enter confirms; Escape cancels.">
  <div id="mErr"></div>
  <div class="mrow">
    <button id="mCancel" title="Close this without changing anything. Nothing has been written yet — a join or split only touches your files once you confirm here.">Cancel</button>
    <button id="mOk" title="Do it. This writes to disk immediately: folders are created and removed in sandbox/ and script.json is rewritten, all in one go. The previous state is archived to z_History/ first, so it is recoverable but not undoable from the editor.">Confirm</button>
  </div>
</div></div>
  <div class="playerName">{player_label}</div>
<script>
  const SEQ = {manifest};
  const ROOT_REL = {root_rel!r};
  const $ = id => document.getElementById(id);
  const pad = n => String(n).padStart(5, '0');
  const status = m => {{ $('status').textContent = m; }};

  // ── the timeline index ────────────────────────────────────────────────
  // Global frame -> which scene, and how far into it. The timeline's length is
  // the sum of every scene's BASE length, because that is what is on screen.
  //
  // Rebuilt, not computed once: adding or deleting a frame changes a scene's
  // length, and every start after it moves. Editing on a stale index would put
  // the NEXT edit into the wrong scene, which is the one failure here that
  // writes to a file.
  let starts = [], total = 0, ver = Date.now();
  function reindex() {{
    starts = []; total = 0;
    for (const s of SEQ) {{ starts.push(total); total += s.base_n; }}
    $('slider').max = Math.max(1, total);
  }}
  function at(g) {{
    let i = 0;
    while (i + 1 < SEQ.length && g > starts[i + 1]) i++;
    return {{ i, local: g - starts[i] }};      // local is 1-based
  }}
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

  function paint() {{
    // The Background/Overlay/Solo row is gone: the scene rows' ticks say which
    // layer an edit touches, so a second control saying it again was one more
    // thing to keep in step. What is left of paint() is the accent colour, so
    // the frame border still shows which layer is being worked on. Both layers
    // are always shown now -- there is no control left to un-solo with, and a
    // view stuck dimmed with no way back is worse than no solo at all.
    // Four states, not two: `which` only ever names ONE layer, so it cannot
    // tell "both ticked" from "segment only" -- and those mean different things
    // for + and -. Read the ticks directly.
    const ci = curI(), cn = (SEQ[ci] || {{}}).n;
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
    $('stage').className = '';
  }}

  function show(g) {{
    g = Math.max(1, Math.min(total, g));
    $('slider').value = g;
    const {{ i, local }} = at(g);
    const s = SEQ[i];
    $('baseImg').src = `../${{s.base_slug}}/frames/frame_${{pad(Math.min(local, s.base_n))}}${{s.base_ext}}?v=${{ver}}`;
    if (s.over_slug) {{
      $('overImg').style.display = '';
      // A scene's avatar is usually SHORTER than its footage; hold her last
      // frame rather than blanking her, which is what the finished video does.
      $('overImg').src = `../${{s.over_slug}}/frames/frame_${{pad(Math.min(local, s.over_n))}}${{s.over_ext}}?v=${{ver}}`;
    }} else {{
      $('overImg').style.display = 'none';
    }}
    $('pos').innerHTML = `timeline <b>${{g}}</b> / ${{total}} &middot; ` +
      `${{((g - 1) / (s.fps || 25)).toFixed(2)}}s of ${{(total / (s.fps || 25)).toFixed(2)}}s`;
    if (i !== curScene) {{ curScene = i; onSceneChange(i, local); loadMarks(i); }}
    // EVERY frame, not only at a boundary. The highlighted word moves WITHIN a
    // scene, and this call used to sit inside the branch above — so the word lit
    // up as a scene started and then sat on the first word until the next one.
    // Cheap to run: paintVtt() returns early per row whose state has not
    // changed, and only re-centres when the scene actually moved.
    paintVtt();
    renderReport();
    paintBar();
  }}
  let curScene = -1;

  function paintBar() {{
    const {{ i }} = at(+$('slider').value);
    const n = SEQ[i].n;
    [...$('segbar').children].forEach((el, k) => el.classList.toggle('cur', k === i));
    // Matched on the scene NUMBER, not the row's position: the list holds every
    // scene now, so position and scene are no longer the same thing.
    [...$('sceneList').children].forEach(el => el.classList.toggle('cur', +el.dataset.n === n));
  }}

  function rebuildBar() {{
    $('segbar').innerHTML = '';
    for (let i = 0; i < SEQ.length; i++) {{
      const s = SEQ[i];
      const b = document.createElement('div');
      b.className = 'segblk'; b.style.flex = String(s.base_n); b.dataset.n = s.n;
      b.textContent = s.n; b.title = `${{s.n}} ${{s.label}} — ${{(s.base_n / (s.fps || 25)).toFixed(2)}}s`;
      b.onclick = () => {{ stop(); show(starts[i] + 1); }};
      $('segbar').appendChild(b);
    }}
    paintBar();
  }}

  // ── break points ──────────────────────────────────────────────────────
  // Kept per CACHE SLUG, which is per scene per layer — the same unit the
  // server stores them in. Drawn at their GLOBAL position so a mark stays under
  // the frame it belongs to as the bar rescales.
  const MARKS = {{}};
  const marksOf = (i, w) => MARKS[slugOf(i, w)] || new Set();

  async function loadMarks(i) {{
    for (const w of ['base', 'overlay']) {{
      const slug = slugOf(i, w);
      if (!slug || MARKS[slug]) continue;
      try {{
        const r = await fetch(`/api/marks?slug=${{slug}}`);
        const d = await r.json();
        MARKS[slug] = new Set(d.marks || []);
      }} catch (e) {{ MARKS[slug] = new Set(); }}
    }}
    renderTicks();
    // The marks arrive AFTER the first paint, and the zone is derived from
    // them, so row 4 and the loop label were still reporting "no marks — zone
    // is the whole scene" on a scene that had four. Anything derived from
    // marks has to be redrawn once they land, not only when the playhead moves.
    renderReport();
  }}

  // Every mark on the active layer, as timeline positions, in order.
  function globalMarks() {{
    const out = [];
    for (let i = 0; i < SEQ.length; i++) {{
      for (const m of marksOf(i)) {{
        // A mark past the end of the scene's FOOTAGE has no place on a timeline
        // measured in footage. It is still stored, and still shown when that
        // scene is opened on its own.
        if (m <= SEQ[i].base_n) out.push(starts[i] + m);
      }}
    }}
    return out.sort((a, b) => a - b);
  }}

  function renderTicks() {{
    const t = $('ticks'); t.innerHTML = '';
    for (const g of globalMarks()) {{
      const {{ i, local }} = at(g);
      const el = document.createElement('div');
      el.className = 'tick';
      el.style.left = ((g - 1) / Math.max(1, total - 1) * 100) + '%';
      el.title = `scene ${{SEQ[i].n}} frame ${{local}} — click to jump`;
      el.addEventListener('mousedown', e => {{ e.preventDefault(); e.stopPropagation(); stop(); show(g); }});
      t.appendChild(el);
    }}
  }}

  // ── editing ───────────────────────────────────────────────────────────
  // Every call carries THIS scene's slug and a frame number local to it. The
  // server never sees a timeline frame, which is what keeps a cut on the
  // timeline identical to the same cut made scene by scene.
  async function api(path, body) {{
    const i = curI(), slug = slugOf(i);
    if (!slug) {{ status(`Scene ${{SEQ[i].n}} has no ${{which}} layer to edit.`); return null; }}
    try {{
      const r = await fetch(path, {{ method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(Object.assign({{ slug }}, body)) }});
      const d = await r.json();
      if (d.error) {{ status('Error: ' + d.error); return null; }}
      return d;
    }} catch (e) {{ status('Error: ' + e); return null; }}
  }}

  $('markBtn').onclick = async () => {{
    const i = curI(), {{ local }} = at(+$('slider').value), slug = slugOf(i);
    if (!slug) {{ status(`Scene ${{SEQ[i].n}} has no ${{which}} layer.`); return; }}
    if (local > lenOf(i)) {{
      status(`Frame ${{local}} is past the end of this scene's ${{which}} layer (${{lenOf(i)}}).`);
      return;
    }}
    const set = MARKS[slug] || (MARKS[slug] = new Set());
    const on = !set.has(local);
    const d = await api('/api/mark', {{ frame: local, on }});
    if (!d) return;
    on ? set.add(local) : set.delete(local);
    status(`${{on ? 'Marked' : 'Unmarked'}} frame ${{local}} of scene ${{SEQ[i].n}} (${{which}}).`);
    renderTicks();
  }};

  // Mark-to-mark runs across the WHOLE timeline, not just this scene — the
  // marks either side of a join are exactly the pair worth stepping between.
  function jumpMark(dir) {{
    const s = globalMarks(), g = +$('slider').value;
    const t = dir > 0 ? s.find(m => m > g) : [...s].reverse().find(m => m < g);
    if (t !== undefined) {{ stop(); show(t); }}
    else status(dir > 0 ? 'No mark after here.' : 'No mark before here.');
  }}
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
  (function tooltips() {{
    const tip = document.getElementById('tip');
    let timer = null, held = null;

    function hide() {{
      clearTimeout(timer); timer = null;
      tip.classList.remove('on');
      if (held) {{ held.el.title = held.text; held = null; }}
    }}
    function show(el, text) {{
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
    }}

    document.addEventListener('mouseover', e => {{
      const el = e.target.closest('[title]');
      if (!el || el === (held && held.el)) return;
      hide();
      const text = el.getAttribute('title');
      if (!text) return;
      held = {{ el, text }};
      el.removeAttribute('title');                       // suppress the native one
      // 3 seconds. Long enough that a tip does not chase the pointer across a
      // row of eight buttons on the way to the one you meant.
      timer = setTimeout(() => show(el, text), 3000);
    }});
    document.addEventListener('mouseout', e => {{
      if (held && !held.el.contains(e.relatedTarget)) hide();
    }});
    // A tip that outlives what it describes is a lie, so anything that moves
    // or changes the page takes it down.
    for (const ev of ['mousedown', 'wheel', 'keydown']) document.addEventListener(ev, hide, true);
    window.addEventListener('blur', hide);
  }})();

  // ── naming modal ────────────────────────────────────────────────────────
  // Anything that CREATES a scene has to be named and confirmed before it
  // happens, because it changes the store's own structure rather than a
  // preview. Join uses it now; split will use the same one.
  function askName(opts) {{
    return new Promise(resolve => {{
      const box = $('modal'), name = $('mName'), err = $('mErr');
      $('mTitle').textContent = opts.title;
      $('mBody').innerHTML = opts.body;
      $('mOk').textContent = opts.ok || 'Confirm';
      name.value = opts.value || '';
      err.textContent = '';
      box.classList.add('on');
      name.focus(); name.select();

      const close = v => {{
        box.classList.remove('on');
        document.removeEventListener('keydown', key, true);
        $('mOk').onclick = $('mCancel').onclick = box.onmousedown = null;
        resolve(v);
      }};
      const submit = () => {{
        const v = name.value.trim().toLowerCase();
        // Checked HERE as well as on the server: the name becomes a folder
        // name, and a bad one should be refused before anything is archived.
        if (!/^[a-z0-9][a-z0-9-]{{0,48}}$/.test(v)) {{
          err.textContent = 'Lower-case letters, digits and hyphens only — this becomes a folder name.';
          name.focus(); return;
        }}
        if ((opts.taken || []).includes(v)) {{
          err.textContent = `There is already a scene called "${{v}}".`;
          name.focus(); return;
        }}
        close(v);
      }};
      const key = e => {{
        if (e.key === 'Escape') {{ e.stopPropagation(); close(null); }}
        if (e.key === 'Enter')  {{ e.stopPropagation(); submit(); }}
      }};
      document.addEventListener('keydown', key, true);
      $('mOk').onclick = submit;
      $('mCancel').onclick = () => close(null);
      box.onmousedown = e => {{ if (e.target === box) close(null); }};
    }});
  }}

  // ── which tracks an action acts on ──────────────────────────────────────
  // One place turns the dropdown into the server's vocabulary, and one place
  // paints the border, so the colour can never disagree with what will happen.
  function tracksOf(selId) {{
    const v = $(selId).value;
    return v === 'both' ? ['segment', 'avatar'] : v === 'base' ? ['segment'] : ['avatar'];
  }}
  function paintAct(selId, wrapId) {{
    $(wrapId).dataset.trk = $(selId).value;
  }}
  for (const [sel, wrap] of [['joinTrk', 'joinAct'], ['splitTrk', 'splitAct']]) {{
    $(sel).onchange = () => paintAct(sel, wrap);
    paintAct(sel, wrap);
  }}

  // ── split ───────────────────────────────────────────────────────────────
  // Splits the scene under the pointer at the frame on screen. The frame on
  // screen becomes the FIRST frame of the second half, so what you are looking
  // at is what the new scene opens on.
  async function splitScene() {{
    const i = curI();
    if (i < 0 || !SEQ[i]) return;
    const s = SEQ[i], n = s.n;
    if (s.in_script === false) {{
      alert(`${{String(n).padStart(2, '0')}}-${{s.label}} is a bookend.\\n\\n`
          + `It is a folder with no row in script.json — the fixed opening or `
          + `closing. A split rewrites the scene list, so it cannot take one.\\n\\n`
          + `Move the pointer to a script scene and split that.`);
      return;
    }}
    const {{ local }} = at(+$('slider').value);
    const trk = tracksOf('splitTrk');

    // Same rule as the join, and for the same reason: a split renumbers every
    // scene after the one it cuts, and it reads the files.
    const dirty = SEQ.filter(x => histOf(x.n).length);
    if (dirty.length) {{
      alert(`Save these scenes before splitting.\\n\\n`
          + dirty.map(x => `  ${{x.n}} ${{x.label}} — ${{histOf(x.n).length}} change(s)`).join('\\n')
          + `\\n\\nA split renumbers every scene after the one it cuts, and reads `
          + `the files on disk. These edits are not on disk yet.\\n\\n`
          + `Use each scene's save icon, or "Save all scenes".`);
      return;
    }}
    const dropped = ['segment', 'avatar'].filter(t => !trk.includes(t))
                      .map(t => t === 'segment' ? 'segment' : 'overlay');
    const lens = {{ segment: s.base_n, avatar: s.over_n || 0 }};
    const bad = trk.filter(t => !(local > 1 && local <= (lens[t] || 0)));
    if (bad.length) {{
      status(`Frame ${{local}} is not inside the ${{bad.join(' and ')}} of scene ${{n}}`
           + ` — move the pointer to a frame both halves can exist either side of.`);
      return;
    }}
    const taken = ALL.map(a => (a.label || '').toLowerCase());
    const base = (s.label || 'scene').slice(0, 40);

    const first = await askName({{
      title: `Split scene ${{n}} at frame ${{local}}`,
      ok: 'Next: name the second half',
      value: `${{base}}-a`.slice(0, 49), taken,
      body:
        `<b>${{n}} ${{s.label || ''}}</b> becomes two scenes, cut so that frame`
        + ` <b>${{local}}</b> is the FIRST frame of the second half.`
        + `<ul>`
        + trk.map(t => `<li>${{t === 'segment' ? 'segment' : 'overlay'}}:`
                     + ` <b>${{local - 1}}</b> + <b>${{lens[t] - local + 1}}</b> frames</li>`).join('')
        + (dropped.length ? `<li class="warn">the <b>${{dropped.join(' and ')}}</b> is NOT carried into`
                          + ` either half &mdash; recoverable from z_History/ only</li>` : '')
        + `<li class="warn">the narration line stays whole with the FIRST half;`
        + ` the second is left empty for you to write</li>`
        + `<li>every scene in the script is renumbered <b>1..N</b></li>`
        + `<li>the folder replaced, and script.json, are copied to <b>z_History/</b> first</li></ul>`
        + `<p class="warn">This changes the store, not just the preview, and cannot be undone from here.</p>`
        + `<p>Name the FIRST half:</p>`
    }});
    if (!first) return;
    const second = await askName({{
      title: `Split scene ${{n}} — second half`,
      ok: 'Split and renumber', value: `${{base}}-b`.slice(0, 49),
      taken: taken.concat([first]),
      body: `First half: <b>${{first}}</b> (${{local - 1}} frames, keeps the narration line).`
          + `<p>Name the SECOND half — the one that opens on frame ${{local}}:</p>`
    }});
    if (!second) return;

    stop();
    status(`Splitting scene ${{n}} at frame ${{local}}…`);
    let d;
    try {{
      const r = await fetch('/api/split', {{ method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ root: ROOT_REL, n, at: local,
                               labels: [first, second], tracks: trk }}) }});
      d = await r.json();
    }} catch (e) {{ status(`Split failed: ${{e}}`); return; }}
    if (d.error) {{ status(`Split failed: ${{d.error}}`); return; }}

    RENUMBERED = true;
    paintSaveBtn();
    const moved = (d.renumbered || []).map(r => `${{r.from}}\u2192${{r.to}}`).join(', ');
    alert(`Split scene ${{d.split}} at frame ${{d.at}} into "${{d.labels[0]}}" and "${{d.labels[1]}}".\n\n`
        + `The narration line stayed with "${{d.line_stayed_with}}" — the second half needs one writing.\n\n`
        + (moved ? `Renumbered: ${{moved}}\n\n` : '')
        + `Previous state archived to:\n${{d.archived_to}}\n\n`
        + `The timeline will reload against the new numbering.`);
    location.href = `/api/open-seq-go?root=${{encodeURIComponent(ROOT_REL)}}`
                  + `&ns=${{encodeURIComponent(String(d.split))}}`;
  }}
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
  async function loadRenumberState() {{
    try {{
      const r = await fetch(`/api/renumber-state?root=${{encodeURIComponent(ROOT_REL)}}`);
      const d = await r.json();
      RENUMBERED = !!d.renumbered;
      paintSaveBtn();
      paintBackupBtn();
      // Said, not enforced. Knowing a join moved the numbers is useful; being
      // stopped from saving one scene because of it was not — every edit made
      // after a join is made under the new numbering, since a join reloads the
      // page. Save each scene when you want to.
      if (RENUMBERED) {{
        const moved = (d.moved || []).map(m => `${{m.from}}\u2192${{m.to}}`).join(', ');
        status(`A join or split renumbered these scenes${{moved ? ` (${{moved}})` : ''}}. `
             + `Each scene still saves on its own.`);
      }}
      renderScenes();
    }} catch (e) {{ /* leave it false: refusing to save on a guess is worse */ }}
  }}

  // A bookend — 00-opening, 99-closing — is a real folder with no row in
  // script.json. Join and Split both rewrite the scene list, so neither can
  // touch one. Caught HERE rather than at the server, because the server sees
  // it only after the naming dialog has been filled in and confirmed: the
  // refusal read as "not scenes in the script: [0]" at the end of the job.
  function bookendsOn(list) {{
    return list.filter(s => s.in_script === false)
               .map(s => `${{String(s.n).padStart(2, '0')}}-${{s.label}}`);
  }}

  async function joinTimeline() {{
    if (SEQ.length < 2) {{ status('A join needs at least two scenes on the timeline.'); return; }}
    const bk = bookendsOn(SEQ);
    if (bk.length) {{
      alert(`This timeline includes ${{bk.length === 1 ? 'a bookend' : 'bookends'}}: `
          + `${{bk.join(', ')}}.\n\n`
          + `A bookend is a folder with no row in script.json — the fixed opening `
          + `and closing. A join rewrites the scene list, so it cannot take one.\n\n`
          + `Rebuild the timeline from script scenes only, then join.`);
      return;
    }}
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
    if (pending.length) {{
      const rows = pending.map(n => {{
        const s = SEQ.find(x => x.n === n);
        const c = histOf(n).length;
        return `  ${{n}} ${{s ? s.label : ''}} — ${{c}} change${{c === 1 ? '' : 's'}}`;
      }}).join('\\n');
      alert(`Save these scenes before joining.\\n\\n${{rows}}\\n\\n`
          + `A join renumbers every scene and reads the files on disk. These `
          + `edits are not on disk yet, and once the numbers move they cannot `
          + `be saved under the number they were made against.\\n\\n`
          + `Use each scene's save icon, or "Save all scenes".`);
      return;
    }}
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

    const name = await askName({{
      title: `Join ${{SEQ.length}} scenes into one`,
      ok: 'Join and renumber',
      value: (SEQ[0].label || 'joined').slice(0, 40),
      taken,
      body:
        `In script order: <b>${{SEQ.map(s => `${{s.n}} ${{s.label || ''}}`).join('</b>, <b>')}}</b>.`
        + `<ul>`
        + (trk.includes('segment') ? `<li>segments joined end to end &mdash; <b>${{segF}}</b> frames</li>` : '')
        + (trk.includes('avatar')  ? `<li>avatars joined the same way &mdash; <b>${{ovlF}}</b> frames</li>` : '')
        + (fillNar
           ? `<li><b>${{noNar.map(s => s.label).join(', ')}}</b> has no narration &mdash; `
             + `its time is held open with a transparent silent clip, `
             + `<b>${{noNar.reduce((a, s) => a + s.base_n, 0)}}</b> frames, so the narration `
             + `after it stays where it belongs</li>`
           : '')
        + (dropped.length ? `<li class="warn">the <b>${{dropped.join(' and ')}}</b> of these scenes is NOT carried`
                          + ` into the joined scene &mdash; recoverable from z_History/ only</li>` : '')
        + `<li>their narration lines are joined in order into one line</li>`
        + `<li>every scene in the script is renumbered <b>1..N</b>, since a join leaves a gap</li>`
        + `<li>the folders replaced, and script.json, are copied to <b>z_History/</b> first</li></ul>`
        + `<p class="warn">This changes the store, not just the preview, and cannot be undone from here.</p>`
    }});
    if (!name) return;

    stop();
    status(`Joining ${{list.length}} scenes into "${{name}}"…`);
    let d;
    try {{
      const r = await fetch('/api/join', {{ method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ root: ROOT_REL, ns: list, label: name, tracks: trk, fill_gaps: fillNar }}) }});
      d = await r.json();
    }} catch (e) {{ status(`Join failed: ${{e}}`); return; }}
    if (d.error) {{ status(`Join failed: ${{d.error}}`); return; }}

    RENUMBERED = true;
    paintSaveBtn();
    const moved = (d.renumbered || []).map(r => `${{r.from}}\u2192${{r.to}}`).join(', ');
    alert(`Joined ${{d.joined.join(', ')}} into "${{d.label}}" as scene ${{d.new_n}}.\n\n`
        + (moved ? `Renumbered: ${{moved}}\n\n` : '')
        + `Previous state archived to:\n${{d.archived_to}}\n\n`
        + `The timeline will reload against the new numbering.`);
    location.href = `/api/open-seq-go?root=${{encodeURIComponent(ROOT_REL)}}`
                  + `&ns=${{encodeURIComponent(String(d.new_n))}}`;
  }}
  $('joinBtn').onclick = joinTimeline;

  // ── save every scene that has pending work ──────────────────────────────
  // The only way to save once a join has renumbered things, and useful before
  // that too: a set written together is a set whose numbers agree.
  // ── Backup Scenes ─────────────────────────────────────────────────────
  // Copy every scene folder in sandbox/ into sandbox/z_History/26-8-27_v1.
  //
  // WHY IT EXISTS: none of this is in git. The video is hundreds of megabytes
  // and git keeps every version of every file forever, so the whole Customers/
  // tree is ignored — which leaves no revert at all. A per-file z_History
  // covers "undo that save"; this covers "put the whole set back".
  //
  // A COPY, NOT A MOVE. A backup that empties the folder it backed up is not a
  // backup. The sandbox is edited in place, one scene at a time, and moving it
  // would take away every scene this backup is not about.
  //
  // The second job, and the only conditional one: a join or a split leaves a
  // `_was_n` marker on every scene whose number moved. The files themselves
  // were already written — atomically, by the join — so the marker is the ONLY
  // thing left outstanding, and clearing it is what "I accept this reorder"
  // means. The button turns green while one is pending.
  async function backupScenes() {{
    let plan = null;
    try {{
      const r = await fetch('/api/archive', {{ method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ root: ROOT_REL, folder: 'sandbox',
                              naming: 'add-v', dry: true }}) }});
      plan = await r.json();
    }} catch (e) {{ /* fall through — the message says so rather than guessing */ }}
    if (!plan || plan.error) {{ status(`Could not read the sandbox: ${{plan && plan.error}}`); return; }}
    if (plan.empty) {{ status('The sandbox is empty — nothing to back up.'); return; }}

    const dirty = SEQ.filter(s => histOf(s.n).length).map(s => s.n);
    if (!confirm(`Back up ${{plan.would_archive.length}} scene folder(s)?\n\n`
               + `COPYING TO\n${{plan.into}}\n\n`
               + `Your scenes stay exactly where they are — this is a copy, `
               + `taken because none of this is in git.\n\n`
               + (dirty.length
                  ? `⚠ Scene(s) ${{dirty.join(', ')}} have UNSAVED edits. A backup `
                    + `copies the FILES ON DISK, so those edits are not in it. `
                    + `Save All first if you want them.\n\n`
                  : ``)
               + (RENUMBERED
                  ? `A join or split renumbered the scenes. That note is cleared `
                    + `too — it is the only thing left outstanding after one.`
                  : `No renumber note is outstanding.`))) return;
    stop();
    let dest = null;
    try {{
      const r = await fetch('/api/archive', {{ method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ root: ROOT_REL, folder: 'sandbox',
                              naming: 'add-v' }}) }});
      const d = await r.json();
      if (d.error) {{ status(`Backup failed: ${{d.error}}`); return; }}
      dest = d.archived_to;
    }} catch (e) {{ status(`Backup failed: ${{e}}`); return; }}

    // Only AFTER the copy landed. Clearing the marker first would leave the
    // note gone and the backup missing if the copy then failed.
    let cleared = '';
    if (RENUMBERED) {{
      try {{
        await fetch('/api/renumber-clear', {{ method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ root: ROOT_REL }}) }});
        RENUMBERED = false;
        cleared = ' The renumber note is cleared.';
      }} catch (e) {{ cleared = ' ⚠ The renumber note could not be cleared.'; }}
    }}
    paintBackupBtn();
    renderScenes();
    status(`Backed up to:\n${{dest}}${{cleared}}`);
  }}

  // GREEN while a join or split has left a note outstanding — the one moment
  // this button has a second job, and the moment it is easiest to walk away
  // from. Enabled the rest of the time: a backup is worth taking whenever, and
  // putting the only revert this data has behind a rare event would be worse
  // than the confusion that gating it would avoid.
  function paintBackupBtn() {{
    const b = $('backupBtn');
    if (b) b.classList.toggle('pending', RENUMBERED);
  }}

  // ── Save All ──────────────────────────────────────────────────────────
  // Writes every dirty scene back over its file. THAT IS ALL IT DOES.
  //
  // It used to also snapshot the whole sandbox and clear the renumber note, so
  // one click could do any of three different jobs and nothing on screen said
  // which. Those two moved to Backup Scenes; each button now does one thing
  // that can be named in the label.
  async function saveAllScenes() {{
    const withWork = SEQ.map((s, i) => ({{ i, n: s.n, hist: histOf(s.n) }}))
                        .filter(x => x.hist.length);
    if (!withWork.length) {{
      // Nothing to write. If a join or split left a note outstanding, say
      // WHICH button clears it rather than quietly doing it from here — that
      // silent second job is what made this button unreadable.
      status(RENUMBERED
        ? `No scene has unsaved edits. A join or split left a renumber note; `
          + `Backup Scenes is what clears it.`
        : `No scene has unsaved edits.`);
      return;
    }}
    const lines = withWork.map(x => {{
      const layers = [...new Set(x.hist.flatMap(e => Object.keys(e)))]
        .map(w => w === 'base' ? 'segment' : 'overlay').join(' and ');
      return `  scene ${{x.n}}: ${{layers}} (${{x.hist.length}} change${{x.hist.length === 1 ? '' : 's'}})`;
    }}).join('\\n');
    if (!confirm(`Save ${{withWork.length}} scene(s)?\n\n${{lines}}\n\n`
               + `WRITING TO\n${{ROOT_REL}}/sandbox/\n\n`
               + `Each file keeps its previous version in its own scene's `
               + `z_History/.\n\n`
               + `No whole-set backup is taken and no renumber note is cleared. `
               + `Backup Scenes does both of those.`)) return;
    stop();
    const done = [], failed = [], warn = [];
    for (const x of withWork) {{
      const layers = [...new Set(x.hist.flatMap(e => Object.keys(e)))].filter(w => slugOf(x.i, w));
      let ok = true;
      for (const w of layers) {{
        let d;
        try {{
          const r = await fetch('/api/save', {{ method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ slug: slugOf(x.i, w) }}) }});
          d = await r.json();
        }} catch (e) {{ failed.push(`scene ${{x.n}} ${{w}}: ${{e}}`); ok = false; continue; }}
        if (d.error) {{ failed.push(`scene ${{x.n}} ${{w}}: ${{d.error}}`); ok = false; continue; }}
        if (d.warning) warn.push(`scene ${{x.n}} ${{w}}: ${{d.warning}}`);
      }}
      // Cleared per scene, and only when that scene wrote cleanly — a scene
      // that failed must keep its history so it can be retried or undone.
      if (ok) {{ x.hist.length = 0; done.push(x.n); }}
    }}
    renderScenes();
    status(`Saved ${{done.length}} of ${{withWork.length}} scene(s)`
         + (done.length ? `: ${{done.join(', ')}}` : '') + '.'
         + (failed.length ? `\\n\u26a0 ${{failed.join('; ')}}` : '')
         + (warn.length ? `\\n\u26a0 ${{warn.join('; ')}}` : ''));
  }}
  $('backupBtn').onclick = backupScenes;

  // ── list-level actions ──────────────────────────────────────────────────
  const setAllPicks = on => {{
    for (const c of document.querySelectorAll('.pick')) if (!c.disabled) c.checked = on;
    updatePick();
  }};
  $('selAll').onclick  = () => setAllPicks(true);
  $('selNone').onclick = () => setAllPicks(false);

  // Which scenes a list-level action applies to: ticked AND already on the
  // timeline. A ticked scene that has not been rebuilt in yet has no cache
  // loaded and no frame counts to compare, so it is reported rather than
  // silently treated as done.
  function targets() {{
    const ticked = new Set(picked());
    const on = [], pending = [];
    for (const n of ticked) {{
      const i = SEQ.findIndex(s => s.n === n);
      if (i >= 0) on.push(i); else pending.push(n);
    }}
    return {{ on, pending }};
  }}

  function balanceReport() {{
    const {{ on, pending }} = targets();
    let rows = 0, frames = 0;
    for (const i of on) {{
      if (!slugOf(i, 'base') || !slugOf(i, 'overlay')) continue;
      const d = Math.abs(SEQ[i].base_n - SEQ[i].over_n);
      if (d) {{ rows++; frames += d; }}
    }}
    $('balanceBtn').disabled = rows === 0;
    $('balNote').innerHTML = rows === 0
      ? (on.length
          ? `<span class="ok">&#10003;</span> the ticked scenes already match, track for track.`
          : `Tick a scene to compare its two tracks.`)
        + (pending.length ? ` <span class="skip">${{pending.length}} ticked scene(s) are not on the timeline yet — rebuild first.</span>` : '')
      : `<b>${{rows}}</b> ticked scene${{rows === 1 ? '' : 's'}} differ${{rows === 1 ? 's' : ''}} by <b>${{frames}}</b> frame${{frames === 1 ? '' : 's'}} in total.`
        + (pending.length ? ` <span class="skip">${{pending.length}} not on the timeline yet.</span>` : '');
  }}

  // ── update frame imbalance ──────────────────────────────────────────────
  // The two tracks of a scene are different files and drift apart as each is
  // edited. This pads the SHORTER one by repeating its LAST frame until both
  // hold the same count — the last frame because that is the settled end of
  // the shot, where a repeat is invisible; anywhere else it would show as a
  // stutter mid-motion.
  //
  // Each scene's change goes through its own history, so this is undoable one
  // scene at a time exactly like a hand edit.
  async function balanceScenes() {{
    const {{ on, pending }} = targets();
    const work = [];
    for (const i of on) {{
      if (!slugOf(i, 'base') || !slugOf(i, 'overlay')) continue;
      const diff = SEQ[i].base_n - SEQ[i].over_n;
      if (!diff) continue;
      const short = diff > 0 ? 'overlay' : 'base';
      if (isLocked(SEQ[i].n, short)) {{ work.push({{ i, short, skipped: true }}); continue; }}
      work.push({{ i, short, count: Math.abs(diff) }});
    }}
    const doable = work.filter(w => !w.skipped);
    if (!doable.length) {{
      status(work.length
        ? `Nothing done — the track needing frames is locked on every scene that differs.`
        : `Nothing to do — the ticked scenes already match.`);
      return;
    }}
    if (!confirm(`Balance ${{doable.length}} scene(s)?\n\n`
               + doable.map(w => `  scene ${{SEQ[w.i].n}}: +${{w.count}} to the `
                                + `${{w.short === 'base' ? 'segment' : 'overlay'}}`).join('\\n')
               + `\n\nEach repeats that track's LAST frame. Undoable per scene.`)) return;
    stop();
    const done = [], failed = [];
    for (const w of doable) {{
      const {{ i, short, count }} = w;
      const before = await snapshot(i, [short]);
      const len = lenOf(i, short);
      let d;
      try {{
        const r = await fetch('/api/frames/dup', {{ method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ slug: slugOf(i, short), at: len, count, side: 'right' }}) }});
        d = await r.json();
      }} catch (e) {{ failed.push(`scene ${{SEQ[i].n}}: ${{e}}`); continue; }}
      if (d.error) {{ failed.push(`scene ${{SEQ[i].n}}: ${{d.error}}`); continue; }}
      if (short === 'base') SEQ[i].base_n = d.nb_frames; else SEQ[i].over_n = d.nb_frames;
      MARKS[slugOf(i, short)] = new Set(d.marks || []);
      const row = ALL.find(x => x.n === SEQ[i].n);
      if (row) {{
        if (short === 'base') {{ row.frames = d.nb_frames; row.frames_exact = true; }}
        else {{ row.overlay_frames = d.nb_frames; row.overlay_frames_exact = true; }}
      }}
      pushHist(i, before);
      done.push(`${{SEQ[i].n}} +${{count}} ${{short === 'base' ? 'seg' : 'ovl'}}`);
    }}
    ver++;
    reindex(); rebuildBar(); renderNote(); renderScenes();
    show(+$('slider').value); renderTicks(); renderReport();
    const skipped = work.filter(w => w.skipped).map(w => SEQ[w.i].n);
    status(`Balanced ${{done.length}} scene(s): ${{done.join(', ')}}. `
         + `Timeline is ${{(total / (SEQ[0].fps || 25)).toFixed(2)}}s.`
         + (skipped.length ? `\n\u26a0 skipped ${{skipped.join(', ')}} — the track needing frames is locked.` : '')
         + (pending.length ? `\n\u26a0 ${{pending.length}} ticked scene(s) are not on the timeline.` : '')
         + (failed.length ? `\n\u26a0 ${{failed.join('; ')}}` : ''));
  }}
  $('balanceBtn').onclick = balanceScenes;

  // ── per-scene change history ────────────────────────────────────────────
  // One stack per SCENE, because a scene is what gets saved. An entry is the
  // frame map of each layer BEFORE an edit, so undo is "put this layer back to
  // that map" — no need to keep the JPEGs themselves, since a map plus the
  // source rebuilds any past state exactly.
  //
  // Cleared on a successful save: at that moment the file on disk IS the
  // current state, so there is nothing left to undo back to.
  const HIST = {{}};                       // scene number -> [{{base, overlay}}, ...]
  const histOf = n => (HIST[n] = HIST[n] || []);

  // Fetched, not cached: a map is only wanted at the moment an edit is about
  // to happen, and holding one per clip for a 14-scene timeline would be a lot
  // of integers kept alive for scenes nobody touches.
  async function snapshot(i, layers) {{
    const e = {{}};
    for (const w of layers) {{
      const slug = slugOf(i, w);
      if (!slug) continue;
      try {{
        const r = await fetch(`/api/frames/map?slug=${{encodeURIComponent(slug)}}`);
        const d = await r.json();
        if (d.frame_map) e[w] = d.frame_map;
      }} catch (err) {{ /* a snapshot we could not take is one we do not offer */ }}
    }}
    return e;
  }}
  function pushHist(i, entry) {{
    if (!entry || (!entry.base && !entry.overlay)) return;
    histOf(SEQ[i].n).push(entry);
    renderScenes();
  }}

  // ── undo ────────────────────────────────────────────────────────────────
  // One click, one step back, until the stack is empty and the scene matches
  // the file it was last saved to. Each entry names only the layers that
  // actually changed, so undoing a segment-only edit leaves the overlay alone.
  async function undoScene(n) {{
    const i = SEQ.findIndex(s => s.n === n);
    const hist = histOf(n);
    if (i < 0 || !hist.length) return;
    stop();
    const entry = hist[hist.length - 1];
    status(`Undoing the last change to scene ${{n}}…`);
    const done = [];
    for (const [w, map] of Object.entries(entry)) {{
      const slug = slugOf(i, w);
      if (!slug || !map) continue;
      let d;
      try {{
        const r = await fetch('/api/frames/restore', {{ method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ slug, frame_map: map }}) }});
        d = await r.json();
      }} catch (e) {{ status(`Undo failed on ${{w}}: ${{e}}`); return; }}
      if (d.error) {{ status(`Undo failed on ${{w}} of scene ${{n}}: ${{d.error}}`); return; }}
      if (w === 'base') SEQ[i].base_n = d.nb_frames; else SEQ[i].over_n = d.nb_frames;
      MARKS[slug] = new Set(d.marks || []);
      const row = ALL.find(x => x.n === n);
      if (row) {{
        if (w === 'base') {{ row.frames = d.nb_frames; row.frames_exact = true; }}
        else {{ row.overlay_frames = d.nb_frames; row.overlay_frames_exact = true; }}
      }}
      done.push(`${{w === 'base' ? 'segment' : 'overlay'}} ${{d.nb_frames}}`);
    }}
    // Popped only after every layer in the entry is back, or a half-applied
    // undo would leave the stack claiming work that was never reversed.
    hist.pop();
    ver++;
    reindex(); rebuildBar(); renderNote(); renderScenes();
    show(Math.min(total, starts[i] + 1));
    renderTicks(); renderReport();
    status(`Undid one change on scene ${{n}} — ${{done.join(', ')}}. `
         + `${{hist.length}} left. Timeline is ${{(total / (SEQ[0].fps || 25)).toFixed(2)}}s.`);
  }}

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
  function paintSaveBtn() {{}}



  async function saveScene(n) {{
    const i = SEQ.findIndex(s => s.n === n);
    const hist = histOf(n);
    if (i < 0 || !hist.length) return;
    // After a join every scene has been renumbered, so a scene's number no
    // longer means what it did when its edits were made. Writing one on its own
    // would put it on disk under a number the rest of the set has not been
    // written under yet.

    // Which layers this scene actually has pending work on.
    const layers = [...new Set(hist.flatMap(e => Object.keys(e)))].filter(w => slugOf(i, w));
    if (!layers.length) {{ hist.length = 0; renderScenes(); return; }}
    const names = layers.map(w => w === 'base' ? 'segment' : 'overlay').join(' and ');
    if (!confirm(`Save scene ${{n}} (${{SEQ[i].label}})?\n\n`
               + `WRITING TO\n${{ROOT_REL}}/sandbox/`
               + `${{String(n).padStart(2, '0')}}-${{SEQ[i].label}}/\n\n`
               + `Writes the ${{names}} over the current file. That file is `
               + `archived to this scene's own z_History/ first.\n\n`
               + `A snapshot of the WHOLE sandbox is taken by "Save all scenes", `
               + `not by this.\n\n`
               + `This scene's ${{hist.length}} undo step(s) are cleared.`)) return;
    stop();
    const done = [], warn = [];
    for (const w of layers) {{
      let d;
      try {{
        const r = await fetch('/api/save', {{ method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ slug: slugOf(i, w) }}) }});
        d = await r.json();
      }} catch (e) {{ status(`Save failed on ${{w}}: ${{e}}`); return; }}
      if (d.error) {{ status(`Save failed on ${{w}} of scene ${{n}}: ${{d.error}}`); return; }}
      done.push(`${{w === 'base' ? 'segment' : 'overlay'}} ${{d.duration_s}}s`);
      // The server counts the frames it actually wrote. Surface a mismatch
      // loudly: a save that quietly writes a different length than the one you
      // edited is the worst kind of wrong.
      if (d.warning) warn.push(`${{w === 'base' ? 'segment' : 'overlay'}}: ${{d.warning}}`);
    }}
    // Cleared only after EVERY layer wrote. A partial save that emptied the
    // history would strand the unwritten layer with no way back.
    hist.length = 0;
    renderScenes();
    status(`Saved scene ${{n}} — ${{done.join(', ')}}. History cleared.`
         + (warn.length ? `\n\u26a0 ${{warn.join(' | ')}}` : ''));
  }}

  // ── the marked zone ─────────────────────────────────────────────────────
  // Marks divide a scene into zones. The zone is the one the playhead is
  // INSIDE: from the mark at or before it, to the next mark (or the scene's
  // end). With no marks the zone is the whole scene, which is why loop still
  // does something sensible before anything is marked.
  //
  // Returned in LOCAL frames, because every edit endpoint speaks local frames
  // and converting once here keeps that conversion in one place.
  function zoneOf(i, local) {{
    const n = lenOf(i);
    const ms = [...(MARKS[slugOf(i)] || [])].sort((x, y) => x - y);
    let a = 1, b = n;
    for (const m of ms) {{
      if (m <= local) a = m;
      else {{ b = m - 1; break; }}
    }}
    return {{ a, b: Math.max(a, Math.min(b, n)), marked: ms.length > 0 }};
  }}

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
  async function resync(i) {{
    const fixed = [];
    for (const w of ['base', 'overlay']) {{
      const slug = slugOf(i, w);
      if (!slug) continue;
      try {{
        const r = await fetch(`/api/frames/map?slug=${{encodeURIComponent(slug)}}`);
        const d = await r.json();
        if (d.error || typeof d.nb_frames !== 'number') continue;
        const was = lenOf(i, w);
        if (was !== d.nb_frames) {{
          if (w === 'base') SEQ[i].base_n = d.nb_frames; else SEQ[i].over_n = d.nb_frames;
          fixed.push(`${{w === 'base' ? 'segment' : 'overlay'}} ${{was}}\u2192${{d.nb_frames}}`);
        }}
      }} catch (e) {{ /* keep the page's number; the next edit refuses loudly */ }}
    }}
    if (fixed.length) {{ reindex(); rebuildBar(); renderScenes(); }}
    return fixed;
  }}


  // ── copy and paste a frame ──────────────────────────────────────────────
  // CLIP holds a POSITION, not a picture: which scene, which frame, on which
  // tracks. Pasting re-inserts that very frame — the map records the same
  // source frame the original showed, so nothing is decoded, re-encoded or
  // guessed at. A trip out to the system clipboard and back would cost a PNG
  // round trip and leave the map describing a frame it no longer knows.
  let CLIP = null;

  function paintPaste() {{
    const b = $('pasteFrame');
    if (!b) return;
    b.disabled = !CLIP;
    const tip = CLIP
      ? `Paste a copy of scene ${{CLIP.n}}'s frame ${{CLIP.local}} in after the `
        + `frame on screen, on the ticked tracks. Copied from `
        + `${{CLIP.layers.map(w => w === 'base' ? 'segment' : 'overlay').join(' + ')}}.`
      : 'Nothing copied yet — press Copy first.';
    b.dataset.tip = tip;
    b.title = tip;
  }}

  // The picture, for pasting into something else on the Mac. Separate from the
  // internal copy on purpose: this one IS a picture, and is no use for putting
  // a frame back into a clip.
  async function toMacClipboard(i, local) {{
    const s = SEQ[i];
    const url = `../${{s.base_slug}}/frames/frame_${{pad(Math.min(local, s.base_n))}}${{s.base_ext}}?v=${{ver}}`;
    try {{
      const img = new Image();
      img.src = url;
      await img.decode();
      const c = document.createElement('canvas');
      c.width = img.naturalWidth; c.height = img.naturalHeight;
      c.getContext('2d').drawImage(img, 0, 0);
      // PNG because that is the only image type browsers reliably write to a
      // clipboard; the frame itself is untouched either way.
      const blob = await new Promise(r => c.toBlob(r, 'image/png'));
      await navigator.clipboard.write([new ClipboardItem({{ 'image/png': blob }})]);
      return `${{img.naturalWidth}}\u00d7${{img.naturalHeight}}`;
    }} catch (e) {{
      return null;
    }}
  }}

  async function copyFrame(alsoMac) {{
    const i = curI();
    if (i < 0 || !SEQ[i]) return;
    const n = SEQ[i].n;
    const layers = ['base', 'overlay'].filter(w => !isLocked(n, w) && slugOf(i, w));
    if (!layers.length) {{
      status(`Scene ${{n}}: tick the segment or the overlay first — nothing to copy.`);
      return;
    }}
    const {{ local }} = at(+$('slider').value);
    CLIP = {{ i, n, local, layers, label: SEQ[i].label }};
    paintPaste();
    let extra = '';
    if (alsoMac) {{
      const size = await toMacClipboard(i, local);
      extra = size ? ` The picture is on the Mac clipboard too (${{size}}).`
                   : ' The Mac clipboard refused it — the browser only allows that '
                     + 'from a real click on a focused page.';
    }}
    status(`Copied scene ${{n}} frame ${{local}} `
         + `(${{layers.map(w => w === 'base' ? 'segment' : 'overlay').join(' + ')}}).`
         + ` Move to where you want it and press Paste.${{extra}}`);
  }}

  async function pasteFrame() {{
    if (!CLIP) return;
    const i = curI();
    if (i < 0 || !SEQ[i]) return;
    const n = SEQ[i].n;
    if (i !== CLIP.i) {{
      status(`The copied frame is from scene ${{CLIP.n}}, and the playhead is on `
           + `scene ${{n}}. A paste stays inside one scene — the two clips are `
           + `different files.`);
      return;
    }}
    const layers = ['base', 'overlay'].filter(w => !isLocked(n, w) && slugOf(i, w)
                                                   && CLIP.layers.includes(w));
    if (!layers.length) {{
      status(`Nothing to paste onto: the copy came from `
           + `${{CLIP.layers.join(' + ')}}, and those tracks are not ticked now.`);
      return;
    }}
    stop();
    const fixed = await resync(i);
    if (fixed.length) {{
      status(`Scene ${{n}}: this page was out of step with the clip `
           + `(${{fixed.join(', ')}}). Corrected — try the paste again.`);
      return;
    }}
    const before = await snapshot(i, layers);
    const {{ local }} = at(+$('slider').value);

    // CHECK EVERY TRACK BEFORE WRITING ANY. The two tracks are routinely
    // different lengths — 480 segment against 442 avatar is normal — so a frame
    // that exists in one can be past the end of the other. Writing them in turn
    // and stopping at the first error left the segment pasted and the avatar
    // refused: a half-done edit, reported as a failure. It happened four times
    // in a row, each adding a frame to one track only.
    const tooShort = layers.filter(w => local > lenOf(i, w) || CLIP.local > lenOf(i, w));
    if (tooShort.length) {{
      const names = tooShort.map(w => w === 'base' ? 'segment' : 'overlay');
      alert(`Frame ${{local}} is past the end of the `
          + `${{names.join(' and ')}} on scene ${{n}}.\n\n`
          + layers.map(w => `  ${{w === 'base' ? 'segment' : 'overlay'}}: `
                          + `${{lenOf(i, w)}} frames`).join('\\n')
          + `\n\nNothing was pasted. The two tracks are different lengths, so a `
          + `frame that exists in one can be past the end of the other — untick `
          + `the shorter track, or move to a frame both of them have.`);
      return;
    }}

    const done = [];
    for (const w of layers) {{
      try {{
        const r = await fetch('/api/frames/paste', {{ method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ slug: slugOf(i, w),
                                 from: CLIP.local, at: local }}) }});
        const d = await r.json();
        if (d.error) {{
          // Past the pre-flight and still refused: something changed under us.
          // Say what DID happen, because a track already written is not nothing.
          alert(`Paste failed on the ${{w === 'base' ? 'segment' : 'overlay'}}: ${{d.error}}\n\n`
              + (done.length ? `The ${{done.join(', ')}} was already written. Use Undo `
                             + `to take it back.` : 'Nothing was written.'));
          if (done.length) pushHist(i, before);
          reindex(); rebuildBar(); renderScenes();
          return;
        }}
        if (w === 'base') SEQ[i].base_n = d.nb_frames; else SEQ[i].over_n = d.nb_frames;
        done.push(`${{w === 'base' ? 'segment' : 'overlay'}} ${{d.nb_frames}}`);
      }} catch (e) {{ status(`Paste failed: ${{e}}`); return; }}
    }}
    pushHist(i, before);
    ver++;
    reindex(); rebuildBar(); renderScenes();
    const g = starts[i] + Math.min(local + 1, lenOf(i, 'base'));
    $('slider').value = g; show(g);
    status(`Pasted scene ${{CLIP.n}}'s frame ${{CLIP.local}} after frame ${{local}} — `
         + `${{done.join(', ')}}. Timeline is ${{(total / (SEQ[0].fps || 25)).toFixed(2)}}s.`);
  }}

  async function doEdit(kind, span) {{
    const i = curI();
    if (i < 0 || !SEQ[i]) return;
    const n = SEQ[i].n;
    const layers = ['base', 'overlay'].filter(w => !isLocked(n, w) && slugOf(i, w));
    if (!layers.length) {{
      status(`Scene ${{n}}: tick the segment or the overlay first — nothing to act on.`);
      return;
    }}
    stop();
    // Straighten the page's counts BEFORE aiming an edit at a frame number.
    const fixed = await resync(i);
    if (fixed.length) {{
      status(`Scene ${{n}}: this page was out of step with the clip `
           + `(${{fixed.join(', ')}}). Corrected — try that edit again.`);
      return;
    }}
    // Snapshot BEFORE the write, and of exactly the layers about to change.
    const before = await snapshot(i, layers);
    const {{ local }} = at(+$('slider').value);
    // CHECK EVERY TICKED TRACK BEFORE WRITING ANY. The two are routinely
    // different lengths — 480 segment against 442 avatar is normal — so the
    // frame on screen can exist in one and be past the end of the other. This
    // loop used to `continue` past a refusal, which changed the tracks that
    // worked and skipped the rest: a half-done edit that reads as an error.
    if (!span) {{
      const short = layers.filter(w => local > lenOf(i, w));
      if (short.length) {{
        alert(`Frame ${{local}} is past the end of the `
            + `${{short.map(w => w === 'base' ? 'segment' : 'overlay').join(' and ')}} `
            + `on scene ${{n}}.\n\n`
            + layers.map(w => `  ${{w === 'base' ? 'segment' : 'overlay'}}: `
                            + `${{lenOf(i, w)}} frames`).join('\\n')
            + `\n\nNothing was changed. Untick the shorter track, or move to a `
            + `frame both of them have.`);
        return;
      }}
    }}

    // ONE zone, decided BEFORE anything is written. Editing the first layer
    // shifts its marks, so recomputing the zone for the second layer read the
    // ALREADY-MOVED marks and gave a different, larger span: a 35-frame zone
    // grew the segment by 35 and the overlay by 70. The zone the user is
    // looking at is the zone both layers get.
    const zone = span ? zoneOf(i, local) : null;
    const changed = [];
    for (const w of layers) {{
      const len = lenOf(i, w);
      let path, body;
      if (span) {{
        const z = zone;
        path = kind === 'dup' ? '/api/frames/dup-span' : '/api/frames/del-span';
        body = {{ slug: slugOf(i, w), a: Math.min(z.a, len), b: Math.min(z.b, len) }};
      // NOTE: neither branch clamps with lenOf(). That clamp read this page's
      // OWN idea of the length, and when it had drifted below the cache's real
      // one — 478 here against 476 there — every frame past its number silently
      // became the LAST frame, so deleting frame 477 took one off the END
      // instead of the frame on screen. The server validates a span against the
      // real length and refuses outside it, so sending the frame unclamped
      // turns a drift into a visible refusal instead of a wrong deletion.
      }} else if (kind === 'dup') {{
        // Insert the copy immediately AFTER the frame on screen, so the new
        // frame is the one the playhead lands on below.
        path = '/api/frames/dup';
        body = {{ slug: slugOf(i, w), at: local, count: 1, side: 'right' }};
      }} else {{
        // Delete the frame ON SCREEN. The single-frame endpoint deletes to one
        // SIDE of the current frame and so could never remove the frame you are
        // looking at; a one-frame span is exactly that frame.
        path = '/api/frames/del-span';
        body = {{ slug: slugOf(i, w), a: local, b: local }};
      }}
      let d;
      try {{
        const r = await fetch(path, {{ method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify(body) }});
        d = await r.json();
      }} catch (e) {{ status(`Error on ${{w}}: ${{e}}`); continue; }}
      if (d.error) {{ status(`Error on ${{w}} of scene ${{n}}: ${{d.error}}`); continue; }}
      if (!span && kind === 'del' && d.actual === 0) continue;
      if (w === 'base') SEQ[i].base_n = d.nb_frames; else SEQ[i].over_n = d.nb_frames;
      MARKS[slugOf(i, w)] = new Set(d.marks || []);
      const row = ALL.find(x => x.n === n);
      if (row) {{
        if (w === 'base') {{ row.frames = d.nb_frames; row.frames_exact = true; }}
        else {{ row.overlay_frames = d.nb_frames; row.overlay_frames_exact = true; }}
      }}
      changed.push(`${{w === 'base' ? 'segment' : 'overlay'}} ${{d.nb_frames}}`);
    }}
    if (!changed.length) {{ status('Nothing changed.'); return; }}
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
    status(`${{kind === 'dup' ? 'Added' : 'Removed'}} ${{span ? 'the marked zone' : '1 frame'}} `
         + `on scene ${{n}} — ${{changed.join(', ')}}. `
         + `Timeline is ${{(total / (SEQ[0].fps || 25)).toFixed(2)}}s.`);
  }}

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
  function repCell(label, value, cls) {{
    return `<span class="rc"><span class="rk">${{label}}</span>`
         + `<span class="rv ${{cls || ''}}">${{value}}</span></span>`;
  }}
  function renderReport() {{
    const i = curI();
    const g = $('rep');
    if (i < 0 || !SEQ[i]) {{
      g.innerHTML = repCell('scene', '\u2014') + repCell('segment', '\u2014')
                  + repCell('selection', '\u2014') + repCell('overlay', '\u2014');
      return;
    }}
    const s = SEQ[i], fps = s.fps || 25;
    const {{ local }} = at(+$('slider').value);
    const z = zoneOf(i, Math.min(local, lenOf(i)));
    const zoneLen = z.b - z.a + 1;

    const track = w => {{
      const len = lenOf(i, w), slug = slugOf(i, w);
      if (!slug) return `<i class="off">no ${{w === 'base' ? 'segment' : 'overlay'}}</i>`;
      if (isLocked(s.n, w)) return `<i class="off">unticked</i>`;
      const f = Math.min(local, len);
      const a = Math.min(z.a, len), b = Math.min(z.b, len);
      return `<b>${{f}}</b>/${{len}}<span class="sep">zone</span>`
           + `<b>${{a}}\u2013${{b}}</b> (${{b - a + 1}}f)`;
    }};

    // The grid fills left-to-right, so this ORDER is the layout. SEGMENT and
    // OVERLAY now sit in the same column, one above the other, because the
    // thing you read them for is comparing the two frame counts — 483 over 439
    // is a glance; 483 beside a duration and 439 under a scene name is not.
    g.innerHTML =
        repCell('scene', `<b>${{s.n}}</b> <span class="nm">${{s.label || ''}}</span>`)
      + repCell('segment', track('base'), 'seg')
      + repCell('selection', `<b>${{(zoneLen / fps).toFixed(2)}}s</b>`
                           + `<span class="sep">timeline</span>`
                           + `<b>${{(total / fps).toFixed(2)}}s</b>`)
      + repCell('overlay', track('overlay'), 'ovl');
  }}

  $('copyFrame').onclick = ev => copyFrame(ev.shiftKey);
  $('pasteFrame').onclick = () => pasteFrame();
  $('addFrame').onclick = () => doEdit('dup', false);
  $('delFrame').onclick = () => doEdit('del', false);
  $('addZone').onclick  = () => doEdit('dup', true);
  $('delZone').onclick  = () => doEdit('del', true);

  // The per-row + / - is the SAME operation as row 3's + / - Frame, so it is
  // the same code. Two paths for one action drift apart, and one of them then
  // deletes a different frame than the other.
  async function rowEdit(n, kind) {{
    const i = SEQ.findIndex(s => s.n === n);
    if (i < 0 || i !== curI()) return;
    return doEdit(kind, false);
  }}


  // ── Save Scenes ───────────────────────────────────────────────────────
  // Every scene on THIS TIMELINE that has unsaved edits, written back over its
  // file in sandbox/.
  //
  // This slot used to be Cut scene, and it went for three reasons. It wrote
  // loose numbered files into the MP4 Splitter's dev/_cuts/, which are not
  // scenes and need a hand-off before they are. It took only ONE layer — the
  // segment whenever the segment was ticked — with nothing on screen saying so.
  // And Split already does the job properly: it names both halves and rewrites
  // the scene list. The slot went to what is actually reached for from here.
  $('cutBtn').onclick = saveAllScenes;

  // ── Save All ──────────────────────────────────────────────────────────
  // The SAME set as Save Scenes, and there is no third set to reach: Rebuild
  // navigates the page, so a scene taken off the timeline takes its pending
  // edits with it. Two ways to one call, because that is where the hand is.
  //
  // It used to save a SINGLE layer of the current scene and leave that scene's
  // undo history untouched, while the save icon on the scene row saved every
  // dirty layer and cleared it. Per-scene saving lives on those icons now.
  $('saveBtn').onclick = saveAllScenes;

  // ── audio ────────────────────────────────────────────────────────────
  // ONE element, re-pointed at each boundary. Two alternating elements would
  // hide the first-play load stall, but every clip is a few seconds of AAC and
  // the browser caches it after one pass, so the second loop is already
  // seamless — the extra element was buying almost nothing.
  const aud = $('audA');
  function audioFor(i) {{
    const s = SEQ[i];
    // Sarah's voice rides on the AVATAR clip. The footage is normally silent,
    // so falling through to it gives silence rather than the wrong voice.
    if (s.over_audio) return `../${{s.over_slug}}/audio.m4a`;
    if (s.base_audio) return `../${{s.base_slug}}/audio.m4a`;
    return null;
  }}
  // ── VTT ─────────────────────────────────────────────────────────────────
  // Video Timing Table, not WebVTT. Per scene: how long the footage runs, how
  // long the line takes to say, and the gap between them.
  //
  // The clip length comes from the TIMELINE, not from the file on disk, so it
  // moves as frames are added or cut. vtt.py reads the file, which is right for
  // a report and wrong here -- a gap that does not budge while you edit frames
  // is a lie with a decimal point on it.
  let VTT = null;                       // {{wps, scenes:[...]}} from the server
  const vLine = {{}};                   // n -> the text currently in the box
  const vDirty = new Set();             // n -> edited but not written yet

  const clipS = i => lenOf(i, 'base') / (SEQ[i].fps || 25);
  const wordsOf = t => t.split(/\\s+/).filter(w => /[A-Za-z0-9]/.test(w)).length;
  function speechS(n, text) {{
    const r = VTT && VTT.byN[n];
    if (!r) return null;
    return wordsOf(text) / VTT.wps + (r.pause || 0);
  }}

  async function loadVtt() {{
    try {{
      const res = await fetch(`/api/vtt?root=${{encodeURIComponent(ROOT_REL)}}`);
      const d = await res.json();
      if (d.error) return;
      d.byN = {{}};
      for (const r of d.scenes) d.byN[r.n] = r;
      VTT = d;
    }} catch (e) {{ return; }}
    renderVtt();
    paintVtt();
  }}

  function renderVtt() {{
    const box = $('vttRows');
    box.innerHTML = '';
    if (!VTT) return;
    SEQ.forEach((sc, i) => {{
      const r = VTT.byN[sc.n];
      const row = document.createElement('div');
      row.className = 'vt';
      row.dataset.i = i;
      if (vLine[sc.n] === undefined) vLine[sc.n] = r ? r.line : '';
      // A bookend (00-opening, 99-closing) is on the timeline but is not a
      // script scene, so it has no line to edit. Shown anyway, greyed: a table
      // that silently skips rows does not match what is playing.
      row.innerHTML =
        `<span class="vn">${{sc.n}}</span>` +
        `<span class="vl"></span>` +
        `<span class="vt3"></span>` +
        (r ? '' : `<span class="vtodo">not a script scene — no line</span>`);
      if (r) {{
        const ta = document.createElement('textarea');
        ta.rows = 2;
        ta.value = vLine[sc.n];
        ta.dataset.n = sc.n;
        ta.title = 'The line for this scene. Editing it here writes '
                 + 'script.json, which is what HeyGen is paid to say. '
                 + 'Saved when you click away; Esc puts it back.';
        ta.addEventListener('input', () => {{
          vLine[sc.n] = ta.value;
          vDirty.add(sc.n);
          row.classList.add('dirty');
          paintVttRow(row, i);           // the gap moves as you type
          paintVttSum();
        }});
        ta.addEventListener('keydown', ev => {{
          if (ev.key === 'Escape') {{
            ta.value = VTT.byN[sc.n].line; ta.dispatchEvent(new Event('input'));
            vDirty.delete(sc.n); row.classList.remove('dirty'); ta.blur();
          }}
          if (ev.key === 'Enter' && (ev.metaKey || ev.ctrlKey)) ta.blur();
        }});
        ta.addEventListener('blur', () => {{
          // Closing the box hands the row back to the highlighter.
          row.classList.remove('editing');
          saveLine(sc.n);
        }});
        row.appendChild(ta);
      }}
      row.addEventListener('click', () => {{
        if (+$('slider').value < 1) return;
        const g = starts[i] + 1;
        if (at(+$('slider').value).i !== i) {{ $('slider').value = g; show(g); }}
        const ta = row.querySelector('textarea');
        // Shown BEFORE focusing: a display:none element cannot take focus, so
        // focusing first would silently do nothing and the box would stay shut.
        if (ta) {{ row.classList.add('editing'); ta.focus(); }}
      }});
      box.appendChild(row);
      paintVttRow(row, i);
    }});
    paintVttSum();
  }}

  function paintVttRow(row, i) {{
    const sc = SEQ[i], r = VTT && VTT.byN[sc.n];
    const c = clipS(i);
    const lab = row.querySelector('.vl');
    const txt = vLine[sc.n] || '';
    // Per-WORD spans, so the one being spoken can be picked out. Escaped by
    // hand rather than trusted: this is the store's own narration copy, and an
    // ampersand or an angle bracket in it is ordinary text, not markup.
    if (r && txt) {{
      lab.innerHTML = txt.split(/\\s+/).filter(Boolean).map(w =>
        `<span class="w">${{w.replace(/&/g, '&amp;').replace(/</g, '&lt;')
                            .replace(/>/g, '&gt;')}}</span>`).join(' ');
    }} else {{
      lab.textContent = r ? '— no line yet —' : sc.label;
    }}
    lab.title = txt;
    const cell = row.querySelector('.vt3');
    if (!r) {{ cell.textContent = `${{c.toFixed(1)}}s`; return; }}
    const sp = speechS(sc.n, txt), gap = c - sp;
    // Negative is the defect that ships silently: the line is still being said
    // when the footage has already moved on.
    const cls = gap < 0 ? 'gapNeg' : (gap > 2.5 ? 'gapBad' : 'gapOk');
    cell.innerHTML = `${{c.toFixed(1)}}s clip &middot; ${{sp.toFixed(1)}}s said &middot; `
                   + `<span class="${{cls}}">${{gap >= 0 ? '' : '−'}}${{Math.abs(gap).toFixed(1)}}s gap</span>`;
  }}

  function paintVttSum() {{
    if (!VTT) return;
    let c = 0, sp = 0, bad = 0, neg = 0;
    SEQ.forEach((sc, i) => {{
      c += clipS(i);
      const r = VTT.byN[sc.n];
      if (!r) return;
      const t = speechS(sc.n, vLine[sc.n] || '');
      sp += t;
      const g = clipS(i) - t;
      if (g < 0) neg++; else if (g > 2.5) bad++;
    }});
    const dead = c > 0 ? Math.round((c - sp) / c * 100) : 0;
    $('vttSum').textContent =
      `${{c.toFixed(1)}}s clip · ${{sp.toFixed(1)}}s said · ${{dead}}% dead air`
      + (neg ? ` · ${{neg}} overrun` : '') + (bad ? ` · ${{bad}} over 2.5s` : '')
      + (vDirty.size ? ` · ${{vDirty.size}} unsaved` : '');
  }}

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
  function paintSpokenWord(row, i) {{
    if (!row || !VTT) return;
    const words = row.querySelectorAll('.vl .w');
    if (!words.length) return;
    const s = SEQ[i], W = words.length;
    const t = (at(+$('slider').value).local - 1) / (s.fps || 25);
    const runs = s.speech_runs || [];
    let k = -1;

    if (runs.length) {{
      const D = runs.reduce((sum, r) => sum + (r[1] - r[0]), 0);
      if (D > 0 && t < runs[0][0]) {{
        // She has not started. Nothing is lit — that is the honest picture,
        // and it is also the clearest way to see how long the lead-in is.
        k = -1;
      }} else if (D > 0) {{
        let acc = 0;
        for (const r of runs) {{
          const share = ((r[1] - r[0]) / D) * W;
          // Between sentences: HOLD where the last run ended.
          //
          // `acc` here is the shares of every run already passed, and the last
          // word of that run was floor(acc + share) — which is floor(acc)
          // exactly. Holding anything else moves the highlight while she is
          // silent. This said `floor(acc) - 1`, so at every pause the tracer
          // stepped BACK a word and then forward again when she resumed.
          if (t < r[0]) {{ k = Math.floor(acc); break; }}
          if (t <= r[1]) {{ k = Math.floor(acc + ((t - r[0]) / (r[1] - r[0])) * share); break; }}
          acc += share;
        }}
        // Past the last run: she has finished, so the line ends lit on its
        // last word rather than going dark while the footage plays on.
        if (k === -1) k = W - 1;
        k = Math.max(0, Math.min(W - 1, k));
      }}
    }} else {{
      // No measurement for this clip — a scene with no avatar, or one whose
      // audio could not be read. Fall back to the voice's average rate from
      // the scene's own start, and say nothing more confident than that.
      k = Math.max(-1, Math.min(W - 1, Math.floor(t * VTT.wps)));
    }}

    for (let j = 0; j < W; j++) words[j].classList.toggle('wnow', j === k);
  }}

  let vttCentred = -1;
  function centreVtt(row) {{
    const box = $('vttRows');
    if (!box || !row) return;
    box.scrollTop = row.offsetTop + row.offsetHeight / 2 - box.clientHeight / 2;
  }}

  function paintVtt() {{
    const rows = [...document.querySelectorAll('#vttRows .vt')];
    if (!rows.length) return;
    const cur = at(+$('slider').value).i;
    rows.forEach(row => {{
      const on = +row.dataset.i === cur;
      if (on === row.classList.contains('on')) return;
      // Leaving a scene closes its editor. Blur alone was not enough to save it:
      // the box is hidden by the same class change, and a hidden field that
      // never fired blur takes the edit with it. Written here instead, where the
      // decision to leave is actually made.
      if (!on && row.classList.contains('dirty')) saveLine(SEQ[+row.dataset.i].n);
      row.classList.toggle('on', on);
    }});
    // AFTER the classes are set, so the open row has its real height — and only
    // when the scene actually changed. Re-centring every frame would fight the
    // scrollbar while someone is reading, and would pull the panel out from
    // under a line being typed.
    const active = rows.find(r => +r.dataset.i === cur);
    if (cur !== vttCentred) {{
      vttCentred = cur;
      centreVtt(active);
      // The row just left goes back to plain text. A word left lit on a scene
      // that is no longer playing points at nothing.
      rows.forEach(r => r.querySelectorAll('.vl .wnow')
                         .forEach(w => w.classList.remove('wnow')));
    }}
    // Every frame, not only at a boundary: this is the thing that moves. Not
    // while the box is open — the highlight lives in the label, which is
    // hidden then, and there is nothing to light.
    if (active && !active.classList.contains('editing')) paintSpokenWord(active, cur);
  }}

  // Closing the tab with an edit still in the box. fetch() with keepalive
  // survives the page going away; a normal one is cancelled mid-flight.
  window.addEventListener('beforeunload', () => {{
    for (const n of vDirty) {{
      navigator.sendBeacon('/api/line', new Blob(
        [JSON.stringify({{ root: ROOT_REL, n, line: vLine[n] }})],
        {{ type: 'application/json' }}));
    }}
  }});

  async function saveLine(n) {{
    if (!vDirty.has(n)) return;
    const text = vLine[n];
    try {{
      const res = await fetch('/api/line', {{ method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ root: ROOT_REL, n, line: text }}) }});
      const d = await res.json();
      if (d.error) {{ status(`Line ${{n}} not saved: ${{d.error}}`); return; }}
      VTT.byN[n].line = d.line;
      VTT.byN[n].words = d.words;
      vLine[n] = d.line;
      vDirty.delete(n);
      const row = [...document.querySelectorAll('#vttRows .vt')]
        .find(x => SEQ[+x.dataset.i].n === n);
      if (row) {{
        row.classList.remove('dirty');
        const ta = row.querySelector('textarea');
        if (ta && ta.value !== d.line) ta.value = d.line;   // whitespace tidied
      }}
      paintVttSum();
      if (!d.unchanged) status(`Scene ${{n}}'s line saved to script.json.`);
    }} catch (e) {{ status(`Line ${{n}} not saved: ${{e}}`); }}
  }}

  function onSceneChange(i, local) {{
    // The lock applies to the scene under the PLAYHEAD, so crossing a boundary
    // can hand you a locked scene or take you off one. Re-gate on every change,
    // or the buttons keep describing the scene you just left.
    refreshEditGate();
    const src = audioFor(i);
    if (!src) {{ aud.pause(); aud.removeAttribute('src'); return; }}
    if (aud.dataset.key !== src) {{ aud.dataset.key = src; aud.src = src; }}
    aud.currentTime = Math.max(0, (local - 1) / (SEQ[i].fps || 25));
    // One element re-pointed per scene, so the rate is set again at every
    // boundary — assigning a new src resets playbackRate to 1, and the sound
    // would race the picture from the next scene on.
    if (RATE < AUDIO_RATE_FLOOR) {{ aud.pause(); }}
    else {{
      aud.playbackRate = RATE;
      if (playing) aud.play().catch(() => {{}});
    }}
  }}

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
  function loopBounds() {{
    if (!$('loopChk').checked) return {{ lo: 1, hi: total }};
    const i = at(g0).i;
    if (i < 0 || !SEQ[i]) return {{ lo: 1, hi: total }};
    const z = zoneOf(i, at(g0).local);
    const start = starts[i];
    return {{ lo: start + z.a, hi: Math.min(total, start + z.b) }};
  }}
  function tick() {{
    if (!playing) return;
    const fps = SEQ[at(+$('slider').value).i].fps || 25;
    let g = g0 + Math.floor((performance.now() - t0) / 1000 * fps * RATE);
    const {{ lo, hi }} = loopBounds();
    if (g > hi) {{
      if ($('loopChk').checked) {{
        t0 = performance.now(); g0 = lo; g = lo;
        // Take the SOUND back too. show() only re-points the audio when the
        // SCENE changes, and a loop inside one scene never changes it -- so the
        // narration carried on past the zone and was finished and silent after
        // one pass while the picture kept looping. That is what "the loop does
        // not work" sounds like even when every frame is right.
        const p = at(lo);
        if (aud.dataset.key) {{
          aud.currentTime = Math.max(0, (p.local - 1) / (SEQ[p.i].fps || 25));
          if (aud.paused && RATE >= AUDIO_RATE_FLOOR) aud.play().catch(() => {{}});
        }}
      }}
      else {{ stop(); show(total); return; }}
    }}
    show(g);
    if (g % 20 === 0) preload(g + 1);
  }}
  function preload(from) {{
    for (let k = from; k < from + 40 && k <= total; k++) {{
      const {{ i, local }} = at(k); const s = SEQ[i];
      new Image().src = `../${{s.base_slug}}/frames/frame_${{pad(Math.min(local, s.base_n))}}${{s.base_ext}}?v=${{ver}}`;
      if (s.over_slug)
        new Image().src = `../${{s.over_slug}}/frames/frame_${{pad(Math.min(local, s.over_n))}}${{s.over_ext}}?v=${{ver}}`;
    }}
  }}
  function play() {{
    playing = true; g0 = (+$('slider').value >= total) ? 1 : +$('slider').value;
    t0 = performance.now(); $('playBtn').innerHTML = '&#10074;&#10074; Pause';
    $('playBtn').classList.add('on'); preload(g0);
    // Put the sound where the PICTURE is before starting it. onSceneChange
    // only re-points the audio when the scene changes, so scrubbing WITHIN a
    // scene left the track wherever it had got to — press Play after dragging
    // back and the voice ran seconds ahead of the frame. The layered view has
    // always done this; the timeline never did.
    {{
      const {{ i, local }} = at(g0);
      if (aud.dataset.key) aud.currentTime = Math.max(0, (local - 1) / (SEQ[i].fps || 25));
    }}
    if (RATE >= AUDIO_RATE_FLOOR) {{
      aud.playbackRate = RATE;
      if (aud.dataset.key) aud.play().catch(() => {{}});
    }} else {{ aud.pause(); }}
    timer = setInterval(tick, 12);
  }}
  function stop() {{
    playing = false; if (timer) clearInterval(timer); timer = null;
    aud.pause();
    $('playBtn').innerHTML = '&#9654; Play'; $('playBtn').classList.remove('on');
  }}
  $('playBtn').onclick = () => playing ? stop() : play();
  $('rateSel').onchange = () => {{
    RATE = parseFloat($('rateSel').value);
    $('rateSel').classList.toggle('off1', RATE !== 1);
    $('status').textContent = RATE < AUDIO_RATE_FLOOR ? `Audio is off below ${{AUDIO_RATE_FLOOR}}x - the browser will not play a track that slow. The picture is still exact.` : '';
    if (RATE < AUDIO_RATE_FLOOR) aud.pause();
    else {{ aud.playbackRate = RATE; if (playing && aud.dataset.key) aud.play().catch(() => {{}}); }}
    if (!playing) return;
    g0 = +$('slider').value;
    t0 = performance.now();
  }};
  $('muteBtn').onclick = () => {{
    aud.muted = !aud.muted;
    $('muteBtn').innerHTML = aud.muted ? '&#128263;' : '&#128266;';
  }};
  // `which` still exists, because marks, Cut and Save each act on ONE layer.
  // It is now read off the ticks instead of a button: the single ticked layer
  // wins, and when both are ticked the SEGMENT is the target -- the confirms on
  // Cut and Save name it out loud, so it is never a silent choice.
  function syncWhich() {{
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
  }}

  const jump = d => {{ stop(); show(+$('slider').value + d); }};
  $('p1').onclick = () => jump(-1);
  $('n1').onclick = () => jump(1);
  $('p10').onclick = () => jump(-10);
  $('n10').onclick = () => jump(10);
  $('prevScene').onclick = () => {{ stop(); const {{ i }} = at(+$('slider').value); show(starts[Math.max(0, i - 1)] + 1); }};
  $('nextScene').onclick = () => {{ stop(); const {{ i }} = at(+$('slider').value); show(starts[Math.min(SEQ.length - 1, i + 1)] + 1); }};
  $('slider').addEventListener('mousedown', stop);
  $('slider').oninput = () => show(+$('slider').value);


  document.addEventListener('keydown', e => {{
    // A textarea is open whenever the VTT row under the pointer is, so every
    // one of these letters is a letter someone means to type. Space was the
    // loud one: it played the timeline instead of putting a space in the line.
    const t = e.target;
    if (t && (t.tagName === 'TEXTAREA' || t.tagName === 'INPUT'
              || t.isContentEditable) && t.type !== 'range') return;
    if (e.key === ' ') {{ $('playBtn').click(); e.preventDefault(); }}
    if (e.key === 'ArrowLeft')  {{ e.altKey ? jumpMark(-1) : jump(e.shiftKey ? -10 : -1); e.preventDefault(); }}
    if (e.key === 'ArrowRight') {{ e.altKey ? jumpMark(1)  : jump(e.shiftKey ?  10 :  1); e.preventDefault(); }}
    if (e.key === 'm' || e.key === 'M') {{ $('markBtn').click(); e.preventDefault(); }}
    if (e.key === '[') {{ $('prevScene').click(); e.preventDefault(); }}
    if (e.key === ']') {{ $('nextScene').click(); e.preventDefault(); }}
  }});

  // ── the list: EVERY scene, the ticked ones active ─────────────────────
  // Listing only what was on the timeline made every other scene LOOK deleted,
  // and left no way back to them without going out to the single-scene view.
  // The list is the store's full set; the ticks say which are on the timeline.
  const ON = new Set(SEQ.map(s => s.n));
  let ALL = null;

  async function loadScenes() {{
    try {{
      const r = await fetch(`/api/siblings?path=${{encodeURIComponent(SEQ[0].base_rel)}}`);
      const j = await r.json();
      if (j.error) throw new Error(j.error);
      ALL = j.by_version[String(j.current_version ?? 0)] || [];
    }} catch (e) {{
      // The list is a convenience; the timeline plays without it. Falling back
      // to SEQ keeps the panel honest rather than blank — it simply cannot
      // offer the scenes that are OFF the timeline.
      ALL = SEQ.map(s => ({{ n: s.n, label: s.label, missing: false,
                            dur: +(s.base_n / (s.fps || 25)).toFixed(2) }}));
      status('scene list unavailable — ' + e.message);
    }}
    renderScenes();
  }}

  // Scenes whose edits are blocked. A SET OF LOCKS, not of permissions, so the
  // empty default means everything stays editable exactly as before — the lock
  // changes nothing until you deliberately turn one on. Per page load: it is a
  // guard while you work, not a property of the file.
  // Keyed "<scene>:<layer>", because a scene has TWO editable things and they
  // are locked independently: you routinely finish the footage while the avatar
  // is still being retimed. A set of LOCKS, not permissions, so empty means
  // everything stays editable exactly as before.
  const LOCKED = new Set();
  const lockKey = (n, layer) => `${{n}}:${{layer}}`;
  const isLocked = (n, layer) => LOCKED.has(lockKey(n, layer));

  // Gate the controls that CHANGE something, against the scene they would act
  // on. Cut and Save are included: they write files, which is the thing a lock
  // most needs to stop.
  function refreshEditGate() {{
    syncWhich();
    const n = currentSceneN();
    // Gate against the layer that is LIT, because that is the one every edit
    // acts on. Locking the segment must not stop you retiming the avatar.
    const blocked = n != null && isLocked(n, which);
    // The row buttons are enabled only on the scene under the playhead, and
    // only when that row has at least one layer ticked.
    for (const b of document.querySelectorAll('.rowbtn')) {{
      const rn = +b.dataset.n;
      const isCur = rn === n;
      const any = !isLocked(rn, 'base') || !isLocked(rn, 'overlay');
      b.disabled = !isCur || !any;
      b.title = !isCur
          ? `Scene ${{rn}} is not under the pointer. Only the scene the pointer is inside can be`
            + ` edited, because that is the only one with a current frame — click this row's name to go there.`
        : !any
          ? `Tick this row's segment or overlay box first. Those ticks choose which track an edit touches,`
            + ` and with neither ticked there is nothing to act on.`
        : (b.dataset.kind === 'dup'
            ? `Duplicate the frame on screen, on scene ${{rn}}'s ticked track(s). Same as + Frame below.`
            : `Delete the frame on screen, from scene ${{rn}}'s ticked track(s). Same as - Frame below.`);
    }}
    // Save Scenes and Save All are NOT in this list. The gate is about the
    // track under the pointer being locked, and those two act on every scene on
    // the timeline — greying out the only way to save, because of one scene the
    // pointer happens to be sitting in, would be a trap.
    for (const id of ['addFrame', 'delFrame', 'addZone', 'delZone',
                      'addL', 'addR', 'delL', 'delR']) {{
      const el = $(id);
      if (el) {{
        el.disabled = blocked;
        // Keep the control's OWN tip and add the reason on top of it, rather
        // than replacing it. This used to assign '' when not blocked, which
        // silently erased the help text written into the markup — the six
        // controls listed here were the six on the page with an empty title.
        if (el.dataset.tip === undefined) el.dataset.tip = el.getAttribute('title') || '';
        el.title = blocked
          ? `Unavailable: the ${{which === 'base' ? 'segment' : 'overlay'}} of scene ${{n}} is locked.`
            + ` Tick that track's box in the list to edit it.`
            + (el.dataset.tip ? `\n\n${{el.dataset.tip}}` : '')
          : el.dataset.tip;
      }}
    }}
  }}
  // Row styling reflects BOTH locks: one layer locked is dimmed, both locked is
  // struck through. A single "locked" class could not tell those apart.
  function paintLockState() {{
    for (const el of document.querySelectorAll('.scene')) {{
      const n = +el.dataset.n;
      const b = isLocked(n, 'base'), o = isLocked(n, 'overlay');
      el.classList.toggle('lk-base', (b || o) && !(b && o));
      el.classList.toggle('lk-both', b && o);
      el.classList.remove('locked');
    }}
  }}

  const currentSceneN = () => (SEQ[curI()] || {{}}).n ?? null;

  // Totals, footing the list: how many scenes, how long they run, and how many
  // frames each LAYER holds. The two frame totals stay SEPARATE -- they are
  // different files of different lengths, and one combined number would mean
  // nothing. Spacers keep each total under the column it sums.
  function renderTotals(rows) {{
    const usable = rows.filter(r => !r.missing);
    const secs = usable.reduce((a, r) => a + (r.dur || 0), 0);
    const segF = usable.reduce((a, r) => a + (r.frames || 0), 0);
    const ovF  = usable.reduce((a, r) => a + (r.overlay_frames || 0), 0);

    const d = document.createElement('div');
    d.className = 'scene totals';
    d.title = `${{usable.length}} scenes, ${{secs.toFixed(2)}}s, `
            + `${{segF}} segment frames, ${{ovF}} overlay frames`;
    const pad = kind => {{
      const x = document.createElement('span');
      x.className = 'cbpad ' + kind;
      return x;
    }};
    d.appendChild(pad('pk'));

    const body = document.createElement('span');
    body.style.cssText = 'display:flex;gap:8px;align-items:baseline;flex:1 1 0;min-width:0;overflow:hidden';
    body.innerHTML = `<span class="lab">${{usable.length}} scenes</span>`
                   + `<span class="dur">${{secs.toFixed(2)}}s</span>`;
    d.appendChild(body);

    for (const [layer, total] of [['base', segF], ['overlay', ovF]]) {{
      d.appendChild(pad('ed'));
      const f = document.createElement('span');
      f.className = 'frames' + (layer === 'overlay' ? ' ov' : '');
      f.textContent = total;
      f.title = `${{total}} ${{layer === 'base' ? 'segment' : 'overlay'}} frames in total`;
      d.appendChild(f);
    }}
    for (let k = 0; k < 2; k++) {{
      const x = document.createElement('span');
      x.className = 'cbpad btn';   // stands in for a +/- so the totals still line up
      d.appendChild(x);
    }}
    $('sceneList').appendChild(d);
  }}

  function renderScenes() {{
    $('sceneList').innerHTML = '';
    for (const it of ALL) {{
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
        ? `Scene ${{it.n}} has no footage, so it cannot go on the timeline.`
        : `Put scene ${{it.n}} on the timeline, or take it off. Ticking does not rebuild by`
          + ` itself — press Rebuild underneath once the set is the one you want.`;
      cb.onclick = ev => {{ ev.stopPropagation(); updatePick(); }};
      d.appendChild(cb);

      const body = document.createElement('span');
      body.style.cssText = 'display:flex;gap:8px;align-items:baseline;flex:1 1 0;min-width:0;overflow:hidden';
      body.innerHTML = `<span class="num">${{it.n}}</span>` +
        `<span class="lab">${{it.label || it.n}}</span>` +
        (it.missing ? `<span class="ovv" style="color:#e05555;border-color:#7a3a3a">missing</span>` : '') +
        `<span class="dur">${{it.dur ?? '?'}}s</span>`;
      // Only a scene ON the timeline has anywhere to jump to. For the rest the
      // checkbox is the whole interaction, so the name is not dressed up as
      // clickable when clicking it can do nothing.
      if (on) {{
        const i = SEQ.findIndex(s => s.n === it.n);
        body.style.cursor = 'pointer';
        body.onclick = () => {{ stop(); show(starts[i] + 1); }};
        d.title = `${{it.n}} ${{it.label || ''}} — jump to this scene`;
      }} else {{
        d.title = `${{it.n}} ${{it.label || ''}} — tick to put it on the timeline`;
      }}
      d.appendChild(body);
      // Two locks and two counts: the SEGMENT (the footage) and the OVERLAY
      // (the avatar). They are separate controls because they are separate
      // files with separate lengths, edited one layer at a time.
      const addPair = (layer, count, exact, present) => {{
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.className = 'edcb' + (layer === 'overlay' ? ' ov' : '');
        cb.dataset.n = it.n; cb.dataset.layer = layer;
        cb.checked = !isLocked(it.n, layer);
        cb.disabled = !present;
        cb.title = present
          ? `Include this scene's ${{layer === 'base' ? 'SEGMENT (the footage)' : 'OVERLAY (the avatar)'}}`
            + ` in edits. Untick it to protect this track while you work on the other one —`
            + ` + / - Frame, + / - Zone, Cut and Save all skip an unticked track.`
          : `This scene has no ${{layer === 'base' ? 'segment' : 'overlay'}}, so there is nothing to edit.`;
        cb.onclick = ev => {{
          ev.stopPropagation();
          if (cb.checked) LOCKED.delete(lockKey(it.n, layer));
          else LOCKED.add(lockKey(it.n, layer));
          paintLockState();
          refreshEditGate();
          renderReport();
        }};
        d.appendChild(cb);

        const fr = document.createElement('span');
        fr.className = 'frames' + (layer === 'overlay' ? ' ov' : '') + (exact ? '' : ' est');
        fr.dataset.n = it.n; fr.dataset.layer = layer;
        fr.textContent = count == null ? '—' : (exact ? String(count) : '~' + count);
        fr.title = count == null
          ? `No ${{layer === 'base' ? 'segment' : 'overlay'}} on this scene, so there is nothing to count.`
          : (exact
              ? `${{count}} frames in this scene's ${{layer === 'base' ? 'segment' : 'overlay'}}, counted frame by frame.`
                + ` The two tracks are separate files and drift apart as you edit — Update Frame Imbalance evens them up.`
              : `About ${{count}} frames, read from the file header without extracting it.`
                + ` It can be out by one until the scene has been opened.`);
        d.appendChild(fr);
      }};
      addPair('base', it.frames, it.frames_exact, !it.missing);
      addPair('overlay', it.overlay_frames, it.overlay_frames_exact, !!it.overlay);

      // +/- act on whichever layers THIS ROW has ticked. The ticks already say
      // what may be edited, so they choose the target too rather than a
      // separate control saying it a second way.
      for (const [kind, glyph, cls] of [['dup', '+', 'plus'], ['del', '\u2212', 'minus']]) {{
        const b = document.createElement('button');
        b.className = `rowbtn ${{cls}}`;
        b.dataset.n = it.n; b.dataset.kind = kind;
        b.textContent = glyph;
        b.onclick = ev => {{ ev.stopPropagation(); rowEdit(it.n, kind); }};
        d.appendChild(b);
      }}
      // Undo and Save for THIS scene. Both are lit only while the scene has
      // unsaved changes -- the same condition, because a save is what empties
      // the history and an undo is what walks back through it.
      const hist = histOf(it.n);
      for (const [act, glyph, cls, tip] of [
            ['undo', '\u21b6', 'undo', 'Undo the last change to this scene'],
            ['save', '\u2913', 'save', 'Save this scene to sandbox and clear its history']]) {{
        const hb = document.createElement('button');
        hb.className = `histbtn ${{cls}}`;
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
        hb.disabled = hist.length === 0;
        // Dirty the moment this scene has an unsaved change; pristine again
        // when it is saved OR when every change has been undone — both end with
        // an empty history, which is the one thing that decides it.
        hb.classList.toggle('dirty', act === 'save' && hist.length > 0);
        hb.title = hist.length === 0
          ? `Scene ${{it.n}} has no unsaved changes, so there is nothing to ${{act}}.`
            + ` These two light up as soon as you edit this scene.`
          : `${{tip}}. ${{hist.length}} change${{hist.length === 1 ? '' : 's'}} pending on scene ${{it.n}};`
            + ` undo walks back one per click, and save clears them all.`;
        hb.onclick = ev => {{ ev.stopPropagation(); act === 'undo' ? undoScene(it.n) : saveScene(it.n); }};
        d.appendChild(hb);
      }}

      $('sceneList').appendChild(d);
    }}
    renderTotals(ALL);
    paintLockState();
    refreshEditGate();
    updatePick();
    paintBar();
  }}

  // Rebuilding is a NAVIGATION, not a live edit: a different set of scenes is a
  // different timeline with different frame numbers, and pretending otherwise
  // would leave the slider pointing at a frame that no longer exists.
  const picked = () => [...document.querySelectorAll('.pick')]
    .filter(c => c.checked).map(c => +c.dataset.n).sort((a, b) => a - b);
  function updatePick() {{
    const ns = picked();
    const same = ns.length === ON.size && ns.every(n => ON.has(n));
    $('rebuildBtn').disabled = same || ns.length === 0;
    balanceReport();
    $('rebuildBtn').innerHTML = ns.length === 0
      ? 'Tick at least one scene'
      : same ? `&#10003; These ${{ns.length}} are on the timeline`
             : `&#8635; Rebuild with ${{ns.length}} scene${{ns.length === 1 ? '' : 's'}}`;
  }}
  $('rebuildBtn').onclick = () => {{
    const ns = picked();
    if (!ns.length) return;
    status(`Rebuilding with ${{ns.length}} scene(s)…`);
    location.href = `/api/open-seq-go?root=${{encodeURIComponent(ROOT_REL)}}&ns=${{ns.join(',')}}`;
  }};

  // A function, not a one-off: `total` is only known after reindex(), and an
  // edit changes it. Written once at load it read "0.0s" — a number that looked
  // like a measurement and was really just the order the lines ran in.
  // The note this wrote is gone from the page. Kept as a no-op rather than
  // chased through its three callers, all of which fire after a length change.
  function renderNote() {{}}

  reindex(); rebuildBar(); paint(); renderNote(); loadScenes(); show(1);
  paintPaste();
  loadRenumberState();
  loadVtt();
  renderReport();   // row 4 must say something before the first click
</script></body></html>
"""


def write_seq(outdir, manifest, box=750, root_rel=""):
    """Write the multi-scene timeline viewer."""
    total = sum(m["base_n"] for m in manifest)
    names = ", ".join(str(m["n"]) for m in manifest)
    html = SEQ_TEMPLATE.format(
        player_label=label(),
        title=f"timeline: scenes {names}", box=box, total=max(1, total),
        manifest=json.dumps(manifest), root_rel=root_rel)
    with open(os.path.join(outdir, "viewer.html"), "w") as fh:
        fh.write(html)
