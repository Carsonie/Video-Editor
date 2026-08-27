// Command editord serves both video players — the Go backend of the rebuild.
//
//	go run ./cmd/editord --port 8870
//
// It answers the SAME 29 endpoints as the Python server, so the existing test
// suite validates it unchanged. That is the whole point of this phase: the
// backend is proved against tests that never knew it was rewritten.
//
// It runs BESIDE the Python server, on its own port and its own cache, so the
// working editors keep working while this is built.
package main

import (
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"

	"rentify.app/video-editor/internal/editor"
)

// findRepoRoot walks up looking for the folder that HAS a Customers/
// subdirectory — not a hardcoded depth, so moving this tool does not silently
// point the browser at the wrong place.
func findRepoRoot(start string) (string, error) {
	d := start
	for i := 0; i < 10; i++ {
		if fi, err := os.Stat(filepath.Join(d, "Customers")); err == nil && fi.IsDir() {
			return d, nil
		}
		parent := filepath.Dir(d)
		if parent == d {
			break
		}
		d = parent
	}
	return "", fmt.Errorf("could not find a Customers/ folder above %s — run setup_demo.py first", start)
}

func main() {
	port := flag.Int("port", 8870, "port to serve on")
	// The Go server keeps its OWN cache by default. The two servers write
	// meta.json with independently derived mtimes, so a shared cache would have
	// each of them decide the other's extraction was stale and redo it — slow,
	// and confusing to debug. Point them at one folder deliberately, not by
	// accident.
	cacheDir := flag.String("cache", "", "frame cache (default <repo>/cache-go)")
	rootFlag := flag.String("root", "", "repo root holding Customers/ (default: found by walking up)")
	// The test drives hundreds of calls and writes its own log. Without this it
	// would bury a day of real editing in its own fixture traffic.
	noLog := flag.Bool("no-session-log", false, "do not write the editing session log")
	flag.Parse()

	here, err := os.Getwd()
	if err != nil {
		log.Fatal(err)
	}
	root := *rootFlag
	if root == "" {
		if exe, err := os.Executable(); err == nil {
			if r, err := findRepoRoot(filepath.Dir(exe)); err == nil {
				root = r
			}
		}
	}
	if root == "" {
		r, err := findRepoRoot(here)
		if err != nil {
			log.Fatal(err)
		}
		root = r
	}
	cache := *cacheDir
	if cache == "" {
		cache = filepath.Join(root, "cache-go")
	}
	if err := os.MkdirAll(cache, 0o755); err != nil {
		log.Fatal(err)
	}

	editor.SetVersionRoot(root)
	session := editor.NewSessionLog(root, *noLog)
	session.Start(*port, root)

	s := editor.New(root, cache, session)
	fmt.Printf("  video players serving on http://localhost:%d   (Go)\n", *port)
	fmt.Printf("  browse root: %s\n", filepath.Join(root, "Customers"))
	fmt.Printf("  frame cache: %s\n", cache)
	fmt.Printf("  session log: %s\n", session.Path())

	addr := fmt.Sprintf("127.0.0.1:%d", *port)
	if err := http.ListenAndServe(addr, s.Handler()); err != nil {
		log.Fatal(err)
	}
}
