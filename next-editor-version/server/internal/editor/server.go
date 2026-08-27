package editor

// The server itself — routing, the Customers/ boundary, and the two things
// that wrap EVERY mutating call: the per-cache-folder lock and the session log.
//
// Both are taken here rather than inside each handler, for the same reason:
// there are eighteen of them, and the one that forgets is the one that corrupts
// a cache at two clicks a second, or leaves a hole in the record that nothing
// would ever point at.

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

type Server struct {
	Root      string // the repo root
	Customers string // <root>/Customers — nothing outside it is browsable
	Cache     string // where extractions live
	Session   *SessionLog
	mux       *http.ServeMux
}

// VideoExts — what can be opened in a viewer. `.webm` is here so the AVATAR
// clips can be inspected frame by frame like anything else: the morphs, the
// narration renders and the close-out are where the hard-to-see faults live —
// a mouth moving with no audio behind it, a pose that pops — and they were
// previously only reviewable by building a whole video and watching it.
var VideoExts = []string{".mp4", ".webm"}

func isVideo(p string) bool {
	low := strings.ToLower(p)
	for _, e := range VideoExts {
		if strings.HasSuffix(low, e) {
			return true
		}
	}
	return false
}

func New(root, cache string, session *SessionLog) *Server {
	s := &Server{
		Root:      root,
		Customers: filepath.Join(root, "Customers"),
		Cache:     cache,
		Session:   session,
	}
	s.routes()
	return s
}

func (s *Server) Handler() http.Handler { return s.mux }

// safeJoin resolves `rel` under Customers/ and refuses anything that would
// escape it, `..` included. Every path this server opens goes through here.
func (s *Server) safeJoin(rel string) (string, bool) {
	rel = strings.Trim(rel, "/")
	target := filepath.Clean(filepath.Join(s.Customers, rel))
	if target != s.Customers && !strings.HasPrefix(target, s.Customers+string(os.PathSeparator)) {
		return "", false
	}
	return target, true
}

// resolveOutdir turns a slug into a cache folder.
//
// A slug is a literal cache subfolder NAME, never a path — anything with a
// separator is refused so this cannot be used to escape the cache.
//
// `which` selects one half of a PAIR. A pair keeps two complete extractions
// side by side, each with its own frames, meta and break points, so either can
// be edited without disturbing the other. Every editing endpoint takes it,
// which is what lets one set of controls drive whichever layer is active.
func (s *Server) resolveOutdir(slug, which string) (string, bool) {
	if slug == "" || strings.ContainsAny(slug, `/\`) || slug == "." || slug == ".." {
		return "", false
	}
	outdir := filepath.Join(s.Cache, slug)
	if which != "" {
		if which != "base" && which != "overlay" {
			return "", false
		}
		outdir = filepath.Join(outdir, which)
	}
	if !isDir(outdir) || !isFile(metaPath(outdir)) {
		return "", false
	}
	return outdir, true
}

// ── replies ─────────────────────────────────────────────────────────────────

// reply carries what was answered back out to the session log, which needs the
// body and the status and cannot get them from an http.ResponseWriter.
type reply struct {
	body   map[string]any
	status int
}

func sendJSON(w http.ResponseWriter, r *reply, obj map[string]any, status int) {
	if r != nil {
		r.body, r.status = obj, status
	}
	b, err := json.Marshal(obj)
	if err != nil {
		http.Error(w, `{"error":"could not encode the answer"}`, 500)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Content-Length", strconv.Itoa(len(b)))
	w.WriteHeader(status)
	_, _ = w.Write(b)
}

func fail(w http.ResponseWriter, r *reply, status int, format string, a ...any) {
	sendJSON(w, r, map[string]any{"error": fmt.Sprintf(format, a...)}, status)
}

// ── request payloads ────────────────────────────────────────────────────────

// Payload is a POST body, read as a map so a handler can ask for a key the way
// the Python did — and so the session log can show the arguments of any call
// without a struct per endpoint.
type Payload map[string]any

func (p Payload) str(k string) string {
	if v, ok := p[k].(string); ok {
		return v
	}
	return ""
}

func (p Payload) has(k string) bool { _, ok := p[k]; return ok }

func (p Payload) intOK(k string) (int, bool) {
	switch v := p[k].(type) {
	case float64:
		return int(v), true
	case string:
		n, err := strconv.Atoi(v)
		return n, err == nil
	}
	return 0, false
}

func (p Payload) boolOr(k string, def bool) bool {
	if v, ok := p[k].(bool); ok {
		return v
	}
	return def
}

func (p Payload) strings(k string) []string {
	raw, ok := p[k].([]any)
	if !ok {
		return nil
	}
	out := make([]string, 0, len(raw))
	for _, x := range raw {
		if sv, ok := x.(string); ok {
			out = append(out, sv)
		} else {
			out = append(out, fmt.Sprint(x))
		}
	}
	return out
}

func (p Payload) ints(k string) ([]int, bool) {
	raw, ok := p[k].([]any)
	if !ok {
		return nil, false
	}
	out := make([]int, 0, len(raw))
	for _, x := range raw {
		switch v := x.(type) {
		case float64:
			out = append(out, int(v))
		case string:
			n, err := strconv.Atoi(v)
			if err != nil {
				return nil, false
			}
			out = append(out, n)
		default:
			return nil, false
		}
	}
	return out, true
}

// ── routing ─────────────────────────────────────────────────────────────────

type getHandler func(http.ResponseWriter, *http.Request, *reply)
type postHandler func(http.ResponseWriter, *reply, Payload)

func (s *Server) routes() {
	s.mux = http.NewServeMux()

	gets := map[string]getHandler{
		"/api/list":           s.apiList,
		"/api/open":           s.apiOpen,
		"/api/open-pair":      s.apiOpenPair,
		"/api/open-pair-go":   s.apiOpenPairGo,
		"/api/open-seq":       s.apiOpenSeq,
		"/api/open-seq-go":    s.apiOpenSeqGo,
		"/api/siblings":       s.apiSiblings,
		"/api/renumber-state": s.apiRenumberState,
		"/api/vtt":            s.apiVTT,
		"/api/frames/map":     s.apiMap,
		"/api/marks":          s.apiMarks,
		"/api/clip":           s.apiClip,
	}
	posts := map[string]postHandler{
		"/api/mark":            s.apiMark,
		"/api/clear-marks":     s.apiClearMarks,
		"/api/frames/dup":      s.apiFramesDup,
		"/api/frames/paste":    s.apiPaste,
		"/api/frames/del":      s.apiFramesDel,
		"/api/frames/dup-span": func(w http.ResponseWriter, r *reply, p Payload) { s.apiSpan(w, r, p, "dup") },
		"/api/frames/del-span": func(w http.ResponseWriter, r *reply, p Payload) { s.apiSpan(w, r, p, "del") },
		"/api/frames/restore":  s.apiRestore,
		"/api/renumber-clear":  s.apiRenumberClear,
		"/api/split":           s.apiSplit,
		"/api/join":            s.apiJoin,
		"/api/handoff":         s.apiHandoff,
		"/api/archive":         s.apiArchive,
		"/api/line":            s.apiLine,
		"/api/cut":             s.apiCut,
		"/api/save":            s.apiSave,
		"/api/clear-edits":     s.apiClearEdits,
		"/api/reset-editor":    s.apiResetEditor,
	}

	for path, fn := range gets {
		h := fn
		p := path
		s.mux.HandleFunc(p, func(w http.ResponseWriter, req *http.Request) {
			rep := &reply{status: 200}
			h(w, req, rep)
			// Only the ways IN are logged, and only they need to be: a line
			// saying what you opened is what makes the edits under it readable.
			// Every other GET is a frame image or a poll, and logging those
			// would bury the record in its own noise.
			s.Session.LogGET(p, req.URL.Query(), rep)
		})
	}

	for path, fn := range posts {
		h := fn
		p := path
		s.mux.HandleFunc(p, func(w http.ResponseWriter, req *http.Request) {
			rep := &reply{status: 200}
			if req.Method != http.MethodPost {
				fail(w, rep, 405, "%s is POST only", p)
				return
			}
			var payload Payload
			dec := json.NewDecoder(req.Body)
			if err := dec.Decode(&payload); err != nil {
				if err.Error() != "EOF" {
					fail(w, rep, 400, "malformed JSON body")
					return
				}
				payload = Payload{}
			}
			// ONE WRITER AT A TIME per cache folder. Taken here rather than in
			// each of the handlers that mutate one: nine places is nine chances
			// to forget, and the one forgotten is the one that corrupts a cache.
			if slug := payload.str("slug"); slug != "" {
				if outdir, ok := s.resolveOutdir(slug, payload.str("which")); ok {
					lock := DirLock(outdir)
					lock.Lock()
					h(w, rep, payload)
					lock.Unlock()
					s.Session.LogPOST(p, payload, rep)
					return
				}
			}
			h(w, rep, payload)
			s.Session.LogPOST(p, payload, rep)
		})
	}

	// Everything else is a static file out of the cache — the frames, the
	// viewer pages, the extracted audio — with the browser at the root.
	files := http.FileServer(http.Dir(s.Cache))
	s.mux.HandleFunc("/", func(w http.ResponseWriter, req *http.Request) {
		if req.URL.Path == "/" || req.URL.Path == "/browse.html" {
			w.Header().Set("Content-Type", "text/html; charset=utf-8")
			_, _ = w.Write([]byte(browseHTML))
			return
		}
		files.ServeHTTP(w, req)
	})
}

func (s *Server) log(m string) { fmt.Fprintln(os.Stderr, m) }
