// Avatar Editor — the player behind all three Play buttons.
//
// Split out of gap-builder.js on 2026-09-02 (Carson's own call): the audio
// side had grown from "one shared <video> a Sound Bits row loads into" to
// three buttons, a run queue, an audibility rule and a picture-follows-the-
// voice animation, all tangled through a file whose actual subject is the
// library and the two frame rows. Everything that acts on the PLAYER now
// lives here; gap-builder.js hands over what it owns and calls in.
//
// THE ONE FILE HERE WITH ITS OWN SCOPE
// app.js and gap-builder.js deliberately share one flat top-level scope so
// each can reach the other's declarations by name. This file does NOT join
// that arrangement — it is wrapped, and everything it needs is defined
// inside it. The only way in is the small object it returns, so the player
// cannot quietly grow a dependency on some unrelated global again, which is
// how the tangle it was extracted from started.
//
// WHAT IT DOES NOT OWN
// The library itself (which clips are checked), the Frame Selector's row of
// frames, and the Clip-Gap Builder's own current clip all belong to
// gap-builder.js and change as the user works. They arrive through
// configure() as FUNCTIONS, not values, so this file always reads what is
// true now rather than a copy taken at wiring time — PICKED and LIB_FRAMES
// are both REASSIGNED as the user works, so a captured reference would go
// stale the first time a box was ticked.
'use strict';

const FramePlayer = (function () {

  // ── the shared player, and the three buttons ───────────────────────────
  // One <video> for everything: a Sound Bits row's ▶, and all three Play
  // buttons. Only one thing is ever audible, which is the point — these are
  // three views of the same pipeline, not three independent players.
  const player = document.getElementById('soundBitPlayer');
  const video = document.getElementById('soundBitVideo');
  const nameEl = document.getElementById('soundBitName');
  const rateEl = document.getElementById('soundBitRate');

  //   libs      Audio Menu           every CHECKED clip, the originals
  //   selector  Frame Selector Menu  the Frame Selector's own collection
  //   builder   Gap Builder Menu     the Clip-Gap Builder's current clip
  const btnLibs = document.getElementById('gmSoundBitPlayPause');
  const btnSelector = document.getElementById('gmLibPlayPause');
  const btnBuilder = document.getElementById('gmBuilderPlayPause');

  // What gap-builder.js lends us. Deliberately all functions — see the
  // header note on why a captured value would go stale.
  let src = {
    picked: () => [],        // PICKED — the checked clips, in checked order
    frames: () => [],        // LIB_FRAMES — the Frame Selector's flat row
    viewIndices: () => [],   // which of those the row is showing right now
    builderClip: () => null, // the clip the Clip-Gap Builder is showing
    order: () => [],         // LIB_ORDER — every library path, as DISPLAYED
  };

  // Which file is loaded right now — not just "is it playing" but WHICH,
  // so a toggle can tell "mine is already playing, so pause" from
  // "something else is playing, so switch to mine."
  let currentPath = null;

  // ── runs ───────────────────────────────────────────────────────────────
  // A run is a set of clips played one after another. Each button owns its
  // own, over its own stage of the pipeline. A run's queue is a SNAPSHOT
  // taken when Play is pressed; if the collection behind it changes, the
  // run is ended outright rather than left to drift (see endRun(), and the
  // bug in its comment).
  let queue = [];
  let queueLen = 0;      // what it started with, for the "2/5" label
  let owner = null;      // 'libs' | 'selector' | null

  const active = () => queue.length > 0;

  function clearRun() { queue = []; queueLen = 0; owner = null; }

  // ── which clips each button plays ──────────────────────────────────────
  // Silent clips are left OUT of every run, not played and sat through.
  // Every .webm in this library carries an Opus stream, INCLUDING the idle
  // loops and gap-fillers, whose tracks are silent — so "has an audio
  // stream" was never the right question. has_audio is measured server-side
  // (see has_audible() in serve.py) and travels with each clip. Playing a
  // silent 10-second idle loop first is exactly what made a run look like
  // it had started on the wrong clip.
  const audiblePicked = () => src.picked().filter(c => c.has_audio);

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

  // Re-point a run that is ALREADY GOING at a changed set of clips, without
  // interrupting the one being heard. Ticking another box mid-run should
  // extend the stack, not stop the audio — but the clip playing right now
  // stays exactly where it is, and what follows is whatever comes after it
  // in the new stack. A clip that has just been UNticked is simply no
  // longer in that remainder.
  function resync(which, clips) {
    if (owner !== which || !active()) return false;
    const cur = queue[0];
    // Where the run is up to, read BEFORE the queue is rebuilt — the label
    // has to keep counting from here rather than restarting at 1/N.
    const pos = queueLen - queue.length + 1;
    const at = clips.findIndex(c => c.path === cur.path);
    const rest = at >= 0 ? clips.slice(at + 1) : clips.filter(c => c.path !== cur.path);
    queue = [cur, ...rest];
    queueLen = pos - 1 + queue.length;
    // The clip keeps playing untouched, but "1/2" is now wrong — the run it
    // belongs to just got longer or shorter. Rewrite the count only; the
    // <video> is deliberately not reloaded.
    nameEl.textContent = queueLen > 1 ? `${pos}/${queueLen} — ${cur.name}` : cur.name;
    return true;
  }

  // The distinct clips behind the Frame Selector's row, in the order they
  // first appear. DISTINCT matters: the row is FRAMES, and a 482-frame clip
  // is 482 entries pointing at one file — one per frame would replay the
  // same voice hundreds of times. Reads the CURRENT view, so "Show Selected
  // on Timeline" narrows the run to just the selection.
  function selectorClips() {
    const frames = src.frames(), seen = new Set(), out = [];
    for (const i of src.viewIndices()) {
      const c = frames[i]?.clip;
      if (c && c.has_audio && !seen.has(c.path)) { seen.add(c.path); out.push(c); }
    }
    return out;
  }

  // ── playing ────────────────────────────────────────────────────────────
  function playFile(f, label, fromRun) {
    // A single-clip play takes the shared player over, so a run already
    // going is cancelled rather than hijacking the next `ended` and
    // carrying on with its own next item.
    if (!fromRun) clearRun();
    player.hidden = false;
    nameEl.textContent = label;
    currentPath = f.path;
    video.src = `/api/lib_media?path=${encodeURIComponent(f.path)}`;
    video.playbackRate = +rateEl.value;
    video.play();
    player.scrollIntoView({block: 'nearest'});
    refresh();
  }

  function playHead() {
    const f = queue[0];
    if (!f) { clearRun(); syncLabels(); return; }
    const pos = queueLen - queue.length + 1;
    playFile(f, queueLen > 1 ? `${pos}/${queueLen} — ${f.name}` : f.name, true);
  }

  // Step to the next clip. Reached two ways and BOTH matter: one that ends
  // normally, and one that fails to load at all — so a run can never stall
  // on a file the browser refuses.
  function advance() {
    queue.shift();
    if (queue.length) playHead();
    else { clearRun(); syncLabels(); }
  }

  // Press the button whose run is going and it means pause/resume; press a
  // different one and it takes the player over with its own run. That is
  // the whole reason a run records its owner. Returns false when there was
  // nothing for this button to play.
  function toggleRun(which, clips) {
    if (owner === which && active()) {
      if (video.paused) video.play();
      else video.pause();
      return true;
    }
    if (!clips.length) return false;
    queue = [...clips];
    queueLen = queue.length;
    owner = which;
    playHead();
    return true;
  }

  // The two panel buttons that play ONE clip read as toggles: clicking one
  // while its own clip is what's playing pauses it; any other state
  // switches the player onto that clip.
  function playOrToggle(f, label) {
    if (!f) return;
    if (currentPath === f.path && !video.paused) video.pause();
    else playFile(f, label);
  }

  // ── the picture does NOT follow the voice ──────────────────────────────
  // Deliberately nothing here. An earlier version stepped the Frame
  // Selector's viewer through the playing clip's frames, and it was wrong:
  // the Frame Selector is a separate workspace holding a separate
  // collection, and having it scrub itself meant pressing Play in the
  // Audio Menu silently moved a panel nobody was pointing at — Carson
  // found it parked on frame 327 of 482 with only the Audio Menu running.
  //
  // The shared <video> below the library IS the picture now, so there is
  // nothing left for a frame stepper to add. Playing audio must move
  // NOTHING except that one player. Do not reconnect this.

  // ── the buttons' own state ─────────────────────────────────────────────
  // Cheap: just the Play/Pause wording. Called on every frame step, so it
  // stays free of the collection scans refresh() does.
  //
  // Only the button whose OWN run is going claims "Pause" — pressing any
  // other would take the player over, not stop it. The Audio Menu's button
  // is the exception: with nothing checked it is a plain transport for
  // whatever single clip a row's ▶ left loaded, so it says Pause then too.
  function syncLabels() {
    const playing = !video.paused;
    const libsOwns = owner === 'libs' || (owner === null && !src.picked().length);
    btnLibs.textContent = (playing && libsOwns) ? 'Pause' : 'Play';
    btnSelector.textContent = (playing && owner === 'selector')
      ? "Pause Frame Selector's Audio" : "Play Frame Selector's Audio";
    btnBuilder.textContent = (playing && currentPath === src.builderClip()?.path)
      ? "Pause This Clip's Audio" : "Play This Clip's Audio";
  }

  // Full: what each button can do, and whether it says so in GREEN.
  // Green means "this button's own stage has something that can actually be
  // HEARD" — not merely "has something". A collection of stills, idle loops
  // or gap-fillers has frames but no voice, so it stays white.
  function refresh() {
    const heard = audiblePicked().length;
    const picked = src.picked().length;
    btnLibs.disabled = !heard && !currentPath;
    btnLibs.classList.toggle('ready', heard > 0);
    btnLibs.title = heard
      ? `Plays every checked clip that has a voice in it — ${heard} of them, `
        + `in the order checked, one after another. Click again to pause the run.`
      : picked
        ? `${picked} checked, but none of them carry any audio — nothing to play.`
        : 'Check one or more clips in sarah_clips/libs above first.';

    const sel = selectorClips().length;
    const rowHas = src.viewIndices().length;
    btnSelector.disabled = !sel;
    btnSelector.classList.toggle('ready', sel > 0);
    btnSelector.title = sel
      ? `Plays the Frame Selector's own collection — the ${sel} clip`
        + `${sel === 1 ? '' : 's'} in it with a voice, in row order, one after `
        + `another. With "Show Selected on Timeline" on, that is just the `
        + `selection. Click again to pause the run.`
      : rowHas
        ? 'The frames in the Frame Selector carry no audio — nothing to play.'
        : 'Check a clip in sarah_clips/libs above to fill the Frame Selector first.';

    const bc = src.builderClip();
    btnBuilder.disabled = !bc;

    syncLabels();
  }

  // ── wiring ─────────────────────────────────────────────────────────────
  rateEl.onchange = () => { video.playbackRate = +rateEl.value; };
  video.onplay = () => { syncLabels(); };
  video.onpause = () => { syncLabels(); };
  video.onended = () => { if (active()) advance(); else syncLabels(); };
  // A file the browser cannot play must not end the run early.
  video.onerror = () => { if (active()) advance(); };

  return {
    // Hand over what gap-builder.js owns. Call once, after those exist.
    // The BUTTONS are not wired here — gap-builder.js owns the clicks and
    // routes each to its own scenario at the bottom of this file, so a
    // trace reads button → gap-builder → scenario → this engine.
    configure(sources) {
      Object.assign(src, sources);
      refresh();
    },

    refresh,      // recompute what each button can do, and its colour
    syncLabels,   // cheap: just the Play/Pause wording

    // ── what the three scenarios below call in on ────────────────────────
    run: toggleRun,       // play a LIST of clips as one owned run
    playOne: playOrToggle,// play/pause ONE clip
    resync,               // re-point a RUNNING run at a changed set of clips
    // Each scenario's own idea of "what would I play" — also what refresh()
    // reads to decide green vs white.
    audiblePicked,
    checkedInOrder,
    selectorClips,
    builderClip: () => src.builderClip(),
    // Plain transport for whatever single clip is loaded, with no run.
    toggleLoaded() { if (video.paused) video.play(); else video.pause(); },

    // What the player is doing right now — for tracing a run from the
    // console alongside the scenarios' own log lines.
    _state: () => ({queue: queue.map(c => c.name), owner,
                    paused: video.paused, srcFrames: src.frames().length}),

    // A Sound Bits row's own ▶ — play this one file, cancelling any run.
    playClip(f, label) { playFile(f, label, false); },

    // The collection behind a run changed, so the run over it is dead.
    // This was a real bug: play, pause, change what is checked, press play
    // again — and it RESUMED the stale run, the old clip's voice against
    // the new collection's pictures. Which is exactly what "it played the
    // wrong clip" looked like.
    //
    // `which` limits it to ONE run's owner. The Frame Selector's run is
    // ended on any change, because its frame row is rebuilt underneath it
    // and every index it held is meaningless. The Audio Menu's run is NOT
    // — ticking another box there extends its stack instead (see resync()
    // and OriginalAudio.rebuild()), so the voice keeps playing.
    endRun(which) {
      if (which && owner !== which) return;
      clearRun();
      video.pause();
    },

    // Clear: back to nothing loaded at all.
    reset() {
      clearRun();
      video.pause();
      video.removeAttribute('src');
      currentPath = null;
      player.hidden = true;
      nameEl.textContent = 'No Sound Bit loaded';
      btnLibs.disabled = true;
      btnLibs.classList.remove('ready');
      syncLabels();
    },
  };
})();

// ═════════════════════════════════════════════════════════════════════════
// THE THREE SCENARIOS
// ═════════════════════════════════════════════════════════════════════════
// FramePlayer above is the pure engine — it knows how to run a queue, keep
// the picture with the voice, and render the buttons' state. It does NOT
// know which clips any one button plays. That is what these three are:
// one per button, each holding only its own specifics and handing them to
// the engine.
//
// A click traces straight through, and each step says so:
//
//   the button  →  gap-builder.js's onclick  →  <Scenario>.play()
//                                            →  FramePlayer's engine
//
// Each logs "Inside: <name>" on the way through, so the console shows
// which scenario a click actually reached.

// ── 1. the Audio Menu's "Play" ───────────────────────────────────────────
// THE ORIGINALS: every clip checked in sarah_clips/libs that can actually
// be heard, in the order it was checked.
const OriginalAudio = (function () {
  // THE STACK. Not worked out at the moment Play is pressed — it is kept
  // up to date by every checkbox event, so it is always in step with what
  // is actually ticked (Carson's own rule). Play/Pause then just walks it.
  //
  // Ordered TOP TO BOTTOM as the library shows it, not by when each box was
  // ticked: tick catalogue-search and then intro-and-login, and it still
  // plays intro-and-login first, because that is what you see.
  let STACK = [];

  // Called on every tick/untick — see toggleLibClip() in gap-builder.js.
  function rebuild() {
    STACK = FramePlayer.checkedInOrder().filter(c => c.has_audio);
    console.log('Inside: OriginalAudio.rebuild', {stack: STACK.map(c => c.name)});
    // If this stack's own run is playing right now, keep it playing and
    // just re-point what comes NEXT — ticking another box mid-run should
    // add to the run, not stop the voice.
    FramePlayer.resync('libs', STACK);
    return STACK;
  }

  function play() {
    console.log('Inside: OriginalAudio', {stack: STACK.map(c => c.name)});
    // Nothing ticked that can be heard — fall back to plain play/pause
    // for whatever single clip a row's ▶ or another button left loaded.
    if (!FramePlayer.run('libs', STACK)) FramePlayer.toggleLoaded();
  }

  return {play, rebuild, stack: () => STACK, clips: () => STACK};
})();

// ── 2. the Frame Selector Menu's "Play Frame Selector's Audio" ───────────
// THE FRAME SELECTOR'S OWN COLLECTION: the distinct clips behind the row
// as it stands — narrowed to just the selection while "Show Selected on
// Timeline" is on.
const FrameSelector = (function () {
  function clips() { return FramePlayer.selectorClips(); }

  function play() {
    console.log('Inside: FrameSelector', {clips: clips().map(c => c.name)});
    FramePlayer.run('selector', clips());
  }

  return {play, clips};
})();

// ── 3. the Gap Builder Controller Menu's "Play This Clip's Audio" ────────
// THE CLIP-GAP BUILDER'S OWN: whichever clip that panel is showing right
// now. Still one clip rather than a run — this is the button that has not
// been reworked yet.
const GapBuilder = (function () {
  function clip() { return FramePlayer.builderClip(); }

  function play() {
    console.log('Inside: GapBuilder', {clip: clip()?.name ?? null});
    FramePlayer.playOne(clip(), clip()?.name);
  }

  return {play, clip};
})();
