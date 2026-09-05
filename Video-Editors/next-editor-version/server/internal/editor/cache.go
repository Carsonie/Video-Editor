package editor

// The frame cache — the Go port of shared/frames.py.
//
// A clip is extracted ONCE into cache/<slug>/frames/frame_00001.jpg… and every
// edit is made against those files plus `frame_map`. That map is the single
// source of truth: frame_map[i] is the SOURCE frame number that cache frame
// i+1 shows. It is what lets a rebuild reproduce a duplicate as a real held
// frame and a deletion as genuinely absent, and it is what undo restores.

import (
	"crypto/sha1"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"sync"
	"time"
)

// ── one writer at a time, per cache folder ──────────────────────────────────
// The server is threaded, so two clicks a second apart run at once. Nothing
// used to stop two of them re-extracting into the SAME frames/ directory, and
// they stomped on each other: six Undo clicks in six seconds left a 440-frame
// clip with a 204-frame cache, by way of 216 and 381.
//
// Keyed on the folder, so edits to different clips still run in parallel —
// which is the whole reason the server is concurrent.
var (
	dirLocks   = map[string]*sync.Mutex{}
	locksGuard sync.Mutex
)

func DirLock(outdir string) *sync.Mutex {
	key, err := filepath.Abs(outdir)
	if err != nil {
		key = outdir
	}
	locksGuard.Lock()
	defer locksGuard.Unlock()
	if m, ok := dirLocks[key]; ok {
		return m
	}
	m := &sync.Mutex{}
	dirLocks[key] = m
	return m
}

// Meta is cache/<slug>/meta.json. Field names and types match the Python
// exactly — the two servers read each other's caches, and a Python test asserts
// on `ext` and `alpha_png` in this very file.
type Meta struct {
	Source     string  `json:"source"`
	Size       int64   `json:"size"`
	Mtime      float64 `json:"mtime"`
	Box        int     `json:"box"`
	AlphaPNG   bool    `json:"alpha_png"`
	Ext        string  `json:"ext"`
	HasAudio   bool    `json:"has_audio"`
	FPS        float64 `json:"fps"`
	NbFrames   int     `json:"nb_frames"`
	Width      int     `json:"width"`
	Height     int     `json:"height"`
	Duration   float64 `json:"duration"`
	DispW      int     `json:"disp_w"`
	DispH      int     `json:"disp_h"`
	SourceName string  `json:"source_name"`
	FrameMap   []int   `json:"frame_map"`
	Edited     bool    `json:"edited"`
}

func metaPath(outdir string) string  { return filepath.Join(outdir, "meta.json") }
func framesDir(outdir string) string { return filepath.Join(outdir, "frames") }

func LoadMeta(outdir string) (*Meta, error) {
	b, err := os.ReadFile(metaPath(outdir))
	if err != nil {
		return nil, err
	}
	var m Meta
	if err := json.Unmarshal(b, &m); err != nil {
		return nil, err
	}
	return &m, nil
}

func SaveMeta(outdir string, m *Meta) error {
	b, err := json.MarshalIndent(m, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(metaPath(outdir), b, 0o644)
}

// GetFrameMap defaults to the identity mapping — exactly correct for a cache
// nothing has ever edited, and the right answer for one built before the field
// existed. Never mutates `m`.
func GetFrameMap(m *Meta) []int {
	if len(m.FrameMap) > 0 {
		out := make([]int, len(m.FrameMap))
		copy(out, m.FrameMap)
		return out
	}
	out := make([]int, m.NbFrames)
	for i := range out {
		out[i] = i + 1
	}
	return out
}

var slugUnsafe = regexp.MustCompile(`[^A-Za-z0-9._-]`)

// SlugFor names a cache folder. The slug becomes a URL PATH SEGMENT
// (`<slug>/viewer.html`), so only characters that survive there unescaped are
// kept. `#` is not one: a source named `#1-v2-segment.mp4` produced a slug
// starting with `#`, and `location.href = "#slug/viewer.html"` was read as an
// in-page anchor jump. Nothing errored; the page silently stayed put.
func SlugFor(path string) string {
	abs, err := filepath.Abs(path)
	if err != nil {
		abs = path
	}
	sum := sha1.Sum([]byte(abs))
	h := hex.EncodeToString(sum[:])[:8]
	base := strings.TrimSuffix(filepath.Base(path), filepath.Ext(path))
	safe := slugUnsafe.ReplaceAllString(base, "")
	if safe == "" {
		safe = "video"
	}
	return safe + "_" + h
}

func framePath(dir string, f int, ext string) string {
	return filepath.Join(dir, fmt.Sprintf("frame_%05d%s", f, ext))
}

// restamp gives a frame file the current mtime.
//
// A rename carries a file's mtime with it, so after a shift `frame_00090.jpg`
// holds different pixels while still claiming the timestamp of whatever moved
// into that slot. The viewer fetches frames by a URL that does not change, so
// the browser revalidates, the server truthfully answers 304, and the STALE
// picture is shown. The symptom is badly misleading: the count drops but the
// pictures do not move, so a delete in the middle looks exactly like frames
// being removed from the END.
//
// A frame's URL is its position, so its position changing IS its content
// changing, and the mtime has to say so.
func restamp(p string) {
	now := time.Now()
	_ = os.Chtimes(p, now, now)
}

// ExtractAudio pulls `src`'s audio to outdir/audio.m4a. Reports whether the
// clip ends up with sound.
//
// Re-encoded to AAC in m4a rather than copied: sources here are Opus-in-WebM
// and AAC-in-mp4, and only one of those plays everywhere. A viewer that works
// for the mp4 and is silent for the WebM is worse than no audio at all,
// because the silence looks like the clip.
func ExtractAudio(src, outdir string, log func(string)) bool {
	audio := filepath.Join(outdir, "audio.m4a")
	ok := hasAudioStream(src)
	if ok {
		_, errs, err := run("ffmpeg", "-v", "error", "-i", src, "-vn",
			"-c:a", "aac", "-b:a", "128k", "-y", audio)
		if err != nil {
			ok = false
			log(fmt.Sprintf("  ⚠ audio extraction failed, continuing silent: %s", tail(errs, 200)))
		}
	}
	if !ok {
		_ = os.Remove(audio)
	}
	return ok
}

// BuildFrames extracts every frame of `video` and writes its viewer page.
// Returns the cache folder.
//
// Cached on the resolved source path plus its size, mtime, box and alpha mode.
// A rebuild is skipped when all of those still match — `force` redoes it anyway.
func BuildFrames(s *Server, video, out string, box int, force, alphaPNG bool, log func(string)) (string, error) {
	src, err := filepath.Abs(video)
	if err != nil {
		return "", err
	}
	st, err := os.Stat(src)
	if err != nil {
		return "", fmt.Errorf("no such file: %s", src)
	}
	outdir := out
	if outdir == "" {
		outdir = filepath.Join(s.Cache, SlugFor(src))
	}
	fdir := framesDir(outdir)

	sigSize := st.Size()
	sigMtime := float64(st.ModTime().UnixNano()) / 1e9

	if !force {
		if prior, err := LoadMeta(outdir); err == nil && isDir(fdir) {
			same := prior.Source == src && prior.Size == sigSize &&
				prior.Mtime == sigMtime && prior.Box == box && prior.AlphaPNG == alphaPNG
			if same {
				// A cache built before audio was extracted should not have to
				// be thrown away to gain it. Half a second, against
				// re-extracting every frame.
				if prior.HasAudio && !isFile(filepath.Join(outdir, "audio.m4a")) {
					log("  cached extraction has no audio — pulling just the audio")
					prior.HasAudio = ExtractAudio(src, outdir, log)
					_ = SaveMeta(outdir, prior)
				}
				// Always rewrite the page against the CURRENT template —
				// otherwise a template fix never reaches an old cache without a
				// wasteful full re-extraction.
				if err := WriteViewer(outdir, prior); err != nil {
					return "", err
				}
				log(fmt.Sprintf("  using cached extraction: %s", outdir))
				return outdir, nil
			}
			log("  source changed since last extraction — re-extracting")
		}
	}

	if err := os.MkdirAll(fdir, 0o755); err != nil {
		return "", err
	}
	entries, _ := os.ReadDir(fdir)
	for _, e := range entries {
		_ = os.Remove(filepath.Join(fdir, e.Name()))
	}

	alpha := IsAlpha(src)
	dec := DecFor(src)

	fps, err := probeRate(src, dec)
	if err != nil {
		return "", fmt.Errorf("could not read the frame rate of %s: %w", filepath.Base(src), err)
	}
	width, err := probeInt(src, "width", true, dec)
	if err != nil {
		return "", err
	}
	height, err := probeInt(src, "height", true, dec)
	if err != nil {
		return "", err
	}
	duration, _ := probeFloat(src, "duration", false, dec)

	log(fmt.Sprintf("  source: %dx%d @ %sfps, %.2fs", width, height, fmtG(fps), duration))
	log(fmt.Sprintf("  extracting frames into %s ...", fdir))

	// JPEG cannot carry alpha, and a transparent frame written straight to JPEG
	// comes out BLACK — an avatar clip becomes a black rectangle with a person
	// somewhere in it. `alphaPNG` keeps the REAL alpha as PNG, for layering one
	// clip over another in the browser; otherwise alpha is flattened onto the
	// same flat grey the finished video uses.
	ext := ".jpg"
	if alphaPNG {
		ext = ".png"
	}
	scale := fmt.Sprintf("scale=%d:%d:force_original_aspect_ratio=decrease", box, box)

	args := append([]string{"-v", "error"}, dec...)
	if alpha && !alphaPNG {
		vf := fmt.Sprintf("color=c=0x232323:s=%dx%d[bg];[bg][0:v]overlay=0:0:shortest=1,%s",
			width, height, scale)
		args = append(args, "-i", src, "-filter_complex", vf)
		// `shortest=1` is NOT enough to end this on the clip's last frame. The
		// background is an INFINITE `color=` source, and on two of ski-demo's
		// clips the composite ran past the input: 00-opening decodes 284 frames
		// and wrote 285. Every other alpha clip happened to come out right,
		// which is what makes it a trap. So the count is decoded first and the
		// output capped to it outright.
		if n := DecodedFrames(src, dec); n > 0 {
			args = append(args, "-frames:v", fmt.Sprint(n))
		}
	} else {
		args = append(args, "-i", src, "-vf", scale)
	}
	if alphaPNG {
		args = append(args, "-pix_fmt", "rgba")
	} else {
		args = append(args, "-q:v", "3")
	}
	// -fps_mode passthrough: write EXACTLY the frames the file decodes and no
	// others. Without it ffmpeg's image writer runs at constant frame rate and
	// fills the container's declared duration, which on every MP4 here is
	// ~0.021s longer than the last frame — so it DUPLICATED the final frame to
	// pad. Measured: a clip that decodes 198 frames produced 199 JPEGs; another
	// that decodes 125 produced 127, its last three files byte-identical.
	// A preview that invents frames cannot be used to judge length, and /api/save
	// rebuilds from these frames, so the padding could reach the real clip.
	args = append(args, "-fps_mode", "passthrough", "-start_number", "1",
		filepath.Join(fdir, "frame_%05d"+ext))
	if _, errs, err := run("ffmpeg", args...); err != nil {
		return "", fmt.Errorf("ffmpeg extraction failed:\n%s", errs)
	}

	// Frames alone cannot show SYNC — whether her mouth matches her words is
	// the one fault this tool kept missing — so the clip's own audio is
	// extracted once and played against the playhead.
	hasAudio := ExtractAudio(src, outdir, log)

	nb := countFrames(fdir)
	if nb == 0 {
		return "", fmt.Errorf("ffmpeg produced no frames — check the source file")
	}

	dispW, dispH := box, box
	if width >= height {
		dispW, dispH = box, roundHalfEven(float64(box)*float64(height)/float64(width))
	} else {
		dispH, dispW = box, roundHalfEven(float64(box)*float64(width)/float64(height))
	}

	fmap := make([]int, nb)
	for i := range fmap {
		fmap[i] = i + 1
	}
	m := &Meta{
		Source: src, Size: sigSize, Mtime: sigMtime, Box: box, AlphaPNG: alphaPNG,
		Ext: ext, HasAudio: hasAudio, FPS: fps, NbFrames: nb,
		Width: width, Height: height, Duration: duration,
		DispW: dispW, DispH: dispH, SourceName: filepath.Base(src),
		// frame_map starts as the identity (cache frame N *is* source frame N).
		// Every edit updates it in lockstep with the files, so a cut can later
		// rebuild the same holds and gaps from the real source.
		FrameMap: fmap,
		// Set true by any frame edit — lets Save start disabled and light up
		// only once there is something a save would change. Equal adds and
		// deletes could leave N unchanged with the clip genuinely edited, so
		// the count alone cannot answer this.
		Edited: false,
	}
	if err := SaveMeta(outdir, m); err != nil {
		return "", err
	}
	if err := WriteViewer(outdir, m); err != nil {
		return "", err
	}
	log(fmt.Sprintf("  %d frames extracted (%sfps)", nb, fmtG(fps)))
	return outdir, nil
}

func countFrames(dir string) int {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return 0
	}
	n := 0
	for _, e := range entries {
		if strings.HasPrefix(e.Name(), "frame_") {
			n++
		}
	}
	return n
}

// roundHalfEven matches Python's round(), which rounds a .5 to the nearest
// EVEN integer rather than always up. The display box maths is the only place
// that shows, and a page one pixel taller than the Python one would be a
// difference nobody could explain later.
func roundHalfEven(f float64) int {
	i := int(f)
	frac := f - float64(i)
	switch {
	case frac > 0.5:
		return i + 1
	case frac < 0.5:
		return i
	default:
		if i%2 == 0 {
			return i
		}
		return i + 1
	}
}

// ── the frame edits ─────────────────────────────────────────────────────────

func touchEdit(outdir string, m *Meta, newN int) error {
	m.Edited = true
	m.NbFrames = newN
	m.Duration = float64(newN) / m.FPS
	if err := SaveMeta(outdir, m); err != nil {
		return err
	}
	return WriteViewer(outdir, m)
}

// PasteFrame puts a COPY of frame `from` immediately after frame `at`.
//
// EXACT, and that is the whole point: the map records the SOURCE frame the copy
// shows, so a pasted frame IS the same frame, not a re-encode of a picture of
// one. Going out to the system clipboard and back would cost a decode, a PNG
// round trip and an encode, and the map would have no idea what it was.
//
// Returns (new frame count, the frame to land on).
func PasteFrame(outdir string, from, at int) (int, int, error) {
	m, err := LoadMeta(outdir)
	if err != nil {
		return 0, 0, err
	}
	n := m.NbFrames
	for _, c := range []struct {
		name string
		f    int
	}{{"source", from}, {"target", at}} {
		if c.f < 1 || c.f > n {
			return 0, 0, fmt.Errorf("%s frame %d is outside 1..%d", c.name, c.f, n)
		}
	}
	fdir, ext := framesDir(outdir), m.Ext
	// Read the pixels BEFORE any renaming — `from` may itself be about to move.
	pixels, err := os.ReadFile(framePath(fdir, from, ext))
	if err != nil {
		return 0, 0, err
	}
	fmap := GetFrameMap(m)
	srcIndex := fmap[from-1]

	// DESCENDING, so a shift never lands on a file it has not read yet.
	for f := n; f > at; f-- {
		dst := framePath(fdir, f+1, ext)
		if err := os.Rename(framePath(fdir, f, ext), dst); err != nil {
			return 0, 0, err
		}
		restamp(dst)
	}
	dst := framePath(fdir, at+1, ext)
	if err := os.WriteFile(dst, pixels, 0o644); err != nil {
		return 0, 0, err
	}
	restamp(dst)

	m.FrameMap = insertInts(fmap, at, []int{srcIndex})
	m.NbFrames = n + 1
	if err := SaveMeta(outdir, m); err != nil {
		return 0, 0, err
	}
	return n + 1, at + 1, nil
}

// DuplicateFrameRight inserts `count` copies of frame `at` immediately to its
// right. Frame `at` keeps its number; everything after shifts right.
//
// No upper bound beyond n — duplicating the LAST frame is valid, and is exactly
// why this does not refuse at at == n.
func DuplicateFrameRight(outdir string, at, count int) (int, int, error) {
	m, err := LoadMeta(outdir)
	if err != nil {
		return 0, 0, err
	}
	n := m.NbFrames
	if at < 1 || at > n {
		return 0, 0, fmt.Errorf("frame %d is outside 1..%d", at, n)
	}
	fdir, ext := framesDir(outdir), m.Ext
	for f := n; f > at; f-- {
		dst := framePath(fdir, f+count, ext)
		if err := os.Rename(framePath(fdir, f, ext), dst); err != nil {
			return 0, 0, err
		}
		restamp(dst)
	}
	pixels, err := os.ReadFile(framePath(fdir, at, ext))
	if err != nil {
		return 0, 0, err
	}
	for i := 1; i <= count; i++ {
		// copy, not move — frame `at` itself must survive every iteration
		p := framePath(fdir, at+i, ext)
		if err := os.WriteFile(p, pixels, 0o644); err != nil {
			return 0, 0, err
		}
		restamp(p)
	}
	fmap := GetFrameMap(m)
	m.FrameMap = insertInts(fmap, at, repeat(fmap[at-1], count))
	if err := touchEdit(outdir, m, n+count); err != nil {
		return 0, 0, err
	}
	return n + count, at + count, nil
}

// DuplicateFrameLeft inserts `count` copies of frame `at` immediately to its
// LEFT. `at`'s content survives but its number shifts to at+count — the copies
// take the slots it used to occupy. Valid at at == 1 too.
func DuplicateFrameLeft(outdir string, at, count int) (int, int, error) {
	m, err := LoadMeta(outdir)
	if err != nil {
		return 0, 0, err
	}
	n := m.NbFrames
	if at < 1 || at > n {
		return 0, 0, fmt.Errorf("frame %d is outside 1..%d", at, n)
	}
	fdir, ext := framesDir(outdir), m.Ext
	// Read BEFORE shifting — the shift moves that same file out from under
	// `at`'s old path.
	original, err := os.ReadFile(framePath(fdir, at, ext))
	if err != nil {
		return 0, 0, err
	}
	for f := n; f >= at; f-- {
		dst := framePath(fdir, f+count, ext)
		if err := os.Rename(framePath(fdir, f, ext), dst); err != nil {
			return 0, 0, err
		}
		restamp(dst)
	}
	for i := 0; i < count; i++ {
		p := framePath(fdir, at+i, ext)
		if err := os.WriteFile(p, original, 0o644); err != nil {
			return 0, 0, err
		}
		restamp(p)
	}
	fmap := GetFrameMap(m)
	m.FrameMap = insertInts(fmap, at-1, repeat(fmap[at-1], count))
	if err := touchEdit(outdir, m, n+count); err != nil {
		return 0, 0, err
	}
	return n + count, at + count, nil
}

// DeleteFramesLeft removes up to `count` frames immediately to the LEFT of
// `at`. Clamped so it can never delete frame 1 or below.
//
// Returns (new count, where `at`'s own content ended up, how many were ACTUALLY
// removed, and the deleted range) — the actual count can be less than asked
// near the start, and the caller needs the range to move the marks.
func DeleteFramesLeft(outdir string, at, count int) (int, int, int, [2]int, bool, error) {
	m, err := LoadMeta(outdir)
	if err != nil {
		return 0, 0, 0, [2]int{}, false, err
	}
	n := m.NbFrames
	if at < 1 || at > n {
		return 0, 0, 0, [2]int{}, false, fmt.Errorf("frame %d is outside 1..%d", at, n)
	}
	actual := min(count, at-1)
	if actual <= 0 {
		return n, at, 0, [2]int{}, false, nil
	}
	fdir, ext := framesDir(outdir), m.Ext
	delStart, delEnd := at-actual, at-1
	for f := delStart; f <= delEnd; f++ {
		_ = os.Remove(framePath(fdir, f, ext))
	}
	// ASCENDING, so a shift never overwrites a file before it has been read.
	for f := at; f <= n; f++ {
		dst := framePath(fdir, f-actual, ext)
		if err := os.Rename(framePath(fdir, f, ext), dst); err != nil {
			return 0, 0, 0, [2]int{}, false, err
		}
		restamp(dst)
	}
	fmap := GetFrameMap(m)
	m.FrameMap = append(fmap[:delStart-1:delStart-1], fmap[delEnd:]...)
	if err := touchEdit(outdir, m, n-actual); err != nil {
		return 0, 0, 0, [2]int{}, false, err
	}
	return n - actual, at - actual, actual, [2]int{delStart, delEnd}, true, nil
}

// DeleteFramesRight removes up to `count` frames immediately to the RIGHT of
// `at`. Frame `at` is never touched, so the viewer's position does not move —
// unlike the left variant, where everything from `at` onward shifts.
func DeleteFramesRight(outdir string, at, count int) (int, int, int, [2]int, bool, error) {
	m, err := LoadMeta(outdir)
	if err != nil {
		return 0, 0, 0, [2]int{}, false, err
	}
	n := m.NbFrames
	if at < 1 || at > n {
		return 0, 0, 0, [2]int{}, false, fmt.Errorf("frame %d is outside 1..%d", at, n)
	}
	actual := min(count, n-at)
	if actual <= 0 {
		return n, at, 0, [2]int{}, false, nil
	}
	fdir, ext := framesDir(outdir), m.Ext
	delStart, delEnd := at+1, at+actual
	for f := delStart; f <= delEnd; f++ {
		_ = os.Remove(framePath(fdir, f, ext))
	}
	for f := delEnd + 1; f <= n; f++ {
		dst := framePath(fdir, f-actual, ext)
		if err := os.Rename(framePath(fdir, f, ext), dst); err != nil {
			return 0, 0, 0, [2]int{}, false, err
		}
		restamp(dst)
	}
	fmap := GetFrameMap(m)
	m.FrameMap = append(fmap[:delStart-1:delStart-1], fmap[delEnd:]...)
	if err := touchEdit(outdir, m, n-actual); err != nil {
		return 0, 0, 0, [2]int{}, false, err
	}
	return n - actual, at, actual, [2]int{delStart, delEnd}, true, nil
}

// DuplicateSpan inserts a copy of frames a..b immediately after b — "loop this
// marked zone once more". The single-frame version repeats ONE frame `count`
// times; this repeats a RUN, which is a different thing.
func DuplicateSpan(outdir string, a, b int) (int, int, error) {
	m, err := LoadMeta(outdir)
	if err != nil {
		return 0, 0, err
	}
	n := m.NbFrames
	if !(1 <= a && a <= b && b <= n) {
		return 0, 0, fmt.Errorf("span %d..%d is outside 1..%d", a, b, n)
	}
	k := b - a + 1
	fdir, ext := framesDir(outdir), m.Ext
	for f := n; f > b; f-- {
		dst := framePath(fdir, f+k, ext)
		if err := os.Rename(framePath(fdir, f, ext), dst); err != nil {
			return 0, 0, err
		}
		restamp(dst)
	}
	for i := 0; i < k; i++ {
		pixels, err := os.ReadFile(framePath(fdir, a+i, ext))
		if err != nil {
			return 0, 0, err
		}
		p := framePath(fdir, b+1+i, ext)
		if err := os.WriteFile(p, pixels, 0o644); err != nil {
			return 0, 0, err
		}
		restamp(p)
	}
	fmap := GetFrameMap(m)
	m.FrameMap = insertInts(fmap, b, append([]int(nil), fmap[a-1:b]...))
	if err := touchEdit(outdir, m, n+k); err != nil {
		return 0, 0, err
	}
	return n + k, b + k, nil
}

// DeleteSpan removes frames a..b. Refuses to empty the clip: something has to
// be left to look at, and a zero-frame cache is a broken viewer, not a short one.
func DeleteSpan(outdir string, a, b int) (int, int, error) {
	m, err := LoadMeta(outdir)
	if err != nil {
		return 0, 0, err
	}
	n := m.NbFrames
	if !(1 <= a && a <= b && b <= n) {
		return 0, 0, fmt.Errorf("span %d..%d is outside 1..%d", a, b, n)
	}
	k := b - a + 1
	if k >= n {
		return 0, 0, fmt.Errorf("that span is the whole clip — refusing to leave it empty")
	}
	fdir, ext := framesDir(outdir), m.Ext
	for f := a; f <= b; f++ {
		_ = os.Remove(framePath(fdir, f, ext))
	}
	for f := b + 1; f <= n; f++ {
		dst := framePath(fdir, f-k, ext)
		if err := os.Rename(framePath(fdir, f, ext), dst); err != nil {
			return 0, 0, err
		}
		restamp(dst)
	}
	fmap := GetFrameMap(m)
	m.FrameMap = append(fmap[:a-1:a-1], fmap[b:]...)
	if err := touchEdit(outdir, m, n-k); err != nil {
		return 0, 0, err
	}
	return n - k, max(1, a-1), nil
}

// RestoreMap puts a cache back to a previous frame map — the mechanism behind
// undo.
//
// A frame map is the whole truth about an edited clip, so any past state can be
// rebuilt from the source plus its map and no history of the images has to be
// kept.
//
// Re-extracting first is deliberate. Undoing an ADD could be done by deleting
// the inserted copies; undoing a DELETE cannot — those files are gone. Rather
// than have undo work for one kind of edit and not the other, both go the same
// way: extract clean, then lay the target map over it.
func RestoreMap(s *Server, outdir string, target []int, log func(string)) (int, error) {
	m, err := LoadMeta(outdir)
	if err != nil {
		return 0, err
	}
	src := m.Source
	if !isFile(src) {
		return 0, fmt.Errorf("source no longer exists: %s", src)
	}
	ext := m.Ext

	// VALIDATED BEFORE ANYTHING IS RE-EXTRACTED. This used to re-extract first
	// and check afterwards, so a map that failed the check had already wiped the
	// edits it was meant to restore — the error read as "nothing happened" while
	// the cache was already back to raw.
	//
	// The count comes from the SOURCE, not the cache, because the cache is
	// exactly what is about to be replaced.
	if len(target) == 0 {
		return 0, fmt.Errorf("refusing to restore an empty map")
	}
	var dec []string
	if ext == ".png" {
		dec = vp9Decoder
	}
	nSrc := DecodedFrames(src, dec)
	if nSrc < 0 {
		return 0, fmt.Errorf("could not count the frames in %s", filepath.Base(src))
	}
	var bad []int
	for _, x := range target {
		if x < 1 || x > nSrc {
			bad = append(bad, x)
		}
	}
	if len(bad) > 0 {
		sort.Ints(bad)
		bad = uniqueInts(bad)
		if len(bad) > 5 {
			bad = bad[:5]
		}
		return 0, fmt.Errorf("map refers to frames outside 1..%d: %v", nSrc, bad)
	}

	if _, err := BuildFrames(s, src, outdir, m.Box, true, ext == ".png", log); err != nil {
		return 0, err
	}

	fdir := framesDir(outdir)
	staging := filepath.Join(outdir, "frames.restoring")
	_ = os.RemoveAll(staging)
	if err := os.MkdirAll(staging, 0o755); err != nil {
		return 0, err
	}
	defer os.RemoveAll(staging)
	// Built into a temp directory and swapped in, so a failure part way through
	// cannot leave a half-renumbered frames/ behind.
	for i, srcF := range target {
		pixels, err := os.ReadFile(framePath(fdir, srcF, ext))
		if err != nil {
			return 0, err
		}
		if err := os.WriteFile(framePath(staging, i+1, ext), pixels, 0o644); err != nil {
			return 0, err
		}
	}
	if err := os.RemoveAll(fdir); err != nil {
		return 0, err
	}
	if err := os.Rename(staging, fdir); err != nil {
		return 0, err
	}

	m, err = LoadMeta(outdir)
	if err != nil {
		return 0, err
	}
	m.FrameMap = append([]int(nil), target...)
	m.NbFrames = len(target)
	m.Duration = float64(len(target)) / m.FPS
	m.Edited = !isIdentity(target, nSrc)
	if err := SaveMeta(outdir, m); err != nil {
		return 0, err
	}
	if err := WriteViewer(outdir, m); err != nil {
		return 0, err
	}
	return len(target), nil
}

// Run is one piece of a rebuild, as GroupFrameRuns sees it.
//
//	kind "cut"  — a contiguous ascending run: cut straight from the source
//	kind "hold" — a repeated value (a duplicate): that one source frame, held
type Run struct {
	Kind string
	A    int // cut: first source frame.  hold: the source frame to hold
	B    int // cut: last source frame.   hold: how many frames to hold it
}

// GroupFrameRuns turns a slice of frame_map values into the pieces a rebuild
// can build directly.
//
// A jump that is neither +1 nor a repeat — a deletion — just ends one cut run
// and starts the next. Nothing special has to happen for it: the deleted source
// frames are simply never referenced.
//
// An unedited segment collapses to a single "cut", the exact shape this
// produced before frame editing existed.
func GroupFrameRuns(seq []int) []Run {
	var runs []Run
	i, n := 0, len(seq)
	for i < n {
		j := i
		if j+1 < n && seq[j+1] == seq[j] {
			for j+1 < n && seq[j+1] == seq[j] {
				j++
			}
			runs = append(runs, Run{"hold", seq[i], j - i + 1})
		} else {
			for j+1 < n && seq[j+1] == seq[j]+1 {
				j++
			}
			runs = append(runs, Run{"cut", seq[i], seq[j]})
		}
		i = j + 1
	}
	return runs
}

// ── small helpers ───────────────────────────────────────────────────────────

func insertInts(s []int, at int, vals []int) []int {
	out := make([]int, 0, len(s)+len(vals))
	out = append(out, s[:at]...)
	out = append(out, vals...)
	out = append(out, s[at:]...)
	return out
}

func repeat(v, n int) []int {
	out := make([]int, n)
	for i := range out {
		out[i] = v
	}
	return out
}

func uniqueInts(s []int) []int {
	out := s[:0]
	for i, v := range s {
		if i == 0 || v != s[i-1] {
			out = append(out, v)
		}
	}
	return out
}

func isIdentity(s []int, n int) bool {
	if len(s) != n {
		return false
	}
	for i, v := range s {
		if v != i+1 {
			return false
		}
	}
	return true
}

func isDir(p string) bool  { fi, err := os.Stat(p); return err == nil && fi.IsDir() }
func isFile(p string) bool { fi, err := os.Stat(p); return err == nil && !fi.IsDir() }
