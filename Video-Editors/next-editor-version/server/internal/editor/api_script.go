package editor

// The endpoints that rewrite video/script.json.
//
// A scene is a folder of clips AND a row in that file carrying its narration
// line, and that file is read by nine tools in this pipeline INCLUDING the one
// that spends money on renders. So everything here archives the whole previous
// state before it writes, script.json included: a join is not reversible from
// the editor, so it has to be reversible from disk.

import (
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

// apiVTT — the VTT rows for a store. Video Timing Table, not WebVTT subtitles.
//
// Sends the LINES and the maths behind them; the clip length is left to the
// page, which knows what is actually on the timeline including edits that have
// not been saved yet. Reading the file on disk instead is right for a report and
// wrong for an editor — there, a gap that does not move while you add frames is
// just a lie with a decimal point.
func (s *Server) apiVTT(w http.ResponseWriter, req *http.Request, rep *reply) {
	rootRel := req.URL.Query().Get("root")
	final, ok := s.safeJoin(rootRel)
	if !ok || !isDir(final) {
		fail(w, rep, 400, "not a folder under Customers/: %s", rootRel)
		return
	}
	if !isFile(ScriptPath(final)) {
		fail(w, rep, 400, "this store has no video/script.json")
		return
	}
	doc, err := LoadScript(final)
	if err != nil {
		fail(w, rep, 400, "this store has no video/script.json")
		return
	}
	rows := []map[string]any{}
	for _, sc := range doc.Scenes() {
		line := sc.Line()
		pause := 0.0
		if raw, ok := sc["pauses"].([]any); ok {
			for _, x := range raw {
				if pm, ok := x.(map[string]any); ok {
					if v, ok := pm["seconds"].(float64); ok {
						pause += v
					}
				}
			}
		}
		_, todo := sc["_line_todo"]
		rows = append(rows, map[string]any{
			"n": sc.N(), "label": sc.Label(), "line": line,
			// `words` comes from the pipeline's own count rather than being
			// re-implemented: it drops tokens with no letter or digit, because a
			// spaced em dash is not spoken and counting it added 0.29s to every
			// line that had one.
			"words": Words(line), "pause": pause, "todo": todo,
		})
	}
	wps := 3.44
	if v, ok := doc["words_per_second"].(float64); ok {
		wps = v
	}
	sendJSON(w, rep, map[string]any{
		"wps": wps, "store": strOf(doc["store"]), "title": strOf(doc["title"]),
		"scenes": rows}, 200)
}

// apiLine rewrites ONE scene's narration line.
//
// script.json is the single source of truth for the copy, and the render tool
// reads the same field — so editing a line here is editing what HeyGen will be
// paid to say. The previous script is copied to z_History/line-edits/ first.
// They are a few kB each and the whole reason to edit copy in the player is to
// try wordings, so the cheap thing to keep is the trail of what it used to be.
//
// Clearing `_line_todo` is deliberate: a split leaves that marker on the half
// with no line, and the marker's whole job is done the moment someone writes one.
func (s *Server) apiLine(w http.ResponseWriter, rep *reply, p Payload) {
	final, ok := s.safeJoin(p.str("root"))
	if !ok || !isDir(final) {
		fail(w, rep, 400, "not a folder under Customers/: %s", p.str("root"))
		return
	}
	n, ok := p.intOK("n")
	if !ok {
		fail(w, rep, 400, "n must be an integer")
		return
	}
	raw, ok := p["line"].(string)
	if !ok {
		fail(w, rep, 400, "line must be text")
		return
	}
	line := strings.Join(strings.Fields(raw), " ")
	scriptP := ScriptPath(final)
	if !isFile(scriptP) {
		fail(w, rep, 400, "this store has no video/script.json")
		return
	}
	doc, err := LoadScript(final)
	if err != nil {
		fail(w, rep, 400, "this store has no video/script.json")
		return
	}
	scenes := doc.Scenes()
	var node Scene
	for _, sc := range scenes {
		if sc.N() == n {
			node = sc
			break
		}
	}
	if node == nil {
		fail(w, rep, 400, "scene %d is not in the script", n)
		return
	}
	if node.Line() == line {
		sendJSON(w, rep, map[string]any{
			"n": n, "line": line, "words": Words(line), "unchanged": true}, 200)
		return
	}
	hist := filepath.Join(final, ArchiveDir, "line-edits")
	if os.MkdirAll(hist, 0o755) == nil {
		_ = copyFile(scriptP, filepath.Join(hist,
			fmt.Sprintf("script-%s.json", time.Now().Format("20060102-150405"))))
	}
	node["line"] = line
	delete(node, "_line_todo")
	if err := SaveScript(final, doc); err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	sendJSON(w, rep, map[string]any{"n": n, "line": line, "words": Words(line)}, 200)
}

// apiJoin joins several scenes into one, in the store's sandbox.
//
// WHAT THIS TOUCHES, because it is more than media:
//
//   - concatenates the segments, and the avatars, in scene order
//   - joins the narration lines with a space, in the same order
//   - writes ONE new sandbox folder for the result
//   - renumbers EVERY scene in the script, because a join leaves a hole and
//     downstream tools index by `n`
//   - archives the whole previous state first
//
// Concatenation is done on the FILES, by stream copy, so joining does not add a
// generation of re-encoding to footage that has already been through one.
func (s *Server) apiJoin(w http.ResponseWriter, rep *reply, p Payload) {
	final, ok := s.safeJoin(p.str("root"))
	if !ok || !isDir(final) {
		fail(w, rep, 400, "not a folder under Customers/: %s", p.str("root"))
		return
	}
	ns, _ := p.ints("ns")
	label := strings.TrimSpace(p.str("label"))
	tracks := p.strings("tracks")
	if len(tracks) == 0 {
		tracks = []string{"segment", "avatar"}
	}
	if len(ns) < 2 {
		fail(w, rep, 400, "a join needs at least two scenes")
		return
	}
	if !nameRE.MatchString(label) {
		fail(w, rep, 400, "name must be lower-case letters, digits and hyphens")
		return
	}
	scriptP := ScriptPath(final)
	if !isFile(scriptP) {
		fail(w, rep, 400, "this store has no video/script.json")
		return
	}
	doc, err := LoadScript(final)
	if err != nil {
		fail(w, rep, 400, "this store has no video/script.json")
		return
	}
	scenes := doc.Scenes()
	byN := map[int]Scene{}
	for _, sc := range scenes {
		byN[sc.N()] = sc
	}
	var missing []int
	want := map[int]bool{}
	for _, n := range ns {
		if _, ok := byN[n]; !ok {
			missing = append(missing, n)
		}
		want[n] = true
	}
	if len(missing) > 0 {
		fail(w, rep, 400, "not scenes in the script: %v", missing)
		return
	}

	// In SCRIPT order, not the order they were clicked: the join is a splice of
	// the video's own sequence, and any other order would silently reorder the
	// narration.
	var order []int
	for _, sc := range scenes {
		if want[sc.N()] {
			order = append(order, sc.N())
		}
	}
	type part struct {
		n                          int
		segment, avatar, narration string
	}
	var parts []part
	for _, n := range order {
		sb := SandboxOnly(final, n, byN[n].Label())
		if sb.Segment == "" {
			fail(w, rep, 400, "scene %d has no segment in sandbox", n)
			return
		}
		parts = append(parts, part{n, sb.Segment, sb.Avatar, sb.Narration})
	}

	// A track some scenes have and others do not. Two ways this can go, and the
	// difference is the whole point: dropping it SILENTLY moves every later clip
	// forward — the opening has no narration, so scene 2's would start at frame 1
	// and Sarah would say the login line over the intro. Filling the gap holds
	// that time open instead.
	fill := p.boolOr("fill_gaps", false)
	type gap struct {
		which   string
		missing []int
		like    string
	}
	var gaps []gap
	if contains(tracks, "avatar") {
		for _, spec := range []struct {
			what string
			get  func(part) string
		}{
			{"avatar", func(x part) string { return x.avatar }},
			{"narration", func(x part) string { return x.narration }},
		} {
			var miss []int
			present := ""
			for _, x := range parts {
				if spec.get(x) == "" {
					miss = append(miss, x.n)
				} else if present == "" {
					present = spec.get(x)
				}
			}
			if len(miss) == 0 || present == "" {
				continue
			}
			if !fill {
				var names []string
				for _, n := range miss {
					names = append(names, fmt.Sprint(n))
				}
				sendJSON(w, rep, map[string]any{
					"error": fmt.Sprintf("scene(s) %s have no %s and the others do. "+
						"Joining as-is would move every later %s forward. Send fill_gaps "+
						"to hold that time open with a transparent silent clip instead.",
						strings.Join(names, ", "), spec.what, spec.what),
					"gap":            spec.what,
					"scenes_missing": miss}, 400)
				return
			}
			gaps = append(gaps, gap{spec.what, miss, present})
		}
	}

	stamp := time.Now().Format("20060102-150405")
	hist := filepath.Join(final, ArchiveDir, "join-"+stamp)
	if err := os.MkdirAll(hist, 0o755); err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	if err := copyFile(scriptP, filepath.Join(hist, "script.json")); err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}

	first := order[0]
	newDir := filepath.Join(SandboxRoot(final), fmt.Sprintf("%02d-%s", first, label))
	tmpDir, err := os.MkdirTemp("", "video_players_join_")
	if err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	defer os.RemoveAll(tmpDir)

	filled := []map[string]any{}
	// Each gap gets a filler as long as that SCENE is — measured on its segment,
	// which is the scene's true duration. Built before the concat so the parts
	// list is complete when it runs.
	for _, g := range gaps {
		inMiss := map[int]bool{}
		for _, n := range g.missing {
			inMiss[n] = true
		}
		for k := range parts {
			if !inMiss[parts[k].n] {
				continue
			}
			nFrames := DecodedFrames(parts[k].segment, DecFor(parts[k].segment))
			dst := filepath.Join(tmpDir, fmt.Sprintf("fill_%s_%d.webm", g.which, parts[k].n))
			if err := makeGapFiller(g.like, nFrames, dst); err != nil {
				fail(w, rep, 500, "%s", err)
				return
			}
			if g.which == "avatar" {
				parts[k].avatar = dst
			} else {
				parts[k].narration = dst
			}
			filled = append(filled, map[string]any{
				"scene": parts[k].n, "track": g.which, "frames": nFrames})
		}
	}

	// narration.webm rides with the AVATAR, and is not separately choosable,
	// because it is what the avatar was rendered from — the build composites the
	// narration, not the avatar. Left behind, the joined scene had no narration
	// of its own and the lookup fell back to dev/, quietly handing the build the
	// PRE-JOIN narration of the first half only. No error, just a different video
	// from the one the folder names imply.
	for _, spec := range []struct {
		kind, needs string
		get         func(part) string
	}{
		{"segment.mp4", "segment", func(x part) string { return x.segment }},
		{"avatar.webm", "avatar", func(x part) string { return x.avatar }},
		{"narration.webm", "avatar", func(x part) string { return x.narration }},
	} {
		if !contains(tracks, spec.needs) {
			continue // a track not chosen is not carried over
		}
		var srcs []string
		for _, x := range parts {
			if v := spec.get(x); v != "" {
				srcs = append(srcs, v)
			}
		}
		if len(srcs) == 0 {
			continue
		}
		lst := filepath.Join(tmpDir, spec.kind+".txt")
		var sb strings.Builder
		for _, x := range srcs {
			a, _ := filepath.Abs(x)
			fmt.Fprintf(&sb, "file '%s'\n", a)
		}
		if err := os.WriteFile(lst, []byte(sb.String()), 0o644); err != nil {
			fail(w, rep, 500, "%s", err)
			return
		}
		out := filepath.Join(tmpDir, spec.kind)
		if _, errs, err := run("ffmpeg", "-v", "error", "-f", "concat", "-safe", "0",
			"-i", lst, "-c", "copy", "-y", out); err != nil {
			fail(w, rep, 500, "joining %s: %s", spec.kind, tail(errs, 400))
			return
		}
	}

	// Archive every folder being consumed, THEN put the new one in place.
	for _, x := range parts {
		d := filepath.Dir(x.segment)
		_ = copyTree(d, filepath.Join(hist, filepath.Base(d)))
	}
	for _, x := range parts {
		_ = os.RemoveAll(filepath.Dir(x.segment))
	}
	if err := os.MkdirAll(newDir, 0o755); err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	for _, kind := range []string{"segment.mp4", "avatar.webm", "narration.webm"} {
		built := filepath.Join(tmpDir, kind)
		if isFile(built) {
			if err := copyFile(built, filepath.Join(newDir, kind)); err != nil {
				fail(w, rep, 500, "%s", err)
				return
			}
		}
	}

	var lines []string
	var joinedFrom []any
	for _, n := range order {
		if l := strings.TrimSpace(byN[n].Line()); l != "" {
			lines = append(lines, l)
		}
		joinedFrom = append(joinedFrom, map[string]any{"n": n, "label": byN[n].Label()})
	}
	joined := Scene{
		"n": first, "label": label,
		"line":         strings.TrimSpace(strings.Join(lines, " ")),
		"_joined_from": joinedFrom,
		"_joined_on":   stamp,
	}
	kept := []Scene{}
	for _, sc := range scenes {
		if !want[sc.N()] {
			kept = append(kept, sc)
		}
	}
	kept = append(kept, joined)
	sort.SliceStable(kept, func(i, j int) bool { return kept[i].N() < kept[j].N() })

	renum := renumber(kept)
	doc.SetScenes(kept)
	renamed := renumberSandboxFolders(final, kept)
	doc["_join_note"] = fmt.Sprintf("%s: joined scenes %v into '%s'. Every scene "+
		"renumbered sequentially. Previous state in z_History/join-%s/.",
		stamp, order, label, stamp)
	if err := SaveScript(final, doc); err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	sendJSON(w, rep, map[string]any{
		"joined": order, "label": label, "new_n": joined.N(),
		"renamed": renamed, "filled": filled, "renumbered": renum,
		"scenes": len(kept), "archived_to": relTo(s.Customers, hist)}, 200)
}

// apiSplit splits one scene in two at a frame.
//
// The counterpart to join and it costs the same: two new folders, script.json
// rewritten, every scene renumbered, and the previous state archived first.
//
// The cut is FRAME-ACCURATE. `-frames:v` for the head and `-ss` on the frame
// boundary for the tail, never a duration cutoff — the same rule the rebuild had
// to learn, for the same reason: a duration drops the frame that ends on the
// boundary, and here that frame would simply vanish from the video rather than
// being in one half or the other.
//
// THE NARRATION CANNOT BE SPLIT AUTOMATICALLY. A line belongs to a whole
// thought, not to a frame count, so the whole line stays with the FIRST half and
// the second is left empty for a human to write.
func (s *Server) apiSplit(w http.ResponseWriter, rep *reply, p Payload) {
	final, ok := s.safeJoin(p.str("root"))
	if !ok || !isDir(final) {
		fail(w, rep, 400, "not a folder under Customers/: %s", p.str("root"))
		return
	}
	n, nok := p.intOK("n")
	at, aok := p.intOK("at")
	if !nok || !aok {
		fail(w, rep, 400, "n and at must be integers")
		return
	}
	names := p.strings("labels")
	tracks := p.strings("tracks")
	if len(tracks) == 0 {
		tracks = []string{"segment", "avatar"}
	}
	if len(names) != 2 {
		fail(w, rep, 400, "two names are needed, one per half")
		return
	}
	for _, nm := range names {
		if !nameRE.MatchString(nm) {
			fail(w, rep, 400, "bad name: %q", nm)
			return
		}
	}
	if names[0] == names[1] {
		fail(w, rep, 400, "the two halves need different names")
		return
	}
	scriptP := ScriptPath(final)
	if !isFile(scriptP) {
		fail(w, rep, 400, "this store has no video/script.json")
		return
	}
	doc, err := LoadScript(final)
	if err != nil {
		fail(w, rep, 400, "this store has no video/script.json")
		return
	}
	scenes := doc.Scenes()
	var node Scene
	for _, sc := range scenes {
		if sc.N() == n {
			node = sc
			break
		}
	}
	if node == nil {
		fail(w, rep, 400, "scene %d is not in the script", n)
		return
	}

	sb := SandboxOnly(final, n, node.Label())
	srcs := map[string]string{
		"segment": sb.Segment, "avatar": sb.Avatar, "narration": sb.Narration}
	// narration.webm is cut wherever the avatar is, for the same reason the join
	// carries it: it is the render the avatar came from and what the build
	// actually composites. It is not separately choosable.
	needs := map[string]string{"segment": "segment", "avatar": "avatar", "narration": "avatar"}
	var chosen []string
	for _, t := range []string{"segment", "avatar", "narration"} {
		if contains(tracks, needs[t]) && srcs[t] != "" {
			chosen = append(chosen, t)
		}
	}
	if len(chosen) == 0 {
		fail(w, rep, 400, "none of the chosen tracks exist on that scene")
		return
	}

	// Every chosen track is measured and the cut point checked BEFORE a single
	// byte is written. The two tracks are routinely different lengths — a
	// 190-frame segment under a 152-frame avatar is normal — so a frame that is
	// fine for one can be off the end of the other. Checked late, the refusal
	// still left an archive behind for a split that never happened, which reads
	// afterwards as if it had.
	type sizes struct {
		fps   float64
		total int
	}
	plan := map[string]sizes{}
	for _, t := range chosen {
		src := srcs[t]
		fps, err := probeRate(src, nil)
		if err != nil {
			fail(w, rep, 500, "%s", err)
			return
		}
		total := DecodedFrames(src, DecFor(src))
		if total < 0 || !(1 < at && at <= total) {
			fail(w, rep, 400, "frame %d is not inside %s (1..%d)", at, t, total)
			return
		}
		plan[t] = sizes{fps, total}
	}

	stamp := time.Now().Format("20060102-150405")
	hist := filepath.Join(final, ArchiveDir, "split-"+stamp)
	if err := os.MkdirAll(hist, 0o755); err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	if err := copyFile(scriptP, filepath.Join(hist, "script.json")); err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	oldDir := filepath.Dir(srcs[chosen[0]])
	_ = copyTree(oldDir, filepath.Join(hist, filepath.Base(oldDir)))

	tmpDir, err := os.MkdirTemp("", "video_players_split_")
	if err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	defer os.RemoveAll(tmpDir)

	made := []map[string]string{{}, {}}
	for _, t := range chosen {
		src := srcs[t]
		sz := plan[t]
		dec, enc, ext := DecFor(src), encFor(src), extFor(src)
		head := filepath.Join(tmpDir, t+"_a"+ext)
		tailP := filepath.Join(tmpDir, t+"_b"+ext)

		args := append([]string{"-v", "error"}, dec...)
		args = append(args, "-i", src, "-frames:v", fmt.Sprint(at-1))
		args = append(args, enc...)
		args = append(args, "-y", head)
		if _, errs, err := run("ffmpeg", args...); err != nil {
			fail(w, rep, 500, "splitting %s head: %s", t, tail(errs, 300))
			return
		}
		args = append([]string{"-v", "error"}, dec...)
		args = append(args, "-ss", fmt.Sprintf("%.6f", float64(at-1)/sz.fps), "-i", src,
			"-frames:v", fmt.Sprint(sz.total-at+1))
		args = append(args, enc...)
		args = append(args, "-y", tailP)
		if _, errs, err := run("ffmpeg", args...); err != nil {
			fail(w, rep, 500, "splitting %s tail: %s", t, tail(errs, 300))
			return
		}
		made[0][t] = head
		made[1][t] = tailP
	}

	_ = os.RemoveAll(oldDir)
	for half := 0; half < 2; half++ {
		d := filepath.Join(SandboxRoot(final), fmt.Sprintf("%02d-%s", n, names[half]))
		if err := os.MkdirAll(d, 0o755); err != nil {
			fail(w, rep, 500, "%s", err)
			return
		}
		for t, built := range made[half] {
			if err := copyFile(built, filepath.Join(d, TrackFile[t])); err != nil {
				fail(w, rep, 500, "%s", err)
				return
			}
		}
	}

	headNode := Scene{}
	for k, v := range node {
		headNode[k] = v
	}
	headNode["label"] = names[0]
	headNode["line"] = node.Line()
	headNode["_split_on"] = stamp
	headNode["_split_at"] = at
	tailNode := Scene{
		"n": node.N(), "label": names[1], "line": "",
		"_split_on": stamp, "_split_from": node.Label(),
		"_line_todo": "the narration stayed with the first half; write this one"}

	out := []Scene{}
	for _, sc := range scenes {
		if sc.N() == n {
			out = append(out, headNode, tailNode)
		} else {
			out = append(out, sc)
		}
	}
	renum := renumber(out)
	doc.SetScenes(out)
	renamed := renumberSandboxFolders(final, out)
	doc["_split_note"] = fmt.Sprintf("%s: split scene %d at frame %d into '%s' and "+
		"'%s'. Tracks: %s. Every scene renumbered. Previous state in "+
		"z_History/split-%s/.", stamp, n, at, names[0], names[1],
		strings.Join(chosen, ", "), stamp)
	if err := SaveScript(final, doc); err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	sendJSON(w, rep, map[string]any{
		"split": n, "at": at, "labels": names, "tracks": chosen,
		"renamed": renamed, "renumbered": renum, "scenes": len(out),
		"line_stayed_with": names[0],
		"archived_to":      relTo(s.Customers, hist)}, 200)
}

// apiRenumberState — has this store been renumbered since it was last saved as
// a set?
//
// Read from script.json rather than remembered in the page. A join or a split
// RELOADS the timeline, so a flag held in JavaScript dies at exactly the moment
// it starts mattering — the rule it enforces would be gone one navigation after
// the renumber that caused it.
func (s *Server) apiRenumberState(w http.ResponseWriter, req *http.Request, rep *reply) {
	final, ok := s.safeJoin(req.URL.Query().Get("root"))
	if !ok || !isDir(final) {
		fail(w, rep, 400, "not a folder under Customers/")
		return
	}
	if !isFile(ScriptPath(final)) {
		sendJSON(w, rep, map[string]any{"renumbered": false, "moved": []any{}}, 200)
		return
	}
	doc, err := LoadScript(final)
	if err != nil {
		sendJSON(w, rep, map[string]any{"renumbered": false, "moved": []any{}}, 200)
		return
	}
	moved := []any{}
	for _, sc := range doc.Scenes() {
		if was, ok := sc["_was_n"]; ok {
			moved = append(moved, map[string]any{"from": plain(was), "to": sc.N()})
		}
	}
	sendJSON(w, rep, map[string]any{"renumbered": len(moved) > 0, "moved": moved}, 200)
}

// apiRenumberClear drops the `_was_n` markers — the set has been written, so the
// numbers on disk and the numbers in the script agree again.
func (s *Server) apiRenumberClear(w http.ResponseWriter, rep *reply, p Payload) {
	final, ok := s.safeJoin(p.str("root"))
	if !ok || !isDir(final) {
		fail(w, rep, 400, "not a folder under Customers/")
		return
	}
	if !isFile(ScriptPath(final)) {
		fail(w, rep, 400, "no script.json")
		return
	}
	doc, err := LoadScript(final)
	if err != nil {
		fail(w, rep, 400, "no script.json")
		return
	}
	cleared := 0
	for _, sc := range doc.Scenes() {
		if _, ok := sc["_was_n"]; ok {
			delete(sc, "_was_n")
			cleared++
		}
	}
	if cleared > 0 {
		if err := SaveScript(final, doc); err != nil {
			fail(w, rep, 500, "%s", err)
			return
		}
	}
	sendJSON(w, rep, map[string]any{"cleared": cleared}, 200)
}

// renumber puts the scene list back to 1..N with no gaps, marking every scene
// whose number moved. A join leaves a hole and a split adds one, and `n` is what
// the rest of the pipeline indexes by.
func renumber(scenes []Scene) []any {
	moved := []any{}
	for i, sc := range scenes {
		want := i + 1
		if sc.N() != want {
			sc["_was_n"] = sc.N()
			moved = append(moved, map[string]any{"from": sc.N(), "to": want})
		}
		sc["n"] = want
	}
	return moved
}

func contains(list []string, v string) bool {
	for _, x := range list {
		if x == v {
			return true
		}
	}
	return false
}

func strOf(v any) string {
	if s, ok := v.(string); ok {
		return s
	}
	return ""
}
