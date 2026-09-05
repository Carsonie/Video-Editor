// Package editor is the Go port of the Python video-editor server —
// shared/serve.py, shared/frames.py and shared/paths.py, one for one.
//
// # THE RULES THIS FILE EXISTS TO KEEP
//
// Every ffmpeg and ffprobe flag here was paid for with a real defect. None of
// them are stylistic:
//
//   - `-frames:v N`, NEVER `-t seconds`. A duration cutoff drops the frame
//     that lands exactly on the boundary. Asking for 30 frames at 25fps
//     returned 29; an edited clip lost one frame per cut, so an 89-frame
//     preview wrote 87 — for three weeks, with a zero exit code and a
//     playable file.
//   - An alpha WebM MUST be decoded with `-c:v libvpx-vp9` given BEFORE the
//     input. Without it ffmpeg picks a decoder that silently drops the alpha
//     and still reports success.
//   - VP9 carries NO frame count in its container. Count decoded frames.
//   - `format=yuva420p` belongs in the FILTER CHAIN. `-pix_fmt yuva420p` on
//     the output is not enough: the encoder happily writes an alpha plane
//     that is 100% opaque, so the file reports the right pixel format and is
//     solid black.
package editor

import (
	"fmt"
	"math"
	"os/exec"
	"strconv"
	"strings"
)

// ENCODE — must match cut_segments.py exactly. `-crf 18` is explicit: x264
// defaults to 23, which measures fine but this footage is small UI TEXT on
// flat dark panels, where the usual metrics flatter a soft result.
var ENCODE = []string{"-c:v", "libx264", "-crf", "18", "-c:a", "aac",
	"-pix_fmt", "yuv420p", "-movflags", "+faststart"}

// ENCODE_ALPHA — H.264 CANNOT carry an alpha channel. Cutting an avatar
// through ENCODE produced Sarah on a black rectangle, silently, because the
// alpha was already gone at the decode step.
//
//	-auto-alt-ref 0   alt-ref frames are what drop alpha in libvpx-vp9
//	-b:v 2M           matches make_scene_overlays.py, so a cut clip and a
//	                  composited one are the same picture
var ENCODE_ALPHA = []string{"-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
	"-auto-alt-ref", "0", "-b:v", "2M", "-c:a", "libopus"}

var vp9Decoder = []string{"-c:v", "libvpx-vp9"}

// IsAlpha — a `.webm` here always means a transparent avatar render. That is
// the only kind this pipeline produces or consumes.
func IsAlpha(path string) bool {
	return strings.HasSuffix(strings.ToLower(path), ".webm")
}

// DecFor is the decoder to force, BEFORE `-i`.
func DecFor(path string) []string {
	if IsAlpha(path) {
		return vp9Decoder
	}
	return nil
}

func encFor(path string) []string {
	if IsAlpha(path) {
		return ENCODE_ALPHA
	}
	return ENCODE
}

func extFor(path string) string {
	if IsAlpha(path) {
		return ".webm"
	}
	return ".mp4"
}

// run is every ffmpeg/ffprobe call in this package. Returns stdout, stderr and
// the error, because a non-zero exit with useful stderr is the normal way
// these tools say what went wrong.
func run(name string, args ...string) (string, string, error) {
	cmd := exec.Command(name, args...)
	var out, errb strings.Builder
	cmd.Stdout = &out
	cmd.Stderr = &errb
	err := cmd.Run()
	return strings.TrimSpace(out.String()), errb.String(), err
}

func tail(s string, n int) string {
	s = strings.TrimSpace(s)
	if len(s) > n {
		return s[len(s)-n:]
	}
	return s
}

// Probe reads one ffprobe entry. `stream` selects the video stream's entries
// rather than the container's; `dec` forces a decoder and must be given before
// the input or an alpha WebM comes back as yuv420p.
func Probe(path, entry string, stream bool, dec []string) (string, error) {
	args := []string{"-v", "error"}
	if stream {
		args = append(args, "-select_streams", "v")
	}
	args = append(args, dec...)
	prefix := "format="
	if stream {
		prefix = "stream="
	}
	args = append(args, "-show_entries", prefix+entry, "-of", "csv=p=0", path)
	out, errs, err := run("ffprobe", args...)
	if err != nil {
		return "", fmt.Errorf("ffprobe failed on %s:\n%s", path, errs)
	}
	return out, nil
}

func probeFloat(path, entry string, stream bool, dec []string) (float64, error) {
	s, err := Probe(path, entry, stream, dec)
	if err != nil {
		return 0, err
	}
	// ffprobe answers a multi-stream file with one value per line.
	s = strings.TrimSpace(strings.Split(s, "\n")[0])
	return strconv.ParseFloat(s, 64)
}

func probeInt(path, entry string, stream bool, dec []string) (int, error) {
	f, err := probeFloat(path, entry, stream, dec)
	return int(f), err
}

// probeRate turns ffprobe's `25/1` into 25.0.
func probeRate(path string, dec []string) (float64, error) {
	s, err := Probe(path, "r_frame_rate", true, dec)
	if err != nil {
		return 0, err
	}
	s = strings.TrimSpace(strings.Split(s, "\n")[0])
	num, den, ok := strings.Cut(s, "/")
	n, err := strconv.ParseFloat(strings.TrimSpace(num), 64)
	if err != nil {
		return 0, err
	}
	if !ok || strings.TrimSpace(den) == "" {
		return n, nil
	}
	d, err := strconv.ParseFloat(strings.TrimSpace(den), 64)
	if err != nil || d == 0 {
		return n, nil
	}
	return n / d, nil
}

// DecodedFrames is how many frames a file really decodes. It decodes the whole
// stream, so it is slow — used only where the header cannot be trusted (every
// VP9 clip) or where an output has to be checked against an exact count.
// Returns -1 when ffprobe cannot say.
func DecodedFrames(path string, dec []string) int {
	args := append([]string{"-v", "error"}, dec...)
	args = append(args, "-select_streams", "v", "-count_frames",
		"-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", path)
	out, _, err := run("ffprobe", args...)
	if err != nil {
		return -1
	}
	out = strings.TrimSpace(strings.Split(out, "\n")[0])
	n, err := strconv.Atoi(out)
	if err != nil {
		return -1
	}
	return n
}

// hasAudioStream — whether this file carries any audio at all.
func hasAudioStream(path string) bool {
	out, _, _ := run("ffprobe", "-v", "error", "-select_streams", "a",
		"-show_entries", "stream=codec_type", "-of", "csv=p=0", path)
	return strings.TrimSpace(out) != ""
}

// pyFloat renders a float the way Python's str() does, so a page generated
// here is byte-comparable with one generated by the Python player: an integral
// value keeps its `.0`, which Go's default formatting drops.
func pyFloat(f float64) string {
	if f == math.Trunc(f) && math.Abs(f) < 1e16 {
		return strconv.FormatFloat(f, 'f', 1, 64)
	}
	return strconv.FormatFloat(f, 'g', -1, 64)
}

// fmtG matches Python's `{:g}` — used inside ffmpeg filter strings, where
// `fps=25` is wanted and `fps=25.000000` is noise.
func fmtG(f float64) string {
	return strconv.FormatFloat(f, 'g', -1, 64)
}
