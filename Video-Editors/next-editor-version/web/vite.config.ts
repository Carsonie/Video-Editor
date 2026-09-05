import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';

// The front-end server. It serves the app and proxies everything the Go
// backend owns, so the browser talks to one origin and nothing needs CORS.
//
// TWO kinds of path go across:
//   /api/*             the 29 endpoints
//   /<slug>/frames/*   the extracted frames, and each clip's audio
//
// The second one cannot be matched by prefix — a cache slug is an arbitrary
// name — so it is matched by SHAPE instead. Anything that is not the app's own
// asset and looks like a cache file belongs to the backend.
const BACKEND = process.env.EDITOR_API ?? 'http://localhost:8870';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5180,
    proxy: {
      '/api': BACKEND,
      // frames, audio and the old server-rendered pages
      '^/[^/]+/(frames/.*|audio\\.m4a|viewer\\.html)$': BACKEND,
    },
  },
});
