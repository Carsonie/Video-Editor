import { useState } from 'react';
import {
  Alert,
  Button,
  Divider,
  Group,
  Stack,
  Text,
  TextInput,
  Tooltip,
  UnstyledButton,
} from '@mantine/core';

import { api } from '../api';
import type { CutResponse } from '../types';
import type { Segment } from './Timeline';

/**
 * The drawer's first tab: the break points, what Cut would write, and the
 * hand-off that turns loose cuts into scenes.
 *
 * THE SEGMENT LIST SITS ABOVE THE BUTTON THAT WRITES IT. The durations drawn
 * over the timeline say the same thing in a shape you can point at; this one
 * you can read.
 */
export function MarksPanel({
  slug,
  marks,
  segments,
  frame,
  fmtTime,
  onFrame,
  onMarksChanged,
}: {
  slug: string;
  marks: number[];
  segments: Segment[];
  frame: number;
  fmtTime: (n: number) => string;
  onFrame: (n: number) => void;
  onMarksChanged: (marks: number[]) => void;
}) {
  const [cutting, setCutting] = useState(false);
  const [cut, setCut] = useState<CutResponse | null>(null);
  const [names, setNames] = useState<string[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const totalFrames = segments.reduce((a, s) => a + s.frames, 0);
  const totalDur = segments.reduce((a, s) => a + s.dur, 0);

  async function doCut() {
    setError(null);
    setStatus(null);
    setCutting(true);
    try {
      const d = await api.cut(slug);
      setCut(d);
      // One name per segment, and the hand-off refuses until every one is
      // filled — a scene with no name is a folder nothing can find.
      setNames(d.segments.map(() => ''));
      const bad = d.segments.filter((s) => s.error || s.warning);
      setStatus(
        `Wrote ${d.count} segment${d.count === 1 ? '' : 's'} as version ${d.version} into ${d.outdir}` +
          (bad.length ? ` — ${bad.length} with a warning` : ''),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setCutting(false);
    }
  }

  async function doHandoff() {
    if (!cut) return;
    setError(null);
    try {
      const d = await api.handoff(slug, cut.version, names);
      setStatus(
        `Handed off ${d.handed_off.length} scene(s) into ${d.into}` +
          (d.archived_to ? ` — the generation before it is in ${d.archived_to}` : ''),
      );
      setCut(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  const namesReady =
    names.length > 0 &&
    names.every((n) => /^[a-z0-9][a-z0-9-]{0,48}$/.test(n)) &&
    new Set(names).size === names.length;

  return (
    <Stack gap={8}>
      <Group justify="space-between">
        <Text fz={11} c="dimmed" tt="uppercase" fw={600}>
          {marks.length === 0
            ? 'No break points'
            : `${marks.length} break point${marks.length === 1 ? '' : 's'}`}
        </Text>
        <Tooltip label="Remove every break point">
          <Button
            size="compact-xs"
            disabled={marks.length === 0}
            onClick={() =>
              void api.clearMarks(slug).then((d) => onMarksChanged(d.marks))
            }
          >
            Clear all
          </Button>
        </Tooltip>
      </Group>

      {marks.length === 0 ? (
        <Text fz={12} c="dimmed">
          Move to a frame and press <b>Mark</b> (or <b>M</b>) to set a break point.
          Cutting splits the source FILE — never these preview frames.
        </Text>
      ) : (
        <Stack gap={2}>
          {marks.map((m) => (
            <UnstyledButton
              key={m}
              onClick={() => onFrame(m)}
              px={8}
              py={4}
              style={{
                borderRadius: 4,
                background: m === frame ? 'var(--panel2)' : undefined,
              }}
            >
              <Group justify="space-between">
                <Text fz={12} className="num">
                  frame {m}
                </Text>
                <Text fz={12} c="dimmed" className="num">
                  {fmtTime(m)}
                </Text>
              </Group>
            </UnstyledButton>
          ))}
        </Stack>
      )}

      <Divider my={4} />

      <Text fz={11} c="dimmed" tt="uppercase" fw={600}>
        Segments
      </Text>
      <Stack gap={2}>
        {segments.map((s) => (
          <Group key={s.n} justify="space-between">
            <Text
              fz={12}
              className="num"
              c={frame >= s.start && frame <= s.end ? undefined : 'dimmed'}
            >
              {s.n} · {s.start}–{s.end}
            </Text>
            <Text fz={12} c="dimmed" className="num">
              {s.frames}f · {s.dur.toFixed(2)}s
            </Text>
          </Group>
        ))}
      </Stack>
      <Text fz={11} c="dimmed" className="num">
        {segments.length} segment{segments.length === 1 ? '' : 's'} · {totalFrames} frames ·{' '}
        {totalDur.toFixed(2)}s
      </Text>

      <Divider my={4} />

      <Tooltip label="Cut the SOURCE FILE at every break point and write the pieces to dev/_cuts/. Reads the original with ffmpeg — never these preview frames. Cutting again keeps the earlier attempt and bumps its version.">
        <Button
          fullWidth
          loading={cutting}
          disabled={marks.length === 0}
          onClick={() => void doCut()}
        >
          ✂️ Cut into segments
        </Button>
      </Tooltip>

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

      {cut && (
        <>
          <Divider my={4} />
          <Text fz={11} c="dimmed" tt="uppercase" fw={600}>
            Hand off to dev
          </Text>
          <Text fz={11} c="dimmed">
            Name each piece and it becomes a scene: dev/03-&lt;name&gt;/segment-v1.mp4,
            with a row in script.json to match. Lower-case letters, digits and hyphens.
          </Text>
          {cut.segments.map((s, i) => (
            <TextInput
              key={s.name}
              size="xs"
              label={s.name}
              placeholder="catalogue-search"
              value={names[i] ?? ''}
              error={
                names[i] && !/^[a-z0-9][a-z0-9-]{0,48}$/.test(names[i])
                  ? 'lower-case letters, digits and hyphens'
                  : undefined
              }
              onChange={(e) => {
                const next = [...names];
                next[i] = e.currentTarget.value;
                setNames(next);
              }}
              styles={{ label: { fontSize: 11, color: 'var(--dim)' } }}
            />
          ))}
          <Tooltip label="Copy these segments into dev/ as named scenes, and write a scene row for each into script.json. This is where the Segment and Avatar Editor picks the work up. dev holds ONE generation — the one it replaces is archived first.">
            <Button fullWidth disabled={!namesReady} onClick={() => void doHandoff()}>
              → Hand off to dev
            </Button>
          </Tooltip>
        </>
      )}
    </Stack>
  );
}
