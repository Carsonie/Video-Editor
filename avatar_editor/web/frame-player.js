// Avatar Editor — the players behind the three Play buttons.
//
// Split out of gap-builder.js on 2026-09-02 (Carson's own call): the audio
// side had grown from "one shared <video> a Sound Bits row loads into" to
// three buttons, a run queue and an audibility rule, all tangled through a
// file whose actual subject is the library and the two frame rows.
// Everything that acts on a PLAYER now lives here; gap-builder.js hands
// over what it owns and calls in.
//
// ONE ENGINE PER PANEL, NOT ONE SHARED ONE
// It began as a single <video> that every button drove. That was wrong for
// the same reason the frame stepper was wrong: pressing Play in the Frame
// Selector Menu reached across the page and took over the Audio Menu's
// previewer, so a panel nobody was pointing at started showing and saying
// something else. FramePlayer is now a FACTORY — call create() once per
// panel and each gets its own <video>, its own name label, its own speed
// dropdown and its own run. A panel's Play button only moves its own panel.
//
// The one thing they share is the room's air: starting a run on one engine
// pauses every other, because two voices at once is never what was wanted.
// That is the ONLY cross-talk, and it all goes through stopOthers().
//
// THE ONE FILE HERE WITH ITS OWN SCOPE
// app.js and gap-builder.js deliberately share one flat top-level scope so
// each can reach the other's declarations by name. This file does NOT join
// that arrangement — it is wrapped, and everything it needs is defined
// inside it. The only way in is the small objects it returns, so a player
// cannot quietly grow a dependency on some unrelated global again, which
// is how the tangle it was extracted from started.
'use strict';

// ═════════════════════════════════════════════════════════════════════════
// WHAT gap-builder.js LENDS US
// ═════════════════════════════════════════════════════════════════════════
// The library itself (which clips are checked), the Frame Selector's row of
// frames, and the Clip-Gap Builder's own current clip all belong to
// gap-builder.js and change as the user works. They arrive as FUNCTIONS,
// not values, so this file always reads what is true NOW rather than a copy
// taken at wiring time — PICKED and LIB_FRAMES are both REASSIGNED as the
// user works, so a captured reference would go stale the first time a box
// was ticked.
//
// Kept apart from the engines on purpose: this is the ONE description of
// the library, read by all the scenarios, while an engine knows only about
// its own <video>. An engine able to reach in here would be back to knowing
// which panel it belongs to.
const LibSources = (function () {
  let src = {
    picked: () => [],        // PICKED — the checked clips, in checked order
    frames: () => [],        // LIB_FRAMES — the Frame Selector's flat row
    viewIndices: () => [],   // which of those the row is showing right now
    order: () => [],         // LIB_ORDER — every library path, as DISPLAYED
    showFrame: () => {},     // move the Frame Selector's viewer to a position
    slider: () => null,      // the Frame Selector's own slider element
    builderFrames: () => [], // BUILDER_FRAMES — the Clip-Gap Builder's row
    builderShow: () => {},   // move the Clip-Gap Builder's viewer
    builderSlider: () => null,
  };

  // The checked clips in the order the LIBRARY SHOWS them, top to bottom —
  // not the order the boxes happened to be ticked in, which is what PICKED
  // records. Carson's own rule for the Audio Menu's stack: it plays down
  // the list the way you read it.
  function checkedInOrder() {
    const picked = src.picked();
    return src.order()
      .map(path => picked.find(c => c.path === path))
      .filter(Boolean);
  }

  // The distinct clips behind the Frame Selector's row, in the order they
  // first appear. DISTINCT matters: the row is FRAMES, and a 482-frame clip
  // is 482 entries pointing at one file — one per frame would replay the
  // same voice hundreds of times. Reads the CURRENT view, so "Show Selected
  // on Timeline" narrows the run to just the selection.
  //
  // Silent clips are left out here, and out of every other run. Every .webm
  // in this library carries an Opus stream, INCLUDING the idle loops and
  // gap-fillers, whose tracks are silent — so "has an audio stream" was
  // never the right question. has_audio is measured server-side (see
  // has_audible() in serve.py) and travels with each clip. Playing a silent
  // 10-second idle loop first is exactly what made a run look like it had
  // started on the wrong clip.
  function distinctAudible(frames, indices) {
    const seen = new Set(), out = [];
    for (const i of indices) {
      const c = frames[i]?.clip;
      if (c && c.has_audio && !seen.has(c.path)) { seen.add(c.path); out.push(c); }
    }
    return out;
  }

  const selectorClips = () => distinctAudible(src.frames(), src.viewIndices());

  // The Clip-Gap Builder's row, in order — EVERY distinct clip in it, not
  // only the ones that can be heard. This panel is a timeline: the point
  // of its Play is watching the collection go past, and a still or an idle
  // loop is as much a part of it as a spoken line. It plays silently and
  // the frames still step. (The other two panels filter, because there the
  // point IS the voice.) No view filter either — this row IS the
  // collection, with nothing hidden.
  function builderClips() {
    const frames = src.builderFrames(), seen = new Set(), out = [];
    for (const f of frames) {
      const c = f?.clip;
      if (c && !seen.has(c.path)) { seen.add(c.path); out.push(c); }
    }
    return out;
  }

  // Where frame k of a clip sits in a row, or -1. Matched on the frame's
  // OWN index within its clip (`local`), never on "the clip starts at
  // position P, so frame k is at P+k" — the Clip-Gap Builder's row is
  // built by pasting, so a clip can appear in pieces, out of order, or
  // more than once, and only `local` survives all three.
  function posOf(frames, indices, clip, k) {
    for (let p = 0; p < indices.length; p++) {
      const f = frames[indices[p]];
      if (f && f.clip.path === clip.path && f.local === k) return p;
    }
    return -1;
  }

  return {
    configure(sources) { Object.assign(src, sources); },
    picked: () => src.picked(),
    frames: () => src.frames(),
    viewIndices: () => src.viewIndices(),
    showFrame: pos => src.showFrame(pos),
    slider: () => src.slider(),
    builderFrames: () => src.builderFrames(),
    builderShow: i => src.builderShow(i),
    builderSliderEl: () => src.builderSlider(),
    checkedInOrder, selectorClips, builderClips, posOf,
  };
})();

// ═════════════════════════════════════════════════════════════════════════
// THE ENGINE — one instance per panel
// ═════════════════════════════════════════════════════════════════════════
// Pure: it knows how to load a file, walk a queue, and say whether it is
// playing. It does NOT know which clips belong to it, what its button
// should say, or which panel it sits in. All of that comes from the
// scenario that created it.
const FramePlayer = (function () {

  const engines = [];

  // Two voices at once is never what was wanted, so a starting run quiets
  // the others. Deliberately a PAUSE, not a reset: the other panel keeps
  // its clip loaded and its own place in it, ready to resume.
  function stopOthers(me) {
    for (const e of engines) if (e !== me) e.pause();
  }

  function create(dom) {
    const player = document.getElementById(dom.player);
    const video = document.getElementById(dom.video);
    const nameEl = document.getElementById(dom.name);
    const rateEl = document.getElementById(dom.rate);
    const emptyText = dom.empty || 'Nothing loaded';

    // Which file is loaded right now — not just "is it playing" but WHICH,
    // so a toggle can tell "mine is already playing, so pause" from
    // "something else is playing, so switch to mine."
    let currentPath = null;
    let currentClip = null;   // ...and the clip object it came from

    // A run is a set of clips played one after another. Its queue is a
    // SNAPSHOT taken when Play is pressed; if the collection behind it
    // changes, the run is either re-pointed (resync) or ended outright
    // (endRun) rather than left to drift.
    let queue = [];
    let queueLen = 0;      // what it started with, for the "2/5" label

    // What to redraw after anything that could change a button. Supplied
    // by the scenarios, because only they know the wording. A LIST: the
    // Audio Menu's engine renders two buttons, its own and the Clip-Gap
    // Builder's, because those two still share it.
    const renderers = [];
    const redraw = () => { for (const fn of renderers) fn(); };

    const active = () => queue.length > 0;
    const playing = () => !video.paused;
    function clearRun() { queue = []; queueLen = 0; }

    // Anything that wants to move WITH the voice registers here, and the
    // engine calls it on every animation frame while something is playing.
    // Kept generic on purpose: the engine still knows nothing about frames,
    // rows or panels — it only knows how to say "another moment passed."
    //
    // requestAnimationFrame, NOT the video's own `timeupdate`, which fires
    // about four times a second — far too coarse for 25fps. Note that a
    // browser suspends rAF entirely in a hidden or background tab, so a
    // picture only moves while the panel is actually on screen.
    const tickers = [];
    let raf = null;
    function frame() {
      raf = null;
      if (video.paused) return;
      for (const fn of tickers) fn(video.currentTime, video.duration, currentClip);
      raf = requestAnimationFrame(frame);
    }
    function startTicking() { if (raf === null && tickers.length) raf = requestAnimationFrame(frame); }
    function stopTicking() { if (raf !== null) { cancelAnimationFrame(raf); raf = null; } }

    const label = (pos, f) =>
      queueLen > 1 ? `${pos}/${queueLen} — ${f.name}` : f.name;

    function playFile(f, text, fromRun) {
      // A single-clip play takes this engine over, so a run already going
      // is cancelled rather than hijacking the next `ended` and carrying
      // on with its own next item.
      if (!fromRun) clearRun();
      stopOthers(api);
      player.hidden = false;
      nameEl.textContent = text;
      currentPath = f.path;
      currentClip = f;
      video.src = `/api/lib_media?path=${encodeURIComponent(f.path)}`;
      video.playbackRate = +rateEl.value;
      video.play();
      player.scrollIntoView({block: 'nearest'});
      redraw();
    }

    function playHead() {
      const f = queue[0];
      if (!f) { clearRun(); redraw(); return; }
      playFile(f, label(queueLen - queue.length + 1, f), true);
    }

    // Step to the next clip. Reached two ways and BOTH matter: one that
    // ends normally, and one that fails to load at all — so a run can
    // never stall on a file the browser refuses.
    function advance() {
      queue.shift();
      if (queue.length) playHead();
      else { clearRun(); redraw(); }
    }

    const api = {
      // Add something to redraw after any state change, and run it once.
      render(fn) { renderers.push(fn); fn(); return api; },
      redraw,

      // Add something to move WITH the voice — called on every animation
      // frame while this engine is playing, with (currentTime, duration,
      // the clip being heard).
      tick(fn) { tickers.push(fn); return api; },

      // ── asking ──────────────────────────────────────────────────────
      playing, active,
      loaded: () => currentPath,
      isLoaded: f => !!f && currentPath === f.path,
      queueNames: () => queue.map(c => c.name),

      // ── playing ─────────────────────────────────────────────────────
      // Play a LIST as one run. Pressing the same button while this
      // engine's own run is going means pause/resume instead. Returns
      // false when there was nothing for it to play.
      run(clips) {
        if (active()) { api.toggleLoaded(); return true; }
        if (!clips.length) return false;
        queue = [...clips];
        queueLen = queue.length;
        playHead();
        return true;
      },

      // Play/pause ONE clip, with no run behind it.
      playOne(f, text) {
        if (!f) return;
        if (currentPath === f.path && playing()) video.pause();
        else playFile(f, text ?? f.name, false);
      },

      // Plain transport for whatever single clip is already loaded.
      toggleLoaded() {
        if (video.paused) { stopOthers(api); video.play(); } else video.pause();
      },

      pause() { if (!video.paused) video.pause(); },

      // Re-point a run that is ALREADY GOING at a changed set of clips,
      // without interrupting the one being heard. Ticking another box
      // mid-run should extend the run, not stop the audio — the clip
      // playing right now stays exactly where it is, and what follows is
      // whatever comes after it in the new list. A clip just removed is
      // simply no longer in that remainder.
      resync(clips) {
        if (!active()) return false;
        const cur = queue[0];
        // Where the run is up to, read BEFORE the queue is rebuilt — the
        // label has to keep counting from here, not restart at 1/N.
        const pos = queueLen - queue.length + 1;
        const at = clips.findIndex(c => c.path === cur.path);
        const rest = at >= 0 ? clips.slice(at + 1)
                             : clips.filter(c => c.path !== cur.path);
        queue = [cur, ...rest];
        queueLen = pos - 1 + queue.length;
        // The clip keeps playing untouched, but "1/2" is now wrong — the
        // run it belongs to just got longer or shorter. Rewrite the count
        // only; the <video> is deliberately not reloaded.
        nameEl.textContent = label(pos, cur);
        redraw();
        return true;
      },

      // ── stopping ────────────────────────────────────────────────────
      // The collection behind this run changed in a way that makes the run
      // meaningless, so end it. This was a real bug: play, pause, change
      // what is checked, press play again — and it RESUMED the stale run,
      // the old clip's voice against the new collection's pictures. Which
      // is exactly what "it played the wrong clip" looked like.
      endRun() { stopTicking(); clearRun(); video.pause(); redraw(); },

      // Back to nothing loaded at all.
      reset() {
        stopTicking();
        clearRun();
        video.pause();
        video.removeAttribute('src');
        currentPath = null;
        currentClip = null;
        player.hidden = true;
        nameEl.textContent = emptyText;
        redraw();
      },
    };

    rateEl.onchange = () => { video.playbackRate = +rateEl.value; };
    video.onplay = () => { redraw(); startTicking(); };
    video.onpause = () => { redraw(); stopTicking(); };
    video.onended = () => { stopTicking(); if (active()) advance(); else redraw(); };
    // A file the browser cannot play must not end the run early.
    video.onerror = () => { if (active()) advance(); };

    engines.push(api);
    return api;
  }

  return {create, all: () => engines.slice()};
})();

// ═════════════════════════════════════════════════════════════════════════
// THE THREE SCENARIOS
// ═════════════════════════════════════════════════════════════════════════
// FramePlayer above is the pure engine — it knows how to run a queue and
// nothing else. It does NOT know which clips any one button plays, what
// that button should say, or which panel it lives in. That is what these
// three are: one per button, each holding only its own specifics.
//
// A click traces straight through, and each step says so:
//
//   the button  →  gap-builder.js's onclick  →  <Scenario>.play()
//                                            →  its own engine
//
// Each logs "Inside: <name>" on the way through, so the console shows
// which scenario a click actually reached.

// ── 1. the Audio Menu's "Play" ───────────────────────────────────────────
// THE ORIGINALS: every clip checked in sarah_clips/libs that can actually
// be heard. Plays into the small player under the library.
const OriginalAudio = (function () {
  const btn = document.getElementById('gmSoundBitPlayPause');
  const P = FramePlayer.create({
    player: 'soundBitPlayer', video: 'soundBitVideo',
    name: 'soundBitName', rate: 'soundBitRate',
    empty: 'No Sound Bit loaded',
  });

  // THE STACK. Not worked out at the moment Play is pressed — it is kept
  // up to date by every checkbox event, so it is always in step with what
  // is actually ticked (Carson's own rule). Play/Pause then just walks it.
  //
  // Ordered TOP TO BOTTOM as the library shows it, not by when each box was
  // ticked: tick catalogue-search and then intro-and-login, and it still
  // plays intro-and-login first, because that is what you see.
  let STACK = [];

  // Green means "there is something here that can actually be HEARD" — not
  // merely "there is something". A pile of stills, idle loops or gap
  // fillers has frames but no voice, so it stays white.
  P.render(() => {
    btn.textContent = P.playing() ? 'Pause' : 'Play';
    btn.disabled = !STACK.length && !P.loaded();
    btn.classList.toggle('ready', STACK.length > 0);
    const picked = LibSources.picked().length;
    btn.title = STACK.length
      ? `Plays every checked clip that has a voice in it — ${STACK.length} of `
        + `them, in library order, one after another. Click again to pause.`
      : picked
        ? `${picked} checked, but none of them carry any audio — nothing to play.`
        : 'Check one or more clips in sarah_clips/libs above first.';
  });

  // Called on every tick/untick — see toggleLibClip() in gap-builder.js.
  function rebuild() {
    STACK = LibSources.checkedInOrder().filter(c => c.has_audio);
    console.log('Inside: OriginalAudio.rebuild', {stack: STACK.map(c => c.name)});
    // If this stack's own run is playing right now, keep it playing and
    // just re-point what comes NEXT — ticking another box mid-run should
    // add to the run, not stop the voice.
    P.resync(STACK);
    P.redraw();
    return STACK;
  }

  function play() {
    console.log('Inside: OriginalAudio', {stack: STACK.map(c => c.name)});
    // Nothing ticked that can be heard — fall back to plain play/pause
    // for whatever single clip a row's ▶ left loaded.
    if (!P.run(STACK)) P.toggleLoaded();
  }

  // A Sound Bits row's own ▶ lands here: one file, no run.
  function playClip(f, text) { P.playOne(f, text); }

  return {play, rebuild, playClip, stack: () => STACK, engine: () => P};
})();

// ── 2. the Frame Selector Menu's "Play Frame Selector's Audio" ───────────
// THE FRAME SELECTOR'S OWN COLLECTION: the distinct clips behind the row as
// it stands — narrowed to just the selection while "Show Selected on
// Timeline" is on.
//
// Plays into the Frame Selector's OWN player, inside the Frame Selector's
// OWN panel. It used to drive the Audio Menu's one, which meant pressing
// this button changed what a panel across the page was showing and saying.
// Carson's call, and the same rule as the frame stepper before it: a
// panel's button moves that panel and nothing else.
const FrameSelector = (function () {
  const btn = document.getElementById('gmLibPlayPause');
  const P = FramePlayer.create({
    player: 'fsPlayer', video: 'fsVideo',
    name: 'fsName', rate: 'fsRate',
  });

  function clips() { return LibSources.selectorClips(); }

  P.render(() => {
    btn.textContent = P.playing()
      ? "Pause Frame Selector's Audio" : "Play Frame Selector's Audio";
    const n = clips().length;
    const rowHas = LibSources.viewIndices().length;
    btn.disabled = !n;
    btn.classList.toggle('ready', n > 0);
    btn.title = n
      ? `Plays the Frame Selector's own collection — the ${n} clip`
        + `${n === 1 ? '' : 's'} in it with a voice, in row order, one after `
        + `another, in this panel's own player below. With "Show Selected on `
        + `Timeline" on, that is just the selection. Click again to pause.`
      : rowHas
        ? 'The frames in the Frame Selector carry no audio — nothing to play.'
        : 'Check a clip in sarah_clips/libs above to fill the Frame Selector first.';
  });

  // ── the frames follow the voice ─────────────────────────────────────
  // THE POINT of this button. The row holds the Frame Selector's own
  // frames; the run plays their voices; and this walks the panel's own
  // viewer through those same frames in time with what is being heard.
  // The Frame counter and the slider move with it, because they are what
  // showFrame() updates.
  //
  // The frame comes from the audio clock as a FRACTION of the clip
  // (currentTime / duration * clip.n) rather than assuming 25fps, so any
  // speed from 0.125x to 2x stays in step.
  //
  // Touches the viewer only when the computed frame actually CHANGES, so
  // this costs one image swap per frame rather than one per animation tick.
  //
  // Where the clip's frames START in the row is looked up per tick rather
  // than cached: "Show Selected on Timeline" can be switched mid-run, and
  // the answer moves when it is.
  P.tick((t, dur, clip) => {
    if (!clip || !clip.n || !isFinite(dur) || dur <= 0) return;
    const k = Math.min(clip.n - 1, Math.floor(t / dur * clip.n));
    // The view can filter this frame out entirely; leave the picture where
    // it is rather than jumping somewhere wrong.
    const pos = LibSources.posOf(LibSources.frames(),
                                 LibSources.viewIndices(), clip, k);
    const slider = LibSources.slider();
    if (pos >= 0 && slider && +slider.value !== pos) {
      slider.value = pos;
      LibSources.showFrame(pos);
    }
  });

  function play() {
    console.log('Inside: FrameSelector', {clips: clips().map(c => c.name)});
    P.run(clips());
  }

  // The row was rebuilt underneath this run, so every index it held is
  // meaningless — end it outright rather than re-point it.
  function endRun() { P.endRun(); }

  return {play, clips, endRun, engine: () => P};
})();

// ── 3. the Gap Builder Menu's "Play Clip-Gap Builder's Audio" ───────────
// THE CLIP-GAP BUILDER'S OWN: whichever clip that panel is showing right
// now. Still ONE clip rather than a run, and still borrowing the Audio
// Menu's player — this is the button that has not been reworked yet.
const GapBuilder = (function () {
  const btn = document.getElementById('gmBuilderPlayPause');
  const P = FramePlayer.create({
    player: 'gbPlayer', video: 'gbVideo',
    name: 'gbName', rate: 'gbRate',
  });

  function clips() { return LibSources.builderClips(); }

  P.render(() => {
    // Carson's rule for this button: green whenever the collection has
    // frames to run. Not "has a voice in it" — that is the other two
    // buttons' question, and asking it here left a full collection of
    // frames looking like there was nothing to play.
    const rowHas = LibSources.builderFrames().length;
    const n = clips().length;
    btn.disabled = !rowHas;
    btn.classList.toggle('ready', rowHas > 0);
    btn.textContent = P.playing()
      ? "Pause Clip-Gap Builder's Audio" : "Play Clip-Gap Builder's Audio";
    btn.title = rowHas
      ? `Runs this collection — ${rowHas} frame${rowHas === 1 ? '' : 's'} from `
        + `${n} clip${n === 1 ? '' : 's'}, in row order, in the viewer above, `
        + `with each clip's own voice where it has one. Click again to pause.`
      : 'Build the collection above first.';
  });

  // ── the frames follow the voice ─────────────────────────────────────
  // Its own viewer, its own row, its own voice — the same arrangement the
  // Frame Selector has, over a different collection. This row is BUILT by
  // pasting, so it can hold a clip in pieces, out of order or twice over;
  // posOf() matches each frame by its own index within its clip, which is
  // the only thing that survives all three.
  P.tick((t, dur, clip) => {
    if (!clip || !clip.n || !isFinite(dur) || dur <= 0) return;
    const frames = LibSources.builderFrames();
    const k = Math.min(clip.n - 1, Math.floor(t / dur * clip.n));
    const pos = LibSources.posOf(frames, frames.map((_, i) => i), clip, k);
    const slider = LibSources.builderSliderEl();
    if (pos >= 0 && slider && +slider.value !== pos) {
      slider.value = pos;
      LibSources.builderShow(pos);
    }
  });

  function play() {
    console.log('Inside: GapBuilder', {clips: clips().map(c => c.name)});
    P.run(clips());
  }

  // The row was rebuilt underneath this run, so every position it held is
  // meaningless — end it rather than re-point it.
  function endRun() { P.endRun(); }

  return {play, clips, endRun, engine: () => P};
})();

// ═════════════════════════════════════════════════════════════════════════
// THE ONE DOOR gap-builder.js AND app.js COME THROUGH
// ═════════════════════════════════════════════════════════════════════════
const Players = {
  // Hand over what gap-builder.js owns. Call once, after those exist.
  // The BUTTONS are not wired here — gap-builder.js owns the clicks and
  // routes each to its own scenario above, so a trace reads
  // button → gap-builder → scenario → engine.
  configure(sources) { LibSources.configure(sources); Players.refresh(); },

  // Recompute every button's wording, colour, enabled state and tooltip.
  refresh() { for (const e of FramePlayer.all()) e.redraw(); },

  // Back to nothing loaded, in every panel.
  reset() { for (const e of FramePlayer.all()) e.reset(); },
};
