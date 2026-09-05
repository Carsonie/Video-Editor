#!/usr/bin/env python3
"""
Write a video folder's VTT as a browser table — video/vtt.html.

    python3 build/vtt_html.py "<video folder>"                 # newest script_v<N>.json
    python3 build/vtt_html.py "<video folder>" --version 33     # a specific build
    python3 build/vtt_html.py "<video folder>" --open           # ...and open a Chrome tab

THIS IS WHAT "SHOW ME THE VTT" MEANS. Carson's voice command, 2026-09-04 —
the browser table, not the markdown one and not the plain CLI output. See
.claude/skills/vtt/SKILL.md.

It exists as a script and not as steps in the skill because it was written
by hand once and would otherwise be re-derived, differently, every time.

WHERE THE NUMBERS COME FROM, and none of them are typed:
  clip length + every frame count   ffprobe, on sandbox/<NN-label>/
  the lines                         video/script_v<N>.json — the snapshot of
                                    the script that produced that build
  speech length                     words / words_per_second, the voice's own
                                    measured rate out of the script file

The <title> becomes the Chrome tab label, so it names the store and the
build: "ski-demo VTT v33". Several of these get opened at once and a tab
saying "vtt" is no use.
"""
import argparse
import glob
import html
import json
import os
import re
import subprocess
import sys


def frames(path, alpha=False):
    """DECODED frame count. An alpha WebM must have its decoder forced or
    ffprobe reports yuv420p and hands back the wrong stream."""
    if not os.path.isfile(path):
        return None
    dec = ["-c:v", "libvpx-vp9"] if alpha else []
    r = subprocess.run(["ffprobe", "-v", "error"] + dec +
                       ["-count_frames", "-select_streams", "v:0",
                        "-show_entries", "stream=nb_read_frames",
                        "-of", "csv=p=0", path], capture_output=True, text=True)
    try:
        return int(r.stdout.strip())
    except ValueError:
        return None


def pick_script(F, version):
    """script_v<N>.json is a RECORD of a build, so the VTT for v33 reads v33's."""
    if version:
        p = os.path.join(F, "video", f"script_v{version}.json")
        if not os.path.isfile(p):
            sys.exit(f"  no script_v{version}.json in {os.path.join(F, 'video')}")
        return p, str(version)
    found = glob.glob(os.path.join(F, "video", "script_v*.json"))
    if not found:
        p = os.path.join(F, "sandbox", "script.json")
        if not os.path.isfile(p):
            sys.exit("  no script_v<N>.json and no sandbox/script.json")
        return p, "sandbox"
    p = max(found, key=lambda x: int(re.search(r"_v(\d+)\.json$", x).group(1)))
    return p, re.search(r"_v(\d+)\.json$", p).group(1)


def collect(F, script_path):
    doc = json.load(open(script_path))
    wps = float(doc.get("words_per_second", 3.44))
    sb = os.path.join(F, "sandbox")
    rows = []
    for sc in doc["scenes"]:
        n, label, line = int(sc["n"]), sc["label"], sc["line"]
        d = os.path.join(sb, f"{n:02d}-{label}")
        seg = frames(os.path.join(d, "segment.mp4"))
        av = frames(os.path.join(d, "avatar.webm"), alpha=True)
        nar = frames(os.path.join(d, "narration.webm"), alpha=True)
        words = len(re.findall(r"[\w'’-]+", line))
        clip = seg / 25 if seg else 0.0
        speech = words / wps
        rows.append(dict(n=n, label=label, line=line, seg=seg, av=av, nar=nar,
                         words=words, clip=clip, speech=speech, gap=clip - speech,
                         missing=seg is None))
    return doc, wps, rows


def render(doc, wps, rows, ver, script_path):
    e = html.escape
    T = dict(clip=sum(r["clip"] for r in rows), sp=sum(r["speech"] for r in rows),
             w=sum(r["words"] for r in rows), seg=sum(r["seg"] or 0 for r in rows),
             av=sum(r["av"] or 0 for r in rows))
    T["gap"] = T["clip"] - T["sp"]
    over = [r for r in rows if r["gap"] > 2.5]
    short = [r for r in rows if r["nar"] and r["av"] and r["av"] < r["nar"]]
    store = doc.get("store", "?")
    title = doc.get("title", "")
    vlabel = f"v{ver}" if ver != "sandbox" else "sandbox"

    body = []
    for r in rows:
        gw = ' class="warn"' if r["gap"] > 2.5 else ""
        nw = ' class="warn"' if (r["nar"] and r["av"] and r["av"] < r["nar"]) else ""
        dlt = f' <span class="d">−{r["nar"] - r["av"]}</span>' if nw else ""
        body.append(
            f'    <tr class="scene"><td class="n">{r["n"]}</td>'
            f'<td class="lab">{e(r["label"])}</td>'
            f'<td class="num">{r["clip"]:.1f}s</td>'
            f'<td class="num">{r["speech"]:.1f}s</td>'
            f'<td class="num"{gw}>{r["gap"]:.1f}s</td>'
            f'<td class="num">{r["seg"] if r["seg"] else "–"}</td>'
            f'<td class="num">{r["av"] if r["av"] else "–"}</td>'
            f'<td class="num"{nw}>{r["nar"] if r["nar"] else "–"}{dlt}</td>'
            f'<td class="num w">{r["words"]}</td></tr>\n'
            f'    <tr class="say"><td></td><td colspan="8">&ldquo;{e(r["line"])}&rdquo;</td></tr>')

    note = ""
    if short:
        items = "".join(
            f'<li><b>{r["n"]} {e(r["label"])}</b> — avatar {r["av"]} frames, '
            f'narration {r["nar"]} (<b>{r["nar"] - r["av"]}</b> shorter)</li>' for r in short)
        note = f'''
<div class="notes">
  <h2>⚠ {len(short)} avatar(s) shorter than the narration they were cut from</h2>
  <p>Where a scene reads <b>segment = avatar</b> exactly, that is not automatically
  good. It can mean the avatar was built to the footage&rsquo;s length — or that it was
  trimmed to fit, cutting the end off Sarah&rsquo;s recorded line. The check is the avatar
  against its own <code>narration.webm</code>, never against the segment:</p>
  <ul>{items}</ul>
  <p>A shorter avatar does not always mean lost words — the narration carries lead-in
  and tail silence too. It means the scene is worth listening to.</p>
</div>'''

    return f"""<title>{e(store)} VTT {vlabel}</title>
<style>
  :root {{ --bg:#f7f7f5; --panel:#fff; --ink:#1c1f22; --dim:#6a7278; --line:#e2e5e7;
           --accent:#7b4fb5; --warn:#a8631a; --warnbg:#fdf3e4; --say:#4a5257; --zebra:#fafafa; }}
  @media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
    --bg:#17191b; --panel:#1e2124; --ink:#e6eaec; --dim:#8b949c; --line:#2f353a;
    --accent:#c3a9e0; --warn:#e0c060; --warnbg:#2c2617; --say:#9aa4ae; --zebra:#212528; }} }}
  :root[data-theme="dark"] {{
    --bg:#17191b; --panel:#1e2124; --ink:#e6eaec; --dim:#8b949c; --line:#2f353a;
    --accent:#c3a9e0; --warn:#e0c060; --warnbg:#2c2617; --say:#9aa4ae; --zebra:#212528; }}
  body {{ background:var(--bg); color:var(--ink); margin:0; padding:28px 22px 60px;
    font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif; }}
  .wrap {{ max-width:1180px; margin:0 auto; }}
  h1 {{ font-size:20px; margin:0 0 4px; letter-spacing:-.01em; }}
  h1 .v {{ color:var(--accent); font-weight:700; }}
  .sub {{ color:var(--dim); font-size:12.5px; margin:0 0 18px; }}
  .strip {{ display:flex; flex-wrap:wrap; gap:10px; margin:0 0 20px; }}
  .stat {{ background:var(--panel); border:1px solid var(--line); border-radius:8px;
           padding:9px 14px; min-width:104px; }}
  .stat .k {{ font-size:10px; letter-spacing:.13em; color:var(--dim); text-transform:uppercase; }}
  .stat .v {{ font-size:19px; font-weight:650; margin-top:2px; font-variant-numeric:tabular-nums; }}
  .scroll {{ overflow-x:auto; background:var(--panel); border:1px solid var(--line);
             border-radius:10px; }}
  table {{ border-collapse:collapse; width:100%; min-width:840px; }}
  th {{ text-align:right; font-size:10px; letter-spacing:.11em; text-transform:uppercase;
        color:var(--dim); font-weight:700; padding:11px 12px;
        border-bottom:1px solid var(--line); white-space:nowrap; }}
  th.l {{ text-align:left; }}
  td {{ padding:9px 12px; border-bottom:1px solid var(--line); vertical-align:baseline; }}
  tr.scene:nth-of-type(4n+1) td {{ background:var(--zebra); }}
  td.n {{ color:var(--dim); text-align:right; width:34px; font-variant-numeric:tabular-nums; }}
  td.lab {{ font-weight:600; white-space:nowrap; }}
  td.num {{ text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }}
  td.w {{ color:var(--dim); }}
  td.warn {{ color:var(--warn); font-weight:700; background:var(--warnbg); }}
  .d {{ font-size:11px; opacity:.8; }}
  tr.say td {{ color:var(--say); font-style:italic; padding:2px 12px 13px; }}
  tr.total td {{ font-weight:700; border-bottom:none; border-top:2px solid var(--line);
                 background:transparent; }}
  .notes {{ margin-top:26px; background:var(--panel); border:1px solid var(--line);
            border-left:3px solid var(--warn); border-radius:8px; padding:14px 18px; }}
  .notes h2 {{ font-size:13px; margin:0 0 8px; }}
  .notes ul {{ margin:6px 0 0; padding-left:20px; }}
  .notes li {{ margin:3px 0; }}
  .notes p {{ margin:8px 0 0; color:var(--dim); font-size:12.5px; }}
  footer {{ margin-top:22px; color:var(--dim); font-size:11.5px; line-height:1.7; }}
  code {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:11.5px;
          background:var(--zebra); padding:1px 5px; border-radius:4px; }}
</style>

<div class="wrap">
<h1>VTT — {e(store)} · {e(title)} <span class="v">{vlabel}</span></h1>
<p class="sub">Video Timing Table. Not WebVTT subtitles — per scene, how long the footage
runs, how long Sarah&rsquo;s line takes to say, and the gap between them.</p>

<div class="strip">
  <div class="stat"><div class="k">clip</div><div class="v">{T['clip']:.1f}s</div></div>
  <div class="stat"><div class="k">said</div><div class="v">{T['sp']:.1f}s</div></div>
  <div class="stat"><div class="k">dead air</div><div class="v">{(T['gap'] / T['clip'] * 100) if T['clip'] else 0:.0f}%</div></div>
  <div class="stat"><div class="k">over 2.5s</div><div class="v">{len(over)}</div></div>
  <div class="stat"><div class="k">words</div><div class="v">{T['w']}</div></div>
  <div class="stat"><div class="k">frames</div><div class="v">{T['seg']}</div></div>
</div>

<div class="scroll"><table>
  <thead><tr><th></th><th class="l">{e(store.title())} scenes</th>
  <th>clip</th><th>speech</th><th>gap</th>
  <th>segment</th><th>avatar</th><th>narration</th><th>words</th></tr></thead>
  <tbody>
{chr(10).join(body)}
    <tr class="scene total"><td></td><td class="lab">total</td>
      <td class="num">{T['clip']:.1f}s</td><td class="num">{T['sp']:.1f}s</td>
      <td class="num">{T['gap']:.1f}s</td><td class="num">{T['seg']}</td>
      <td class="num">{T['av']}</td><td class="num">–</td>
      <td class="num w">{T['w']}</td></tr>
  </tbody>
</table></div>
{note}
<footer>
  Speech length is estimated at <b>{wps} words/sec</b>, the voice&rsquo;s measured rate.
  Clip length and every frame count are read from the files on disk in
  <code>sandbox/</code> — never typed by hand.<br>
  Lines come from <code>{e(os.path.basename(script_path))}</code>.<br>
  Written by <code>build/vtt_html.py</code>.
</footer>
</div>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", help="the video folder, e.g. .../videos/01-first-time-ordering")
    ap.add_argument("--version", help="which script_v<N>.json to read; default is the newest")
    ap.add_argument("--open", action="store_true", help="open it in a new Chrome tab")
    a = ap.parse_args()

    F = os.path.abspath(a.folder)
    if not os.path.isdir(os.path.join(F, "sandbox")):
        sys.exit(f"  no sandbox/ in {F} — is that a video folder?")

    script_path, ver = pick_script(F, a.version)
    doc, wps, rows = collect(F, script_path)

    missing = [r for r in rows if r["missing"]]
    for r in missing:
        print(f"  ⚠ scene {r['n']} {r['label']}: no segment.mp4 in sandbox/ — "
              f"its clip and gap read 0.0s")

    out = os.path.join(F, "video", "vtt.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w").write(render(doc, wps, rows, ver, script_path))
    print(f"  {len(rows)} scenes from {os.path.basename(script_path)}")
    print(f"  -> {out}")

    if a.open:
        subprocess.run(["open", "-a", "Google Chrome", out], check=False)
        print("  opened in a new Chrome tab")


if __name__ == "__main__":
    main()
