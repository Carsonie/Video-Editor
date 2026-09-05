package editor

// The session log — a record of real editing, kept as you work.
//
// The test writes its own log; this is the other half: what actually happened
// to your files, in the same shape. One file per DAY, appended, with a header
// each time the server starts.
//
// Only calls that CHANGE something are logged — plus the ways IN, because a
// line saying what you were working on is what makes the rest readable.
//
// It has already earned its place twice: it showed a Join that never reached
// the server at all, and four pastes that landed on one track and were refused
// on the other.

import (
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

type action struct {
	label string
	keys  []string // which payload keys are worth showing
}

var actions = map[string]action{
	"/api/frames/dup":      {"+ Frame", []string{"at", "count", "side"}},
	"/api/frames/del":      {"- Frame", []string{"at", "count", "side"}},
	"/api/frames/dup-span": {"+ Zone", []string{"a", "b"}},
	"/api/frames/del-span": {"- Zone", []string{"a", "b"}},
	"/api/frames/restore":  {"Undo", nil},
	"/api/frames/paste":    {"Paste frame", []string{"from", "at"}},
	"/api/mark":            {"Mark", []string{"frame", "on"}},
	"/api/clear-marks":     {"Unmark all", nil},
	"/api/save":            {"Save scene", nil},
	"/api/cut":             {"Cut scene", nil},
	"/api/clear-edits":     {"Discard edits", nil},
	"/api/reset-editor":    {"Reset editor", nil},
	"/api/join":            {"Join", []string{"ns", "label", "tracks"}},
	"/api/split":           {"Split", []string{"n", "at", "labels", "tracks"}},
	"/api/line":            {"Edit line", []string{"n"}},
	"/api/renumber-clear":  {"Lift lock", nil},
	"/api/handoff":         {"Hand off", []string{"version", "names"}},
	"/api/archive":         {"Archive", []string{"folder"}},
	"/api/open":            {"Open clip", []string{"path"}},
	"/api/open-pair":       {"Open layered", []string{"base"}},
	"/api/open-seq":        {"Open timeline", []string{"root", "ns"}},
	"/api/open-pair-go":    {"Open layered", []string{"base"}},
	"/api/open-seq-go":     {"Open timeline", []string{"root", "ns"}},
}

// resultKeys — what is worth showing back, in the order it reads best.
var resultKeys = []string{"nb_frames", "count", "version", "duration_s", "joined",
	"split", "label", "labels", "line", "renamed", "url", "slug"}

type SessionLog struct {
	path string
	off  bool
	mu   sync.Mutex
}

func NewSessionLog(root string, off bool) *SessionLog {
	return &SessionLog{
		path: filepath.Join(root, "logs", fmt.Sprintf("editor_%s.log", time.Now().Format("20060102"))),
		off:  off,
	}
}

func (s *SessionLog) Path() string {
	if s.off {
		return "off"
	}
	return s.path
}

func (s *SessionLog) Start(port int, root string) {
	if s.off {
		return
	}
	_ = os.MkdirAll(filepath.Dir(s.path), 0o755)
	ver := SAELabel("Segment and Avatar Editor", "segment_avatar_editor")
	s.write(fmt.Sprintf("\nEditor Session:  %s\nPlayer:          %s\nServer:          http://localhost:%d  (Go)\n\n",
		time.Now().Format("2006-01-02T15:04:05"), ver, port))
}

func (s *SessionLog) write(text string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	f, err := os.OpenFile(s.path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return // a log that can break the editor is worse than no log
	}
	defer f.Close()
	_, _ = f.WriteString(text)
}

func (s *SessionLog) LogGET(path string, q url.Values, rep *reply) {
	if s == nil || s.off {
		return
	}
	if _, ok := actions[path]; !ok {
		return
	}
	p := Payload{}
	for k := range q {
		p[k] = q.Get(k)
	}
	s.line(path, p, rep)
}

func (s *SessionLog) LogPOST(path string, p Payload, rep *reply) {
	if s == nil || s.off {
		return
	}
	s.line(path, p, rep)
}

func (s *SessionLog) line(path string, p Payload, rep *reply) {
	act, ok := actions[path]
	if !ok {
		return
	}
	var args []string
	for _, k := range act.keys {
		if v, present := p[k]; present && v != nil {
			args = append(args, fmt.Sprintf("%s=%v", k, plain(v)))
		}
	}
	// What it acted on: a cache slug for frame work, a store for the rest.
	who := p.str("slug")
	if who == "" {
		who = p.str("root")
	}
	argStr := strings.Join(args, " ")
	if path == "/api/open" {
		src := p.str("path")
		who = filepath.Base(filepath.Dir(src))
		argStr = filepath.Base(src)
	}

	tail := ""
	if rep.status != 200 || rep.body["error"] != nil {
		e := rep.body["error"]
		if e == nil {
			e = rep.status
		}
		tail = fmt.Sprintf("REFUSED: %v", e)
	} else {
		var parts []string
		for _, k := range resultKeys {
			if v, ok := rep.body[k]; ok {
				parts = append(parts, fmt.Sprintf("%s=%v", k, plain(v)))
			}
		}
		tail = strings.Join(parts, "  ")
	}
	s.write(strings.TrimRight(fmt.Sprintf("%s  %-14s %-26s %s  %s",
		time.Now().Format("15:04:05"), act.label, who, argStr, tail), " ") + "\n")
}

// plain renders a value the way the Python log did — a float that is really an
// integer prints without its `.0`, so `at=440` does not read as `at=440.0`.
func plain(v any) any {
	switch x := v.(type) {
	case float64:
		if x == float64(int64(x)) {
			return int64(x)
		}
	case []any:
		out := make([]any, len(x))
		for i, e := range x {
			out[i] = plain(e)
		}
		return out
	}
	return v
}
