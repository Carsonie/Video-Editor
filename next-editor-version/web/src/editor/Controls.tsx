import { Button, Checkbox, Group, NativeSelect, Stack, Text, Tooltip } from '@mantine/core';

import type { Playback } from '../hooks/usePlayback';

/** Which tracks join and split act on. A track NOT picked is not carried into
 *  the result — that is the whole meaning of the choice, and why the button
 *  takes that track's colour when one is picked alone. */
export type TrackPick = 'both' | 'base' | 'overlay';

const trackColour: Record<TrackPick, string | undefined> = {
  both: 'teal.7',
  base: 'teal.9',
  overlay: 'grape.7',
};

export function Controls({
  play,
  loop,
  onLoop,
  onStep,
  onScene,
  onMark,
  marked,
  onJumpMark,
  joinTrack,
  splitTrack,
  onJoinTrack,
  onSplitTrack,
  onJoin,
  onSplit,
  canJoin,
  canSplit,
  joinWhy,
  splitWhy,
  onFrame,
  onZone,
  onCopy,
  onPaste,
  canPaste,
  onCut,
  onSave,
  canSave,
  canEdit,
  editWhy,
  busy,
}: {
  play: Playback;
  loop: boolean;
  onLoop: (v: boolean) => void;
  onStep: (d: number) => void;
  onScene: (d: 1 | -1) => void;
  onMark: () => void;
  marked: boolean;
  onJumpMark: (d: 1 | -1) => void;
  joinTrack: TrackPick;
  splitTrack: TrackPick;
  onJoinTrack: (t: TrackPick) => void;
  onSplitTrack: (t: TrackPick) => void;
  onJoin: () => void;
  onSplit: () => void;
  canJoin: boolean;
  canSplit: boolean;
  joinWhy: string;
  splitWhy: string;
  onFrame: (kind: 'dup' | 'del') => void;
  onZone: (kind: 'dup' | 'del') => void;
  onCopy: (alsoMac: boolean) => void;
  onPaste: () => void;
  canPaste: boolean;
  onCut: () => void;
  onSave: () => void;
  canSave: boolean;
  canEdit: boolean;
  editWhy: string;
  busy: string | null;
}) {
  return (
    <Stack gap={6}>
      {/* 1 — moving through it */}
      <Group className="rowbar" gap={5} wrap="wrap">
        <Tooltip label="Play or pause the timeline (space). It starts from wherever the pointer is, so drag it first to watch a particular moment.">
          <Button onClick={play.toggle} w={70}>
            {play.playing ? '❚❚ Pause' : '▶ Play'}
          </Button>
        </Tooltip>
        <Tooltip label="Mute the narration. The picture is unaffected — useful when you are judging motion and the voice is a distraction.">
          <Button w={34} onClick={() => play.setMuted(!play.muted)}>
            {play.muted ? '🔇' : '🔊'}
          </Button>
        </Tooltip>
        <Tooltip label="Playback speed. Slow right down to judge a seam: at 25fps a cut is over in 40ms, and 0.125x stretches that to 320ms. Below 0.25x the browser will not play audio, so those speeds are silent.">
          <NativeSelect
            size="xs"
            w={70}
            value={String(play.rate)}
            onChange={(e) => play.setRate(Number(e.currentTarget.value))}
            data={['2', '1', '0.5', '0.25', '0.125'].map((v) => ({ value: v, label: `${v}x` }))}
          />
        </Tooltip>
        <Tooltip label="Back 10 frames">
          <Button onClick={() => onStep(-10)}>◀◀</Button>
        </Tooltip>
        <Tooltip label="Back one frame (←). This is the control for finding the exact frame a change happens on.">
          <Button onClick={() => onStep(-1)} w={34}>◀</Button>
        </Tooltip>
        <Tooltip label="Forward one frame (→). Step through a transition one frame at a time to see where it really begins.">
          <Button onClick={() => onStep(1)} w={34}>▶</Button>
        </Tooltip>
        <Tooltip label="Forward 10 frames">
          <Button onClick={() => onStep(10)}>▶▶</Button>
        </Tooltip>
        <Tooltip label="Jump to the start of the previous scene (keyboard: [ )">
          <Button onClick={() => onScene(-1)}>|◀ scene</Button>
        </Tooltip>
        <Tooltip label="Jump to the start of the next scene (keyboard: ] )">
          <Button onClick={() => onScene(1)}>scene ▶|</Button>
        </Tooltip>
      </Group>

      {/* 2 — marks, and the two operations that rewrite the scene list */}
      <Group className="rowbar" gap={5} wrap="wrap">
        <Tooltip label="Mark or unmark this frame (m). Marks divide a scene into ZONES — the span between two marks — which is what Loop Zone plays and what ＋ Zone and － Zone act on.">
          <Button
            variant={marked ? 'filled' : 'default'}
            color={marked ? 'mark.5' : undefined}
            onClick={onMark}
          >
            ◆ Mark / Unmark
          </Button>
        </Tooltip>
        <Tooltip label="Jump back to the previous mark. Marks show as ticks on the bar; you can also click a tick directly.">
          <Button onClick={() => onJumpMark(-1)}>[ prev mark</Button>
        </Tooltip>
        <Tooltip label="Jump forward to the next mark.">
          <Button onClick={() => onJumpMark(1)}>next mark ]</Button>
        </Tooltip>
        <Tooltip label="Loop the zone the pointer is inside — the span between the marks either side of it. With no marks it loops the whole scene. Turn this on to watch one seam over and over while you trim it.">
          <Checkbox
            size="xs"
            checked={loop}
            onChange={(e) => onLoop(e.currentTarget.checked)}
            label="↻ Loop Zone"
            styles={{ label: { fontSize: 12, paddingLeft: 6 } }}
          />
        </Tooltip>

        <Group gap={0} ml="auto">
          <Tooltip label={canJoin ? 'Join every scene on the timeline into ONE new scene. You are asked to name it first and shown exactly what will be merged. Scene numbers are rewritten 1..N afterwards, so from then on scenes must be saved as a set.' : joinWhy}>
            <Button
              variant={canJoin ? 'filled' : 'default'}
              color={canJoin ? trackColour[joinTrack] : undefined}
              disabled={!canJoin}
              loading={busy === 'join'}
              onClick={onJoin}
              style={{ borderTopRightRadius: 0, borderBottomRightRadius: 0 }}
            >
              Join
            </Button>
          </Tooltip>
          <Tooltip label="Which tracks the join acts on. Both is the normal case; pick one alone and the button takes that track's colour. A track you do not pick is NOT carried into the joined scene.">
            <NativeSelect
              size="xs"
              w={86}
              value={joinTrack}
              onChange={(e) => onJoinTrack(e.currentTarget.value as TrackPick)}
              data={[
                { value: 'both', label: 'both' },
                { value: 'base', label: 'segment' },
                { value: 'overlay', label: 'overlay' },
              ]}
              styles={{ input: { borderTopLeftRadius: 0, borderBottomLeftRadius: 0 } }}
            />
          </Tooltip>
        </Group>

        <Group gap={0}>
          <Tooltip label={canSplit ? 'Split the scene under the pointer in two, at the frame on screen. You are asked to name both halves. Every scene is renumbered afterwards, so from then on scenes must be saved as a set. THE NARRATION CANNOT BE SPLIT — the whole line stays with the first half.' : splitWhy}>
            <Button
              variant={canSplit ? 'filled' : 'default'}
              color={canSplit ? trackColour[splitTrack] : undefined}
              disabled={!canSplit}
              loading={busy === 'split'}
              onClick={onSplit}
              style={{ borderTopRightRadius: 0, borderBottomRightRadius: 0 }}
            >
              Split
            </Button>
          </Tooltip>
          <Tooltip label="Which tracks the split acts on. A track you do not pick stays whole and is not carried into either half.">
            <NativeSelect
              size="xs"
              w={86}
              value={splitTrack}
              onChange={(e) => onSplitTrack(e.currentTarget.value as TrackPick)}
              data={[
                { value: 'both', label: 'both' },
                { value: 'base', label: 'segment' },
                { value: 'overlay', label: 'overlay' },
              ]}
              styles={{ input: { borderTopLeftRadius: 0, borderBottomLeftRadius: 0 } }}
            />
          </Tooltip>
        </Group>
      </Group>

      {/* 3 — changing the frames */}
      <Group className="rowbar" gap={5} wrap="wrap">
        <Tooltip label={canEdit ? 'Duplicate the frame on screen, on whichever tracks this scene has ticked. The copy becomes the frame you are looking at. Use it to hold a still moment for longer.' : editWhy}>
          <Button disabled={!canEdit} onClick={() => onFrame('dup')}>＋ Frame</Button>
        </Tooltip>
        <Tooltip label={canEdit ? 'Delete the frame on screen, on whichever tracks this scene has ticked. The next frame moves into its place, so the timeline appears to step forward.' : editWhy}>
          <Button disabled={!canEdit} onClick={() => onFrame('del')}>－ Frame</Button>
        </Tooltip>
        <Tooltip label={canEdit ? 'Repeat the whole marked zone once more, on the ticked tracks. Useful for stretching a settled stretch to fit a longer line of narration.' : editWhy}>
          <Button disabled={!canEdit} onClick={() => onZone('dup')}>＋ Zone</Button>
        </Tooltip>
        <Tooltip label={canEdit ? 'Remove the whole marked zone from the ticked tracks. Mark either side of what you want gone, then press this.' : editWhy}>
          <Button disabled={!canEdit} onClick={() => onZone('del')}>－ Zone</Button>
        </Tooltip>

        <Text c="dimmed" fz={14} px={4}>│</Text>

        <Tooltip label="Copy the frame on screen. It is remembered by POSITION, not as a picture — pasting it later inserts the very same frame, with no re-encoding. Hold Shift as you click to put the picture on the Mac clipboard as well.">
          <Button onClick={(e) => onCopy(e.shiftKey)}>⧉ Copy</Button>
        </Tooltip>
        <Tooltip label={canPaste ? 'Paste the copied frame in after the frame on screen, on the ticked tracks.' : 'Nothing is copied yet — press Copy first.'}>
          <Button disabled={!canPaste} onClick={onPaste}>⧉ Paste</Button>
        </Tooltip>

        <Text c="dimmed" fz={14} px={4}>│</Text>

        <Tooltip label="Cut this scene into separate files at every mark, writing them to the video's dev/_cuts/. It never changes the scene you are editing — it only writes new numbered files.">
          <Button loading={busy === 'cut'} onClick={onCut}>✂ Cut scene</Button>
        </Tooltip>
        <Tooltip label={canSave ? "Write this scene's edits back over its file in sandbox/. The current file is archived to z_History/ first. This is the ONE control here that changes a file you already had." : 'Nothing to save on this scene — or the scenes have been renumbered, in which case they have to be saved as a set.'}>
          <Button disabled={!canSave} loading={busy === 'save'} onClick={onSave}>
            💾 Save scene
          </Button>
        </Tooltip>
      </Group>
    </Stack>
  );
}
