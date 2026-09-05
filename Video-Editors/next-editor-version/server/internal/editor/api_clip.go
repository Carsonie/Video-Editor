package editor

// The endpoints that write REAL FILES — cut, save, the two resets, the
// splitter's hand-off, and the generation archive.
//
// Every one of them archives before it overwrites. That is the whole safety
// story here: none of these can be undone from the editor, so all of them have
// to be undoable from disk.

import (
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
)

// apiCut cuts the ORIGINAL source video at every marked frame, FRAME-EDITOR-
// AWARE: each segment is built from `frame_map`, so a duplicate becomes a real
// held frame in the output and a deletion is really absent, not just hidden in
// the preview.
func (s *Server) apiCut(w http.ResponseWriter, rep *reply, p Payload) {
	outdir, ok := s.resolveOutdir(p.str("slug"), p.str("which"))
	if !ok {
		fail(w, rep, 400, "unknown slug")
		return
	}
	m, err := LoadMeta(outdir)
	if err != nil {
		fail(w, rep, 400, "unknown slug")
		return
	}
	marks := loadMarks(outdir)
	if len(marks) == 0 {
		fail(w, rep, 400, "no break points marked yet")
		return
	}
	src := m.Source
	if !isFile(src) {
		fail(w, rep, 500, "source no longer exists: %s", src)
		return
	}
	frameMap := GetFrameMap(m)

	destDir := deriveSegmentsDir(src)
	if err := os.MkdirAll(destDir, 0o755); err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	version := nextVersion(destDir)
	// An avatar cut stays a WebM. Writing Sarah's pieces as .mp4 would name them
	// correctly and strip the transparency they exist for.
	segExt := extFor(src)

	tmpDir, err := os.MkdirTemp("", "video_players_cut_")
	if err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	defer os.RemoveAll(tmpDir)

	boundaries := append([]int{1}, marks...)
	boundaries = append(boundaries, m.NbFrames+1)
	segments := []map[string]any{}
	for i := 0; i < len(boundaries)-1; i++ {
		startF, endF := boundaries[i], boundaries[i+1]-1
		if endF < startF {
			continue
		}
		durS := float64(endF-startF+1) / m.FPS
		name := fmt.Sprintf("Num_%d-v%d-segment%s", len(segments)+1, version, segExt)
		dst := filepath.Join(destDir, name)
		runs := GroupFrameRuns(frameMap[startF-1 : endF])
		edited := len(runs) > 1
		if errs, err := buildSegment(src, m.FPS, runs, dst, tmpDir); err != nil {
			segments = append(segments, map[string]any{"name": name, "error": tail(errs, 500)})
			continue
		}
		got, _ := probeFloat(dst, "duration", false, nil)
		var warning any
		if abs(got-durS) >= 0.15 {
			warning = fmt.Sprintf("wanted %.2fs, got %.2fs", durS, got)
		}
		segments = append(segments, map[string]any{
			"name": name, "start_frame": startF, "end_frame": endF,
			"duration_s": round3(got), "edited": edited, "warning": warning})
	}
	sendJSON(w, rep, map[string]any{
		"outdir": destDir, "version": version,
		"count": len(segments), "segments": segments}, 200)
}

// apiSave rebuilds the WHOLE current edited frame sequence and OVERWRITES the
// file this viewer opened.
//
// The confirmation naming the destination happens in the browser before this is
// ever called; by the time it is hit the user has already agreed.
func (s *Server) apiSave(w http.ResponseWriter, rep *reply, p Payload) {
	outdir, ok := s.resolveOutdir(p.str("slug"), p.str("which"))
	if !ok {
		fail(w, rep, 400, "unknown slug")
		return
	}
	m, err := LoadMeta(outdir)
	if err != nil {
		fail(w, rep, 400, "unknown slug")
		return
	}
	src := m.Source
	if !isFile(src) {
		fail(w, rep, 500, "source no longer exists: %s", src)
		return
	}
	frameMap := GetFrameMap(m)
	wantFrames := len(frameMap)

	tmpDir, err := os.MkdirTemp("", "video_players_save_")
	if err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	defer os.RemoveAll(tmpDir)

	built := filepath.Join(tmpDir, "built"+extFor(src))
	if errs, err := buildSegment(src, m.FPS, GroupFrameRuns(frameMap), built, tmpDir); err != nil {
		fail(w, rep, 500, "%s", tail(errs, 500))
		return
	}
	got, _ := probeFloat(built, "duration", false, nil)

	// Archived first, the same convention every other tool here follows before
	// an overwrite — so a bad save is one file move away from undone, even
	// though this endpoint does not offer to undo it.
	histDir := filepath.Join(filepath.Dir(src), ArchiveDir, time.Now().Format("20060102-150405"))
	if err := os.MkdirAll(histDir, 0o755); err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	archived := filepath.Join(histDir, filepath.Base(src))
	if err := copyFile(src, archived); err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	if err := copyFile(built, src); err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}

	// The source on disk is now the edited clip, so every edit this cache is
	// still holding has ALREADY been applied. Re-extract from what was just
	// written, and drop the marks with it.
	//
	// Without this the cache keeps describing the PRE-save file: `edited` stays
	// true, so Save re-arms and the page still reads as unsaved — which is
	// exactly how a landed save gets reported as "it didn't save" — and the
	// frame map keeps pointing at source frames the shortened file no longer
	// has, so a SECOND save would rebuild against the wrong frames and silently
	// write a wrong, shorter clip.
	//
	// alpha_png comes from the meta being REPLACED. An overlay re-extracted
	// without it comes back as flat JPEG: no alpha, and named .jpg while the
	// page asks for .png, so every overlay frame 404s and Sarah simply is not
	// there. This fires after every save of an overlay, which is worse.
	if _, err := BuildFrames(s, src, outdir, m.Box, true, m.Ext == ".png", s.log); err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	_ = saveMarks(outdir, nil)
	newMeta, err := LoadMeta(outdir)
	if err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}

	// VERIFY WHAT WAS WRITTEN, IN FRAMES. A rebuild seeks by time and each piece
	// rounds on its own, so an edited clip can come back short of the length
	// that was on screen: measured, an 89-frame preview wrote 87 — one frame
	// lost per cut. That is exactly the class of fault this whole tool exists to
	// catch, so a save says so instead of letting it pass.
	wrote := DecodedFrames(src, DecFor(src))
	var warning any
	if wrote >= 0 && wrote != wantFrames {
		warning = fmt.Sprintf("wrote %d frames, expected %d — the rebuild is "+
			"time-based and loses a frame per cut", wrote, wantFrames)
	}
	sendJSON(w, rep, map[string]any{
		"path": src, "archived_to": archived, "duration_s": round3(got),
		"nb_frames": newMeta.NbFrames, "frames_written": nilIfNeg(wrote),
		"frames_expected": wantFrames, "warning": warning}, 200)
}

// apiClearEdits resets this cache to exactly the state a first-ever Open
// produces. The SOURCE FILE is never touched, only the cache — the opposite of
// save, which writes the source and leaves the cache's edit state alone.
func (s *Server) apiClearEdits(w http.ResponseWriter, rep *reply, p Payload) {
	outdir, ok := s.resolveOutdir(p.str("slug"), p.str("which"))
	if !ok {
		fail(w, rep, 400, "unknown slug")
		return
	}
	m, err := LoadMeta(outdir)
	if err != nil {
		fail(w, rep, 400, "unknown slug")
		return
	}
	if !isFile(m.Source) {
		fail(w, rep, 500, "source no longer exists: %s", m.Source)
		return
	}
	// alpha_png carried over from the meta being replaced — the SAME trap save
	// has. Without it an overlay comes back as flat JPEG and every overlay frame
	// 404s, so the avatar vanishes and only the background shows through.
	if _, err := BuildFrames(s, m.Source, outdir, m.Box, true, m.Ext == ".png", s.log); err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	_ = saveMarks(outdir, nil)
	newMeta, err := LoadMeta(outdir)
	if err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	sendJSON(w, rep, map[string]any{"nb_frames": newMeta.NbFrames}, 200)
}

// apiResetEditor unloads this video from the tool entirely: the whole cache
// directory goes, viewer page included. The SOURCE FILE named inside meta.json
// is never touched or even opened here; only the regenerable cache goes.
//
// Distinct from clear-edits: that keeps the video loaded and discards edits,
// this unloads the video.
func (s *Server) apiResetEditor(w http.ResponseWriter, rep *reply, p Payload) {
	outdir, ok := s.resolveOutdir(p.str("slug"), p.str("which"))
	if !ok {
		fail(w, rep, 400, "unknown slug")
		return
	}
	_ = os.RemoveAll(outdir)
	sendJSON(w, rep, map[string]any{"ok": true}, 200)
}

var nameRE = regexp.MustCompile(`^[a-z0-9][a-z0-9-]{0,48}$`)

// apiHandoff hands a cut's segments over to dev/, named.
//
// The splitter writes dev/_cuts/Num_3-v1-segment.mp4; naming it here makes it
// dev/03-catalogue-search/segment-v1.mp4 — a scene, and the starting point of a
// video. That scene row in script.json is what makes it a scene rather than a
// loose file.
//
// dev holds ONE generation. Depositing archives the one before it and starts the
// numbering again at 1, so what is in dev is always exactly the cut you last
// made, not a pile of them.
//
// COPIES out of _cuts, never moves. _cuts is the versioned record of what the
// splitter produced, and a second attempt at naming has to stay possible.
func (s *Server) apiHandoff(w http.ResponseWriter, rep *reply, p Payload) {
	outdir, ok := s.resolveOutdir(p.str("slug"), p.str("which"))
	if !ok {
		fail(w, rep, 400, "unknown slug")
		return
	}
	m, err := LoadMeta(outdir)
	if err != nil {
		fail(w, rep, 400, "this clip has no extraction to hand off")
		return
	}
	src := m.Source
	if src == "" || !isFile(src) {
		fail(w, rep, 400, "source no longer exists: %s", src)
		return
	}
	cutsDir := deriveSegmentsDir(src)
	if !isDir(cutsDir) {
		fail(w, rep, 400, "nothing has been cut yet")
		return
	}
	// The video folder is the one holding sandbox/ — two up from _cuts.
	final := filepath.Dir(filepath.Dir(cutsDir))

	// deriveSegmentsDir falls back to "a dev beside the source" for a clip that
	// is not inside a store's videos/<name>/ tree. That is fine for CUTTING —
	// the pieces land next to what they came from — but a handoff there writes a
	// whole parallel mini-store: measured once as
	// sandbox/01-alpha-scene/sandbox/01-login-screen/ plus its own script.json,
	// reported as a success, with nothing where the editor looks. A scene only
	// means something inside a video folder, so this says no rather than
	// building a store nobody asked for.
	parent := filepath.Base(filepath.Dir(final))
	if parent != "videos" && filepath.Base(final) != "final" {
		fail(w, rep, 400, "this clip is not inside a store's videos/<name>/ folder, "+
			"so there is no video for these scenes to belong to. "+
			"Cutting still works; the pieces are in %s", cutsDir)
		return
	}

	version, ok := p.intOK("version")
	if !ok {
		fail(w, rep, 400, "version must be an integer")
		return
	}
	type found struct {
		num  int
		name string
	}
	var hits []found
	entries, _ := os.ReadDir(cutsDir)
	for _, e := range entries {
		mm := segmentNameRE.FindStringSubmatch(e.Name())
		if mm == nil {
			continue
		}
		if v, _ := strconv.Atoi(mm[2]); v == version {
			num, _ := strconv.Atoi(mm[1])
			hits = append(hits, found{num, e.Name()})
		}
	}
	sort.Slice(hits, func(i, j int) bool { return hits[i].num < hits[j].num })
	if len(hits) == 0 {
		fail(w, rep, 400, "no cut segments at version %d", version)
		return
	}

	names := p.strings("names")
	if len(names) != len(hits) {
		fail(w, rep, 400, "%d segments but %d name(s)", len(hits), len(names))
		return
	}
	seen := map[string]bool{}
	for _, nm := range names {
		if !nameRE.MatchString(nm) {
			fail(w, rep, 400, "bad name: %q — lower-case letters, digits and hyphens", nm)
			return
		}
		if seen[nm] {
			fail(w, rep, 400, "two segments cannot share a name")
			return
		}
		seen[nm] = true
	}

	scriptP := ScriptPath(final)
	doc, err := LoadScript(final)
	if err != nil {
		doc = Script{}
	}

	// A fresh cut REPLACES dev, it does not append to it. The generation it
	// replaces goes to dev/z_History/ first, with the script that described it,
	// because a scene list and the folders it names are only meaningful together.
	droot := DevRoot(final)
	if err := os.MkdirAll(droot, 0o755); err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	archived, err := ArchiveContents(droot, []string{"_cuts"}, true)
	if err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	if archived != "" && isFile(scriptP) {
		if err := os.Rename(scriptP, filepath.Join(archived, "script.json")); err == nil {
			delete(doc, "scenes")
		}
	}
	scenes := doc.Scenes()

	type plan struct {
		n    int
		name string
		dir  string
		src  string
	}
	var planned []plan
	for k, h := range hits {
		n := 1 + k
		d := filepath.Join(droot, fmt.Sprintf("%02d-%s", n, names[k]))
		// Checking the exact folder name is not enough: a scene is found by its
		// NN- PREFIX, so any folder already using that number wins the lookup and
		// the new scene is invisible while a different one answers to its number.
		var clash []string
		if isDir(droot) {
			es, _ := os.ReadDir(droot)
			rx := regexp.MustCompile(fmt.Sprintf(`^%02d(-|$)`, n))
			for _, e := range es {
				if rx.MatchString(e.Name()) && isDir(filepath.Join(droot, e.Name())) {
					clash = append(clash, e.Name())
				}
			}
		}
		if len(clash) > 0 {
			fail(w, rep, 400, "sandbox already has %s, so scene %d is taken. "+
				"The script and the folders disagree — fix that before handing off, "+
				"or these scenes cannot be found.", clash[0], n)
			return
		}
		planned = append(planned, plan{n, names[k], d, filepath.Join(cutsDir, h.name)})
	}

	if len(scenes) > 0 && isFile(scriptP) {
		hist := filepath.Join(final, ArchiveDir, "handoff")
		if os.MkdirAll(hist, 0o755) == nil {
			_ = copyFile(scriptP, filepath.Join(hist,
				fmt.Sprintf("script-%s.json", time.Now().Format("20060102-150405"))))
		}
	}

	made := []map[string]any{}
	for _, pl := range planned {
		if err := os.MkdirAll(pl.dir, 0o755); err != nil {
			fail(w, rep, 500, "%s", err)
			return
		}
		// dev's own convention: versioned filenames. A fresh deposit starts at
		// v1 — the generations above it live in z_History, not in the filename.
		base := "segment-v1.mp4"
		if IsAlpha(pl.src) {
			base = "avatar-v1.webm"
		}
		dst := filepath.Join(pl.dir, base)
		if err := copyFile(pl.src, dst); err != nil {
			fail(w, rep, 500, "%s", err)
			return
		}
		scenes = append(scenes, Scene{
			"n": pl.n, "label": pl.name, "line": "",
			"_line_todo": "written by the splitter's handoff; the line is still to write"})
		made = append(made, map[string]any{
			"n": pl.n, "label": pl.name, "folder": filepath.Base(pl.dir),
			"frames": nilIfNeg(DecodedFrames(dst, DecFor(dst)))})
	}

	doc.SetScenes(scenes)
	if err := SaveScript(final, doc); err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	sendJSON(w, rep, map[string]any{
		"handed_off": made, "first_n": 1, "scenes": len(scenes),
		"script": scriptP, "into": droot,
		"archived_to": nilIfEmpty(archived)}, 200)
}

// apiArchive snapshots a folder's generation into <folder>/z_History/<date>-v_N/.
//
// sandbox is COPIED and dev is MOVED — the one way the two differ. dev is
// replaced wholesale, so moving is right there; the sandbox is edited in place,
// one scene at a time, and moving it would take away the scenes this save is
// not touching.
//
// Called at a GENERATION boundary — "Save all scenes" — not on every single-scene
// save. The per-scene history inside each scene folder already answers "what did
// this clip look like before I saved it", and it costs one file; this answers
// "what did the whole sandbox look like before this batch", and a real sandbox is
// 80MB. One per batch is a record; one per click is a disk full of near-identical
// copies.
//
// `dry` asks what WOULD happen, so the editor's confirmation can name the
// destination before the user agrees to it rather than after.
func (s *Server) apiArchive(w http.ResponseWriter, rep *reply, p Payload) {
	// Two ways in, ONE rule. The editor knows the video folder and passes `root`;
	// the splitter knows only the clip it opened, so it passes `slug` and the
	// video folder is derived exactly as the handoff derives it. Deriving it a
	// second time in the page would be a second rule to keep in step, which is
	// how the folders drifted apart before.
	var final string
	if slug := p.str("slug"); slug != "" {
		outdir, ok := s.resolveOutdir(slug, p.str("which"))
		if !ok {
			fail(w, rep, 400, "unknown slug")
			return
		}
		m, err := LoadMeta(outdir)
		if err != nil {
			fail(w, rep, 400, "this clip has no extraction")
			return
		}
		cuts := deriveSegmentsDir(m.Source)
		final = filepath.Dir(filepath.Dir(cuts))
	} else {
		var ok bool
		final, ok = s.safeJoin(p.str("root"))
		if !ok {
			final = ""
		}
	}
	if final == "" || !isDir(final) {
		fail(w, rep, 400, "not a folder under Customers/: %s", p.str("root")+p.str("slug"))
		return
	}
	which := p.str("folder")
	if which == "" {
		which = "sandbox"
	}
	roots := map[string]string{"sandbox": SandboxRoot(final), "dev": DevRoot(final)}
	folder, ok := roots[which]
	if !ok {
		fail(w, rep, 400, "folder must be 'sandbox' or 'dev'")
		return
	}
	if !isDir(folder) {
		fail(w, rep, 400, "this video has no %s/ folder", which)
		return
	}
	keep := []string{"_cuts"}
	holds := ArchivableNames(folder, keep)
	if holds == nil {
		holds = []string{}
	}
	if p.boolOr("dry", false) {
		sendJSON(w, rep, map[string]any{
			"folder": folder, "would_archive": holds,
			"into":  filepath.Join(folder, ArchiveDir, ArchiveName(folder)),
			"empty": len(holds) == 0}, 200)
		return
	}
	if len(holds) == 0 {
		sendJSON(w, rep, map[string]any{
			"folder": folder, "archived_to": nil,
			"archived": []string{}, "empty": true}, 200)
		return
	}
	dest, err := ArchiveContents(folder, keep, which == "dev")
	if err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	sendJSON(w, rep, map[string]any{
		"folder": folder, "archived_to": dest, "archived": holds,
		"empty": false, "moved": which == "dev"}, 200)
}

func abs(f float64) float64 {
	if f < 0 {
		return -f
	}
	return f
}

func round3(f float64) float64 {
	return float64(int64(f*1000+0.5)) / 1000
}

var _ = strings.TrimSpace
