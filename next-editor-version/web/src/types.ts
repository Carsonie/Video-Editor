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
