import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router';
import {
  Alert,
  Box,
  Group,
  Loader,
  Paper,
  ScrollArea,
  Stack,
  Text,
  Tooltip,
} from '@mantine/core';

import { api, frameUrl, audioUrl } from '../api';
import { Controls, type TrackPick } from '../editor/Controls';
import { SceneList } from '../editor/SceneList';
import { VttPanel } from '../editor/VttPanel';
import {
  extOf,
  lenOf,
  layerName,
  slugOf,
  useTimeline,
  type Layer,
} from '../editor/useTimeline';
import { usePlayback } from '../hooks/usePlayback';

const BOX = 750;

/**
 * The Segment and Avatar Editor.
 *
 * Several scenes on ONE timeline, the avatar laid over the footage. A scene on
 * its own cannot show the thing that most often goes wrong — how one scene
 * JOINS the next. A hard cut, a pose that jumps, a voice that starts before the
 * picture settles: all of them live at a boundary, and a single-clip viewer has
 * no boundaries in it.
 *
 * A ONE-SCENE timeline is the layered view. Same controls, same code — the
 * Python build had two pages for this and they drifted.
 */
export function Editor() {
  const [params, setParams] = useSearchParams();
  const root = params.get('root') ?? '';
  const nsParam = params.get('ns') ?? '';
  const ns = useMemo(
    () => nsParam.split(',').filter(Boolean).map(Number),
    [nsParam],
  );

  // `ns=all` is how the browser hands over without knowing the scene numbers.
  // Resolved from the SCRIPT, so the timeline opens on the video's own scene
  // list. Bookends are not in the script and so are not included — they are
  // ticked on from the scene list, deliberately, because a bookend can sit on a
  // timeline but cannot be joined or split.
  useEffect(() => {
    if (nsParam !== 'all' || !root) return;
    void api
      .vtt(root)
      .then((v) => setParams({ root, ns: v.scenes.map((r) => r.n).join(',') }, { replace: true }))
      .catch(() => setParams({ root, ns: '1' }, { replace: true }));
  }, [nsParam, root, setParams]);

  const t = useTimeline(root, nsParam === 'all' ? [] : ns);
  const [g, setG] = useState(1);
  const [picked, setPicked] = useState<Set<number>>(new Set());
  /** "n:layer" for every track PROTECTED from edits. Absent means editable. */
  const [locked, setLocked] = useState<Set<string>>(new Set());
  const [loop, setLoop] = useState(false);
  const [joinTrack, setJoinTrack] = useState<TrackPick>('both');
  const [splitTrack, setSplitTrack] = useState<TrackPick>('both');
  const [clip, setClip] = useState<{ i: number; local: number } | null>(null);
  const [history, setHistory] = useState<Record<number, number[][][]>>({});
  const [renumbered, setRenumbered] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { scenes, starts, total, marks, ver } = t;
  const here = t.at(g);
  const scene = here.scene;

  useEffect(() => setPicked(new Set(scenes.map((s) => s.n))), [scenes]);

  // THE UNDO HISTORY IS KEYED BY POSITION, so it cannot outlive the set of
  // scenes it was taken from. After a join, index 0 is a DIFFERENT clip, and
  // offering to restore the pre-join frame map into it is offering to undo one
  // clip's edits onto another. The server would refuse the map, so the damage
  // stops there — but a control that can only fail should not be on screen.
  useEffect(() => {
    setHistory({});
  }, [nsParam, root]);
  useEffect(() => setG((x) => Math.max(1, Math.min(total, x))), [total]);

  // Once a join or a split has renumbered the scenes, a SINGLE-scene save is
  // refused: the numbers on disk and the numbers in the script disagree until
  // the whole set is written. Read from script.json rather than remembered
  // here — a join RELOADS the timeline, so a flag held in JavaScript dies at
  // exactly the moment it starts mattering.
  const readRenumber = useCallback(async () => {
    if (!root) return;
    try {
      setRenumbered((await api.renumberState(root)).renumbered);
    } catch {
      setRenumbered(false);
    }
  }, [root]);
  useEffect(() => void readRenumber(), [readRenumber, scenes]);

  const guard = useCallback(async (what: string, fn: () => Promise<void>) => {
    setError(null);
    setBusy(what);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }, []);

  // ── which layers an edit touches ────────────────────────────────────────
  const liveLayers = useCallback(
    (i: number): Layer[] =>
      (['base', 'overlay'] as Layer[]).filter((l) => {
        const s = scenes[i];
        return s && slugOf(s, l) && !locked.has(`${s.n}:${l}`);
      }),
    [scenes, locked],
  );

  const layers = scene ? liveLayers(here.i) : [];

  // ── the zone ────────────────────────────────────────────────────────────
  const zoneOf = useCallback(
    (i: number, layer: Layer, local: number) => {
      const s = scenes[i];
      const slug = slugOf(s, layer);
      const ms = slug ? [...(marks[slug] ?? [])].sort((a, b) => a - b) : [];
      let a = 1;
      let b = lenOf(s, layer);
      for (const m of ms) {
        if (m <= local) a = m;
        else {
          b = m - 1;
          break;
        }
      }
      return { a, b: Math.max(a, b) };
    },
    [scenes, marks],
  );

  const play = usePlayback({
    frame: g,
    total,
    fps: scene?.fps ?? 25,
    hasAudio: Boolean(scene?.over_audio || scene?.base_audio),
    loopZone: loop && scene
      ? (() => {
          const z = zoneOf(here.i, 'base', here.local);
          return { a: starts[here.i] + z.a, b: starts[here.i] + z.b };
        })()
      : null,
    onFrame: setG,
  });

  // ── editing ─────────────────────────────────────────────────────────────
  const snapshot = useCallback(
    async (i: number, ls: Layer[]) => {
      const maps: number[][] = [];
      for (const l of ls) {
        const slug = slugOf(scenes[i], l);
        maps.push(slug ? (await api.frameMap(slug)).frame_map : []);
      }
      return maps;
    },
    [scenes],
  );

  const pushHist = useCallback((i: number, maps: number[][]) => {
    setHistory((h) => ({ ...h, [i]: [...(h[i] ?? []), maps].slice(-20) }));
  }, []);

  /**
   * One edit, on every ticked track of the current scene.
   *
   * TWO RULES, both paid for:
   *
   * 1. CHECK EVERY TICKED TRACK BEFORE WRITING ANY. The tracks are routinely
   *    different lengths — 480 segment against 442 avatar is normal — so the
   *    frame on screen can exist in one and be past the end of the other. This
   *    used to skip past a refusal, which changed the tracks that worked and
   *    left the rest: a HALF-DONE edit that reads as an error.
   *
   * 2. ONE zone, decided BEFORE anything is written. Editing the first layer
   *    shifts its marks, so recomputing the zone for the second read the
   *    already-moved marks and gave a larger span — a 35-frame zone grew the
   *    segment by 35 and the overlay by 70. The zone the user is looking at is
   *    the zone both layers get.
   */
  const doEdit = useCallback(
    (kind: 'dup' | 'del', span: boolean) =>
      void guard('edit', async () => {
        const i = here.i;
        const s = scenes[i];
        if (!s) return;
        const ls = liveLayers(i);
        if (ls.length === 0) {
          setStatus(`Scene ${s.n}: tick the segment or the overlay first — nothing to act on.`);
          return;
        }
        play.stop();
        // Straighten the counts BEFORE aiming an edit at a frame number.
        const fixed = await t.resync(i);
        if (fixed.length) {
          setStatus(
            `Scene ${s.n}: this page was out of step with the clip (${fixed.join(', ')}). ` +
              `Corrected — try that edit again.`,
          );
          return;
        }
        const local = here.local;
        if (!span) {
          const short = ls.filter((l) => local > lenOf(s, l));
          if (short.length) {
            setError(
              `Frame ${local} is past the end of the ${short.map(layerName).join(' and ')} ` +
                `on scene ${s.n} (${ls.map((l) => `${layerName(l)}: ${lenOf(s, l)}`).join(', ')}). ` +
                `Nothing was changed. Untick the shorter track, or move to a frame both have.`,
            );
            return;
          }
        }
        const zone = span ? zoneOf(i, 'base', local) : null;
        const before = await snapshot(i, ls);
        const changed: string[] = [];
        for (const l of ls) {
          const slug = slugOf(s, l)!;
          const d = span
            ? kind === 'dup'
              ? await api.dupSpan(slug, zone!.a, zone!.b)
              : await api.delSpan(slug, zone!.a, zone!.b)
            : kind === 'dup'
              ? await api.dup(slug, local, 1, 'right')
              : await api.del(slug, local, 1, 'right');
          t.setSceneLen(i, l, d.nb_frames);
          if (d.marks) t.setMarksFor(slug, d.marks);
          changed.push(`${layerName(l)} → ${d.nb_frames}`);
        }
        pushHist(i, before);
        setStatus(`Scene ${s.n}: ${changed.join(' · ')}`);
      }),
    [guard, here, scenes, liveLayers, play, t, zoneOf, snapshot, pushHist],
  );

  const toggleMark = useCallback(
    () =>
      void guard('mark', async () => {
        const s = scene;
        if (!s) return;
        const slug = slugOf(s, 'base');
        if (!slug) return;
        const on = !(marks[slug] ?? []).includes(here.local);
        const d = await api.mark(slug, here.local, on);
        t.setMarksFor(slug, d.marks);
      }),
    [guard, scene, marks, here, t],
  );

  const undoScene = useCallback(
    () =>
      void guard('undo', async () => {
        const i = here.i;
        const stack = history[i] ?? [];
        const prev = stack[stack.length - 1];
        if (!prev) return;
        const ls = liveLayers(i);
        for (let k = 0; k < ls.length && k < prev.length; k++) {
          const slug = slugOf(scenes[i], ls[k]);
          if (!slug || prev[k].length === 0) continue;
          const d = await api.restore(slug, prev[k]);
          t.setSceneLen(i, ls[k], d.nb_frames);
          t.setMarksFor(slug, d.marks);
        }
        setHistory((h) => ({ ...h, [i]: stack.slice(0, -1) }));
        setStatus(`Scene ${scenes[i]?.n}: undone`);
      }),
    [guard, here.i, history, liveLayers, scenes, t],
  );

  const balance = useCallback(
    () =>
      void guard('balance', async () => {
        const work = scenes
          .map((s, i) => ({ s, i }))
          .filter(({ s }) => picked.has(s.n) && s.over_slug && s.base_n !== s.over_n)
          .map(({ s, i }) => {
            const diff = s.base_n - s.over_n;
            const short: Layer = diff > 0 ? 'overlay' : 'base';
            return { i, s, short, count: Math.abs(diff) };
          })
          .filter((w) => !locked.has(`${w.s.n}:${w.short}`));
        if (work.length === 0) {
          setStatus('Nothing to do — the ticked scenes already match, or the short track is locked.');
          return;
        }
        if (
          !window.confirm(
            `Balance ${work.length} scene(s)?\n\n` +
              work.map((w) => `  scene ${w.s.n}: +${w.count} to the ${layerName(w.short)}`).join('\n') +
              `\n\nEach repeats that track's LAST frame. The last frame is the settled end ` +
              `of the shot, so the repeat is invisible. Undoable per scene.`,
          )
        )
          return;
        play.stop();
        const done: string[] = [];
        for (const w of work) {
          const slug = slugOf(w.s, w.short)!;
          const before = await snapshot(w.i, [w.short]);
          const d = await api.dup(slug, lenOf(w.s, w.short), w.count, 'right');
          t.setSceneLen(w.i, w.short, d.nb_frames);
          if (d.marks) t.setMarksFor(slug, d.marks);
          pushHist(w.i, before);
          done.push(`${w.s.n} +${w.count} ${w.short === 'base' ? 'seg' : 'ovl'}`);
        }
        setStatus(`Balanced: ${done.join(', ')}`);
      }),
    [guard, scenes, picked, locked, play, snapshot, t, pushHist],
  );

  const saveScene = useCallback(
    (i: number) =>
      guard('save', async () => {
        const s = scenes[i];
        const ls = liveLayers(i);
        if (!s || ls.length === 0) return;
        if (
          !window.confirm(
            `Overwrite scene ${s.n} (${s.label}) in sandbox/?\n\n` +
              ls.map((l) => `  ${layerName(l)}: ${lenOf(s, l)} frames`).join('\n') +
              `\n\nEach file is archived to z_History/ first.`,
          )
        )
          return;
        const notes: string[] = [];
        for (const l of ls) {
          const d = await api.save(slugOf(s, l)!);
          t.setSceneLen(i, l, d.nb_frames);
          // The rebuild is time-based per piece, so it CAN come back short of
          // the length that was on screen. A save says so rather than letting
          // it pass — that is the fault this whole tool exists to catch.
          notes.push(d.warning ? `⚠ ${layerName(l)}: ${d.warning}` : `${layerName(l)}: ${d.nb_frames}`);
        }
        setHistory((h) => ({ ...h, [i]: [] }));
        setStatus(`Saved scene ${s.n} — ${notes.join(' · ')}`);
      }),
    [guard, scenes, liveLayers, t],
  );

  const saveAll = useCallback(
    () =>
      void guard('saveAll', async () => {
        const dirty = scenes.map((_, i) => i).filter((i) => (history[i] ?? []).length > 0);
        if (dirty.length === 0) {
          setStatus('Nothing has unsaved edits.');
          return;
        }
        if (
          !window.confirm(
            `Write ${dirty.length} scene(s) back to sandbox/?\n\n` +
              dirty.map((i) => `  ${scenes[i].n} ${scenes[i].label}`).join('\n') +
              `\n\nEach file is archived to z_History/ first.`,
          )
        )
          return;
        for (const i of dirty) {
          for (const l of liveLayers(i)) {
            await api.save(slugOf(scenes[i], l)!);
          }
        }
        setHistory({});
        // The set has been written, so the numbers on disk and the numbers in
        // the script agree again — lift the lock.
        if (renumbered) await api.renumberClear(root);
        await readRenumber();
        setStatus(`Saved ${dirty.length} scene(s).`);
      }),
    [guard, scenes, history, liveLayers, renumbered, root, readRenumber],
  );

  const doJoin = useCallback(
    () =>
      void guard('join', async () => {
        const eligible = scenes.filter((s) => s.in_script);
        if (eligible.length < 2) return;
        const label = window.prompt(
          `Join these ${eligible.length} scenes into ONE?\n\n` +
            eligible.map((s) => `  ${s.n} ${s.label}`).join('\n') +
            `\n\nThe narration lines are joined with a space, every scene is ` +
            `renumbered 1..N, and the previous state is archived first.\n\n` +
            `Name for the joined scene (lower-case letters, digits, hyphens):`,
          '',
        );
        if (!label) return;
        const tracks =
          joinTrack === 'both' ? ['segment', 'avatar'] : joinTrack === 'base' ? ['segment'] : ['avatar'];
        const body = { root, ns: eligible.map((s) => s.n), label, tracks };
        try {
          const d = await api.join(body);
          setParams({ root, ns: String(d.new_n) });
          setStatus(`Joined ${d.joined.join(', ')} into '${d.label}' — archived to ${d.archived_to}`);
          await t.reload();
        } catch (e) {
          // A track some scenes have and others do not. Dropping it SILENTLY
          // moves every later clip forward — the opening has no narration, so
          // scene 2's would start at frame 1 and Sarah would say the login line
          // over the intro. Filling the gap holds that time open instead.
          const msg = e instanceof Error ? e.message : String(e);
          if (!/fill_gaps/.test(msg)) throw e;
          if (!window.confirm(`${msg}\n\nFill the gap and join?`)) return;
          const d = await api.join({ ...body, fill_gaps: true });
          setParams({ root, ns: String(d.new_n) });
          setStatus(
            `Joined ${d.joined.join(', ')} into '${d.label}' — ` +
              `filled ${d.filled.map((f) => `scene ${f.scene} (${f.frames}f ${f.track})`).join(', ')}`,
          );
          await t.reload();
        }
      }),
    [guard, scenes, joinTrack, root, setParams, t],
  );

  const doSplit = useCallback(
    () =>
      void guard('split', async () => {
        const s = scene;
        if (!s || !s.in_script) return;
        const a = window.prompt(
          `Split scene ${s.n} (${s.label}) at frame ${here.local}?\n\n` +
            `THE NARRATION CANNOT BE SPLIT — the whole line stays with the FIRST ` +
            `half and the second is left empty for you to write.\n\n` +
            `Name for the first half:`,
          s.label,
        );
        if (!a) return;
        const b = window.prompt('Name for the second half:', '');
        if (!b) return;
        const tracks =
          splitTrack === 'both' ? ['segment', 'avatar'] : splitTrack === 'base' ? ['segment'] : ['avatar'];
        const d = await api.split({ root, n: s.n, at: here.local, labels: [a, b], tracks });
        setParams({ root, ns: `${d.split},${d.split + 1}` });
        setStatus(
          `Split into '${d.labels[0]}' and '${d.labels[1]}' — the line stayed with ` +
            `'${d.line_stayed_with}'. Archived to ${d.archived_to}`,
        );
        await t.reload();
      }),
    [guard, scene, here.local, splitTrack, root, setParams, t],
  );

  const copyFrame = useCallback(
    (alsoMac: boolean) => {
      setClip({ i: here.i, local: here.local });
      setStatus(`Copied scene ${scene?.n} frame ${here.local}.`);
      if (!alsoMac || !scene) return;
      // The Mac clipboard gets a PICTURE. The editor's own paste does not use
      // it — that would cost a decode, a round trip and an encode, and the
      // frame map would have no idea what the pasted frame was.
      void fetch(frameUrl(slugOf(scene, 'base')!, here.local, extOf(scene, 'base'), ver))
        .then((r) => r.blob())
        .then((b) => navigator.clipboard.write([new ClipboardItem({ [b.type]: b })]))
        .then(() => setStatus(`Copied frame ${here.local} — and put the picture on the Mac clipboard.`))
        .catch(() => setStatus(`Copied frame ${here.local}. The Mac clipboard refused the picture.`));
    },
    [here, scene, ver],
  );

  const pasteFrame = useCallback(
    () =>
      void guard('paste', async () => {
        if (!clip || !scene) return;
        const i = here.i;
        const ls = liveLayers(i);
        if (ls.length === 0) {
          setStatus('Tick the segment or the overlay first — nothing to paste into.');
          return;
        }
        // Same rule as an edit: check every ticked track before writing any.
        // A paste that lands on one and is refused on the other is a half-done
        // edit, and that shipped four times.
        const src = scenes[clip.i];
        const bad = ls.filter(
          (l) => clip.local > lenOf(src, l) || here.local > lenOf(scene, l),
        );
        if (bad.length) {
          setError(
            `That frame is past the end of the ${bad.map(layerName).join(' and ')}. ` +
              `Nothing was changed.`,
          );
          return;
        }
        for (const l of ls) {
          const d = await api.paste(slugOf(scene, l)!, clip.local, here.local);
          t.setSceneLen(i, l, d.nb_frames);
          if (d.marks) t.setMarksFor(slugOf(scene, l)!, d.marks);
        }
        setStatus(`Pasted frame ${clip.local} after frame ${here.local}.`);
      }),
    [guard, clip, scene, here, scenes, liveLayers, t],
  );

  // ── keyboard ────────────────────────────────────────────────────────────
  const jumpScene = useCallback(
    (d: 1 | -1) => {
      const next = here.i + d;
      if (next < 0 || next >= scenes.length) return;
      setG(starts[next] + 1);
    },
    [here.i, scenes.length, starts],
  );

  const jumpMark = useCallback(
    (d: 1 | -1) => {
      const slug = scene ? slugOf(scene, 'base') : null;
      const ms = slug ? [...(marks[slug] ?? [])].sort((a, b) => a - b) : [];
      const list = d === 1 ? ms : [...ms].reverse();
      const next = list.find((m) => (d === 1 ? m > here.local : m < here.local));
      if (next !== undefined) setG(starts[here.i] + next);
    },
    [scene, marks, here, starts],
  );

  const kb = useRef({ jumpScene, jumpMark, toggleMark, play, setG, total });
  kb.current = { jumpScene, jumpMark, toggleMark, play, setG, total };

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const el = e.target as HTMLElement | null;
      // A typed line is not a shortcut. Without this, writing narration in the
      // VTT panel marks frames and plays the timeline.
      if (el && /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)) return;
      const k = kb.current;
      if (e.key === 'ArrowLeft') {
        k.setG((x) => Math.max(1, x - (e.shiftKey ? 10 : 1)));
        e.preventDefault();
      }
      if (e.key === 'ArrowRight') {
        k.setG((x) => Math.min(k.total, x + (e.shiftKey ? 10 : 1)));
        e.preventDefault();
      }
      if (e.key === ' ') {
        k.play.toggle();
        e.preventDefault();
      }
      if (e.key === 'm' || e.key === 'M') {
        k.toggleMark();
        e.preventDefault();
      }
      if (e.key === '[') {
        e.shiftKey ? k.jumpScene(-1) : k.jumpMark(-1);
        e.preventDefault();
      }
      if (e.key === ']') {
        e.shiftKey ? k.jumpScene(1) : k.jumpMark(1);
        e.preventDefault();
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // ── render ──────────────────────────────────────────────────────────────
  if (t.error) {
    return (
      <Box maw={700} mx="auto" px="md">
        <Alert color="red" title="That timeline could not be built">
          {t.error}
        </Alert>
      </Box>
    );
  }
  if (!scene) {
    return (
      <Group justify="center" mt="xl" gap="xs">
        <Loader size="sm" />
        <Text c="dimmed">extracting {ns.length} scene(s)…</Text>
      </Group>
    );
  }

  const baseSlug = slugOf(scene, 'base')!;
  const overSlug = slugOf(scene, 'overlay');
  const sceneMarks = [...(marks[baseSlug] ?? [])].sort((a, b) => a - b);
  const inScript = scenes.filter((s) => s.in_script);
  const dirty = (history[here.i] ?? []).length > 0;

  return (
    <Box
      mx="auto"
      px="md"
      style={{
        width: BOX + 330 + 40,
        maxWidth: '100%',
        display: 'grid',
        gridTemplateColumns: `${BOX}px 330px`,
        gap: 14,
        alignItems: 'start',
      }}
    >
      <Stack gap={8} miw={0}>
        {/* The stage: the avatar laid over the footage, which is how the
            finished video is actually built. The overlay is a PNG with real
            alpha; the browser stacks the two. */}
        <Box className="stage" w={BOX}>
          {/* The FOOTAGE sets the box. Its own aspect decides the height —
              hardcoding one put the stage at the wrong shape for any clip that
              was not 750x422, and the avatar then hung off the bottom. */}
          <img
            src={frameUrl(baseSlug, Math.min(here.local, scene.base_n), scene.base_ext, ver)}
            width={BOX}
            style={{ height: 'auto' }}
            alt=""
          />
          {/* The AVATAR on top, filling the same box. It is a full-frame alpha
              PNG — the browser stacks the two, which is how the finished video
              is actually built. */}
          {overSlug && here.local <= scene.over_n && (
            <img
              src={frameUrl(overSlug, here.local, scene.over_ext, ver)}
              alt=""
              style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}
            />
          )}
          {sceneMarks.includes(here.local) && <div className="markOverlay" />}
          {(scene.over_audio || scene.base_audio) && (
            <audio
              ref={play.audioRef}
              src={audioUrl(scene.over_audio && overSlug ? overSlug : baseSlug)}
              preload="auto"
            />
          )}
        </Box>

        <Box className="rowbar">
          <div className="sliderWrap">
            {/* One band per SCENE, over the frames it covers. */}
            <div className="segbar">
              {scenes.map((s, i) => {
                const left = (starts[i] / total) * 100;
                const width = (s.base_n / total) * 100;
                return (
                  <Tooltip
                    key={s.n}
                    label={`${s.n} ${s.label} — ${s.base_n} frames segment, ${s.over_n || '—'} overlay`}
                  >
                    <div
                      className={`segband${i === here.i ? ' here' : ''}`}
                      style={{ left: `${left}%`, width: `${width}%` }}
                      onClick={() => setG(starts[i] + 1)}
                    >
                      {width > 8 ? `${s.n} · ${s.label}` : s.n}
                    </div>
                  </Tooltip>
                );
              })}
            </div>
            <div className="sliderRow">
              <input
                className="slider"
                type="range"
                min={1}
                max={total}
                step={1}
                value={g}
                onChange={(e) => setG(Number(e.currentTarget.value))}
              />
              <div className="ticks">
                {sceneMarks.map((m) => (
                  <Tooltip key={m} label={`mark at scene ${scene.n} frame ${m}`}>
                    <div
                      className={`tick${m === here.local ? ' here' : ''}`}
                      style={{ left: `${((starts[here.i] + m - 1) / (total - 1)) * 100}%` }}
                      onClick={() => setG(starts[here.i] + m)}
                    />
                  </Tooltip>
                ))}
              </div>
            </div>
          </div>
          <Group gap={10} mt={4}>
            <Text fz={12} className="num">
              scene <b>{scene.n}</b> {scene.label} · frame {here.local} / {scene.base_n}
            </Text>
            <Text fz={11} c="grape.4" className="num">
              overlay {scene.over_n || '—'}
            </Text>
            <Text fz={11} c="dimmed" className="num" ml="auto">
              {g} / {total} · {((g - 1) / scene.fps).toFixed(3)}s
            </Text>
          </Group>
        </Box>

        <Controls
          play={play}
          loop={loop}
          onLoop={setLoop}
          onStep={(d) => setG((x) => Math.max(1, Math.min(total, x + d)))}
          onScene={jumpScene}
          onMark={toggleMark}
          marked={sceneMarks.includes(here.local)}
          onJumpMark={jumpMark}
          joinTrack={joinTrack}
          splitTrack={splitTrack}
          onJoinTrack={setJoinTrack}
          onSplitTrack={setSplitTrack}
          onJoin={doJoin}
          onSplit={doSplit}
          canJoin={inScript.length >= 2}
          canSplit={scene.in_script && here.local > 1}
          joinWhy={
            inScript.length < 2
              ? 'A join needs at least two scenes that are IN the script. A bookend has no row in script.json, so it cannot be joined.'
              : ''
          }
          splitWhy={
            !scene.in_script
              ? 'This is a bookend — it has no row in script.json, so there is no scene list to rewrite.'
              : 'Move off frame 1 first; a split has to leave something in the first half.'
          }
          onFrame={(k) => doEdit(k, false)}
          onZone={(k) => doEdit(k, true)}
          onCopy={copyFrame}
          onPaste={pasteFrame}
          canPaste={clip !== null}
          onCut={() =>
            void guard('cut', async () => {
              const d = await api.cut(baseSlug);
              setStatus(`Cut into ${d.count} piece(s) as version ${d.version} — ${d.outdir}`);
            })
          }
          onSave={() => void saveScene(here.i)}
          canSave={dirty && !renumbered}
          canEdit={layers.length > 0}
          editWhy={`Scene ${scene.n} has neither track ticked — tick the segment or the overlay in the list to act on it.`}
          busy={busy}
        />

        {renumbered && (
          <Alert color="yellow" p="xs">
            <Text fz={12}>
              The scenes have been renumbered by a join or a split, so the numbers on disk
              and the numbers in the script disagree until the whole set is written.
              Use <b>Save all scenes</b> — a single-scene save is refused until then.
            </Text>
          </Alert>
        )}
        {status && (
          <Text fz={12} c="yellow.4">
            {status}
          </Text>
        )}
        {error && (
          <Alert color="red" p="xs" withCloseButton onClose={() => setError(null)}>
            <Text fz={12}>{error}</Text>
          </Alert>
        )}
        {(history[here.i] ?? []).length > 0 && (
          <Group gap={8}>
            <Text
              fz={12}
              c="blue.4"
              style={{ cursor: 'pointer' }}
              onClick={undoScene}
            >
              ↶ Undo the last edit on scene {scene.n} ({(history[here.i] ?? []).length} to go back)
            </Text>
          </Group>
        )}

        <Paper withBorder radius="md" p="xs">
          <VttPanel
            rows={t.vtt}
            wps={t.wps}
            scenes={scenes}
            currentN={scene.n}
            onSave={async (n, line) => {
              await api.line(root, n, line);
              await t.reload();
            }}
          />
        </Paper>
      </Stack>

      <Paper withBorder radius="md" p="xs">
        <ScrollArea.Autosize mah="calc(100vh - 60px)">
          <SceneList
            all={t.all}
            scenes={scenes}
            picked={picked}
            locked={locked}
            currentN={scene.n}
            onPick={(n, on) =>
              setPicked((p) => {
                const next = new Set(p);
                on ? next.add(n) : next.delete(n);
                return next;
              })
            }
            onLock={(n, layer, unlocked) =>
              setLocked((l) => {
                const next = new Set(l);
                unlocked ? next.delete(`${n}:${layer}`) : next.add(`${n}:${layer}`);
                return next;
              })
            }
            onJump={(n) => {
              const i = scenes.findIndex((s) => s.n === n);
              if (i >= 0) {
                play.stop();
                setG(starts[i] + 1);
              }
            }}
            onRebuild={() =>
              setParams({ root, ns: [...picked].sort((a, b) => a - b).join(',') })
            }
            onSelectAll={(on) =>
              setPicked(on ? new Set(t.all.filter((r) => !r.missing).map((r) => r.n)) : new Set())
            }
            onBalance={balance}
            onSaveAll={saveAll}
            busy={busy}
          />
        </ScrollArea.Autosize>
      </Paper>
    </Box>
  );
}
