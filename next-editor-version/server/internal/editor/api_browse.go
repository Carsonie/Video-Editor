package editor

// The ways IN: browsing Customers/, opening a clip, and the two multi-clip
// views the Segment and Avatar Editor is built on.

import (
	"crypto/sha1"
	"encoding/hex"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
)

func (s *Server) apiList(w http.ResponseWriter, req *http.Request, rep *reply) {
	rel := req.URL.Query().Get("path")
	target, ok := s.safeJoin(rel)
	if !ok || !isDir(target) {
		fail(w, rep, 400, "not a folder under Customers/: %s", rel)
		return
	}
	entries, _ := os.ReadDir(target)
	names := make([]string, 0, len(entries))
	for _, e := range entries {
		names = append(names, e.Name())
	}
	sort.Slice(names, func(i, j int) bool {
		return strings.ToLower(names[i]) < strings.ToLower(names[j])
	})

	dirs, files := []map[string]any{}, []map[string]any{}
	for _, name := range names {
		if strings.HasPrefix(name, ".") {
			continue
		}
		full := filepath.Join(target, name)
		childRel := name
		if trimmed := strings.TrimRight(rel, "/"); trimmed != "" {
			childRel = trimmed + "/" + name
		}
		if isDir(full) {
			// A STORE folder is any folder with its own help-videos/raw_mp4/ —
			// derived by checking the real filesystem, not assumed from depth,
			// so this works whether Customers/ is 2 levels deep or a hundred.
			var rawJump, segJump any
			if isDir(filepath.Join(full, "help-videos", "raw_mp4")) {
				rawJump = childRel + "/help-videos/raw_mp4"
			}
			if isDir(filepath.Join(full, "help-videos", "final", "segments")) {
				segJump = childRel + "/help-videos/final/segments"
			}
			dirs = append(dirs, map[string]any{
				"name": name, "path": childRel,
				"jump": rawJump, "segments_jump": segJump})
		} else if isVideo(name) {
			fi, err := os.Stat(full)
			size := int64(0)
			if err == nil {
				size = fi.Size()
			}
			files = append(files, map[string]any{"name": name, "path": childRel, "size": size})
		}
	}
	var parent any
	if trimmed := strings.Trim(rel, "/"); trimmed != "" {
		parts := strings.Split(trimmed, "/")
		parent = strings.Join(parts[:len(parts)-1], "/")
	}
	sendJSON(w, rep, map[string]any{
		"path": strings.Trim(rel, "/"), "parent": parent,
		"dirs": dirs, "files": files}, 200)
}

func (s *Server) apiOpen(w http.ResponseWriter, req *http.Request, rep *reply) {
	rel := req.URL.Query().Get("path")
	target, ok := s.safeJoin(rel)
	if !ok || !isFile(target) || !isVideo(target) {
		fail(w, rep, 400, "not a video under Customers/: %s", rel)
		return
	}
	// An ALPHA clip has to be extracted as PNG or its transparency is gone.
	// `.webm` was added to the openable extensions so an avatar could be
	// inspected frame by frame like anything else — but this once never passed
	// alpha_png, so it came back flat, and the very thing you open an avatar to
	// look at was the thing that got dropped.
	outdir, err := BuildFrames(s, target, "", 750, false, IsAlpha(target), s.log)
	if err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	sendJSON(w, rep, map[string]any{"url": filepath.Base(outdir) + "/viewer.html"}, 200)
}

// apiOpenPair opens TWO clips as one layered view: an mp4 running underneath
// and an alpha WebM on top, which is how the finished video is actually built.
//
// Each half gets its OWN complete extraction under <slug>/base/ and
// <slug>/overlay/ — frames, meta and break points — so either can be cut or
// frame-edited without touching the other. Compositing them into a single set
// of frames would have been less code and would have thrown that away.
//
// The overlay is extracted as PNG with its real alpha; the browser stacks the
// two images. That is also why the base stays JPEG: only the layer that needs
// transparency pays for it.
func (s *Server) apiOpenPair(w http.ResponseWriter, req *http.Request, rep *reply) {
	s.openPair(w, req, rep, false)
}

// apiOpenPairGo is the same, but redirects straight to the viewer. The scene
// list needs a plain navigation, not a fetch-then-assign: the extraction can
// take a while, and a link that simply goes somewhere is both simpler and
// honest about what is happening.
func (s *Server) apiOpenPairGo(w http.ResponseWriter, req *http.Request, rep *reply) {
	s.openPair(w, req, rep, true)
}

func (s *Server) openPair(w http.ResponseWriter, req *http.Request, rep *reply, redirect bool) {
	q := req.URL.Query()
	bRel, oRel := q.Get("base"), q.Get("overlay")
	base, bok := s.safeJoin(bRel)
	over, ook := s.safeJoin(oRel)
	for _, c := range []struct {
		label, p, rel string
		ok            bool
	}{{"base", base, bRel, bok}, {"overlay", over, oRel, ook}} {
		if !c.ok || !isFile(c.p) || !isVideo(c.p) {
			fail(w, rep, 400, "%s is not a video under Customers/: %s", c.label, c.rel)
			return
		}
	}
	sum := sha1.Sum([]byte(base + "|" + over))
	slug := "pair_" + hex.EncodeToString(sum[:])[:10]
	outdir := filepath.Join(s.Cache, slug)
	if err := os.MkdirAll(outdir, 0o755); err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	bdir, err := BuildFrames(s, base, filepath.Join(outdir, "base"), 750, false, false, s.log)
	if err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	odir, err := BuildFrames(s, over, filepath.Join(outdir, "overlay"), 750, false, true, s.log)
	if err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	bm, err := LoadMeta(bdir)
	if err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	om, err := LoadMeta(odir)
	if err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	if err := WritePair(outdir, bm, om, 750, bRel, oRel); err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	if redirect {
		http.Redirect(w, req, "/"+slug+"/viewer.html", http.StatusFound)
		rep.status = 302
		return
	}
	sendJSON(w, rep, map[string]any{
		"url": slug + "/viewer.html", "slug": slug,
		"base_frames": bm.NbFrames, "overlay_frames": om.NbFrames}, 200)
}

func (s *Server) apiOpenSeq(w http.ResponseWriter, req *http.Request, rep *reply) {
	s.openSeq(w, req, rep, false)
}

func (s *Server) apiOpenSeqGo(w http.ResponseWriter, req *http.Request, rep *reply) {
	s.openSeq(w, req, rep, true)
}

// openSeq opens SEVERAL scenes as one timeline.
//
// A scene on its own cannot show the thing that most often goes wrong — how one
// scene JOINS the next. Each scene keeps its OWN extraction (they are ordinary
// pairs, cached and reused), and the viewer holds a manifest that maps a global
// frame to a scene plus a local frame. Concatenating the frames into one new
// cache would have been simpler and would have thrown away both the reuse and
// the ability to say WHICH scene you are looking at.
func (s *Server) openSeq(w http.ResponseWriter, req *http.Request, rep *reply, redirect bool) {
	q := req.URL.Query()
	rootRel := q.Get("root")
	var ns []string
	for _, x := range strings.Split(q.Get("ns"), ",") {
		if strings.TrimSpace(x) != "" {
			ns = append(ns, strings.TrimSpace(x))
		}
	}
	root, ok := s.safeJoin(rootRel)
	if !ok || !isDir(root) {
		fail(w, rep, 400, "not a folder under Customers/: %s", rootRel)
		return
	}
	if len(ns) == 0 {
		fail(w, rep, 400, "no scenes selected")
		return
	}

	labels := map[int]string{}
	inScript := map[int]bool{}
	for _, nl := range ScenesFromScript(root) {
		labels[nl.N] = nl.Label
		inScript[nl.N] = true
	}

	manifest := []map[string]any{}
	missing := []int{}
	for _, raw := range ns {
		n, err := strconv.Atoi(raw)
		if err != nil {
			continue
		}
		sb := SandboxOnly(root, n, labels[n])
		seg, avSeg := sb.Segment, sb.Avatar
		hasNarration := sb.Narration != ""
		label := labels[n]
		if seg == "" {
			// A BOOKEND: a real folder with no row in script.json. It can sit on
			// a timeline — that is the point, you watch the joins — but it
			// cannot be joined or split, because both rewrite the scene list and
			// it is not in one.
			sroot := SandboxRoot(root)
			if isDir(sroot) {
				entries, _ := os.ReadDir(sroot)
				names := []string{}
				for _, e := range entries {
					names = append(names, e.Name())
				}
				sort.Strings(names)
				rx := regexp.MustCompile(fmt.Sprintf(`^%02d-(.+)$`, n))
				for _, name := range names {
					m := rx.FindStringSubmatch(name)
					if m == nil {
						continue
					}
					cand := filepath.Join(sroot, name, "segment.mp4")
					if isFile(cand) {
						seg, label = cand, m[1]
						if a := filepath.Join(sroot, name, "avatar.webm"); isFile(a) {
							avSeg = a
						}
					}
					break
				}
			}
		}
		if seg == "" {
			missing = append(missing, n)
			continue
		}
		bdir, err := BuildFrames(s, seg, "", 750, false, false, s.log)
		if err != nil {
			fail(w, rep, 500, "scene %d: %s", n, err)
			return
		}
		var om *Meta
		odir := ""
		if avSeg != "" {
			odir, err = BuildFrames(s, avSeg, "", 750, false, true, s.log)
			if err != nil {
				fail(w, rep, 500, "scene %d: %s", n, err)
				return
			}
			if om, err = LoadMeta(odir); err != nil {
				fail(w, rep, 500, "scene %d: %s", n, err)
				return
			}
		}
		bm, err := LoadMeta(bdir)
		if err != nil {
			fail(w, rep, 500, "scene %d: %s", n, err)
			return
		}
		// A bookend has no script node, so no label — but its FOLDER is named
		// (`00-opening`). Falling back to the number alone made the timeline say
		// "00", which is the one thing the reader already knows.
		if label == "" {
			folder := filepath.Base(filepath.Dir(seg))
			if regexp.MustCompile(`^\d\d-`).MatchString(folder) {
				label = folder[3:]
			} else {
				label = folder
			}
		}
		row := map[string]any{
			"n": n, "label": label,
			"in_script": inScript[n],
			// Whether this scene has a raw narration render. The opening has
			// none — it is built from TWO HeyGen clips plus the morph, so its
			// avatar IS the finished article. A join across that gap has to fill
			// it or the next scene's narration slides forward on top.
			"has_narration": hasNarration,
			"base_slug":     filepath.Base(bdir),
			"base_n":        bm.NbFrames,
			"base_ext":      bm.Ext,
			"base_audio":    bm.HasAudio,
			"over_slug":     nil,
			"over_n":        0,
			"over_ext":      ".png",
			"over_audio":    false,
			// The two SOURCE paths, so a read-only alert can offer to open this
			// scene where cutting actually happens. Without them it could only
			// say no.
			"base_rel": relTo(s.Customers, seg),
			"over_rel": nil,
			"fps":      bm.FPS,
		}
		if om != nil {
			row["over_slug"] = filepath.Base(odir)
			row["over_n"] = om.NbFrames
			row["over_ext"] = om.Ext
			row["over_audio"] = om.HasAudio
			row["over_rel"] = relTo(s.Customers, avSeg)
		}
		manifest = append(manifest, row)
	}
	if len(manifest) == 0 {
		fail(w, rep, 400, "none of %v resolved", ns)
		return
	}

	var key strings.Builder
	sceneNs := []int{}
	for _, m := range manifest {
		fmt.Fprintf(&key, "%d|", m["n"])
		sceneNs = append(sceneNs, m["n"].(int))
	}
	sum := sha1.Sum([]byte(strings.TrimSuffix(key.String(), "|") + root))
	slug := "seq_" + hex.EncodeToString(sum[:])[:10]
	outdir := filepath.Join(s.Cache, slug)
	if err := os.MkdirAll(outdir, 0o755); err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	if err := WriteSeq(outdir, manifest, 750, relTo(s.Customers, root)); err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	if redirect {
		http.Redirect(w, req, "/"+slug+"/viewer.html", http.StatusFound)
		rep.status = 302
		return
	}
	sendJSON(w, rep, map[string]any{
		"url": slug + "/viewer.html", "slug": slug,
		"scenes": sceneNs, "missing": missing}, 200)
}

// apiSiblings — every scene of this store, RESOLVED, not a directory listing.
//
// A scene's footage lives in dev/<NN>-<label>/segment-v6.mp4, a store may be
// half-migrated, and the only correct answer comes from the path rules. It also
// means a scene reports which LAYER each part came from — sandbox, dev or flat
// — because an override you have forgotten about is the failure this layout
// makes possible.
func (s *Server) apiSiblings(w http.ResponseWriter, req *http.Request, rep *reply) {
	rel := req.URL.Query().Get("path")
	target, ok := s.safeJoin(rel)
	if !ok || !isFile(target) {
		fail(w, rep, 400, "not a file under Customers/: %s", rel)
		return
	}
	// Walk up to the store's `final/` — the folder holding video/script.json.
	final := filepath.Dir(target)
	for i := 0; i < 4; i++ {
		if isFile(ScriptPath(final)) {
			break
		}
		final = filepath.Dir(final)
	}
	if !isFile(ScriptPath(final)) {
		fail(w, rep, 400, "no video/script.json above %s", rel)
		return
	}

	// SANDBOX ONLY. A scene with no sandbox copy is shown as missing rather than
	// silently resolved from dev, because an edit that appears to work on a file
	// the editor cannot write is worse than an obvious gap.
	items := []map[string]any{}
	known := map[int]bool{}
	targetAbs, _ := filepath.Abs(target)
	for _, nl := range ScenesFromScript(final) {
		sb := SandboxOnly(final, nl.N, nl.Label)
		seg, av := sb.Segment, sb.Avatar
		known[nl.N] = true
		nfr, nex := -1, false
		if seg != "" {
			nfr, nex = s.frameCount(seg)
		}
		ofr, oex := -1, false
		if av != "" {
			ofr, oex = s.frameCount(av)
		}
		var dur any
		if seg != "" {
			if d, err := probeFloat(seg, "duration", false, nil); err == nil {
				dur = round2(d)
			}
		}
		name := "—"
		if seg != "" {
			name = filepath.Base(seg)
		}
		cur := seg != ""
		if cur {
			a, _ := filepath.Abs(seg)
			cur = a == targetAbs
		}
		items = append(items, map[string]any{
			"n": nl.N, "label": nl.Label, "name": name, "dur": dur,
			"path":        nilIfEmpty(relTo(s.Customers, seg)),
			"overlay":     nilIfEmpty(relTo(s.Customers, av)),
			"src":         nilIfEmpty(SourceOf(final, seg)),
			"overlay_src": nilIfEmpty(SourceOf(final, av)),
			"missing":     seg == "",
			"frames":      nilIfNeg(nfr), "frames_exact": nex,
			"overlay_frames": nilIfNeg(ofr), "overlay_frames_exact": oex,
			"current": cur,
		})
	}

	// BOOKENDS and anything else in sandbox that is not a script scene. The
	// opening and closing are not "scenes" — they are not in script.json and
	// never will be — but they ARE a base + overlay pair, so the editor can
	// review them with the same controls. Numbered 00 and 99 so they sit at the
	// ends of the list where they belong.
	sroot := SandboxRoot(final)
	if isDir(sroot) {
		entries, _ := os.ReadDir(sroot)
		names := []string{}
		for _, e := range entries {
			names = append(names, e.Name())
		}
		sort.Strings(names)
		rx := regexp.MustCompile(`^(\d+)-(.+)$`)
		for _, d := range names {
			m := rx.FindStringSubmatch(d)
			if m == nil || !isDir(filepath.Join(sroot, d)) {
				continue
			}
			n, _ := strconv.Atoi(m[1])
			if known[n] {
				continue
			}
			seg := filepath.Join(sroot, d, "segment.mp4")
			av := filepath.Join(sroot, d, "avatar.webm")
			if !isFile(seg) {
				continue
			}
			var dur any
			if v, err := probeFloat(seg, "duration", false, nil); err == nil {
				dur = round2(v)
			}
			bfr, bex := s.frameCount(seg)
			afr, aex := -1, false
			if isFile(av) {
				afr, aex = s.frameCount(av)
			}
			a, _ := filepath.Abs(seg)
			row := map[string]any{
				"n": n, "label": m[2], "name": "segment.mp4", "dur": dur,
				"frames": nilIfNeg(bfr), "frames_exact": bex,
				"overlay_frames": nilIfNeg(afr), "overlay_frames_exact": aex,
				"path": relTo(s.Customers, seg), "src": "sandbox",
				"overlay": nil, "overlay_src": nil,
				"missing": false, "extra": true, "current": a == targetAbs,
			}
			if isFile(av) {
				row["overlay"] = relTo(s.Customers, av)
				row["overlay_src"] = "sandbox"
			}
			items = append(items, row)
		}
	}
	sort.Slice(items, func(i, j int) bool {
		return items[i]["n"].(int) < items[j]["n"].(int)
	})

	v := Versions(final)
	segV := v["segment"]
	sendJSON(w, rep, map[string]any{
		"layout":          Layout(final),
		"editor_scope":    "sandbox",
		"versions":        segV,
		"current_version": firstOrNil(segV),
		"overlay_version": firstOrNil(v["avatar"]),
		"script_version":  firstOrNil(v["script"]),
		"by_version":      map[string]any{strconv.Itoa(firstOr0(segV)): items},
		"folder":          relTo(s.Customers, final),
	}, 200)
}

// apiMap — one clip's frame map: for each cache frame, the SOURCE frame it
// shows.
//
// The page asks for this before an edit so it can keep a snapshot to undo back
// to. It is not sent with the manifest because most scenes are never edited, and
// a map is one integer per frame — paid for only when needed.
func (s *Server) apiMap(w http.ResponseWriter, req *http.Request, rep *reply) {
	q := req.URL.Query()
	outdir, ok := s.resolveOutdir(q.Get("slug"), q.Get("which"))
	if !ok {
		fail(w, rep, 400, "unknown slug")
		return
	}
	m, err := LoadMeta(outdir)
	if err != nil {
		fail(w, rep, 400, "unknown slug")
		return
	}
	sendJSON(w, rep, map[string]any{
		"frame_map": GetFrameMap(m), "nb_frames": m.NbFrames}, 200)
}

func (s *Server) apiMarks(w http.ResponseWriter, req *http.Request, rep *reply) {
	q := req.URL.Query()
	outdir, ok := s.resolveOutdir(q.Get("slug"), q.Get("which"))
	if !ok {
		fail(w, rep, 400, "unknown slug")
		return
	}
	sendJSON(w, rep, map[string]any{"marks": loadMarks(outdir)}, 200)
}

// ── small helpers ───────────────────────────────────────────────────────────

func relTo(base, p string) string {
	if p == "" {
		return ""
	}
	r, err := filepath.Rel(base, p)
	if err != nil {
		return p
	}
	return r
}

func nilIfEmpty(s string) any {
	if s == "" {
		return nil
	}
	return s
}

func nilIfNeg(n int) any {
	if n < 0 {
		return nil
	}
	return n
}

func firstOrNil(v []int) any {
	if len(v) == 0 {
		return nil
	}
	return v[0]
}

func firstOr0(v []int) int {
	if len(v) == 0 {
		return 0
	}
	return v[0]
}

func round2(f float64) float64 {
	return float64(int64(f*100+0.5)) / 100
}
