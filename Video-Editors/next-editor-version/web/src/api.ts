// The typed client for the Go backend.
//
// ONE rule runs through all of it: an endpoint that refuses says so in the
// body, with a 400 and an `error` string, and that message is written for a
// person to read. So `request` throws an Error carrying THAT text, never a
// status code — the UI shows what the server said rather than inventing its
// own wording for it.

import type {
  ArchiveResponse,
  ClipMeta,
  JoinResponse,
  OpenSeqResponse,
  RenumberState,
  SiblingsResponse,
  SplitResponse,
  VttResponse,
  CutResponse,
  EditResponse,
  FrameMapResponse,
  HandoffResponse,
  ListResponse,
  MarksResponse,
  OpenResponse,
  SaveResponse,
} from './types';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  let body: unknown;
  try {
    body = await res.json();
  } catch {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  const err = (body as { error?: string }).error;
  if (err) throw new Error(err);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return body as T;
}

function get<T>(path: string, params: Record<string, string | number>): Promise<T> {
  const qs = new URLSearchParams(
    Object.entries(params).map(([k, v]) => [k, String(v)]),
  );
  return request<T>(`${path}?${qs}`);
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

/** `which` picks one half of a layered pair. Undefined for a single clip. */
export type Which = 'base' | 'overlay' | undefined;

export const api = {
  // ── browsing ──────────────────────────────────────────────────────────
  list: (path: string) => get<ListResponse>('/api/list', { path }),
  open: (path: string) => get<OpenResponse>('/api/open', { path }),

  /** Several scenes as ONE timeline. A scene on its own cannot show the thing
   *  that most often goes wrong — how one scene JOINS the next. */
  openSeq: (root: string, ns: number[]) =>
    get<OpenSeqResponse>('/api/open-seq', { root, ns: ns.join(',') }),
  /** Every scene of this store, resolved — not a directory listing. */
  siblings: (path: string) => get<SiblingsResponse>('/api/siblings', { path }),

  // ── the script ────────────────────────────────────────────────────────
  /** The Video Timing Table — the lines, and the maths behind them. The clip
   *  LENGTH is left to the page, which knows what is on the timeline including
   *  edits not yet saved; a gap that does not move while you add frames is
   *  just a lie with a decimal point. */
  vtt: (root: string) => get<VttResponse>('/api/vtt', { root }),
  line: (root: string, n: number, line: string) =>
    post<{ n: number; line: string; words: number; unchanged?: boolean }>('/api/line', {
      root,
      n,
      line,
    }),
  join: (body: {
    root: string;
    ns: number[];
    label: string;
    tracks: string[];
    fill_gaps?: boolean;
  }) => post<JoinResponse>('/api/join', body),
  split: (body: { root: string; n: number; at: number; labels: string[]; tracks: string[] }) =>
    post<SplitResponse>('/api/split', body),
  renumberState: (root: string) => get<RenumberState>('/api/renumber-state', { root }),
  renumberClear: (root: string) => post<{ cleared: number }>('/api/renumber-clear', { root }),

  // ── one clip ──────────────────────────────────────────────────────────
  /** The clip's own facts. The old players baked these into the generated
   *  page; a static bundle is handed a slug instead, so it has to ask. */
  clip: (slug: string, which?: Which) =>
    get<ClipMeta>('/api/clip', which ? { slug, which } : { slug }),
  frameMap: (slug: string, which?: Which) =>
    get<FrameMapResponse>('/api/frames/map', which ? { slug, which } : { slug }),
  marks: (slug: string, which?: Which) =>
    get<MarksResponse>('/api/marks', which ? { slug, which } : { slug }),

  mark: (slug: string, frame: number, on: boolean, which?: Which) =>
    post<MarksResponse>('/api/mark', { slug, frame, on, which }),
  clearMarks: (slug: string, which?: Which) =>
    post<MarksResponse>('/api/clear-marks', { slug, which }),

  // ── the frame edits ───────────────────────────────────────────────────
  // Every one of these acts on the PREVIEW CACHE only. The source video is
  // untouched until Save.
  dup: (slug: string, at: number, count: number, side: 'left' | 'right', which?: Which) =>
    post<EditResponse>('/api/frames/dup', { slug, at, count, side, which }),
  del: (slug: string, at: number, count: number, side: 'left' | 'right', which?: Which) =>
    post<EditResponse>('/api/frames/del', { slug, at, count, side, which }),
  dupSpan: (slug: string, a: number, b: number, which?: Which) =>
    post<EditResponse>('/api/frames/dup-span', { slug, a, b, which }),
  delSpan: (slug: string, a: number, b: number, which?: Which) =>
    post<EditResponse>('/api/frames/del-span', { slug, a, b, which }),
  paste: (slug: string, from: number, at: number, which?: Which) =>
    post<EditResponse>('/api/frames/paste', { slug, from, at, which }),
  /** Undo. The map comes from the page, which snapshotted it before the edit. */
  restore: (slug: string, frame_map: number[], which?: Which) =>
    post<{ nb_frames: number; marks: number[] }>('/api/frames/restore', {
      slug,
      frame_map,
      which,
    }),

  // ── writing to disk ───────────────────────────────────────────────────
  cut: (slug: string, which?: Which) => post<CutResponse>('/api/cut', { slug, which }),
  save: (slug: string, which?: Which) => post<SaveResponse>('/api/save', { slug, which }),
  clearEdits: (slug: string, which?: Which) =>
    post<{ nb_frames: number }>('/api/clear-edits', { slug, which }),
  resetEditor: (slug: string, which?: Which) =>
    post<{ ok: boolean }>('/api/reset-editor', { slug, which }),
  handoff: (slug: string, version: number, names: string[], which?: Which) =>
    post<HandoffResponse>('/api/handoff', { slug, version, names, which }),
  /** `dry` asks what WOULD happen, so a confirmation can name the destination
   *  before the user agrees to it rather than after. */
  archive: (body: {
    slug?: string;
    root?: string;
    folder: 'sandbox' | 'dev';
    dry?: boolean;
  }) => post<ArchiveResponse>('/api/archive', body),
};

/** The URL of one extracted frame.
 *
 *  `ver` busts the browser cache. A frame's URL is its POSITION, so after an
 *  edit the same URL holds different pixels — without this the browser
 *  revalidates, the server truthfully answers 304, and the STALE picture is
 *  shown. The symptom is badly misleading: the count drops but the pictures do
 *  not move, so a delete in the middle looks exactly like frames coming off the
 *  end.
 */
export function frameUrl(slug: string, n: number, ext: string, ver: number): string {
  return `/${slug}/frames/frame_${String(n).padStart(5, '0')}${ext}?v=${ver}`;
}

export function audioUrl(slug: string): string {
  return `/${slug}/audio.m4a`;
}
