// What the backend answers with. One shape per endpoint, named after the
// endpoint, so a change in the Go server shows up here as a type error rather
// than as an empty panel.

export type Ext = '.jpg' | '.png';

export interface ListDir {
  name: string;
  path: string;
  /** a store folder jumps straight to its raw recordings */
  jump: string | null;
  segments_jump: string | null;
}

export interface ListFile {
  name: string;
  path: string;
  size: number;
}

export interface ListResponse {
  path: string;
  parent: string | null;
  dirs: ListDir[];
  files: ListFile[];
}

export interface OpenResponse {
  url: string;
}

export interface FrameMapResponse {
  frame_map: number[];
  nb_frames: number;
}

export interface MarksResponse {
  marks: number[];
}

/** Every frame edit answers with the new length and where to stand. */
export interface EditResponse {
  nb_frames: number;
  current: number;
  marks: number[];
  /** − Frame: how many it ACTUALLY took, which can be fewer near an edge */
  actual?: number;
  dropped_marks?: number;
  span?: number;
  frame_map?: number[];
}

export interface CutSegment {
  name: string;
  start_frame?: number;
  end_frame?: number;
  duration_s?: number;
  edited?: boolean;
  warning?: string | null;
  error?: string;
}

export interface CutResponse {
  outdir: string;
  version: number;
  count: number;
  segments: CutSegment[];
}

export interface SaveResponse {
  path: string;
  archived_to: string;
  duration_s: number;
  nb_frames: number;
  frames_written: number | null;
  frames_expected: number;
  /** set when the rebuild wrote a different number of frames than the preview
   *  showed — the class of fault this whole tool exists to catch */
  warning: string | null;
}

export interface HandoffMade {
  n: number;
  label: string;
  folder: string;
  frames: number | null;
}

export interface HandoffResponse {
  handed_off: HandoffMade[];
  first_n: number;
  scenes: number;
  script: string;
  into: string;
  archived_to: string | null;
}

export interface ArchiveResponse {
  folder: string;
  would_archive?: string[];
  into?: string;
  archived_to?: string | null;
  archived?: string[];
  empty: boolean;
  moved?: boolean;
}

/** The page's own idea of the clip it is editing, from the viewer config the
 *  backend embeds. Phase 2 reads it from /api/clip instead — see api.ts. */
export interface ClipMeta {
  slug: string;
  source: string;
  source_name: string;
  nb_frames: number;
  fps: number;
  ext: Ext;
  has_audio: boolean;
  edited: boolean;
  disp_w: number;
  disp_h: number;
}

export interface ApiError {
  error: string;
}

// ── the Segment and Avatar Editor ───────────────────────────────────────────

/** One scene on the timeline. Each keeps its OWN extraction — they are ordinary
 *  pairs, cached and reused — and the manifest maps a global frame to a scene
 *  plus a local one. Concatenating the frames into one new cache would have
 *  been simpler and would have thrown away both the reuse and the ability to
 *  say WHICH scene you are looking at. */
export interface SeqScene {
  n: number;
  label: string;
  /** A BOOKEND (00-opening, 99-closing) is a real folder with no row in
   *  script.json. It can sit on a timeline — that is the point, you watch the
   *  joins — but it cannot be joined or split, because both rewrite the scene
   *  list and it is not in one. The page has to know that BEFORE it offers to. */
  in_script: boolean;
  /** The opening has no raw narration render — it is built from two clips plus
   *  a morph. A join across that gap has to FILL it, or the next scene's
   *  narration slides forward on top of the opening. */
  has_narration: boolean;
  base_slug: string;
  base_n: number;
  base_ext: Ext;
  base_audio: boolean;
  over_slug: string | null;
  over_n: number;
  over_ext: Ext;
  over_audio: boolean;
  base_rel: string;
  over_rel: string | null;
  fps: number;
}

export interface OpenSeqResponse {
  url: string;
  slug: string;
  scenes: number[];
  missing: number[];
  manifest: SeqScene[];
}

/** One row of /api/siblings: every scene of the store, resolved. */
export interface SiblingRow {
  n: number;
  label: string;
  name: string;
  dur: number | null;
  path: string | null;
  overlay: string | null;
  src: string | null;
  overlay_src: string | null;
  /** No sandbox copy. Shown as a gap rather than quietly resolved from dev,
   *  because an edit that appears to work on a file the editor cannot write is
   *  worse than an obvious hole. */
  missing: boolean;
  extra?: boolean;
  frames: number | null;
  frames_exact: boolean;
  overlay_frames: number | null;
  overlay_frames_exact: boolean;
  current: boolean;
}

export interface SiblingsResponse {
  layout: string;
  editor_scope: string;
  by_version: Record<string, SiblingRow[]>;
  folder: string;
}

export interface VttRow {
  n: number;
  label: string;
  line: string;
  words: number;
  pause: number;
  /** left on the half of a split with no line — its job is done the moment
   *  someone writes one */
  todo: boolean;
}

export interface VttResponse {
  wps: number;
  store: string;
  title: string;
  scenes: VttRow[];
}

export interface JoinResponse {
  joined: number[];
  label: string;
  new_n: number;
  renamed: string[];
  filled: { scene: number; track: string; frames: number }[];
  renumbered: { from: number; to: number }[];
  scenes: number;
  archived_to: string;
  /** set on a REFUSAL: the track some scenes have and others do not */
  gap?: string;
  scenes_missing?: number[];
}

export interface SplitResponse {
  split: number;
  at: number;
  labels: string[];
  tracks: string[];
  renamed: string[];
  renumbered: { from: number; to: number }[];
  scenes: number;
  line_stayed_with: string;
  archived_to: string;
}

export interface RenumberState {
  renumbered: boolean;
  moved: { from: number; to: number }[];
}
