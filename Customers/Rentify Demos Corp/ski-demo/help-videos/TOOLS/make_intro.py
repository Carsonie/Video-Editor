#!/usr/bin/env python3
"""
The INTRO frame — a full-frame title card to hold at the front of a video.

    python3 make_intro.py                         # rebuild intro-special-skis.png
    python3 make_intro.py --from-script "<recipe folder>"
    python3 make_intro.py --title "Adding a Collection|with Variants" \
                          --sub "Special Skis" --step "Sign in" --step "..." \
                          --out intro-special-skis.png

Carson, 2026-09-21: *"I need an intro to this. I want a set of duplicated images
to intro the video. I want it in the same style as our current layover image, but
in a full frame size."*

⚠ FULL FRAME, NOT A CARD ON A PAGE. `back-to-dashboard.png` is a transparent
layer with a small card in the middle, laid over real footage. This is the
opposite: the whole frame IS the design, it is opaque, and nothing shows through.
So it is not overlaid — it is held as its OWN frames at the front of the film.

    HOW IT GETS INTO THE VIDEO (the outline; NOTE.md has the real procedure)
    1. encode this PNG as N frames of silent video at the clip's own fps
    2. it becomes its own scene folder, sandbox/00-intro/segment.mp4
    3. a bookend scene has no row in script.json and no voice, which the SAE
       already understands — see api_open_seq's `in_script` flag

⚠ THE STYLE IS BORROWED, NOT REINVENTED. Every colour and face here is the same
as make_overlay.py's, so the intro and the in-video notes look like one set:
near-black ground, the app's own button blue for rules, `#6FCF97` green for the
things a viewer should read, Arial Bold. If one changes, change both.

⚠ NO TIMES ON THE STEP LIST. `chapters.txt` still carries 0:00 / 0:14 / 0:52 /
1:58 / 3:14 / 5:51, which were measured off the 375.88s cut. The film is 281.46s
now, so every one of those is wrong. The steps are listed in order with no
timestamps, which cannot go stale.
"""
import argparse
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))

# ── THE SHARED PALETTE — keep in step with make_overlay.py ───────────────────
GROUND = (24, 24, 26, 255)        # #18181A  the card fill, now the whole frame
GREEN = (111, 207, 151, 255)      # #6FCF97  Carson's pick over yellow
WHITE = (255, 255, 255, 255)
GREY = (168, 170, 176, 255)
DIM = (112, 114, 120, 255)
BLUE = (31, 111, 178, 255)        # #1F6FB2  the app's Update-button blue
RULE = (70, 72, 78, 255)

BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
REG = "/System/Library/Fonts/Supplemental/Arial.ttf"

DEFAULTS = dict(
    eyebrow="RENTIFY   ·   BUSINESS CONTROL PANEL",
    title=["Adding a Collection", "with Variants"],
    sub="Special Skis",
    # ⚠ CARSON'S OWN WORDING, 2026-09-21. These are NOT the chapter titles in
    # `vtt script.txt` any more — he reworded 2 through 5 after seeing the frame.
    # Do not "tidy" them back into the shorter chapter names.
    steps=["Sign in",
           "Find your store",
           "Creating a new variant collection",
           "Adding the first item",
           "Duplicating items for building the variants",
           "Sign out"],
    foot="Ski Demo — Blue Mountain",
)


def spaced(d, text, font, x, y, fill, extra=14):
    """
    Letter-spaced text. PIL has no tracking, so the eyebrow is drawn a character
    at a time — an all-caps label set solid reads as a word, not as a label.
    """
    for ch in text:
        d.text((x, y), ch, font=font, fill=fill)
        x += d.textlength(ch, font=font) + extra
    return x


def spaced_width(d, text, font, extra=14):
    return sum(d.textlength(c, font=font) + extra for c in text) - extra


def build(w, h, eyebrow, title, sub, steps, foot):
    """
    One opaque full frame.

    ⚠ IT IS LAID OUT TOP TO BOTTOM AND THEN CHECKED, NOT EYEBALLED. The first
    build put the footer at a fixed `h - 300` while the step list grew downward
    from a fixed start, so on a 1926-tall frame the footer landed ON TOP of
    steps 5 and 6 — two lines of text in the same place, which a thumbnail hides
    and a viewer sees immediately. Now every block advances one cursor, the
    footer follows the list, and the whole stack is centred in what is left.
    A layout that cannot fit RAISES rather than overlapping.
    """
    im = Image.new("RGB", (w, h), GROUND[:3])
    d = ImageDraw.Draw(im)

    pad = 84
    d.rounded_rectangle([pad, pad, w - pad, h - pad], radius=34,
                        outline=BLUE, width=5)

    f_eye = ImageFont.truetype(BOLD, 40)
    f_title = ImageFont.truetype(BOLD, 146)
    f_sub = ImageFont.truetype(BOLD, 94)
    f_lab = ImageFont.truetype(BOLD, 42)
    f_step = ImageFont.truetype(BOLD, 66)
    f_foot = ImageFont.truetype(REG, 46)
    f_tiny = ImageFont.truetype(REG, 34)

    # ── the stack, as (advance, draw) pairs. Nothing draws until the height is
    #    known, so the whole thing can be centred and checked first.
    EYE, T_LINE, T_GAP, SUB, SUB_GAP = 104, 168, 22, 148, 64
    RULE_GAP, LAB, LAB_GAP, STEP = 72, 100, 0, 96
    FOOT_GAP, FOOT, TINY = 104, 74, 48

    tall = (EYE + T_LINE * len(title) + T_GAP + SUB + SUB_GAP + RULE_GAP
            + LAB + LAB_GAP + STEP * len(steps) + FOOT_GAP + FOOT + TINY)
    room = h - 2 * pad - 60
    if tall > room:
        raise ValueError(f"the intro needs {tall}px but only {room}px fits — "
                         f"drop a step, shorten the title, or lower the sizes")
    y = pad + 30 + (room - tall) // 2

    def mid(text, font, yy, fill):
        d.text(((w - d.textlength(text, font=font)) / 2, yy), text, font=font, fill=fill)

    spaced(d, eyebrow, f_eye, (w - spaced_width(d, eyebrow, f_eye)) / 2, y, DIM)
    y += EYE
    for line in title:
        mid(line, f_title, y, WHITE)
        y += T_LINE
    y += T_GAP
    mid(sub, f_sub, y, GREEN)
    y += SUB + SUB_GAP

    d.line([w * 0.32, y, w * 0.68, y], fill=BLUE, width=5)
    y += RULE_GAP

    lab = "WHAT THIS COVERS"
    spaced(d, lab, f_lab, (w - spaced_width(d, lab, f_lab, 12)) / 2, y, DIM, extra=12)
    y += LAB + LAB_GAP

    # ⚠ THE LIST IS LEFT-ALIGNED AS A BLOCK, NOT CENTRED LINE BY LINE. Six
    # centred lines of different lengths read as a ragged pile; one left edge
    # reads as a list. The block itself is centred on the frame.
    widest = max(d.textlength(s, font=f_step) for s in steps)
    x_num = (w - (88 + widest)) / 2
    for i, step in enumerate(steps, 1):
        d.text((x_num, y), f"{i}", font=f_step, fill=GREEN)
        d.text((x_num + 88, y), step, font=f_step, fill=WHITE)
        y += STEP

    y += FOOT_GAP
    mid(foot, f_foot, y, GREY)
    y += FOOT
    mid("powered by rentify.app", f_tiny, y, DIM)
    return im


def from_script(folder):
    """Title and store straight off script.json, so the frame cannot disagree."""
    p = os.path.join(folder, "script.json")
    if not os.path.isfile(p):
        sys.exit(f"no script.json in {folder}")
    s = json.load(open(p))
    title = s.get("title") or ""
    # "Adding a collection with variants — Special Skis" -> title | sub
    head, _, sub = title.partition("—")
    return head.strip(), sub.strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="intro-special-skis.png")
    ap.add_argument("--w", type=int, default=2304, help="the CLIP's width")
    ap.add_argument("--h", type=int, default=1926, help="the CLIP's height")
    ap.add_argument("--eyebrow", default=DEFAULTS["eyebrow"])
    ap.add_argument("--title", help="one string, split the lines with |")
    ap.add_argument("--sub", default=DEFAULTS["sub"])
    ap.add_argument("--step", action="append", help="one step, give it once each")
    ap.add_argument("--foot", default=DEFAULTS["foot"])
    ap.add_argument("--from-script", help="take the title and sub off a recipe's script.json")
    a = ap.parse_args()

    title = [x.strip() for x in a.title.split("|")] if a.title else DEFAULTS["title"]
    sub = a.sub
    if a.from_script:
        head, s = from_script(a.from_script)
        if head:
            # two lines, broken on the last space before the middle
            words = head.split()
            cut = max(1, len(words) // 2)
            title = [" ".join(words[:cut]).strip(), " ".join(words[cut:]).strip()]
        if s:
            sub = s

    im = build(a.w, a.h, a.eyebrow, title, sub, a.step or DEFAULTS["steps"], a.foot)
    out = a.out if os.path.isabs(a.out) else os.path.join(HERE, a.out)
    im.save(out)
    print(f"  intro  {a.w}x{a.h}  opaque, full frame  ->  {out}")


if __name__ == "__main__":
    main()
