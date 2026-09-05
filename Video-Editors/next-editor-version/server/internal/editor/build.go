package editor

// Rebuilding real files from a frame map, and the folder rules around where
// the results land.

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
)

// ── marks ───────────────────────────────────────────────────────────────────

func marksPath(outdir string) string { return filepath.Join(outdir, "breakpoints.json") }

func loadMarks(outdir string) []int {
	b, err := os.ReadFile(marksPath(outdir))
	if err != nil {
		return []int{}
	}
	var doc struct {
		Marks []int `json:"marks"`
	}
	if json.Unmarshal(b, &doc) != nil {
		return []int{}
	}
	return sortedUnique(doc.Marks)
}

func saveMarks(outdir string, marks []int) error {
	b, err := json.MarshalIndent(map[string][]int{"marks": sortedUnique(marks)}, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(marksPath(outdir), b, 0o644)
}

func sortedUnique(in []int) []int {
	out := append([]int(nil), in...)
	sort.Ints(out)
	out = uniqueInts(out)
	if out == nil {
		return []int{}
	}
	return out
}

// ── where a cut lands ───────────────────────────────────────────────────────

// deriveSegmentsDir — the video's own `dev/_cuts`.
//
// A deposit into dev/ archives the generation it replaces first, so nothing is
// overwritten and the previous cut is always one folder away. A fresh cut IS
// the start of a video, and it belongs where the build looks for its source.
//
// Detected from the source path's own SHAPE rather than a hardcoded depth:
//
//	.../help-videos/raw_mp4/<file>       -> the newest videos/<slug>/dev/_cuts
//	.../videos/<slug>/{dev,sandbox}/...  -> that video's dev/_cuts
//	anything else                        -> a dev/_cuts beside the source
func deriveSegmentsDir(source string) string {
	d, _ := filepath.Abs(filepath.Dir(source))
	parts := strings.Split(d, string(os.PathSeparator))

	for i := len(parts) - 1; i >= 0; i-- {
		if parts[i] == "videos" && i+1 < len(parts) {
			return filepath.Join(strings.Join(parts[:i+2], string(os.PathSeparator)), "dev", "_cuts")
		}
	}

	if filepath.Base(d) == "raw_mp4" {
		hv := filepath.Dir(d)
		vids := filepath.Join(hv, "videos")
		if isDir(vids) {
			entries, _ := os.ReadDir(vids)
			var subs []string
			for _, e := range entries {
				if isDir(filepath.Join(vids, e.Name())) {
					subs = append(subs, e.Name())
				}
			}
			sort.Strings(subs)
			if len(subs) > 0 {
				return filepath.Join(vids, subs[len(subs)-1], "dev", "_cuts")
			}
		}
		if isDir(filepath.Join(hv, "final")) {
			return filepath.Join(hv, "final", "dev", "_cuts")
		}
	}
	return filepath.Join(d, "dev", "_cuts")
}

var segmentNameRE = regexp.MustCompile(`^Num_(\d+)-v(\d+)-segment\.(?:mp4|webm)$`)

// nextVersion — every cut in a folder is one BATCH sharing one version number,
// one higher than anything already there. Re-cutting after moving a break point
// keeps every earlier attempt instead of overwriting it. Derived by scanning
// the real files, not from a counter that could drift from what is on disk.
func nextVersion(dir string) int {
	if !isDir(dir) {
		return 1
	}
	entries, _ := os.ReadDir(dir)
	best := 0
	for _, e := range entries {
		if m := segmentNameRE.FindStringSubmatch(e.Name()); m != nil {
			if v, _ := strconv.Atoi(m[2]); v > best {
				best = v
			}
		}
	}
	return best + 1
}

// TrackFile — what each track is called on disk. ONE mapping, so a track cannot
// be written under the wrong name by one operation and the right one by another.
var TrackFile = map[string]string{
	"segment":   "segment.mp4",
	"avatar":    "avatar.webm",
	"narration": "narration.webm",
}

// ── building a clip from runs ───────────────────────────────────────────────

// buildSegment builds one clip from GroupFrameRuns' pieces.
//
// A single "cut" — the common case, nothing here was ever frame-edited — goes
// straight to one ffmpeg call. Several runs mean an edit landed inside: each
// piece is built separately and concatenated, and a "hold" is one still frame
// extracted from the source and looped at the source's OWN rate, never slowed
// footage.
//
// LENGTH IS COUNTED IN FRAMES, NOT SECONDS. Every piece used to end with
// `-t duration`, and a duration cutoff drops the frame whose span ends exactly
// on the boundary: 30 frames returned 29, 58 returned 57. Each piece rounded on
// its own, so an edited clip lost one frame PER CUT — an 89-frame preview wrote
// 87. `-frames:v N` asks for the thing actually wanted.
//
// The `-ss` seek stays: it was never the problem. Verified by md5 — the frame it
// lands on is byte-identical to the same frame pulled with an exact select.
func buildSegment(src string, fps float64, runs []Run, dst, tmpDir string) (string, error) {
	// Transparency has to survive all three of decode, encode and container.
	// Miss any one and the failure is a black box, not an error.
	dec := DecFor(src)
	enc := encFor(src)
	ext := extFor(src)

	if len(runs) == 1 && runs[0].Kind == "cut" {
		s, e := runs[0].A, runs[0].B
		args := append([]string{"-v", "error"}, dec...)
		args = append(args, "-ss", fmt.Sprintf("%.6f", float64(s-1)/fps), "-i", src,
			"-frames:v", strconv.Itoa(e-s+1))
		args = append(args, enc...)
		args = append(args, "-y", dst)
		_, errs, err := run("ffmpeg", args...)
		return errs, err
	}

	var parts []string
	for i, piece := range runs {
		var errs string
		var err error
		var part string
		if piece.Kind == "cut" {
			s, e := piece.A, piece.B
			part = filepath.Join(tmpDir, fmt.Sprintf("p%d_cut%s", i, ext))
			args := append([]string{"-v", "error"}, dec...)
			args = append(args, "-ss", fmt.Sprintf("%.6f", float64(s-1)/fps), "-i", src,
				"-frames:v", strconv.Itoa(e-s+1))
			args = append(args, enc...)
			args = append(args, "-y", part)
			_, errs, err = run("ffmpeg", args...)
		} else {
			frame, count := piece.A, piece.B
			// PNG carries alpha, so a held frame keeps it — but only if the
			// frame was DECODED with alpha in the first place.
			still := filepath.Join(tmpDir, fmt.Sprintf("p%d_still.png", i))
			args := append([]string{"-v", "error"}, dec...)
			args = append(args, "-ss", fmt.Sprintf("%.3f", float64(frame-1)/fps),
				"-i", src, "-frames:v", "1", "-y", still)
			if _, errs, err = run("ffmpeg", args...); err != nil {
				return errs, err
			}
			part = filepath.Join(tmpDir, fmt.Sprintf("p%d_hold%s", i, ext))
			vf := "fps=" + fmtG(fps)
			if IsAlpha(src) {
				vf += ",format=yuva420p"
			}
			args = []string{"-v", "error", "-loop", "1", "-i", still,
				"-frames:v", strconv.Itoa(count), "-vf", vf}
			args = append(args, enc...)
			args = append(args, "-y", part)
			_, errs, err = run("ffmpeg", args...)
		}
		if err != nil {
			return errs, err
		}
		parts = append(parts, part)
	}

	lst := filepath.Join(tmpDir, "list.txt")
	var sb strings.Builder
	for _, p := range parts {
		abs, _ := filepath.Abs(p)
		fmt.Fprintf(&sb, "file '%s'\n", abs)
	}
	if err := os.WriteFile(lst, []byte(sb.String()), 0o644); err != nil {
		return "", err
	}
	// `dec` AGAIN, and it is easy to miss here. The concat demuxer re-DECODES
	// every part, so without it the alpha is dropped at this last step — and the
	// result still comes out yuva420p, because the encoder happily writes an
	// alpha plane that is 100% opaque. Measured exactly that before this line
	// was fixed: a saved clip reported the right pixel format and was solid.
	args := append([]string{"-v", "error"}, dec...)
	args = append(args, "-f", "concat", "-safe", "0", "-i", lst)
	args = append(args, enc...)
	args = append(args, "-y", dst)
	_, errs, err := run("ffmpeg", args...)
	return errs, err
}

// makeGapFiller builds a transparent, silent clip `frames` long, matching
// `like`'s size and rate.
//
// Used where a scene HAS NO track the others have — the opening has no
// narration render. Concatenating without it makes the next scene's narration
// start at frame 1 instead of after the opening, so Sarah says the login line
// over the intro. The filler holds that time open.
//
// Transparent and silent is the honest content: for the opening's duration
// there IS no narration, and that is what "no narration" looks like once it has
// to occupy time.
func makeGapFiller(like string, frames int, dst string) error {
	w, err := probeInt(like, "width", true, vp9Decoder)
	if err != nil {
		return err
	}
	h, err := probeInt(like, "height", true, vp9Decoder)
	if err != nil {
		return err
	}
	rate, err := Probe(like, "r_frame_rate", true, vp9Decoder)
	if err != nil {
		return err
	}
	rate = strings.TrimSpace(strings.Split(rate, "\n")[0])
	if !strings.Contains(rate, "/") {
		rate += "/1"
	}
	args := []string{"-v", "error",
		// `,format=yuva420p` in the FILTER, not just -pix_fmt on the output.
		// Without it the colour source hands over yuv420p and the encoder adds
		// an OPAQUE alpha channel — measured 255 everywhere. The filler would
		// have blacked the opening out instead of being invisible.
		"-f", "lavfi", "-i", fmt.Sprintf("color=c=black@0.0:s=%dx%d:r=%s,format=yuva420p", w, h, rate),
		"-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
		"-frames:v", strconv.Itoa(frames)}
	args = append(args, ENCODE_ALPHA...)
	args = append(args, "-shortest", "-y", dst)
	if _, errs, err := run("ffmpeg", args...); err != nil {
		return fmt.Errorf("could not build the %d-frame filler: %s", frames, tail(errs, 300))
	}
	return nil
}

// renumberSandboxFolders renames sandbox folders so their NN- prefix matches
// the scene numbers.
//
// A scene's folder is found by that prefix, so renumbering the SCRIPT without
// renaming the folders makes every moved scene unresolvable — it simply
// vanishes from the editor. Measured exactly that: after a join, scene 2's
// folder was still 03-logout-menu and its segment came back as nothing.
//
// Matched by LABEL, not by the old number, because the numbers are what just
// changed. Renamed in TWO passes through a temporary name, so a folder is never
// renamed onto one that has not moved out of the way yet — renumbering 3->2
// while 2 still exists is the normal case, not the exception.
//
// dev/ is deliberately NOT touched. It is the untouched copy of what was there
// before, and after a join or split it genuinely no longer mirrors sandbox;
// pretending otherwise would lose the record.
func renumberSandboxFolders(final string, scenes []Scene) []string {
	root := SandboxRoot(final)
	if !isDir(root) {
		return []string{}
	}
	cur := map[string]string{}
	entries, _ := os.ReadDir(root)
	rx := regexp.MustCompile(`^(\d+)-(.+)$`)
	for _, e := range entries {
		if m := rx.FindStringSubmatch(e.Name()); m != nil && isDir(filepath.Join(root, e.Name())) {
			cur[m[2]] = filepath.Join(root, e.Name())
		}
	}
	type move struct{ src, dst string }
	var moves []move
	for _, sc := range scenes {
		lab := sc.Label()
		src, ok := cur[lab]
		if lab == "" || !ok {
			continue
		}
		want := filepath.Join(root, fmt.Sprintf("%02d-%s", sc.N(), lab))
		a, _ := filepath.Abs(src)
		b, _ := filepath.Abs(want)
		if a != b {
			moves = append(moves, move{src, want})
		}
	}
	type staged struct{ tmp, dst string }
	var st []staged
	for _, mv := range moves {
		tmp := mv.src + ".renumbering"
		if os.Rename(mv.src, tmp) == nil {
			st = append(st, staged{tmp, mv.dst})
		}
	}
	out := []string{}
	for _, s := range st {
		if os.Rename(s.tmp, s.dst) == nil {
			out = append(out, filepath.Base(s.dst))
		}
	}
	return out
}

// frameCount — how many frames the editor will actually work with, and whether
// that number is known or estimated.
//
// ffprobe's container `nb_frames` and the extractor DISAGREE: on one real
// segment the container says 198 and the extraction produces 199 real files.
// Every other number in this tool — the slider, the frame map, what Cut and Save
// write — is the extracted one, so showing the container's would put a number on
// screen that contradicts the editor by one.
//
// So: if the clip has been extracted, report meta's count and call it exact.
// Otherwise fall back to the container and mark it an estimate, which the page
// renders with a leading ~. Never silently mix the two.
func (s *Server) frameCount(path string) (int, bool) {
	outdir := filepath.Join(s.Cache, SlugFor(path))
	if m, err := LoadMeta(outdir); err == nil && m.NbFrames > 0 {
		return m.NbFrames, true
	}
	if n, err := probeInt(path, "nb_frames", true, nil); err == nil && n > 0 {
		return n, false
	}
	// VP9 carries no frame count in the container — `nb_frames` is N/A on every
	// avatar clip, with or without the decoder forced. Counting packets does
	// work and agrees with the extraction, but it reads the whole file, so it is
	// the LAST resort and only for a clip nobody has opened yet.
	out, _, err := run("ffprobe", "-v", "error", "-select_streams", "v",
		"-count_packets", "-show_entries", "stream=nb_read_packets",
		"-of", "csv=p=0", path)
	if err == nil {
		if n, err := strconv.Atoi(strings.TrimSpace(strings.Split(out, "\n")[0])); err == nil {
			return n, false
		}
	}
	return -1, false
}
