import { Button, Checkbox, Group, NativeSelect, Stack, Text, Tooltip } from '@mantine/core';

import type { Playback } from '../hooks/usePlayback';

/**
 * Row 2 of the toolbar: HOW YOU MOVE.
 *
 * Split out from the edit controls for a plain reason — the frame counter used
 * to sit in the same row as the delete buttons.
 */
export function NavRow({
  frame,
  total,
  timecode,
  totalTime,
  segNow,
  play,
  loop,
  onLoop,
  onStep,
  canBack,
  canFwd,
}: {
  frame: number;
  total: number;
  timecode: string;
  totalTime: string;
  segNow: string;
  play: Playback;
  loop: boolean;
  onLoop: (v: boolean) => void;
  onStep: (delta: number) => void;
  canBack: boolean;
  canFwd: boolean;
}) {
  return (
    <Group className="rowbar" gap={6} wrap="wrap">
      <Tooltip label="Play / pause (space)">
        <Button onClick={play.toggle} w={34}>
          {play.playing ? '❚❚' : '▶'}
        </Button>
      </Tooltip>
      <Tooltip label={play.muted ? 'Unmute' : 'Mute'}>
        <Button onClick={() => play.setMuted(!play.muted)} w={34}>
          {play.muted ? '🔇' : '🔊'}
        </Button>
      </Tooltip>
      <Tooltip label="Playback speed. Slow to judge a seam; 2x to skim. It changes no frame and no file.">
        <NativeSelect
          size="xs"
          w={70}
          value={String(play.rate)}
          onChange={(e) => play.setRate(Number(e.currentTarget.value))}
          data={['2', '1', '0.5', '0.25', '0.125'].map((v) => ({
            value: v,
            label: `${v}x`,
          }))}
        />
      </Tooltip>

      <Tooltip label="Back 100 frames">
        <Button disabled={!canBack} onClick={() => onStep(-100)}>«100</Button>
      </Tooltip>
      <Tooltip label="Back 10 frames (Shift+←)">
        <Button disabled={!canBack} onClick={() => onStep(-10)}>«10</Button>
      </Tooltip>
      <Tooltip label="Previous frame (←)">
        <Button disabled={!canBack} onClick={() => onStep(-1)} w={34}>◀</Button>
      </Tooltip>
      <Tooltip label="Next frame (→)">
        <Button disabled={!canFwd} onClick={() => onStep(1)} w={34}>▶</Button>
      </Tooltip>
      <Tooltip label="Forward 10 frames (Shift+→)">
        <Button disabled={!canFwd} onClick={() => onStep(10)}>10»</Button>
      </Tooltip>
      <Tooltip label="Forward 100 frames">
        <Button disabled={!canFwd} onClick={() => onStep(100)}>100»</Button>
      </Tooltip>

      <Tooltip label="Play only the zone — the span between the break points either side of the pointer — over and over. With nothing marked the zone is the whole clip. Judging a cut point is watching the same two seconds repeatedly, which is what this is for.">
        <Checkbox
          size="xs"
          checked={loop}
          onChange={(e) => onLoop(e.currentTarget.checked)}
          label="↻ Loop Zone"
          styles={{ label: { fontSize: 12, paddingLeft: 6 } }}
        />
      </Tooltip>

      <Stack gap={0} ml="auto" align="flex-end">
        <Text fz={12} className="num">
          frame {frame} / {total} · {timecode}
        </Text>
        <Text fz={11} c="dimmed" className="num">
          total <b>{totalTime}</b>
        </Text>
        {segNow && (
          <Text fz={11} c="dimmed" className="num">
            {segNow}
          </Text>
        )}
      </Stack>
    </Group>
  );
}
