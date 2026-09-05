package editor

// The folder-tree browser, rooted at Customers/ — the page that finds a
// recording so it can be opened without already knowing its path.
//
// Lifted verbatim from the Python server, where it was an f-string and every
// brace had to be doubled. Here it is a raw string literal: a brace is a brace.
const browseHTML = `<!doctype html>
<html><head><meta charset="utf-8"><title>Browse Customers — video editor</title>
<style>
  :root { color-scheme: dark; }
  body { margin:0; background:#1a1a1a; color:#eee; font-family:-apple-system,sans-serif;
         display:flex; flex-direction:column; align-items:center; padding:16px 0; }
  #panel { width:750px; }
  h1 { font-size:15px; font-weight:600; margin:0 0 10px; color:#ccc; }
  #crumb { font-size:12px; color:#888; margin-bottom:10px; word-break:break-all; }
  #status { font-size:13px; color:#e0c060; min-height:18px; margin-bottom:8px; }
  #list { border:1px solid #333; border-radius:8px; overflow:hidden; }
  .row { padding:9px 14px; cursor:pointer; border-bottom:1px solid #2a2a2a;
         display:flex; justify-content:space-between; font-size:13px; }
  .row:last-child { border-bottom:none; }
  .row:hover { background:#2a2a2a; }
  .row.file { color:#9fd0ff; }
  .row .size { color:#777; font-variant-numeric:tabular-nums; }
  .badges { display:flex; gap:8px; }
  .chip { color:#9aa; padding:2px 8px; border:1px solid #444; border-radius:10px;
          font-size:11px; white-space:nowrap; }
  .chip:hover { color:#fff; border-color:#6a6; background:#1f3320; }
  .empty { padding:14px; color:#666; font-size:13px; }
  .slotbtn { margin-left:8px; background:#2c3236; color:#eee; border:1px solid #4a5259;
              border-radius:5px; padding:2px 8px; font-size:13px; cursor:pointer; }
  .slotbtn.base:hover { border-color:#2ecc40; color:#2ecc40; }
  .slotbtn.overlay:hover { border-color:#a56cff; color:#a56cff; }
</style></head>
<body>
  <div id="panel">
    <h1>Browse Customers/ for a raw recording</h1>
    <div id="crumb">Customers/</div>
    <div id="pairbar" style="display:none;gap:10px;align-items:center;flex-wrap:wrap;
       margin:8px 0;padding:8px 10px;border:1px solid #3a4248;border-radius:8px;background:#1b1f22">
    <span style="color:#2ecc40;font-weight:600">▩ background</span>
    <span id="pbBase" style="color:#ccc">—</span>
    <span style="color:#a56cff;font-weight:600">◈ overlay</span>
    <span id="pbOver" style="color:#ccc">—</span>
    <button id="pbGo" onclick="openPair()" disabled
      style="background:#2c3236;color:#eee;border:1px solid #4a5259;border-radius:6px;
             padding:6px 12px;cursor:pointer">Layer these ▶</button>
    <button onclick="PAIR.base=PAIR.overlay=null;paintPair()"
      style="background:none;color:#889;border:0;cursor:pointer">clear</button>
  </div>
  <div id="status"></div>
    <div id="list"></div>
  </div>
<script>
  function fmtSize(b) {
    if (b > 1e6) return (b / 1e6).toFixed(1) + ' MB';
    if (b > 1e3) return (b / 1e3).toFixed(0) + ' KB';
    return b + ' B';
  }
  function row(icon, label, sizeText, onclick, isFile) {
    const d = document.createElement('div');
    d.className = 'row' + (isFile ? ' file' : '');
    const l = document.createElement('span'); l.textContent = ` + "`" + `${icon}  ${label}` + "`" + `;
    d.appendChild(l);
    if (sizeText) { const s = document.createElement('span'); s.className = 'size'; s.textContent = sizeText; d.appendChild(s); }
    d.onclick = onclick;
    return d;
  }
  // A store row: clicking the name still jumps to raw_mp4 (unchanged default),
  // and a "segments" chip sits right beside it when that folder exists too —
  // added so the cut segments this tool itself produces are as reachable as
  // the raw recording they came from, not three folders deeper.
  function storeRow(d) {
    const div = document.createElement('div');
    div.className = 'row';
    const label = document.createElement('span');
    label.textContent = ` + "`" + `🎬  ${d.name}` + "`" + `;
    div.appendChild(label);
    const badges = document.createElement('span');
    badges.className = 'badges';
    const chip = (text, target) => {
      const c = document.createElement('span');
      c.className = 'chip';
      c.textContent = text;
      c.onclick = (e) => { e.stopPropagation(); list(target); };
      return c;
    };
    badges.appendChild(chip('raw_mp4 →', d.jump));
    if (d.segments_jump) badges.appendChild(chip('segments →', d.segments_jump));
    div.appendChild(badges);
    div.onclick = () => list(d.jump);
    return div;
  }
  async function list(path) {
    setStatus('');
    const r = await fetch(` + "`" + `/api/list?path=${encodeURIComponent(path)}` + "`" + `);
    const data = await r.json();
    if (data.error) { setStatus('Error: ' + data.error); return; }
    document.getElementById('crumb').textContent = 'Customers/' + data.path;
    const el = document.getElementById('list');
    el.innerHTML = '';
    if (data.parent !== null) el.appendChild(row('⬆️', '.. (up)', '', () => list(data.parent)));
    for (const d of data.dirs) {
      el.appendChild(d.jump ? storeRow(d) : row('📁', d.name, '', () => list(d.path)));
    }
    for (const f of data.files) {
      const r = row('🎬', f.name, fmtSize(f.size), () => openFile(f.path), true);
      // Layering needs two files, usually from different folders, so the picks
      // have to survive navigating away — hence slots rather than a selection.
      for (const [slot, glyph, tip] of [['base','▩','use as BACKGROUND (mp4)'],
                                        ['overlay','◈','use as OVERLAY (webm)']]) {
        const b = document.createElement('button');
        b.className = 'slotbtn ' + slot;
        b.textContent = glyph; b.title = tip;
        b.onclick = ev => { ev.stopPropagation(); PAIR[slot] = f.path; paintPair(); };
        r.appendChild(b);
      }
      el.appendChild(r);
    }
    if (data.parent === null && data.dirs.length === 0 && data.files.length === 0)
      el.appendChild(Object.assign(document.createElement('div'), { className: 'empty', textContent: 'Customers/ is empty.' }));
  }
  const PAIR = { base: null, overlay: null };
  function paintPair() {
    const bar = document.getElementById('pairbar');
    const nm = p => p ? p.split('/').pop() : '—';
    document.getElementById('pbBase').textContent = nm(PAIR.base);
    document.getElementById('pbOver').textContent = nm(PAIR.overlay);
    document.getElementById('pbGo').disabled = !(PAIR.base && PAIR.overlay);
    bar.style.display = (PAIR.base || PAIR.overlay) ? 'flex' : 'none';
  }
  async function openPair() {
    setStatus('Extracting BOTH clips — the overlay keeps its alpha, so this takes a moment…');
    try {
      const r = await fetch(` + "`" + `/api/open-pair?base=${encodeURIComponent(PAIR.base)}` + "`" + `
                            + ` + "`" + `&overlay=${encodeURIComponent(PAIR.overlay)}` + "`" + `);
      const d = await r.json();
      if (d.error) { setStatus('Error: ' + d.error); return; }
      location.href = d.url;
    } catch (e) { setStatus('Error: ' + e); }
  }
  function setStatus(msg) { document.getElementById('status').textContent = msg; }
  async function openFile(path) {
    setStatus(` + "`" + `Extracting frames from ${path} — this can take a moment for a long recording…` + "`" + `);
    try {
      const r = await fetch(` + "`" + `/api/open?path=${encodeURIComponent(path)}` + "`" + `);
      const data = await r.json();
      if (data.error) { setStatus('Error: ' + data.error); return; }
      location.href = data.url;
    } catch (e) { setStatus('Error: ' + e); }
  }
  paintPair();
  list('');
</script>
</body></html>
`
