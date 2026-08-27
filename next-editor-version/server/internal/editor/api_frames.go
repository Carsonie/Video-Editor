package editor

// The frame edits. Every one of these acts on the PREVIEW CACHE only — the
// extracted frames plus the frame map. None of them touches the source video;
// that is what /api/save is for.
//
// Each also MOVES THE MARKS. A mark points at a cache position, so an edit that
// shifts content has to shift the marks with it or they silently come to mean
// something else.

import (
	"net/http"
	"sort"
)

func (s *Server) apiMark(w http.ResponseWriter, rep *reply, p Payload) {
	outdir, ok := s.resolveOutdir(p.str("slug"), p.str("which"))
	if !ok {
		fail(w, rep, 400, "unknown slug")
		return
	}
	frame, ok := p.intOK("frame")
	if !ok {
		fail(w, rep, 400, "frame must be an integer")
		return
	}
	m, err := LoadMeta(outdir)
	if err != nil {
		fail(w, rep, 400, "unknown slug")
		return
	}
	if frame < 1 || frame > m.NbFrames {
		fail(w, rep, 400, "frame %d is outside 1..%d", frame, m.NbFrames)
		return
	}
	marks := loadMarks(outdir)
	if p.boolOr("on", true) {
		marks = append(marks, frame)
	} else {
		out := marks[:0]
		for _, x := range marks {
			if x != frame {
				out = append(out, x)
			}
		}
		marks = out
	}
	marks = sortedUnique(marks)
	if err := saveMarks(outdir, marks); err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	sendJSON(w, rep, map[string]any{"marks": marks}, 200)
}

func (s *Server) apiClearMarks(w http.ResponseWriter, rep *reply, p Payload) {
	outdir, ok := s.resolveOutdir(p.str("slug"), p.str("which"))
	if !ok {
		fail(w, rep, 400, "unknown slug")
		return
	}
	if err := saveMarks(outdir, nil); err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	sendJSON(w, rep, map[string]any{"marks": []int{}}, 200)
}

// apiFramesDup — ＋ Frame: insert `count` copies of the current frame, to its
// `side`.
func (s *Server) apiFramesDup(w http.ResponseWriter, rep *reply, p Payload) {
	outdir, ok := s.resolveOutdir(p.str("slug"), p.str("which"))
	if !ok {
		fail(w, rep, 400, "unknown slug")
		return
	}
	at, aok := p.intOK("at")
	count, cok := p.intOK("count")
	if !aok || !cok {
		fail(w, rep, 400, "at and count must be integers")
		return
	}
	if count < 1 {
		fail(w, rep, 400, "count must be at least 1")
		return
	}
	side := p.str("side")
	if side == "" {
		side = "right"
	}
	if side != "left" && side != "right" {
		fail(w, rep, 400, "side must be 'left' or 'right'")
		return
	}
	var newN, newCur int
	var err error
	var marks []int
	if side == "right" {
		newN, newCur, err = DuplicateFrameRight(outdir, at, count)
		// right insert: `at` itself does not move, only what is AFTER it does
		marks = shiftMarks(loadMarks(outdir), count, func(m int) bool { return m > at })
	} else {
		newN, newCur, err = DuplicateFrameLeft(outdir, at, count)
		// left insert: `at` itself moves too — its content shifts right
		marks = shiftMarks(loadMarks(outdir), count, func(m int) bool { return m >= at })
	}
	if err != nil {
		fail(w, rep, 400, "%s", err)
		return
	}
	marks = sortedUnique(marks)
	_ = saveMarks(outdir, marks)
	sendJSON(w, rep, map[string]any{
		"nb_frames": newN, "current": newCur, "marks": marks}, 200)
}

// apiFramesDel — − Frame: delete up to `count` frames immediately to the `side`
// of the current frame, clamped so it can never delete past either edge.
//
// Returns the ACTUAL count removed — which can be less than asked near an edge
// — and how many marks were dropped because they pointed at content that no
// longer exists.
func (s *Server) apiFramesDel(w http.ResponseWriter, rep *reply, p Payload) {
	outdir, ok := s.resolveOutdir(p.str("slug"), p.str("which"))
	if !ok {
		fail(w, rep, 400, "unknown slug")
		return
	}
	at, aok := p.intOK("at")
	count, cok := p.intOK("count")
	if !aok || !cok {
		fail(w, rep, 400, "at and count must be integers")
		return
	}
	if count < 1 {
		fail(w, rep, 400, "count must be at least 1")
		return
	}
	side := p.str("side")
	if side == "" {
		side = "left"
	}
	if side != "left" && side != "right" {
		fail(w, rep, 400, "side must be 'left' or 'right'")
		return
	}
	var newN, newCur, actual int
	var rng [2]int
	var had bool
	var err error
	if side == "left" {
		newN, newCur, actual, rng, had, err = DeleteFramesLeft(outdir, at, count)
	} else {
		newN, newCur, actual, rng, had, err = DeleteFramesRight(outdir, at, count)
	}
	if err != nil {
		fail(w, rep, 400, "%s", err)
		return
	}
	marks, dropped := loadMarks(outdir), 0
	if had {
		kept := []int{}
		for _, m := range marks {
			switch {
			case rng[0] <= m && m <= rng[1]:
				dropped++
			case m > rng[1]:
				kept = append(kept, m-actual)
			default:
				kept = append(kept, m)
			}
		}
		marks = sortedUnique(kept)
		_ = saveMarks(outdir, marks)
	}
	sendJSON(w, rep, map[string]any{
		"nb_frames": newN, "current": newCur, "actual": actual,
		"dropped_marks": dropped, "marks": marks}, 200)
}

// apiPaste — paste a copy of one frame after another, inside the same clip.
//
// `from` and `at` are both CACHE positions. The copy carries the source frame
// the original showed, so the map stays truthful and a pasted frame is the same
// frame, not a picture of one.
func (s *Server) apiPaste(w http.ResponseWriter, rep *reply, p Payload) {
	outdir, ok := s.resolveOutdir(p.str("slug"), p.str("which"))
	if !ok {
		fail(w, rep, 400, "unknown slug")
		return
	}
	from, fok := p.intOK("from")
	at, aok := p.intOK("at")
	if !fok || !aok {
		fail(w, rep, 400, "from and at must be integers")
		return
	}
	n, cur, err := PasteFrame(outdir, from, at)
	if err != nil {
		fail(w, rep, 400, "%s", err)
		return
	}
	// A paste inserts one frame, so a mark AFTER the insert shifts by one.
	marks := sortedUnique(shiftMarks(loadMarks(outdir), 1, func(m int) bool { return m > at }))
	_ = saveMarks(outdir, marks)
	m, err := LoadMeta(outdir)
	if err != nil {
		fail(w, rep, 500, "%s", err)
		return
	}
	sendJSON(w, rep, map[string]any{
		"nb_frames": n, "current": cur, "marks": marks,
		"frame_map": GetFrameMap(m)}, 200)
}

// apiSpan — repeat or remove a RUN of frames a..b: the marked zone the timeline
// is looping over.
//
// The single-frame endpoints act on one frame `count` times; this acts on a
// span once, which is what "loop this zone again" and "cut this zone out"
// actually mean.
func (s *Server) apiSpan(w http.ResponseWriter, rep *reply, p Payload, mode string) {
	outdir, ok := s.resolveOutdir(p.str("slug"), p.str("which"))
	if !ok {
		fail(w, rep, 400, "unknown slug")
		return
	}
	a, aok := p.intOK("a")
	b, bok := p.intOK("b")
	if !aok || !bok {
		fail(w, rep, 400, "a and b must be integers")
		return
	}
	if b < a {
		a, b = b, a
	}
	var newN, newCur int
	var err error
	if mode == "dup" {
		newN, newCur, err = DuplicateSpan(outdir, a, b)
	} else {
		newN, newCur, err = DeleteSpan(outdir, a, b)
	}
	if err != nil {
		fail(w, rep, 400, "%s", err)
		return
	}
	// A mark that still points at content is kept pointing at the same content.
	k := b - a + 1
	kept, dropped := []int{}, 0
	for _, m := range loadMarks(outdir) {
		if mode == "dup" {
			if m > b {
				kept = append(kept, m+k)
			} else {
				kept = append(kept, m)
			}
			continue
		}
		switch {
		case a <= m && m <= b:
			dropped++
		case m > b:
			kept = append(kept, m-k)
		default:
			kept = append(kept, m)
		}
	}
	marks := sortedUnique(kept)
	_ = saveMarks(outdir, marks)
	sendJSON(w, rep, map[string]any{
		"nb_frames": newN, "current": newCur, "span": k,
		"dropped_marks": dropped, "marks": marks}, 200)
}

// apiRestore — put one clip's cache back to a given frame map: one step of the
// per-scene undo. The map comes from the page, which snapshotted it before
// making the edit being undone.
//
// A mark past the restored end is dropped rather than left pointing at nothing.
func (s *Server) apiRestore(w http.ResponseWriter, rep *reply, p Payload) {
	outdir, ok := s.resolveOutdir(p.str("slug"), p.str("which"))
	if !ok {
		fail(w, rep, 400, "unknown slug")
		return
	}
	target, ok := p.ints("frame_map")
	if !ok || len(target) == 0 {
		fail(w, rep, 400, "frame_map must be a non-empty list")
		return
	}
	n, err := RestoreMap(s, outdir, target, s.log)
	if err != nil {
		fail(w, rep, 400, "%s", err)
		return
	}
	kept := []int{}
	for _, m := range loadMarks(outdir) {
		if 1 <= m && m <= n {
			kept = append(kept, m)
		}
	}
	sort.Ints(kept)
	_ = saveMarks(outdir, kept)
	sendJSON(w, rep, map[string]any{"nb_frames": n, "marks": sortedUnique(kept)}, 200)
}

func shiftMarks(marks []int, by int, moves func(int) bool) []int {
	out := make([]int, 0, len(marks))
	for _, m := range marks {
		if moves(m) {
			out = append(out, m+by)
		} else {
			out = append(out, m)
		}
	}
	return out
}
