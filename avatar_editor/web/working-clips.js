// Avatar Editor — Working Clips.
//
// The panel to the right of Timeline Scenes: Carson's OWN clips, as
// opposed to sarah_clips/libs on the far left, which holds what HeyGen and
// the transition tools produced. A collection assembled in the Clip-Gap
// Builder is saved here under a name, and can then be dropped back into
// the Frame Selector over a selection ("Replace Selected").
//
// Three sections and no more, because three kinds of thing get built here:
//
//   IDLE          a still or a loop — Sarah waiting, not speaking
//   TRANSITIONS   the frames that carry one pose into another
//   SOUND_BITS    a spoken line
//
// WHY ITS OWN FILE
// The same reason frame-player.js is: gap-builder.js is already the
// library, two frame rows and a menu, and this is a fourth subject. It
// keeps its own scope and hands out one object, so nothing here can be
// reached by accident from the two files that share a flat scope.
//
// WHAT IT BORROWS, and when
// BUILDER.frames, libFrameUrl() and pad() come from gap-builder.js;
// loadStore/saveStore and the two modal dialogs come from app.js, which
// loads AFTER this file. Nothing here runs at load time except wiring, so
// by the time any of it is called, all of it exists.
'use strict';

const WorkingClips = (function () {

  // The three sections, in the order they are shown. `key` is what goes in
  // storage and in the Gap Builder Menu's dropdown; `label` is what the
  // panel shows.
  const SECTIONS = [
    {key: 'idle', label: 'IDLE'},
    {key: 'transitions', label: 'TRANSITIONS'},
    {key: 'sound_bits', label: 'SOUND_BITS'},
  ];

  const wcStatus = document.getElementById('wcStatus');
  const wcGroups = document.getElementById('wcGroups');

  // {idle: [entry], transitions: [entry], sound_bits: [entry]}
  // entry = {id, name, n, clips: [clip], frames: [{c, local}]}
  //
  // Frames are stored COMPACTLY — an index into the entry's own short list
  // of clips, plus the frame's index within that clip. Written out in full
  // ({url, clip, local} per frame, the shape the rest of the editor uses)
  // a single 482-frame clip is about 100KB of JSON, and localStorage gives
  // the whole page roughly 5MB. Deduplicating the clip makes the same
  // entry a few KB. The full shape is rebuilt on the way out, in frames().
  let DATA = {idle: [], transitions: [], sound_bits: []};

  // Which entry is ACTIVE — at most one across all three sections, because
  // "Replace Selected" needs one answer, not a list. Ticking a second box
  // unticks the first. Not saved: it is a pointer for the next action, not
  // part of the collection.
  let ACTIVE = null;   // {section, id} | null

  const list = key => DATA[key] || [];
  const find = ref => ref && (DATA[ref.section] || []).find(e => e.id === ref.id);

  // ── the saved shape, in and out ─────────────────────────────────────────
  function pack(frames, name) {
    const clips = [];
    const at = new Map();
    const packed = [];
    for (const f of frames) {
      let ci = at.get(f.clip.path);
      if (ci === undefined) { ci = clips.length; at.set(f.clip.path, ci); clips.push(f.clip); }
      packed.push({c: ci, local: f.local});
    }
    return {id: `wc_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
            name, n: frames.length, clips, frames: packed};
  }

  // Back to the {url, clip, local} shape LIB.frames and BUILDER.frames use,
  // with the URL rebuilt rather than stored — a stored URL would be a
  // second copy of something already derivable, and would go stale if the
  // frame cache were ever re-slugged.
  function frames(entry) {
    if (!entry) return [];
    return entry.frames.map(p => {
      const clip = entry.clips[p.c];
      return {url: libFrameUrl(clip, p.local), clip, local: p.local};
    });
  }

  function persist() { saveStore({workingClips: DATA}); }

  // ── the panel ───────────────────────────────────────────────────────────
  function render() {
    wcGroups.innerHTML = '';
    let total = 0;
    for (const sec of SECTIONS) {
      const items = list(sec.key);
      total += items.length;
      const box = document.createElement('div');
      box.className = 'libgroup';
      const head = document.createElement('h4');
      head.textContent = `${sec.label} (${items.length})`;
      box.appendChild(head);
      if (!items.length) {
        const e = document.createElement('div');
        e.className = 'libempty';
        e.textContent = 'empty';
        box.appendChild(e);
      }
      for (const entry of items) {
        const row = document.createElement('div');
        row.className = 'libfile';
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.checked = !!ACTIVE && ACTIVE.section === sec.key && ACTIVE.id === entry.id;
        cb.title = `Make ${entry.name} the active clip — Replace Selected uses it.`;
        cb.onchange = () => setActive(cb.checked ? {section: sec.key, id: entry.id} : null);
        const name = document.createElement('span');
        name.className = 'name';
        name.textContent = entry.name;
        name.title = `${entry.name} — ${entry.n} frame(s) from `
          + `${entry.clips.length} source clip(s)`;
        // The frame count sits where sarah_clips/libs puts a file's size or
        // duration, so the two panels' rows line up.
        const meta = document.createElement('span');
        meta.className = 'meta';
        meta.textContent = `${entry.n}f`;
        const del = document.createElement('button');
        del.type = 'button';
        del.className = 'soundBitPlay wcDelete';
        del.textContent = '×';
        del.title = `Delete ${entry.name} from Working Clips. Cannot be undone.`;
        del.onclick = () => remove(sec.key, entry.id);
        row.appendChild(cb); row.appendChild(name);
        row.appendChild(meta); row.appendChild(del);
        box.appendChild(row);
      }
      wcGroups.appendChild(box);
    }
    wcStatus.textContent = total
      ? `${total} saved clip(s) — tick one to make it active.`
      : 'Nothing saved yet.';
    refreshButtons();
  }

  function setActive(ref) {
    ACTIVE = ref;
    render();
  }

  function remove(section, id) {
    DATA[section] = list(section).filter(e => e.id !== id);
    if (ACTIVE && ACTIVE.section === section && ACTIVE.id === id) ACTIVE = null;
    persist();
    render();
  }

  // ── saving out of the Clip-Gap Builder ──────────────────────────────────
  // Every frame, in the order the Builder has them — this is a snapshot of
  // that collection, so a later edit there cannot reach back and change
  // what was saved.
  async function saveBuilder(section, askName) {
    if (!BUILDER.frames.length) return {ok: false, why: 'The Clip-Gap Builder is empty.'};
    const name = await askName();
    if (!name) return {ok: false, why: 'cancelled'};
    const entry = pack(BUILDER.frames.slice(), name);
    DATA[section] = list(section).concat([entry]);
    persist();
    render();
    return {ok: true, entry, section};
  }

  // ── the two buttons that depend on this panel's state ───────────────────
  function refreshButtons() {
    // "Save to:" is a BUTTON that happens to be a dropdown — picking a
    // section is the save. It is a <div>, so there is no disabled state to
    // set on it; the <select> inside carries that, and the row carries the
    // green and the tooltip the way every other button here does.
    const save = document.getElementById('gmSaveToWorking');
    const target = document.getElementById('gmSaveTarget');
    if (save && target) {
      const n = typeof BUILDER.frames === 'undefined' ? 0 : BUILDER.frames.length;
      target.disabled = !n;
      save.classList.toggle('ready', n > 0);
      save.classList.toggle('isDisabled', !n);
      save.title = n
        ? `Pick a section to save all ${n} frame(s) in the Clip-Gap Builder, in `
          + `order, into Working Clips under a name you type next.`
        : 'Build the collection above first.';
    }
    const rep = document.getElementById('gmReplaceSelected');
    if (rep) {
      const entry = find(ACTIVE);
      const sel = typeof LIB.selected === 'undefined' ? 0 : LIB.selected.size;
      rep.disabled = !entry || !sel;
      rep.classList.toggle('ready', !!entry && sel > 0);
      rep.title = !entry
        ? 'Tick a clip in Working Clips to make it active first.'
        : !sel
          ? `"${entry.name}" is active — now Select Frames above and pick the `
            + `range it should replace.`
          : `Replaces the ${sel} selected frame(s) above with "${entry.name}" `
            + `(${entry.n} frame(s)). You are warned first if the counts differ.`;
    }
  }

  return {
    render, refreshButtons, saveBuilder,
    sections: () => SECTIONS.slice(),
    active: () => find(ACTIVE),
    activeFrames: () => frames(find(ACTIVE)),
    count: key => list(key).length,
    // Comes back with everything else that is not tied to one scene — see
    // restoreGlobals() in app.js.
    restore() {
      const s = loadStore();
      if (s.workingClips) {
        for (const sec of SECTIONS)
          if (Array.isArray(s.workingClips[sec.key])) DATA[sec.key] = s.workingClips[sec.key];
      }
      render();
    },
    // For the tests and for tracing from the console.
    _data: () => DATA,
  };
})();
