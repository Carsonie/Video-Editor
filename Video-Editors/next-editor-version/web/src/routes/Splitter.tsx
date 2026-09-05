import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams } from 'react-router';
import {
  Alert,
  Box,
  Group,
  Loader,
  Paper,
  Stack,
  Tabs,
  Text,
} from '@mantine/core';

import { api } from '../api';
import { useClip } from '../hooks/useClip';
import { usePlayback } from '../hooks/usePlayback';
import { EditRow, type Mode, type Sub } from '../splitter/EditRow';
import { FilePanel } from '../splitter/FilePanel';
import { MarksPanel } from '../splitter/MarksPanel';
import { NavRow } from '../splitter/NavRow';
import { Stage } from '../splitter/Stage';
import { Timeline, type Segment } from '../splitter/Timeline';

/**
 * The MP4 Splitter: mark a recording, cut it, hand the pieces over.
 *
 * THE LAYOUT IS THE ARGUMENT. The frame takes the whole main column. ONE
 * toolbar under it holds every control touched every few seconds, in three
 * rows with one job each — WHERE you are, HOW you move, WHAT you change.
 * Anything touched once a session lives in the drawer on the right, behind a
 * tab, where it cannot be hit by accident.
 */
export function Splitter() {
  const { slug = '' } = useParams();
  const clip = useClip(slug);
  const { meta, marks, frameMap, ver } = clip;

  const [frame, setFrame] = useState(1);
  const [mode, setMode] = useState<Mode>('nav');
  const [sub, setSub] = useState<Sub>('add');
  const [loop, setLoop] = useState(false);
  const [tab, setTab] = useState<string | null>('marks');
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  /** Snapshots of the frame map, newest last. Undo restores one. */
  const [history, setHistory] = useState<number[][]>([]);

  const total = meta?.nb_frames ?? 1;
  const fps = meta?.fps ?? 25;
  const sortedMarks = useMemo(() => [...marks].sort((a, b) => a - b), [marks]);

  // The break-point colour follows the FILE: purple for an alpha clip, green
  // for an opaque one. In this view there is no layer toggle to read, so the
  // marks are the only thing that can say which kind is open.
  useEffect(() => {
    if (meta) document.documentElement.dataset.alpha = String(meta.ext === '.png');
  }, [meta]);

  const clamp = useCallback((n: number) => Math.max(1, Math.min(total, n)), [total]);
  const goto = useCallback((n: number) => setFrame(clamp(n)), [clamp]);

  useEffect(() => {
    setFrame((f) => Math.max(1, Math.min(total, f)));
  }, [total]);

  const fmtTime = useCallback(
    (n: number) => `${((n - 1) / fps).toFixed(3)}s`,
    [fps],
  );

  // ── the zone ────────────────────────────────────────────────────────────
  // The span between the break points either side of the pointer. With nothing
  // marked it is the whole clip, which is what makes "− Zone" still meaningful
  // on an unmarked recording.
  const zone = useMemo(() => {
    let a = 1;
    let b = total;
    for (const m of sortedMarks) {
      if (m <= frame) a = m;
      else {
        b = m - 1;
        break;
      }
    }
    return { a, b: Math.max(a, Math.min(b, total)) };
  }, [sortedMarks, frame, total]);

  const segments: Segment[] = useMemo(() => {
    const bounds = [1, ...sortedMarks, total + 1];
    const out: Segment[] = [];
    for (let i = 0; i < bounds.length - 1; i++) {
      const start = bounds[i];
      const end = bounds[i + 1] - 1;
      if (end < start) continue;
      const frames = end - start + 1;
      out.push({ n: out.length + 1, start, end, frames, dur: frames / fps });
    }
    return out;
  }, [sortedMarks, total, fps]);

  const play = usePlayback({
    frame,
    total,
    fps,
    hasAudio: meta?.has_audio ?? false,
    loopZone: loop ? zone : null,
    onFrame: setFrame,
  });

  // ── acting ──────────────────────────────────────────────────────────────
  const run = useCallback(
    async (fn: () => Promise<void>) => {
      setError(null);
      try {
        await fn();
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    },
    [],
  );

  /** Keep the map we are about to change, so Undo has somewhere to go back to. */
  const snapshot = useCallback(() => {
    setHistory((h) => [...h, frameMap].slice(-40));
  }, [frameMap]);

  const toggleMark = useCallback(() => {
    void run(async () => {
      const d = await api.mark(slug, frame, !marks.has(frame));
      clip.setMarks(new Set(d.marks));
    });
  }, [run, slug, frame, marks, clip]);

  /**
   * A step. In nav it moves the pointer; in Frame Editor the SAME buttons
   * insert or delete `count` frames on that side — that is the whole point of
   * the mode, and why it has to be impossible to miss which one is on.
   */
  const step = useCallback(
    (delta: number) => {
      if (mode === 'nav') {
        goto(frame + delta);
        return;
      }
      const count = Math.abs(delta);
      const side = delta < 0 ? 'left' : 'right';
      void run(async () => {
        snapshot();
        const d =
          sub === 'add'
            ? await api.dup(slug, frame, count, side)
            : await api.del(slug, frame, count, side);
        clip.applyEdit(d);
        setFrame(clamp(d.current));
        if (sub === 'sub' && d.actual !== undefined && d.actual < count) {
          setStatus(
            d.actual === 0
              ? `Nothing to take on that side — clamped at the edge.`
              : `Took ${d.actual} of ${count} — clamped at the edge.`,
          );
        } else {
          setStatus(null);
        }
      });
    },
    [mode, sub, goto, frame, run, snapshot, slug, clip, clamp],
  );

  const editZone = useCallback(
    (kind: 'dup' | 'del') => {
      const { a, b } = zone;
      const what = `frames ${a}–${b} (${b - a + 1} frames, ${((b - a + 1) / fps).toFixed(2)}s)`;
      if (
        !window.confirm(
          kind === 'dup'
            ? `Repeat ${what}?\n\nThe preview changes; the source file does not, until you Save.`
            : `Delete ${what}?\n\nThe preview changes; the source file does not, until you Save.`,
        )
      )
        return;
      void run(async () => {
        snapshot();
        const d =
          kind === 'dup'
            ? await api.dupSpan(slug, a, b)
            : await api.delSpan(slug, a, b);
        clip.applyEdit(d);
        setFrame(clamp(d.current));
        setStatus(
          `${kind === 'dup' ? 'Repeated' : 'Removed'} ${b - a + 1} frames` +
            (d.dropped_marks ? ` · ${d.dropped_marks} break point(s) dropped` : ''),
        );
      });
    },
    [zone, fps, run, snapshot, slug, clip, clamp],
  );

  const undo = useCallback(() => {
    const prev = history[history.length - 1];
    if (!prev) return;
    void run(async () => {
      const d = await api.restore(slug, prev);
      setHistory((h) => h.slice(0, -1));
      clip.applyEdit({ nb_frames: d.nb_frames, marks: d.marks });
      // Undo can take a clip all the way back to the file on disk, and only the
      // server knows when it has: `edited` is not derivable from the count.
      // Without this, Save stays armed with nothing to save.
      await clip.refreshMeta();
      setFrame((f) => Math.max(1, Math.min(d.nb_frames, f)));
      setStatus(`Undone — back to ${d.nb_frames} frames`);
    });
  }, [history, run, slug, clip]);

  // ── keyboard ────────────────────────────────────────────────────────────
  // Three speeds on one pair of keys, the cheapest gesture for the commonest
  // job:
  //   ←/→        one frame     — the frame-accurate work this tool exists for
  //   Shift+←/→  ten frames    — coarse scrubbing
  //   Alt+←/→    break point   — walking the cut to check every boundary
  // Alt is checked FIRST: without that, Alt+← would step a frame as well and
  // land one frame off the mark, which is the exact error being checked for.
  const jumpMark = useCallback(
    (dir: 1 | -1) => {
      const list = dir === 1 ? sortedMarks : [...sortedMarks].reverse();
      const next = list.find((m) => (dir === 1 ? m > frame : m < frame));
      if (next !== undefined) goto(next);
    },
    [sortedMarks, frame, goto],
  );

  const stepRef = useRef(step);
  stepRef.current = step;

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const el = e.target as HTMLElement | null;
      // A typed name is not a shortcut. Without this, naming a scene "add"
      // toggles the mode three times.
      if (el && /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)) return;
      if (e.key === 'ArrowLeft') {
        if (e.altKey) jumpMark(-1);
        else stepRef.current(e.shiftKey ? -10 : -1);
        e.preventDefault();
      }
      if (e.key === 'ArrowRight') {
        if (e.altKey) jumpMark(1);
        else stepRef.current(e.shiftKey ? 10 : 1);
        e.preventDefault();
      }
      if (e.key === ' ') {
        play.toggle();
        e.preventDefault();
      }
      if (e.key === 'm' || e.key === 'M') {
        toggleMark();
        e.preventDefault();
      }
      // Walk the break points themselves. Checking a cut means visiting every
      // boundary in turn to confirm it landed on the FIRST frame of the new
      // page.
      if (e.key === '[') {
        jumpMark(-1);
        e.preventDefault();
      }
      if (e.key === ']') {
        jumpMark(1);
        e.preventDefault();
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [jumpMark, play, toggleMark]);

  // ── render ──────────────────────────────────────────────────────────────
  if (clip.error) {
    return (
      <Box maw={700} mx="auto" px="md">
        <Alert color="red" title="That clip could not be opened">
          {clip.error}
        </Alert>
      </Box>
    );
  }
  if (!meta) {
    return (
      <Group justify="center" mt="xl" gap="xs">
        <Loader size="sm" />
        <Text c="dimmed">extracting…</Text>
      </Group>
    );
  }

  const here = segments.find((s) => frame >= s.start && frame <= s.end);
  // Boundary rules depend on what a click currently DOES. Navigation and
  // Subtract both need a real frame on that side. Add has no such limit —
  // extending a hold at either end of the clip is exactly what it is for.
  const adding = mode === 'frame-editor' && sub === 'add';

  return (
    <Box
      mx="auto"
      px="md"
      style={{
        width: meta.disp_w + 278 + 32,
        maxWidth: '100%',
        display: 'grid',
        gridTemplateColumns: `${meta.disp_w}px 264px`,
        gap: 14,
        alignItems: 'start',
      }}
    >
      <Stack gap={8} miw={0}>
        <Group gap={8} align="baseline" px={2}>
          <Text fz={12} c="dimmed" truncate>
            {meta.source_name}
          </Text>
          <Text fz={11} c="dimmed" ml="auto" className="num">
            {meta.fps}fps
          </Text>
        </Group>

        <Stage
          slug={slug}
          frame={frame}
          ext={meta.ext}
          ver={ver}
          w={meta.disp_w}
          h={meta.disp_h}
          marked={marks.has(frame)}
          hasAudio={meta.has_audio}
          audioRef={play.audioRef}
        />

        <Box className="rowbar">
          <Timeline
            frame={frame}
            total={total}
            segments={segments}
            marks={sortedMarks}
            onFrame={goto}
            fmtTime={fmtTime}
          />
        </Box>

        <NavRow
          frame={frame}
          total={total}
          timecode={fmtTime(frame)}
          totalTime={`${(total / fps).toFixed(3)}s`}
          segNow={here ? `segment ${here.n} of ${segments.length}` : ''}
          play={play}
          loop={loop}
          onLoop={setLoop}
          onStep={step}
          canBack={adding || frame > 1}
          canFwd={adding || frame < total}
        />

        <EditRow
          mode={mode}
          sub={sub}
          marked={marks.has(frame)}
          canUndo={history.length > 0}
          onMark={toggleMark}
          onMode={setMode}
          onSub={setSub}
          onZone={editZone}
          onUndo={undo}
          zoneLabel={`frames ${zone.a}–${zone.b}`}
        />

        {status && (
          <Text fz={12} c="yellow.4">
            {status}
          </Text>
        )}
        {error && (
          <Alert color="red" p="xs">
            <Text fz={12}>{error}</Text>
          </Alert>
        )}
        <Text fz={11} c="dimmed">
          Frame Editor edits the preview here. Cut and Save rebuild those frames
          from the ORIGINAL file — never a screenshot of this preview.
        </Text>
      </Stack>

      <Paper withBorder radius="md" p="xs">
        <Tabs value={tab} onChange={setTab} variant="pills">
          <Tabs.List grow mb="xs">
            <Tabs.Tab value="marks" fz={11}>
              Break points{marks.size > 0 ? ` (${marks.size})` : ''}
            </Tabs.Tab>
            <Tabs.Tab value="file" fz={11}>
              File{meta.edited ? ' •' : ''}
            </Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="marks">
            <MarksPanel
              slug={slug}
              marks={sortedMarks}
              segments={segments}
              frame={frame}
              fmtTime={fmtTime}
              onFrame={goto}
              onMarksChanged={(m) => clip.setMarks(new Set(m))}
            />
          </Tabs.Panel>

          <Tabs.Panel value="file">
            <FilePanel
              meta={meta}
              edited={meta.edited}
              onSaved={(msg) => {
                setStatus(msg);
                setHistory([]);
                void clip.reload();
              }}
              onCleared={() => {
                setStatus('Edits discarded — the preview is back to the file on disk.');
                setHistory([]);
                void clip.reload();
              }}
            />
          </Tabs.Panel>
        </Tabs>
      </Paper>
    </Box>
  );
}
