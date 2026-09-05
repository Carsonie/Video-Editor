package editor

// ONE place that knows where a help video's parts live — the Go port of
// shared/paths.py.
//
// Before this existed, nine tools each hardcoded `segments/`, `scenes/`,
// `sarah_clips/` and `video/`. Renaming anything meant finding all nine, and
// the two that were missed failed QUIETLY — a folder that no longer exists
// reads as "no files", which looks like an empty store rather than a broken
// path.
//
// TWO LAYOUTS, ON PURPOSE
//
//	FLAT (original)                 DEV (per scene)
//	final/segments/                 final/dev/05-dates-and-review/
//	  Num_5-v6-segment.mp4            segment-v6.mp4
//	final/scenes/                     narration-v1.webm
//	  sarah-scene-05-alpha.webm       avatar-v1.webm
//
// DEV is preferred and FLAT is the fallback, PER FILE, so a half-migrated store
// keeps working. A migration that must be finished in one go is a migration
// that gets abandoned halfway with nothing working.

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
)

var (
	segRE       = regexp.MustCompile(`^Num_(\d+)-v(\d+)-segment\.mp4$`)
	legacySegRE = regexp.MustCompile(`^segment-(\d+)(?:_\d+)?-(.+)\.mp4$`)
	devSegRE    = regexp.MustCompile(`^segment-v(\d+)\.mp4$`)
	devAvRE     = regexp.MustCompile(`^avatar-v(\d+)\.webm$`)
	devNarRE    = regexp.MustCompile(`^narration-v(\d+)\.webm$`)
	nonSlug     = regexp.MustCompile(`[^a-z0-9]+`)
)

// ArchiveDir — every folder that gets WRITTEN keeps its own, and each write
// that replaces a generation puts the old one there first.
const ArchiveDir = "z_History"

var archiveRE = regexp.MustCompile(`^(\d{4}-\d{2}-\d{2})-v_(\d+)$`)

// Scene is one row of video/script.json. The extra fields are carried through
// verbatim so a join or a split never silently drops a key some other tool in
// the pipeline reads.
type Scene map[string]any

func (s Scene) N() int {
	switch v := s["n"].(type) {
	case float64:
		return int(v)
	case int:
		return v
	}
	return -1
}

func (s Scene) Label() string {
	if v, ok := s["label"].(string); ok {
		return v
	}
	return ""
}

func (s Scene) Line() string {
	if v, ok := s["line"].(string); ok {
		return v
	}
	return ""
}

// Script is video/script.json, read as a map so unknown top-level keys survive
// a rewrite.
type Script map[string]any

func (d Script) Scenes() []Scene {
	raw, _ := d["scenes"].([]any)
	out := make([]Scene, 0, len(raw))
	for _, r := range raw {
		if m, ok := r.(map[string]any); ok {
			out = append(out, Scene(m))
		}
	}
	return out
}

func (d Script) SetScenes(s []Scene) {
	raw := make([]any, len(s))
	for i, x := range s {
		raw[i] = map[string]any(x)
	}
	d["scenes"] = raw
}

func ScriptPath(final string) string  { return filepath.Join(final, "video", "script.json") }
func VideoDir(final string) string    { return filepath.Join(final, "video") }
func DevRoot(final string) string     { return filepath.Join(final, "dev") }
func SandboxRoot(final string) string { return filepath.Join(final, "sandbox") }

func LoadScript(final string) (Script, error) {
	b, err := os.ReadFile(ScriptPath(final))
	if err != nil {
		return nil, err
	}
	var d Script
	if err := json.Unmarshal(b, &d); err != nil {
		return nil, err
	}
	return d, nil
}

func SaveScript(final string, d Script) error {
	b, err := json.MarshalIndent(d, "", "  ")
	if err != nil {
		return err
	}
	if err := os.MkdirAll(VideoDir(final), 0o755); err != nil {
		return err
	}
	return os.WriteFile(ScriptPath(final), b, 0o644)
}

// Slugify: 5, "dates-and-review" -> "05-dates-and-review". Zero-padded so a
// directory listing is already in scene order rather than 1, 10, 11, 2.
func Slugify(label string, n int) string {
	lab := strings.Trim(nonSlug.ReplaceAllString(strings.ToLower(label), "-"), "-")
	if lab == "" {
		return fmt.Sprintf("%02d", n)
	}
	return fmt.Sprintf("%02d-%s", n, lab)
}

// dirByNumber finds a scene folder by its NN- PREFIX rather than by name. The
// label is only a convenience for humans; matching on it would break the moment
// a scene is renamed in script.json, which has happened twice.
func dirByNumber(root string, n int) string {
	if !isDir(root) {
		return ""
	}
	entries, _ := os.ReadDir(root)
	names := make([]string, 0, len(entries))
	for _, e := range entries {
		names = append(names, e.Name())
	}
	sort.Strings(names)
	rx := regexp.MustCompile(fmt.Sprintf(`^%02d(-|$)`, n))
	for _, name := range names {
		if rx.MatchString(name) && isDir(filepath.Join(root, name)) {
			return filepath.Join(root, name)
		}
	}
	return ""
}

func SandboxDir(final string, n int, label string) string {
	if d := dirByNumber(SandboxRoot(final), n); d != "" {
		return d
	}
	return filepath.Join(SandboxRoot(final), Slugify(label, n))
}

func SceneDir(final string, n int, label string) string {
	if d := dirByNumber(DevRoot(final), n); d != "" {
		return d
	}
	return filepath.Join(DevRoot(final), Slugify(label, n))
}

// sandboxFile — the first of `names` present in this scene's sandbox folder.
//
// Sandbox files carry NO version. They are yours, they are the newest thing you
// did, and versioning them would only invite the question this whole layer
// exists to avoid — which of my edits is the build using.
func sandboxFile(final string, n int, label string, names ...string) string {
	sd := SandboxDir(final, n, label)
	for _, nm := range names {
		p := filepath.Join(sd, nm)
		if isFile(p) {
			return p
		}
	}
	return ""
}

func newestVersioned(dir string, rx *regexp.Regexp) (string, int) {
	if !isDir(dir) {
		return "", -1
	}
	entries, _ := os.ReadDir(dir)
	best, bestV := "", -1
	for _, e := range entries {
		m := rx.FindStringSubmatch(e.Name())
		if m == nil {
			continue
		}
		if v, _ := strconv.Atoi(m[1]); v > bestV {
			best, bestV = filepath.Join(dir, e.Name()), v
		}
	}
	return best, bestV
}

// SandboxParts — this scene's parts in the SANDBOX, or "" for each. NO fallback
// to dev.
//
// The editor uses this rather than the resolving lookups: everything it reads
// and writes stays in sandbox/, and dev/ is the untouched copy. Returning
// nothing for a missing part is the POINT — the editor must SHOW the gap rather
// than quietly fall through to dev and let an edit appear to work.
type SandboxParts struct {
	Segment   string
	Narration string
	Avatar    string
}

func SandboxOnly(final string, n int, label string) SandboxParts {
	return SandboxParts{
		Segment:   sandboxFile(final, n, label, "segment.mp4", "segment.mov"),
		Narration: sandboxFile(final, n, label, "narration.webm"),
		Avatar:    sandboxFile(final, n, label, "avatar.webm"),
	}
}

// SourceOf — which layer a resolved path came from: sandbox, dev or flat.
//
// Every tool that BUILDS something must report this. A sandbox file silently
// entering a finished video is the one failure this layer could introduce, and
// it would be invisible in the output: the video would just be different from
// the one the folder names imply.
func SourceOf(final, path string) string {
	if path == "" {
		return ""
	}
	ap, _ := filepath.Abs(path)
	if sb, _ := filepath.Abs(SandboxRoot(final)); strings.HasPrefix(ap, sb+string(os.PathSeparator)) {
		return "sandbox"
	}
	if dv, _ := filepath.Abs(DevRoot(final)); strings.HasPrefix(ap, dv+string(os.PathSeparator)) {
		return "dev"
	}
	return "flat"
}

// ScenesFromScript — [(n, label)] in scene order, from the store's own script.
type NLabel struct {
	N     int
	Label string
}

func ScenesFromScript(final string) []NLabel {
	d, err := LoadScript(final)
	if err != nil {
		return nil
	}
	var out []NLabel
	for _, s := range d.Scenes() {
		out = append(out, NLabel{s.N(), s.Label()})
	}
	return out
}

// Versions — every version on disk, so a caller can SHOW which are in play
// rather than assume they agree. They move independently, and a mismatch is
// invisible in the picture until the wrong voice plays.
func Versions(final string) map[string][]int {
	out := map[string][]int{"segment": {}, "avatar": {}, "script": {}}
	if root := DevRoot(final); isDir(root) {
		entries, _ := os.ReadDir(root)
		for _, e := range entries {
			sd := filepath.Join(root, e.Name())
			if !isDir(sd) {
				continue
			}
			files, _ := os.ReadDir(sd)
			for _, f := range files {
				if m := devSegRE.FindStringSubmatch(f.Name()); m != nil {
					v, _ := strconv.Atoi(m[1])
					out["segment"] = append(out["segment"], v)
				}
				if m := devAvRE.FindStringSubmatch(f.Name()); m != nil {
					v, _ := strconv.Atoi(m[1])
					out["avatar"] = append(out["avatar"], v)
				}
			}
		}
	}
	if flat := filepath.Join(final, "segments"); isDir(flat) {
		entries, _ := os.ReadDir(flat)
		for _, e := range entries {
			if m := segRE.FindStringSubmatch(e.Name()); m != nil {
				v, _ := strconv.Atoi(m[2])
				out["segment"] = append(out["segment"], v)
			}
		}
	}
	if ovr := filepath.Join(final, "sarah_clips", "scene_overlays"); isDir(ovr) {
		entries, _ := os.ReadDir(ovr)
		rx := regexp.MustCompile(`^v(\d+)$`)
		for _, e := range entries {
			if m := rx.FindStringSubmatch(e.Name()); m != nil {
				v, _ := strconv.Atoi(m[1])
				out["avatar"] = append(out["avatar"], v)
			}
		}
	}
	if vd := VideoDir(final); isDir(vd) {
		entries, _ := os.ReadDir(vd)
		rx := regexp.MustCompile(`^script_v(\d+)\.json$`)
		for _, e := range entries {
			if m := rx.FindStringSubmatch(e.Name()); m != nil {
				v, _ := strconv.Atoi(m[1])
				out["script"] = append(out["script"], v)
			}
		}
	}
	for k, v := range out {
		sort.Sort(sort.Reverse(sort.IntSlice(v)))
		out[k] = uniqueInts(v)
	}
	return out
}

// Layout — "dev", "flat" or "mixed", for a tool that wants to say which it found.
func Layout(final string) string {
	hasDev := false
	if root := DevRoot(final); isDir(root) {
		entries, _ := os.ReadDir(root)
		for _, e := range entries {
			if isDir(filepath.Join(root, e.Name())) {
				hasDev = true
				break
			}
		}
	}
	hasFlat := false
	if flat := filepath.Join(final, "segments"); isDir(flat) {
		entries, _ := os.ReadDir(flat)
		for _, e := range entries {
			if segRE.MatchString(e.Name()) {
				hasFlat = true
				break
			}
		}
	}
	switch {
	case hasDev && hasFlat:
		return "mixed"
	case hasDev:
		return "dev"
	default:
		return "flat"
	}
}

// ── generation archives ─────────────────────────────────────────────────────
//
// One archive per GENERATION, not per file. The per-file archives inside a
// scene folder answer "what did this clip look like before I saved it"; these
// answer "what did the whole folder look like before this batch", which is the
// question you have after a bad cut or a bad build.
//
// Named by DATE plus a sequence within that date: 2026-08-26-v_1, then v_2 the
// next time that day. A timestamp would sort correctly and read as noise; a
// bare sequence would sort correctly and say nothing. This says when, and which.

func ArchiveName(folder string) string {
	day := time.Now().Format("2006-01-02")
	root := filepath.Join(folder, ArchiveDir)
	seen := 0
	if isDir(root) {
		entries, _ := os.ReadDir(root)
		for _, e := range entries {
			if m := archiveRE.FindStringSubmatch(e.Name()); m != nil && m[1] == day {
				if v, _ := strconv.Atoi(m[2]); v > seen {
					seen = v
				}
			}
		}
	}
	return fmt.Sprintf("%s-v_%d", day, seen+1)
}

// ArchivableNames — what a generation archive of `folder` would take.
func ArchivableNames(folder string, keep []string) []string {
	if !isDir(folder) {
		return nil
	}
	skip := map[string]bool{ArchiveDir: true}
	for _, k := range keep {
		skip[k] = true
	}
	entries, _ := os.ReadDir(folder)
	var names []string
	for _, e := range entries {
		if skip[e.Name()] || strings.HasPrefix(e.Name(), ".") {
			continue
		}
		names = append(names, e.Name())
	}
	sort.Strings(names)
	return names
}

// ArchiveContents puts a folder's current generation into
// folder/z_History/<date>-v_N/.
//
// `move` decides which of the two shapes this is:
//
//	MOVE — the folder is being REPLACED wholesale, as when a fresh cut lands in
//	       dev/. Afterwards the folder is empty and the new work has it to
//	       itself, which is the point: dev holds one generation, not a pile.
//	COPY — the folder is being edited in place, as when the sandbox is saved.
//	       Moving would take away the scenes this save is not touching.
//
// Returns "" when there was nothing to archive. Doing nothing is the normal
// case for a first run and must not look like a failure.
func ArchiveContents(folder string, keep []string, move bool) (string, error) {
	names := ArchivableNames(folder, keep)
	if len(names) == 0 {
		return "", nil
	}
	dest := filepath.Join(folder, ArchiveDir, ArchiveName(folder))
	if err := os.MkdirAll(dest, 0o755); err != nil {
		return "", err
	}
	for _, x := range names {
		src, dst := filepath.Join(folder, x), filepath.Join(dest, x)
		if move {
			if err := os.Rename(src, dst); err != nil {
				return "", err
			}
			continue
		}
		if isDir(src) {
			if err := copyTree(src, dst); err != nil {
				return "", err
			}
		} else if err := copyFile(src, dst); err != nil {
			return "", err
		}
	}
	return dest, nil
}

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	if err := os.MkdirAll(filepath.Dir(dst), 0o755); err != nil {
		return err
	}
	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer out.Close()
	if _, err := io.Copy(out, in); err != nil {
		return err
	}
	// copy2 semantics: the archived file keeps the original's mtime, so an
	// archive reads as a snapshot of when the work was done, not of when it
	// was filed away.
	if fi, err := os.Stat(src); err == nil {
		_ = os.Chtimes(dst, fi.ModTime(), fi.ModTime())
	}
	return nil
}

func copyTree(src, dst string) error {
	return filepath.Walk(src, func(p string, fi os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		rel, err := filepath.Rel(src, p)
		if err != nil {
			return err
		}
		target := filepath.Join(dst, rel)
		if fi.IsDir() {
			return os.MkdirAll(target, 0o755)
		}
		return copyFile(p, target)
	})
}
