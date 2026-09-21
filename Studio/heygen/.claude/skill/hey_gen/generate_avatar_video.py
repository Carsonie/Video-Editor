#!/usr/bin/env python3
"""generate_avatar_video.py — create ONE HeyGen avatar video, poll, download.

Uses the CURRENT v3 endpoint POST /v3/videos (verbatim "Video Generation",
NOT the Video Agent — so the avatar speaks your script exactly, no AI rewriting).

Flow:
  1. POST /v3/videos            -> returns { data: { video_id } }
  2. GET  /v3/videos/{id}       -> poll until status completed|failed
  3. download video_url         -> local file

Reads HEYGEN_API_KEY from env or .env.local (walks up from cwd).

USAGE (intro, full-screen, solid light-blue background -> mp4):
  python3 generate_avatar_video.py \
      --avatar 468eabb3326a4d8587ba29d065b1eba7 \
      --voice 04d0ae1d0af2489ca7d3bb402a39a890 \
      --script "Hi, I'm Sarah. Learn how to place your first equipment rental order." \
      --bg "#E8F4F8" \
      --out videos/<slug>/temp/first-time-ordering-intro.mp4

USAGE (corner, transparent webm -> no bg, matting required):
  python3 generate_avatar_video.py \
      --avatar 468eabb3326a4d8587ba29d065b1eba7 \
      --voice 04d0ae1d0af2489ca7d3bb402a39a890 \
      --script "Let me show you how. Here are the steps to complete your first rental." \
      --webm \
      --out videos/<slug>/temp/first-time-ordering-corner.webm

Options:
  --aspect 16:9 (default) | 9:16 | 4:5 | 5:4 | 1:1 | auto
  --engine avatar_v   (optional; omit to let HeyGen default to Avatar IV)
  --bg "#RRGGBB"      solid background color (mp4 only)
  --webm              transparent output (ignores --bg; needs matting avatar)
  --dry-run           print the request body and exit WITHOUT generating
"""
import json, subprocess, os, sys, time, urllib.request, argparse

API = "https://api.heygen.com"


def load_key():
    k = os.environ.get("HEYGEN_API_KEY")
    if k:
        return k
    here = os.getcwd()
    for _ in range(6):
        p = os.path.join(here, ".env.local")
        if os.path.exists(p):
            for line in open(p):
                line = line.strip()
                if line.startswith("HEYGEN_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        here = os.path.dirname(here)
    return None


KEY = load_key()
if not KEY:
    sys.exit("HEYGEN_API_KEY not found in env or any parent .env.local")


def curl_json(method, path, body=None):
    cmd = ["curl", "-s", "--max-time", "60", "-X", method,
           "-H", f"x-api-key: {KEY}", "-H", "Content-Type: application/json",
           API + path]
    if body is not None:
        cmd += ["-d", json.dumps(body)]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    try:
        return json.loads(out)
    except Exception:
        print("Non-JSON response:", out[:400])
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--avatar", required=True)
    ap.add_argument("--voice", required=True)
    ap.add_argument("--script", required=True)
    ap.add_argument("--aspect", default="16:9")
    ap.add_argument("--engine", default=None)
    ap.add_argument("--bg", default=None)
    ap.add_argument("--webm", action="store_true")
    ap.add_argument("--out", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    body = {
        "type": "avatar",
        "avatar_id": a.avatar,
        "voice_id": a.voice,
        "script": a.script,
        "aspect_ratio": a.aspect,
        "output_format": "webm" if a.webm else "mp4",
    }
    if a.engine:
        body["engine"] = {"type": a.engine}
    if a.webm:
        # webm rejects background; transparency is automatic
        pass
    elif a.bg:
        body["background"] = {"type": "color", "value": a.bg}

    print("Request body:")
    print(json.dumps(body, indent=2))
    if a.dry_run:
        print("\n[dry-run] not submitting.")
        return

    print("\nSubmitting to POST /v3/videos ...")
    resp = curl_json("POST", "/v3/videos", body)
    if not resp:
        sys.exit("No/invalid response from create call.")
    if resp.get("error"):
        sys.exit(f"API error: {resp['error']}")
    data = resp.get("data", {})
    video_id = data.get("video_id") or data.get("id")
    if not video_id:
        sys.exit(f"No video_id in response: {json.dumps(resp)[:400]}")
    print("video_id:", video_id)

    # poll
    print("Polling status (most videos finish in 1-5 min)...")
    url = None
    for i in range(120):  # up to ~20 min at 10s
        time.sleep(10)
        s = curl_json("GET", f"/v3/videos/{video_id}")
        if not s:
            print("  (poll: no response, retrying)")
            continue
        d = s.get("data", {})
        status = d.get("status")
        print(f"  [{i*10+10}s] status={status}")
        if status == "completed":
            url = d.get("video_url")
            break
        if status == "failed":
            sys.exit(f"FAILED: {d.get('failure_code')} - {d.get('failure_message')}")
    if not url:
        sys.exit("Timed out waiting for video.")

    # download
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    print("Downloading ->", a.out)
    urllib.request.urlretrieve(url, a.out)
    print("Done:", a.out)


if __name__ == "__main__":
    main()
