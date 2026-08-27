package editor

// /api/clip — one clip's facts, as JSON.
//
// THE ONLY ENDPOINT THE REBUILD ADDS, and it exists because of what the
// rebuild changes. The Python players baked these values straight into the
// page: `const N = 40; const FPS = 25.0;` were written into the JavaScript at
// extraction time, so the page never had to ask.
//
// A React front end is served as a static bundle and is handed a slug, not a
// generated page — so it has to ask. This is that question, and nothing else:
// no new behaviour, no new state, and nothing on disk that did not already
// exist inside meta.json.

import (
	"net/http"
	"path/filepath"
)

func (s *Server) apiClip(w http.ResponseWriter, req *http.Request, rep *reply) {
	q := req.URL.Query()
	slug := q.Get("slug")
	outdir, ok := s.resolveOutdir(slug, q.Get("which"))
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
		"slug":        slug,
		"source":      m.Source,
		"source_name": m.SourceName,
		"nb_frames":   m.NbFrames,
		"fps":         m.FPS,
		"ext":         m.Ext,
		"has_audio":   m.HasAudio,
		// `edited` means frames were added or removed, so the extracted audio —
		// which is the ORIGINAL — no longer lines up. The page says so rather
		// than letting a false sync be believed. It is also what lets Save start
		// disabled: equal adds and deletes leave the COUNT unchanged with the
		// clip genuinely edited, so the count alone cannot answer this.
		"edited": m.Edited,
		"disp_w": m.DispW,
		"disp_h": m.DispH,
		// Where a cut would land, and the video folder a hand-off would write
		// into. Both are derived from the source path's own shape, in the
		// backend, so the page never has to know the folder rules — deriving
		// them a second time in JavaScript is how the folders drifted apart
		// before.
		"cuts_dir":     deriveSegmentsDir(m.Source),
		"video_folder": filepath.Dir(filepath.Dir(deriveSegmentsDir(m.Source))),
		// True when this clip is transparent — an avatar render. The break
		// points are drawn PURPLE for one and GREEN for the other, because
		// cutting Sarah is not cutting the screen recording and the two are easy
		// to confuse once a long avatar render is being spliced like any other
		// clip.
		"alpha": m.Ext == ".png",
	}, 200)
}
