import { useCallback, useEffect, useState } from 'react';

import { api } from '../api';
import type { ClipMeta } from '../types';

/**
 * Everything the splitter knows about the clip it has open: the facts from the
 * backend, the marks, and the frame map.
 *
 * `ver` is the cache buster for frame images and it is CENTRAL, not incidental.
 * A frame's URL is its POSITION, so after an edit the same URL holds different
 * pixels — and without a new `ver` the browser revalidates, the server
 * truthfully answers 304, and the STALE picture is shown. The symptom is badly
 * misleading: the count drops but the pictures do not move, so a delete in the
 * middle of a clip looks exactly like frames being taken off the END. That was
 * reported as a bug once, in those words.
 */
export interface Clip {
  meta: ClipMeta | null;
  marks: Set<number>;
  frameMap: number[];
  ver: number;
  error: string | null;
  loading: boolean;
  /** Take everything from the server again — after a save, or a cut. */
  reload: () => Promise<void>;
  setMarks: (m: Set<number>) => void;
  /** Fold an edit's answer in: new length, new marks, a fresh picture. */
  applyEdit: (r: { nb_frames: number; marks?: number[] }) => void;
  /** Ask the backend whether this clip still counts as edited.
   *
   *  Undo can take a clip all the way back to the file on disk, at which point
   *  there is nothing left to save — and only the server knows that, because
   *  `edited` is not derivable from the COUNT. Equal adds and deletes leave the
   *  count unchanged with the clip genuinely edited, and undoing the last one
   *  leaves it changed with the clip genuinely clean. */
  refreshMeta: () => Promise<void>;
}

export function useClip(slug: string): Clip {
  const [meta, setMeta] = useState<ClipMeta | null>(null);
  const [marks, setMarks] = useState<Set<number>>(new Set());
  const [frameMap, setFrameMap] = useState<number[]>([]);
  const [ver, setVer] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const [m, mk, fm] = await Promise.all([
        api.clip(slug),
        api.marks(slug),
        api.frameMap(slug),
      ]);
      setMeta(m);
      setMarks(new Set(mk.marks));
      setFrameMap(fm.frame_map);
      setVer((v) => v + 1);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [slug]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const refreshMeta = useCallback(async () => {
    const m = await api.clip(slug);
    setMeta(m);
  }, [slug]);

  const applyEdit = useCallback((r: { nb_frames: number; marks?: number[] }) => {
    setMeta((m) => (m ? { ...m, nb_frames: r.nb_frames, edited: true } : m));
    if (r.marks) setMarks(new Set(r.marks));
    setVer((v) => v + 1);
    // The map has changed shape, so re-read it rather than guessing. It is one
    // integer per frame and only fetched when something actually moved.
    void api.frameMap(slug).then((fm) => setFrameMap(fm.frame_map));
  }, [slug]);

  return {
    meta, marks, frameMap, ver, error, loading,
    reload, setMarks, applyEdit, refreshMeta,
  };
}
