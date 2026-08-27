package editor

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

// SAELabel is the "MP4 Splitter v8" string rendered at the foot of a page.
//
// The number is read from the PLAYER'S OWN `VERSION` file, at runtime, exactly
// as the Python players read it — that file is the single source of the number,
// and the repo's rule is that the version on screen is the version in git.
//
// The pages this server renders ARE those players' pages, lifted verbatim, so
// they carry those players' versions. A Go marker here would say something true
// about the server and something false about the page.
var repoRootForVersions string

func SetVersionRoot(root string) { repoRootForVersions = root }

func SAELabel(name, folder string) string {
	v := "?"
	if repoRootForVersions != "" {
		b, err := os.ReadFile(filepath.Join(repoRootForVersions, folder, "VERSION"))
		if err == nil && strings.TrimSpace(string(b)) != "" {
			v = strings.TrimSpace(string(b))
		}
	}
	return fmt.Sprintf("%s v%s", name, v)
}

func itoa(v any) string {
	switch x := v.(type) {
	case int:
		return fmt.Sprint(x)
	case float64:
		return fmt.Sprint(int(x))
	}
	return fmt.Sprint(v)
}

var wordish = regexp.MustCompile(`[A-Za-z0-9]`)

// Words counts SPOKEN words — the port of vtt.py's own count, not a re-write.
//
// A token with no letter or digit in it is punctuation standing alone. An em
// dash between spaces is the one that occurs here, and the voice does not say
// it. A plain split counted it, which added a whole word — 0.29s at 3.44 words
// per second — to every line written with a spaced dash.
func Words(line string) int {
	n := 0
	for _, w := range strings.Fields(line) {
		if wordish.MatchString(w) {
			n++
		}
	}
	return n
}
