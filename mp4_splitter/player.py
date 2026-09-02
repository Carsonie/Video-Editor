#!/usr/bin/env python3
"""
The MP4 Splitter — the player that opens ONE clip and cuts it into numbered
segments at the break points you mark.

Its page is also every clip's own page: a layered or timeline view is built
from individual clips, and this is what each of them opens on its own.

Frame extraction, the frame map and the edit maths all live in this same
package's own frames.py — duplicated from shared/frames.py on 2026-09-02
when MP4 Splitter and the Segment and Avatar Editor split into fully
independent tools, not imported from shared/ any more.
"""
import json
import os

from mp4_splitter import frames

probe = frames.probe

# The player's name and version, shown at the foot of its page. The version
# lives in a VERSION file beside this module rather than in the source, so a
# bump is a one-line diff that a commit hook can see and a reader can trust.
NAME = "MP4 Splitter"

def _version():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERSION")
    try:
        return open(p).read().strip() or "?"
    except OSError:
        return "?"

def label():
    return f"{NAME} v{_version()}"


def write(outdir, meta):
    """
    (Re)write viewer.html from meta.json — no re-extraction needed. The stage
    is sized to the ACTUAL frame dimensions (disp_w x disp_h), not a padded
    square: no letterbox bars, width held at --box and height following the
    source's own aspect ratio.
    """
    html = TEMPLATE.format(
        title=meta.get("source_name", os.path.basename(meta["source"])),
        has_audio="true" if meta.get("has_audio") else "false",
        # `edited` means frames were added or removed, so the extracted audio —
        # which is the ORIGINAL — no longer lines up. The viewer says so rather
        # than letting a false sync be believed.
        edited_flag="true" if meta.get("edited") else "false",
        nb_frames=meta["nb_frames"], fps=meta["fps"],
        disp_w=meta["disp_w"], disp_h=meta["disp_h"],
        # Toolbelt puts a fixed-width drawer beside the stage. 264 + the 14px
        # grid gap; stack_w is the point below which that no longer fits and
        # the drawer drops under the video instead.
        app_w=meta["disp_w"] + 278, stack_w=meta["disp_w"] + 292,
        source=meta.get("source_name", os.path.basename(meta["source"])),
        slug=os.path.basename(outdir.rstrip(os.sep)),
        # json.dumps, not manual quoting — the source path can contain
        # spaces, quotes, anything a real filesystem path can hold (this
        # project's own paths already do: "Rentify Demos Corp").
        source_path=json.dumps(meta["source"]),
        edited=json.dumps(bool(meta.get("edited", False))),
        player_label=label(),
    )
    open(os.path.join(outdir, "viewer.html"), "w").write(html)


TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8"><title>{title} — video editor</title>
<style>
  :root {{
    color-scheme: dark;
    /* Break points are GREEN on an mp4 and PURPLE on a WebM — the same two
       colours the layered view uses for background and overlay. In THIS view
       there is no layer toggle to read, so the marks are the only thing that
       can say which kind of file is open. Cutting Sarah is not cutting the
       screen recording, and the two are easy to confuse once a long avatar
       render is being spliced like any other clip. */
    --mark:#2ecc40; --markHi:#5aff70; --markGlow:rgba(46,204,64,.35);
  }}
  :root.alpha {{
    --mark:#a56cff; --markHi:#c9a3ff; --markGlow:rgba(165,108,255,.40);
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:#1a1a1a; color:#eee; font-family:-apple-system,sans-serif;
         padding:14px 0 26px; }}

  /* ── Toolbelt layout ───────────────────────────────────────────────────
     The frame takes the whole main column. ONE toolbar under it holds every
     control touched every few seconds — mode, transport, readouts. Anything
     touched once a session lives in the drawer on the right, behind a tab,
     where it cannot be hit by accident.

     Replaced (2026-08-21) a stack of eleven centred full-width rows in which
     the six step buttons were dealt over three rows, the mode switch that
     rewrites what those buttons DO sat below them, and Reset Editor — the
     most destructive control in the tool — sat at the bottom of the scroll
     with the same weight as Browse. */
  #app {{ width:{app_w}px; max-width:100%; margin:0 auto;
         display:grid; grid-template-columns:{disp_w}px 264px; gap:14px; align-items:start; }}
  #main {{ display:flex; flex-direction:column; gap:8px; min-width:0; }}

  #topbar {{ display:flex; align-items:baseline; gap:8px; padding:0 2px 2px; }}
  #topbar #srcName {{ font-size:12px; color:#bbb; overflow:hidden; text-overflow:ellipsis;
                     white-space:nowrap; }}
  #topbar #srcMeta {{ font-size:11px; color:#666; flex-shrink:0; margin-left:auto;
                     font-variant-numeric:tabular-nums; }}

  #stage {{ width:{disp_w}px; height:{disp_h}px; background:#000; border:1px solid #333;
           position:relative; }}
  #frame {{ width:{disp_w}px; height:{disp_h}px; display:block; }}
  /* Marked-frame indicator — CSS drawn on top of the <img>, never part of the
     pixels themselves. Cutting reads the ORIGINAL source file with ffmpeg, which
     has no idea this div exists, so this green can never end up in an output
     .mp4 no matter what. */
  #markOverlay {{ position:absolute; inset:0; display:none; pointer-events:none;
                 background:rgba(46,204,64,0.30); border:4px solid #2ecc40;
                 box-sizing:border-box; }}

  /* ── the one toolbar ── */
  /* THREE rows, one job each: where you are, how you move, what you change.
     Was two, and before that one. The segment durations drawn over the slider
     are only readable if the slider is wide, and a slider sharing a row with
     eight step buttons is not — so the timeline now has a row to itself and
     spans the whole width. Splitting nav from edit matters for a different
     reason: the frame counter used to sit in the same row as the delete
     buttons. */
  #toolbar {{ display:flex; flex-direction:column; align-items:stretch; gap:9px;
             background:#212629; border:1px solid #353c42; border-radius:7px;
             padding:9px 11px; }}
  /* Each row gets its own box, so the three jobs read apart at a glance rather
     than by remembering which button sits where. */
  .toolRow {{ display:flex; align-items:center; gap:8px; flex-wrap:wrap;
             border:1px solid #3d454c; border-radius:7px;
             padding:8px 10px; background:#1b2024; }}
  /* The timeline row holds ONE thing and it should use the whole width — it was
     wedged between the step buttons before, which made the only control you
     drag the narrowest thing on the bar. */
  #rowTimeline {{ padding:6px 10px 8px; }}
  #rowTimeline #sliderWrap {{ flex:1 1 100%; }}
  /* The nav row is the tight one: nine step controls, Loop, and the readouts.
     It needed 760px in a 726px column, so the readouts fell to a second line.
     A smaller gap buys the 34px back — the main column is a FIXED width, so
     this does not come right on a wider window. */
  #rowNav {{ gap:5px; }}
  #readouts {{ text-align:right; min-width:104px; margin-left:auto;
              font-variant-numeric:tabular-nums; }}
  #readouts #posLine {{ font-size:12px; color:#e6e9ec; }}
  /* Total Time is the whole reason Frame Editor exists — you stretch or
     shorten this clip until it matches the narration's fixed length. It used
     to be plain centred text between two unrelated buttons; here it sits in
     the readout block, where the eye already is. */
  #readouts #totalTime {{ font-size:11px; color:#8b949c; }}
  #readouts #totalTime b {{ color:#cfd6dc; font-weight:600; }}
  /* On a long clip cut into many segments the bands get too narrow to hold
     their own label. This line always names the segment the playhead is in
     and its length, so that figure is never unreadable. */
  #readouts #segNow {{ font-size:11px; color:#8b949c; }}
  #readouts #segNow b {{ color:#9fe0ab; font-weight:600; }}

  /* Segmented controls — the mode switch is now physically joined to, and
     level with, the step buttons whose meaning it rewrites. */
  .seg-group {{ display:flex; border:1px solid #4a5259; border-radius:6px; overflow:hidden;
               flex-shrink:0; }}
  .seg-group > button {{ border:0; border-radius:0; height:30px; width:auto; padding:0 11px;
                        font-size:12px; }}
  .seg-group > button + button {{ border-left:1px solid #4a5259; }}
  /* Both halves stay clickable at all times; only the styling shows which is
     current. A literal `disabled` on the inactive one would make switching
     back impossible. */
  button.mode-btn.active, button.sub-btn.active {{ background:#1f5c2e; color:#fff; }}
  button.mode-btn.inactive, button.sub-btn.inactive {{ opacity:0.45; }}
  button.mode-btn.active:hover, button.sub-btn.active:hover {{ background:#256b37; }}
  /* visibility, not display: Add/Subtract appearing must not re-flow the
     toolbar. A control bar that changes width or height when you switch mode
     moves every button out from under the cursor. */
  #subToggle {{ visibility:hidden; }}
  #subToggle.visible {{ visibility:visible; }}
  .sub-btn {{ font-size:11px !important; padding:0 9px !important; }}

  /* Frame Editor tints the six step buttons: green = duplicates frames,
     red = deletes them — so a click reads as constructive/dangerous at a
     glance, not by memory of which mode is on. */
  .edit-add {{ background:#1f4a2e !important; border-color:#2ecc40 !important; }}
  .edit-add:hover {{ background:#255a37 !important; }}
  .edit-del {{ background:#4a2323 !important; border-color:#e05555 !important; }}
  .edit-del:hover {{ background:#5a2b2b !important; }}

  /* ── slider + segment bar ── */
  #sliderWrap {{ position:relative; flex:1; min-width:90px; height:44px;
                display:flex; flex-direction:column; justify-content:flex-end; }}
  /* A range thumb travels from half-a-thumb in to half-a-thumb short of the
     end, but the ticks and the segment bar were laid out across the FULL
     width. So a break point and the pointer could only agree at the exact
     middle, and drifted by up to half a thumb at the ends — clicking a marker
     left the pointer visibly beside it. Fixed in the Segment and Avatar Editor
     first; the same bug was still here. The thumb is given an explicit size so
     the inset is a known number rather than whatever the browser picked. */
  :root {{ --thumb:14px; --halfthumb:7px; }}
  #sliderWrap input[type=range] {{ -webkit-appearance:none; appearance:none;
       width:100%; margin:0; height:var(--thumb); background:transparent; }}
  #sliderWrap input[type=range]::-webkit-slider-runnable-track {{
       height:6px; border-radius:3px; background:#39424a; }}
  #sliderWrap input[type=range]::-webkit-slider-thumb {{ -webkit-appearance:none;
       appearance:none; width:var(--thumb); height:var(--thumb); border-radius:50%;
       background:var(--mark); border:none; margin-top:-4px; }}
  #sliderWrap input[type=range]::-moz-range-track {{ height:6px; border-radius:3px;
       background:#39424a; }}
  #sliderWrap input[type=range]::-moz-range-thumb {{ width:var(--thumb);
       height:var(--thumb); border-radius:50%; background:var(--mark); border:none; }}
  #sliderRow {{ position:relative; height:24px; display:flex; align-items:center; }}
  /* Segment bar — the durations of the files Cut is about to write, drawn
     over the top of the slider, each band spanning exactly the frames that
     segment covers. Boundaries mirror /api/cut's own
     `[1] + marks + [nb_frames+1]` rule, including its skip of an empty
     segment, so a label here is the duration that actually gets written. */
  #segbar {{ position:relative; height:19px; margin:0 var(--halfthumb) 1px; }}
  .seg {{ position:absolute; top:0; bottom:0; display:flex; align-items:center;
         justify-content:center; overflow:hidden; background:#2b3237;
         border-radius:2px; font-size:11px; color:#cfd6dc;
         font-variant-numeric:tabular-nums; white-space:nowrap; }}
  .seg.alt {{ background:#232a2e; }}
  .seg.here {{ background:#1f4a2e; color:#dff5e2; }}
  :root.alpha .seg.here {{ background:#3a2a5c; color:#ece2ff; }}
  /* No break points means one span and nothing to cut — shown, but dimmed,
     so the bar never changes height and never implies a cut is available. */
  .seg.idle {{ background:#242424; color:#7d858b; }}
  .seg > span {{ flex:none; padding:0 3px; }}
  .seg.narrow > span {{ display:none; }}

  /* The CONTAINER stays click-through so the slider still takes a click or a
     drag anywhere along its length; only the ticks themselves opt back in. */
  #ticks {{ position:absolute; left:var(--halfthumb); right:var(--halfthumb);
           top:50%; height:14px; margin-top:-7px; pointer-events:none; }}
  .tick {{ position:absolute; top:0; width:3px; height:100%; background:var(--mark);
          transform:translateX(-50%); border-radius:1px;
          pointer-events:auto; cursor:pointer; }}
  /* A 3px target cannot be hit with a mouse. This widens the CLICKABLE area to
     15px without widening the 3px line the eye sees. */
  .tick::before {{ content:''; position:absolute; left:-6px; right:-6px;
                  top:-5px; bottom:-5px; }}
  .tick:hover {{ background:var(--markHi); box-shadow:0 0 0 2px var(--markGlow); }}
  .tick.at {{ background:#eaff00; box-shadow:0 0 0 2px rgba(234,255,0,.4); }}

  button, a.stepbtn {{ background:#2c3236; color:#eee; border:1px solid #4a5259;
           border-radius:6px; width:44px; height:36px; font-size:18px; cursor:pointer;
           font-family:inherit; }}
  button.stepbtn, a.stepbtn {{ width:auto; padding:0 12px; font-size:13px; height:30px;
           display:inline-flex; align-items:center; justify-content:center; gap:5px;
           text-decoration:none; box-sizing:border-box; white-space:nowrap; }}
  .navbtn {{ height:30px; font-size:13px; padding:0 8px; width:auto; }}
  .navbtn.one {{ width:32px; padding:0; font-size:15px; }}
  button:hover, a.stepbtn:hover {{ background:#373e43; }}
  button:disabled {{ opacity:0.35; cursor:default; }}
  button:focus-visible, a:focus-visible {{ outline:2px solid #7aa7ff; outline-offset:1px; }}

  /* Matched to .navbtn so the transport reads as one row of controls. */
  .navsel {{ background:#2c3236; color:#eee; border:1px solid #4a5259; border-radius:6px;
            height:30px; font-size:13px; font-family:inherit; padding:0 4px; cursor:pointer; }}
  .navsel:hover {{ background:#373e43; }}
  .navsel:focus-visible {{ outline:2px solid #7aa7ff; outline-offset:1px; }}
  /* Lit while anything other than 1x is selected, so a clip playing at an odd
     speed can never be mistaken for one playing normally. */
  .navsel.off1 {{ background:#1f5c2e; border-color:#2ecc40; color:#fff; }}
  #editNote {{ font-size:11px; color:#886; padding:0 2px; }}
  #editStatus {{ font-size:12px; color:#e0c060; white-space:pre-line; padding:0 2px;
               min-height:16px; }}

  /* ── drawer ── */
  #drawer {{ display:flex; flex-direction:column; gap:8px; }}
  #tabs {{ display:flex; border:1px solid #4a5259; border-radius:6px; overflow:hidden; }}
  .tab {{ flex:1; border:0; border-radius:0; height:32px; width:auto; font-size:12px;
         display:inline-flex; align-items:center; justify-content:center; gap:5px; }}
  .tab + .tab {{ border-left:1px solid #4a5259; }}
  .tab.active {{ background:#3a4248; color:#fff; }}
  .tab.inactive {{ opacity:0.5; }}
  /* A tab that hides a control also hides that control's STATE. These two
     badges put the state back on the outside of the tab: how many break
     points are waiting, and whether there are unsaved Frame Editor edits. */
  .badge {{ font-size:10px; min-width:16px; height:16px; padding:0 4px; border-radius:8px;
           background:#4a5259; color:#dfe4e8; display:inline-flex; align-items:center;
           justify-content:center; font-variant-numeric:tabular-nums; }}
  .badge.on {{ background:#2ecc40; color:#0d2b13; }}
  .msq {{ display:inline-block; width:11px; height:11px; border-radius:2px;
          background:var(--mark); margin-right:6px; vertical-align:-1px; }}
  .badge.dot {{ min-width:8px; width:8px; height:8px; padding:0; border-radius:50%;
               background:#2e8ecc; }}
  .badge.hidden {{ display:none; }}

  .panel {{ border:1px solid #353c42; border-radius:7px; background:#212629; padding:11px; }}
  .panel[hidden] {{ display:none; }}
  .panelHead {{ display:flex; justify-content:space-between; align-items:center; gap:8px;
               margin-bottom:9px; }}
  .lbl {{ font-size:10px; letter-spacing:.12em; text-transform:uppercase; color:#7d858b; }}
  #clearBtn {{ width:auto; height:24px; padding:0 8px; font-size:11px;
              background:#3a2323; border-color:#663; color:#f99; flex-shrink:0; }}
  #clearBtn:hover {{ background:#4a2b2b; }}
  #marksList {{ display:flex; flex-direction:column; gap:3px; max-height:210px;
               overflow-y:auto; }}
  .markRow {{ display:flex; justify-content:space-between; align-items:center;
             background:#181c1f; border-radius:4px; padding:5px 9px; font-size:12px;
             font-variant-numeric:tabular-nums; }}
  .markRow .jump {{ cursor:pointer; color:#c8cfd5; }}
  .markRow .jump b {{ color:#fff; font-weight:600; }}
  .markRow button {{ background:none; border:none; color:#f66; cursor:pointer;
                    font-size:14px; width:auto; height:auto; padding:0 3px; }}
  .markRow button:hover {{ color:#f99; background:none; }}
  .empty {{ font-size:11px; color:#6d757b; padding:6px 2px; line-height:1.5; }}

  .stack {{ display:flex; flex-direction:column; gap:6px; }}
  .full {{ width:100%; }}
  /* Actions grouped by consequence, never mixed in one undifferentiated row:
     Cut and Save WRITE files; Clear all edits and Reset Editor THROW WORK
     AWAY. The divider and the red block are the only thing standing between
     a mis-click and a deleted cache. */
  .riskHead {{ color:#c08484; }}
  #cutBtn {{ background:#1f5c2e; border-color:#2ecc40; }}
  #cutBtn:hover {{ background:#256b37; }}
  :root.alpha #cutBtn {{ background:#3a2a5c; border-color:var(--mark); }}
  :root.alpha #cutBtn:hover {{ background:#48357180; background:#483571; }}
  :root.alpha .badge.on {{ background:var(--mark); color:#1a0d33; }}
  #cutBtn:disabled {{ background:#2c3236; border-color:#4a5259; }}
  #saveBtn {{ background:#1a3a5c; border-color:#2e8ecc; }}
  #saveBtn:hover {{ background:#204a72; }}
  #saveBtn:disabled {{ background:#2c3236; border-color:#4a5259; }}
  /* Ported from the Segment and Avatar Editor. A native tooltip appears at the
     browser's own timing and cannot be styled or placed, so a control whose tip
     runs to three lines is unreadable at the moment you need it. */
  #segList {{ margin:6px 0 0; max-height:190px; overflow:auto; }}
  .sgrow {{ display:flex; align-items:baseline; gap:7px; padding:3px 4px;
           border-radius:4px; font-size:11px; color:#cfd6dc; cursor:pointer;
           font-variant-numeric:tabular-nums; }}
  .sgrow:nth-child(odd) {{ background:#20262a; }}
  .sgrow.here {{ background:#1f4a2e; color:#dff5e2; }}
  .sgrow .sn {{ color:#8b949c; width:38px; flex:none; }}
  .sgrow.here .sn {{ color:#9fe0ab; }}
  .sgrow .sf {{ margin-left:auto; color:#8b949c; }}
  .sgrow.here .sf {{ color:#cfe9d4; }}
  #segTotals {{ margin-top:6px; padding-top:6px; border-top:1px solid #353c42;
               display:flex; gap:7px; font-size:11px; color:#8b949c;
               font-variant-numeric:tabular-nums; }}
  #segTotals b {{ color:#cfd6dc; font-weight:600; }}
  #segTotals .st {{ margin-left:auto; }}
  #tip {{ position:fixed; z-index:99; max-width:320px; padding:7px 10px;
         background:#0f1214; color:#dfe4e7; border:1px solid #66727c;
         border-radius:6px; font-size:12px; line-height:1.45;
         box-shadow:0 6px 20px rgba(0,0,0,.55); pointer-events:none;
         opacity:0; transition:opacity .12s ease; }}
  #tip.on {{ opacity:1; }}
  #loopLbl {{ display:inline-flex; align-items:center; gap:5px; font-size:13px;
             color:#cfd6dc; border:1px solid #4a5259; border-radius:6px;
             padding:6px 9px; cursor:pointer; user-select:none; white-space:nowrap; }}
  #loopLbl:hover {{ border-color:var(--mark); }}
  #loopLbl input {{ margin:0; accent-color:var(--mark); cursor:pointer; }}
  #clearEditsBtn {{ background:#4a2323; border-color:#e05555; color:#f6c9c9; }}
  #clearEditsBtn:hover {{ background:#5a2b2b; }}
  #resetEditorBtn {{ background:#5c1414; border-color:#ff4444; color:#ffdddd; }}
  #resetEditorBtn:hover {{ background:#711b1b; }}
  #handoff {{ margin-top:2px; }}
  .hrow {{ display:flex; align-items:center; gap:6px; margin:5px 0; }}
  .hrow .hn {{ color:#8a949b; font-size:11px; width:58px; flex:none;
              font-variant-numeric:tabular-nums; }}
  .hrow input {{ flex:1; min-width:0; background:#1b2024; color:#e6ebee;
                border:1px solid #3a4249; border-radius:5px; padding:5px 7px;
                font:inherit; font-size:12px; }}
  .hrow input:focus {{ outline:none; border-color:var(--mark); }}
  .hrow input.bad {{ border-color:#e05555; }}
  #handoffStatus {{ margin-top:7px; font-size:11px; color:#e0c060;
                   white-space:pre-line; line-height:1.5; word-break:break-word; }}
  #cutStatus {{ margin-top:8px; font-size:11px; color:#e0c060; white-space:pre-line;
              line-height:1.5; word-break:break-word; }}
  #fileMeta {{ font-size:11px; color:#7d858b; line-height:1.6; word-break:break-word; }}
  hr.sep {{ border:0; border-top:1px solid #353c42; margin:11px 0 9px; }}

  @media (max-width: {stack_w}px) {{
    #app {{ grid-template-columns:{disp_w}px; width:{disp_w}px; }}
  }}
  /* The player's own name, at the foot of the page. Three players share this
     server and look alike at a glance; this is what says which one you are in
     before you touch a control. */
  .playerName {{ margin:22px auto 4px; text-align:center; font-size:12px;
                letter-spacing:.16em; text-transform:uppercase; color:#6d757b; }}
</style></head>
<body>
  <div id="app">
    <div id="main">
      <div id="topbar">
        <span id="srcName">{source}</span>
        <span id="srcMeta">{fps:g}fps</span>
      </div>

      <div id="stage"><img id="frame" src="frames/frame_00001.jpg"><div id="markOverlay"></div></div>
      <audio id="aud" src="audio.m4a" preload="auto"></audio>

      <!-- Three rows, one job each: WHERE you are, HOW you move, WHAT you
           change. The timeline used to sit wedged between the step buttons, so
           the one control you drag was the narrowest thing on the bar and the
           frame counter was in the same row as the delete buttons. -->
      <div id="toolbar">

        <!-- 1. the timeline, and nothing else -->
        <div class="toolRow" id="rowTimeline">
          <div id="sliderWrap">
            <div id="segbar"></div>
            <div id="sliderRow">
              <input id="slider" type="range" min="1" max="{nb_frames}" value="1" step="1">
              <div id="ticks"></div>
            </div>
          </div>
        </div>

        <!-- 2. moving through it -->
        <div class="toolRow" id="rowNav">
          <button id="playBtn" class="stepbtn navbtn" title="Play / pause (space)">▶</button>
          <button id="muteBtn" class="stepbtn navbtn" title="Mute / unmute">🔊</button>
          <select id="rateSel" class="navsel" title="Playback speed. Slow to judge a seam; 2x to skim.">
            <option value="2">2x</option>
            <option value="1" selected>1x</option>
            <option value="0.5">0.5x</option>
            <option value="0.25">0.25x</option>
            <option value="0.125">0.125x</option>
          </select>
          <button id="prev100" class="stepbtn navbtn" title="Back 100 frames">«100</button>
          <button id="prev10" class="stepbtn navbtn" title="Back 10 frames">«10</button>
          <button id="prev" class="stepbtn navbtn one" title="Previous frame (←)">◀</button>
          <button id="next" class="stepbtn navbtn one" title="Next frame (→)">▶</button>
          <button id="next10" class="stepbtn navbtn" title="Forward 10 frames">10»</button>
          <button id="next100" class="stepbtn navbtn" title="Forward 100 frames">100»</button>
          <label id="loopLbl" title="Play only the zone, over and over. Judging a cut point is watching the same two seconds repeatedly, which is what this is for."><input type="checkbox" id="loopChk" title="Play only the zone — the span between the break points either side of the pointer — over and over. With nothing marked the zone is the whole clip."> ↻ Loop Zone</label>

          <div id="readouts">
            <div id="posLine"><span id="framecount">frame 1 / {nb_frames}</span> · <span id="timecode">0.000s</span></div>
            <div id="totalTime">total <b>0.000s</b></div>
            <div id="segNow"></div>
          </div>
        </div>

        <!-- 3. changing it -->
        <div class="toolRow" id="rowEdit">
          <span class="seg-group">
            <button id="markBtn" class="mode-btn" title="Mark or unmark this frame as a break point (M)"><span class="msq"></span>Mark</button>
            <button id="frameEditorBtn" class="mode-btn" title="Frame Editor: the step buttons insert or delete frames instead of navigating">✂️ Edit</button>
          </span>
          <span class="seg-group" id="subToggle">
            <button id="addBtn" class="sub-btn" title="Add — the step buttons duplicate this frame on that side">＋ Add</button>
            <button id="subtractBtn" class="sub-btn" title="Subtract — the step buttons delete frames on that side">－ Sub</button>
          </span>
          <!-- Zone: the whole span between the break points either side of the
               playhead, acted on in one go. Trimming a dead patch out of a
               recording is this tool's job, and one frame at a time made a
               three-second patch seventy-five clicks. -->
          <span class="seg-group" id="zoneToggle">
            <button id="addZoneBtn" class="sub-btn" title="Repeat the whole zone — the span between the break points either side of the pointer. With no break points the zone is the whole clip.">＋ Zone</button>
            <button id="delZoneBtn" class="sub-btn" title="Delete the whole zone in one go — the span between the break points either side of the pointer. This is how an unwanted patch comes out.">－ Zone</button>
          </span>
          <button id="undoBtn" class="stepbtn navbtn" disabled title="Step back through this clip's edits, one at a time. Cleared when you save. The source file is never touched either way.">↶ Undo</button>
        </div>
      </div>

      <div id="tip"></div>
      <div id="editStatus"></div>
      <div id="editNote">Frame Editor edits the preview here. Cut and Save rebuild those frames from the original file — never a screenshot of this preview.</div>
    </div>

    <aside id="drawer">
      <div id="tabs">
        <button class="tab" id="tabMarks" title="The break points you have set, in order, with the time of each. Click one to jump the pointer to it.">Break points <span class="badge hidden" id="markBadge">0</span></button>
        <button class="tab" id="tabFile" title="This clip's details, and the controls that write to disk: Save, discard edits, and Reset Editor.">File <span class="badge dot hidden" id="editBadge" title="Unsaved Frame Editor edits"></span></button>
      </div>

      <section class="panel" id="panelMarks">
        <div class="panelHead">
          <span class="lbl" id="marksLabel">No break points</span>
          <button id="clearBtn" disabled title="Remove every break point">Clear all</button>
        </div>
        <div id="marksList"></div>
        <div class="empty" id="marksEmpty">Move to a frame and press <b>Mark</b> (or <b>M</b>) to set a break point. Cutting splits <b>{source}</b> itself — never these preview frames.</div>
        <hr class="sep">
        <!-- What Cut is about to write, above the button that writes it. The
             durations drawn over the slider say the same thing in a shape you
             can point at; this one you can read. -->
        <span class="lbl">Segments</span>
        <div id="segList"></div>
        <div id="segTotals"></div>
        <hr class="sep">
        <button id="cutBtn" class="stepbtn full" disabled title="Cut the SOURCE FILE at every break point and write the pieces to dev/_cuts/. Reads the original with ffmpeg — never these preview frames. Cutting again keeps the earlier attempt and bumps its version.">✂️ Cut into segments</button>
        <div id="cutStatus"></div>
        <!-- The handover. The splitter writes _cuts/Num_3-v1-segment.mp4; the
             Segment and Avatar Editor reads sandbox/03-<name>/segment.mp4.
             Naming them here is what turns loose cuts into scenes. -->
        <div id="handoff" hidden>
          <hr class="sep">
          <span class="lbl">Hand off to sandbox</span>
          <div id="handoffRows"></div>
          <button id="handoffBtn" class="stepbtn full" title="Copy these segments into the sandbox as named scenes, and write a scene row for each into script.json. This is where the Segment and Avatar Editor picks the work up.">→ Hand off to sandbox</button>
          <div id="handoffStatus"></div>
        </div>
      </section>

      <section class="panel" id="panelFile" hidden>
        <span class="lbl">Clip</span>
        <div id="fileMeta">{source}<br>{fps:g}fps · <span id="fileFrames">{nb_frames} frames</span></div>
        <div class="stack" style="margin-top:9px">
          <a class="stepbtn full" href="../browse.html" title="Browse the Customers folder for another recording">📁 Browse…</a>
        </div>
        <hr class="sep">
        <span class="lbl">Write to disk</span>
        <div class="stack" style="margin-top:7px">
          <button id="saveBtn" class="stepbtn full" disabled title="Rebuild this clip's edits and overwrite the file this viewer opened">💾 Save edited segment</button>
        </div>
        <hr class="sep">
        <span class="lbl riskHead">Discard</span>
        <div class="stack" style="margin-top:7px">
          <button id="clearEditsBtn" class="stepbtn full" title="Discard every edit and break point in this preview and re-extract clean frames — the source file is never touched">↺ Clear all edits</button>
          <button id="resetEditorBtn" class="stepbtn full" title="Delete this video's entire cache in the tool — frames, edits, break points, everything — and return to Browse. The original video FILE is never touched.">🗑️ Reset Editor</button>
        </div>
      </section>
    </aside>
  </div>
  <div class="playerName">{player_label}</div>
<script>
  let N = {nb_frames};
  const FPS = {fps}, SLUG = "{slug}", SOURCE_PATH = {source_path};
  // A .webm here is always a transparent avatar render — the only kind this
  // pipeline makes. Set before anything paints, so no mark is ever drawn in the
  // wrong colour even for one frame.
  const IS_ALPHA = String(SOURCE_PATH).toLowerCase().endsWith('.webm');
  if (IS_ALPHA) document.documentElement.classList.add('alpha');
  let hasEdits = {edited};
  const img = document.getElementById('frame');
  const slider = document.getElementById('slider');
  const playBtn = document.getElementById('playBtn');
  const rateSel = document.getElementById('rateSel');
  const muteBtn = document.getElementById('muteBtn');
  const aud = document.getElementById('aud');
  const HAS_AUDIO = {has_audio};
  const EDITED = {edited_flag};
  const ticks = document.getElementById('ticks');
  const segbar = document.getElementById('segbar');
  const prev = document.getElementById('prev');
  const next = document.getElementById('next');
  const prev10 = document.getElementById('prev10');
  const next10 = document.getElementById('next10');
  const prev100 = document.getElementById('prev100');
  const next100 = document.getElementById('next100');
  const framecount = document.getElementById('framecount');
  const timecode = document.getElementById('timecode');
  const markBtn = document.getElementById('markBtn');
  // The button's square was the emoji 🟩 — literally green, and unchangeable.
  // On a WebM it sat next to purple marks claiming to make green ones.
  function markSquare(on) {{
    const e = document.createElement('span');
    e.className = 'msq';
    e.style.background = on ? 'var(--markHi)' : 'var(--mark)';
    return e;
  }}
  const frameEditorBtn = document.getElementById('frameEditorBtn');
  const subToggle = document.getElementById('subToggle');
  const addBtn = document.getElementById('addBtn');
  const subtractBtn = document.getElementById('subtractBtn');
  const addZoneBtn = document.getElementById('addZoneBtn');
  const delZoneBtn = document.getElementById('delZoneBtn');
  const undoBtn = document.getElementById('undoBtn');
  const loopChk = document.getElementById('loopChk');
  const markOverlay = document.getElementById('markOverlay');
  const marksList = document.getElementById('marksList');
  const marksEmpty = document.getElementById('marksEmpty');
  const marksLabel = document.getElementById('marksLabel');
  const markBadge = document.getElementById('markBadge');
  const editBadge = document.getElementById('editBadge');
  const cutBtn = document.getElementById('cutBtn');
  const saveBtn = document.getElementById('saveBtn');
  const clearEditsBtn = document.getElementById('clearEditsBtn');
  const resetEditorBtn = document.getElementById('resetEditorBtn');
  const cutStatus = document.getElementById('cutStatus');
  const handoff = document.getElementById('handoff');
  const handoffRows = document.getElementById('handoffRows');
  const handoffBtn = document.getElementById('handoffBtn');
  const handoffStatus = document.getElementById('handoffStatus');
  const clearBtn = document.getElementById('clearBtn');
  const editStatus = document.getElementById('editStatus');
  const totalTime = document.getElementById('totalTime');
  const segNow = document.getElementById('segNow');
  const fileFrames = document.getElementById('fileFrames');
  const tabMarks = document.getElementById('tabMarks');
  const tabFile = document.getElementById('tabFile');
  const panelMarks = document.getElementById('panelMarks');
  const panelFile = document.getElementById('panelFile');

  let marks = new Set();
  let mode = 'mark';       // 'mark' | 'frame-editor'
  let editSub = 'add';     // 'add' | 'subtract' — only meaningful in frame-editor mode
  let tab = 'marks';       // 'marks' | 'file'

  function pad(n) {{ return String(n).padStart(5, '0'); }}
  function fmtTime(n) {{ return ((n - 1) / FPS).toFixed(3) + 's'; }}
  // The whole point of Frame Editor: the avatar's narration is the fixed
  // length, and this clip has to be stretched or shortened to match it. This
  // is the number to watch while doing that — total frames / fps, updated
  // every time N changes, never on plain navigation (moving the playhead
  // doesn't change how long the clip is).
  function updateTotalTime() {{
    totalTime.innerHTML = `total <b>${{(N / FPS).toFixed(3)}}s</b>`;
    fileFrames.textContent = `${{N}} frames`;
  }}

  // Cache-buster for frame URLs. A frame's URL is its POSITION, so any edit
  // that shifts frames changes what lives at an unchanged URL. The server now
  // restamps shifted files so revalidation is honest, but this makes the
  // viewer immune regardless of what any cache in between decides to do —
  // the failure it prevents (silently showing stale pictures) is invisible
  // until the finished video is wrong.
  let frameVer = Date.now();

  function show(n) {{
    n = Math.max(1, Math.min(N, n));
    slider.value = n;
    img.src = `frames/frame_${{pad(n)}}.jpg?v=${{frameVer}}`;
    framecount.textContent = `frame ${{n}} / ${{N}}`;
    timecode.textContent = fmtTime(n);
    // Boundary rules depend on what a click currently DOES. Navigation and
    // Subtract both need a real frame on that side (nothing before frame 1,
    // nothing after the last frame). Add has no such limit in either
    // direction — extending a hold at either end of the clip with more
    // copies of the edge frame is exactly what this mode is for.
    const adding = mode === 'frame-editor' && editSub === 'add';
    prev.disabled = prev10.disabled = prev100.disabled = adding ? false : (n <= 1);
    next.disabled = next10.disabled = next100.disabled = adding ? false : (n >= N);
    updateMarkUI();
    highlightSegment(n);
    markTickAt(n);
  }}
  // preload the next single-step frame so ◀/▶ never shows a blank flash
  function preload(n) {{ if (n >= 1 && n <= N) new Image().src = `frames/frame_${{pad(n)}}.jpg?v=${{frameVer}}`; }}
  function step(delta) {{ const n = +slider.value + delta; show(n); if (Math.abs(delta) === 1) preload(n + delta); }}

  function updateMarkUI() {{
    const n = +slider.value;
    const on = marks.has(n);
    markOverlay.style.display = on ? 'block' : 'none';
    markBtn.textContent = (on ? 'Marked' : 'Mark');
    markBtn.prepend(markSquare(on));
    markBtn.title = on ? 'Unmark this frame (M)' : 'Mark this frame as a break point (M)';
  }}

  function updateModeUI() {{
    const editing = mode === 'frame-editor';
    markBtn.classList.toggle('active', !editing);
    markBtn.classList.toggle('inactive', editing);
    frameEditorBtn.classList.toggle('active', editing);
    frameEditorBtn.classList.toggle('inactive', !editing);
    subToggle.classList.toggle('visible', editing);

    const adding = editSub === 'add';
    addBtn.classList.toggle('active', adding);
    addBtn.classList.toggle('inactive', !adding);
    subtractBtn.classList.toggle('active', !adding);
    subtractBtn.classList.toggle('inactive', adding);

    // Tint by WHAT the click does, not by which side of the slider the
    // button sits on — in Add, both sides duplicate (green); in Subtract,
    // both sides delete (red). Only relevant while actually in edit mode.
    const tintAdd = editing && adding, tintDel = editing && !adding;
    for (const b of [prev, next, prev10, next10, prev100, next100]) {{
      b.classList.toggle('edit-add', tintAdd);
      b.classList.toggle('edit-del', tintDel);
    }}

    if (!editing) {{
      prev.title = 'Previous frame (←)'; next.title = 'Next frame (→)';
      prev10.title = 'Back 10 frames'; next10.title = 'Forward 10 frames';
      prev100.title = 'Back 100 frames'; next100.title = 'Forward 100 frames';
    }} else if (adding) {{
      prev.title = 'Duplicate this frame, insert to the left';
      next.title = 'Duplicate this frame, insert to the right';
      prev10.title = 'Duplicate this frame 10x, insert to the left';
      next10.title = 'Duplicate this frame 10x, insert to the right';
      prev100.title = 'Duplicate this frame 100x, insert to the left';
      next100.title = 'Duplicate this frame 100x, insert to the right';
    }} else {{
      prev.title = 'Delete 1 frame to the left';
      next.title = 'Delete 1 frame to the right';
      prev10.title = 'Delete 10 frames to the left';
      next10.title = 'Delete 10 frames to the right';
      prev100.title = 'Delete 100 frames to the left';
      next100.title = 'Delete 100 frames to the right';
    }}
    show(+slider.value);  // refreshes the boundary-disabled state for the new mode
  }}

  function setTab(which) {{
    tab = which;
    const onMarks = which === 'marks';
    tabMarks.classList.toggle('active', onMarks);
    tabMarks.classList.toggle('inactive', !onMarks);
    tabFile.classList.toggle('active', !onMarks);
    tabFile.classList.toggle('inactive', onMarks);
    panelMarks.hidden = !onMarks;
    panelFile.hidden = onMarks;
  }}

  // ── segments ─────────────────────────────────────────────────────────
  // A DELIBERATE mirror of /api/cut's own boundary rule in serve.py:
  //     boundaries = [1] + marks + [nb_frames + 1]
  //     start = boundaries[i], end = boundaries[i+1] - 1
  //     if end < start: continue          (a mark on frame 1 makes an empty
  //                                        first segment, which is skipped —
  //                                        so Num_1 is the SECOND span)
  //     duration = (end - start + 1) / fps
  // If these two ever drift apart, the durations drawn over the slider stop
  // being the durations that get written. Change them together.
  function computeSegments() {{
    const sorted = [...marks].sort((a, b) => a - b);
    const bounds = [1, ...sorted, N + 1];
    const segs = [];
    for (let i = 0; i < bounds.length - 1; i++) {{
      const start = bounds[i], end = bounds[i + 1] - 1;
      if (end < start) continue;
      segs.push({{ n: segs.length + 1, start, end,
                  frames: end - start + 1, dur: (end - start + 1) / FPS }});
    }}
    return segs;
  }}

  // Frame f's position along the track, as a 0..1 fraction — the same mapping
  // renderTicks uses, so each band's edge lands exactly on its green tick.
  function pos(f) {{ return N <= 1 ? 0 : (f - 1) / (N - 1); }}

  function renderSegments() {{
    const segs = computeSegments();
    const idle = marks.size === 0;
    const fitting = [];
    segbar.innerHTML = '';
    segs.forEach((s, i) => {{
      const left = pos(s.start);
      // The last band runs to the very end of the track; every other one
      // stops where the next band starts, so they abut with no gap.
      const right = (i === segs.length - 1) ? 1 : pos(s.end + 1);
      const el = document.createElement('div');
      el.className = 'seg' + (idle ? ' idle' : (i % 2 ? ' alt' : ''));
      el.style.left = (left * 100) + '%';
      el.style.width = Math.max(0, (right - left) * 100) + '%';
      el.dataset.start = s.start;
      el.dataset.end = s.end;
      el.dataset.name = `Num_${{s.n}}`;
      el.dataset.dur = s.dur;
      el.title = idle
        ? `Whole clip — ${{s.frames}} frames, ${{s.dur.toFixed(3)}}s. No break points yet, so there is nothing to cut.`
        : `Num_${{s.n}} — frames ${{s.start}}–${{s.end}} (${{s.frames}}), ${{s.dur.toFixed(3)}}s`;
      const label = document.createElement('span');
      label.textContent = s.dur.toFixed(3) + 's';
      el.appendChild(label);
      segbar.appendChild(el);
      fitting.push({{ el, label, dur: s.dur }});
    }});
    // Fit the labels in a SECOND pass, after every band is in the document,
    // so the browser lays out once instead of once per band. A band too
    // narrow for `12.345s` gets `12.3s`; one too narrow for that shows
    // nothing and leaves the figure to the tooltip and to #segNow. Measured,
    // not guessed from a pixel constant — the text width depends on the
    // digits and on whatever font actually resolved.
    for (const f of fitting) {{
      const band = f.el.clientWidth;
      if (label_fits(f.label, band)) continue;
      f.label.textContent = f.dur.toFixed(1) + 's';
      if (label_fits(f.label, band)) continue;
      f.el.classList.add('narrow');
    }}
    highlightSegment(+slider.value);
  }}

  function label_fits(label, band) {{ return label.scrollWidth <= band; }}

  // Which segment the playhead is in — so "the clip I am about to cut here"
  // is visible without counting marks.
  function highlightSegment(n) {{
    let here = null;
    for (const el of segbar.children) {{
      const on = marks.size > 0 && n >= +el.dataset.start && n <= +el.dataset.end;
      el.classList.toggle('here', on);
      if (on) here = el;
    }}
    segNow.innerHTML = here
      ? `${{here.dataset.name}} · <b>${{(+here.dataset.dur).toFixed(3)}}s</b>`
      : '';
    // The list follows the playhead the cheap way: a class toggled on rows that
    // already exist. Rebuilding it every frame would rebuild the DOM 25 times a
    // second to change one background colour.
    const bands = [...segbar.children];
    const at = here ? bands.indexOf(here) : -1;
    const rows = document.querySelectorAll('#segList .sgrow');
    for (let i = 0; i < rows.length; i++) rows[i].classList.toggle('here', i === at);
  }}

  function renderTicks() {{
    ticks.innerHTML = '';
    for (const m of marks) {{
      const t = document.createElement('div');
      t.className = 'tick';
      t.style.left = (pos(m) * 100) + '%';
      t.dataset.frame = m;
      t.title = `frame ${{m}} (${{fmtTime(m)}}) — click to jump here`;
      // mousedown, not click: the tick sits ON the slider, so a plain click
      // would first let the slider seek to wherever the pointer landed and
      // only then jump — a visible double-move. Taking mousedown and stopping
      // it there means the tick wins outright and the frame is exact.
      t.addEventListener('mousedown', (e) => {{
        e.preventDefault();
        e.stopPropagation();
        show(m);
      }});
      ticks.appendChild(t);
    }}
    markTickAt(+slider.value);
  }}

  // Highlight the tick the viewer is parked on, so stepping through the marks
  // shows which boundary is being looked at.
  function markTickAt(n) {{
    for (const t of ticks.children) t.classList.toggle('at', +t.dataset.frame === n);
  }}

  // Walk to the previous/next break point. Checking a cut means visiting every
  // boundary in turn, and scrubbing thousands of frames by hand to reach each
  // one is what made that unpleasant.
  function jumpMark(dir) {{
    const sorted = [...marks].sort((a, b) => a - b);
    if (!sorted.length) return;
    const n = +slider.value;
    const next = dir > 0 ? sorted.find(m => m > n)
                         : [...sorted].reverse().find(m => m < n);
    if (next !== undefined) show(next);
  }}

  function renderMarksList() {{
    const sorted = [...marks].sort((a, b) => a - b);
    const segs = computeSegments();
    cutBtn.disabled = sorted.length === 0;
    clearBtn.disabled = sorted.length === 0;
    cutBtn.textContent = segs.length >= 2
      ? `✂️ Cut into ${{segs.length}} segments` : '✂️ Cut into segments';
    marksLabel.textContent = sorted.length === 0 ? 'No break points'
      : `${{sorted.length}} break point${{sorted.length === 1 ? '' : 's'}} · click a mark, or ⌥←/⌥→`;
    markBadge.textContent = sorted.length;
    markBadge.classList.toggle('hidden', sorted.length === 0);
    markBadge.classList.toggle('on', sorted.length > 0);
    marksEmpty.hidden = sorted.length > 0;
    marksList.innerHTML = '';
    for (const m of sorted) {{
      const row = document.createElement('div');
      row.className = 'markRow';
      const label = document.createElement('span');
      label.className = 'jump';
      label.innerHTML = `<b>${{m}}</b>  ${{fmtTime(m)}}`;
      label.title = 'Jump to this frame';
      label.onclick = () => show(m);
      const x = document.createElement('button');
      x.textContent = '✕';
      x.title = 'Remove this break point';
      x.onclick = () => setMark(m, false);
      row.appendChild(label);
      row.appendChild(x);
      marksList.appendChild(row);
    }}
  }}

  // Every path that changes the marks or the frame count has to refresh all
  // three views of them — the ticks, the segment durations and the list.
  function refreshMarkViews() {{
    renderTicks();
    renderSegments();
    renderSegList();
    renderMarksList();
    updateMarkUI();
  }}

  // The same computeSegments() the slider bands come from, so the list and the
  // bar can never disagree about what Cut will write.
  function renderSegList() {{
    const segs = computeSegments();
    const at = +slider.value;
    const box = document.getElementById('segList');
    box.innerHTML = '';
    for (const sg of segs) {{
      const row = document.createElement('div');
      row.className = 'sgrow' + (at >= sg.start && at <= sg.end ? ' here' : '');
      row.title = `Frames ${{sg.start}}-${{sg.end}}, written as `
                + `Num_${{sg.n}}-v<next>-segment.mp4. Click to jump to its first frame.`;
      row.innerHTML = `<span class="sn">Num_${{sg.n}}</span>`
                    + `<span class="sd">${{sg.dur.toFixed(2)}}s</span>`
                    + `<span class="sf">${{sg.frames}}f</span>`;
      row.addEventListener('click', () => {{ slider.value = sg.start; show(sg.start); }});
      box.appendChild(row);
    }}
    const frames = segs.reduce((a, sg) => a + sg.frames, 0);
    const secs = segs.reduce((a, sg) => a + sg.dur, 0);
    document.getElementById('segTotals').innerHTML =
      `<span><b>${{segs.length}}</b> segment${{segs.length === 1 ? '' : 's'}}</span>`
      + `<span class="st"><b>${{secs.toFixed(2)}}</b>s &middot; <b>${{frames}}</b>f</span>`;
  }}

  function setEdited(on) {{
    hasEdits = on;
    saveBtn.disabled = !on;
    editBadge.classList.toggle('hidden', !on);
  }}

  async function setMark(frame, on) {{
    const r = await fetch('/api/mark', {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{slug: SLUG, frame, on}})
    }});
    const data = await r.json();
    if (data.error) {{ cutStatus.textContent = 'Error: ' + data.error; return; }}
    marks = new Set(data.marks);
    refreshMarkViews();
  }}

  async function loadMarks() {{
    const r = await fetch(`/api/marks?slug=${{encodeURIComponent(SLUG)}}`);
    const data = await r.json();
    if (data.marks) {{
      marks = new Set(data.marks);
      refreshMarkViews();
    }}
  }}

  function applyFrameEdit(data) {{
    N = data.nb_frames;
    slider.max = N;
    marks = new Set(data.marks);
    updateTotalTime();
    frameVer++;          // frames moved on disk — every cached frame URL is now suspect
    setEdited(true);
    show(data.current);
    refreshMarkViews();
  }}

  // ── zone, undo, loop ────────────────────────────────────────────────────
  // The ZONE is the span the playhead is inside: from the break point at or
  // before it, to the next one (or the end of the clip). With no break points
  // the zone is the whole clip, which is why Loop still does something sensible
  // before anything is marked.
  function zoneOf() {{
    const at = +slider.value;
    const ms = [...marks].sort((x, y) => x - y);
    let a = 1, b = N;
    for (const m of ms) {{
      if (m <= at) a = m;
      else {{ b = m - 1; break; }}
    }}
    return {{ a, b: Math.max(a, Math.min(b, N)), marked: ms.length > 0 }};
  }}

  // One step per edit, so Undo can walk back through them. A frame map is a
  // list of ints — the whole history of a long session is a few kB, and the
  // alternative (recomputing what an edit did in reverse) has to be right for
  // every edit type or it silently corrupts the clip.
  let HIST = [];
  async function frameMap() {{
    const r = await fetch(`/api/frames/map?slug=${{encodeURIComponent(SLUG)}}`);
    const d = await r.json();
    return d.error ? null : d.frame_map;
  }}
  async function pushHistory() {{
    const m = await frameMap();
    if (m) HIST.push(m);
    refreshUndo();
  }}
  function refreshUndo() {{
    undoBtn.disabled = HIST.length === 0;
    undoBtn.title = HIST.length
      ? `Step back through this clip's edits, one at a time. ${{HIST.length}} to undo. `
        + `Cleared when you save.`
      : `No edits to undo yet. This lights up as soon as you add or delete a frame.`;
  }}

  async function editZone(kind) {{
    const z = zoneOf();
    if (kind === 'del' && z.b - z.a + 1 >= N) {{
      editStatus.textContent = 'That zone is the whole clip — deleting it would leave nothing.';
      return;
    }}
    await pushHistory();
    const r = await fetch(`/api/frames/${{kind}}-span`, {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{slug: SLUG, a: z.a, b: z.b}})
    }});
    const data = await r.json();
    if (data.error) {{ HIST.pop(); refreshUndo(); editStatus.textContent = 'Error: ' + data.error; return; }}
    applyFrameEdit(data);
    const n = z.b - z.a + 1;
    editStatus.textContent = (kind === 'dup'
      ? `Repeated frames ${{z.a}}–${{z.b}} (${{n}} frames)`
      : `Deleted frames ${{z.a}}–${{z.b}} (${{n}} frames)`)
      + ` — now ${{N}} frames.`
      + (z.marked ? '' : ' No break points, so the zone was the whole clip.');
  }}

  addZoneBtn.addEventListener('click', () => editZone('dup'));
  delZoneBtn.addEventListener('click', () => editZone('del'));

  undoBtn.addEventListener('click', async () => {{
    if (!HIST.length) return;
    const prev = HIST.pop();
    undoBtn.disabled = true;
    const r = await fetch('/api/frames/restore', {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{slug: SLUG, frame_map: prev}})
    }});
    const data = await r.json();
    if (data.error) {{ HIST.push(prev); refreshUndo(); editStatus.textContent = 'Error: ' + data.error; return; }}
    applyFrameEdit(data);
    refreshUndo();
    editStatus.textContent = `Undone — back to ${{N}} frames.`
      + (HIST.length ? ` ${{HIST.length}} more to undo.` : ' Nothing left to undo.');
  }});

  let LOOP = false;
  loopChk.addEventListener('change', () => {{
    LOOP = loopChk.checked;
    if (!LOOP) return;
    const z = zoneOf();
    editStatus.textContent = `Looping frames ${{z.a}}–${{z.b}}`
      + (z.marked ? '.' : ' — the whole clip, since nothing is marked.');
  }});

  async function editDup(side, count) {{
    const at = +slider.value;
    await pushHistory();
    const r = await fetch('/api/frames/dup', {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{slug: SLUG, at, count, side}})
    }});
    const data = await r.json();
    if (data.error) {{ editStatus.textContent = 'Error: ' + data.error; return; }}
    applyFrameEdit(data);
    editStatus.textContent = `Duplicated frame ${{at}} x${{count}}, inserted to the ${{side}} — now ${{N}} frames, viewing frame ${{data.current}}.`;
  }}

  async function editDelete(side, count) {{
    const at = +slider.value;
    await pushHistory();
    const r = await fetch('/api/frames/del', {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{slug: SLUG, at, count, side}})
    }});
    const data = await r.json();
    if (data.error) {{ editStatus.textContent = 'Error: ' + data.error; return; }}
    if (data.actual === 0) {{ editStatus.textContent = `Nothing to the ${{side}} of frame ${{at}} — nothing deleted.`; return; }}
    applyFrameEdit(data);
    let msg = `Deleted ${{data.actual}} frame(s) to the ${{side}} of frame ${{at}} — now ${{N}} frames, viewing frame ${{data.current}}.`;
    if (data.actual < count) msg += ` (asked for ${{count}}, hit the ${{side === 'left' ? 'start' : 'end'}} of the clip.)`;
    if (data.dropped_marks > 0) msg += ` ${{data.dropped_marks}} break point(s) in the deleted range were removed.`;
    editStatus.textContent = msg;
  }}

  // ── tooltips ────────────────────────────────────────────────────────────
  // Ported from the Segment and Avatar Editor. Reads each element's own
  // `title`, so every control is covered — including the ones whose text
  // changes with state. The title is REMOVED while hovering and put back on
  // leave, or the browser's native tooltip appears underneath this one at its
  // own timing.
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
      // Placed once it is measurable, and kept on screen: a tip that runs off
      // the edge is no more use than no tip.
      const r = el.getBoundingClientRect(), t = tip.getBoundingClientRect();
      let x = r.left + r.width / 2 - t.width / 2;
      let y = r.top - t.height - 8;
      if (y < 6) y = r.bottom + 8;
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
      el.removeAttribute('title');
      timer = setTimeout(() => show(el, text), 2000);
    }});
    document.addEventListener('mouseout', e => {{
      if (held && !held.el.contains(e.relatedTarget)) hide();
    }});
    // A tip that outlives what it describes is a lie, so anything that moves or
    // changes the page takes it down.
    for (const ev of ['mousedown', 'wheel', 'keydown']) document.addEventListener(ev, hide, true);
    window.addEventListener('blur', hide);
  }})();

  // ── playback ──────────────────────────────────────────────────────────
  // Paced against the WALL CLOCK — the frame shown is computed from elapsed
  // time, never incremented per tick, so the timer's own jitter cannot
  // accumulate into drift. A drifting preview is worse than none when the
  // point is judging timing.
  //
  // A timer, not requestAnimationFrame: rAF is suspended entirely while a tab
  // is hidden, so playback would silently stall the moment you looked at
  // something else. A timer keeps running (throttled), and because the frame
  // comes from the clock it simply resumes at the right place.
  //
  // ⚠ SILENT. These are extracted frames, not the video; no audio is played.
  let playing = false, rafId = null, playT0 = 0, playF0 = 1;
  // Half speed exists to judge a seam. At 25fps a cut lands in 40ms, which is
  // too fast to see twice the same way; at 0.5x it lands in 80ms and can be
  // watched. It is a PLAYBACK rate only — it changes no frame and no file.
  let RATE = 1;
  // 2x skims a long recording; the slow rates exist to judge a seam. At 25fps a
  // cut lands in 40ms — 0.125x stretches that to 320ms, which can actually be
  // watched. PLAYBACK ONLY: no frame and no file changes at any rate.
  //
  // Browsers mute audio outside roughly 0.25x..4x, so at the two slowest rates
  // the sound would go silent WITHOUT the clip being silent. Since the audio
  // clock is also the frame clock here, a muted-but-running track is still a
  // correct clock — but a track the browser refuses to advance is not, so the
  // frame falls back to the wall clock whenever the audio is not moving.
  const AUDIO_RATE_FLOOR = 0.25;
  function playPreload(from) {{
    for (let i = from; i < from + 40 && i <= N; i++) preload(i);
  }}
  function playTick() {{
    if (!playing) return;
    // When there IS audio, the AUDIO CLOCK drives the frame. Two independent
    // clocks drift apart, and the one thing this playback exists to judge is
    // whether picture and sound agree — so there must only be one clock, and it
    // has to be the one the ear is listening to.
    // Loop Zone wraps at the zone's edges instead of the clip's. The audio is
    // wound back with it — a loop where the picture repeats and the voice
    // carries on is worse than no loop when the point is judging a cut.
    const z = LOOP ? zoneOf() : null;
    const lo = z ? z.a : 1, hi = z ? z.b : N;
    let n;
    if (HAS_AUDIO && !aud.paused) {{
      n = Math.floor(aud.currentTime * FPS) + 1;
      if (n > hi || n < lo) {{ aud.currentTime = (lo - 1) / FPS; n = lo; }}
    }} else {{
      n = playF0 + Math.floor((performance.now() - playT0) / 1000 * FPS * RATE);
    }}
    if (n > hi || n < lo) {{ playT0 = performance.now(); playF0 = lo; n = lo; }}
    show(n);
    if (n % 20 === 0) playPreload(n + 1);
  }}
  function playStop() {{
    playing = false;
    if (rafId) clearInterval(rafId);
    rafId = null;
    if (HAS_AUDIO) aud.pause();
    playBtn.textContent = '▶';
  }}
  playBtn.addEventListener('click', () => {{
    if (playing) return playStop();
    playing = true;
    const z0 = LOOP ? zoneOf() : null;
    playF0 = (+slider.value >= N) ? 1 : +slider.value;
    if (z0 && (playF0 < z0.a || playF0 > z0.b)) playF0 = z0.a;
    playT0 = performance.now();
    playBtn.textContent = '❚❚';
    playPreload(playF0);
    if (HAS_AUDIO) {{
      aud.currentTime = (playF0 - 1) / FPS;
      // The audio clock IS the frame clock when there is sound, so slowing the
      // audio slows the picture with it — no second adjustment, and therefore
      // nothing that can drift out of step with it.
      aud.playbackRate = Math.max(AUDIO_RATE_FLOOR, RATE);
      if (RATE >= AUDIO_RATE_FLOOR) aud.play().catch(() => {{}});   // a blocked autoplay must not kill playback
    }}
    // Tick faster than the frame rate so each frame lands close to its time.
    rafId = setInterval(playTick, Math.max(8, 1000 / (FPS * RATE) / 2));
  }});
  rateSel.addEventListener('change', () => {{
    RATE = parseFloat(rateSel.value);
    rateSel.classList.toggle('off1', RATE !== 1);
    // Say it out loud. Sound stopping on its own looks like a broken clip, and
    // the reason (the browser will not play a track this slow) is not guessable
    // from anything on screen.
    editStatus.textContent = (HAS_AUDIO && RATE < AUDIO_RATE_FLOOR)
      ? `Audio is off below ${{AUDIO_RATE_FLOOR}}x — the browser will not play a track that slow. The picture is still exact.`
      : '';
    if (!playing) return;
    // Mid-play the change must not jump. The silent path measures elapsed time
    // from playT0, so that origin is rebased onto the frame showing right now;
    // the audio path just takes the new rate.
    if (HAS_AUDIO) applyAudioRate();
    playF0 = +slider.value;
    playT0 = performance.now();
    clearInterval(rafId);
    rafId = setInterval(playTick, Math.max(8, 1000 / (FPS * RATE) / 2));
  }});
  // Below the floor the browser will not play the track at all, so it is paused
  // outright rather than left to drift: a stopped clock is caught by playTick,
  // a wrong one is not.
  function applyAudioRate() {{
    if (RATE < AUDIO_RATE_FLOOR) {{ aud.pause(); return; }}
    aud.playbackRate = RATE;
    if (playing && aud.paused) {{
      aud.currentTime = (+slider.value - 1) / FPS;
      aud.play().catch(() => {{}});
    }}
  }}
  muteBtn.addEventListener('click', () => {{
    aud.muted = !aud.muted;
    muteBtn.textContent = aud.muted ? '🔇' : '🔊';
  }});
  if (!HAS_AUDIO) {{
    muteBtn.disabled = true;
    muteBtn.textContent = '🔇';
    muteBtn.title = 'this clip has no audio track';
  }} else if (EDITED) {{
    // Frames have been added or removed; the audio is the ORIGINAL and no
    // longer lines up. Better to say so than to let a bad sync be believed.
    muteBtn.title = 'audio is the ORIGINAL — frames were edited, so it no longer lines up';
    muteBtn.textContent = '🔈';
  }}
  // Any manual navigation takes control back.
  for (const b of [prev, next, prev10, next10, prev100, next100])
    b.addEventListener('click', playStop, true);
  slider.addEventListener('mousedown', playStop);

  markBtn.addEventListener('click', () => {{
    mode = 'mark'; updateModeUI();
    setMark(+slider.value, !marks.has(+slider.value));
  }});
  frameEditorBtn.addEventListener('click', () => {{ mode = 'frame-editor'; updateModeUI(); }});
  addBtn.addEventListener('click', () => {{ mode = 'frame-editor'; editSub = 'add'; updateModeUI(); }});
  subtractBtn.addEventListener('click', () => {{ mode = 'frame-editor'; editSub = 'subtract'; updateModeUI(); }});
  tabMarks.addEventListener('click', () => setTab('marks'));
  tabFile.addEventListener('click', () => setTab('file'));

  clearBtn.addEventListener('click', async () => {{
    if (marks.size === 0) return;
    if (!confirm(`Remove all ${{marks.size}} break point(s)? This does not touch any segment already cut.`)) return;
    const r = await fetch('/api/clear-marks', {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{slug: SLUG}})
    }});
    const data = await r.json();
    if (data.error) {{ cutStatus.textContent = 'Error: ' + data.error; return; }}
    marks = new Set(data.marks);
    refreshMarkViews();
    cutStatus.textContent = '';
  }});

  cutBtn.addEventListener('click', async () => {{
    const label = cutBtn.textContent;
    cutBtn.disabled = true;
    cutStatus.textContent = `Cutting ${{computeSegments().length}} segment(s) from the source file — this can take a moment…`;
    try {{
      const r = await fetch('/api/cut', {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{slug: SLUG}})
      }});
      const data = await r.json();
      if (data.error) {{ cutStatus.textContent = 'Error: ' + data.error; return; }}
      let msg = `Wrote ${{data.count}} segment(s) to:\\n${{data.outdir}}\\n`;
      msg += data.segments.map(s => s.error ? `  ✕ ${{s.name}}: ${{s.error}}` :
                                       `  ${{s.name}}  ${{s.duration_s}}s` + (s.edited ? '  ✎ edited' : '') +
                                       (s.warning ? `  ⚠ ${{s.warning}}` : '')).join('\\n');
      cutStatus.textContent = msg;
      showHandoff(data);
    }} catch (e) {{
      cutStatus.textContent = 'Error: ' + e;
    }} finally {{
      cutBtn.textContent = label;
      cutBtn.disabled = marks.size === 0;
    }}
  }});

  // ── hand off to the sandbox ─────────────────────────────────────────────
  // The last step this tool was missing. A cut leaves
  // sandbox/_cuts/Num_3-v1-segment.mp4; the Segment and Avatar Editor reads
  // sandbox/03-<name>/segment.mp4 and the scene rows in script.json. Naming
  // them here is what turns loose cuts into scenes, and it is the point where
  // this tool's job ends and the editor's begins.
  let CUT_VERSION = null;

  function showHandoff(data) {{
    CUT_VERSION = data.version;
    handoffRows.innerHTML = '';
    (data.segments || []).forEach((seg, k) => {{
      if (seg.error) return;
      const row = document.createElement('div');
      row.className = 'hrow';
      const n = document.createElement('span');
      n.className = 'hn';
      n.textContent = `${{k + 1}} · ${{seg.duration_s}}s`;
      const inp = document.createElement('input');
      inp.placeholder = 'name this scene';
      inp.spellcheck = false;
      inp.dataset.k = k;
      // Typed straight into a folder name, so the rule is enforced as you type
      // rather than thrown back by the server after the naming is done.
      inp.addEventListener('input', () => {{
        inp.value = inp.value.toLowerCase().replace(/[^a-z0-9-]/g, '-')
                             .replace(/-+/g, '-').slice(0, 49);
        inp.classList.remove('bad');
        refreshHandoff();
      }});
      row.appendChild(n); row.appendChild(inp);
      handoffRows.appendChild(row);
    }});
    handoff.hidden = handoffRows.children.length === 0;
    handoffStatus.textContent = '';
    refreshHandoff();
  }}

  function handoffNames() {{
    return [...handoffRows.querySelectorAll('input')].map(i => i.value.replace(/^-|-$/g, ''));
  }}

  function refreshHandoff() {{
    const names = handoffNames();
    const filled = names.every(v => v.length > 0);
    const unique = new Set(names).size === names.length;
    handoffBtn.disabled = !filled || !unique;
    handoffBtn.textContent = !filled ? '→ Name every segment first'
                           : !unique ? '→ Two names are the same'
                           : `→ Hand off ${{names.length}} segment(s) to sandbox`;
  }}

  handoffBtn.addEventListener('click', async () => {{
    const names = handoffNames();
    // Ask the server what is in dev BEFORE asking the user, so the confirmation
    // names the real destination and the real archive rather than describing
    // them. A deposit REPLACES dev, so what is there now has to be said out loud.
    let plan = null;
    try {{
      const r = await fetch('/api/archive', {{ method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{ slug: SLUG, folder: 'dev', dry: true }})
      }});
      plan = await r.json();
    }} catch (e) {{ /* fall through to a plainer question */ }}
    const known = plan && !plan.error;
    const where = known ? plan.folder : `the video's dev/ folder`;
    if (!confirm(`Hand ${{names.length}} segment(s) over as scenes?\n\n`
               + names.map((v, i) => `  ${{String(i + 1).padStart(2, '0')}}-${{v}}`).join('\\n')
               + `\n\nWRITING TO\n${{where}}\n\n`
               + (known && !plan.empty
                  ? `dev already holds ${{plan.would_archive.length}} folder(s):\n`
                    + `  ${{plan.would_archive.join(', ')}}\n\n`
                    + `They are MOVED here first, with the script that named them:\n`
                    + `${{plan.into}}\n\n`
                    + `dev then holds only this cut.`
                  : known
                    ? `dev is empty, so nothing is archived first.`
                    : `Could not read what is in dev — it will be archived if anything is.`)
               + `\n\nThe cuts stay in _cuts/ either way.`)) return;
    handoffBtn.disabled = true;
    handoffStatus.textContent = 'Handing off…';
    try {{
      const r = await fetch('/api/handoff', {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{slug: SLUG, version: CUT_VERSION, names}})
      }});
      const data = await r.json();
      if (data.error) {{ handoffStatus.textContent = 'Error: ' + data.error; refreshHandoff(); return; }}
      handoffStatus.textContent =
        `Handed off ${{data.handed_off.length}} scene(s):\n`
        + data.handed_off.map(x => `  ${{x.folder}}  ${{x.frames}} frames`).join('\\n')
        + `\n\nThe store now has ${{data.scenes}} scene(s). Open it in the `
        + `Segment and Avatar Editor to write the lines and add the avatar.`;
      handoffBtn.textContent = '✓ Handed off';
    }} catch (e) {{
      handoffStatus.textContent = 'Error: ' + e;
      refreshHandoff();
    }}
  }});

  saveBtn.addEventListener('click', async () => {{
    const slash = SOURCE_PATH.lastIndexOf('/');
    const folder = SOURCE_PATH.substring(0, slash);
    const file = SOURCE_PATH.substring(slash + 1);
    const ok = confirm(
      `Save this edited clip — ${{N}} frames, ${{(N / FPS).toFixed(3)}}s?\n\n` +
      `This OVERWRITES the original file. The current version is archived ` +
      `to z_History/ first, but this is not reversible from here.\n\n` +
      `Folder:\n${{folder}}\n\nFile:\n${{file}}`
    );
    if (!ok) return;
    saveBtn.disabled = true;
    editStatus.textContent = 'Saving — rebuilding the edited clip from the source file…';
    try {{
      const r = await fetch('/api/save', {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{slug: SLUG}})
      }});
      const data = await r.json();
      if (data.error) {{ editStatus.textContent = 'Error: ' + data.error; saveBtn.disabled = false; return; }}
      // The server has re-extracted this cache from the file it just wrote,
      // so the frames, frame_map and edited flag this page is holding are all
      // stale — reload rather than patch them one by one. The receipt has to
      // outlive the reload, or a landed save would leave no trace on screen
      // and read as if nothing happened.
      // The server compares what it WROTE against what was asked for. Ignoring
      // that warning is how Save lost a frame per cut for three weeks with
      // nothing on screen saying so.
      HIST = [];                 // the saved file is the new baseline
      if (data.warning) alert('Save finished, but the frame count is wrong:\\n\\n'
                            + data.warning
                            + '\\n\\nCheck the file before you cut from it.');
      sessionStorage.setItem('videoEditorSaved',
        `Saved ${{data.duration_s}}s (${{data.nb_frames}} frames) to:\n${{data.path}}\n\nPrevious version archived to:\n${{data.archived_to}}`);
      location.reload();
      return;
    }} catch (e) {{
      editStatus.textContent = 'Error: ' + e;
    }} finally {{
      saveBtn.disabled = !hasEdits;
    }}
  }});

  clearEditsBtn.addEventListener('click', async () => {{
    HIST = [];
    const ok = confirm(
      `Clear all edits?\n\n` +
      `This discards every Frame Editor edit and every break point in THIS ` +
      `PREVIEW ONLY, and re-extracts fresh frames straight from the source. ` +
      `The source file on disk is never touched — this cannot affect it. ` +
      `The video stays loaded.\n\n` +
      `Not reversible from here.`
    );
    if (!ok) return;
    clearEditsBtn.disabled = true;
    editStatus.textContent = 'Clearing edits — re-extracting frames from the source…';
    try {{
      const r = await fetch('/api/clear-edits', {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{slug: SLUG}})
      }});
      const data = await r.json();
      if (data.error) {{ editStatus.textContent = 'Error: ' + data.error; clearEditsBtn.disabled = false; return; }}
      location.reload();
    }} catch (e) {{
      editStatus.textContent = 'Error: ' + e;
      clearEditsBtn.disabled = false;
    }}
  }});

  resetEditorBtn.addEventListener('click', async () => {{
    HIST = [];
    const ok = confirm(
      `Reset the editor?\n\n` +
      `This deletes EVERYTHING this tool has for this video — every ` +
      `frame, every edit, every break point. It cannot be undone from here.\n\n` +
      `The original video FILE on your disk is NOT deleted — reopen it from ` +
      `Browse any time to start over.\n\n` +
      `This will take you back to Browse.`
    );
    if (!ok) return;
    resetEditorBtn.disabled = true;
    editStatus.textContent = 'Resetting the editor — deleting this video\\'s cache…';
    try {{
      const r = await fetch('/api/reset-editor', {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{slug: SLUG}})
      }});
      const data = await r.json();
      if (data.error) {{ editStatus.textContent = 'Error: ' + data.error; resetEditorBtn.disabled = false; return; }}
      // replace(), not href= — this page's cache is gone server-side, so it
      // must not be a page Back can return to. href= leaves a history entry
      // that Chrome's bfcache can serve straight from memory, showing this
      // exact pre-delete DOM/state as if nothing happened.
      location.replace('../browse.html');
    }} catch (e) {{
      editStatus.textContent = 'Error: ' + e;
      resetEditorBtn.disabled = false;
    }}
  }});

  slider.addEventListener('input', () => show(+slider.value));
  // In Frame Editor mode these six buttons stop navigating and start
  // editing the preview cache; the slider itself still just moves the
  // playhead either way, so it's how you position yourself before a cut.
  // Left button always acts on the left, right always on the right — WHAT it
  // does (duplicate vs delete) comes from editSub, independent of side.
  function leftClick(count) {{ editSub === 'add' ? editDup('left', count) : editDelete('left', count); }}
  function rightClick(count) {{ editSub === 'add' ? editDup('right', count) : editDelete('right', count); }}
  prev.addEventListener('click', () => mode === 'frame-editor' ? leftClick(1) : step(-1));
  next.addEventListener('click', () => mode === 'frame-editor' ? rightClick(1) : step(1));
  prev10.addEventListener('click', () => mode === 'frame-editor' ? leftClick(10) : step(-10));
  next10.addEventListener('click', () => mode === 'frame-editor' ? rightClick(10) : step(10));
  prev100.addEventListener('click', () => mode === 'frame-editor' ? leftClick(100) : step(-100));
  next100.addEventListener('click', () => mode === 'frame-editor' ? rightClick(100) : step(100));
  // Keyboard arrows stay navigation-only in every mode, on purpose — muscle
  // memory reaching for the left/right keys should never delete or
  // duplicate a frame. Only the buttons themselves edit.
  document.addEventListener('keydown', (e) => {{
    // Three speeds on one pair of keys, cheapest gesture for the commonest job:
    //   ←/→          one frame   — the frame-accurate work this tool exists for
    //   Shift+←/→    ten frames  — coarse scrubbing
    //   Alt+←/→      break point — walking the cut to check every boundary
    // Alt is checked FIRST: without that, Alt+← would step a frame as well and
    // land one frame off the mark, which is the exact error being checked for.
    if (e.key === 'ArrowLeft') {{
      if (e.altKey) jumpMark(-1); else step(e.shiftKey ? -10 : -1);
      e.preventDefault();
    }}
    if (e.key === 'ArrowRight') {{
      if (e.altKey) jumpMark(1); else step(e.shiftKey ? 10 : 1);
      e.preventDefault();
    }}
    if (e.key === ' ') {{ playBtn.click(); e.preventDefault(); }}
    if (e.key === 'm' || e.key === 'M') {{ const n = +slider.value; setMark(n, !marks.has(n)); e.preventDefault(); }}
    // Walk the break points themselves. Checking a cut means visiting every
    // boundary in turn to confirm it landed on the FIRST frame of the new
    // page; without this that is a manual scrub through thousands of frames.
    if (e.key === '[') {{ jumpMark(-1); e.preventDefault(); }}
    if (e.key === ']') {{ jumpMark(1); e.preventDefault(); }}
  }});
  // The "does this label fit?" test is measured in pixels, so it has to be
  // re-run whenever the bar's width changes.
  window.addEventListener('resize', renderSegments);

  setTab('marks');
  updateModeUI();
  updateTotalTime();
  setEdited(hasEdits);
  const savedMsg = sessionStorage.getItem('videoEditorSaved');
  if (savedMsg) {{ sessionStorage.removeItem('videoEditorSaved'); editStatus.textContent = savedMsg; }}
  show(1);
  renderSegments();
  renderMarksList();
  loadMarks();
  refreshUndo();
</script>
</body></html>
"""

if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# PAIR VIEWER — an mp4 running underneath, an alpha WebM layered on top
# ---------------------------------------------------------------------------
#
# Added 2026-08-21. The two tracks of a help video were only ever reviewable
# after a full assemble, which is minutes per look — and the faults that matter
# are exactly the ones that only exist in the COMBINATION: a mouth moving with
# no audio behind it, a background that is the wrong screen, an avatar landing
# a few pixels off. Layering them here makes those a glance instead of a build.
#
# The layering is done in the BROWSER, not by compositing frames on disk: the
# base stays JPEG, the overlay is PNG with its real alpha, and two <img> sit on
# top of each other. That keeps each clip independently editable — one frame_map
# each, one set of break points each — which compositing to disk would destroy.
#
# Geometry mirrors what assemble_video.py does: the base is scaled to the canvas
# WIDTH and centred vertically inside a square, and the overlay covers that
# square exactly. So what is previewed is the real arrangement, not an
# approximation.

