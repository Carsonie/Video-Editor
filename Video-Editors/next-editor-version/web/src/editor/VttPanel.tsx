import { useEffect, useState } from 'react';
import { Box, Group, Stack, Text, Textarea, Tooltip } from '@mantine/core';

import type { SeqScene, VttRow } from '../types';

/**
 * The VTT — Video Timing Table, not WebVTT subtitles.
 *
 * What it answers is one question: does the line FIT the footage? The gap is
 * clip length minus spoken length, and a NEGATIVE gap is the defect that ships
 * silently — the line is still being said when the picture has moved on.
 *
 * The clip length comes from the TIMELINE, not from the file on disk. Reading
 * the file is right for a report and wrong for an editor: a gap that does not
 * move while you add frames is just a lie with a decimal point.
 *
 * A line is edited IN PLACE because rewriting a line is free and rendering it
 * is not. script.json is the single source of truth for the copy, and the
 * render tool reads the same field — so editing here is editing what HeyGen
 * will be paid to say.
 */
export function VttPanel({
  rows,
  wps,
  scenes,
  currentN,
  onSave,
}: {
  rows: VttRow[];
  wps: number;
  scenes: SeqScene[];
  currentN: number | null;
  onSave: (n: number, line: string) => Promise<void>;
}) {
  if (rows.length === 0) {
    return (
      <Text fz={11} c="dimmed">
        This store has no video/script.json, so there are no lines to time.
      </Text>
    );
  }

  const onTimeline = new Map(scenes.map((s) => [s.n, s]));
  let clipTotal = 0;
  let spokenTotal = 0;
  for (const r of rows) {
    const s = onTimeline.get(r.n);
    if (!s) continue;
    clipTotal += s.base_n / s.fps;
    spokenTotal += r.words / wps + r.pause;
  }

  return (
    <Stack gap={4}>
      <Group gap={8}>
        <Text fz={12} fw={600} c="dimmed" tt="uppercase">
          VTT
        </Text>
        <Text fz={11} c="dimmed" className="num">
          {clipTotal.toFixed(2)}s of footage · {spokenTotal.toFixed(2)}s spoken ·{' '}
          <b style={{ color: clipTotal - spokenTotal < 0 ? 'var(--bad)' : undefined }}>
            {(clipTotal - spokenTotal >= 0 ? '+' : '') + (clipTotal - spokenTotal).toFixed(2)}s
          </b>{' '}
          at {wps} words/sec
        </Text>
      </Group>

      {rows.map((r) => (
        <VttLine
          key={r.n}
          row={r}
          wps={wps}
          scene={onTimeline.get(r.n) ?? null}
          here={r.n === currentN}
          onSave={onSave}
        />
      ))}
    </Stack>
  );
}

function VttLine({
  row,
  wps,
  scene,
  here,
  onSave,
}: {
  row: VttRow;
  wps: number;
  scene: SeqScene | null;
  here: boolean;
  onSave: (n: number, line: string) => Promise<void>;
}) {
  const [text, setText] = useState(row.line);
  const [saving, setSaving] = useState(false);
  useEffect(() => setText(row.line), [row.line]);

  const clip = scene ? scene.base_n / scene.fps : null;
  const words = text.trim().split(/\s+/).filter((w) => /[A-Za-z0-9]/.test(w)).length;
  const spoken = words / wps + row.pause;
  const gap = clip === null ? null : clip - spoken;
  const dirty = text !== row.line;

  return (
    <Box
      px={6}
      py={4}
      style={{
        borderRadius: 4,
        background: here ? 'var(--panel2)' : undefined,
        borderLeft: here ? '2px solid var(--mark)' : '2px solid transparent',
        opacity: scene ? 1 : 0.5,
      }}
    >
      <Group gap={8} wrap="nowrap" align="baseline">
        <Text fz={11} c="dimmed" className="num" w={16}>
          {row.n}
        </Text>
        <Text fz={11} c="dimmed" truncate w={110}>
          {row.label}
        </Text>
        <Textarea
          autosize
          minRows={1}
          size="xs"
          style={{ flex: '1 1 0', minWidth: 0 }}
          value={text}
          placeholder={row.todo ? 'the narration stayed with the other half — write this one' : ''}
          onChange={(e) => setText(e.currentTarget.value)}
          onBlur={() => {
            if (!dirty) return;
            setSaving(true);
            void onSave(row.n, text).finally(() => setSaving(false));
          }}
          styles={{ input: { fontSize: 12, background: 'transparent' } }}
        />
        <Tooltip
          label={
            gap === null
              ? 'This scene is not on the timeline, so there is no length to compare against.'
              : gap < 0
                ? `OVERRUNS by ${(-gap).toFixed(2)}s — the line is still being said when the picture has moved on. Lengthen the scene, or shorten the line.`
                : `${gap.toFixed(2)}s of footage left after the line is spoken.`
          }
        >
          <Text
            fz={11}
            w={54}
            ta="right"
            className="num"
            c={gap === null ? 'dimmed' : gap < 0 ? 'red.4' : gap > 2.5 ? 'yellow.4' : 'dimmed'}
          >
            {saving ? '…' : gap === null ? '—' : `${gap >= 0 ? '+' : ''}${gap.toFixed(2)}s`}
          </Text>
        </Tooltip>
      </Group>
    </Box>
  );
}
