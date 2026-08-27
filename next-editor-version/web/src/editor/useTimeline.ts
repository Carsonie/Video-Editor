import { useCallback, useEffect, useMemo, useState } from 'react';

import { api } from '../api';
import type { SeqScene, SiblingRow, VttRow } from '../types';

export type Layer = 'base' | 'overlay';

/** Where a global frame lands: which scene, and the frame inside it. */
export interface At {
  i: number;
  local: number;
  scene: SeqScene | null;
}

export interface Timeline {
  scenes: SeqScene[];
  all: SiblingRow[];
  vtt: VttRow[];
  wps: number;
  /** cumulative frame offset of each scene, so `starts[i] + local` is global */
  starts: number[];
  total: number;
  marks: Record<string, number[]>;
  /** the version stamp on every frame URL — see the note in useClip */
  ver: number;
  loading: boolean;
  error: string | null;
  at: (g: number) => At;
  reload: () => Promise<void>;
  /** Take one scene's counts from the SERVER rather than from this page.
   *
   *  The page's idea of a length can drift below the cache's real one — 478
   *  here against 476 there — and an edit aimed at a frame number is then
   *  aimed at the wrong frame. Straighten the counts BEFORE writing. */
  resync: (i: number) => Promise<string[]>;
  setSceneLen: (i: number, layer: Layer, n: number) => void;
  setMarksFor: (slug: string, marks: number[]) => void;
  bump: () => void;
}

export function slugOf(s: SeqScene | null, layer: Layer): string | null {
  if (!s) return null;
  return layer === 'base' ? s.base_slug : s.over_slug;
}

export function lenOf(s: SeqScene | null, layer: Layer): number {
  if (!s) return 0;
  return layer === 'base' ? s.base_n : s.over_n;
}

export function extOf(s: SeqScene | null, layer: Layer): string {
  if (!s) return '.jpg';
  return layer === 'base' ? s.base_ext : s.over_ext;
}

/** A scene's own name for the reader. `base` is the FOOTAGE and `overlay` is
 *  the AVATAR — two separate files, with separate lengths, edited one layer at
 *  a time, so they are never called "the clip". */
export function layerName(layer: Layer): string {
  return layer === 'base' ? 'segment' : 'overlay';
}

export function useTimeline(root: string, ns: number[]): Timeline {
  const [scenes, setScenes] = useState<SeqScene[]>([]);
  const [all, setAll] = useState<SiblingRow[]>([]);
  const [vtt, setVtt] = useState<VttRow[]>([]);
  const [wps, setWps] = useState(3.44);
  const [marks, setMarks] = useState<Record<string, number[]>>({});
  const [ver, setVer] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const key = ns.join(',');

  const reload = useCallback(async () => {
    // Nothing asked for yet. This is the normal state for one render while
    // `ns=all` is being resolved from the script, and asking the backend for
    // an empty set is a refusal, not a question — it would put "no scenes
    // selected" on screen as though something were wrong.
    const want = key.split(',').filter(Boolean).map(Number);
    if (!root || want.length === 0) {
      setLoading(true);
      return;
    }
    setLoading(true);
    try {
      const seq = await api.openSeq(root, want);
      // A backend too old to send the manifest answers everything else
      // perfectly and hands back nothing to draw. Left unchecked that is a
      // BLANK PAGE and a stack trace three layers down — it happened, and the
      // cause was a server process still running the previous build.
      if (!Array.isArray(seq.manifest)) {
        throw new Error(
          'The backend answered without a manifest. It is running an older ' +
            'build than this page expects — restart the Go server.',
        );
      }
      setScenes(seq.manifest);

      // The scene list comes from /api/siblings, which resolves EVERY scene of
      // the store — including the ones not on the timeline, which is what the
      // ticks in the list are for.
      const first = seq.manifest[0];
      if (first) {
        const sib = await api.siblings(first.base_rel);
        setAll(Object.values(sib.by_version)[0] ?? []);
      }

      try {
        const v = await api.vtt(root);
        setVtt(v.scenes);
        setWps(v.wps);
      } catch {
        // A store with no script.json has no lines to show. That is a gap in
        // the panel, not a failure of the editor.
        setVtt([]);
      }

      const got: Record<string, number[]> = {};
      await Promise.all(
        seq.manifest.flatMap((s) =>
          (['base', 'overlay'] as Layer[]).map(async (l) => {
            const slug = slugOf(s, l);
            if (!slug) return;
            got[slug] = (await api.marks(slug)).marks;
          }),
        ),
      );
      setMarks(got);
      setVer((v) => v + 1);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [root, key]);

  useEffect(() => {
    void reload();
  }, [reload]);

  // The timeline's length is the SEGMENT's, scene by scene. The overlay is
  // routinely shorter — a 190-frame segment under a 152-frame avatar is normal
  // — and the footage is what the viewer is watching.
  const starts = useMemo(() => {
    const out: number[] = [];
    let acc = 0;
    for (const s of scenes) {
      out.push(acc);
      acc += s.base_n;
    }
    return out;
  }, [scenes]);

  const total = useMemo(
    () => Math.max(1, scenes.reduce((a, s) => a + s.base_n, 0)),
    [scenes],
  );

  const at = useCallback(
    (g: number): At => {
      for (let i = scenes.length - 1; i >= 0; i--) {
        if (g > starts[i]) return { i, local: g - starts[i], scene: scenes[i] };
      }
      return { i: 0, local: 1, scene: scenes[0] ?? null };
    },
    [scenes, starts],
  );

  const setSceneLen = useCallback((i: number, layer: Layer, n: number) => {
    setScenes((cur) =>
      cur.map((s, k) =>
        k === i ? { ...s, ...(layer === 'base' ? { base_n: n } : { over_n: n }) } : s,
      ),
    );
    setVer((v) => v + 1);
  }, []);

  const setMarksFor = useCallback((slug: string, m: number[]) => {
    setMarks((cur) => ({ ...cur, [slug]: m }));
  }, []);

  const bump = useCallback(() => setVer((v) => v + 1), []);

  const resync = useCallback(
    async (i: number): Promise<string[]> => {
      const s = scenes[i];
      if (!s) return [];
      const fixed: string[] = [];
      for (const layer of ['base', 'overlay'] as Layer[]) {
        const slug = slugOf(s, layer);
        if (!slug) continue;
        const real = (await api.frameMap(slug)).nb_frames;
        if (real !== lenOf(s, layer)) {
          fixed.push(`${layerName(layer)} ${lenOf(s, layer)} → ${real}`);
          setSceneLen(i, layer, real);
        }
      }
      return fixed;
    },
    [scenes, setSceneLen],
  );

  return {
    scenes, all, vtt, wps, starts, total, marks, ver, loading, error,
    at, reload, resync, setSceneLen, setMarksFor, bump,
  };
}
