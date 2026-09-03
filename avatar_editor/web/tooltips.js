// Avatar Editor — the 3-second tooltip.
//
// Every button on this page already carries a `title` explaining what it
// does. The browser's own tooltip for those is a poor way to read them:
// it appears after about a second, so it fires constantly while you are
// just moving the mouse across a stack of buttons, it is a bare unstyled
// box in the corner of the cursor, and on a long sentence it wraps
// wherever it likes.
//
// So: hold still on a control for THREE SECONDS and one styled tooltip
// appears, matching the rest of the page. Carson's own number — long
// enough that passing over a button never triggers it, short enough that
// stopping on one because you are unsure gets you an answer.
//
// TITLE STAYS THE SOURCE
// The text is read from the element's own `title` at hover time, not
// copied somewhere at load. That matters because several of these are
// REWRITTEN as the page works — every Play button's title says how many
// clips it would play, and Save to:'s says how many frames it would save.
// A copy taken at load would be a lie by the second click.
//
// The native tooltip is suppressed by removing `title` on the way in and
// putting it back on the way out, so both never show at once and nothing
// that writes to `.title` later has to know this file exists.
//
// DELEGATED, so it covers controls that do not exist yet
// The library's rows, Timeline Scenes' rows and Working Clips' rows are
// all built at runtime, and more will be. One listener on the document
// covers every one of them, now and later, with nothing to remember to
// wire up.
//
// CHECKBOXES ARE DELIBERATELY LEFT OUT — Carson's own call. A tick box
// says what it does by being ticked.
'use strict';

const Tooltips = (function () {

  const DELAY = 3000;   // ms of holding still, Carson's own number
  const GAP = 10;       // px between the cursor and the box

  let el = null;        // the tooltip itself, made on first use
  let timer = null;
  let holding = null;   // the element whose title we are holding
  let heldTitle = null;

  // What counts as "a control". Checkboxes are excluded here and nowhere
  // else, so there is one place to look when asking why one has no tip.
  function target(node) {
    const c = node.closest && node.closest('button, select, .gapMenuBtn, .pill, .ibtn');
    if (!c) return null;
    if (c.matches('input[type=checkbox]')) return null;
    return c;
  }

  // The text to show. A control can point at another element's title
  // instead of carrying its own — the Save to: dropdown does, because the
  // row around it is the button and owns the description.
  function tipFor(c) {
    const from = c.getAttribute('data-tip-from');
    const src = from ? (document.getElementById(from) || c) : c;
    return (src.getAttribute('title') || src.dataset.heldTitle || '').trim();
  }

  function box() {
    if (el) return el;
    el = document.createElement('div');
    el.className = 'tip3';
    el.hidden = true;
    document.body.appendChild(el);
    return el;
  }

  function show(text, x, y) {
    const b = box();
    b.textContent = text;
    b.hidden = false;
    // Kept inside the window on both axes: these are long sentences, and
    // the buttons that carry the longest ones sit against the right edge.
    const r = b.getBoundingClientRect();
    let left = x + GAP;
    let top = y + GAP;
    if (left + r.width > window.innerWidth - 8) left = Math.max(8, x - GAP - r.width);
    if (top + r.height > window.innerHeight - 8) top = Math.max(8, y - GAP - r.height);
    b.style.left = `${left}px`;
    b.style.top = `${top}px`;
  }

  function hide() {
    clearTimeout(timer);
    timer = null;
    if (holding && heldTitle !== null) {
      // Only put it back if nothing else has written a title meanwhile —
      // a refresh mid-hover would otherwise be undone by this.
      if (!holding.getAttribute('title')) holding.setAttribute('title', heldTitle);
      delete holding.dataset.heldTitle;
    }
    holding = null;
    heldTitle = null;
    if (el) el.hidden = true;
  }

  document.addEventListener('mouseover', e => {
    const c = target(e.target);
    if (!c || c === holding) return;
    hide();
    const text = tipFor(c);
    if (!text) return;
    holding = c;
    // Take the native tooltip out of the way for as long as the pointer is
    // here. Stashed on the element too, so tipFor() can still read it.
    heldTitle = c.getAttribute('title');
    if (heldTitle !== null) {
      c.dataset.heldTitle = heldTitle;
      c.removeAttribute('title');
    }
    const x = e.clientX, y = e.clientY;
    timer = setTimeout(() => show(tipFor(c), x, y), DELAY);
  }, true);

  document.addEventListener('mouseout', e => {
    if (holding && !holding.contains(e.relatedTarget)) hide();
  }, true);

  // Any of these means the pointer is no longer just resting on a control.
  for (const ev of ['mousedown', 'wheel', 'keydown']) {
    document.addEventListener(ev, hide, true);
  }
  window.addEventListener('blur', hide);

  return {
    // For the tests, and for trying a different delay from the console
    // without editing the file.
    delay: () => DELAY,
    visible: () => !!el && !el.hidden,
    text: () => (el ? el.textContent : ''),
    _showNow(c) { const t = tipFor(c); if (t) show(t, 0, 0); },
    _hide: hide,
  };
})();
