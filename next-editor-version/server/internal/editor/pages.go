package editor

// The three player pages.
//
// These are the SAME pages the Python players write — lifted verbatim out of
// their `.format()` templates and stored here as Go templates. Nothing about
// the JavaScript or the CSS changed in the move; only the placeholders did.
//
// WHY THAT MATTERS
//
// In Python the pages were `str.format()` templates, so every CSS and JS brace
// had to be doubled, and two traps shipped because of it:
//
//   * a stray apostrophe in a single-quoted JS string killed the WHOLE page
//     silently — every control died, Play included;
//   * `\n` in the source became a real newline, which is legal inside a
//     backtick literal and a syntax error inside a single-quoted string.
//
// Here the page text is a plain file. Braces are braces. The delimiters are
// U+27E6/U+27E7 rather than Go's own `{{ }}` because these files are 240kB of
// real JavaScript and CSS, in which every ASCII delimiter pair already occurs.
//
// The `node --check` step in the test suite still applies and must not be
// dropped: a page that fails to parse still answers every endpoint perfectly.

import (
	"embed"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"text/template"
)

//go:embed templates/*.gohtml
var pageFS embed.FS

var pageTpl = template.Must(
	template.New("pages").
		Delims("⟦", "⟧").
		Funcs(template.FuncMap{"quote": quote}).
		ParseFS(pageFS, "templates/*.gohtml"))

// quote is Python's `!r` for a string — the value arrives at the page ALREADY
// QUOTED. Dropping it once emitted `ext: .jpg` into the JavaScript, a syntax
// error that killed the whole page: every control dead, Play included.
//
// Single quotes, and the two characters that could end the literal early are
// escaped. A real newline inside a single-quoted JS string is a syntax error
// too — that trap has shipped here before — so it is escaped as well.
func quote(v any) string {
	return "'" + strings.NewReplacer(
		`\`, `\\`,
		`'`, `\'`,
		"\n", `\n`,
		"\r", `\r`,
	).Replace(fmt.Sprint(v)) + "'"
}

func render(outdir, name string, data any) error {
	var b strings.Builder
	if err := pageTpl.ExecuteTemplate(&b, name, data); err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(outdir, "viewer.html"), []byte(b.String()), 0o644)
}

// jsonStr is Python's json.dumps for one value — used where the page needs a
// JS literal it cannot build by hand. A source path can contain spaces, quotes,
// anything a real filesystem path holds, and this project's own paths already
// do ("Rentify Demos Corp").
func jsonStr(v any) string {
	b, err := json.Marshal(v)
	if err != nil {
		return "null"
	}
	// Go escapes <, > and & for HTML by default. These land inside <script>,
	// where the escapes are wrong — a label containing "&" would render as
	// "&" on screen.
	s := string(b)
	s = strings.ReplaceAll(s, `<`, "<")
	s = strings.ReplaceAll(s, `>`, ">")
	s = strings.ReplaceAll(s, `&`, "&")
	return s
}

func boolJS(b bool) string {
	if b {
		return "true"
	}
	return "false"
}

// ── the MP4 Splitter ────────────────────────────────────────────────────────

type splitterData struct {
	Title, Source, Slug, PlayerLabel string
	HasAudio, EditedFlag             string
	SourcePath, Edited               string
	NbFrames, DispW, DispH           int
	AppW, StackW                     int
	// The SAME rate, rendered two ways, because the page asks for both: `Fps`
	// as Python's str(), so an integral rate keeps its `.0`, and `FpsG` as
	// Python's `:g` for the places that want `25` rather than `25.000000`.
	Fps, FpsG string
}

// WriteViewer (re)writes a clip's OWN page from its meta. Every extracted clip
// gets one, including the clips a layered or timeline view is built from: it is
// what "open this scene on its own" opens, and what a frame edit has to refresh.
//
// The stage is sized to the ACTUAL frame dimensions, not a padded square — no
// letterbox bars, width held at the box and height following the source's aspect.
func WriteViewer(outdir string, m *Meta) error {
	title := m.SourceName
	if title == "" {
		title = filepath.Base(m.Source)
	}
	return render(outdir, "splitter.gohtml", splitterData{
		Title:    title,
		Source:   title,
		Slug:     filepath.Base(strings.TrimRight(outdir, string(os.PathSeparator))),
		HasAudio: boolJS(m.HasAudio),
		// `edited` means frames were added or removed, so the extracted audio —
		// which is the ORIGINAL — no longer lines up. The viewer says so rather
		// than letting a false sync be believed.
		EditedFlag: boolJS(m.Edited),
		NbFrames:   m.NbFrames,
		Fps:        pyFloat(m.FPS),
		FpsG:       fmtG(m.FPS),
		DispW:      m.DispW,
		DispH:      m.DispH,
		// The toolbelt is a fixed-width drawer beside the stage: 264 plus the
		// 14px grid gap. stack_w is the point below which it no longer fits and
		// drops under the video instead.
		AppW:        m.DispW + 278,
		StackW:      m.DispW + 292,
		SourcePath:  jsonStr(m.Source),
		Edited:      jsonStr(m.Edited),
		PlayerLabel: SAELabel("MP4 Splitter", "mp4_splitter"),
	})
}

// ── the Segment and Avatar Editor, layered ──────────────────────────────────

type pairData struct {
	PlayerLabel, Title, Slug string
	BaseRel, OverlayRel      string
	Box, MaxN, BaseN, OverN  int
	BaseExt, OverExt         string
	BaseFps, OverFps         string
	BaseName, OverName       string
	BaseAudio, OverAudio     string
}

// WritePair writes the layered viewer for a base/overlay pair.
//
// base_rel/overlay_rel are the two sources relative to Customers/. The viewer
// needs them to list the base's sibling scenes and to reload itself against a
// different one while carrying the same overlay across.
func WritePair(outdir string, base, over *Meta, box int, baseRel, overRel string) error {
	maxN := base.NbFrames
	if over.NbFrames > maxN {
		maxN = over.NbFrames
	}
	return render(outdir, "pair.gohtml", pairData{
		PlayerLabel: SAELabel("Segment and Avatar Editor", "segment_avatar_editor"),
		Title:       base.SourceName + " + " + over.SourceName,
		Box:         box,
		Slug:        filepath.Base(strings.TrimRight(outdir, "/")),
		BaseRel:     baseRel, OverlayRel: overRel,
		MaxN: maxN, BaseN: base.NbFrames, OverN: over.NbFrames,
		BaseExt: base.Ext, OverExt: over.Ext,
		BaseFps: pyFloat(base.FPS), OverFps: pyFloat(over.FPS),
		BaseName: base.SourceName, OverName: over.SourceName,
		BaseAudio: boolJS(base.HasAudio), OverAudio: boolJS(over.HasAudio),
	})
}

// ── the Segment and Avatar Editor, timeline ─────────────────────────────────

type seqData struct {
	PlayerLabel, Title, Manifest, RootRel string
	Box, Total                            int
}

// WriteSeq writes the multi-scene timeline viewer.
//
// A scene on its own cannot show the thing that most often goes wrong — how one
// scene JOINS the next. A hard cut, a pose that jumps, a voice that starts
// before the picture settles: all of them live at a boundary, and a single-clip
// viewer has no boundaries in it.
func WriteSeq(outdir string, manifest []map[string]any, box int, rootRel string) error {
	total, names := 0, []string{}
	for _, m := range manifest {
		if v, ok := m["base_n"].(int); ok {
			total += v
		}
		names = append(names, itoa(m["n"]))
	}
	if total < 1 {
		total = 1
	}
	return render(outdir, "seq.gohtml", seqData{
		PlayerLabel: SAELabel("Segment and Avatar Editor", "segment_avatar_editor"),
		Title:       "timeline: scenes " + strings.Join(names, ", "),
		Box:         box,
		Total:       total,
		Manifest:    jsonStr(manifest),
		RootRel:     rootRel,
	})
}
