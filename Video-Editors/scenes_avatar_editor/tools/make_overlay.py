#!/usr/bin/env python3
"""
Build a transparent note card to lay over a scene's frames.

    python3 make_overlay.py                        # rebuild back-to-dashboard.png
    python3 make_overlay.py --preview <clip.mp4> --frame 214
    python3 make_overlay.py --head "Back to the Store" --keys "Mac:  Command + J" \
                            --keys "Windows:  Control + J" --out back-to-store.png

Carson, 2026-09-21: *"Now I add a folder in BCP_raw called TOOLS. Add this image
overlay there and we will use it various locations."*

WHY THE SCRIPT AND NOT ONLY THE PNG
-----------------------------------
The PNG is the thing that gets overlaid, and for the same wording it is all you
need. This exists so the NEXT note does not start from a blank canvas: the card
geometry, the colours, the fonts and the two-line key layout are settled here,
so a new note is one --head and two --keys away and still looks like the others.

⚠ THE CARD IS FULL FRAME, NOT A CROP. It is written at the clip's own size with
everything outside the card transparent, so ffmpeg takes `overlay=0:0` and the
card lands dead centre with no arithmetic. A cropped card would need an x and a
y at every call site, and a wrong one is only visible by eye.

    ffmpeg -i segment.mp4 -i back-to-dashboard.png \
      -filter_complex "[0][1]overlay=0:0:enable='eq(n,213)'[v]" \
      -map "[v]" -map "0:a" -c:v libx264 -crf 16 -preset medium \
      -pix_fmt yuv420p -c:a copy -fps_mode cfr out.mp4

⚠ THE SIZE MUST MATCH THE CLIP. Every special-skis scene is 2304x1926. A clip of
another size needs --w/--h, or the card sits in a corner at the wrong scale.

See NOTE.md in this folder for the whole procedure, including the backup and the
sync that a real edit needs either side of the ffmpeg call.
"""
import argparse
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))

# ── THE LOOK, AND WHERE EACH VALUE CAME FROM ─────────────────────────────────
# Carson picked the colour twice: the first card was yellow #FFC72C and his
# answer was "the yellow is too bold, lets try green". This green reads clean on
# the app's near-black panels without shouting. The card's edge is the app's own
# button blue, so the note looks like part of the product rather than a sticker.
GREEN = (111, 207, 151, 255)          # #6FCF97  the keys
WHITE = (255, 255, 255, 255)          # the heading
GREY = (168, 170, 176, 255)           # the footnote
RULE = (70, 72, 78, 255)              # the hairline under the heading
FILL = (24, 24, 26, 240)              # the card itself, near-opaque
EDGE = (31, 111, 178, 255)            # #1F6FB2  the Update button's blue

BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
REG = "/System/Library/Fonts/Supplemental/Arial.ttf"

# ⚠ 74, NOT 76. Carson, 2026-09-21: "reduce the font size by 2 pts in 'Back to
# the dashboard'". Keep this and the key size apart — the heading is meant to sit
# just above the keys, not match them.
HEAD_PT = 74
KEY_PT = 72
FOOT_PT = 46

# ⚠ ARIAL HAS NO COMMAND GLYPH. The first build set U+2318 and it rendered as an
# empty box in every font on this Mac. The word is also plainer for a viewer who
# has never seen the symbol, so the note spells it out. Do not "fix" this back.
DEFAULT_HEAD = "Back to the Dashboard"
DEFAULT_KEYS = ["Mac:  Command + K", "Windows:  Control + K"]
DEFAULT_FOOT = "works from any page"


def build(w, h, head, keys, foot, cw=1500, ch=560):
    """One transparent full-frame layer with the card centred in it."""
    card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    x0, y0 = (w - cw) // 2, (h - ch) // 2
    d.rounded_rectangle([x0, y0, x0 + cw, y0 + ch], radius=30,
                        fill=FILL, outline=EDGE, width=5)

    f_head = ImageFont.truetype(BOLD, HEAD_PT)
    f_key = ImageFont.truetype(BOLD, KEY_PT)
    f_foot = ImageFont.truetype(REG, FOOT_PT)

    def mid(text, font, y, fill):
        tw = d.textbbox((0, 0), text, font=font)[2]
        d.text(((w - tw) // 2, y), text, font=font, fill=fill)

    mid(head, f_head, y0 + 55, WHITE)
    d.line([x0 + 300, y0 + 170, x0 + cw - 300, y0 + 170], fill=RULE, width=3)
    for i, line in enumerate(keys[:2]):
        mid(line, f_key, y0 + 208 + i * 100, GREEN)
    if foot:
        mid(foot, f_foot, y0 + 430, GREY)
    return card


def frame_of(clip, n):
    """One frame out of a clip as an image — n is 1-based, the way the SAE counts."""
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", clip,
                        "-vf", f"select='eq(n\\,{n - 1})'", "-vsync", "0",
                        "-frames:v", "1", "-f", "image2pipe",
                        "-vcodec", "png", "-"], capture_output=True)
    if not p.stdout:
        sys.exit(f"could not read frame {n} of {clip}\n{p.stderr.decode()[-400:]}")
    import io
    return Image.open(io.BytesIO(p.stdout)).convert("RGB")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="back-to-dashboard.png")
    ap.add_argument("--head", default=DEFAULT_HEAD)
    ap.add_argument("--keys", action="append", help="one key line, give it twice")
    ap.add_argument("--foot", default=DEFAULT_FOOT)
    ap.add_argument("--w", type=int, default=2304, help="the CLIP's width")
    ap.add_argument("--h", type=int, default=1926, help="the CLIP's height")
    ap.add_argument("--preview", help="a clip to composite onto, to look before burning")
    ap.add_argument("--frame", type=int, default=0, help="which frame to preview, 1-based")
    a = ap.parse_args()

    keys = a.keys or DEFAULT_KEYS
    card = build(a.w, a.h, a.head, keys, a.foot)
    out = a.out if os.path.isabs(a.out) else os.path.join(HERE, a.out)
    card.save(out)
    print(f"  card   {a.w}x{a.h}  transparent, card centred  ->  {out}")

    if a.preview:
        n = a.frame or 1
        base = frame_of(a.preview, n)
        if base.size != (a.w, a.h):
            sys.exit(f"the clip is {base.size[0]}x{base.size[1]} but the card is "
                     f"{a.w}x{a.h} — pass --w/--h to match the clip")
        shot = out.replace(".png", f"_on_frame{n}.png")
        Image.alpha_composite(base.convert("RGBA"), card).convert("RGB").save(shot)
        print(f"  look   frame {n} of {os.path.basename(a.preview)}  ->  {shot}")


if __name__ == "__main__":
    main()
