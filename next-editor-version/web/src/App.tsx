import { Navigate, Route, Routes } from 'react-router';

import { Browse } from './routes/Browse';
import { Splitter } from './routes/Splitter';

// Three views, and the URL says which clip each is looking at — so a page can
// be reloaded, or a link to one scene sent to someone, without the app having
// to remember anything.
export function App() {
  return (
    <Routes>
      <Route path="/" element={<Browse />} />
      <Route path="/browse" element={<Browse />} />
      <Route path="/clip/:slug" element={<Splitter />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
